# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ce qu'un provider doit savoir faire, et ce qu'il ne doit pas faire.

**Un provider ne touche jamais à l'objet d'inventaire d'Ansible.** Il rend un
`ProviderResult` ; c'est le moteur qui décide ensuite quoi en faire. Sans
cette règle, ajouter un produit demanderait de toucher au cœur.

**Un provider n'importe pas le SDK.** Il reçoit une fabrique de clients, un
par région, qui expose les actions du contrat par leur nom. Un test lui passe
un objet qui rend des réponses figées, et la normalisation se mesure sans
réseau ni identifiants.

**Un provider dit ce qu'il ajoute.** Ses axes de groupes propres vont dans sa
table `group_axes`, d'un nom d'axe à la clé de `metadata` qui le porte, et le
cœur les lit là sans les connaître.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..models import ProviderResult


@dataclass(frozen=True)
class DiscoveryContext:
    """Ce que l'utilisateur a demandé, tel qu'un provider en a besoin."""

    #: Les régions à interroger, déjà résolues : jamais vide à l'exécution.
    regions: tuple[str, ...] = ()
    #: Les filtres de l'API, tels quels, avec le vocabulaire du contrat.
    api_filters: Mapping[str, Any] = field(default_factory=dict)
    include_raw: bool = False


#: Une fabrique de client : une région, un client qui parle à cette région.
#: `None` demande le client de la région que le SDK résout lui-même.
#: `Optional` et non `str | None` : cet alias est évalué à l'exécution, et le
#: pylint d'`ansible-test sanity` (ansible-core 2.18 et plus) y voit une
#: opération binaire non prise en charge, mesuré en CI sur les quatre versions.
ClientFactory = Callable[[Optional[str]], Any]  # noqa: UP045


class InventoryProvider(Protocol):
    """L'interface qu'un produit doit remplir pour entrer dans l'inventaire."""

    name: str

    #: Les axes de groupes que ce produit ajoute au cœur : nom de l'axe vers
    #: la clé de `metadata` qui le porte.
    group_axes: Mapping[str, str]

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        """Découvre les machines de ce produit et rend un résultat.

        Le corps est une docstring et non le `...` habituel d'un `Protocol` :
        `ansible-test sanity` refuse `def f(): ...` en E704 sur ansible-core
        2.17 et 2.18.
        """
