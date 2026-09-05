# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le déroulé d'une liste paginée, jusqu'à la dernière page.

Une lecture qui rend un jeton de page suivante n'a pas fini : rendre la
première page serait mentir sur le parc. Ce module déroule les pages ; il ne
sait ni quelle action il appelle ni ce qu'elle liste, c'est l'appelant qui
le lui dit. C'est la même règle que le runtime des modules applique à ses
lectures, écrite une seconde fois parce que le plugin d'inventaire ne dispose
pas d'un `AnsibleModule` pour l'appeler.

Un jeton rendu deux fois de suite arrête la boucle : l'API ne le promet pas,
et une boucle sans fin vaut moins qu'une liste tronquée **dite**.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

#: Un appel de page : reçoit les mots-clés de la requête, rend la réponse.
PageCall = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class Paged:
    """Ce que le déroulé a rendu, et combien il a coûté."""

    items: tuple[Any, ...]
    calls: int
    #: Vrai quand la boucle s'est arrêtée sur un jeton répété : la liste peut
    #: être incomplète, et l'appelant doit le dire.
    truncated: bool = False


def paginate(
    call: PageCall,
    kwargs: Mapping[str, Any],
    payload_field: str,
    token_field: str,
) -> Paged:
    """Appelle une lecture, et déroule ses pages jusqu'à la dernière."""
    items: list[Any] = []
    token: Any = None
    vus: set[Any] = set()
    appels = 0
    tronque = False

    while True:
        requete = dict(kwargs)
        if token:
            requete[token_field] = token
        resultat = call(requete)
        appels += 1
        page = resultat if isinstance(resultat, dict) else {}
        items.extend(page.get(payload_field) or [])
        token = page.get(token_field)
        if not token:
            break
        if token in vus:
            tronque = True
            break
        vus.add(token)

    return Paged(items=tuple(items), calls=appels, truncated=tronque)
