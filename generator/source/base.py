"""Accès au contrat versionné qui décrit l'API d'Outscale.

**Un seul document, un tag par opération.** Outscale publie un document
OpenAPI 3.0 unique (`outscale/osc-api`, `outscale.yaml`, mesuré sur le tag
1.42.0 : 236 chemins, 236 opérations, 50 tags) et c'est le **tag** qui dit à
quelle ressource une opération appartient : `ReadVms`, `StartVms` et
`UpdateVm` portent le tag `Vm`. Le document ne déclare aucune liste `tags`
racine ni aucune hiérarchie : chaque opération porte exactement un tag, et ce
tag est sa propre famille.

`specs/outscale/products.txt` indexe donc des tags, pas des fichiers, et
cette couche **découpe** le document par tag avant de le confier au parser.
Le parser ne sait rien des tags : il reçoit un document dont `paths` ne porte
que les opérations du produit demandé, et il traduit.

Le générateur ne lit jamais le réseau pendant une génération : le
téléchargement est une opération séparée (`mise run sync:api`), et une
évolution de l'API arrive comme un diff dans une revue.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from generator.parser.naming import snake_case

#: Racine des documents versionnés, relative à la racine du dépôt.
DEFAULT_SPEC_ROOT = Path(__file__).resolve().parents[2] / "specs" / "outscale"

#: Nom du fichier de contrat, par version : `outscale.v1.yml`. La version est
#: celle du chemin de l'API (`/api/v1`), pas celle du document (`1.42.0`), qui
#: se lit dans `info.version` et que le rapport de dérive compare.
DOCUMENT_STEM = "outscale"

#: Méthodes HTTP qu'un chemin OpenAPI peut porter. Mesuré : Outscale n'emploie
#: que POST, et le parser le vérifie ; la liste reste complète pour que le
#: recensement compte une méthode inattendue au lieu de la perdre.
_METHODS: tuple[str, ...] = ("get", "post", "put", "patch", "delete")


class SpecNotFoundError(FileNotFoundError):
    """Le document demandé n'est pas présent dans la copie versionnée."""


class ProductNotFoundError(LookupError):
    """Le produit demandé n'est pas dans `products.txt`, ou aucun tag ne le porte."""


@dataclass(frozen=True)
class ProductEntry:
    """Une ligne de `products.txt` : `<Tag> [<nom-produit>] <version>`.

    Sans nom de produit, le nom est le tag en snake_case : `LoadBalancer`
    donne `load_balancer`, et c'est le préfixe des modules comme le nom du
    fichier d'overrides.
    """

    tag: str
    product: str
    version: str


@dataclass(frozen=True)
class SpecDocument:
    """Le contrat d'un produit, découpé et prêt pour le parser."""

    product: str
    version: str
    path: Path
    #: Le document OpenAPI, dont `paths` ne porte que les opérations du produit.
    document: dict[str, Any]
    #: Les tags du produit. Un seul chez Outscale, gardé en tuple pour que le
    #: rapport et les tests lisent la même forme quelle que soit l'API.
    tags: tuple[str, ...] = ()

    @property
    def slug(self) -> str:
        return f"{self.product}.{self.version}"


@dataclass(frozen=True)
class ProductCensus:
    """Ce que le document contient, tag par tag, avant tout découpage.

    C'est la mesure qui garde visible ce que `products.txt` n'indexe pas : une
    opération hors périmètre n'est pas perdue, elle est comptée ici.
    """

    #: Nombre d'opérations par tag.
    by_tag: dict[str, int] = field(default_factory=dict)
    #: Opérations sans aucun tag, donc rattachables à aucun produit.
    untagged: tuple[str, ...] = ()
    #: Opérations qui portent plusieurs tags. Mesuré : aucune ; si une
    #: apparaissait, elle compterait dans chaque tag et serait nommée ici.
    multi_tag: tuple[str, ...] = ()
    #: Opérations portées par une autre méthode que POST. Mesuré : aucune.
    non_post: tuple[str, ...] = ()
    #: Nombre d'opérations distinctes du document, tags ou pas.
    operations: int = 0

    @property
    def total(self) -> int:
        return self.operations


def read_products(root: Path = DEFAULT_SPEC_ROOT) -> list[ProductEntry]:
    """Lit l'index : `<Tag> [<nom-produit>] <version>`, commentaires ignorés."""
    index = root / "products.txt"
    if not index.is_file():
        raise SpecNotFoundError(f"index absent : {index}")
    entries: list[ProductEntry] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) == 2:
            tag, version = fields
            product = snake_case(tag)
        elif len(fields) == 3:
            tag, product, version = fields
        else:
            raise ValueError(f"{index} : ligne mal formée : {line!r}")
        entries.append(ProductEntry(tag=tag, product=product, version=version))
    return entries


def census(document: dict[str, Any]) -> ProductCensus:
    """Recense les opérations du document par tag, sans rien filtrer."""
    by_tag: Counter[str] = Counter()
    untagged: list[str] = []
    multi_tag: list[str] = []
    non_post: list[str] = []
    operations = 0
    for path, item in document.get("paths", {}).items():
        for method in _METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            operations += 1
            identifier = str(operation.get("operationId") or f"{method.upper()} {path}")
            if method != "post":
                non_post.append(identifier)
            tags = [str(tag) for tag in operation.get("tags") or ()]
            if not tags:
                untagged.append(identifier)
                continue
            if len(tags) > 1:
                multi_tag.append(identifier)
            for tag in sorted(set(tags)):
                by_tag[tag] += 1
    return ProductCensus(
        by_tag=dict(sorted(by_tag.items())),
        untagged=tuple(sorted(untagged)),
        multi_tag=tuple(sorted(multi_tag)),
        non_post=tuple(sorted(non_post)),
        operations=operations,
    )


def split_product(document: dict[str, Any], tag: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Découpe le document : ne garde que les opérations qui portent `tag`."""
    paths: dict[str, Any] = {}
    for path, item in document.get("paths", {}).items():
        kept: dict[str, Any] = {key: value for key, value in item.items() if key not in _METHODS}
        found = False
        for method in _METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            tags = [str(name) for name in operation.get("tags") or ()]
            if tag in tags:
                kept[method] = operation
                found = True
        if found:
            paths[path] = kept

    if not paths:
        raise ProductNotFoundError(
            f"aucune opération ne porte le tag {tag!r} ; "
            "vérifier le tag avec `python -m generator products`"
        )
    cut = dict(document)
    cut["paths"] = paths
    return cut, (tag,)


@dataclass(frozen=True)
class VendoredSpecSource:
    """Lit `specs/outscale/outscale.<version>.yml` et le découpe par produit."""

    root: Path = DEFAULT_SPEC_ROOT

    def document_path(self, version: str) -> Path:
        return self.root / f"{DOCUMENT_STEM}.{version}.yml"

    def load_document(self, version: str) -> dict[str, Any]:
        """Le document entier, tel que publié, sans découpage."""
        path = self.document_path(version)
        if not path.is_file():
            raise SpecNotFoundError(
                f"contrat absent : {path}. Lancer `mise run sync:api` pour le télécharger."
            )
        with path.open(encoding="utf-8") as handle:
            document = yaml.load(handle, Loader=_loader())
        if not isinstance(document, dict) or "paths" not in document:
            raise ValueError(f"{path} ne contient pas un document OpenAPI")
        return document

    def load(self, product: str, version: str) -> SpecDocument:
        """Le contrat du produit, découpé selon `products.txt`."""
        entry = next(
            (
                item
                for item in read_products(self.root)
                if item.version == version and product in (item.product, item.tag)
            ),
            None,
        )
        if entry is None:
            raise ProductNotFoundError(
                f"produit {product!r} ({version}) absent de {self.root / 'products.txt'}"
            )
        document = self.load_document(version)
        cut, family = split_product(document, entry.tag)
        return SpecDocument(
            product=entry.product,
            version=version,
            path=self.document_path(version),
            document=cut,
            tags=family,
        )

    def available(self) -> list[tuple[str, str]]:
        """Les couples (produit, version) que l'index déclare, dans son ordre."""
        return [(entry.product, entry.version) for entry in read_products(self.root)]


def _loader() -> type[yaml.SafeLoader]:
    """Le chargeur C quand la bibliothèque le fournit, le pur Python sinon.

    Le document fait près d'un mégaoctet ; le chargeur pur Python met plusieurs
    secondes là où le chargeur C en met une fraction, et les deux rendent le
    même arbre. Le choix ne change pas le résultat, seulement le temps.
    """
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)
