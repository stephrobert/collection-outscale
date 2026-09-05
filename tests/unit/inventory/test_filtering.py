"""Le filtrage local, sur les tags, les états et les identifiants."""

from __future__ import annotations

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.filtering import (
    Filters,
    keep,
)

TAGS = {"env": "prod", "role": "web"}


def test_any_garde_une_machine_qui_porte_un_des_tags() -> None:
    garde, _ = keep("i-1", TAGS, "running", Filters(tags={"env": "prod", "tier": "db"}))
    assert garde


def test_all_exige_tous_les_tags_et_nomme_les_manquants() -> None:
    garde, raison = keep(
        "i-1", TAGS, "running", Filters(tags={"env": "prod", "tier": "db"}, tags_match="all")
    )
    assert not garde and "tier" in raison


def test_une_valeur_vide_veut_dire_la_cle_existe() -> None:
    assert keep("i-1", TAGS, None, Filters(tags={"role": ""}))[0]
    assert not keep("i-1", {"env": "prod"}, None, Filters(tags={"role": ""}))[0]


def test_une_valeur_differente_ne_correspond_pas() -> None:
    garde, raison = keep("i-1", TAGS, None, Filters(tags={"env": "staging"}))
    assert not garde and "env" in raison


def test_letat_filtre() -> None:
    assert not keep("i-1", TAGS, "stopped", Filters(states=("running",)))[0]
    assert keep("i-1", TAGS, "running", Filters(states=("running",)))[0]


def test_une_exclusion_par_tag_lemporte_sur_tout() -> None:
    garde, raison = keep(
        "i-1", TAGS, "running", Filters(tags={"env": "prod"}, exclude_tags={"role": "web"})
    )
    assert not garde and "exclue" in raison
    assert not keep("i-1", TAGS, "running", Filters(exclude_tags={"role": ""}))[0]


def test_une_exclusion_par_identifiant_lemporte_sur_tout() -> None:
    garde, raison = keep(
        "i-9", TAGS, "running", Filters(tags={"env": "prod"}, exclude_ids=("i-9",))
    )
    assert not garde and "identifiant" in raison
    assert keep("i-1", TAGS, "running", Filters(exclude_ids=("i-9",)))[0]


def test_sans_filtre_tout_est_retenu_et_dit() -> None:
    assert keep("i-1", {}, None, Filters()) == (True, "retenue")
