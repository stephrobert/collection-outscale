"""L'outillage refuse les verdicts qui n'ont rien mesuré.

Deux commandes de ce dépôt peuvent rendre un vert parfait sans avoir rien
regardé : `ansible-test sanity`, qui sort en 0 sur zéro fichier examiné, et
l'archive, qui existe même quand elle oublie un plugin ou emporte les tests.
Ce fichier tient la garde de chacune, parce qu'une garde qu'aucun test ne
mesure est un commentaire.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import package
import pytest
import sanity

from generator.ansible.collection import Collection

# ---- sanity ---------------------------------------------------------------


def test_sanity_refuse_une_collection_que_git_ne_suit_pas() -> None:
    """Le cas exact du faux vert : dans un dépôt, zéro fichier suivi."""
    message = sanity.refusal(under_git=True, tracked=0, where="ansible_collections/x/y")
    assert message is not None
    assert "aucune cible" in message


def test_sanity_mesure_une_collection_suivie() -> None:
    assert sanity.refusal(under_git=True, tracked=27, where="x") is None


def test_hors_dun_depot_git_sanity_parcourt_le_disque() -> None:
    """Hors dépôt, `ansible-test` ne demande rien à git : refuser là serait
    refuser une mesure qui a lieu."""
    assert sanity.refusal(under_git=False, tracked=0, where="x") is None


def test_sanity_refuse_un_vert_qui_na_rien_examine() -> None:
    """`All targets skipped` sort en 0 : c'est la seule chose qui le distingue
    d'une collection irréprochable."""
    assert not sanity.measured_something("Running sanity test...\nWARNING: All targets skipped.\n")


def test_sanity_accepte_une_sortie_qui_a_examine_quelque_chose() -> None:
    assert sanity.measured_something("Running sanity test 'pep8' with Python 3.12\n")


# ---- archive --------------------------------------------------------------


def _collection(tmp_path: Path, plugins: tuple[str, ...]) -> Collection:
    """Une collection sur disque, avec les plugins nommés."""
    racine = tmp_path / "ansible_collections" / "lab" / "gadget"
    for relatif in plugins:
        chemin = racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("", encoding="utf-8")
    return Collection(namespace="lab", name="gadget", version="1.0.0", path=racine)


def _archive(tmp_path: Path, fichiers: tuple[str, ...], repertoires: tuple[str, ...] = ()) -> Path:
    """Une archive qui porte exactement ces fichiers et ces répertoires."""
    chemin = tmp_path / "lab-gadget-1.0.0.tar.gz"
    with tarfile.open(chemin, "w:gz") as tar:
        for repertoire in repertoires:
            info = tarfile.TarInfo(repertoire)
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        for fichier in fichiers:
            info = tarfile.TarInfo(fichier)
            info.size = 0
            tar.addfile(info)
    return chemin


def test_un_repertoire_interdit_meme_vide_est_une_fuite() -> None:
    """L'archive de Scaleway emportait un `tests/` vide, et le contrôle qui ne
    regardait que les fichiers ne le voyait pas."""
    assert package.leaks(("MANIFEST.json", "tests")) == ["tests"]


def test_un_fichier_sous_un_repertoire_interdit_est_une_fuite() -> None:
    assert package.leaks(("generator/cli.py", "plugins/modules/a.py")) == ["generator"]


def test_une_archive_propre_ne_fuit_rien() -> None:
    assert package.leaks(("MANIFEST.json", "plugins/modules/a.py", "meta/runtime.yml")) == []


def test_ce_que_larchive_doit_porter_se_lit_sur_le_disque(tmp_path: Path) -> None:
    """Un module renommé entre dans le contrôle sans qu'on y pense."""
    collection = _collection(
        tmp_path,
        ("plugins/modules/gadget_info.py", "plugins/module_utils/outscale.py"),
    )
    attendu = package.required_entries(collection)
    assert "plugins/modules/gadget_info.py" in attendu
    assert "plugins/module_utils/outscale.py" in attendu
    assert "MANIFEST.json" in attendu


def test_une_archive_qui_oublie_un_plugin_est_refusee(tmp_path: Path) -> None:
    """Sans cette moitié, une archive vide passerait tous les contrôles de l'autre."""
    collection = _collection(tmp_path, ("plugins/modules/gadget_info.py",))
    archive = _archive(tmp_path, (*package.REQUIRED_METADATA,))
    with pytest.raises(package.PackageError, match="gadget_info"):
        package.check_contents(archive, collection)


def test_une_archive_qui_emporte_les_tests_est_refusee(tmp_path: Path) -> None:
    collection = _collection(tmp_path, ("plugins/modules/gadget_info.py",))
    archive = _archive(
        tmp_path,
        (*package.REQUIRED_METADATA, "plugins/modules/gadget_info.py"),
        repertoires=("tests",),
    )
    with pytest.raises(package.PackageError, match="tests"):
        package.check_contents(archive, collection)


def test_une_archive_complete_est_acceptee(tmp_path: Path) -> None:
    """Le cas voisin : une garde qui refuse tout ferait passer les précédents."""
    collection = _collection(tmp_path, ("plugins/modules/gadget_info.py",))
    archive = _archive(tmp_path, (*package.REQUIRED_METADATA, "plugins/modules/gadget_info.py"))
    contenu = package.check_contents(archive, collection)
    assert "plugins/modules/gadget_info.py" in contenu


def test_les_plugins_dinventaire_se_lisent_sur_le_disque(tmp_path: Path) -> None:
    """Le nom d'un plugin codé en dur a survécu à son renommage chez Scaleway."""
    collection = _collection(tmp_path, ("plugins/inventory/compute.py", "plugins/inventory/_x.py"))
    assert package.inventory_plugins(collection) == ("compute",)


def test_sans_repertoire_dinventaire_aucun_plugin_nest_invente(tmp_path: Path) -> None:
    collection = _collection(tmp_path, ("plugins/modules/gadget_info.py",))
    assert package.inventory_plugins(collection) == ()
