"""Un override est une affirmation : il doit désigner quelque chose, et se justifier."""

from __future__ import annotations

from pathlib import Path

import pytest

from generator.ir.enums import ApiType, GenerationMode, OperationKind
from generator.ir.models import ApiService
from generator.overrides.loader import OverrideError, load_overrides
from generator.plan import plan_service


def _write(root: Path, contenu: str) -> Path:
    path = root / "widget.yml"
    path.write_text(contenu, encoding="utf-8")
    return path


def test_un_produit_sans_fichier_donne_un_ensemble_vide(tmp_path: Path) -> None:
    overrides = load_overrides("widget", root=tmp_path)
    assert overrides.operations == {}
    assert overrides.source is None


def test_un_override_change_la_classification(tmp_path: Path, widget_service: ApiService) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StartWidgets:
    generation: ignore
    reason: un test
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    start = next(item for item in plan.operations if item.operation.id == "StartWidgets")
    assert start.kind is OperationKind.IGNORE
    assert start.mode is GenerationMode.OVERRIDE
    assert start.module is None


def test_un_override_renomme_la_ressource(tmp_path: Path, widget_service: ApiService) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.WidgetSecret.ReadWidgetSecret:
    resource: widget_password
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    secret = next(item for item in plan.operations if item.operation.id == "ReadWidgetSecret")
    assert secret.resource == "widget_password"
    assert secret.module == "widget_password_info"


def test_un_champ_inconnu_est_refuse(tmp_path: Path) -> None:
    """Une faute de frappe produirait sinon un override silencieusement inerte."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.ReadWidgets:
    generatoin: ignore
    reason: faute de frappe volontaire
""",
    )
    with pytest.raises(OverrideError, match="champs inconnus"):
        load_overrides("widget", root=tmp_path)


def test_une_classification_sans_raison_est_refusee(tmp_path: Path) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.ReadWidgets:
    generation: ignore
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_retirer_un_module_sans_raison_est_refuse(tmp_path: Path) -> None:
    """Ne pas publier ce que l'exemple n'exerce pas est une décision, et elle se relit."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.WidgetConsole.ReadWidgetConsole:
    expose: false
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_retirer_un_module_laisse_loperation_classee(
    tmp_path: Path, widget_service: ApiService
) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.WidgetConsole.ReadWidgetConsole:
    expose: false
    reason: aucune cible
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    console = next(item for item in plan.operations if item.operation.id == "ReadWidgetConsole")
    assert console.kind is OperationKind.INFO
    assert console.module is None
    assert console.hidden_reason == "aucune cible"
    assert console in plan.day2, "classée compte dans la couverture, sans module"


def test_un_renommage_doption_sans_raison_est_refuse(tmp_path: Path) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StartWidgets:
    parameters:
      WidgetIds:
        option: ids
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_un_type_inconnu_est_refuse(tmp_path: Path) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.WidgetSecret.ReadWidgetSecret:
    parameters:
      WidgetId:
        type: chaine
        reason: le contrat ne dit pas le type
""",
    )
    with pytest.raises(OverrideError, match="type="):
        load_overrides("widget", root=tmp_path)


def test_un_type_pose_par_override_est_lu(tmp_path: Path) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.WidgetSecret.ReadWidgetSecret:
    parameters:
      WidgetId:
        type: string
        reason: le contrat ne dit pas le type, et un identifiant est une chaîne
""",
    )
    overrides = load_overrides("widget", root=tmp_path)
    declaration = overrides.get("widget.v1.WidgetSecret.ReadWidgetSecret")
    assert declaration is not None
    assert declaration.parameters["WidgetId"].type is ApiType.STRING


def test_un_override_orphelin_est_signale(tmp_path: Path, widget_service: ApiService) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.ReadWidgetsDisparu:
    generation: ignore
    reason: cette opération n'existe plus
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    assert plan.orphan_overrides == ("widget.v1.Widget.ReadWidgetsDisparu",)


def test_une_action_always_sans_etat_attendu_est_refusee(tmp_path: Path) -> None:
    """Une action qui agit toujours doit dire vers quel état : sinon le runtime
    agirait sans rien vérifier, et personne ne saurait pourquoi."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StartWidgets:
    wait:
      field: State
      states:
        start: running
      always: [reboot]
      reason: test
""",
    )
    with pytest.raises(OverrideError, match="always"):
        load_overrides("widget", root=tmp_path)


def test_un_etat_attendu_sans_raison_est_refuse(tmp_path: Path) -> None:
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StartWidgets:
    wait:
      states:
        start: running
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_le_champ_detat_vaut_state_par_defaut(tmp_path: Path) -> None:
    """`State` est le nom que le contrat donne à l'état de presque toute ressource."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StartWidgets:
    wait:
      states:
        start: running
      reason: test
""",
    )
    declaration = load_overrides("widget", root=tmp_path).get("widget.v1.Widget.StartWidgets")
    assert declaration is not None and declaration.wait is not None
    assert declaration.wait.field == "State"
