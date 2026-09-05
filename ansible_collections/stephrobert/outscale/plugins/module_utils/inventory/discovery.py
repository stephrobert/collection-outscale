# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""L'orchestration : construire les clients, lancer les providers, agréger.

C'est la seule couche qui importe le SDK. Les providers reçoivent une fabrique
de clients, et le plugin reçoit un résultat. Chacune se teste donc sans les
autres.

**Un client par région.** L'hôte de l'API porte la région
(`api.{region}.outscale.com`) : il n'existe pas d'appel qui parle de tout le
compte. Avec une URL explicite (un émulateur), un seul client sert toutes les
régions, et c'est dit. Un `Gateway` coûte une seconde à construire, parce
qu'il charge sa copie du contrat : la fabrique n'en construit jamais deux
pour la même région.

**La région par défaut est celle du SDK.** Il la résout depuis
l'environnement (`OSC_REGION`), puis le profil, puis `eu-west-2`. Le plugin
ne la devine pas : il construit le client sans région et lui demande.
"""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import AuthenticationFailed
from .models import ProviderResult
from .providers.base import ClientFactory, DiscoveryContext
from .providers.vm import VmProvider

try:
    from osc_sdk_python import Gateway
    from osc_sdk_python.credentials import Endpoint

    SDK_IMPORT_ERROR: str | None = None
    HAS_SDK = True
except ImportError:
    SDK_IMPORT_ERROR = traceback.format_exc()
    HAS_SDK = False

#: Les providers de hosts que cette version connaît. Ajouter un produit, c'est
#: ajouter une ligne ici et un fichier de provider ; aucune autre couche ne
#: connaît le nom d'un produit.
HOST_PROVIDERS: tuple[str, ...] = ("vm",)

_FABRIQUES: Mapping[str, Any] = {"vm": VmProvider}


@dataclass
class DiscoveryReport:
    """Ce que la découverte a fait, pour le mode debug et le rapport d'échec."""

    api_calls: int = 0
    providers: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        resume = ", ".join(f"{nom}={compte}" for nom, compte in sorted(self.providers.items()))
        return [
            f"appels d'API : {self.api_calls}",
            f"hosts par provider : {resume or 'aucun'}",
            *(f"avertissement : {texte}" for texte in self.warnings),
            *(f"erreur : {texte}" for texte in self.errors),
        ]


def client_factory(
    access_key: str | None = None,
    secret_key: str | None = None,
    profile: str | None = None,
    api_url: str | None = None,
) -> ClientFactory:
    """Une fabrique de clients, un par région, ou un seul quand l'URL est imposée.

    Rien n'est obligatoire : le SDK lit `~/.osc/config.json` et
    l'environnement, et un mot-clé absent le laisse faire. `OSC_ENDPOINT_API`
    reste honoré de bout en bout : avec une URL, toutes les régions parlent au
    même hôte, ce qui est ce qu'un émulateur attend.
    """
    if not HAS_SDK:
        raise ImportError(SDK_IMPORT_ERROR or "le SDK osc-sdk-python n'est pas installé")
    clients: dict[str | None, Any] = {}

    def for_region(region: str | None) -> Any:
        cle = None if api_url else region
        if cle in clients:
            return clients[cle]
        kwargs: dict[str, Any] = {}
        if profile:
            kwargs["profile"] = profile
        if access_key:
            kwargs["access_key"] = access_key
        if secret_key:
            kwargs["secret_key"] = secret_key
        if api_url:
            kwargs["endpoints"] = Endpoint(api=api_url)
        elif region:
            kwargs["region"] = region
        client = Gateway(**kwargs)
        clients[cle] = client
        if cle is None:
            # Le client sans région a résolu la sienne : le même servira
            # cette région, plutôt qu'un second qui rechargerait le contrat.
            resolue = default_region_of(client)
            if resolue and not api_url:
                clients[resolue] = client
        return client

    return for_region


def default_region_of(client: Any) -> str | None:
    """La région qu'un client a résolue, lue sur lui plutôt que devinée."""
    lecteur = getattr(client, "region", None)
    if not callable(lecteur):
        return None
    valeur = lecteur()
    return str(valeur) if valeur else None


def resolve_regions(requested: tuple[str, ...], client_for: ClientFactory) -> tuple[str, ...]:
    """Les régions à interroger : celles demandées, sinon celle du SDK.

    Sans région demandée et sans région résolue par le SDK, le plugin ne sait
    pas où regarder, et le dit plutôt que de choisir une région à sa place.
    """
    if requested:
        return tuple(dict.fromkeys(requested))
    resolue = default_region_of(client_for(None))
    if not resolue:
        raise ValueError(
            "aucune région : donner `regions`, ou OSC_REGION, ou un profil qui en porte une"
        )
    return (resolue,)


def providers_for(client_for: ClientFactory, products: tuple[str, ...]) -> tuple[Any, ...]:
    """Instancie les providers demandés, et refuse un produit inconnu."""
    inconnus = sorted(set(products) - set(HOST_PROVIDERS))
    if inconnus:
        raise ValueError(f"produit(s) inconnu(s) : {inconnus}. Connus : {list(HOST_PROVIDERS)}")
    return tuple(_FABRIQUES[nom](client_for) for nom in products)


def group_axes(products: tuple[str, ...]) -> dict[str, str]:
    """Les axes de groupes que les produits demandés ajoutent au cœur.

    Lus sur la classe, pour ne pas instancier un provider avant d'avoir un
    client. Deux produits qui déclarent le même axe doivent le porter par la
    même clé ; sinon c'est une erreur de programmation, et elle est dite.
    """
    axes: dict[str, str] = {}
    for nom in products:
        if nom not in _FABRIQUES:
            raise ValueError(f"produit inconnu : {nom}. Connus : {list(HOST_PROVIDERS)}")
        for axe, cle in dict(_FABRIQUES[nom].group_axes).items():
            if axes.get(axe, cle) != cle:
                raise ValueError(f"l'axe {axe} est porté par deux clés : {axes[axe]} et {cle}")
            axes[axe] = cle
    return axes


def discover(
    client_for: ClientFactory,
    context: DiscoveryContext,
    products: tuple[str, ...],
    strict: bool = True,
) -> tuple[ProviderResult, DiscoveryReport]:
    """Lance les providers et agrège leurs résultats.

    En mode strict, l'échec d'un provider fait échouer l'inventaire. Sinon il
    devient un avertissement, et le rapport nomme le provider fautif. Dans les
    deux cas, l'échec est **dit**.
    """
    resultat = ProviderResult()
    report = DiscoveryReport()

    for provider in providers_for(client_for, products):
        try:
            partiel = provider.discover(context)
        except AuthenticationFailed:
            raise
        except Exception as erreur:
            message = f"{provider.name} : {erreur}"
            if strict:
                raise
            report.errors.append(message)
            continue

        resultat = resultat.merge(partiel)
        report.api_calls += partiel.api_calls
        report.providers[provider.name] = len(partiel.hosts)
        report.warnings.extend(partiel.warnings)
        report.errors.extend(partiel.errors)

    return resultat, report
