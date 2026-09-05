"""Le témoin du mode strict : il sort en 2 sur une opération non classée.

`report --strict` sort en 0 sur un dépôt sain comme sur un mode strict cassé :
un contrôle qui cherche une absence est indiscernable d'un contrôle qui n'a
rien regardé. Ce fichier plante le témoin, en fabriquant un contrat que
personne ne sait classer, et exige le code 2. Le code est ce dont la CI
dépend, donc c'est le code qui est mesuré, pas un message.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from generator.cli import EXIT_OK, EXIT_UNDECIDED, main

REPO_ROOT = Path(__file__).resolve().parents[3]
WIDGET_INPUT = REPO_ROOT / "tests" / "fixtures" / "widget" / "input"


def _spec_root(tmp_path: Path, *, with_unknown: bool) -> Path:
    """Le contrat de laboratoire, avec ou sans une opération que rien ne tranche.

    Un POST dont le verbe est `Frob` : aucune règle ne le connaît, et c'est le
    point. Le reste du contrat est celui du laboratoire, dont les autres tests
    prouvent déjà qu'il se classe entièrement.
    """
    racine = tmp_path / "specs"
    shutil.copytree(WIDGET_INPUT, racine)
    if with_unknown:
        chemin = racine / "outscale.v1.yml"
        document = yaml.safe_load(chemin.read_text(encoding="utf-8"))
        document["paths"]["/FrobWidget"] = {
            "post": {
                "operationId": "FrobWidget",
                "description": "Frobs a widget.",
                "tags": ["Widget"],
                "responses": {"200": {"description": "OK"}},
            }
        }
        chemin.write_text(yaml.safe_dump(document), encoding="utf-8")
    return racine


def _report(tmp_path: Path, racine: Path, *, strict: bool) -> int:
    arguments = [
        "--spec-root",
        str(racine),
        "report",
        "widget",
        "--output-dir",
        str(tmp_path / "reports"),
    ]
    if strict:
        arguments.append("--strict")
    return main(arguments)


def test_le_mode_strict_sort_en_2_sur_une_operation_non_classee(tmp_path: Path) -> None:
    """Le témoin. Sans lui, un mode strict cassé se lirait comme un dépôt sain."""
    racine = _spec_root(tmp_path, with_unknown=True)
    assert _report(tmp_path, racine, strict=True) == EXIT_UNDECIDED


def test_sans_strict_le_rapport_dit_et_ne_refuse_pas(tmp_path: Path) -> None:
    """Le contre-exemple : c'est `--strict` qui transforme le constat en refus."""
    racine = _spec_root(tmp_path, with_unknown=True)
    assert _report(tmp_path, racine, strict=False) == EXIT_OK


def test_le_mode_strict_sort_en_0_quand_tout_est_classe(tmp_path: Path) -> None:
    """Le cas voisin : un mode strict qui refuse tout ferait passer le témoin."""
    racine = _spec_root(tmp_path, with_unknown=False)
    assert _report(tmp_path, racine, strict=True) == EXIT_OK


def test_le_recensement_compte_les_unknown_de_chaque_tag(tmp_path: Path, capsys: object) -> None:
    """`products --classify` est la seule mesure qui voit un tag non indexé."""
    import pytest

    racine = _spec_root(tmp_path, with_unknown=False)
    assert main(["--spec-root", str(racine), "products", "--classify"]) == EXIT_OK
    capture = pytest.importorskip("pytest").CaptureFixture  # noqa: F841
    sortie = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Other" in sortie and "Ping" in sortie
    assert "1 opération(s) non classée(s) sur 16" in sortie
    assert "Orphan" in sortie
