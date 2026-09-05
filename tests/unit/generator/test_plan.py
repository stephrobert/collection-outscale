"""Le plan compte ce qu'il compte, et ne maquille pas la mesure."""

from __future__ import annotations

from generator.ir.enums import OperationKind
from generator.ir.models import ApiService
from generator.overrides.loader import OverrideSet
from generator.plan import ProductPlan, plan_service


def test_une_couverture_sans_operation_day2_est_indefinie() -> None:
    """Un ratio sans dénominateur n'est pas zéro : il n'existe pas."""
    vide = plan_service(ApiService(name="vide", version="v1"), OverrideSet(source=None))
    assert vide.coverage() is None
    assert vide.built_coverage(("un_module",)) is None


def test_classee_nest_pas_portee_par_un_module(widget_plan: ProductPlan) -> None:
    assert widget_plan.coverage() == 1.0
    assert widget_plan.built_coverage(()) == 0.0
    assert widget_plan.built_coverage(("widget_info",)) == 1 / len(widget_plan.day2)


def test_le_denominateur_exclut_le_cycle_de_vie_et_lecarte(widget_plan: ProductPlan) -> None:
    day2 = {plan.kind for plan in widget_plan.day2}
    assert OperationKind.LIFECYCLE not in day2
    assert OperationKind.IGNORE not in day2
    assert len(widget_plan.day2) == 8, "7 lectures et actions, 1 gestion d'état"


def test_chaque_classe_est_comptee_meme_a_zero(widget_plan: ProductPlan) -> None:
    comptes = widget_plan.count_by_kind()
    assert set(comptes) == set(OperationKind)
    assert comptes[OperationKind.UNKNOWN] == 0
    assert comptes[OperationKind.LIFECYCLE] == 3


def test_les_lectures_paginees_sont_comptees(widget_plan: ProductPlan) -> None:
    paginees = {plan.operation.id for plan in widget_plan.paginated}
    assert paginees == {"ReadWidgets"}


def test_les_operations_cachees_sont_comptees_a_part(widget_plan: ProductPlan) -> None:
    """Une opération classée sans module compte dans la couverture, et se lit à part."""
    assert [item.operation.id for item in widget_plan.hidden] == ["ReadWidgetConsole"]


def test_un_module_regroupe_ses_operations(widget_plan: ProductPlan) -> None:
    modules = widget_plan.modules()
    assert [plan.operation.id for plan in modules["widget_info"]] == ["ReadWidgets"]
    assert {plan.operation.id for plan in modules["widget_action"]} == {
        "StartWidgets",
        "StopWidgets",
        "RebootWidgets",
    }
    assert "widget_console_info" not in modules
