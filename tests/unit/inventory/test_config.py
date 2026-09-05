"""La configuration refuse ce qu'elle ne sait pas faire, et sa clé de cache
change avec tout ce qui change le résultat."""

from __future__ import annotations

from typing import Any

import pytest

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.config import (
    ConfigError,
    from_options,
)

#: Ce qu'un provider ajoute aux axes du cœur, sans que le cœur le nomme.
AXES_DU_PROVIDER = {"flavor": "flavor"}


def _options(**valeurs: Any) -> Any:
    def get_option(nom: str) -> Any:
        return valeurs.get(nom)

    return get_option


def test_les_defauts_donnent_une_configuration_complete() -> None:
    config = from_options(_options())
    assert config.regions == ()
    assert config.hostnames == ("tag:Name", "id")
    assert config.group_by == ("region", "subregion", "state", "tags")
    assert config.address.priority == ("public_ipv4", "private_ipv4")
    assert config.address.entry_role is None and config.address.entry_tag == "role"
    assert dict(config.api_filters) == {}


@pytest.mark.parametrize(
    ("option", "valeur", "attendu"),
    [
        ("group_by", ["couleur"], "axe"),
        ("address_priority", ["ipv5"], "famille"),
        ("hostnames", ["nom"], "source"),
        ("hostnames", ["tag:"], "source"),
        ("tags_match", "some", "tags_match"),
        ("tags", ["env"], "dictionnaire"),
        ("exclude_tags", ["env"], "dictionnaire"),
        ("filters", ["VmStateNames"], "dictionnaire"),
        ("entry_tag", "  ", "entry_tag"),
    ],
)
def test_un_nom_inconnu_est_refuse_pas_ignore(option: str, valeur: Any, attendu: str) -> None:
    """L'ignorer produirait un inventaire silencieusement différent de la demande."""
    with pytest.raises(ConfigError, match=attendu):
        from_options(_options(**{option: valeur}))


def test_les_axes_du_provider_sont_acceptes_sans_que_le_coeur_les_connaisse() -> None:
    with pytest.raises(ConfigError, match="flavor"):
        from_options(_options(group_by=["flavor"]))
    config = from_options(_options(group_by=["flavor", "region"]), AXES_DU_PROVIDER)
    assert config.group_by == ("flavor", "region")


def test_les_filtres_et_exclusions_sont_lus() -> None:
    config = from_options(
        _options(
            tags={"env": "prod", "role": None},
            states=["running"],
            exclude_tags={"managed_by": "talos"},
            exclude_ids=["i-9"],
            filters={"VmStateNames": ["running"], "Tags": ["env=prod"]},
            regions=["eu-west-2", "cloudgouv-eu-west-1"],
            entry_role="bastion",
        )
    )
    assert dict(config.filters.tags) == {"env": "prod", "role": ""}
    assert config.filters.states == ("running",)
    assert dict(config.filters.exclude_tags) == {"managed_by": "talos"}
    assert config.filters.exclude_ids == ("i-9",)
    assert dict(config.api_filters) == {"VmStateNames": ["running"], "Tags": ["env=prod"]}
    assert config.regions == ("eu-west-2", "cloudgouv-eu-west-1")
    assert config.address.entry_role == "bastion"


def test_la_cle_de_cache_change_avec_le_compte_les_filtres_et_lurl() -> None:
    """Deux comptes sans profil partageaient sinon le même parc en cache."""
    config = from_options(_options(strict=True))
    a = config.cache_fingerprint(None, "AK1|")
    b = config.cache_fingerprint(None, "AK2|")
    url = config.cache_fingerprint("http://127.0.0.1:4811/api/v1", "AK1|")
    souple = from_options(_options(strict=False)).cache_fingerprint(None, "AK1|")
    filtre = from_options(_options(filters={"VmStateNames": ["running"]})).cache_fingerprint(
        None, "AK1|"
    )
    assert len({a, b, url, souple, filtre}) == 5
    assert "AK1" not in a


def test_la_cle_de_cache_est_stable_dune_execution_a_lautre() -> None:
    options = _options(regions=["eu-west-2"], filters={"VmStateNames": ["running"]})
    assert from_options(options).cache_fingerprint(None, "x") == from_options(
        options
    ).cache_fingerprint(None, "x")
