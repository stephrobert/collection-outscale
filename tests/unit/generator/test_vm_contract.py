"""Le contrat réel de vm : ce que le golden fige, et ce que le plan en dit.

Ces tests rougissent quand Outscale bouge. C'est voulu : une évolution de
l'API doit arriver comme un diff relu, jamais comme un résultat qui change
tout seul. `mise run golden:update` régénère le golden, et son diff se lit.
"""

from __future__ import annotations

import json

from generator.ansible.mapping import module_name
from generator.ir.enums import OperationKind
from generator.ir.models import ApiService
from generator.plan import ProductPlan, build_plan
from generator.source.base import read_products

from .conftest import FIXTURES, OUTSCALE_SPECS

GOLDEN = FIXTURES / "vm" / "expected_ir.json"


def test_lir_de_vm_est_celle_du_golden(vm_service: ApiService) -> None:
    assert GOLDEN.is_file(), "lancer `mise run golden:update` pour figer l'IR"
    assert json.loads(vm_service.to_json()) == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_aucune_operation_de_vm_nest_inconnue(vm_plan: ProductPlan) -> None:
    assert vm_plan.unknown == ()


def test_aucun_override_de_vm_nest_orphelin(vm_plan: ProductPlan) -> None:
    assert vm_plan.orphan_overrides == ()


def test_la_couverture_de_vm_nomme_son_denominateur(vm_plan: ProductPlan) -> None:
    """10 candidates Day-2 sur 12 opérations : les 2 autres sont écartées, pas cachées."""
    comptes = vm_plan.count_by_kind()
    assert len(vm_plan.operations) == 12
    assert len(vm_plan.day2) == 10
    assert comptes[OperationKind.LIFECYCLE] == 2
    assert comptes[OperationKind.INFO] == 6
    assert comptes[OperationKind.ACTION] == 3
    assert comptes[OperationKind.MANAGE] == 1
    assert vm_plan.coverage() == 1.0


def test_les_lectures_de_vm_paginent_sauf_les_lectures_unitaires(vm_service: ApiService) -> None:
    """Mesuré : quatre lectures paginent, `ReadAdminPassword` et `ReadConsoleOutput` non."""
    paginees = {op.id for op in vm_service.operations if op.is_paginated}
    assert paginees == {"ReadVms", "ReadVmTypes", "ReadVmsState", "ReadVmsStopHistory"}


def test_le_document_versionne_est_celui_que_le_sdk_embarque(vm_service: ApiService) -> None:
    """Le SDK refuse ce que sa copie du contrat ne connaît pas : les deux suivent."""
    from osc_sdk_python import Gateway

    gateway = Gateway(access_key="x", secret_key="y", region="eu-west-2")
    assert gateway.api_version == vm_service.document_version


def test_aucun_module_du_plan_ne_porte_de_verbe() -> None:
    """Un nom de module ne dit pas comment l'API s'appelle : `vm_info`, jamais `read_vms`."""
    verbes = ("read_", "create_", "delete_", "update_", "start_", "stop_", "link_")
    for entree in read_products(OUTSCALE_SPECS):
        plan = build_plan(entree.product, entree.version, spec_root=OUTSCALE_SPECS)
        for nom in plan.modules():
            assert not nom.startswith(verbes), nom
            assert not nom.startswith(entree.product + "_" + entree.product), nom
        assert plan.unknown == () and plan.orphan_overrides == ()
    assert module_name("vm", "vm", OperationKind.INFO) == "vm_info"
