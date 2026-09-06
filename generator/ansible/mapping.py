"""Traduction du vocabulaire de l'API vers celui d'Ansible.

Trois traductions vivent ici, et une seule fois : le **nom** d'un module, le
**nom** d'une option et le **type** d'une option. Les templates ne doivent
contenir aucune des trois.

**Le nom d'option n'est pas inversé.** `VmIds` devient `vm_ids`, et le module
généré porte les deux côte à côte (`OperationBinding.body_params` est un
dictionnaire option -> nom du contrat). Reconstituer `VmIds` depuis `vm_ids`
serait deviner, et le SDK officiel exige le nom exact du contrat.
"""

from __future__ import annotations

import re

from generator.ir.enums import ApiType, OperationKind
from generator.ir.models import ApiParameter
from generator.parser.naming import option_name as _option_name

#: Suffixe de module par classification. `MANAGE` n'en porte aucun : le module
#: qui gère l'état durable d'une ressource porte le nom de la ressource.
_MODULE_SUFFIX: dict[OperationKind, str | None] = {
    OperationKind.INFO: "_info",
    OperationKind.ACTION: "_action",
    OperationKind.MANAGE: "",
    OperationKind.WORKFLOW: "",
}

#: Correspondance des types de l'IR vers les types `argument_spec`.
_ANSIBLE_TYPES: dict[ApiType, str] = {
    ApiType.STRING: "str",
    ApiType.INTEGER: "int",
    ApiType.NUMBER: "float",
    ApiType.BOOLEAN: "bool",
    ApiType.ENUM: "str",
    ApiType.ARRAY: "list",
    ApiType.MAP: "dict",
    ApiType.OBJECT: "dict",
}

#: Fragments de nom qui rendent un paramètre sensible. La liste est
#: volontairement large : un faux positif se corrige par un override, un faux
#: négatif écrit un secret dans le journal d'Ansible.
_SENSITIVE_FRAGMENTS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "passphrase",
    "private_key",
    "credential",
)

#: Paramètres portés par le module_utils commun : ils ne se redéclarent jamais
#: dans un module généré.
COMMON_PARAMETERS: frozenset[str] = frozenset(
    {"access_key", "secret_key", "region", "profile", "api_url", "wait", "wait_timeout"}
)

#: Champs de requête que le contrat porte et qu'un module n'expose pas, avec
#: leur raison, mesurée :
#:
#: * `DryRun` (226 requêtes sur 236) demande à l'API de vérifier les droits
#:   sans agir. Le check mode d'Ansible n'envoie rien du tout, et exposer un
#:   drapeau qui fait rendre une erreur `DryRunOperation` à un module serait
#:   un piège ;
#: * `NextPageToken` et `ResultsPerPage` (36 lectures) sont la pagination, et
#:   c'est le runtime qui la déroule jusqu'au bout. Un utilisateur qui les
#:   réglerait obtiendrait une page au lieu d'une liste.
REQUEST_FLAGS: frozenset[str] = frozenset({"dry_run", "next_page_token", "results_per_page"})


class UnmappedType(Exception):
    """Un type de l'IR n'a pas d'équivalent `argument_spec`."""

    def __init__(self, parameter: str, type: ApiType) -> None:
        super().__init__(f"{parameter} : type {type.value} sans correspondance Ansible")
        self.parameter = parameter
        self.type = type


def module_name(product: str, resource: str, kind: OperationKind) -> str | None:
    """Nom du module Ansible, ou `None` quand la classe n'en produit pas.

    Le nom suit `<produit>_<ressource>[_info|_action]` et ne contient jamais un
    verbe : `vm_info`, jamais `read_vms`.

    **Le produit n'est pas redoublé.** Chez Outscale, le produit est le tag et
    la ressource se lit dans l'identifiant : pour `Vm.ReadVms` les deux
    disent `vm`, pour `Vm.ReadVmTypes` la ressource `vm_type` commence par le
    produit. La concaténation naïve donnerait `vm_vm_info` et
    `vm_vm_type_info` ; quand la ressource commence par le nom du produit, le
    nom du module est la ressource seule : `vm_info`, `vm_type_info`,
    `load_balancer_info`. Une ressource qui ne commence pas par le produit
    garde le préfixe, parce qu'elle a besoin de dire d'où elle vient :
    `Vm.ReadAdminPassword` donne `vm_admin_password_info`.
    """
    suffix = _MODULE_SUFFIX.get(kind)
    if suffix is None:
        return None
    if resource == product or resource.startswith(product + "_"):
        return f"{resource}{suffix}"
    return f"{product}_{resource}{suffix}"


def option_name(parameter: ApiParameter) -> str:
    """Le nom d'option Ansible d'un paramètre du contrat : `VmIds` -> `vm_ids`."""
    return _option_name(parameter.name)


def sdk_method(operation_id: str) -> str:
    """Le nom de méthode du SDK Python officiel pour un `operationId`.

    Ce n'est pas une supposition : `osc_sdk_python.Gateway` dispatche tout
    attribut vers l'action du même nom (`__getattr__`), et refuse une action
    absente de sa copie du contrat (`ActionNotExists`). Le nom est donc
    l'identifiant lui-même, et une garde de test vérifie que le SDK installé
    connaît chaque action qu'un module appelle.
    """
    return operation_id


#: Ce qu'`ansible-test sanity` soupçonne d'être un secret, recopié de
#: `validate_modules/constants.py` (`NO_LOG_REGEX`). Un nom qui y correspond
#: sans `no_log` fait échouer `validate-modules` en `no-log-needed` : chez
#: Outscale, `keypair_name` et `access_key_id` sont des noms de ressources, pas
#: des secrets. Quand le mapping a décidé que ce n'est pas un secret, il le
#: **dit**, par `no_log: False`, plutôt que de laisser sanity le supposer.
_SANITY_SUSPECTS = re.compile(r"(?:pass(?!ive)|secret|token|key)", re.IGNORECASE)


def looks_secret_to_sanity(name: str) -> bool:
    """Vrai quand `validate-modules` exigerait un `no_log` explicite sur ce nom."""
    return _SANITY_SUSPECTS.search(name) is not None


def is_sensitive(parameter: ApiParameter) -> bool:
    """Vrai quand le paramètre doit recevoir `no_log=True`.

    Un identifiant ou un nom n'est jamais le secret lui-même : `keypair_name`
    désigne une clé, il ne la porte pas ; `access_key_id` désigne une clé
    d'API, et c'est `secret_key` qui est le secret.
    """
    name = option_name(parameter)
    if name.endswith(("_id", "_ids", "_name", "_names")):
        return False
    return any(fragment in name for fragment in _SENSITIVE_FRAGMENTS)


def return_type(api_type: ApiType) -> str:
    """Le type Ansible d'un champ **rendu**, avec un repli assumé.

    `argument_spec_entry` lève `UnmappedType` sur un type qu'il ne sait pas
    traduire, et c'est juste : un module qui accepterait un paramètre sans
    savoir ce qu'il en fait mentirait sur ce qu'il accepte.

    Un champ de réponse n'a pas cette conséquence : il n'est pas envoyé, il
    est lu. Refuser un module entier parce qu'un champ de sa réponse porte un
    type non traduit coûterait plus que ce que ça protège, et `raw` est le
    type Ansible qui dit exactement « ce que l'API rend, tel quel ».
    """
    return _ANSIBLE_TYPES.get(api_type, "raw")


def argument_spec_entry(parameter: ApiParameter) -> dict[str, object]:
    """Traduit un paramètre de l'IR en entrée d'`argument_spec`.

    Lève `UnmappedType` plutôt que de deviner : un type inconnu doit remonter
    dans le rapport, pas devenir un `str` par défaut.

    `required` vient du contrat quand il le déclare. Mesuré : 164 corps sur
    236 portent une liste `required`, et `StartVms` exige `VmIds`.
    """
    ansible_type = _ANSIBLE_TYPES.get(parameter.type)
    if ansible_type is None:
        raise UnmappedType(parameter=option_name(parameter), type=parameter.type)

    entry: dict[str, object] = {"type": ansible_type}
    if parameter.required:
        entry["required"] = True
    if parameter.type is ApiType.ENUM and parameter.enum_values:
        entry["choices"] = list(parameter.enum_values)
    if parameter.type is ApiType.ARRAY:
        element = _ANSIBLE_TYPES.get(parameter.item_type or ApiType.STRING, "str")
        entry["elements"] = element
    if parameter.default is not None and parameter.type is not ApiType.ENUM:
        entry["default"] = parameter.default
    if is_sensitive(parameter):
        entry["no_log"] = True
    elif looks_secret_to_sanity(option_name(parameter)):
        entry["no_log"] = False
    return entry
