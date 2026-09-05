"""L'orchestration : un client par région, la région par défaut, et ce qu'un
échec devient selon le mode strict."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory import discovery
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.errors import (
    AuthenticationFailed,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.providers.base import (
    DiscoveryContext,
)


class _Client:
    def __init__(self, region: str = "eu-west-2", vms: list[dict[str, Any]] | None = None) -> None:
        self._region = region
        self.vms = vms or []
        self.appels: list[dict[str, Any]] = []

    def region(self) -> str:
        return self._region

    def ReadVms(self, **kwargs: Any) -> dict[str, Any]:
        self.appels.append(kwargs)
        return {"Vms": self.vms, "ResponseContext": {"RequestId": "x"}}


class _Gateway:
    """Le double du SDK : note comment il a été construit, et rend sa région."""

    construits: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _Gateway.construits.append(kwargs)

    def region(self) -> str:
        return str(self.kwargs.get("region") or "eu-west-2")


class _Endpoint:
    def __init__(self, api: str) -> None:
        self.api = api


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> type[_Gateway]:
    _Gateway.construits = []
    monkeypatch.setattr(discovery, "Gateway", _Gateway)
    monkeypatch.setattr(discovery, "Endpoint", _Endpoint)
    monkeypatch.setattr(discovery, "HAS_SDK", True)
    return _Gateway


def test_la_fabrique_rend_un_client_par_region_et_jamais_deux(sdk: type[_Gateway]) -> None:
    par_region = discovery.client_factory("AK", "SK", None, None)
    a = par_region("eu-west-2")
    assert par_region("eu-west-2") is a
    par_region("cloudgouv-eu-west-1")
    assert [c.get("region") for c in sdk.construits] == ["eu-west-2", "cloudgouv-eu-west-1"]
    assert sdk.construits[0]["access_key"] == "AK" and sdk.construits[0]["secret_key"] == "SK"


def test_avec_une_url_un_seul_client_sert_toutes_les_regions(sdk: type[_Gateway]) -> None:
    """`OSC_ENDPOINT_API` reste honoré : toutes les régions parlent au même hôte."""
    emulateur = discovery.client_factory(None, None, None, "http://127.0.0.1:4811/api/v1")
    a = emulateur("eu-west-2")
    assert emulateur("cloudgouv-eu-west-1") is a and emulateur(None) is a
    assert len(sdk.construits) == 1
    assert sdk.construits[0]["endpoints"].api == "http://127.0.0.1:4811/api/v1"
    assert "region" not in sdk.construits[0]


def test_rien_nest_impose_au_sdk_quand_rien_nest_donne(sdk: type[_Gateway]) -> None:
    """Le SDK lit lui-même le profil et l'environnement : un mot-clé absent le laisse faire."""
    discovery.client_factory()(None)
    assert sdk.construits == [{}]
    discovery.client_factory(profile="lab")("eu-west-2")
    assert sdk.construits[1] == {"profile": "lab", "region": "eu-west-2"}


def test_la_region_par_defaut_est_celle_du_sdk_et_son_client_est_reutilise(
    sdk: type[_Gateway],
) -> None:
    """Un `Gateway` coûte une seconde : celui qui a résolu la région la sert."""
    par_region = discovery.client_factory()
    assert discovery.resolve_regions((), par_region) == ("eu-west-2",)
    par_region("eu-west-2")
    assert len(sdk.construits) == 1


def test_les_regions_demandees_priment_et_se_dedoublonnent() -> None:
    regions = discovery.resolve_regions(("eu-west-2", "eu-west-2", "us-east-2"), lambda r: None)
    assert regions == ("eu-west-2", "us-east-2")


def test_sans_region_resolue_le_plugin_le_dit_plutot_que_de_choisir() -> None:
    class _Muet:
        def region(self) -> None:
            return None

    with pytest.raises(ValueError, match="région"):
        discovery.resolve_regions((), lambda r: _Muet())


def test_la_decouverte_agrege_et_compte() -> None:
    client = _Client(vms=[{"VmId": "i-1", "Tags": [{"Key": "Name", "Value": "web01"}]}])
    resultat, report = discovery.discover(
        lambda r: client, DiscoveryContext(regions=("eu-west-2",)), ("vm",)
    )
    assert [h.name for h in resultat.hosts] == ["web01"]
    assert report.providers == {"vm": 1} and report.api_calls == 1
    assert "hosts par provider : vm=1" in report.lines()


def test_un_produit_inconnu_est_refuse() -> None:
    with pytest.raises(ValueError, match="mars"):
        discovery.providers_for(lambda r: None, ("mars",))
    with pytest.raises(ValueError, match="mars"):
        discovery.group_axes(("mars",))


def test_les_axes_des_providers_sont_lus_sur_la_classe() -> None:
    axes = discovery.group_axes(("vm",))
    assert axes == dict(discovery.VmProvider.group_axes)


def test_en_mode_strict_une_panne_de_provider_remonte_sinon_elle_est_dite() -> None:
    class _Casse:
        name = "vm"
        group_axes: ClassVar[dict[str, str]] = {}

        def __init__(self, client_for: Any) -> None:
            pass

        def discover(self, context: DiscoveryContext) -> Any:
            raise RuntimeError("boom")

    fabriques = {"vm": _Casse}
    original = discovery._FABRIQUES
    discovery._FABRIQUES = fabriques  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError):
            discovery.discover(lambda r: None, DiscoveryContext(), ("vm",), strict=True)
        _, report = discovery.discover(lambda r: None, DiscoveryContext(), ("vm",), strict=False)
        assert report.errors == ["vm : boom"]
    finally:
        discovery._FABRIQUES = original  # type: ignore[assignment]


def test_un_refus_dauthentification_remonte_meme_hors_mode_strict() -> None:
    class _Refus(_Client):
        def ReadVms(self, **kwargs: Any) -> dict[str, Any]:
            raise AuthenticationFailed("identifiants refusés")

    with pytest.raises(AuthenticationFailed):
        discovery.discover(
            lambda r: _Refus(), DiscoveryContext(regions=("eu-west-2",)), ("vm",), strict=False
        )


def test_sans_sdk_la_fabrique_le_dit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "HAS_SDK", False)
    with pytest.raises(ImportError):
        discovery.client_factory()
