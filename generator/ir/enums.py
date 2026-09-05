"""Concepts fermés de la représentation intermédiaire.

Chaque enum décrit un ensemble de valeurs que la chaîne de génération traite
exhaustivement. Une valeur inconnue est représentée explicitement (UNKNOWN)
plutôt que perdue : le rapport doit pouvoir dire ce que le générateur n'a pas
su interpréter.

Il n'y a pas de `Scope` ici, et c'est une différence mesurée avec Scaleway :
Outscale porte la région dans l'URL du serveur (`api.{region}.outscale.com`),
pas dans le chemin, et la sous-région (`eu-west-2a`) est une propriété de la
ressource (`Placement.SubregionName`), pas un paramètre d'appel. Toute
opération est régionale de la même façon, et la liste des régions vit sur le
service (`ApiService.regions`), pas sur l'opération.
"""

from __future__ import annotations

from enum import StrEnum


class HTTPMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParameterLocation(StrEnum):
    PATH = "path"
    QUERY = "query"
    BODY = "body"
    HEADER = "header"


class ApiType(StrEnum):
    """Type d'un paramètre, indépendant d'Ansible et du SDK."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    ARRAY = "array"
    MAP = "map"
    OBJECT = "object"
    UNKNOWN = "unknown"


class OperationKind(StrEnum):
    """Classification Ansible d'une opération de l'API."""

    INFO = "info"
    ACTION = "action"
    MANAGE = "manage"
    WORKFLOW = "workflow"
    LIFECYCLE = "lifecycle"
    IGNORE = "ignore"
    UNKNOWN = "unknown"


class GenerationMode(StrEnum):
    """Origine de la décision de classification, pour le rapport de couverture."""

    AUTO = "auto"
    OVERRIDE = "override"
    MANUAL = "manual"


#: Classifications qui participent au dénominateur de la couverture Day-2.
DAY2_KINDS: frozenset[OperationKind] = frozenset(
    {
        OperationKind.INFO,
        OperationKind.ACTION,
        OperationKind.MANAGE,
        OperationKind.WORKFLOW,
    }
)
