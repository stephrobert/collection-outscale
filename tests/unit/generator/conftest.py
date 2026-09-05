"""Fixtures partagées des tests du générateur."""

from __future__ import annotations

from pathlib import Path

import pytest

from generator.ansible.collection import Collection
from generator.ir.models import ApiService
from generator.overrides.loader import load_overrides
from generator.parser.openapi import parse_document
from generator.plan import ProductPlan, build_plan, plan_service
from generator.source.base import VendoredSpecSource

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
WIDGET_SPECS = FIXTURES / "widget" / "input"
WIDGET_OVERRIDES = FIXTURES / "widget" / "overrides"
OUTSCALE_SPECS = REPO_ROOT / "specs" / "outscale"

#: Identité figée pour les tests de rendu : ils mesurent le renderer, pas le
#: namespace du jour.
LAB_COLLECTION = Collection(
    namespace="lab",
    name="widget",
    version="9.9.9",
    path=FIXTURES / "widget" / "ansible_collections" / "lab" / "widget",
    authors=("Contrat de laboratoire (@lab)",),
)


@pytest.fixture(scope="session")
def widget_service() -> ApiService:
    """IR du contrat de laboratoire, indépendant des évolutions de l'API Outscale."""
    return parse_document(VendoredSpecSource(root=WIDGET_SPECS).load("widget", "v1"))


@pytest.fixture(scope="session")
def gadget_service() -> ApiService:
    """IR du second produit du laboratoire : identifiant seul, état imbriqué."""
    return parse_document(VendoredSpecSource(root=WIDGET_SPECS).load("gadget", "v1"))


@pytest.fixture()
def widget_plan(widget_service: ApiService) -> ProductPlan:
    """Le plan du laboratoire, avec ses overrides."""
    return plan_service(widget_service, load_overrides("widget", root=WIDGET_OVERRIDES))


@pytest.fixture()
def gadget_plan(gadget_service: ApiService) -> ProductPlan:
    return plan_service(gadget_service, load_overrides("gadget", root=WIDGET_OVERRIDES))


@pytest.fixture(scope="session")
def vm_service() -> ApiService:
    """IR du produit vm réel, tel qu'il est versionné dans `specs/`."""
    return parse_document(VendoredSpecSource(root=OUTSCALE_SPECS).load("vm", "v1"))


@pytest.fixture(scope="session")
def vm_plan() -> ProductPlan:
    return build_plan("vm", "v1", spec_root=OUTSCALE_SPECS)
