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
    sdk_method,
)
from generator.ir.enums import ApiType, OperationKind
from generator.ir.models import ApiOperation, ApiParameter
from generator.overrides.loader import OperationOverride, OverrideSet, ParameterOverride
from generator.parser.naming import pluralize_phrase, split_words
from generator.plan import OperationPlan, ProductPlan

#: Classes que le renderer sait produire aujourd'hui. Une classe absente n'est
#: pas ignorée : elle est rendue dans le rapport de génération avec sa raison.
RENDERABLE_KINDS: frozenset[OperationKind] = frozenset(
    {OperationKind.INFO, OperationKind.ACTION, OperationKind.MANAGE}
)

#: Ce qu'on écrit quand le contrat ne décrit pas un paramètre.
UNDOCUMENTED = "Not documented by the Outscale API contract."

#: Identifiant d'exemple. Un exemple montre une forme, pas une ressource, et
#: les identifiants d'Outscale portent un préfixe par ressource (`i-`, `vol-`)
#: qu'un exemple générique ne doit pas prétendre connaître.
EXAMPLE_ID = "example-id"

#: Région d'exemple : celle que le contrat déclare par défaut.
EXAMPLE_REGION = "eu-west-2"

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
    option_docs: dict[str, str]
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
        return self.resource.replace("_", " ")

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
            option: dict[str, Any] = {"description": self.option_docs.get(name, UNDOCUMENTED)}
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
                return f"Gather information about Outscale {pluralize_phrase(self.resource)}"
            return f"Read the Outscale {self.resource_words}"
        if self.kind is OperationKind.MANAGE:
            return f"Manage the settings of an Outscale {self.resource_words}"
        return f"Perform an action on Outscale {pluralize_phrase(self.resource)}"

    def long_description(self) -> str:
        if self.kind is OperationKind.INFO:
            if self.operation is not None and self.operation.is_list:
                return (
                    f"List Outscale {pluralize_phrase(self.resource)}, optionally filtered. "
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
        return (
            f"Trigger one of the following actions on existing "
            f"{pluralize_phrase(self.resource)}: {names}."
        )

    def examples_documentation(self) -> list[dict[str, Any]]:
        fqcn = self.collection.module_fqcn(self.name)
        if self.kind is OperationKind.INFO:
            task: dict[str, Any] = {"region": EXAMPLE_REGION}
            for name, entry in self.options.items():
                if entry.get("required"):
                    task[name] = self._example_value(entry)
            is_list = self.operation is not None and self.operation.is_list
            title = (
                f"List {pluralize_phrase(self.resource)}"
                if is_list
                else f"Read the {self.resource_words}"
            )
            examples: list[dict[str, Any]] = [{"name": title, fqcn: task, "register": "result"}]
            if is_list and "filters" in self.options:
                examples.append(
                    {
                        "name": f"List {pluralize_phrase(self.resource)} matching a filter",
                        fqcn: {
                            "region": EXAMPLE_REGION,
                            "filters": {"Tags": ["role=web"]},
                        },
                        "register": "result",
                    }
                )
            return examples
        if self.kind is OperationKind.MANAGE:
            task = {"region": EXAMPLE_REGION}
            for name, entry in self.options.items():
                if entry.get("required"):
                    task[name] = self._example_value(entry)
            # `actions_on_next_boot: {}` n'apprend rien à qui lit l'exemple : une
            # option scalaire d'abord, un dictionnaire ou une liste à défaut.
            scalars = [n for n in self.compare if self.options[n]["type"] not in ("dict", "list")]
            for name in scalars or list(self.compare):
                if name not in task:
                    task[name] = self._example_value(self.options[name])
                    break
            return [{"name": f"Set the settings of a {self.resource_words}", fqcn: task}]
        first = self.actions[0]
        task = {"region": EXAMPLE_REGION, "action": first.name}
        for name, entry in self.options.items():
            if name != "action" and (entry.get("required") or name in first.required):
                task[name] = self._example_value(entry)
        return [{"name": f"Run {first.name} on a {self.resource_words}", fqcn: task}]

    @staticmethod
    def _example_value(entry: dict[str, Any]) -> Any:
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
        if self.kind is OperationKind.INFO:
            if self.operation is not None and self.operation.is_list:
                plural = pluralize_phrase(self.resource).replace(" ", "_")
                return {
                    plural: {
                        "description": f"The {pluralize_phrase(self.resource)}.",
                        "returned": "always",
                        "type": "list",
                        "elements": "dict",
                    }
                }
            return {
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
        if self.kind is OperationKind.MANAGE:
            return {
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
        returned: dict[str, Any] = {
            "result": {
                "description": ("The API response of the action, without the response context."),
                "returned": "when the action was sent",
                "type": "dict",
            }
        }
        if self.waitable and self.state_field is not None:
            returned["states"] = {
                "description": (
                    f"The C({self.state_field}) of each {self.resource_words}, by identifier, "
                    "read after the action."
                ),
                "returned": "when an expected state is declared for the action",
                "type": "dict",
            }
        return returned


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
    docs: dict[str, str] = {}
    limits: list[str] = []
    required = _collect_options(item, plan.overrides, options, docs, limits, required_allowed=True)
    for option in required:
        options[option]["required"] = True

    sensitive = bool(SENSITIVE_WORDS & set(split_words(item.operation.id)))
    return AnsibleModuleSpec(
        name=name,
        kind=OperationKind.INFO,
        product=plan.service.name,
        resource=item.resource,
        collection=collection,
        options=options,
        option_docs=docs,
        operation=_binding(item.operation, plan.overrides.get(item.operation.key)),
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
    docs: dict[str, str] = {}
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
            item, plan.overrides, options, docs, limits, required_allowed=False
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
    docs["action"] = "The action to trigger on the " + pluralize_phrase(resource) + "."

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
    docs: dict[str, str] = {}
    limits: list[str] = []
    required = _collect_options(item, plan.overrides, options, docs, limits, required_allowed=False)
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
    docs: dict[str, str],
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
            docs[name] = _describe(parameter)
    return required


#: Un lien Markdown du contrat : `[texte](url)`. 130 dans le contrat 1.42.0.
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
#: Un saut de ligne HTML du contrat : `<br />`. 426 dans le contrat 1.42.0.
_HTML_BREAK = re.compile(r"\s*<br\s*/?>\s*")
#: Un code Markdown du contrat : `` `io1` ``. 1054 dans le contrat 1.42.0.
_MARKDOWN_CODE = re.compile(r"`([^`\n]+)`")


def _ansible_markup(text: str) -> str:
    """Le contrat écrit en Markdown et en HTML ; Ansible lit `L()` et des phrases.

    Mesuré : antsibull-docs refuse un lien `[texte](url)` (« Link is formatted
    in Markdown style »), ce qui a rougi les cinq jobs `collection` d'une pull
    request ; et un `<br />` arrive tel quel dans la page. Le lien devient
    `L(texte, url)`, le code `` `io1` `` devient `C(io1)`, le saut de ligne un
    espace, et rien d'autre n'est touché.
    """
    text = _MARKDOWN_LINK.sub(lambda match: f"L({match.group(1)}, {match.group(2)})", text)
    text = _MARKDOWN_CODE.sub(lambda match: f"C({match.group(1)})", text)
    return _HTML_BREAK.sub(" ", text).strip()


def _describe(parameter: ApiParameter) -> str:
    """La description du contrat, complétée des clés d'un objet référencé.

    Rien n'est inventé : les clés viennent des propriétés du schéma que le
    contrat référence (`FiltersVm` en porte 67), et elles sont ce qu'un
    utilisateur a besoin de connaître pour écrire un filtre sans lire l'API.
    """
    text = _ansible_markup(parameter.description or UNDOCUMENTED)
    if parameter.properties and parameter.type is ApiType.OBJECT:
        keys = ", ".join(f"C({key})" for key in parameter.properties)
        text = f"{text} Accepted keys: {keys}."
    return text


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
    )


def _hidden(parameter: ApiParameter, override: OperationOverride | None) -> bool:
    """Vrai quand un override retire le paramètre des options du module."""
    if override is None:
        return False
    parameter_override = override.parameters.get(parameter.name)
    return parameter_override is not None and parameter_override.expose is False
