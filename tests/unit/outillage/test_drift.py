"""Le rapport de dérive voit un produit que le golden ne couvre pas.

Un seul document porte quatorze produits, et le golden ne suit que ceux que
`products.txt` indexe. Une opération apparue dans un produit non indexé ne
ferait rougir aucun golden : le recensement est la seule mesure qui la voit,
et ce fichier exige qu'il la nomme.
"""

from __future__ import annotations

import drift_report


def test_un_produit_non_indexe_qui_grossit_est_nomme() -> None:
    ecarts = drift_report.ecarts_par_produit(
        {"Vm": 12, "VmGroup": 6}, {"Vm": 12, "VmGroup": 8}, frozenset({"Vm"})
    )
    assert ecarts == [("VmGroup", 6, 8, False)]


def test_un_produit_apparu_compte_zero_avant() -> None:
    ecarts = drift_report.ecarts_par_produit(
        {"compute": 111}, {"compute": 111, "edge": 3}, frozenset()
    )
    assert ecarts == [("edge", 0, 3, False)]


def test_un_produit_disparu_compte_zero_apres() -> None:
    ecarts = drift_report.ecarts_par_produit(
        {"compute": 111, "sos": 2}, {"compute": 111}, frozenset()
    )
    assert ecarts == [("sos", 2, 0, False)]


def test_un_produit_indexe_est_marque_comme_suivi() -> None:
    ecarts = drift_report.ecarts_par_produit(
        {"compute": 111}, {"compute": 112}, frozenset({"compute"})
    )
    assert ecarts == [("compute", 111, 112, True)]


def test_sans_ecart_rien_nest_invente() -> None:
    assert drift_report.ecarts_par_produit({"compute": 111}, {"compute": 111}, frozenset()) == []


def test_le_rapport_nomme_le_produit_et_dit_sil_est_suivi() -> None:
    texte = drift_report.rapport(
        ["specs/outscale/outscale.v1.yml"],
        [("dbaas", 146, 148, False), ("compute", 111, 112, True)],
        "",
        374,
        377,
    )
    assert "`dbaas` | 146 | 148 | non" in texte
    assert "`compute` | 111 | 112 | oui" in texte
    assert "374 à 377" in texte


def test_un_golden_inchange_est_dit_plutot_que_tu() -> None:
    texte = drift_report.rapport(["x"], [], "", 1, 1)
    assert "Aucun changement dans l'IR" in texte
    assert "Aucun tag ne change" in texte
