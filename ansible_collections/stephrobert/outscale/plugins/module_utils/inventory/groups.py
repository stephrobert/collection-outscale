# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Les groupes natifs, et l'assainissement de leurs noms.

Une seule implémentation de l'assainissement, ici, testée. Ansible accepte
pour un nom de groupe les lettres, les chiffres et le tiret bas, et refuse un
nom qui commence par un chiffre ; un tag `env=pré-prod` doit donner un groupe
lisible sans casser l'inventaire.

Les axes du cœur sont ceux que tout produit porte : un lieu, un état, des
tags, un réseau. Un produit en ajoute par sa table `group_axes`, qui va d'un
nom d'axe à la clé de `metadata` qui le porte ; le cœur ne les nomme pas.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from .models import InventoryHost

#: Ce que `group_by` accepte de tout produit. Un axe absent de cette table et
#: de celle du provider est une faute de configuration, pas un groupe vide
#: créé en silence.
AXES: tuple[str, ...] = ("region", "subregion", "state", "tags", "net", "subnet")

#: Préfixe des groupes produits par le plugin, pour qu'ils ne se confondent
#: pas avec ceux qu'un `keyed_groups` de l'utilisateur crée.
PREFIX = "osc"

_INVALIDES = re.compile(r"[^A-Za-z0-9_]+")


def known_axes(extra: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Les axes du cœur, puis ceux que le provider ajoute, triés."""
    return (*AXES, *sorted(extra or ()))


def sanitize_group_name(raw: str, fallback: str = "inconnu") -> str:
    """Rend un nom de groupe valide pour Ansible, de façon déterministe.

    Les accents sont dépliés plutôt que supprimés : `pré-prod` devient
    `pre_prod` et non `pr_prod`, ce qui reste lisible pour qui écrit le
    playbook.
    """
    texte = unicodedata.normalize("NFKD", str(raw))
    texte = texte.encode("ascii", "ignore").decode("ascii")
    texte = _INVALIDES.sub("_", texte).strip("_")
    texte = re.sub(r"_{2,}", "_", texte)

    if not texte:
        return fallback
    if texte[0].isdigit():
        return f"_{texte}"
    return texte


def group_names(
    host: InventoryHost,
    axes: tuple[str, ...],
    extra: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Les groupes auxquels cette machine appartient, selon les axes demandés.

    Un tag donne un groupe par paire (`osc_tag_env_prod`) : c'est la clé
    **et** la valeur qui font le sens, `env=prod` et `env=staging` n'ont rien
    en commun. Un tag sans valeur donne un groupe par sa clé seule.
    """
    supplement = extra or {}
    noms: list[str] = []

    for axe in axes:
        if axe == "region" and host.region:
            noms.append(f"{PREFIX}_region_{sanitize_group_name(host.region)}")
        elif axe == "subregion" and host.subregion:
            noms.append(f"{PREFIX}_subregion_{sanitize_group_name(host.subregion)}")
        elif axe == "state" and host.state:
            noms.append(f"{PREFIX}_state_{sanitize_group_name(host.state)}")
        elif axe == "tags":
            for cle, valeur in host.tags.items():
                if not cle:
                    continue
                nom = f"{PREFIX}_tag_{sanitize_group_name(cle)}"
                if valeur:
                    nom = f"{nom}_{sanitize_group_name(valeur)}"
                noms.append(nom)
        elif axe == "net" and host.net_id:
            noms.append(f"{PREFIX}_net_{sanitize_group_name(host.net_id)}")
        elif axe == "subnet" and host.subnet_id:
            noms.append(f"{PREFIX}_subnet_{sanitize_group_name(host.subnet_id)}")
        elif axe in supplement:
            valeur = host.metadata.get(supplement[axe])
            if valeur:
                noms.append(f"{PREFIX}_{axe}_{sanitize_group_name(str(valeur))}")

    # Trié et dédoublonné : deux exécutions doivent produire le même inventaire.
    return tuple(sorted(set(noms)))
