# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le choix de `ansible_host`, et l'explication de ce choix.

C'est la décision la plus lourde de conséquences du plugin : elle détermine
par où Ansible joindra la machine. Elle est donc **pure**, aucun appel d'API,
aucune lecture de configuration globale, et elle **s'explique** : la
sélection rend la règle et la famille à côté de l'adresse, pour que le mode
debug puisse répondre à « pourquoi cette IP a-t-elle été choisie ».

Deux règles, et la seconde l'emporte quand elle est demandée :

* **par famille** : on suit l'ordre de `address_priority` et on prend la
  première adresse disponible ;
* **par point d'entrée** : idée reprise du plugin antérieur du mainteneur. Un
  parc Outscale typique a un bastion avec une adresse publique et des
  machines derrière, sans. Avec `entry_role`, la machine dont le tag `role`
  porte ce rôle est jointe par son adresse publique, et toutes les autres par
  leur adresse privée, à atteindre par `ProxyJump`. Ça remplace un `compose`
  Jinja conditionnel que chacun réécrivait.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import InventoryHost

#: Les familles d'adresses que l'on sait ordonner. Un nom hors de cette liste
#: est une faute de configuration, pas un repli silencieux.
FAMILIES: tuple[str, ...] = ("public_ipv4", "private_ipv4")

#: L'ordre par défaut : l'adresse publique d'abord. Chez Outscale, une machine
#: hors Net n'a pas d'adresse privée routable depuis ailleurs, et un
#: contrôleur qui gère un parc depuis l'extérieur passe par le public.
DEFAULT_PRIORITY: tuple[str, ...] = ("public_ipv4", "private_ipv4")

#: L'ordre d'un point d'entrée, et celui de ce qui est derrière lui.
ENTRY_PRIORITY: tuple[str, ...] = ("public_ipv4", "private_ipv4")
BEHIND_PRIORITY: tuple[str, ...] = ("private_ipv4", "public_ipv4")

#: Le tag qui porte le rôle, par défaut.
DEFAULT_ENTRY_TAG = "role"


@dataclass(frozen=True)
class AddressPolicy:
    """Ce que l'utilisateur a demandé, sous une forme que la fonction sait lire."""

    priority: tuple[str, ...] = DEFAULT_PRIORITY
    #: Le rôle des points d'entrée. Quand il est donné, il décide de l'ordre
    #: des familles à la place de `priority`.
    entry_role: str | None = None
    entry_tag: str = DEFAULT_ENTRY_TAG

    def families(self) -> tuple[str, ...]:
        """Les familles retenues, dans l'ordre, sans les inconnues."""
        return tuple(nom for nom in self.priority if nom in FAMILIES)

    def families_for(self, tags: Mapping[str, str]) -> tuple[tuple[str, ...], str]:
        """L'ordre des familles pour cette machine, et la règle qui l'a donné."""
        if self.entry_role is None:
            return self.families(), "address_priority"
        if str(tags.get(self.entry_tag, "") or "") == self.entry_role:
            return ENTRY_PRIORITY, f"point d'entrée ({self.entry_tag}={self.entry_role})"
        return BEHIND_PRIORITY, f"derrière le point d'entrée ({self.entry_tag}!={self.entry_role})"


@dataclass(frozen=True)
class AddressSelection:
    """L'adresse choisie, et de quoi expliquer pourquoi."""

    address: str | None
    #: `public_ipv4`, `private_ipv4`, ou la raison de l'échec.
    source: str
    #: La règle qui a fixé l'ordre : `address_priority` ou le point d'entrée.
    rule: str = "address_priority"
    #: Ce qui a été regardé, dans l'ordre, avant de trancher.
    considered: tuple[str, ...] = ()

    @property
    def found(self) -> bool:
        return self.address is not None

    def explain(self, host_name: str) -> str:
        """Une ligne lisible pour le mode debug."""
        if not self.found:
            return (
                f"{host_name}: aucune adresse ({self.source}), "
                f"examiné {list(self.considered)} selon {self.rule}"
            )
        return f"{host_name}: {self.address} par {self.source}, selon {self.rule}"


def _from_families(
    familles: tuple[str, ...],
    source: dict[str, tuple[str, ...]],
) -> tuple[str, str] | None:
    """La première adresse non vide, dans l'ordre demandé."""
    for famille in familles:
        adresses = source.get(famille, ())
        if adresses:
            return adresses[0], famille
    return None


def select_ansible_host(host: InventoryHost, policy: AddressPolicy) -> AddressSelection:
    """Choisit l'adresse par laquelle Ansible joindra cette machine.

    Aucune adresse trouvée n'est un résultat, pas une erreur : c'est
    l'appelant qui décide d'écarter le host ou de le garder sans
    `ansible_host`.
    """
    familles, regle = policy.families_for(host.tags)
    disponibles = {"public_ipv4": host.public_ipv4, "private_ipv4": host.private_ipv4}
    trouve = _from_families(familles, disponibles)
    if trouve is None:
        return AddressSelection(
            address=None,
            source="aucune adresse dans les familles demandées",
            rule=regle,
            considered=familles,
        )
    adresse, famille = trouve
    return AddressSelection(address=adresse, source=famille, rule=regle, considered=familles)
