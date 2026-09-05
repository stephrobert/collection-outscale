"""Normalisation des noms entre le vocabulaire de l'API et celui d'Ansible.

Outscale écrit tout en CamelCase : `operationId` (`ReadVms`, `StartVms`),
propriétés (`VmId`, `BlockDeviceMappings`, `NextPageToken`). Mesuré sur le
contrat 1.42.0 : les 236 identifiants et toutes les propriétés commencent par
une majuscule, aucun ne porte de tiret ni de soulignement, trois seulement
portent des majuscules consécutives (`CO2EmissionEntries`,
`ReadCO2EmissionAccount`, `VRam`) et douze portent un chiffre (`Phase1Options`,
`Ipv6Ranges`). Le découpage est donc simple, et il doit le rester : un cas mal
traité se corrige par un override, jamais par une exception glissée ici.

Un nom d'option Ansible s'écrit en snake_case. `option_name` traduit `VmId` en
`vm_id`, et la traduction n'est **pas** inversée : l'IR garde le nom du contrat,
le module généré porte les deux côte à côte, et le runtime envoie celui du
contrat. Reconstituer `VmId` depuis `vm_id` serait deviner : `Ipv6Ranges` et
`Ip6Ranges` ne se distingueraient plus.
"""

from __future__ import annotations

import re

#: Un mot CamelCase : une suite de majuscules suivie de chiffres et non suivie
#: d'une minuscule (`CO2`, `VR` dans `VRam` recule à `V`), ou une majuscule
#: facultative suivie de minuscules et de chiffres (`Vm`, `Ipv6`, `Phase1`).
_CAMEL_WORD = re.compile(r"[A-Z]+[0-9]*(?![a-z])|[A-Z]?[a-z0-9]+")

#: Mots qui finissent par `s` sans être des pluriels, ou dont le singulier ne
#: suit pas la règle. Ceux mesurés dans les identifiants du contrat, et rien
#: de plus : `ReadVmsState` porte `Vms` qui est un vrai pluriel, `ReadCas`
#: porte `Cas` qui est le pluriel de `Ca`, et la règle générale les traite.
IRREGULAR_SINGULARS: dict[str, str] = {
    "dns": "dns",
    "status": "status",
    "access": "access",
    "https": "https",
    "iops": "iops",
    "gpus": "gpu",
}

#: Mots que la table ci-dessus déclare identiques au singulier et au pluriel.
INVARIABLE_WORDS: frozenset[str] = frozenset(
    word for word, singular in IRREGULAR_SINGULARS.items() if word == singular
)


def split_words(name: str) -> list[str]:
    """Découpe un identifiant CamelCase, snake ou kebab en mots, en minuscules.

    >>> split_words("ReadVmTypes")
    ['read', 'vm', 'types']
    >>> split_words("CO2EmissionEntries")
    ['co2', 'emission', 'entries']
    >>> split_words("security_group_rules")
    ['security', 'group', 'rules']
    """
    if "_" in name or "-" in name:
        return [chunk.lower() for chunk in name.replace("-", "_").split("_") if chunk]
    return [chunk.lower() for chunk in _CAMEL_WORD.findall(name)]


def snake_case(name: str) -> str:
    """`SecurityGroup` -> `security_group`."""
    return "_".join(split_words(name))


def option_name(api_name: str) -> str:
    """Nom d'option Ansible d'un paramètre du contrat : `VmIds` -> `vm_ids`.

    La fonction est totale et déterministe, mais pas injective. Le modèle de
    module refuse un conflit plutôt que de laisser deux paramètres se
    recouvrir.
    """
    return snake_case(api_name)


def singularize(word: str) -> str:
    """Singularise un mot anglais avec les seules règles dont l'IR a besoin.

    >>> singularize("vms"), singularize("policies"), singularize("addresses")
    ('vm', 'policy', 'address')
    >>> singularize("dns"), singularize("status"), singularize("gpus")
    ('dns', 'status', 'gpu')
    """
    lowered = word.lower()
    if lowered in IRREGULAR_SINGULARS:
        return IRREGULAR_SINGULARS[lowered]
    if lowered.endswith("ies") and len(lowered) > 4:
        return lowered[:-3] + "y"
    for suffix in ("sses", "shes", "ches", "xes", "zes"):
        if lowered.endswith(suffix):
            return lowered[:-2]
    if lowered.endswith("ss") or not lowered.endswith("s"):
        return lowered
    return lowered[:-1]


def singularize_phrase(phrase: str) -> str:
    """Singularise chaque mot d'une expression snake_case : `security_group_rules`."""
    return "_".join(singularize(word) for word in phrase.split("_") if word)


def pluralize(word: str) -> str:
    """Pluralise un mot anglais, avec les seules règles dont la doc a besoin.

    >>> pluralize("vm"), pluralize("policy"), pluralize("address")
    ('vms', 'policies', 'addresses')
    """
    lowered = word.lower()
    if lowered in INVARIABLE_WORDS:
        return lowered
    if lowered.endswith("y") and len(lowered) > 1 and lowered[-2] not in "aeiou":
        return lowered[:-1] + "ies"
    if lowered.endswith(("s", "sh", "ch", "x", "z")):
        return lowered + "es"
    return lowered + "s"


def pluralize_phrase(phrase: str) -> str:
    """Pluralise le dernier mot d'une expression snake_case, en mots séparés.

    `vm_type` -> `vm types` : c'est la tête de l'expression qui porte le
    nombre, et la documentation se lit en mots, pas en snake_case.
    """
    words = [word for word in phrase.split("_") if word]
    if not words:
        return phrase
    return " ".join([*words[:-1], pluralize(words[-1])])
