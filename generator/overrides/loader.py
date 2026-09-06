"""Chargement des décisions humaines qui corrigent la classification.

La classification automatique ne sera jamais parfaite : elle lit un contrat,
pas une intention. Les overrides sont l'endroit où l'intention s'écrit, une
opération à la fois, avec sa raison.

Quatre garde-fous, parce qu'un override est une affirmation :

* **les clés inconnues sont refusées.** Une faute de frappe dans un nom de
  champ produirait un override silencieusement inerte ;
* **une clé déclarée deux fois est refusée.** YAML garde la dernière et efface
  la première sans un mot : la décision disparaît, et le contrôle d'orphelins
  ne peut rien voir puisque la clé désigne bien une opération ;
* **les overrides orphelins sont signalés.** Un override qui ne désigne aucune
  opération existante décrit une API qui n'existe plus, et le rapport le dit.
  Un texte qui ne comble plus un trou du contrat l'est aussi : le jour où
  Outscale documente le champ, c'est sa phrase qui sort, et celle écrite ici
  devient un texte mort qu'une relecture croirait publié ;
* **retirer un module demande une raison.** `expose: false` sur une opération
  Day-2 la laisse classée et la retire des modules : c'est la décision de ne
  pas publier ce que l'exemple n'exerce pas, et elle se relit. Publier une
  phrase que le contrat ne porte pas en demande une aussi : elle sortira sur
  Galaxy sous le nom de la collection, indiscernable d'une phrase d'Outscale.
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
    {"choices", "required", "expose", "type", "option", "description", "example", "reason"}
)

#: Champs qu'un override de champ rendu peut porter.
_RETURN_FIELDS: frozenset[str] = frozenset({"description", "reason"})

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
    #: Description à publier **quand le contrat n'en porte aucune**, et
    #: seulement là. Le contrat gagne toujours : un override qui recouvrirait
    #: une phrase d'Outscale ferait diverger la page de l'API sans que rien ne
    #: le dise. Devenu inutile, il est signalé comme orphelin.
    description: str | None = None
    #: Valeur que l'exemple publiera, quand ni le contrat ni une convention de
    #: nom ne peuvent la donner. Le cas mesuré est `UpdateVolume.VolumeType` :
    #: le contrat en cite les trois valeurs dans une phrase, pas dans un enum,
    #: et le repli par type publiait `volume_type: example-id`, copiable et
    #: refusé par l'API.
    example: Any = None
    reason: str | None = None


@dataclass(frozen=True)
class ReturnOverride:
    """Ce qu'on publie d'un champ rendu que le contrat ne décrit pas.

    Le dernier recours, après la description que le contrat donne au champ.
    Ce qui s'écrit ici est une décision : la `reason` dit d'où elle vient, et
    le texte sortira sur Galaxy sous le nom de la collection.
    """

    schema: str
    field: str
    description: str
    reason: str


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
    #: Champs rendus, par nom de schéma puis nom de champ.
    returns: dict[str, dict[str, ReturnOverride]] = field(default_factory=dict)

    def get(self, key: str) -> OperationOverride | None:
        return self.operations.get(key)

    def described(self, schema: str | None, field_name: str) -> str | None:
        """La description qu'une décision humaine pose sur ce champ rendu."""
        if schema is None:
            return None
        pose = self.returns.get(schema, {}).get(field_name)
        return pose.description if pose else None

    def orphans(self, service: ApiService) -> tuple[str, ...]:
        """Overrides qui ne portent plus sur rien, par clé ou par effet.

        Deux façons pour un override de devenir inerte, et les deux disent la
        même chose : quelque chose a bougé en amont, et le fichier ne le sait
        pas encore.

        * **la clé ne désigne aucune opération**, ou aucun schéma, ou aucun
          champ. L'opération a disparu, ou la ressource déduite a changé et la
          clé avec elle ;
        * **la description ne comble plus rien.** Outscale a documenté le
          champ, donc c'est sa phrase qui sort, et celle écrite ici n'est plus
          lue par personne.

        Les deux sortent par le même canal, donc `report --strict` sort en 2
        dans les deux cas. C'est ce qui rend la dérive visible, et ça ne se
        désarme pas pour faire passer la CI.
        """
        par_cle = {operation.key: operation for operation in service.operations}
        inertes: list[str] = []
        for cle, override in self.operations.items():
            operation = par_cle.get(cle)
            if operation is None:
                inertes.append(cle)
                continue
            documentes = {p.name for p in operation.parameters if p.description}
            for nom, restriction in override.parameters.items():
                if restriction.description and nom in documentes:
                    inertes.append(
                        f"{cle}.parameters.{nom} : description d'override devenue "
                        "inutile, le contrat en porte une"
                    )
        par_schema = {objet.name: objet for objet in service.objects}
        for schema, champs in self.returns.items():
            objet = par_schema.get(schema)
            if objet is None:
                inertes.append(f"returns.{schema} : aucune réponse ne rend ce schéma")
                continue
            for champ in champs:
                declare = objet.field(champ)
                if declare is None:
                    inertes.append(f"returns.{schema}.{champ} : le schéma ne porte pas ce champ")
                elif declare.description:
                    inertes.append(
                        f"returns.{schema}.{champ} : description d'override devenue "
                        "inutile, le contrat en porte une"
                    )
        return tuple(sorted(inertes))


class _SansDoublon(yaml.SafeLoader):
    """Un chargeur YAML qui refuse une clé déclarée deux fois.

    **YAML garde la dernière occurrence, sans un mot.** Un second bloc écrit
    sous une clé déjà présente n'ajoute pas ses champs : il remplace tout le
    premier. Mesuré chez collection-scaleway : un second bloc a effacé un
    `resource`, et le module publié a changé de nom sans qu'aucun contrôle ne
    rougisse. Le contrôle d'orphelins ne pouvait pas l'attraper, la clé
    désignant bien une opération : c'est la décision qui avait disparu.
    """

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        vues: set[Any] = set()
        for cle_node, _ in node.value:
            cle = self.construct_object(cle_node, deep=deep)
            if cle in vues:
                raise OverrideError(
                    f"clé déclarée deux fois : {cle!r} (ligne "
                    f"{cle_node.start_mark.line + 1}). YAML garde la dernière et "
                    "efface la première en silence : réunir les deux blocs."
                )
            vues.add(cle)
        return super().construct_mapping(node, deep)


def load_overrides(product: str, root: Path = DEFAULT_OVERRIDES_ROOT) -> OverrideSet:
    """Charge `<root>/<product>.yml`, ou un ensemble vide s'il n'existe pas."""
    path = root / f"{product}.yml"
    if not path.is_file():
        return OverrideSet(source=None)

    with path.open(encoding="utf-8") as handle:
        document = yaml.load(handle, _SansDoublon) or {}
    if not isinstance(document, dict):
        raise OverrideError(f"{path} : le document doit être un mapping")

    unknown_sections = set(document) - {"operations", "returns"}
    if unknown_sections:
        raise OverrideError(f"{path} : sections inconnues {sorted(unknown_sections)}")

    operations: dict[str, OperationOverride] = {}
    for key, raw in (document.get("operations") or {}).items():
        operations[str(key)] = _parse_override(str(key), raw, path)
    return OverrideSet(
        source=path,
        operations=operations,
        returns=_parse_returns(document.get("returns"), path),
    )


def _parse_returns(raw: Any, path: Path) -> dict[str, dict[str, ReturnOverride]]:
    """Lit et valide les descriptions posées sur des champs rendus."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OverrideError(f"{path} : `returns` doit être un mapping de schémas")

    par_schema: dict[str, dict[str, ReturnOverride]] = {}
    for schema, champs in raw.items():
        if not isinstance(champs, dict):
            raise OverrideError(f"{path} : returns.{schema} doit être un mapping de champs")
        for champ, declaration in champs.items():
            if not isinstance(declaration, dict):
                raise OverrideError(f"{path} : returns.{schema}.{champ} doit être un mapping")
            inconnus = set(declaration) - _RETURN_FIELDS
            if inconnus:
                raise OverrideError(
                    f"{path} : returns.{schema}.{champ} porte des champs inconnus "
                    f"{sorted(inconnus)}. Champs acceptés : {sorted(_RETURN_FIELDS)}"
                )
            if not declaration.get("description"):
                raise OverrideError(f"{path} : returns.{schema}.{champ} n'écrit aucune description")
            if not declaration.get("reason"):
                raise OverrideError(
                    f"{path} : returns.{schema}.{champ} publie une description sans `reason`. "
                    "Elle sortira sur Galaxy sous le nom de la collection : la raison "
                    "doit dire d'où elle vient."
                )
            par_schema.setdefault(str(schema), {})[str(champ)] = ReturnOverride(
                schema=str(schema),
                field=str(champ),
                description=str(declaration["description"]).strip(),
                reason=str(declaration["reason"]),
            )
    return par_schema


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

        # **Écrire ce que le contrat ne dit pas est une décision, pas une
        # correction.** La phrase ou la valeur sera publiée sur Galaxy sous le
        # nom de la collection, et un lecteur n'a aucun moyen de la distinguer
        # de celles d'Outscale. La `reason` dit d'où elle vient.
        documente = any(declaration.get(champ) is not None for champ in ("description", "example"))
        if documente and not declaration.get("reason"):
            raise OverrideError(
                f"{path} : {key}.parameters.{nom} publie une description ou une valeur "
                "d'exemple sans `reason`. Ce texte sortira sur Galaxy sous le nom de "
                "la collection : la raison doit dire d'où il vient."
            )

        parametres[str(nom)] = ParameterOverride(
            name=str(nom),
            choices=tuple(str(valeur) for valeur in choices or ()),
            required=declaration.get("required"),
            expose=declaration.get("expose"),
            type=_TYPE_VALUES[type_name] if type_name is not None else None,
            option=declaration.get("option"),
            description=declaration.get("description"),
            example=declaration.get("example"),
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
