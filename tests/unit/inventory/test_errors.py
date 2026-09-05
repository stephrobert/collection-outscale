"""La taxonomie des échecs, lue sur la classe de l'exception puis le statut,
et les trois messages qu'un utilisateur doit pouvoir distinguer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.errors import (
    AuthenticationFailed,
    DiscoveryFailed,
    PermissionDenied,
    RequestRejected,
    api_errors,
    classify,
    describe,
)


class HTTPError(Exception):
    """La forme de `requests.HTTPError` : un message, et la réponse accrochée."""

    def __init__(self, status: int, body: Any = None, message: str = "erreur") -> None:
        super().__init__(message)

        def lire() -> Any:
            if isinstance(body, ValueError):
                raise body
            return body

        self.response = SimpleNamespace(status_code=status, json=lire)


class ParameterNotValid(NotImplementedError):
    """Le nom que le SDK donne à un paramètre que sa copie du contrat ignore."""


CORPS = {
    "Errors": [{"Code": "4001", "Type": "InvalidParameterValue", "Details": "the filter Mars"}],
    "ResponseContext": {"RequestId": "abc"},
}


def test_un_401_est_un_refus_dauthentification() -> None:
    assert classify(HTTPError(401)) is AuthenticationFailed


def test_un_403_est_un_droit_manquant() -> None:
    assert classify(HTTPError(403)) is PermissionDenied


def test_un_400_est_une_requete_rejetee() -> None:
    assert classify(HTTPError(400, CORPS)) is RequestRejected


def test_le_sdk_qui_refuse_avant_denvoyer_est_une_requete_rejetee() -> None:
    assert classify(ParameterNotValid("Mars")) is RequestRejected


def test_le_reste_est_une_panne() -> None:
    assert classify(HTTPError(503)) is DiscoveryFailed
    assert classify(ConnectionError("réseau")) is DiscoveryFailed


def test_un_echec_deja_classe_garde_sa_classe() -> None:
    assert classify(PermissionDenied("x")) is PermissionDenied


def test_le_corps_de_lapi_est_lu_code_type_et_details() -> None:
    assert api_errors(HTTPError(400, CORPS)) == ("4001 InvalidParameterValue: the filter Mars",)


def test_un_corps_illisible_ou_absent_ne_casse_rien() -> None:
    assert api_errors(HTTPError(500, ValueError("pas du JSON"))) == ()
    assert api_errors(HTTPError(500, "texte")) == ()
    assert api_errors(ConnectionError("réseau")) == ()


def test_trois_echecs_donnent_trois_messages_differents() -> None:
    """Un 401, un 403 et un 503 n'appellent pas la même réparation."""
    messages = {
        describe(HTTPError(401, message="unauthorized")),
        describe(HTTPError(403, message="forbidden")),
        describe(HTTPError(503, message="unavailable")),
    }
    assert len(messages) == 3
    assert any("identifiants refusés" in m and "401" in m for m in messages)
    assert any("droit manquant" in m and "403" in m for m in messages)
    assert any("panne" in m and "503" in m for m in messages)


def test_le_message_porte_ce_que_lapi_a_ecrit() -> None:
    texte = describe(HTTPError(400, CORPS))
    assert "requête rejetée" in texte and "the filter Mars" in texte and "400" in texte


def test_le_message_dune_panne_reseau_porte_lexception() -> None:
    assert "réseau" in describe(ConnectionError("réseau"))
