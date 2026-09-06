"""Modèle intermédiaire d'un module Ansible, construit depuis le plan.

C'est **la seule source** de l'`argument_spec`, de la `DOCUMENTATION`, des
`EXAMPLES` et du `RETURN` d'un module. Ce fichier porte les décisions ; le
renderer ne fait que les écrire. La règle qui tranche les cas limites : **si un
template a besoin d'un `if` sur autre chose qu'une présence de valeur, la
décision manque ici.**

Trois décisions propres à Outscale valent d'être lues avant le code :

* **une lecture est une opération, pas deux.** Scaleway et Exoscale séparent
  `Get` et `List` ; Outscale n'a que `ReadVms`, une liste filtrée, et
  `ReadVms` avec `Filters.VmIds` est la lecture unitaire. Un module
  d'information porte donc **une** opération, et ses filtres ;
* **une action agit sur des identifiants, et la ressource change d'état
  ensuite.** `StopVms` répond `stopping`, et la machine passe `stopped` plus
  tard. L'état visé se déclare dans un override `wait`, et le module relit la
  ressource par la lecture de la même ressource, avec le filtre que le
  contrat porte pour le sélecteur (`VmIds` pour `VmIds`, `NetPeeringIds` pour
  `NetPeeringId`) : le lien est mécanique, lu dans les propriétés du schéma
  `Filters`, jamais deviné ;
* **un paramètre sans type ne se rend pas.** Un type inconnu écarte le module
  avec sa raison tant qu'un override ne l'a pas typé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from generator.ansible.collection import Collection
from generator.ansible.mapping import (
    COMMON_PARAMETERS,
    REQUEST_FLAGS,
    UnmappedType,
    argument_spec_entry,
    option_name,
    return_type,
    sdk_method,
)
from generator.ir.enums import ApiType, OperationKind
from generator.ir.models import ApiOperation, ApiParameter, ApiService
from generator.overrides.loader import OperationOverride, OverrideSet, ParameterOverride
from generator.parser.naming import pluralize_phrase, split_words
from generator.plan import OperationPlan, ProductPlan

#: Classes que le renderer sait produire aujourd'hui. Une classe absente n'est
#: pas ignorée : elle est rendue dans le rapport de génération avec sa raison.
RENDERABLE_KINDS: frozenset[OperationKind] = frozenset(
    {OperationKind.INFO, OperationKind.ACTION, OperationKind.MANAGE}
)

#: Ce qu'on écrit quand le contrat ne décrit pas un paramètre ni un champ.
#: Utile dans un compte rendu, illisible sur une page Galaxy : la porte
#: documentaire refuse de publier une page qui le porte.
UNDOCUMENTED = "Not documented by the Outscale API contract."

#: Ce qu'on ajoute quand le contrat déclare un paramètre ou un champ déprécié.
#: Le drapeau était lu par le parser et ne sortait nulle part : un lecteur
#: bâtissait sur `vm_initiated_shutdown_behavior` sans savoir que le contrat
#: 1.42.0 le déclare déprécié.
DEPRECATED_NOTICE = "Deprecated by the Outscale API contract."

#: Identifiant d'exemple. Un exemple montre une forme, pas une ressource, et
#: les identifiants d'Outscale portent un préfixe par ressource (`i-`, `vol-`)
#: qu'un exemple générique ne doit pas prétendre connaître.
EXAMPLE_ID = "example-id"

#: Région d'exemple : celle que le contrat déclare par défaut.
EXAMPLE_REGION = "eu-west-2"

#: Adresse d'exemple : le bloc `192.0.2.0/24` que la RFC 5737 réserve à la
#: documentation, comme `example.com` pour les noms. Le repli par type
#: publiait `public_ip: example-id`, copiable et refusé par l'API.
EXAMPLE_PUBLIC_IP = "192.0.2.10"

#: Un tag d'exemple, dans la forme `clé=valeur` que le contrat décrit pour le
#: filtre `Tags` (« in the following format: TAGKEY=TAGVALUE », sur les 21
#: schémas `Filters*` qui le portent).
EXAMPLE_TAG = "role=web"

#: Ce que le nom d'une clé de filtre dit de ce qu'on y met. Mesuré sur le
#: contrat 1.42.0 : les 118 clés `*Ids` et les 44 clés `*Names` des schémas
#: `Filters*` sont toutes des tableaux de chaînes.
FILTER_IDS = "Ids"
FILTER_TAGS = "Tags"

#: Mots qu'une ressource porte en abrégé, et leur forme publiée.
#:
#: Une ressource déduite d'un identifiant arrive en minuscules, `vm`, `nic`,
#: `dhcp_option` : c'est un identifiant, pas de la prose. Collé tel quel dans
#: une phrase, ça donnait « Manage the settings of an Outscale vm » sur une
#: page qui se veut une référence. Le reste des mots n'est pas capitalisé pour
#: autant : ce sont des noms communs, et « Outscale Volume » ne serait pas
#: mieux. Ce que le contrat écrit en capitales dans ses propres phrases (VM,
#: NIC, DHCP, NAT, IP) sort en capitales.
ACRONYMES: dict[str, str] = {
    "vm": "VM",
    "vms": "VMs",
    "nic": "NIC",
    "nics": "NICs",
    "dhcp": "DHCP",
    "nat": "NAT",
    "ip": "IP",
    "ips": "IPs",
    "id": "ID",
    "ids": "IDs",
}

#: Mots d'un `operationId` dont la valeur rendue est un secret. Mesuré :
#: `ReadAdminPassword` rend le mot de passe administrateur d'une machine
#: Windows, `ReadSecretAccessKey` la clé secrète d'une clé d'accès.
SENSITIVE_WORDS: frozenset[str] = frozenset({"password", "secret"})

#: Le nom que le contrat donne au paramètre de filtres d'une lecture.
FILTERS = "Filters"


class ModuleModelError(ValueError):
    """Le plan ne permet pas de construire un module cohérent."""


class UnsupportedKind(ModuleModelError):
    """La classe d'opération n'a pas encore de renderer."""


class AmbiguousModule(ModuleModelError):
    """Les opérations d'un module ne composent pas une forme connue."""


class ConflictingOption(ModuleModelError):
    """Deux paramètres se traduisent vers la même option, ou avec des types différents."""


class UntypedParameter(ModuleModelError):
    """Le contrat tait le type d'un paramètre, et aucun override ne le dit."""


@dataclass(frozen=True)
class OperationBinding:
    """Ce que le runtime doit savoir pour appeler une opération.

    `body_params` va de l'option Ansible (`vm_ids`) au nom du contrat
    (`VmIds`). Le runtime envoie le nom du contrat ; il ne le reconstitue
    jamais.
    """

    id: str
    method: str
    body_params: dict[str, str]
    payload_field: str | None = None
    is_list: bool = False
    page_token: str | None = None
    #: Nom du schéma de la ressource rendue, et de l'enveloppe qui la porte.
    #: Ils servent au `contains` du `RETURN`, jamais au runtime : sans eux, la
    #: page nommait la clé rendue sans dire ce qu'on y trouve.
    payload_schema: str | None = None
    response_schema: str | None = None


@dataclass(frozen=True)
class ReturnField:
    """Un champ d'une clé rendue, tel que le contrat le déclare.

    Ce que le `RETURN` publie sous `contains`. Un niveau par défaut ; un
    second seulement pour l'enveloppe d'une action, dont la ressource est un
    champ (`result.Vms` porte des `VmState`).
    """

    name: str
    type: str
    description: tuple[str, ...]
    returned: str = "when the API returns it"
    elements: str | None = None
    contains: tuple[ReturnField, ...] = ()

    def to_documentation(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "description": list(self.description),
            "returned": self.returned,
            "type": self.type,
        }
        if self.elements:
            entry["elements"] = self.elements
        if self.contains:
            entry["contains"] = {champ.name: champ.to_documentation() for champ in self.contains}
        return entry


@dataclass(frozen=True)
class ActionBinding:
    """Une action d'un module d'action : son nom, et l'opération qu'elle appelle."""

    name: str
    operation: OperationBinding
    #: Options que le contrat exige pour cette action seule.
    required: tuple[str, ...] = ()
    #: État de la ressource attendu une fois l'action faite, s'il est décidé.
    expected_state: str | None = None
    #: Vrai quand l'action agit même si l'état attendu est déjà atteint.
    always_acts: bool = False


@dataclass(frozen=True)
class AnsibleModuleSpec:
    """Tout ce qu'un module généré contient, décidé une fois."""

    name: str
    kind: OperationKind
    product: str
    resource: str
    collection: Collection
    options: dict[str, dict[str, Any]]
    #: Les lignes de description de chaque option : la phrase du contrat, ou
    #: celle qu'un override pose à sa place, puis l'avis de dépréciation.
    option_docs: dict[str, tuple[str, ...]]
    #: Valeurs d'exemple posées par override, par option. Elles ne rejoignent
    #: jamais l'`argument_spec` : c'est de la documentation.
    option_examples: dict[str, Any] = field(default_factory=dict)
    #: Les clés que le schéma `Filters` d'une lecture accepte, telles que le
    #: contrat les nomme. Elles décident quels exemples de filtre sont vrais.
    filter_keys: tuple[str, ...] = ()
    #: Les champs de chaque clé rendue, par clé du `RETURN`.
    contains: dict[str, tuple[ReturnField, ...]] = field(default_factory=dict)
    #: Le type des éléments quand une lecture rend une liste. `dict` presque
    #: toujours ; `ReadPublicIpRanges` rend une liste de chaînes, et la page
    #: disait `elements: dict`.
    list_elements: str = "dict"
    #: La lecture d'un module d'information.
    operation: OperationBinding | None = None
    #: L'option que toutes les actions partagent et exigent, s'il y en a une.
    selector: str | None = None
    actions: tuple[ActionBinding, ...] = ()
    #: Le champ de la ressource qui porte l'état, chemin pointé possible.
    state_field: str | None = None
    #: La lecture de la ressource, quand un état est attendu : c'est elle qui
    #: sépare « l'API a accepté » de « la machine est arrêtée ».
    read_operation: OperationBinding | None = None
    #: La clé de `Filters` qui reçoit la valeur du sélecteur pour cette lecture.
    read_filter: str | None = None
    #: Le champ de chaque élément lu qui porte son identifiant.
    read_id_field: str | None = None
    #: L'écriture d'un module de gestion d'état.
    update_operation: OperationBinding | None = None
    #: Pour un module de gestion d'état, l'option et le champ de la ressource lue
    #: qu'elle se compare à : seules ces options sont exposées.
    compare: dict[str, str] = field(default_factory=dict)
    #: Limites du contrat rencontrées en construisant le module.
    limits: tuple[str, ...] = ()
    sensitive_return: bool = False
    summary: str | None = None

    @property
    def operation_ids(self) -> tuple[str, ...]:
        ids = [self.operation.id] if self.operation is not None else []
        ids.extend(action.operation.id for action in self.actions)
        if self.update_operation is not None:
            ids.append(self.update_operation.id)
        return tuple(ids)

    @property
    def waitable(self) -> bool:
        """Vrai quand au moins une action a un état attendu que le module sait lire."""
        return self.read_operation is not None and any(
            action.expected_state is not None for action in self.actions
        )

    @property
    def resource_words(self) -> str:
        """La ressource en mots publiables : `vm_type` -> `VM type`."""
        return _lisible(self.resource.replace("_", " "))

    @property
    def resource_plural(self) -> str:
        """La ressource au pluriel, en mots publiables : `vm` -> `VMs`."""
        return _lisible(pluralize_phrase(self.resource))

    def argument_spec(self) -> dict[str, dict[str, Any]]:
        return dict(self.options)

    def required_if(self) -> list[tuple[str, str, list[str]]]:
        return [
            ("action", action.name, list(action.required))
            for action in self.actions
            if action.required
        ]

    def documentation(self) -> dict[str, Any]:
        """Le bloc `DOCUMENTATION`, dans l'ordre d'une lecture humaine."""
        options: dict[str, Any] = {}
        for name, entry in self.options.items():
            lignes = self.option_docs.get(name, (UNDOCUMENTED,))
            option: dict[str, Any] = {
                "description": lignes[0] if len(lignes) == 1 else list(lignes)
            }
            option["type"] = entry["type"]
            if entry.get("required"):
                option["required"] = True
            if "choices" in entry:
                option["choices"] = list(entry["choices"])
            if "elements" in entry:
                option["elements"] = entry["elements"]
            if "default" in entry:
                option["default"] = entry["default"]
            options[name] = option

        notes: list[str] = []
        if self.kind is OperationKind.INFO and self.operation is not None:
            if self.operation.page_token is not None:
                notes.append(
                    "The API answers by pages: the module follows the "
                    f"C({self.operation.page_token}) until the last page and returns "
                    "everything the API knows."
                )
            elif self.operation.is_list:
                notes.append(
                    "The API answers in one response, and the contract does not promise "
                    "it is complete: there is no page token on this operation."
                )
        if self.kind is OperationKind.ACTION:
            notes.append(
                "Every action answers at once: the API response is returned under "
                "RV(result), and the resource changes state afterwards."
            )
        if self.waitable and self.state_field is not None:
            expected = ", ".join(
                f"C({action.name}) leads to C({action.expected_state})"
                for action in self.actions
                if action.expected_state is not None
            )
            always = ", ".join(f"C({action.name})" for action in self.actions if action.always_acts)
            notes.append(
                f"When I(wait) is true, the module reads the {self.resource_words} until its "
                f"C({self.state_field}) reaches the expected value ({expected}), and reports "
                f"C(changed=false) without sending anything when every {self.resource_words} "
                "already is in that state"
                + (f", except for {always}, which always acts." if always else ".")
            )
        if self.kind is OperationKind.MANAGE and self.update_operation is not None:
            notes.append(
                f"The module reads the {self.resource_words} by I({self.selector}), compares "
                "every option you give with what the API returns, and sends "
                f"C({self.update_operation.id}) only when something differs: a second run "
                "reports C(changed=false). In check mode nothing is sent."
            )
            notes.append(
                "Only the settings the API reads back are exposed: what it cannot read "
                "back could not be compared, and the module would report a change on "
                "every run."
            )
        if self.sensitive_return:
            notes.append("The returned value is a secret: do not log the task output.")

        document: dict[str, Any] = {
            "module": self.name,
            "short_description": self.short_description(),
            "version_added": self.collection.version,
            "description": [self.long_description()],
            "author": list(self.collection.authors) or [self.collection.fqcn],
            "options": options,
            "extends_documentation_fragment": self.doc_fragments(),
        }
        if notes:
            document["notes"] = notes
        return document

    def doc_fragments(self) -> list[str]:
        """Le fragment commun, et celui de l'attente quand le module attend."""
        fragments = [self.collection.doc_fragment]
        if self.waitable:
            fragments.append(f"{self.collection.doc_fragment}.wait")
        return fragments

    def short_description(self) -> str:
        if self.kind is OperationKind.INFO:
            if self.operation is not None and self.operation.is_list:
                return f"Gather information about Outscale {self.resource_plural}"
            return f"Read the Outscale {self.resource_words}"
        if self.kind is OperationKind.MANAGE:
            return f"Manage the settings of an Outscale {self.resource_words}"
        return f"Perform an action on Outscale {self.resource_plural}"

    def long_description(self) -> str:
        if self.kind is OperationKind.INFO:
            if self.operation is not None and self.operation.is_list:
                return (
                    f"List Outscale {self.resource_plural}, optionally filtered. "
                    "This module never changes anything."
                )
            return f"Read the Outscale {self.resource_words}. This module never changes anything."
        if self.kind is OperationKind.MANAGE:
            settings = ", ".join(f"I({option})" for option in self.compare)
            return (
                f"Set the settings of an existing Outscale {self.resource_words} ({settings}), "
                "and only what differs from what the API returns. Terraform provisions the "
                f"{self.resource_words}, this module operates it."
            )
        names = ", ".join(f"C({action.name})" for action in self.actions)
        return f"Trigger one of the following actions on existing {self.resource_plural}: {names}."

    def examples_documentation(self) -> list[dict[str, Any]]:
        """Un exemple par chose que le module sait faire, pas un par opération.

        Lire, lister, filtrer ; écrire, et simuler l'écriture ; déclencher
        chaque action. Chaque tâche se copie telle quelle : aucune valeur
        entre chevrons, aucune clé de filtre que le schéma `Filters` ne porte
        pas, aucun nom de tâche repris de l'identifiant du SDK.
        """
        if self.kind is OperationKind.INFO:
            return self._info_examples()
        if self.kind is OperationKind.MANAGE:
            return self._manage_examples()
        return self._action_examples()

    def _required_values(self) -> dict[str, Any]:
        task: dict[str, Any] = {"region": EXAMPLE_REGION}
        for name, entry in self.options.items():
            if entry.get("required"):
                task[name] = self._example_value(name, entry)
        return task

    def _info_examples(self) -> list[dict[str, Any]]:
        fqcn = self.collection.module_fqcn(self.name)
        task = self._required_values()
        is_list = self.operation is not None and self.operation.is_list
        title = f"List {self.resource_plural}" if is_list else f"Read the {self.resource_words}"
        examples: list[dict[str, Any]] = [{"name": title, fqcn: task, "register": "result"}]
        if not is_list or "filters" not in self.options:
            return examples

        # **Une clé de filtre vient du schéma `Filters`, jamais d'une
        # habitude.** `Tags: [role=web]` était publié sur cinq lectures dont le
        # schéma ne porte pas `Tags` (`FiltersVmType`, `FiltersLoadBalancer`,
        # `FiltersTag`, `FiltersSubregion`, `FiltersVmsState`) : copiable, et
        # refusé par l'API.
        cle_ids = _id_filter_key(self.resource, self.filter_keys)
        if cle_ids is not None:
            propre = cle_ids == _camel(self.resource) + FILTER_IDS
            examples.append(
                {
                    "name": (
                        f"Read {self.resource_plural} by ID"
                        if propre
                        else f"List {self.resource_plural} filtered by {cle_ids}"
                    ),
                    fqcn: {**task, "filters": {cle_ids: [EXAMPLE_ID]}},
                    "register": "result",
                }
            )
        if FILTER_TAGS in self.filter_keys:
            examples.append(
                {
                    "name": f"List {self.resource_plural} matching a tag",
                    fqcn: {**task, "filters": {FILTER_TAGS: [EXAMPLE_TAG]}},
                    "register": "result",
                }
            )
        return examples

    def _manage_examples(self) -> list[dict[str, Any]]:
        fqcn = self.collection.module_fqcn(self.name)
        task = self._required_values()
        reglage = self._setting_for_example()
        if reglage is not None and reglage not in task:
            task[reglage] = self._example_value(reglage, self.options[reglage])
        article = _article(self.resource_words)
        # **Le mode simulation se montre.** Les notes en parlent depuis le
        # premier module, aucune tâche ne le montrait ; c'est pourtant ce qu'on
        # fait avant d'écrire sur un parc qu'on ne possède pas seul, et
        # `diff: true` est ce qui rend la comparaison lisible plutôt que de
        # rendre un `changed` sans contenu. Même paramètres que l'écriture :
        # une simulation qui n'écrit pas la même chose ne simule rien.
        return [
            {"name": f"Set the settings of {article} {self.resource_words}", fqcn: task},
            {
                "name": f"Preview the change on {article} {self.resource_words} without writing",
                fqcn: dict(task),
                "check_mode": True,
                "diff": True,
            },
        ]

    def _action_examples(self) -> list[dict[str, Any]]:
        """Une tâche par action exposée : c'est ce qu'un lecteur vient chercher.

        « Run reboot on a vm » montrait une action sur trois, et nommait la
        tâche par le verbe du SDK plutôt que par ce qu'elle fait.
        """
        fqcn = self.collection.module_fqcn(self.name)
        examples: list[dict[str, Any]] = []
        for action in self.actions:
            task: dict[str, Any] = {"region": EXAMPLE_REGION, "action": action.name}
            for name, entry in self.options.items():
                if name != "action" and (entry.get("required") or name in action.required):
                    task[name] = self._example_value(name, entry)
            verbe = action.name.replace("_", " ").capitalize()
            pluriel = self.selector is not None and self.options[self.selector]["type"] == "list"
            cible = (
                self.resource_plural
                if pluriel
                else f"{_article(self.resource_words)} {self.resource_words}"
            )
            examples.append({"name": f"{verbe} {cible}", fqcn: task})
        return examples

    def _setting_for_example(self) -> str | None:
        """L'option gérée que l'exemple d'écriture règle, et pourquoi celle-là.

        Par ordre de confiance dans la valeur publiée : une valeur posée par
        override, une valeur d'enum que la même page liste, un booléen, une
        chaîne dont une convention de nom donne la valeur, puis le repli
        d'avant, une option scalaire quelconque avant un dictionnaire.
        `actions_on_next_boot: {}` et `bsu_optimized: true`, dont le contrat
        dit « This parameter is not available », n'apprenaient rien.
        """
        candidats = list(self.compare)
        if not candidats:
            return None
        for nom in candidats:
            if nom in self.option_examples:
                return nom
        for nom in candidats:
            if self.options[nom].get("choices"):
                return nom
        for nom in candidats:
            if self.options[nom]["type"] == "bool":
                return nom
        for nom in candidats:
            if self.options[nom]["type"] == "str" and _valeur_par_convention(nom) is not None:
                return nom
        for nom in candidats:
            if self.options[nom]["type"] not in ("dict", "list"):
                return nom
        return candidats[0]

    def _example_value(self, name: str, entry: dict[str, Any]) -> Any:
        """Valeur d'exemple d'une option, déterministe et jamais aléatoire.

        L'ordre est celui de la confiance : ce qu'un override pose, ce que le
        contrat porte (un enum), une convention de nom, un repli par type.
        """
        if name in self.option_examples:
            return self.option_examples[name]
        if entry.get("choices"):
            return entry["choices"][0]
        par_nom = _valeur_par_convention(name)
        if par_nom is not None:
            return par_nom
        if entry["type"] == "list":
            return [EXAMPLE_ID]
        if entry["type"] == "bool":
            return True
        if entry["type"] == "int":
            return 1
        if entry["type"] == "dict":
            return {}
        return EXAMPLE_ID

    def return_documentation(self) -> dict[str, Any]:
        rendu: dict[str, Any]
        if self.kind is OperationKind.INFO:
            if self.operation is not None and self.operation.is_list:
                plural = pluralize_phrase(self.resource).replace(" ", "_")
                rendu = {
                    plural: {
                        "description": f"The {self.resource_plural}.",
                        "returned": "always",
                        "type": "list",
                        "elements": self.list_elements,
                    }
                }
            else:
                rendu = {
                    self.resource: {
                        "description": (
                            f"The {self.resource_words}"
                            + (
                                "."
                                if self.operation is not None and self.operation.payload_field
                                else ", as the API answers it, without the response context."
                            )
                        ),
                        "returned": "always",
                        "type": "dict",
                    }
                }
        elif self.kind is OperationKind.MANAGE:
            rendu = {
                self.resource: {
                    "description": f"The {self.resource_words}, read after the update.",
                    "returned": "always",
                    "type": "dict",
                },
                "changes": {
                    "description": (
                        "What differed, by option: the value the API returned before, and "
                        "the value you asked for."
                    ),
                    "returned": "when something differed",
                    "type": "dict",
                },
            }
        else:
            rendu = {
                "result": {
                    "description": (
                        "The API response of the action, without the response context."
                    ),
                    "returned": "when the action was sent",
                    "type": "dict",
                }
            }
            if self.waitable and self.state_field is not None:
                rendu["states"] = {
                    "description": (
                        f"The C({self.state_field}) of each {self.resource_words}, by "
                        "identifier, read after the action."
                    ),
                    "returned": "when an expected state is declared for the action",
                    "type": "dict",
                }
        # **Nommer la clé ne dit pas ce qu'on y trouve.** Les champs viennent
        # du contrat, une fois par schéma ; une clé que le module compose
        # lui-même (`changes`, `states`) n'a pas de schéma et n'en reçoit pas.
        for cle, champs in self.contains.items():
            if champs and cle in rendu:
                rendu[cle]["contains"] = {champ.name: champ.to_documentation() for champ in champs}
        return rendu


def build_module_specs(
    plan: ProductPlan,
    collection: Collection,
    *,
    only: tuple[str, ...] = (),
) -> tuple[tuple[AnsibleModuleSpec, ...], list[tuple[str, str]]]:
    """Construit un modèle par module du plan, et dit ce qui n'a pas pu l'être."""
    specs: list[AnsibleModuleSpec] = []
    skipped: list[tuple[str, str]] = []
    for name, operations in plan.modules().items():
        if only and name not in only:
            skipped.append((name, "hors du périmètre demandé"))
            continue
        try:
            specs.append(_build_spec(name, operations, plan, collection))
        except ModuleModelError as error:
            skipped.append((name, str(error)))
    return tuple(specs), skipped


def _build_spec(
    name: str,
    operations: tuple[OperationPlan, ...],
    plan: ProductPlan,
    collection: Collection,
) -> AnsibleModuleSpec:
    kinds = {item.kind for item in operations}
    if len(kinds) != 1:
        raise AmbiguousModule(f"{name} : classes mêlées {sorted(k.value for k in kinds)}")
    kind = kinds.pop()
    if kind not in RENDERABLE_KINDS:
        raise UnsupportedKind(f"{name} : la classe {kind.value.upper()} n'a pas encore de renderer")
    if kind is OperationKind.INFO:
        return _build_info_spec(name, operations, plan, collection)
    if kind is OperationKind.MANAGE:
        return _build_manage_spec(name, operations, plan, collection)
    return _build_action_spec(name, operations, plan, collection)


def _build_info_spec(
    name: str,
    operations: tuple[OperationPlan, ...],
    plan: ProductPlan,
    collection: Collection,
) -> AnsibleModuleSpec:
    """Un module d'information porte une lecture, et ses filtres."""
    if len(operations) != 1:
        raise AmbiguousModule(
            f"{name} : {len(operations)} lectures {[o.operation.id for o in operations]}, "
            "un module d'information n'en porte qu'une chez Outscale ; corriger la "
            "ressource déduite par un override"
        )
    item = operations[0]
    options: dict[str, dict[str, Any]] = {}
    docs: dict[str, tuple[str, ...]] = {}
    examples: dict[str, Any] = {}
    limits: list[str] = []
    required = _collect_options(
        item, plan.overrides, options, docs, examples, limits, required_allowed=True
    )
    for option in required:
        options[option]["required"] = True

    sensitive = bool(SENSITIVE_WORDS & set(split_words(item.operation.id)))
    binding = _binding(item.operation, plan.overrides.get(item.operation.key))
    filters = item.operation.parameter(FILTERS)
    # La ressource rendue quand la réponse en désigne une ; l'enveloppe entière,
    # hors contexte, quand la charge utile est indécidable et que le module
    # rend la réponse telle quelle.
    schema = binding.payload_schema if binding.payload_field else binding.response_schema
    cle = pluralize_phrase(item.resource).replace(" ", "_") if binding.is_list else item.resource
    return AnsibleModuleSpec(
        name=name,
        kind=OperationKind.INFO,
        product=plan.service.name,
        resource=item.resource,
        collection=collection,
        options=options,
        option_docs=docs,
        option_examples=examples,
        filter_keys=filters.properties if filters is not None else (),
        contains={cle: _fields_of(plan.service, schema, plan.overrides)},
        list_elements=_list_elements(plan.service, binding),
        operation=binding,
        limits=tuple(sorted(set(limits))),
        sensitive_return=sensitive,
        summary=item.operation.summary,
    )


def _build_action_spec(
    name: str,
    operations: tuple[OperationPlan, ...],
    plan: ProductPlan,
    collection: Collection,
) -> AnsibleModuleSpec:
    """Un module d'action regroupe les opérations ponctuelles d'une ressource."""
    resource = operations[0].resource
    options: dict[str, dict[str, Any]] = {}
    docs: dict[str, tuple[str, ...]] = {}
    examples: dict[str, Any] = {}
    limits: list[str] = []
    actions: list[ActionBinding] = []
    seen: dict[str, str] = {}
    required_by_action: list[set[str]] = []

    for item in sorted(operations, key=lambda entry: entry.operation.id):
        action = action_name(item.operation.id, resource)
        if action in seen:
            raise AmbiguousModule(
                f"{name} : {item.operation.id} et {seen[action]} donnent la même action {action!r}"
            )
        seen[action] = item.operation.id
        override = plan.overrides.get(item.operation.key)
        required = _collect_options(
            item, plan.overrides, options, docs, examples, limits, required_allowed=False
        )
        required_by_action.append(set(required))
        expected = None
        always = False
        if override is not None and override.wait is not None:
            expected = override.wait.states.get(action)
            always = action in override.wait.always
        actions.append(
            ActionBinding(
                name=action,
                operation=_binding(item.operation, override),
                required=tuple(sorted(required)),
                expected_state=expected,
                always_acts=always,
            )
        )

    # Le sélecteur est l'option que **toutes** les actions exigent. Une option
    # exigée par une seule action reste propre à cette action, par `required_if`.
    shared = set.intersection(*required_by_action) if required_by_action else set()
    selector = next(iter(sorted(shared))) if len(shared) == 1 else None
    if selector is not None:
        options[selector]["required"] = True
        actions = [
            replace(action, required=tuple(o for o in action.required if o != selector))
            for action in actions
        ]

    options = {
        "action": {"type": "str", "required": True, "choices": [a.name for a in actions]},
        **options,
    }
    docs["action"] = (f"The action to trigger on the {_lisible(pluralize_phrase(resource))}.",)

    state_fields = {
        override.wait.field
        for item in operations
        if (override := plan.overrides.get(item.operation.key)) is not None
        and override.wait is not None
    }
    state_field = next(iter(sorted(state_fields)), None)
    read_operation = read_filter = read_id_field = None
    if state_field is not None:
        contract_name = next(
            (
                name
                for action in actions
                for opt, name in action.operation.body_params.items()
                if opt == selector
            ),
            None,
        )
        read = _read_binding(plan, resource, selector, contract_name, limits)
        if read is not None:
            read_operation, read_filter, read_id_field = read
    return AnsibleModuleSpec(
        name=name,
        kind=OperationKind.ACTION,
        product=plan.service.name,
        resource=resource,
        collection=collection,
        options=options,
        option_docs=docs,
        option_examples=examples,
        contains={"result": _action_result_fields(plan.service, actions, plan.overrides)},
        selector=selector,
        actions=tuple(actions),
        state_field=state_field,
        read_operation=read_operation,
        read_filter=read_filter,
        read_id_field=read_id_field,
        limits=tuple(sorted(set(limits))),
    )


def _build_manage_spec(
    name: str,
    operations: tuple[OperationPlan, ...],
    plan: ProductPlan,
    collection: Collection,
) -> AnsibleModuleSpec:
    """Un module de gestion d'état porte une écriture, et la lecture qui la juge.

    Trois décisions, et chacune est mesurée sur le contrat :

    * **une seule écriture par ressource.** `UpdateVm` est la seule sur `vm` ;
      deux écritures diraient une ressource mal déduite ;
    * **le sélecteur est l'option exigée que la lecture sait filtrer.**
      `UpdateVm` exige `VmId`, et `FiltersVm` porte `VmIds` ; `UpdateNet`
      exige `NetId` et `DhcpOptionsSetId`, et seul `NetId` se retrouve dans
      `FiltersNet` ;
    * **une option n'est exposée que si la lecture la rend.** `UpdateVm` porte
      13 champs que `Vm` rend sous le même nom, et `SecurityGroupIds` que `Vm`
      rend sous une autre forme (`SecurityGroups[]`). Une option qu'on ne peut
      pas relire ne se compare pas, et un module qui l'enverrait rendrait
      `changed` à chaque passage : elle n'est pas exposée, et la limite le dit.
    """
    if len(operations) != 1:
        raise AmbiguousModule(
            f"{name} : {len(operations)} écritures {[o.operation.id for o in operations]}, "
            "un module de gestion d'état n'en porte qu'une ; corriger la ressource déduite"
        )
    item = operations[0]
    resource = item.resource
    override = plan.overrides.get(item.operation.key)
    options: dict[str, dict[str, Any]] = {}
    docs: dict[str, tuple[str, ...]] = {}
    examples: dict[str, Any] = {}
    limits: list[str] = []
    required = _collect_options(
        item, plan.overrides, options, docs, examples, limits, required_allowed=False
    )
    contract_of = {
        _resolved_option(p, override): p.name
        for p in item.operation.parameters
        if _resolved_option(p, override) in options
    }

    if not any(op.resource == resource and op.kind is OperationKind.INFO for op in plan.operations):
        # `UpdateRoute` et `UpdateRouteTableLink` : rien ne rend la ressource,
        # donc rien ne peut juger l'écriture. Le dire ainsi, plutôt que
        # « 0 option filtrable », pour que le compte rendu nomme la cause.
        raise AmbiguousModule(
            f"{name} : aucune lecture ne rend {resource}, rien ne peut juger l'écriture"
        )
    candidates = [
        opt
        for opt in required
        if _read_binding(plan, resource, opt, contract_of[opt], []) is not None
    ]
    if len(candidates) > 1:
        # `UpdateNet` exige `NetId` et `DhcpOptionsSetId`, et `FiltersNet` sait
        # filtrer les deux : l'option qui nomme la ressource est le sélecteur.
        camel = "".join(part.capitalize() for part in resource.split("_"))
        named = [opt for opt in candidates if contract_of[opt].startswith(camel)]
        if len(named) == 1:
            candidates = named
    if len(candidates) != 1:
        raise AmbiguousModule(
            f"{name} : {len(candidates)} option(s) exigée(s) que la lecture sait filtrer "
            f"{candidates}, il en faut exactement une"
        )
    selector = candidates[0]
    read = _read_binding(plan, resource, selector, contract_of[selector], limits)
    assert read is not None
    read_operation, read_filter, read_id_field = read
    readable = set(
        next(
            op.operation.response.payload_fields
            for op in plan.operations
            if op.operation.id == read_operation.id and op.operation.response is not None
        )
    )

    compare: dict[str, str] = {}
    for option in list(options):
        if option == selector:
            options[option]["required"] = True
            continue
        contract_name = contract_of[option]
        if contract_name in readable:
            compare[option] = contract_name
            if option in required:
                options[option]["required"] = True
            continue
        limits.append(
            f"{item.operation.id}.{contract_name} : la lecture ne le rend pas sous ce nom, "
            "l'option n'est pas exposée faute de pouvoir la comparer"
        )
        del options[option]
        del docs[option]
        examples.pop(option, None)
    if not compare:
        raise AmbiguousModule(
            f"{name} : aucune option de {item.operation.id} ne se relit dans "
            f"{read_operation.id}, rien à gérer"
        )

    return AnsibleModuleSpec(
        name=name,
        kind=OperationKind.MANAGE,
        product=plan.service.name,
        resource=resource,
        collection=collection,
        options=options,
        option_docs=docs,
        option_examples=examples,
        # La ressource rendue est celle qu'on relit : mêmes champs, même schéma.
        contains={
            resource: _fields_of(plan.service, read_operation.payload_schema, plan.overrides)
        },
        selector=selector,
        # L'écriture ne porte que le sélecteur et les options comparées : une
        # option retirée faute de pouvoir être relue ne doit pas figurer dans
        # ce que le runtime sait envoyer.
        update_operation=replace(
            _binding(item.operation, override),
            body_params={
                opt: name
                for opt, name in _binding(item.operation, override).body_params.items()
                if opt == selector or opt in compare
            },
        ),
        read_operation=read_operation,
        read_filter=read_filter,
        read_id_field=read_id_field,
        compare=compare,
        limits=tuple(sorted(set(limits))),
        summary=item.operation.summary,
    )


def _read_binding(
    plan: ProductPlan,
    resource: str,
    selector: str | None,
    contract_name: str | None,
    limits: list[str],
) -> tuple[OperationBinding, str, str | None] | None:
    """La lecture de la ressource, et le filtre qui la restreint au sélecteur.

    L'API répond avant que la ressource ait changé d'état : il faut la relire.
    La lecture est celle du module d'information de la même ressource, et le
    contrat dit lui-même comment la restreindre : le schéma `Filters` de
    `ReadVms` porte `VmIds`, celui de `ReadNetPeerings` porte
    `NetPeeringIds`. La clé est le nom du sélecteur tel quel, ou au pluriel.
    Ce qui manque est dit dans les limites, jamais deviné.
    """
    if selector is None or contract_name is None:
        limits.append(f"{resource} : aucune option exigée commune, la ressource ne sera pas relue")
        return None
    candidates = [
        item
        for item in plan.operations
        if item.resource == resource
        and item.kind is OperationKind.INFO
        and item.operation.response is not None
        and item.operation.response.is_list
        and item.operation.parameter(FILTERS) is not None
    ]
    if len(candidates) != 1:
        limits.append(
            f"{resource} : {len(candidates)} lecture(s) filtrée(s), la ressource ne sera pas relue"
        )
        return None
    item = candidates[0]
    filters = item.operation.parameter(FILTERS)
    assert filters is not None
    filter_key = next(
        (key for key in (contract_name, contract_name + "s") if key in filters.properties), None
    )
    if filter_key is None:
        limits.append(
            f"{item.operation.id} : `Filters` ne porte ni {contract_name} ni {contract_name}s, "
            "l'état attendu ne sera pas vérifié après une action"
        )
        return None
    payload_fields = item.operation.response.payload_fields if item.operation.response else ()
    singular = contract_name[:-1] if contract_name.endswith("s") else contract_name
    id_field = next((f for f in (contract_name, singular) if f in payload_fields), None)
    if id_field is None:
        limits.append(
            f"{item.operation.id} : la ressource lue ne porte ni {contract_name} ni {singular}, "
            "les états seront rendus sans identifiant"
        )
    return _binding(item.operation, plan.overrides.get(item.operation.key)), filter_key, id_field


def action_name(operation_id: str, resource: str) -> str:
    """Le nom d'une action : les mots de l'`operationId` sans ceux de la ressource.

    >>> action_name("StartVms", "vm")
    'start'
    >>> action_name("AcceptNetPeering", "net_peering")
    'accept'
    >>> action_name("ScaleUpVmGroup", "vm_group")
    'scale_up'
    """
    words = split_words(operation_id)
    resource_words = resource.split("_")
    size = len(resource_words)
    for start in range(len(words) - size + 1):
        if words[start : start + size] == resource_words:
            words = words[:start] + words[start + size :]
            break
    else:
        # La ressource peut être écrite au pluriel dans l'identifiant.
        singular = [word.rstrip("s") for word in words]
        for start in range(len(words) - size + 1):
            if singular[start : start + size] == [w.rstrip("s") for w in resource_words]:
                words = words[:start] + words[start + size :]
                break
    return "_".join(words) or "_".join(split_words(operation_id))


def _resolved_option(parameter: ApiParameter, override: OperationOverride | None) -> str:
    """Le nom d'option d'un paramètre : celui de l'override s'il en impose un."""
    if override is not None:
        parameter_override = override.parameters.get(parameter.name)
        if parameter_override is not None and parameter_override.option:
            return parameter_override.option
    return option_name(parameter)


def _collect_options(
    item: OperationPlan,
    overrides: OverrideSet,
    options: dict[str, dict[str, Any]],
    docs: dict[str, tuple[str, ...]],
    examples: dict[str, Any],
    limits: list[str],
    *,
    required_allowed: bool,
) -> list[str]:
    """Ajoute les options d'une opération, et rend celles que le contrat exige."""
    override = overrides.get(item.operation.key)
    required: list[str] = []
    for parameter in item.operation.parameters:
        name = _resolved_option(parameter, override)
        if name in COMMON_PARAMETERS or name in REQUEST_FLAGS:
            continue
        if parameter.read_only:
            limits.append(f"{item.operation.id}.{parameter.name} : propriété readOnly, non exposée")
            continue
        parameter_override = override.parameters.get(parameter.name) if override else None
        if parameter_override is not None and parameter_override.expose is False:
            continue
        if not parameter.description:
            # Le compte rendu continue de compter les trous du contrat, même
            # comblés : les combler répare la page publiée, pas l'amont.
            comblee = parameter_override is not None and parameter_override.description
            limits.append(
                f"{item.operation.id}.{parameter.name} : aucune description dans le contrat"
                + (", comblée par override" if comblee else "")
            )
        parameter = _apply_parameter_override(parameter, parameter_override)
        if parameter.type is ApiType.UNKNOWN:
            raise UntypedParameter(
                f"{item.operation.id}.{parameter.name} : type absent du contrat, "
                "un override `type` avec sa raison est nécessaire"
            )
        try:
            entry = argument_spec_entry(parameter)
        except UnmappedType as error:
            raise UntypedParameter(str(error)) from error
        if parameter.type is ApiType.ARRAY and parameter.item_type is None:
            limits.append(
                f"{item.operation.id}.{parameter.name} : tableau sans `items`, "
                "éléments rendus en str"
            )
        if entry.pop("required", False):
            required.append(name)
            if required_allowed:
                entry["required"] = True
        previous = options.get(name)
        if previous is not None and previous.get("type") != entry["type"]:
            raise ConflictingOption(
                f"{name} : {previous['type']} pour une opération, {entry['type']} pour une autre"
            )
        if previous is None:
            options[name] = entry
            docs[name] = _describe(parameter, parameter_override)
            if parameter_override is not None and parameter_override.example is not None:
                examples[name] = parameter_override.example
    return required


#: Un lien Markdown du contrat : `[texte](url)`. 130 dans le contrat 1.42.0.
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
#: Un saut de ligne HTML du contrat : `<br />`. 426 dans le contrat 1.42.0.
_HTML_BREAK = re.compile(r"\s*<br\s*/?>\s*")
#: Un code Markdown du contrat : `` `io1` ``. 1054 dans le contrat 1.42.0.
_MARKDOWN_CODE = re.compile(r"`([^`\n]+)`")
#: Une barre échappée pour un tableau Markdown : `\|`. 78 dans le contrat
#: 1.42.0, et 18 modules la recopiaient telle quelle (« C(standard) \| C(io1) »).
_MARKDOWN_PIPE = re.compile(r"\\\|")


def _ansible_markup(text: str) -> str:
    """Le contrat écrit en Markdown et en HTML ; Ansible lit `L()` et des phrases.

    Mesuré : antsibull-docs refuse un lien `[texte](url)` (« Link is formatted
    in Markdown style »), ce qui a rougi les cinq jobs `collection` d'une pull
    request ; et un `<br />` arrive tel quel dans la page. Le lien devient
    `L(texte, url)`, le code `` `io1` `` devient `C(io1)`, la barre échappée
    `\\|` redevient `|`, le saut de ligne un espace, et rien d'autre n'est
    touché.
    """
    text = _MARKDOWN_LINK.sub(lambda match: f"L({match.group(1)}, {match.group(2)})", text)
    text = _MARKDOWN_CODE.sub(lambda match: f"C({match.group(1)})", text)
    text = _MARKDOWN_PIPE.sub("|", text)
    return _HTML_BREAK.sub(" ", text).strip()


def _describe(
    parameter: ApiParameter, override: ParameterOverride | None = None
) -> tuple[str, ...]:
    """La description du contrat, complétée des clés d'un objet référencé.

    Rien n'est inventé : les clés viennent des propriétés du schéma que le
    contrat référence (`FiltersVm` en porte 67), et elles sont ce qu'un
    utilisateur a besoin de connaître pour écrire un filtre sans lire l'API.

    **Le contrat gagne, l'override comble.** L'ordre est celui-là et pas
    l'inverse : un override qui recouvrirait la phrase d'Outscale ferait
    diverger la page publiée de l'API sans que rien ne le signale. Devenu
    inutile, l'override sort en orphelin plutôt qu'en silence.
    """
    comble = override.description if override is not None else None
    text = _ansible_markup(parameter.description or comble or UNDOCUMENTED)
    if parameter.properties and parameter.type is ApiType.OBJECT:
        keys = ", ".join(f"C({key})" for key in parameter.properties)
        text = f"{text} Accepted keys: {keys}."
    lignes = [text]
    if parameter.deprecated:
        lignes.append(DEPRECATED_NOTICE)
    return tuple(lignes)


def _lisible(mots: str) -> str:
    """Rend une suite de mots publiable, les abréviations en capitales."""
    return " ".join(ACRONYMES.get(mot, mot) for mot in mots.split(" "))


def _list_elements(service: ApiService, binding: OperationBinding) -> str:
    """Le type des éléments d'une liste rendue, lu dans l'enveloppe de la réponse.

    `dict` quand le contrat ne dit rien : c'est la forme de 56 lectures sur
    57. `ReadPublicIpRanges` rend des chaînes, et la page disait `dict`.
    """
    enveloppe = service.object(binding.response_schema)
    champ = enveloppe.field(binding.payload_field) if enveloppe and binding.payload_field else None
    if champ is None or champ.type is not ApiType.ARRAY:
        return "dict"
    return return_type(champ.item_type or ApiType.OBJECT)


def _article(mots: str) -> str:
    """« an image », « an IP », « a VM » : l'article indéfini qui précède."""
    return "an" if mots[:1].lower() in "aeiou" else "a"


def _camel(resource: str) -> str:
    """`net_peering` -> `NetPeering`, la forme que le contrat emploie dans ses clés."""
    return "".join(part.capitalize() for part in resource.split("_"))


def _id_filter_key(resource: str, keys: tuple[str, ...]) -> str | None:
    """La clé de `Filters` qui sélectionne par identifiant, lue dans le schéma.

    Celle qui porte le nom de la ressource (`VmIds` pour `vm`), sinon la seule
    clé `*Ids` du schéma (`VmIds` pour `vm_state`, `ResourceIds` pour `tag`),
    sinon rien : un exemple ne montre pas une clé que le schéma ne porte pas.
    """
    propre = _camel(resource) + FILTER_IDS
    if propre in keys:
        return propre
    candidats = [key for key in keys if key.endswith(FILTER_IDS)]
    return candidats[0] if len(candidats) == 1 else None


#: Ce qu'un exemple montre pour une chaîne libre, par convention de nom.
#:
#: **Ce n'est pas une affirmation sur l'API.** Ces champs n'ont pas de
#: vocabulaire : le contrat les déclare `string` sans enum, donc toute chaîne
#: y est valide, et ce qui se décide ici est seulement ce qu'un lecteur voit.
#: Un champ dont le vocabulaire existe ailleurs que dans un enum du contrat
#: n'a rien à faire ici : il se règle par un override `example`, avec sa raison.
def _valeur_par_convention(name: str) -> Any:
    if name == "description":
        return "Managed by Ansible"
    if name == "public_ip":
        return EXAMPLE_PUBLIC_IP
    if name.endswith("_names"):
        return [f"my-{name[: -len('_names')].replace('_', '-')}"]
    if name.endswith("_name"):
        return f"my-{name[: -len('_name')].replace('_', '-')}"
    return None


def _fields_of(
    service: ApiService,
    schema: str | None,
    overrides: OverrideSet,
    *,
    returned: str = "when the API returns it",
    depth: int = 0,
) -> tuple[ReturnField, ...]:
    """Les champs que le contrat déclare sur la ressource rendue.

    Rend un tuple vide quand le contrat ne porte pas le schéma : un `contains`
    inventé décrirait une réponse que personne n'a lue. Un champ sans
    description sort quand même, avec le repli : sa **présence** est une
    information, et la porte documentaire refuse ensuite de publier le repli.

    Deux étages pour la phrase, du plus sûr au moins sûr : ce que le contrat
    dit du champ, puis ce qu'un override `returns` décide, avec sa raison.
    Mesuré sur 1.42.0 : les 258 champs des 30 schémas rendus sont décrits,
    et le second étage n'a aujourd'hui aucun client sur le contrat réel.
    """
    objet = service.object(schema)
    if objet is None:
        return ()
    champs: list[ReturnField] = []
    for champ in objet.fields:
        phrase = champ.description or overrides.described(objet.name, champ.name) or UNDOCUMENTED
        lignes = [_ansible_markup(phrase)]
        if champ.deprecated:
            lignes.append(DEPRECATED_NOTICE)
        champs.append(
            ReturnField(
                name=champ.name,
                type=return_type(champ.type),
                description=tuple(lignes),
                returned=returned,
                # Un tableau sans `items` est un cas mesuré du contrat, pas une
                # exception : le repli `str` est celui de l'`argument_spec`.
                elements=(
                    return_type(champ.item_type or ApiType.STRING)
                    if champ.type is ApiType.ARRAY
                    else None
                ),
                contains=(
                    _fields_of(service, champ.ref, overrides, depth=depth - 1)
                    if depth > 0 and champ.type in (ApiType.OBJECT, ApiType.ARRAY)
                    else ()
                ),
            )
        )
    return tuple(champs)


def _action_result_fields(
    service: ApiService,
    actions: list[ActionBinding],
    overrides: OverrideSet,
) -> tuple[ReturnField, ...]:
    """Les champs de `result`, la réponse d'une action hors contexte.

    Chaque action a son enveloppe, et elles diffèrent : `StopVms` rend `Vms`,
    `RebootVms` ne rend rien. La clé est partagée, donc ses champs sont
    l'union, et chacun dit après quelles actions il est rendu. Quand deux
    enveloppes décrivent le même champ par deux phrases (« started VMs »,
    « stopped VMs »), chacune sort avec son action : en garder une ferait
    dire « started » d'un arrêt. La ressource que l'enveloppe porte est
    décrite un niveau plus bas : c'est là que le lecteur trouve ce qu'un
    `VmState` contient.
    """
    par_nom: dict[str, ReturnField] = {}
    phrases: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for action in actions:
        for champ in _fields_of(service, action.operation.response_schema, overrides, depth=1):
            par_nom.setdefault(champ.name, champ)
            phrases.setdefault(champ.name, []).append((action.name, champ.description))
    resultat: list[ReturnField] = []
    for nom, champ in par_nom.items():
        distinctes = {description for _, description in phrases[nom]}
        description = (
            champ.description
            if len(distinctes) == 1
            else tuple(f"After C({action}): {' '.join(lignes)}" for action, lignes in phrases[nom])
        )
        resultat.append(
            replace(
                champ,
                description=description,
                returned="after " + ", ".join(f"C({action})" for action, _ in phrases[nom]),
            )
        )
    return tuple(resultat)


def _apply_parameter_override(
    parameter: ApiParameter, override: ParameterOverride | None
) -> ApiParameter:
    """Applique ce qu'un humain a décidé d'un paramètre : type, obligation, choix."""
    if override is None:
        return parameter
    changes: dict[str, Any] = {}
    if override.type is not None:
        changes["type"] = override.type
    if override.required is not None:
        changes["required"] = override.required
    if override.choices:
        changes["enum_values"] = tuple(override.choices)
        changes["type"] = ApiType.ENUM
    if not changes:
        return parameter
    return replace(parameter, **changes)


def _binding(
    operation: ApiOperation, override: OperationOverride | None = None
) -> OperationBinding:
    body = {
        _resolved_option(p, override): p.name
        for p in operation.parameters
        if not p.read_only
        and not _hidden(p, override)
        and _resolved_option(p, override) not in REQUEST_FLAGS
    }
    response = operation.response
    return OperationBinding(
        id=operation.id,
        method=sdk_method(operation.id),
        body_params=body,
        payload_field=response.payload_field if response else None,
        is_list=bool(response and response.is_list),
        page_token=response.page_token if response else None,
        payload_schema=response.payload_schema if response else None,
        response_schema=response.schema if response else None,
    )


def _hidden(parameter: ApiParameter, override: OperationOverride | None) -> bool:
    """Vrai quand un override retire le paramètre des options du module."""
    if override is None:
        return False
    parameter_override = override.parameters.get(parameter.name)
    return parameter_override is not None and parameter_override.expose is False
