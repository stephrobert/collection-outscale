"""Le modèle décide tout ce que le template écrit, et refuse ce qu'il ne sait pas."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from generator.ansible.models import AnsibleModuleSpec, build_module_specs
from generator.ir.enums import OperationKind
from generator.ir.models import ApiService
from generator.overrides.loader import OverrideSet, load_overrides
from generator.plan import ProductPlan, plan_service

from .conftest import LAB_COLLECTION


def _spec(specs: tuple[AnsibleModuleSpec, ...], name: str) -> AnsibleModuleSpec:
    return next(spec for spec in specs if spec.name == name)


def test_un_module_dinformation_porte_une_lecture_et_ses_filtres(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    info = _spec(specs, "widget_info")
    assert info.kind is OperationKind.INFO
    assert info.operation is not None and info.operation.id == "ReadWidgets"
    assert info.options == {"filters": {"type": "dict"}}
    assert info.operation.page_token == "NextPageToken"
    assert info.operation.is_list is True


def test_les_drapeaux_de_requete_ne_deviennent_pas_des_options(widget_plan: ProductPlan) -> None:
    """`DryRun`, `NextPageToken` et `ResultsPerPage` ne sont ni options ni envoyés."""
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    info = _spec(specs, "widget_info")
    assert "dry_run" not in info.options
    assert info.operation is not None
    assert set(info.operation.body_params) == {"filters"}


def test_les_cles_dun_filtre_viennent_du_contrat(widget_plan: ProductPlan) -> None:
    """Rien n'est inventé : les clés sont les propriétés de `FiltersWidget`."""
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    info = _spec(specs, "widget_info")
    assert "C(WidgetIds)" in info.option_docs["filters"][0]
    assert "C(CreationDates)" in info.option_docs["filters"][0]


def test_une_lecture_exige_ce_que_le_contrat_exige(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    secret = _spec(specs, "widget_secret_info")
    assert secret.options["widget_id"]["required"] is True
    assert secret.operation is not None and secret.operation.is_list is False


def test_une_lecture_de_secret_le_dit_dans_sa_documentation(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    secret = _spec(specs, "widget_secret_info")
    assert secret.sensitive_return is True
    assert any("secret" in note for note in secret.documentation()["notes"])
    assert _spec(specs, "widget_info").sensitive_return is False


def test_une_charge_utile_indecidable_rend_la_reponse_entiere(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    secret = _spec(specs, "widget_secret_info")
    assert secret.operation is not None and secret.operation.payload_field is None
    assert "response context" in secret.return_documentation()["widget_secret"]["description"]


def test_une_lecture_retiree_par_override_na_pas_de_module(widget_plan: ProductPlan) -> None:
    specs, skipped = build_module_specs(widget_plan, LAB_COLLECTION)
    assert "widget_console_info" not in {spec.name for spec in specs}
    assert "widget_console_info" not in dict(skipped)
    caches = {item.operation.id: item.hidden_reason for item in widget_plan.hidden}
    assert "ReadWidgetConsole" in caches and "aucune cible" in str(caches["ReadWidgetConsole"])


def test_un_module_daction_regroupe_les_operations_de_la_ressource(
    widget_plan: ProductPlan,
) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    action = _spec(specs, "widget_action")
    assert action.kind is OperationKind.ACTION
    assert action.selector == "widget_ids"
    assert [a.name for a in action.actions] == ["reboot", "start", "stop"]
    assert action.options["action"]["choices"] == ["reboot", "start", "stop"]
    assert action.options["widget_ids"]["required"] is True


def test_ce_que_le_contrat_exige_pour_une_action_seule_devient_required_if(
    widget_service: ApiService,
) -> None:
    """`ForceStop` n'est pas exigé ; exigé par `stop` seule, il le serait par `required_if`."""
    from generator.ir.models import ApiParameter

    operations = tuple(
        replace(
            op,
            parameters=tuple(
                replace(p, required=True) if p.name == "ForceStop" else p for p in op.parameters
            ),
        )
        if op.id == "StopWidgets"
        else op
        for op in widget_service.operations
    )
    service = replace(widget_service, operations=operations)
    specs, _ = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    action = _spec(specs, "widget_action")
    assert ("action", "stop", ["force_stop"]) in action.required_if()
    assert "required" not in action.options["force_stop"], "exigé par stop seule, pas par start"
    assert isinstance(action.actions[0].operation.body_params, dict)
    assert ApiParameter  # le type est importé pour la lisibilité du test


def test_le_binding_garde_le_nom_du_contrat_a_cote_de_loption(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    action = _spec(specs, "widget_action")
    stop = next(a for a in action.actions if a.name == "stop")
    assert stop.operation.body_params == {"widget_ids": "WidgetIds", "force_stop": "ForceStop"}
    assert stop.operation.method == "StopWidgets"


def test_un_etat_attendu_embarque_la_lecture_filtree_de_la_ressource(
    widget_plan: ProductPlan,
) -> None:
    """L'API répond avant que la machine ait changé d'état : le module relit
    `ReadWidgets` filtré sur `WidgetIds`, et identifie chaque élément par `WidgetId`."""
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    action = _spec(specs, "widget_action")
    assert action.state_field == "State"
    assert action.read_operation is not None and action.read_operation.id == "ReadWidgets"
    assert action.read_filter == "WidgetIds"
    assert action.read_id_field == "WidgetId"
    par_nom = {a.name: a for a in action.actions}
    assert par_nom["start"].expected_state == "running" and not par_nom["start"].always_acts
    assert par_nom["stop"].expected_state == "stopped"
    assert par_nom["reboot"].expected_state == "running" and par_nom["reboot"].always_acts
    assert action.waitable is True
    assert "states" in action.return_documentation()
    assert any("changed=false" in note for note in action.documentation()["notes"])


def test_un_identifiant_seul_retrouve_son_filtre_au_pluriel(gadget_plan: ProductPlan) -> None:
    """`NetPeeringId` n'est pas dans `Filters`, `NetPeeringIds` l'est ; l'état est `State.Name`."""
    specs, _ = build_module_specs(gadget_plan, LAB_COLLECTION)
    action = _spec(specs, "gadget_action")
    assert action.selector == "gadget_id"
    assert action.read_filter == "GadgetIds"
    assert action.read_id_field == "GadgetId"
    assert action.state_field == "State.Name"
    assert [a.name for a in action.actions] == ["accept", "reject"]


def test_sans_etat_attendu_aucune_lecture_nest_embarquee(widget_service: ApiService) -> None:
    plan = plan_service(widget_service, OverrideSet(source=None))
    specs, _ = build_module_specs(plan, LAB_COLLECTION)
    action = _spec(specs, "widget_action")
    assert action.read_operation is None and action.state_field is None
    assert action.waitable is False
    assert action.doc_fragments() == ["lab.widget.outscale"]


def test_un_module_qui_attend_declare_le_fragment_wait(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    assert _spec(specs, "widget_action").doc_fragments() == [
        "lab.widget.outscale",
        "lab.widget.outscale.wait",
    ]
    assert _spec(specs, "widget_info").doc_fragments() == ["lab.widget.outscale"]


def test_une_classe_sans_renderer_est_ecartee_avec_sa_raison(widget_plan: ProductPlan) -> None:
    """Un WORKFLOW n'a pas de renderer : il est écarté, nommé, jamais rendu de travers."""
    from generator.classifier.rules import OperationKind as Kind

    operations = tuple(
        replace(item, classification=replace(item.classification, kind=Kind.WORKFLOW))
        if item.operation.id == "UpdateWidget"
        else item
        for item in widget_plan.operations
    )
    _, skipped = build_module_specs(replace(widget_plan, operations=operations), LAB_COLLECTION)
    raisons = dict(skipped)
    assert "widget" in raisons
    assert "WORKFLOW" in raisons["widget"]


def test_deux_lectures_sur_une_ressource_sont_refusees(widget_service: ApiService) -> None:
    """Chez Outscale une ressource n'a qu'une lecture ; deux disent une ressource mal déduite."""
    operations = tuple(
        replace(op, resource="widget") if op.id == "ReadWidgetTypes" else op
        for op in widget_service.operations
    )
    service = replace(widget_service, operations=operations)
    _, skipped = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    raisons = dict(skipped)
    assert "widget_info" in raisons and "2 lectures" in raisons["widget_info"]


def test_un_override_type_rend_un_parametre_sans_type_possible(
    widget_service: ApiService, tmp_path: Path
) -> None:
    from generator.ir.enums import ApiType

    operations = tuple(
        replace(
            op,
            parameters=tuple(
                replace(p, type=ApiType.UNKNOWN) if p.name == "WidgetId" else p
                for p in op.parameters
            ),
        )
        if op.id == "ReadWidgetSecret"
        else op
        for op in widget_service.operations
    )
    service = replace(widget_service, operations=operations)
    _, skipped = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    assert "type absent du contrat" in dict(skipped)["widget_secret_info"]

    (tmp_path / "widget.yml").write_text(
        """
operations:
  widget.v1.WidgetSecret.ReadWidgetSecret:
    parameters:
      WidgetId:
        type: string
        reason: un identifiant est une chaîne, le contrat ne le dit pas
""",
        encoding="utf-8",
    )
    plan = plan_service(service, load_overrides("widget", root=tmp_path))
    specs, _ = build_module_specs(plan, LAB_COLLECTION)
    assert _spec(specs, "widget_secret_info").options["widget_id"] == {
        "type": "str",
        "required": True,
    }


def test_les_exemples_montrent_une_forme_et_pas_une_ressource(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    exemples = _spec(specs, "widget_action").examples_documentation()
    assert exemples[0]["lab.widget.widget_action"] == {
        "region": "eu-west-2",
        "action": "reboot",
        "widget_ids": ["example-id"],
    }
    liste = _spec(specs, "widget_info").examples_documentation()
    assert len(liste) == 3 and "filters" in liste[1]["lab.widget.widget_info"]


# ---- la gestion d'état ------------------------------------------------------


def test_un_module_de_gestion_detat_porte_lecriture_et_la_lecture_qui_la_juge(
    widget_plan: ProductPlan,
) -> None:
    """`UpdateWidget` exige `WidgetId`, que `FiltersWidget` sait filtrer ; les options
    exposées sont celles que `Widget` rend sous le même nom, et rien d'autre."""
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    widget = _spec(specs, "widget")
    assert widget.kind is OperationKind.MANAGE
    assert widget.selector == "widget_id"
    assert widget.options["widget_id"]["required"] is True
    assert widget.compare == {"widget_type": "WidgetType", "performance": "Performance"}
    assert set(widget.options) == {"widget_id", "widget_type", "performance"}
    assert widget.update_operation is not None
    assert widget.update_operation.body_params == {
        "widget_id": "WidgetId",
        "widget_type": "WidgetType",
        "performance": "Performance",
    }
    assert widget.read_operation is not None and widget.read_operation.id == "ReadWidgets"
    assert widget.read_filter == "WidgetIds" and widget.read_id_field == "WidgetId"
    assert any("UpdateWidget.UserData" in limite for limite in widget.limits)
    assert widget.doc_fragments() == ["lab.widget.outscale"]
    assert "changes" in widget.return_documentation()


def test_une_ecriture_dont_rien_ne_se_relit_est_ecartee(widget_service: ApiService) -> None:
    """Sans option comparable, un module écrirait sans jamais pouvoir dire `changed=false`."""
    operations = tuple(
        replace(
            op,
            parameters=tuple(
                p for p in op.parameters if p.name in ("WidgetId", "UserData", "DryRun")
            ),
        )
        if op.id == "UpdateWidget"
        else op
        for op in widget_service.operations
    )
    service = replace(widget_service, operations=operations)
    _, skipped = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    assert "rien à gérer" in dict(skipped)["widget"]


def test_une_option_que_la_lecture_ne_rend_pas_nest_pas_exposee(widget_plan: ProductPlan) -> None:
    """`UserData` et `Options` ne sont pas dans `Widget` : les envoyer rendrait `changed`
    à chaque passage. La limite le dit, et l'option n'existe pas."""
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    widget = _spec(specs, "widget")
    assert "user_data" not in widget.options and "options" not in widget.options
    assert "user_data" not in widget.update_operation.body_params  # type: ignore[union-attr]


def test_une_ecriture_sans_lecture_est_ecartee_en_nommant_la_cause(
    widget_service: ApiService,
) -> None:
    """`UpdateRoute` n'a pas de `ReadRoutes` : la raison est l'absence de lecture,
    pas un compte d'options filtrables, et le compte rendu doit le dire ainsi."""
    operations = tuple(op for op in widget_service.operations if op.id != "ReadWidgets")
    service = replace(widget_service, operations=operations)
    _, skipped = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    assert "aucune lecture ne rend widget" in dict(skipped)["widget"]


def test_deux_ecritures_sur_une_ressource_sont_refusees(widget_service: ApiService) -> None:
    """Une seconde écriture sur `widget` dit une ressource mal déduite : le module
    n'en garde pas une au hasard, il est écarté avec les deux noms."""
    doublon = next(
        replace(op, id="PutWidget") for op in widget_service.operations if op.id == "UpdateWidget"
    )
    service = replace(widget_service, operations=(*widget_service.operations, doublon))
    _, skipped = build_module_specs(plan_service(service, OverrideSet(source=None)), LAB_COLLECTION)
    raison = dict(skipped)["widget"]
    assert "2 écritures" in raison and "PutWidget" in raison


# ---- la mise en forme des descriptions -------------------------------------


def _widget_type(widget_service: ApiService) -> Any:
    update = next(op for op in widget_service.operations if op.id == "UpdateWidget")
    return next(p for p in update.parameters if p.name == "WidgetType")


def test_un_lien_markdown_du_contrat_devient_un_lien_ansible(widget_service: ApiService) -> None:
    """antsibull-docs refuse `[texte](url)` ; mesuré sur `vm.rst`, cinq jobs rouges."""
    from generator.ansible.models import _describe

    parameter = replace(
        _widget_type(widget_service),
        description="See [VM Types](https://docs.outscale.com/en/userguide/VM-Types.html) first.",
    )
    (text,) = _describe(parameter)
    assert "L(VM Types, https://docs.outscale.com/en/userguide/VM-Types.html)" in text
    assert "](" not in text


def test_un_saut_de_ligne_html_du_contrat_devient_un_espace(widget_service: ApiService) -> None:
    from generator.ansible.models import _describe

    parameter = replace(_widget_type(widget_service), description="First.<br />Second.<br/>")
    assert _describe(parameter) == ("First. Second.",)


def test_un_code_markdown_du_contrat_devient_une_constante_ansible(
    widget_service: ApiService,
) -> None:
    """Mesuré : 5 modules sur 32 recopiaient `` `io1` `` là où Ansible écrit C(io1)."""
    from generator.ansible.models import _describe

    parameter = replace(_widget_type(widget_service), description="Either `io1` or `gp2`.")
    assert _describe(parameter) == ("Either C(io1) or C(gp2).",)
