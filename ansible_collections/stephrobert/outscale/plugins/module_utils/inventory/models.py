# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le modèle normalisé de l'inventaire, et lui seul.

Aucune réponse brute de l'API Outscale ne traverse cette frontière. Un
provider traduit ce que son API rend en `InventoryHost` ; tout ce qui vient
après (adresse, nom d'hôte, groupes, variables) ne connaît que ce modèle.
C'est ce qui permet d'ajouter un produit sans toucher au cœur.

**Ce que le contrat d'Outscale impose au modèle**, mesuré sur le schéma de la
machine virtuelle du contrat versionné :

* des **tags** en liste de paires `{Key, Value}`, et non un dictionnaire ; le
  modèle les porte en dictionnaire, parce qu'un nom d'hôte se lit par clé
  (`tag:Name`) et qu'un groupe se nomme par paire ;
* deux niveaux de lieu : la **région**, qui est dans l'hôte de l'API et non
  dans la réponse, et la **sous-région** (`Placement.SubregionName`), qui y
  est ;
* une adresse publique au plus, et des adresses privées portées par les
  interfaces réseau ; le modèle garde des tuples dans les deux cas, parce
  qu'un produit futur peut en porter plusieurs et que le cœur ne doit pas
  changer ;
* un réseau (`NetId`) et un sous-réseau (`SubnetId`), qui sont les découpages
  qu'un opérateur cible, et des groupes de sécurité.

Les dataclasses sont gelées et les collections sont des tuples : un
inventaire immuable se compare, se hache et se sérialise sans surprise, ce
qui est la condition d'un cache honnête.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InventoryHost:
    """Une ressource sur laquelle Ansible peut vouloir agir.

    « Vouloir agir » et non « pouvoir se connecter » : un host sans route SSH
    reste utile, parce qu'un playbook peut le piloter par les modules Day-2 en
    `delegate_to: localhost`. C'est pourquoi `id` et `product` sont
    obligatoires là où l'adresse ne l'est pas.
    """

    id: str
    product: str
    name: str | None = None

    region: str | None = None
    subregion: str | None = None
    state: str | None = None

    #: Les tags, une clé et une valeur.
    tags: Mapping[str, str] = field(default_factory=dict)

    public_ipv4: tuple[str, ...] = ()
    private_ipv4: tuple[str, ...] = ()

    net_id: str | None = None
    subnet_id: str | None = None
    security_group_ids: tuple[str, ...] = ()

    #: Ce qui n'appartient qu'à ce produit, exposé à plat sous le préfixe des
    #: hostvars. Le provider nomme les clés ; le cœur ne les connaît pas.
    metadata: Mapping[str, Any] = field(default_factory=dict)

    #: La réponse brute, seulement si l'utilisateur l'a demandée.
    raw: Any | None = None

    @property
    def tag_pairs(self) -> tuple[str, ...]:
        """Les tags sous la forme `clé=valeur`, triés : ce qu'un rapport lit
        sans connaître la forme du dictionnaire."""
        return tuple(sorted(f"{cle}={valeur}" for cle, valeur in self.tags.items()))


@dataclass(frozen=True)
class ProviderResult:
    """Ce qu'un provider rend : des hosts, et ce qui s'est mal passé.

    Les avertissements et les erreurs font partie du résultat, pas d'un effet
    de bord. Un provider qui échoue en silence rend un inventaire incomplet
    avec un code de retour 0.
    """

    hosts: tuple[InventoryHost, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    #: Nombre d'appels d'API réellement effectués, pages comprises.
    api_calls: int = 0

    def merge(self, other: ProviderResult) -> ProviderResult:
        return ProviderResult(
            hosts=(*self.hosts, *other.hosts),
            warnings=(*self.warnings, *other.warnings),
            errors=(*self.errors, *other.errors),
            api_calls=self.api_calls + other.api_calls,
        )
