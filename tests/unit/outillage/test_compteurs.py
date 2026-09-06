"""Les compteurs des README : dérivés, comparés, et refusés quand ils vieillissent.

Le mécanisme n'a de valeur que si la CI rougit sur un bloc périmé : c'est la
garde que ce fichier mesure. Le contenu du bloc, lui, vient de sources que
d'autres tests jugent déjà (le rapport, la génération, les modules).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import readme_counters

from generator.ansible.collection import Collection
from generator.source.base import ProductEntry


def _readme(tmp_path: Path, bloc: str) -> Path:
    fichier = tmp_path / "README.md"
    fichier.write_text(
        f"# Titre\n\n{readme_counters.DEBUT}\n{bloc}\n{readme_counters.FIN}\n\nsuite\n",
        encoding="utf-8",
    )
    return fichier


def test_un_bloc_perime_fait_echouer_le_controle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un nombre recopié à la main vieillit en silence : le contrôle doit rougir."""
    fichier = _readme(tmp_path, "ancien")
    monkeypatch.setattr(
        readme_counters, "cibles", lambda: {fichier: readme_counters.Cible(bloc="nouveau")}
    )
    assert readme_counters.main(["readme_counters.py", "--check"]) == 1


def test_un_bloc_a_jour_passe_le_controle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fichier = _readme(tmp_path, "nouveau")
    monkeypatch.setattr(
        readme_counters, "cibles", lambda: {fichier: readme_counters.Cible(bloc="nouveau")}
    )
    assert readme_counters.main(["readme_counters.py", "--check"]) == 0


def test_write_reecrit_le_bloc_entre_les_marqueurs_et_rien_dautre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fichier = _readme(tmp_path, "ancien")
    monkeypatch.setattr(
        readme_counters, "cibles", lambda: {fichier: readme_counters.Cible(bloc="nouveau")}
    )
    assert readme_counters.main(["readme_counters.py", "--write"]) == 0
    texte = fichier.read_text(encoding="utf-8")
    assert "nouveau" in texte and "ancien" not in texte
    assert texte.startswith("# Titre\n") and texte.endswith("\nsuite\n")


def test_des_marqueurs_absents_sont_une_erreur_pas_un_silence(tmp_path: Path) -> None:
    fichier = tmp_path / "README.md"
    fichier.write_text("# Sans marqueurs\n", encoding="utf-8")
    with pytest.raises(readme_counters.CompteursError, match="marqueurs"):
        readme_counters._remplace(fichier, fichier.read_text(encoding="utf-8"), "x")


def test_le_produit_dun_module_est_le_plus_long_prefixe_de_lindex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`block_storage_volume_info` appartient à `block_storage`, pas à `block`.

    Aucun nom de produit n'est écrit dans le script : c'est l'index qui dit
    où ranger un module.
    """
    racine = tmp_path / "ansible_collections" / "lab" / "gadget"
    modules = racine / "plugins" / "modules"
    modules.mkdir(parents=True)
    for nom in ("block_volume_info", "block_storage_volume_info"):
        (modules / f"{nom}.py").write_text(
            f'DOCUMENTATION = r"""\nmodule: {nom}\nshort_description: Reads {nom}\n"""\n',
            encoding="utf-8",
        )
    collection = Collection(namespace="lab", name="gadget", version="1.0.0", path=racine)
    monkeypatch.setattr(
        readme_counters,
        "_produits",
        lambda: [
            ProductEntry(tag="Block", product="block", version="v1"),
            ProductEntry(tag="BlockStorage", product="block_storage", version="v1"),
        ],
    )

    par_produit = readme_counters._modules_par_produit(collection)

    assert par_produit == {
        "block": [("block_volume_info", "Reads block_volume_info")],
        "block_storage": [("block_storage_volume_info", "Reads block_storage_volume_info")],
    }


def test_un_module_sans_produit_indexe_est_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = tmp_path / "ansible_collections" / "lab" / "gadget"
    modules = racine / "plugins" / "modules"
    modules.mkdir(parents=True)
    (modules / "orphan_info.py").write_text("", encoding="utf-8")
    collection = Collection(namespace="lab", name="gadget", version="1.0.0", path=racine)
    monkeypatch.setattr(
        readme_counters,
        "_produits",
        lambda: [ProductEntry(tag="Vm", product="vm", version="v1")],
    )
    with pytest.raises(readme_counters.CompteursError, match="orphan_info"):
        readme_counters._modules_par_produit(collection)


def test_le_pourcentage_publie_porte_le_point_decimal_de_langlais() -> None:
    """Le bloc atterrit dans un README publié : la frontière de langue passe là."""
    assert readme_counters._pourcent(0.797) == "79.7%"
    assert readme_counters._pourcent(None) == "n/a"


def test_un_module_de_gestion_detat_porte_le_nom_de_son_produit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`net` est le module MANAGE du produit `net` : le nom sans suffixe est le
    produit lui-même, et `net_peering` n'y est pas rangé pour autant."""
    racine = tmp_path / "ansible_collections" / "lab" / "gadget"
    modules = racine / "plugins" / "modules"
    modules.mkdir(parents=True)
    for nom in ("net", "net_info", "net_peering"):
        (modules / f"{nom}.py").write_text(
            f'DOCUMENTATION = r"""\nmodule: {nom}\nshort_description: Manages {nom}\n"""\n',
            encoding="utf-8",
        )
    collection = Collection(namespace="lab", name="gadget", version="1.0.0", path=racine)
    monkeypatch.setattr(
        readme_counters,
        "_produits",
        lambda: [
            ProductEntry(tag="Net", product="net", version="v1"),
            ProductEntry(tag="NetPeering", product="net_peering", version="v1"),
        ],
    )

    par_produit = readme_counters._modules_par_produit(collection)

    assert par_produit == {
        "net": [("net", "Manages net"), ("net_info", "Manages net_info")],
        "net_peering": [("net_peering", "Manages net_peering")],
    }
