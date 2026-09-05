"""Traduction d'un document OpenAPI 3.0 d'Outscale vers l'IR canonique.

Le parser ne décide rien : il traduit. Toute décision (est-ce un module, sous
quel nom, exposé ou non) appartient au classifieur et aux overrides. Ce qu'il
ne comprend pas, il le signale dans `ApiService.warnings` plutôt que de le
laisser disparaître.

Ce que le document publié porte et ne porte pas est mesuré sur le contrat
1.42.0, pas supposé :

* **tout est un POST sur `/<OperationId>`**, sans paramètre de chemin ni de
  requête : 236 opérations, 236 corps `application/json` référencés par
  `<OperationId>Request`, 236 réponses `<OperationId>Response` ;
* **la pagination est un jeton.** 36 lectures portent `NextPageToken` dans
  leur requête et dans leur réponse, toujours ensemble, et `ResultsPerPage`
  avec. Les 38 autres rendent leur réponse en une fois ;
* **toute réponse porte un `ResponseContext`** qui n'est pas la ressource, et
  226 requêtes sur 236 portent un `DryRun` qui n'est pas une option ;
* **15 `oneOf`, tous de la même forme** : deux variantes `string`, l'une
  `date`, l'autre `date-time`. Le type est celui des variantes ; toute autre
  composition reste inconnue, et le rapport le dit ;
* **`required` est déclaré** sur 164 corps de requête sur 236 ; `readOnly` ne
  l'est nulle part, `nullable` sur 14 propriétés, `deprecated` sur quelques
  propriétés (`VmInitiatedShutdownBehavior` depuis 1.42.0).
"""

from __future__ import annotations

from typing import Any

from generator.ir.enums import ApiType, HTTPMethod, ParameterLocation
from generator.ir.models import ApiEnum, ApiOperation, ApiParameter, ApiResponse, ApiService
from generator.parser.naming import singularize_phrase, split_words
from generator.source.base import SpecDocument

#: Méthodes HTTP qu'un document peut porter. Outscale n'emploie que POST ; la
#: table reste complète pour qu'une autre méthode soit traduite puis signalée
#: par le classifieur, jamais perdue.
_METHODS: dict[str, HTTPMethod] = {
    "get": HTTPMethod.GET,
    "post": HTTPMethod.POST,
    "put": HTTPMethod.PUT,
    "patch": HTTPMethod.PATCH,
    "delete": HTTPMethod.DELETE,
}

_SCALAR_TYPES: dict[str, ApiType] = {
    "string": ApiType.STRING,
    "integer": ApiType.INTEGER,
    "number": ApiType.NUMBER,
    "boolean": ApiType.BOOLEAN,
    "array": ApiType.ARRAY,
    "object": ApiType.OBJECT,
}

#: Le champ que toute réponse porte et qui n'est jamais la ressource.
RESPONSE_CONTEXT = "ResponseContext"

#: Le jeton de pagination, tel que le contrat le nomme.
PAGE_TOKEN = "NextPageToken"


class ParseError(ValueError):
    """Le document n'a pas la forme qu'un contrat Outscale doit avoir."""


def parse_document(spec: SpecDocument) -> ApiService:
    """Construit l'IR d'un produit à partir de son document découpé."""
    document = spec.document
    if "paths" not in document:
        raise ParseError(f"{spec.path} ne déclare aucun chemin")

    schemas: dict[str, Any] = document.get("components", {}).get("schemas", {})
    warnings: list[str] = []
    enums: dict[str, ApiEnum] = {}
    operations: list[ApiOperation] = []

    for path, path_item in document["paths"].items():
        for method_name, method in _METHODS.items():
            operation = path_item.get(method_name)
            if operation is None:
                continue
            operations.append(
                _parse_operation(
                    spec=spec,
                    path=path,
                    method=method,
                    operation=operation,
                    schemas=schemas,
                    enums=enums,
                    warnings=warnings,
                )
            )

    unpaginated = sorted(
        op.id
        for op in operations
        if split_words(op.id)[:1] == ["read"]
        and not op.is_paginated
        and op.response is not None
        and op.response.is_list
    )
    if unpaginated:
        warnings.append(
            f"{len(unpaginated)} lecture(s) de liste sans jeton de page, rendue(s) en une "
            "réponse dont le contrat ne promet pas qu'elle soit complète : "
            + ", ".join(unpaginated)
        )

    info = document.get("info", {})
    return ApiService(
        name=spec.product,
        version=spec.version,
        title=info.get("title"),
        description=_first_paragraph(info.get("description")),
        source=str(spec.path.name),
        document_version=str(info["version"]) if info.get("version") else None,
        regions=_regions_of(document),
        operations=tuple(sorted(operations, key=lambda op: op.id)),
        enums=tuple(sorted(enums.values(), key=lambda enum: enum.name)),
        warnings=tuple(sorted(set(warnings))),
    )


def _regions_of(document: dict[str, Any]) -> tuple[str, ...]:
    """Les régions, lues dans la variable `{region}` de l'URL du serveur.

    Le chemin ne porte pas la région : c'est l'hôte qui la porte
    (`https://api.{region}.outscale.com/api/v1`). Mesuré : cinq régions
    déclarées, `eu-west-2` par défaut.
    """
    for server in document.get("servers", []):
        variables = server.get("variables", {})
        region = variables.get("region", {})
        values = region.get("enum")
        if values:
            return tuple(str(value) for value in values)
    return ()


def _parse_operation(
    *,
    spec: SpecDocument,
    path: str,
    method: HTTPMethod,
    operation: dict[str, Any],
    schemas: dict[str, Any],
    enums: dict[str, ApiEnum],
    warnings: list[str],
) -> ApiOperation:
    operation_id = operation.get("operationId")
    if not operation_id:
        raise ParseError(f"{method.value} {path} n'a pas d'operationId")

    parameters: list[ApiParameter] = []
    for declared in operation.get("parameters", []):
        parameters.append(
            _parse_parameter(
                declared=declared,
                schemas=schemas,
                enums=enums,
                warnings=warnings,
                operation_id=operation_id,
            )
        )
    parameters.extend(
        _parse_body(
            operation=operation,
            schemas=schemas,
            enums=enums,
            warnings=warnings,
            operation_id=operation_id,
        )
    )
    requests_page = any(p.name == PAGE_TOKEN for p in parameters)

    return ApiOperation(
        id=operation_id,
        product=spec.product,
        version=spec.version,
        resource=derive_resource(operation_id),
        http_method=method,
        path=path,
        parameters=tuple(parameters),
        response=_parse_response(operation, schemas, warnings, operation_id, requests_page),
        summary=operation.get("summary") or None,
        description=_first_paragraph(operation.get("description")),
        deprecated=bool(operation.get("deprecated")),
        tags=tuple(operation.get("tags") or ()),
    )


def _parse_parameter(
    *,
    declared: dict[str, Any],
    schemas: dict[str, Any],
    enums: dict[str, ApiEnum],
    warnings: list[str],
    operation_id: str,
) -> ApiParameter:
    name = str(declared["name"])
    location = ParameterLocation(declared.get("in", "query"))
    schema = declared.get("schema")
    if schema is None:
        warnings.append(f"{operation_id}.{name} : paramètre sans schéma, type inconnu")
        resolved = _ResolvedType(ApiType.UNKNOWN)
        schema = {}
    else:
        resolved = _resolve_type(
            schema=schema,
            schemas=schemas,
            enums=enums,
            warnings=warnings,
            context=f"{operation_id}.{name}",
        )
    return ApiParameter(
        name=name,
        type=resolved.type,
        required=bool(declared.get("required", location is ParameterLocation.PATH)),
        location=location,
        description=_first_paragraph(declared.get("description")),
        enum_name=resolved.enum_name,
        enum_values=resolved.enum_values,
        item_type=resolved.item_type,
        default=resolved.default,
        deprecated=bool(schema.get("deprecated") or declared.get("deprecated")),
        format=schema.get("format"),
        ref=resolved.ref,
        properties=resolved.properties,
    )


def _parse_body(
    *,
    operation: dict[str, Any],
    schemas: dict[str, Any],
    enums: dict[str, ApiEnum],
    warnings: list[str],
    operation_id: str,
) -> list[ApiParameter]:
    body = operation.get("requestBody")
    if not body:
        return []
    schema = body.get("content", {}).get("application/json", {}).get("schema")
    if not schema:
        warnings.append(f"{operation_id} : corps de requête sans schéma JSON")
        return []
    schema = _deref(schema, schemas)
    properties: dict[str, Any] = schema.get("properties", {})
    if not properties:
        warnings.append(f"{operation_id} : corps de requête sans propriété déclarée")
    required = set(schema.get("required", ()))

    parameters: list[ApiParameter] = []
    for name, property_schema in properties.items():
        resolved = _resolve_type(
            schema=property_schema,
            schemas=schemas,
            enums=enums,
            warnings=warnings,
            context=f"{operation_id}.{name}",
        )
        parameters.append(
            ApiParameter(
                name=str(name),
                type=resolved.type,
                required=name in required,
                location=ParameterLocation.BODY,
                description=_first_paragraph(property_schema.get("description")),
                enum_name=resolved.enum_name,
                enum_values=resolved.enum_values,
                item_type=resolved.item_type,
                default=resolved.default,
                deprecated=bool(property_schema.get("deprecated")),
                format=property_schema.get("format"),
                ref=resolved.ref,
                read_only=bool(property_schema.get("readOnly")),
                properties=resolved.properties,
            )
        )
    return parameters


class _ResolvedType:
    """Résultat de la lecture d'un schéma de paramètre."""

    __slots__ = ("default", "enum_name", "enum_values", "item_type", "properties", "ref", "type")

    def __init__(
        self,
        type: ApiType,
        enum_name: str | None = None,
        enum_values: tuple[str, ...] = (),
        item_type: ApiType | None = None,
        default: object | None = None,
        ref: str | None = None,
        properties: tuple[str, ...] = (),
    ) -> None:
        self.type = type
        self.enum_name = enum_name
        self.enum_values = enum_values
        self.item_type = item_type
        self.default = default
        self.ref = ref
        self.properties = properties


def _resolve_type(
    *,
    schema: dict[str, Any],
    schemas: dict[str, Any],
    enums: dict[str, ApiEnum],
    warnings: list[str],
    context: str,
) -> _ResolvedType:
    """Traduit un schéma OpenAPI 3.0 en type de l'IR, en enregistrant les enums.

    Le contrat compose des types une seule fois, par `oneOf`, et toujours de
    la même façon : deux variantes `string`, l'une `date` et l'autre
    `date-time`, sur quinze champs de date. Des variantes d'un même type
    scalaire se lisent comme ce type. Toute autre composition (`anyOf`,
    `allOf`, ou un `oneOf` de types différents) est inconnue, et le rapport le
    dit.
    """
    if not schema:
        warnings.append(f"{context} : paramètre sans schéma, type inconnu")
        return _ResolvedType(ApiType.UNKNOWN)

    for composition in ("anyOf", "allOf"):
        if composition in schema:
            warnings.append(f"{context} : `{composition}` non traduit, type inconnu")
            return _ResolvedType(ApiType.UNKNOWN)

    if "oneOf" in schema:
        variants = {str(variant.get("type")) for variant in schema["oneOf"]}
        if (
            len(variants) == 1
            and (only := variants.pop()) in _SCALAR_TYPES
            and only
            not in (
                "array",
                "object",
            )
        ):
            return _ResolvedType(_SCALAR_TYPES[only], default=schema.get("default"))
        warnings.append(f"{context} : `oneOf` de types différents, type inconnu")
        return _ResolvedType(ApiType.UNKNOWN)

    ref = schema.get("$ref")
    if ref:
        target_name = ref.rsplit("/", 1)[-1]
        target = _deref(schema, schemas)
        resolved = _resolve_type(
            schema=target, schemas=schemas, enums=enums, warnings=warnings, context=context
        )
        if resolved.type is ApiType.ENUM:
            enums.setdefault(
                target_name,
                ApiEnum(
                    name=target_name,
                    values=resolved.enum_values,
                    default=target.get("default"),
                    description=_first_paragraph(target.get("description")),
                ),
            )
            return _ResolvedType(
                ApiType.ENUM,
                enum_name=target_name,
                enum_values=resolved.enum_values,
                default=target.get("default"),
                ref=target_name,
            )
        return _ResolvedType(
            resolved.type,
            item_type=resolved.item_type,
            ref=target_name,
            properties=resolved.properties,
        )

    raw_type = schema.get("type")

    if "enum" in schema:
        return _ResolvedType(
            ApiType.ENUM,
            enum_values=tuple(str(value) for value in schema["enum"]),
            default=schema.get("default"),
        )

    if raw_type == "object" or (raw_type is None and "properties" in schema):
        if schema.get("additionalProperties") and not schema.get("properties"):
            return _ResolvedType(ApiType.MAP, default=schema.get("default"))
        return _ResolvedType(
            ApiType.OBJECT,
            default=schema.get("default"),
            properties=tuple(sorted(str(name) for name in schema.get("properties", {}))),
        )

    if raw_type == "array":
        items = schema.get("items")
        if not items:
            warnings.append(f"{context} : tableau sans `items`, type des éléments inconnu")
            return _ResolvedType(ApiType.ARRAY, item_type=None)
        resolved_item = _resolve_type(
            schema=items,
            schemas=schemas,
            enums=enums,
            warnings=warnings,
            context=f"{context}[]",
        )
        return _ResolvedType(ApiType.ARRAY, item_type=resolved_item.type, ref=resolved_item.ref)

    if raw_type in _SCALAR_TYPES:
        return _ResolvedType(_SCALAR_TYPES[raw_type], default=schema.get("default"))

    warnings.append(f"{context} : type OpenAPI non traité ({raw_type!r})")
    return _ResolvedType(ApiType.UNKNOWN)


def _parse_response(
    operation: dict[str, Any],
    schemas: dict[str, Any],
    warnings: list[str],
    operation_id: str,
    requests_page: bool,
) -> ApiResponse | None:
    """Décrit la réponse de succès, et le champ qui porte réellement la ressource.

    Quatre formes mesurées sur les 236 réponses, `ResponseContext` et
    `NextPageToken` retirés :

    * 86 à un objet (`UpdateVm` rend `Vm`), la charge utile est cet objet ;
    * 57 à une liste (`ReadVms` rend `Vms`), la charge utile est cette liste ;
    * 79 vides (`LinkVolume`), l'opération ne rend que l'accusé ;
    * 14 à plusieurs propriétés (`ReadAdminPassword` rend `AdminPassword` et
      `VmId`), indécidables : le module rend la réponse entière, et le
      rapport nomme le cas.
    """
    responses = operation.get("responses", {})
    code = next((key for key in ("200", "201", "202", "204") if key in responses), None)
    if code is None:
        warnings.append(f"{operation_id} : aucune réponse de succès déclarée")
        return None
    success = responses[code]
    schema = success.get("content", {}).get("application/json", {}).get("schema")
    if not schema:
        return ApiResponse()

    ref = schema.get("$ref")
    name = ref.rsplit("/", 1)[-1] if ref else None
    resolved = _deref(schema, schemas)
    properties: dict[str, Any] = dict(resolved.get("properties", {}))
    page_token = None
    if PAGE_TOKEN in properties:
        properties.pop(PAGE_TOKEN)
        if requests_page:
            page_token = PAGE_TOKEN
        else:
            warnings.append(
                f"{operation_id} : la réponse porte {PAGE_TOKEN} sans que la requête le "
                "déclare ; la pagination n'est pas déroulée"
            )
    elif requests_page:
        warnings.append(
            f"{operation_id} : la requête porte {PAGE_TOKEN} sans que la réponse le rende ; "
            "la pagination n'est pas déroulée"
        )
    properties.pop(RESPONSE_CONTEXT, None)

    if not properties:
        return ApiResponse(schema=name, page_token=page_token)

    if len(properties) > 1:
        warnings.append(
            f"{operation_id} : réponse à {len(properties)} propriétés, charge utile indécidable"
        )
        return ApiResponse(
            schema=name, payload_fields=tuple(sorted(properties)), page_token=page_token
        )

    ((field_name, property_schema),) = properties.items()
    if property_schema.get("type") == "array":
        items = property_schema.get("items", {})
        items_ref = str(items.get("$ref", ""))
        payload_schema = items_ref.rsplit("/", 1)[-1] or None
        return ApiResponse(
            schema=name,
            payload_field=str(field_name),
            payload_schema=payload_schema,
            payload_fields=_fields_of(payload_schema, schemas),
            is_list=True,
            page_token=page_token,
        )
    property_ref = str(property_schema.get("$ref", ""))
    payload_schema = property_ref.rsplit("/", 1)[-1] or None
    return ApiResponse(
        schema=name,
        payload_field=str(field_name),
        payload_schema=payload_schema,
        payload_fields=_fields_of(payload_schema, schemas),
        page_token=page_token,
    )


def _fields_of(schema_name: str | None, schemas: dict[str, Any]) -> tuple[str, ...]:
    """Les propriétés d'un schéma nommé, triées ; vide sans schéma."""
    if schema_name is None:
        return ()
    return tuple(sorted(str(name) for name in schemas.get(schema_name, {}).get("properties", {})))


def derive_resource(operation_id: str) -> str:
    """Déduit la ressource portée par un identifiant, en snake_case singulier.

    La règle tient en une phrase : la ressource est l'`operationId` **privé de
    son verbe**, chaque mot au singulier. Le chemin n'entre pas en jeu : il est
    l'identifiant lui-même (`POST /StartVms`), et n'ajoute rien.

    * `ReadVms` -> `vm`, `StartVms` -> `vm`, `UpdateVm` -> `vm`
    * `ReadVmTypes` -> `vm_type`, `ReadVmsState` -> `vm_state`
    * `CreateLoadBalancerListeners` -> `load_balancer_listener`
    * `ReadAdminPassword` -> `admin_password`

    Ce qui diffère des deux autres clouds, et pourquoi : chez Scaleway et
    Exoscale, la ressource se lit dans le **chemin**, et la règle « premier et
    dernier segment » a coûté à chacun un piège documenté dans son
    `CLAUDE.md`. Ici le chemin ne porte que l'identifiant, et c'est
    l'identifiant qui nomme la ressource, ce qui rend la règle plus simple et
    ses défauts visibles dans le rapport : `RegisterVmsInLoadBalancer` donne
    `vm_in_load_balancer`, qui n'est pas un nom qu'un opérateur choisirait,
    mais qui est LIFECYCLE et n'entre dans aucun module.

    Mesuré sur le contrat entier : 236 identifiants, zéro `unknown`.
    """
    words = split_words(operation_id)[1:]
    if not words:
        return "unknown"
    return singularize_phrase("_".join(words))


def _deref(node: dict[str, Any], schemas: dict[str, Any]) -> dict[str, Any]:
    """Résout une référence locale `#/components/schemas/<nom>`."""
    ref = node.get("$ref")
    if not ref:
        return node
    name = ref.rsplit("/", 1)[-1]
    target = schemas.get(name)
    if target is None:
        raise ParseError(f"référence inconnue : {ref}")
    merged = dict(target)
    for key, value in node.items():
        if key != "$ref":
            merged.setdefault(key, value)
    return merged


def _first_paragraph(text: str | None) -> str | None:
    """Garde le premier paragraphe d'une description, sans le réécrire."""
    if not text:
        return None
    paragraph = text.strip().split("\n\n", 1)[0].strip()
    return paragraph or None
