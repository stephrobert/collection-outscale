"""Les groupes natifs, et l'assainissement de leurs noms."""

from __future__ import annotations

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.groups import (
    AXES,
    group_names,
    known_axes,
    sanitize_group_name,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.models import (
    InventoryHost,
)


def test_un_nom_de_groupe_reste_lisible_et_valide() -> None:
    assert sanitize_group_name("pré-prod") == "pre_prod"
    assert sanitize_group_name("tinav5.c1r1p2") == "tinav5_c1r1p2"
    assert sanitize_group_name("2024") == "_2024"
    assert sanitize_group_name("///") == "inconnu"


def test_chaque_axe_donne_ses_groupes() -> None:
    host = InventoryHost(
        id="i-1",
        product="vm",
        region="eu-west-2",
        subregion="eu-west-2a",
        state="running",
        tags={"env": "prod", "role": "web", "orphan": ""},
        net_id="vpc-1",
        subnet_id="subnet-1",
        metadata={"flavor": "tinav5.c1r1p2", "key": "admin"},
    )
    axes = ("region", "subregion", "state", "tags", "net", "subnet", "flavor", "keypair")
    noms = group_names(host, axes, {"flavor": "flavor", "keypair": "key"})
    assert noms == (
        "osc_flavor_tinav5_c1r1p2",
        "osc_keypair_admin",
        "osc_net_vpc_1",
        "osc_region_eu_west_2",
        "osc_state_running",
        "osc_subnet_subnet_1",
        "osc_subregion_eu_west_2a",
        "osc_tag_env_prod",
        "osc_tag_orphan",
        "osc_tag_role_web",
    )


def test_un_axe_sans_valeur_ne_cree_pas_de_groupe_vide() -> None:
    host = InventoryHost(id="i-1", product="vm")
    assert group_names(host, ("region", "subregion", "state", "tags", "net", "subnet")) == ()
    assert group_names(host, ("flavor",), {"flavor": "flavor"}) == ()


def test_les_axes_connus_sont_ceux_du_coeur_puis_ceux_du_provider() -> None:
    assert known_axes() == AXES
    assert known_axes({"z": "z", "a": "a"}) == (*AXES, "a", "z")
