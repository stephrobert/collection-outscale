# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ce que l'utilisateur a demandé, lu une fois et validé une fois.

Le plugin lit ses options par `self.get_option` ; cette couche les transforme
en objets typés que les autres couches savent consommer. Elle ne connaît ni
Ansible ni le SDK, donc elle se teste avec un simple dictionnaire.

Elle porte aussi la clé de cache : tout ce qui change le résultat entre dans
la clé, l'identité du compte comprise, par son empreinte. Deux exécutions sur
deux comptes sans profil déclaré partageraient sinon le même parc en cache.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .address import DEFAULT_ENTRY_TAG, DEFAULT_PRIORITY, FAMILIES, AddressPolicy
from .filtering import Filters
from .groups import known_axes
from .hostname import is_known_source

#: Les axes de groupes proposés par défaut. Assez pour reconnaître son parc,
#: pas assez pour produire des centaines de groupes vides.
DEFAULT_GROUP_BY: tuple[str, ...] = ("region", "subregion", "state", "tags")

#: Les sources de nom d'hôte par défaut. Le tag `Name` d'abord, l'identifiant
#: en dernier recours : un nom d'hôte qui est une adresse change dès que
#: l'adresse change.
DEFAULT_HOSTNAMES: tuple[str, ...] = ("tag:Name", "id")


class ConfigError(ValueError):
    """La configuration demande quelque chose que le plugin ne sait pas faire."""


@dataclass(frozen=True)
class InventoryConfig:
    """La configuration entière, sous une forme que les couches consomment."""

    regions: tuple[str, ...]
    #: Les filtres de l'API, tels quels, avec le vocabulaire du contrat.
    api_filters: Mapping[str, Any]
    hostnames: tuple[str, ...]
    address: AddressPolicy
    require_address: bool
    group_by: tuple[str, ...]
    filters: Filters
    include_raw: bool
    strict: bool

    def cache_fingerprint(self, api_url: str | None, identity: str | None = None) -> str:
        """Une empreinte de tout ce qui change le résultat.

        Seule l'empreinte de l'identité entre ici, jamais sa valeur. `strict`
        en fait partie : il décide si une découverte partielle échoue ou
        passe, donc il change le résultat.
        """
        materiel = {
            "api_url": api_url,
            "identity": hashlib.sha256((identity or "").encode("utf-8")).hexdigest()[:16],
            "regions": self.regions,
            "api_filters": dict(self.api_filters),
            "hostnames": self.hostnames,
            "address": [self.address.priority, self.address.entry_role, self.address.entry_tag],
            "require_address": self.require_address,
            "group_by": self.group_by,
            "filters": [
                dict(self.filters.tags),
                self.filters.tags_match,
                self.filters.states,
                dict(self.filters.exclude_tags),
                self.filters.exclude_ids,
            ],
            "include_raw": self.include_raw,
            "strict": self.strict,
        }
        serialise = json.dumps(materiel, sort_keys=True, default=str)
        return hashlib.sha256(serialise.encode("utf-8")).hexdigest()[:16]


def _liste(valeur: Any) -> tuple[str, ...]:
    if valeur is None:
        return ()
    if isinstance(valeur, str):
        return (valeur,)
    return tuple(str(item) for item in valeur)


def _tags(valeur: Any, option: str) -> dict[str, str]:
    """Un dictionnaire de tags, une valeur vide voulant dire « la clé existe »."""
    if not valeur:
        return {}
    if not isinstance(valeur, Mapping):
        raise ConfigError(f"`{option}` est un dictionnaire, pas {type(valeur).__name__}")
    return {str(cle): "" if item is None else str(item) for cle, item in valeur.items()}


def _api_filters(valeur: Any) -> dict[str, Any]:
    """Les filtres de l'API, vérifiés dans leur forme seulement.

    Leurs noms viennent du contrat, et c'est l'API qui les juge : un nom
    qu'elle ne connaît pas rend un 400 qui le dit, et le plugin le
    rapporte tel quel. Les valider ici demanderait une copie du contrat dans
    le plugin, qui vieillirait.
    """
    if not valeur:
        return {}
    if not isinstance(valeur, Mapping):
        raise ConfigError(f"`filters` est un dictionnaire, pas {type(valeur).__name__}")
    return {str(cle): item for cle, item in valeur.items()}


def from_options(
    get_option: Callable[[str], Any],
    extra_axes: Mapping[str, str] | None = None,
) -> InventoryConfig:
    """Lit et valide les options, et refuse ce qu'elle ne sait pas faire.

    Un nom inconnu dans `group_by`, `hostnames` ou `address_priority` est une
    faute de configuration. L'ignorer produirait un inventaire silencieusement
    différent de ce qui a été demandé. `extra_axes` est ce que le provider
    ajoute aux axes du cœur ; le cœur ne les nomme pas.
    """
    axes_connus = known_axes(extra_axes)
    axes = _liste(get_option("group_by")) or DEFAULT_GROUP_BY
    hors_axes = sorted(set(axes) - set(axes_connus))
    if hors_axes:
        raise ConfigError(
            f"axe(s) de groupe inconnu(s) : {hors_axes}. Connus : {list(axes_connus)}"
        )

    priorite = _liste(get_option("address_priority")) or DEFAULT_PRIORITY
    hors_familles = sorted(set(priorite) - set(FAMILIES))
    if hors_familles:
        raise ConfigError(
            f"famille(s) d'adresse inconnue(s) : {hors_familles}. Connues : {list(FAMILIES)}"
        )

    sources = _liste(get_option("hostnames")) or DEFAULT_HOSTNAMES
    hors_sources = sorted(nom for nom in sources if not is_known_source(nom))
    if hors_sources:
        raise ConfigError(
            f"source(s) de nom d'hôte inconnue(s) : {hors_sources}. "
            f"Connues : {list(DEFAULT_HOSTNAMES)}, `name`, les familles d'adresses, "
            "et `tag:<clé>`"
        )

    correspondance = get_option("tags_match") or "any"
    if correspondance not in ("any", "all"):
        raise ConfigError(f"tags_match vaut '{correspondance}', attendu 'any' ou 'all'")

    role = get_option("entry_role")
    role = str(role) if role else None
    tag_du_role = str(get_option("entry_tag") or DEFAULT_ENTRY_TAG)
    if not tag_du_role.strip():
        raise ConfigError("entry_tag est vide : le rôle doit se lire dans un tag nommé")

    return InventoryConfig(
        regions=_liste(get_option("regions")),
        api_filters=_api_filters(get_option("filters")),
        hostnames=sources,
        address=AddressPolicy(priority=tuple(priorite), entry_role=role, entry_tag=tag_du_role),
        require_address=bool(get_option("require_address")),
        group_by=tuple(axes),
        filters=Filters(
            tags=_tags(get_option("tags"), "tags"),
            tags_match=correspondance,
            states=_liste(get_option("states")),
            exclude_tags=_tags(get_option("exclude_tags"), "exclude_tags"),
            exclude_ids=_liste(get_option("exclude_ids")),
        ),
        include_raw=bool(get_option("include_raw")),
        strict=bool(get_option("strict")),
    )
