"""Combler un trou du contrat est une décision, et une décision se contrôle.

Ce que ces tests protègent tient en une phrase : **la page publiée sur Galaxy
est immuable**. Un module qui y arrive avec « Not documented by the Outscale
API contract. » publie ça pour toujours, et le lecteur n'a nulle part où aller
le compléter.

Les overrides documentaires réparent ça, et introduisent trois façons de mentir
que ces tests refusent : publier un texte sans dire d'où il vient, recouvrir la
phrase du contrat par la sienne, et garder un texte que le contrat a rendu
inutile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from generator.ansible.models import build_module_specs
from generator.ir.models import ApiService
from generator.overrides.loader import OverrideError, load_overrides
from generator.plan import plan_service

from .conftest import LAB_COLLECTION


def _write(root: Path, contenu: str) -> Path:
    path = root / "widget.yml"
    path.write_text(contenu, encoding="utf-8")
    return path


def _spec(service: ApiService, root: Path, module: str):  # type: ignore[no-untyped-def]
    plan = plan_service(service, load_overrides("widget", root=root))
    specs, _ = build_module_specs(plan, LAB_COLLECTION)
    return next(s for s in specs if s.name == module)


def test_une_cle_declaree_deux_fois_est_refusee(tmp_path: Path) -> None:
    """YAML garde la dernière occurrence, et efface la première sans un mot.

    Le cas est arrivé chez collection-scaleway : un second bloc a remplacé
    celui qui portait `resource`, le module publié a changé de nom, et aucun
    contrôle n'a rougi. Le contrôle d'orphelins ne pouvait rien y faire, la
    clé désignant bien une opération : c'est la décision qui avait disparu.
    """
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.UpdateWidget:
    resource: widget
  widget.v1.Widget.UpdateWidget:
    parameters:
      WidgetId:
        description: The ID of the widget.
        reason: le contrat ne le décrit pas
""",
    )
    with pytest.raises(OverrideError, match="deux fois"):
        load_overrides("widget", root=tmp_path)


def test_une_description_publiee_sans_raison_est_refusee(tmp_path: Path) -> None:
    """Le texte sortira sur Galaxy sous le nom de la collection.

    Un lecteur n'a aucun moyen de le distinguer d'une phrase d'Outscale. La
    raison est ce qui dit d'où il vient, et elle n'est pas facultative.
    """
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.UpdateWidget:
    parameters:
      WidgetId:
        description: The ID of the widget.
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_une_valeur_dexemple_sans_raison_est_refusee(tmp_path: Path) -> None:
    """Un exemple se copie : une valeur fausse y est pire qu'un trou."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.UpdateWidget:
    parameters:
      WidgetType:
        example: gizmo
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_un_override_comble_le_trou_du_contrat(tmp_path: Path, widget_service: ApiService) -> None:
    """`UpdateWidget.WidgetId` n'a pas de description dans le contrat de laboratoire."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.UpdateWidget:
    parameters:
      WidgetId:
        description: The ID of the widget.
        reason: recopié de ReadWidgetSecretRequest.WidgetId, qui décrit le même champ
""",
    )
    spec = _spec(widget_service, tmp_path, "widget")
    assert spec.option_docs["widget_id"] == ("The ID of the widget.",)


def test_le_contrat_gagne_toujours_sur_loverride(
    tmp_path: Path, widget_service: ApiService
) -> None:
    """Recouvrir une phrase du contrat ferait diverger la page de l'API.

    Et la divergence serait invisible : rien, sur la page publiée, ne dit qu'un
    texte vient d'un override plutôt que d'Outscale. `StopWidgets.ForceStop`
    est décrit par le contrat.
    """
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StopWidgets:
    parameters:
      ForceStop:
        description: Ce texte ne doit jamais sortir.
        reason: tentative de recouvrement, que le générateur doit ignorer
""",
    )
    spec = _spec(widget_service, tmp_path, "widget_action")
    assert spec.option_docs["force_stop"] == ("Forces the widget to stop.",)


def test_un_override_qui_ne_comble_plus_rien_est_orphelin(
    tmp_path: Path, widget_service: ApiService
) -> None:
    """Le jour où l'amont documente le champ, le texte écrit ici devient mort.

    Il ne se voit plus sur la page, donc plus personne ne le relit, et une
    relecture le croirait publié. Il sort par le canal des orphelins, ce qui
    fait sortir `report --strict` en 2.
    """
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.StopWidgets:
    parameters:
      ForceStop:
        description: Ce texte ne comble plus rien.
        reason: le contrat décrit déjà ForceStop, donc cet override est inerte
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    assert any("ForceStop" in orphelin for orphelin in plan.orphan_overrides), (
        f"orphelins vus : {plan.orphan_overrides}"
    )


def test_une_valeur_dexemple_posee_par_override_sort_dans_lexemple(
    tmp_path: Path, widget_service: ApiService
) -> None:
    """Le cas mesuré est `UpdateVolume.VolumeType` : trois valeurs citées dans une
    phrase, aucune dans un enum, et le repli publiait `example-id`."""
    _write(
        tmp_path,
        """
operations:
  widget.v1.Widget.UpdateWidget:
    parameters:
      WidgetType:
        example: gizmo
        reason: le contrat renvoie à ReadWidgetTypes pour les valeurs, et n'en déclare aucune
""",
    )
    spec = _spec(widget_service, tmp_path, "widget")
    ecriture, _ = spec.examples_documentation()
    assert ecriture[LAB_COLLECTION.module_fqcn("widget")]["widget_type"] == "gizmo"


# ---- les champs rendus ----------------------------------------------------------


def test_une_description_de_retour_sans_raison_est_refusee(tmp_path: Path) -> None:
    """Elle sortira sur Galaxy sous le nom de la collection."""
    _write(
        tmp_path,
        """
returns:
  Widget:
    Performance:
      description: The performance of the widget.
""",
    )
    with pytest.raises(OverrideError, match="sans `reason`"):
        load_overrides("widget", root=tmp_path)


def test_une_description_de_retour_comble_le_champ_muet(
    tmp_path: Path, widget_service: ApiService
) -> None:
    _write(
        tmp_path,
        """
returns:
  Widget:
    Performance:
      description: The performance of the widget.
      reason: recopié de WidgetPerformance, l'enum que le champ référence
""",
    )
    spec = _spec(widget_service, tmp_path, "widget_info")
    champs = {c.name: c.description for c in spec.contains["widgets"]}
    assert champs["Performance"] == ("The performance of the widget.",)


@pytest.mark.parametrize(
    ("bloc", "attendu"),
    [
        ("Disparu:\n    Colour:", "returns.Disparu"),
        ("Widget:\n    Colour:", "returns.Widget.Colour"),
        ("Widget:\n    State:", "returns.Widget.State : description d'override devenue inutile"),
    ],
    ids=["schéma inconnu", "champ inconnu", "champ déjà décrit"],
)
def test_un_override_de_retour_qui_ne_designe_rien_est_orphelin(
    tmp_path: Path, widget_service: ApiService, bloc: str, attendu: str
) -> None:
    """Un schéma qu'aucune réponse ne rend, un champ que le schéma ne porte pas,
    ou un champ que le contrat décrit déjà : trois textes morts."""
    _write(
        tmp_path,
        f"""
returns:
  {bloc}
      description: Colour of the widget.
      reason: cas de test
""",
    )
    plan = plan_service(widget_service, load_overrides("widget", root=tmp_path))
    assert any(orphelin.startswith(attendu) for orphelin in plan.orphan_overrides), (
        f"orphelins vus : {plan.orphan_overrides}"
    )
