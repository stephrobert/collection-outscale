"""Le troisième étage de couverture compte-t-il ce qu'il annonce ?

Appelé par l'exemple se dérive hors ligne du texte des playbooks, joué contre
une cible vient d'un artefact de run, et un écart se déclare avec sa raison,
par produit entier ou par module, jamais en silence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import example_coverage
import pytest


@pytest.fixture
def faux_depot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un dépôt de laboratoire : trois modules de deux produits, un playbook, aucun run."""
    modules = tmp_path / "modules"
    playbooks = tmp_path / "playbooks"
    artefacts = tmp_path / "artefacts"
    inventaire = tmp_path / "inventory"
    for dossier in (modules, playbooks, artefacts, inventaire):
        dossier.mkdir(parents=True)
    (inventaire / "vm.py").write_text("", encoding="utf-8")
    for nom in ("vm_action", "vm_info", "volume_update_task_info"):
        (modules / f"{nom}.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(example_coverage, "MODULES", modules)
    monkeypatch.setattr(example_coverage, "PLAYBOOKS", playbooks)
    monkeypatch.setattr(example_coverage, "ARTEFACTS", artefacts)
    monkeypatch.setattr(example_coverage, "INVENTAIRE", inventaire)
    monkeypatch.setattr(example_coverage, "PREFIXE", "stephrobert.outscale.")
    monkeypatch.setattr(example_coverage, "produits_indexes", lambda: ("vm", "volume"))
    # Les écarts déclarés du vrai dépôt n'ont rien à faire dans un dépôt de
    # laboratoire : chaque test qui en veut un le pose lui-même.
    monkeypatch.setattr(example_coverage, "SANS_CIBLE", {})
    monkeypatch.setattr(example_coverage, "PRODUITS_SANS_CIBLE", {})
    return tmp_path


def _playbook(depot: Path, contenu: str) -> None:
    (depot / "playbooks" / "modules.yml").write_text(contenu, encoding="utf-8")


def test_le_ratio_compte_les_modules_que_lexemple_nomme(faux_depot: Path) -> None:
    _playbook(
        faux_depot,
        "- stephrobert.outscale.vm_action:\n- stephrobert.outscale.volume_update_task_info:\n",
    )
    mesure = example_coverage.mesurer()
    assert mesure["appeles_par_lexemple"] == ["vm_action", "volume_update_task_info"]
    assert mesure["jamais_appeles"] == ["vm_info"]
    assert mesure["ratio_appeles"] == "66,7 %"


def test_le_plugin_dinventaire_nest_pas_un_module(faux_depot: Path) -> None:
    """Son nom vient du répertoire des plugins, pas d'une liste écrite ici."""
    _playbook(faux_depot, "plugin: stephrobert.outscale.vm\n")
    assert example_coverage.mesurer()["appeles_par_lexemple"] == []


def test_un_nom_qui_ne_designe_aucun_module_est_refuse(faux_depot: Path) -> None:
    """Une faute de frappe ne doit pas se ranger en silence du côté « pas un module »."""
    _playbook(faux_depot, "- stephrobert.outscale.vm_infoo:\n")
    with pytest.raises(example_coverage.CouvertureError, match="vm_infoo"):
        example_coverage.mesurer()


def test_sans_module_le_ratio_est_indefini_pas_nul(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vide = tmp_path / "vide"
    vide.mkdir()
    monkeypatch.setattr(example_coverage, "MODULES", vide)
    monkeypatch.setattr(example_coverage, "PLAYBOOKS", vide)
    monkeypatch.setattr(example_coverage, "ARTEFACTS", vide)
    monkeypatch.setattr(example_coverage, "INVENTAIRE", vide)
    assert example_coverage.mesurer()["ratio_appeles"] == "n/a"


def test_sans_run_enregistre_on_le_dit_plutot_que_decrire_zero(faux_depot: Path) -> None:
    """Rien n'a été mesuré n'est pas rien n'a marché."""
    _playbook(faux_depot, "- stephrobert.outscale.vm_info:\n")
    mesure = example_coverage.mesurer()
    assert mesure["runs"] == {}
    assert "aucun run enregistré" in example_coverage.rendre(mesure)


def test_un_run_enregistre_publie_ce_quil_a_joue(faux_depot: Path) -> None:
    _playbook(faux_depot, "- stephrobert.outscale.vm_info:\n")
    artefact: dict[str, Any] = {
        "cible": "emulateur",
        "run_id": "abc",
        "horodatage": "2026-09-04T06:00:00+00:00",
        "modules_joues": ["vm_info"],
        "idempotence_prouvee": ["vm_action.stop"],
        "residu": "sans objet (émulateur)",
    }
    (faux_depot / "artefacts" / "dernier-emulateur.json").write_text(
        json.dumps(artefact), encoding="utf-8"
    )
    run = example_coverage.mesurer()["runs"]["emulateur"]
    assert run["modules_joues"] == ["vm_info"]
    assert run["ratio_joues"] == "33,3 %"
    assert run["idempotence_prouvee"] == 1


# --- la porte, et ce qu'elle refuse ----------------------------------------


def test_un_module_nomme_en_commentaire_ne_compte_pas(faux_depot: Path) -> None:
    """La porte lit les clés de tâches, pas le texte du fichier."""
    _playbook(
        faux_depot,
        "# stephrobert.outscale.vm_action n'a pas de cible ici\n- stephrobert.outscale.vm_info:\n",
    )
    assert example_coverage.mesurer()["appeles_par_lexemple"] == ["vm_info"]


def test_un_module_dans_un_block_compte(faux_depot: Path) -> None:
    _playbook(
        faux_depot,
        "- hosts: localhost\n"
        "  tasks:\n"
        "    - block:\n"
        "        - stephrobert.outscale.vm_action: {}\n"
        "      rescue:\n"
        "        - stephrobert.outscale.vm_info: {}\n",
    )
    assert example_coverage.mesurer()["appeles_par_lexemple"] == [
        "vm_action",
        "vm_info",
    ]


def test_un_produit_declare_sans_cible_couvre_ses_modules(
    faux_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un produit entier que feint ne sert pas se déclare une fois, avec sa mesure."""
    monkeypatch.setattr(example_coverage, "PRODUITS_SANS_CIBLE", {"volume": "feint ne sert rien"})
    _playbook(
        faux_depot,
        "- stephrobert.outscale.vm_action:\n- stephrobert.outscale.vm_info:\n",
    )
    mesure = example_coverage.mesurer()
    assert mesure["non_couverts"] == []
    assert mesure["sans_cible_declaree"] == ["volume_update_task_info"]


def test_un_module_non_couvert_et_non_declare_est_refuse(faux_depot: Path) -> None:
    """Le cas voisin : sans la déclaration, le même module fait échouer."""
    _playbook(
        faux_depot,
        "- stephrobert.outscale.vm_action:\n- stephrobert.outscale.vm_info:\n",
    )
    assert example_coverage.mesurer()["non_couverts"] == ["volume_update_task_info"]


def test_une_declaration_perimee_est_refusee(
    faux_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un module déclaré sans cible que l'exemple appelle pourtant raconte un
    obstacle qui n'existe plus."""
    monkeypatch.setattr(example_coverage, "SANS_CIBLE", {"vm_info": "aucune cible"})
    _playbook(faux_depot, "- stephrobert.outscale.vm_info:\n")
    assert example_coverage.mesurer()["declarations_perimees"] == ["vm_info"]


def test_la_porte_sort_en_1_sur_un_module_sans_cible_ni_raison(
    faux_depot: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _playbook(faux_depot, "- stephrobert.outscale.vm_info:\n")
    assert example_coverage.main(["x", "--check"]) == 1
    assert "vm_action" in capsys.readouterr().err
