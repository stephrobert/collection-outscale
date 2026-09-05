"""Le déroulé d'une liste paginée : jusqu'à la dernière page, jamais au-delà."""

from __future__ import annotations

from typing import Any

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.paging import (
    paginate,
)


def _pages(*reponses: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """Un appel qui rend les réponses dans l'ordre, et note ce qu'on lui a demandé."""
    file = list(reponses)
    demandes: list[dict[str, Any]] = []

    def appel(payload: dict[str, Any]) -> dict[str, Any]:
        demandes.append(payload)
        return file.pop(0)

    return appel, demandes


def test_les_pages_se_suivent_jusqua_labsence_de_jeton() -> None:
    appel, demandes = _pages(
        {"Items": [1, 2], "Next": "p2"},
        {"Items": [3], "Next": "p3"},
        {"Items": [4]},
    )
    resultat = paginate(appel, {"Filters": {"a": 1}}, "Items", "Next")
    assert resultat.items == (1, 2, 3, 4)
    assert resultat.calls == 3 and not resultat.truncated
    assert demandes == [
        {"Filters": {"a": 1}},
        {"Filters": {"a": 1}, "Next": "p2"},
        {"Filters": {"a": 1}, "Next": "p3"},
    ]


def test_une_seule_page_ne_demande_rien_de_plus() -> None:
    appel, demandes = _pages({"Items": [1]})
    assert paginate(appel, {}, "Items", "Next").items == (1,)
    assert demandes == [{}]


def test_un_jeton_repete_arrete_et_le_dit() -> None:
    """Une boucle sans fin vaut moins qu'une liste tronquée dite."""
    appel, _ = _pages({"Items": [1], "Next": "x"}, {"Items": [2], "Next": "x"}, {"Items": [3]})
    resultat = paginate(appel, {}, "Items", "Next")
    assert resultat.items == (1, 2) and resultat.calls == 2 and resultat.truncated


def test_une_page_sans_liste_ni_dictionnaire_compte_pour_rien() -> None:
    appel, _ = _pages(
        {"Next": None},
    )
    assert paginate(appel, {}, "Items", "Next").items == ()
    assert paginate(lambda _: None, {}, "Items", "Next").items == ()
