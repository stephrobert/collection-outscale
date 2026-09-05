"""Assemblage de la chaîne : contrat -> IR -> classification -> overrides.

Le plan est ce que le rapport affiche et ce que le générateur exécutera à
l'étape suivante. Il ne produit aucun fichier : il décide, et il rend visible
ce qu'il a décidé.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from generator.ansible.mapping import module_name
from generator.classifier.rules import Classification, classify
from generator.ir.enums import DAY2_KINDS, GenerationMode, OperationKind
from generator.ir.models import ApiOperation, ApiService
from generator.overrides.loader import DEFAULT_OVERRIDES_ROOT, OverrideSet, load_overrides
from generator.parser.openapi import parse_document
from generator.source.base import DEFAULT_SPEC_ROOT, VendoredSpecSource


@dataclass(frozen=True)
class OperationPlan:
    """Ce que le générateur fera d'une opération, et pourquoi."""

    operation: ApiOperation
    classification: Classification
    resource: str
    module: str | None
    #: La raison pour laquelle aucun module ne porte l'opération, quand un
    #: override l'a décidé. `None` quand un module la porte, ou quand la
    #: classe n'en produit pas.
    hidden_reason: str | None = None

    @property
    def kind(self) -> OperationKind:
        return self.classification.kind

    @property
    def mode(self) -> GenerationMode:
        return self.classification.mode

    @property
    def is_day2(self) -> bool:
        return self.kind in DAY2_KINDS


@dataclass(frozen=True)
class ProductPlan:
    """Plan complet d'un produit, prêt à être rendu en rapport."""

    service: ApiService
    operations: tuple[OperationPlan, ...]
    overrides: OverrideSet
    orphan_overrides: tuple[str, ...]

    @property
    def day2(self) -> tuple[OperationPlan, ...]:
        return tuple(plan for plan in self.operations if plan.is_day2)

    @property
    def paginated(self) -> tuple[OperationPlan, ...]:
        """Les lectures qui se déroulent par un jeton de page."""
        return tuple(plan for plan in self.operations if plan.operation.is_paginated)

    @property
    def hidden(self) -> tuple[OperationPlan, ...]:
        """Les opérations Day-2 qu'un override retire des modules, avec leur raison."""
        return tuple(plan for plan in self.operations if plan.hidden_reason is not None)

    def count_by_kind(self) -> dict[OperationKind, int]:
        """Compte les opérations par classification, toutes classes présentes."""
        counts = {kind: 0 for kind in OperationKind}
        for plan in self.operations:
            counts[plan.kind] += 1
        return counts

    def count_by_mode(self) -> dict[GenerationMode, int]:
        """Compte les opérations Day-2 par mode de génération."""
        counts = {mode: 0 for mode in GenerationMode}
        for plan in self.day2:
            counts[plan.mode] += 1
        return counts

    def coverage(self) -> float | None:
        """Part des opérations Day-2 **classées** pour la génération automatique.

        Ce n'est pas la part des opérations qu'un module porte : pour ce qu'un
        module porte réellement, voir `built_coverage`.

        `None` quand il n'y a aucune opération Day-2 : un ratio sans
        dénominateur n'est pas zéro, il est indéfini, et le rapport doit le
        dire plutôt qu'afficher `0.0 %`.
        """
        day2 = self.day2
        if not day2:
            return None
        automated = sum(
            1 for plan in day2 if plan.mode in (GenerationMode.AUTO, GenerationMode.OVERRIDE)
        )
        return automated / len(day2)

    def built_coverage(self, written: Sequence[str]) -> float | None:
        """Part des opérations Day-2 qu'un module réellement écrit porte.

        `written` vient de l'appelant : le plan sait **nommer** un module, il ne
        sait pas le construire. C'est le modèle Ansible qui décide qu'un module
        est irréalisable, et lui seul.
        """
        day2 = self.day2
        if not day2:
            return None
        day2_ids = {plan.operation.id for plan in day2}
        modules = self.modules()
        portees = {
            item.operation.id
            for name in written
            for item in modules.get(name, ())
            if item.operation.id in day2_ids
        }
        return len(portees) / len(day2)

    @property
    def unknown(self) -> tuple[OperationPlan, ...]:
        return tuple(plan for plan in self.operations if plan.kind is OperationKind.UNKNOWN)

    def modules(self) -> dict[str, tuple[OperationPlan, ...]]:
        """Regroupe les opérations par module cible, dans l'ordre de leur nom."""
        grouped: dict[str, list[OperationPlan]] = {}
        for plan in self.operations:
            if plan.module is None:
                continue
            grouped.setdefault(plan.module, []).append(plan)
        return {name: tuple(plans) for name, plans in sorted(grouped.items())}


def build_plan(
    product: str,
    version: str,
    *,
    spec_root: Path = DEFAULT_SPEC_ROOT,
    overrides_root: Path = DEFAULT_OVERRIDES_ROOT,
) -> ProductPlan:
    """Construit le plan d'un produit à partir de son contrat versionné."""
    service = parse_document(VendoredSpecSource(root=spec_root).load(product, version))
    overrides = load_overrides(product, root=overrides_root)
    return plan_service(service, overrides)


def plan_service(service: ApiService, overrides: OverrideSet) -> ProductPlan:
    """Applique classification et overrides à un service déjà parsé."""
    plans: list[OperationPlan] = []
    for operation in service.operations:
        classification = classify(operation)
        resource = operation.resource
        module: str | None = None
        hidden_reason: str | None = None

        override = overrides.get(operation.key)
        if override is not None:
            if override.resource:
                resource = override.resource
            if override.kind is not None:
                classification = Classification(
                    key=operation.key,
                    kind=override.kind,
                    mode=override.mode or GenerationMode.OVERRIDE,
                    reason=override.reason or "override sans raison",
                )

        module = module_name(service.name, resource, classification.kind)
        if override is not None and override.module:
            module = override.module
        if override is not None and override.expose is False:
            if module is not None:
                hidden_reason = override.reason or "override sans raison"
            module = None

        plans.append(
            OperationPlan(
                operation=operation,
                classification=classification,
                resource=resource,
                module=module,
                hidden_reason=hidden_reason,
            )
        )

    return ProductPlan(
        service=service,
        operations=tuple(plans),
        overrides=overrides,
        orphan_overrides=overrides.orphans(service),
    )
