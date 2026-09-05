# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""La taxonomie des échecs de découverte.

Un identifiant refusé, un droit manquant, une requête que l'API rejette et
une panne n'ont pas la même gravité, et un inventaire qui les confond rend un
parc incomplet, silencieux, avec un code de retour 0 :

* **l'authentification** est fatale partout : aucune région ne peut aboutir,
  et continuer ne produirait qu'un inventaire vide qui se présente comme
  complet ;
* **le droit refusé** ne l'est pas moins pour la région qui le rend : la
  lecture des machines est le seul appel du plugin, et un 403 sur elle veut
  dire que le parc de cette région est inconnu, pas vide ;
* **la requête rejetée** est une faute de configuration, presque toujours un
  filtre que l'API ne connaît pas, et l'API dit lequel ;
* **la panne** est tout le reste : un 5xx, un hôte injoignable, un corps
  illisible.

**Ce qu'Outscale fait, mesuré.** Le SDK lève `requests.HTTPError` et accroche
la réponse à l'exception ; le corps porte
`{"Errors": [{"Code", "Type", "Details"}], "ResponseContext": {...}}`. Un 401
est un refus d'authentification, un 403 un droit manquant, un 400 une requête
rejetée (mesuré contre feint : un filtre inconnu rend `4001
InvalidParameterValue` et nomme les filtres servis). Le SDK refuse aussi de
lui-même un paramètre que sa copie du contrat ne connaît pas, par une
exception héritant de `NotImplementedError`, avant tout envoi.

Le texte du message n'est jamais lu pour classer : un message change sans
prévenir. La classe de l'exception d'abord, puis le statut HTTP.
"""

from __future__ import annotations

from typing import Any


class InventoryError(Exception):
    """Un échec de découverte, classé."""

    #: Le mot que le message porte : trois échecs donnent trois messages.
    label = "échec"


class AuthenticationFailed(InventoryError):
    """Les identifiants sont refusés : rien ne peut être découvert."""

    label = "identifiants refusés"


class PermissionDenied(InventoryError):
    """Le compte n'a pas le droit de lire ce parc : il est inconnu, pas vide."""

    label = "droit manquant"


class RequestRejected(InventoryError):
    """L'API refuse la requête elle-même : un filtre inconnu, un paramètre faux."""

    label = "requête rejetée par l'API"


class DiscoveryFailed(InventoryError):
    """L'API a échoué pour une raison qui n'est ni un droit ni une requête fausse."""

    label = "panne de l'API ou du réseau"


def status_of(error: BaseException) -> int | None:
    """Le statut HTTP porté par une exception du SDK, s'il y en a un.

    `requests.HTTPError.response` est la réponse quand le SDK l'a reçue ; lu
    par `getattr` parce qu'une exception d'une autre origine (réseau, JSON)
    n'en porte pas.
    """
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return int(status) if isinstance(status, int) else None


def api_errors(error: BaseException) -> tuple[str, ...]:
    """Les erreurs que l'API a écrites dans son corps, une ligne chacune.

    `Code`, `Type` et `Details` sont les trois champs du contrat ; la ligne
    les porte dans cet ordre, et se passe de ceux qui manquent.
    """
    response = getattr(error, "response", None)
    lecteur = getattr(response, "json", None)
    if not callable(lecteur):
        return ()
    try:
        body: Any = lecteur()
    except ValueError:
        return ()
    if not isinstance(body, dict):
        return ()
    lignes: list[str] = []
    for item in body.get("Errors") or ():
        if not isinstance(item, dict):
            continue
        entete = " ".join(str(part) for part in (item.get("Code"), item.get("Type")) if part)
        details = item.get("Details")
        if details:
            entete = f"{entete}: {details}" if entete else str(details)
        if entete:
            lignes.append(entete)
    return tuple(lignes)


def classify(error: BaseException) -> type[InventoryError]:
    """Range un échec d'API dans la bonne catégorie.

    Un échec déjà classé garde sa classe. Une exception du SDK qui hérite de
    `NotImplementedError` est un refus avant envoi : le SDK connaît le contrat
    et dit que la requête est fausse. Ensuite le statut HTTP, qui est ce que
    l'API dit d'elle-même.
    """
    if isinstance(error, InventoryError):
        return type(error)
    if isinstance(error, NotImplementedError):
        return RequestRejected
    status = status_of(error)
    if status == 401:
        return AuthenticationFailed
    if status == 403:
        return PermissionDenied
    if status is not None and 400 <= status < 500:
        return RequestRejected
    return DiscoveryFailed


def describe(error: BaseException) -> str:
    """Une ligne qui dit la catégorie, le statut, et ce que l'API a écrit.

    C'est cette ligne que l'utilisateur lit : elle nomme la catégorie en
    clair, parce que « 403 » et « 503 » n'appellent pas la même réparation.
    """
    if isinstance(error, InventoryError):
        return str(error)
    categorie = classify(error)
    status = status_of(error)
    statut = f" (HTTP {status})" if status is not None else ""
    detail = " ; ".join(api_errors(error)) or str(error) or type(error).__name__
    return f"{categorie.label}{statut} : {detail}"
