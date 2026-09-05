"""La source découpe un document unique par tag, et ne perd rien en chemin."""

from __future__ import annotations

from pathlib import Path

import pytest

from generator.source.base import (
    ProductNotFoundError,
    VendoredSpecSource,
    census,
    read_products,
    split_product,
)

from .conftest import WIDGET_SPECS


def test_lindex_designe_des_tags_et_nomme_le_produit_en_snake_case() -> None:
    entrees = read_products(WIDGET_SPECS)
    assert [(e.tag, e.product, e.version) for e in entrees] == [
        ("Widget", "widget", "v1"),
        ("Gadget", "gadget", "v1"),
    ]


def test_un_nom_de_produit_explicite_est_respecte(tmp_path: Path) -> None:
    (tmp_path / "products.txt").write_text("LoadBalancer lb v1\nVm v1\n", encoding="utf-8")
    entrees = read_products(tmp_path)
    assert [(e.tag, e.product) for e in entrees] == [("LoadBalancer", "lb"), ("Vm", "vm")]


def test_une_ligne_mal_formee_est_refusee(tmp_path: Path) -> None:
    (tmp_path / "products.txt").write_text("Vm vm v1 de trop\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mal formée"):
        read_products(tmp_path)


def test_le_decoupage_ne_garde_que_les_operations_du_tag() -> None:
    document = VendoredSpecSource(root=WIDGET_SPECS).load_document("v1")
    cut, famille = split_product(document, "Widget")
    identifiants = {
        op["operationId"]
        for item in cut["paths"].values()
        for op in item.values()
        if isinstance(op, dict)
    }
    assert famille == ("Widget",)
    assert {"ReadWidgets", "LinkGadget", "StartWidgets"} <= identifiants
    assert "ReadGadgets" not in identifiants, "un autre tag ne doit pas entrer"
    assert "Orphan" not in identifiants, "une opération sans tag n'appartient à personne"
    assert "Ping" not in identifiants


def test_un_tag_inconnu_est_refuse() -> None:
    document = VendoredSpecSource(root=WIDGET_SPECS).load_document("v1")
    with pytest.raises(ProductNotFoundError):
        split_product(document, "NExistePas")


def test_le_recensement_compte_chaque_operation_une_fois() -> None:
    """Ce que l'index n'indexe pas n'est pas perdu : il est compté ici."""
    document = VendoredSpecSource(root=WIDGET_SPECS).load_document("v1")
    recensement = census(document)
    assert recensement.by_tag == {"Gadget": 3, "Other": 1, "Widget": 11}
    assert recensement.untagged == ("Orphan",)
    assert recensement.non_post == ("Ping",)
    assert recensement.multi_tag == ()
    assert recensement.total == 16


def test_un_produit_absent_de_lindex_est_refuse() -> None:
    with pytest.raises(ProductNotFoundError):
        VendoredSpecSource(root=WIDGET_SPECS).load("other", "v1")


def test_un_produit_se_charge_par_son_tag_ou_par_son_nom() -> None:
    source = VendoredSpecSource(root=WIDGET_SPECS)
    assert source.load("Widget", "v1").product == "widget"
    assert source.load("widget", "v1").product == "widget"


def test_un_contrat_absent_dit_comment_le_telecharger(tmp_path: Path) -> None:
    (tmp_path / "products.txt").write_text("Widget v1\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="sync:api"):
        VendoredSpecSource(root=tmp_path).load("widget", "v1")
