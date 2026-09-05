# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le filtrage qui reste à faire une fois les réponses reçues.

Deux filtrages, et ils ne se confondent pas. Les filtres de l'API partent
tels quels dans la requête, avec le vocabulaire du contrat : c'est le
provider qui les porte, et ce module ne les voit pas. Ce qui reste se décide
ici, sur le modèle normalisé, par des fonctions pures : les états, les tags
demandés ou exclus, les identifiants exclus.

L'exclusion vient du plugin antérieur du mainteneur : une machine qu'Ansible
ne saura jamais joindre (une image sans SSH, un nœud géré par un autre
outil) n'a rien à faire dans un inventaire qui sert à `ansible-playbook`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Filters:
    """Ce que l'utilisateur garde, et ce qu'il écarte."""

    #: Les tags demandés, clé et valeur. Une valeur vide veut dire « la clé
    #: existe, quelle que soit sa valeur ».
    tags: Mapping[str, str] = field(default_factory=dict)
    tags_match: str = "any"
    states: tuple[str, ...] = ()
    exclude_tags: Mapping[str, str] = field(default_factory=dict)
    exclude_ids: tuple[str, ...] = ()


def _matches(tags: Mapping[str, str], cle: str, valeur: str) -> bool:
    """Vrai quand la machine porte ce tag, à cette valeur ou à n'importe laquelle."""
    if cle not in tags:
        return False
    return not valeur or str(tags[cle]) == valeur


def keep(
    host_id: str,
    tags: Mapping[str, str],
    state: str | None,
    filters: Filters,
) -> tuple[bool, str]:
    """Garde-t-on cette machine, et sinon pourquoi.

    La raison est rendue pour que le mode debug puisse répondre à « pourquoi
    cette machine n'apparaît-elle pas ». Les arguments sont les champs et non
    la machine : la fonction ne dépend d'aucun produit. Les exclusions
    l'emportent sur tout le reste.
    """
    if host_id in filters.exclude_ids:
        return False, "exclue par son identifiant"

    for cle, valeur in filters.exclude_tags.items():
        if _matches(tags, cle, valeur):
            return (
                False,
                f"exclue par le tag '{cle}={valeur}'" if valeur else f"exclue par le tag '{cle}'",
            )

    if filters.states and (state or "") not in filters.states:
        return False, f"état '{state}' hors de {list(filters.states)}"

    if filters.tags:
        verdicts = {cle: _matches(tags, cle, valeur) for cle, valeur in filters.tags.items()}
        if filters.tags_match == "all":
            manquants = sorted(cle for cle, ok in verdicts.items() if not ok)
            if manquants:
                return False, f"tags manquants {manquants}"
        elif not any(verdicts.values()):
            return False, f"aucun des tags {sorted(filters.tags)}"

    return True, "retenue"
