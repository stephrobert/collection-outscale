"""La classification tranche sur le verbe, et ce qu'elle ne tranche pas se voit."""

from __future__ import annotations

from generator.classifier.rules import classify, verb_of
from generator.ir.enums import GenerationMode, HTTPMethod, OperationKind
from generator.ir.models import ApiOperation, ApiService
from generator.plan import ProductPlan


def _operation(operation_id: str, method: HTTPMethod = HTTPMethod.POST) -> ApiOperation:
    return ApiOperation(
        id=operation_id,
        product="x",
        version="v1",
        resource="thing",
        http_method=method,
        path=f"/{operation_id}",
    )


def test_le_verbe_est_le_premier_mot_camel_de_loperation_id() -> None:
    assert verb_of(_operation("StartVms")) == "start"
    assert verb_of(_operation("ReadCO2EmissionAccount")) == "read"


def test_read_est_de_linformation(widget_plan: ProductPlan) -> None:
    par_operation = {plan.operation.id: plan.kind for plan in widget_plan.operations}
    assert par_operation["ReadWidgets"] is OperationKind.INFO
    assert par_operation["ReadWidgetTypes"] is OperationKind.INFO
    assert par_operation["ReadWidgetSecret"] is OperationKind.INFO


def test_create_et_delete_relevent_du_cycle_de_vie(widget_plan: ProductPlan) -> None:
    par_operation = {plan.operation.id: plan.kind for plan in widget_plan.operations}
    assert par_operation["CreateWidget"] is OperationKind.LIFECYCLE
    assert par_operation["DeleteWidgets"] is OperationKind.LIFECYCLE


def test_relier_deux_ressources_releve_du_cycle_de_vie(widget_plan: ProductPlan) -> None:
    """`Link`, `Unlink`, `Register`, `Deregister`, `Add`, `Remove` : le graphe de Terraform."""
    decision = next(p for p in widget_plan.operations if p.operation.id == "LinkGadget")
    assert decision.kind is OperationKind.LIFECYCLE
    assert "relie" in decision.classification.reason
    for verbe in (
        "UnlinkVolume",
        "RegisterVmsInLoadBalancer",
        "DeregisterVms",
        "AddUser",
        "RemoveUser",
    ):
        assert classify(_operation(verbe)).kind is OperationKind.LIFECYCLE


def test_update_put_et_set_sont_une_gestion_detat(widget_plan: ProductPlan) -> None:
    par_operation = {plan.operation.id: plan.kind for plan in widget_plan.operations}
    assert par_operation["UpdateWidget"] is OperationKind.MANAGE
    assert classify(_operation("PutUserPolicy")).kind is OperationKind.MANAGE
    assert classify(_operation("SetDefaultPolicyVersion")).kind is OperationKind.MANAGE


def test_les_verbes_daction_sont_des_actions(widget_plan: ProductPlan) -> None:
    par_operation = {plan.operation.id: plan.kind for plan in widget_plan.operations}
    assert par_operation["StartWidgets"] is OperationKind.ACTION
    assert par_operation["StopWidgets"] is OperationKind.ACTION
    assert par_operation["RebootWidgets"] is OperationKind.ACTION
    for verbe in (
        "AcceptNetPeering",
        "RejectNetPeering",
        "EnableThing",
        "DisableThing",
        "ScaleUpVmGroup",
    ):
        assert classify(_operation(verbe)).kind is OperationKind.ACTION


def test_un_verbe_sans_regle_est_declare_inconnu() -> None:
    """`CheckAuthentication` est le seul du contrat réel, et il reste UNKNOWN."""
    decision = classify(_operation("CheckAuthentication"))
    assert decision.kind is OperationKind.UNKNOWN
    assert "check" in decision.reason


def test_une_methode_autre_que_post_est_declaree_inconnue() -> None:
    """Le contrat ne porte que des POST : un GET est une forme à mesurer, pas à classer."""
    decision = classify(_operation("ReadThing", HTTPMethod.GET))
    assert decision.kind is OperationKind.UNKNOWN
    assert "GET" in decision.reason


def test_la_classification_automatique_se_declare_comme_telle() -> None:
    decision = classify(_operation("ReadThings"))
    assert decision.mode is GenerationMode.AUTO
    assert decision.reason


def test_aucune_operation_ne_disparait_du_plan(
    widget_plan: ProductPlan, widget_service: ApiService
) -> None:
    assert len(widget_plan.operations) == len(widget_service.operations)
    assert {plan.operation.id for plan in widget_plan.operations} == {
        operation.id for operation in widget_service.operations
    }
