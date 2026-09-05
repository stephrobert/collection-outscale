"""Chargement des décisions humaines qui corrigent la classification.

La classification automatique ne sera jamais parfaite : elle lit un contrat,
pas une intention. Les overrides sont l'endroit où l'intention s'écrit, une
opération à la fois, avec sa raison.

Trois garde-fous, parce qu'un override est une affirmation :

* **les clés inconnues sont refusées.** Une faute de frappe dans un nom de
  champ produirait un override silencieusement inerte ;
* **les overrides orphelins sont signalés.** Un override qui ne désigne aucune
  opération existante décrit une API qui n'existe plus, et le rapport le dit ;
* **retirer un module demande une raison.** `expose: false` sur une opération
  Day-2 la laisse classée et la retire des modules : c'est la décision de ne
  pas publier ce que l'exemple n'exerce pas, et elle se relit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from generator.ir.enums import ApiType, GenerationMode, OperationKind
from generator.ir.models import ApiService

DEFAULT_OVERRIDES_ROOT = Path(__file__).resolve().parent

#: Champs qu'un override peut porter. Tout autre nom est une erreur.
KNOWN_FIELDS: frozenset[str] = frozenset(
    {"generation", "module", "resource", "reason", "expose", "parameters", "wait"}
)

#: Valeurs acceptées pour `generation`, et ce qu'elles décident.
#: `manual` n'est pas une classe : c'est une classe WORKFLOW dont
#: l'implémentation reste écrite à la main, donc exclue de la couverture
#: automatique.
_GENERATION_VALUES: dict[str, tuple[OperationKind, GenerationMode]] = {
    "info": (OperationKind.INFO, GenerationMode.OVERRIDE),
    "action": (OperationKind.ACTION, GenerationMode.OVERRIDE),
    "manage": (OperationKind.MANAGE, GenerationMode.OVERRIDE),
    "workflow": (OperationKind.WORKFLOW, GenerationMode.MANUAL),
    "manual": (OperationKind.WORKFLOW, GenerationMode.MANUAL),
    "lifecycle": (OperationKind.LIFECYCLE, GenerationMode.OVERRIDE),
    "ignore": (OperationKind.IGNORE, GenerationMode.OVERRIDE),
}


class OverrideError(ValueError):
    """Le fichier d'overrides contient une déclaration que le générateur refuse."""


#: Champs qu'un override de paramètre peut porter.
_PARAMETER_FIELDS: frozenset[str] = frozenset(
    {"choices", "required", "expose", "type", "option", "reason"}
)

#: Types qu'un override peut poser sur un paramètre dont le contrat tait le type.
_TYPE_VALUES: dict[str, ApiType] = {
    "string": ApiType.STRING,
    "integer": ApiType.INTEGER,
    "boolean": ApiType.BOOLEAN,
}

#: Champs qu'un bloc `wait` peut porter.
_WAIT_FIELDS: frozenset[str] = frozenset({"field", "states", "reason", "always"})


@dataclass(frozen=True)
class ParameterOverride:
    """Restriction humaine posée sur un paramètre du contrat."""

    name: str
    choices: tuple[str, ...] = ()
    required: bool | None = None
    #: Faux retire le paramètre des options du module. Il reste dans le contrat
    #: et dans le rapport : ce qui est retiré est dit, pas effacé.
    expose: bool | None = None
    type: ApiType | None = None
    #: Nom d'option Ansible imposé, quand celui que le mapping calcule ne va
    #: pas. Le module garde le nom du contrat à côté : le runtime envoie le
    #: nom du contrat, jamais le nom de l'option.
    option: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class WaitOverride:
    """Ce qu'une action laisse derrière elle, et comment le vérifier.

    L'API d'Outscale répond tout de suite, et la ressource change d'état
    ensuite : `StopVms` rend `stopping`, puis la machine passe `stopped`. Ce
    bloc dit quel champ de la ressource porte l'état (`State`, ou un chemin
    pointé comme `State.Name` pour un état imbriqué) et quel état chaque
    action vise, pour que le runtime relise la ressource jusque là.
    """

    field: str
    states: dict[str, str]
    reason: str | None = None
    #: Les actions qui agissent même quand l'état attendu est déjà atteint.
    #: `reboot` vise `running` et doit redémarrer une machine qui tourne ;
    #: `start` vise `running` et n'a rien à faire sur une machine qui tourne.
    always: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationOverride:
    """Décision humaine portant sur une opération, identifiée par sa clé."""

    key: str
    kind: OperationKind | None = None
    mode: GenerationMode | None = None
    module: str | None = None
    resource: str | None = None
    reason: str | None = None
    expose: bool | None = None
    parameters: dict[str, ParameterOverride] = field(default_factory=dict)
    wait: WaitOverride | None = None


@dataclass(frozen=True)
class OverrideSet:
    """Ensemble des overrides d'un produit."""

    source: Path | None
    operations: dict[str, OperationOverride] = field(default_factory=dict)

    def get(self, key: str) -> OperationOverride | None:
        return self.operations.get(key)

    def orphans(self, service: ApiService) -> tuple[str, ...]:
        """Clés d'override qui ne désignent aucune opération du contrat."""
        known = {operation.key for operation in service.operations}
        return tuple(sorted(key for key in self.operations if key not in known))


def load_overrides(product: str, root: Path = DEFAULT_OVERRIDES_ROOT) -> OverrideSet:
    """Charge `<root>/<product>.yml`, ou un ensemble vide s'il n'existe pas."""
    path = root / f"{product}.yml"
    if not path.is_file():
        return OverrideSet(source=None)

    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    if not isinstance(document, dict):
        raise OverrideError(f"{path} : le document doit être un mapping")

    unknown_sections = set(document) - {"operations"}
    if unknown_sections:
        raise OverrideError(f"{path} : sections inconnues {sorted(unknown_sections)}")

    operations: dict[str, OperationOverride] = {}
    for key, raw in (document.get("operations") or {}).items():
        operations[str(key)] = _parse_override(str(key), raw, path)
    return OverrideSet(source=path, operations=operations)


def _parse_override(key: str, raw: Any, path: Path) -> OperationOverride:
    if not isinstance(raw, dict):
        raise OverrideError(f"{path} : {key} doit être un mapping")

    unknown = set(raw) - KNOWN_FIELDS
    if unknown:
        raise OverrideError(
            f"{path} : {key} porte des champs inconnus {sorted(unknown)}. "
            f"Champs acceptés : {sorted(KNOWN_FIELDS)}"
        )

    kind: OperationKind | None = None
    mode: GenerationMode | None = None
    generation = raw.get("generation")
    if generation is not None:
        if generation not in _GENERATION_VALUES:
            raise OverrideError(
                f"{path} : {key} déclare generation={generation!r}, "
                f"valeurs acceptées : {sorted(_GENERATION_VALUES)}"
            )
        kind, mode = _GENERATION_VALUES[generation]

    if generation is not None and not raw.get("reason"):
        raise OverrideError(
            f"{path} : {key} change la classification sans `reason`. "
            "Un override sans raison est indéfendable à la relecture."
        )

    expose = raw.get("expose")
    if expose is False and not raw.get("reason"):
        raise OverrideError(
            f"{path} : {key} retire l'opération des modules sans `reason`. "
            "Ne pas publier un module est une décision, et elle se relit."
        )

    return OperationOverride(
        key=key,
        kind=kind,
        mode=mode,
        module=raw.get("module"),
        resource=raw.get("resource"),
        reason=raw.get("reason"),
        expose=expose,
        parameters=_parse_parameters(key, raw.get("parameters"), path),
        wait=_parse_wait(key, raw.get("wait"), path),
    )


def _parse_parameters(key: str, raw: Any, path: Path) -> dict[str, ParameterOverride]:
    """Lit et valide les restrictions posées sur des paramètres."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OverrideError(f"{path} : {key}.parameters doit être un mapping")

    parametres: dict[str, ParameterOverride] = {}
    for nom, declaration in raw.items():
        if not isinstance(declaration, dict):
            raise OverrideError(f"{path} : {key}.parameters.{nom} doit être un mapping")

        inconnus = set(declaration) - _PARAMETER_FIELDS
        if inconnus:
            raise OverrideError(
                f"{path} : {key}.parameters.{nom} porte des champs inconnus "
                f"{sorted(inconnus)}. Champs acceptés : {sorted(_PARAMETER_FIELDS)}"
            )

        choices = declaration.get("choices")
        if choices is not None and not isinstance(choices, list):
            raise OverrideError(f"{path} : {key}.parameters.{nom}.choices doit être une liste")

        type_name = declaration.get("type")
        if type_name is not None and type_name not in _TYPE_VALUES:
            raise OverrideError(
                f"{path} : {key}.parameters.{nom}.type={type_name!r}, "
                f"valeurs acceptées : {sorted(_TYPE_VALUES)}"
            )

        arbitrages = ("choices", "required", "expose", "type", "option")
        decide = any(declaration.get(champ) is not None for champ in arbitrages)
        if decide and not declaration.get("reason"):
            raise OverrideError(
                f"{path} : {key}.parameters.{nom} décide quelque chose sans `reason`. "
                "Restreindre, exiger, typer, renommer ou masquer un paramètre du contrat "
                "est un arbitrage, pas une correction."
            )

        parametres[str(nom)] = ParameterOverride(
            name=str(nom),
            choices=tuple(str(valeur) for valeur in choices or ()),
            required=declaration.get("required"),
            expose=declaration.get("expose"),
            type=_TYPE_VALUES[type_name] if type_name is not None else None,
            option=declaration.get("option"),
            reason=declaration.get("reason"),
        )
    return parametres


def _parse_wait(key: str, raw: Any, path: Path) -> WaitOverride | None:
    """Lit et valide la correspondance action -> état attendu."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise OverrideError(f"{path} : {key}.wait doit être un mapping")

    inconnus = set(raw) - _WAIT_FIELDS
    if inconnus:
        raise OverrideError(
            f"{path} : {key}.wait porte des champs inconnus {sorted(inconnus)}. "
            f"Champs acceptés : {sorted(_WAIT_FIELDS)}"
        )

    states = raw.get("states")
    if not isinstance(states, dict) or not states:
        raise OverrideError(f"{path} : {key}.wait.states doit être un mapping non vide")
    if not raw.get("reason"):
        raise OverrideError(
            f"{path} : {key}.wait déclare des états attendus sans `reason`. "
            "Le contrat ne les dit pas : c'est une décision, et elle se justifie."
        )

    always_raw = raw.get("always") or ()
    if isinstance(always_raw, str) or not isinstance(always_raw, list | tuple):
        raise OverrideError(f"{path} : {key}.wait.always doit être une liste d'actions")
    always = tuple(str(action) for action in always_raw)
    hors_etats = sorted(set(always) - set(states))
    if hors_etats:
        raise OverrideError(
            f"{path} : {key}.wait.always nomme {hors_etats}, qui n'ont pas d'état attendu "
            "dans `states`. Une action qui agit toujours doit dire vers quel état."
        )

    return WaitOverride(
        field=str(raw.get("field") or "State"),
        states={str(action): str(etat) for action, etat in states.items()},
        reason=raw.get("reason"),
        always=always,
    )
