"""Le prochain numéro se déduit des fragments, et rien d'autre ne le décide.

Une version tapée à la main est un nombre recopié de plus. Ce que la version
promet est déjà écrit dans les fragments : une rupture, un ajout, une
correction. Le script lit, il ne choisit pas.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import version


@pytest.mark.parametrize(
    ("sections", "attendu"),
    [
        ({"breaking_changes": ["a.yml"]}, "majeure"),
        ({"removed_features": ["a.yml"], "bugfixes": ["b.yml"]}, "majeure"),
        ({"minor_changes": ["a.yml"], "bugfixes": ["b.yml"]}, "mineure"),
        ({"deprecated_features": ["a.yml"]}, "mineure"),
        ({"bugfixes": ["a.yml"]}, "correctif"),
        ({"security_fixes": ["a.yml"]}, "correctif"),
        ({"release_summary": ["a.yml"]}, None),
        ({}, None),
    ],
)
def test_la_portee_vient_de_la_section_la_plus_forte(
    sections: dict[str, list[str]], attendu: str | None
) -> None:
    """`release_summary` décrit la version, il ne la change pas."""
    assert version.portee(sections) == attendu


def test_sans_fragment_il_ny_a_rien_a_publier() -> None:
    """Une version sans changement décrit n'apporte rien à personne."""
    assert version.portee({}) is None


@pytest.mark.parametrize(
    ("courante", "echelon", "attendue"),
    [
        ("0.1.0", "correctif", "0.1.1"),
        ("0.1.3", "mineure", "0.2.0"),
        ("1.4.2", "majeure", "2.0.0"),
        ("1.4.2", "mineure", "1.5.0"),
    ],
)
def test_le_numero_suivant_suit_le_versionnement_semantique(
    courante: str, echelon: str, attendue: str
) -> None:
    assert version.suivante(courante, echelon) == attendue


def test_une_rupture_avant_1_0_0_incremente_la_mineure() -> None:
    """Déclarer les interfaces stables est un acte humain, pas la conséquence
    mécanique d'un fragment : `0.3.0` rompu donne `0.4.0`, pas `1.0.0`."""
    assert version.suivante("0.3.0", "majeure") == "0.4.0"


def test_une_version_qui_nest_pas_semver_est_refusee() -> None:
    with pytest.raises(version.VersionError, match="sémantique"):
        version.suivante("0.1", "mineure")


def test_les_sections_se_lisent_dans_les_fragments_sur_le_disque(tmp_path: Path) -> None:
    dossier = tmp_path / "changelogs" / "fragments"
    dossier.mkdir(parents=True)
    (dossier / "a.yml").write_text("minor_changes:\n  - A.\n", encoding="utf-8")
    (dossier / "b.yml").write_text("bugfixes:\n  - B.\nminor_changes:\n  - C.\n", encoding="utf-8")
    (dossier / ".gitkeep").write_text("", encoding="utf-8")
    assert version.sections_en_attente(tmp_path) == {
        "minor_changes": ["a.yml", "b.yml"],
        "bugfixes": ["b.yml"],
    }


def test_ecrire_la_version_ne_touche_qua_sa_ligne(tmp_path: Path) -> None:
    """`galaxy.yml` porte ses raisons en commentaires : une réécriture YAML les perdrait."""
    galaxy = tmp_path / "galaxy.yml"
    galaxy.write_text(
        "# Identité de la collection.\nnamespace: lab\nname: widget\nversion: 0.1.0\n"
        "# Publié sur Galaxy, donc en anglais.\ndescription: A test.\n",
        encoding="utf-8",
    )
    version.ecrire_version(tmp_path, "0.2.0")
    texte = galaxy.read_text(encoding="utf-8")
    assert "version: 0.2.0\n" in texte
    assert "# Identité de la collection." in texte
    assert "# Publié sur Galaxy, donc en anglais." in texte


def test_un_galaxy_sans_ligne_de_version_est_refuse(tmp_path: Path) -> None:
    (tmp_path / "galaxy.yml").write_text("namespace: lab\nname: widget\n", encoding="utf-8")
    with pytest.raises(version.VersionError, match="version"):
        version.ecrire_version(tmp_path, "0.2.0")
