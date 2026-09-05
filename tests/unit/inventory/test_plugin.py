"""Ce que le plugin sérialise, et ce qu'il rend après un aller-retour de cache.

Toute exécution passe par cette sérialisation, avec ou sans cache : ce qui n'y
survit pas n'existe pas pour l'utilisateur, même si le provider l'a produit.
"""

from __future__ import annotations

from ansible_collections.stephrobert.outscale.plugins.inventory.vm import (
    ALLOWED_SUFFIXES,
    OPTION_NAMES,
    InventoryModule,
    _plain,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.address import (
    AddressPolicy,
    select_ansible_host,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.models import (
    InventoryHost,
)


def _host() -> InventoryHost:
    return InventoryHost(
        id="i-1",
        product="vm",
        name="web01",
        region="eu-west-2",
        subregion="eu-west-2a",
        state="running",
        tags={"Name": "web01", "env": "prod"},
        public_ipv4=("171.33.0.1",),
        private_ipv4=("10.0.0.5", "10.0.0.6"),
        net_id="vpc-1",
        subnet_id="subnet-1",
        security_group_ids=("sg-1",),
        metadata={"vm_type": "tinav5.c1r1p2", "image_id": "ami-1", "keypair_name": "admin"},
        raw={"VmId": "i-1"},
    )


def test_tout_le_modele_survit_a_laller_retour() -> None:
    rendu = InventoryModule._deserialise(InventoryModule._serialise(_host()))
    assert rendu == _host()


def test_sans_reponse_brute_rien_nest_invente() -> None:
    host = InventoryHost(id="i-1", product="vm")
    assert InventoryModule._deserialise(InventoryModule._serialise(host)).raw is None


def test_ce_quun_cache_ne_sait_pas_ecrire_devient_du_texte() -> None:
    class Opaque:
        def __str__(self) -> str:
            return "objet-opaque"

    assert _plain({"a": Opaque(), "b": [Opaque()], "n": 3}) == {
        "a": "objet-opaque",
        "b": ["objet-opaque"],
        "n": 3,
    }


def test_les_hostvars_portent_de_quoi_enchainer_sur_les_modules() -> None:
    host = _host()
    variables = InventoryModule._host_variables(host, select_ansible_host(host, AddressPolicy()))
    assert variables["outscale_id"] == "i-1" and variables["outscale_region"] == "eu-west-2"
    assert variables["outscale_subregion"] == "eu-west-2a"
    assert variables["outscale_public_ipv4"] == "171.33.0.1"
    assert variables["outscale_private_ipv4"] == "10.0.0.5"
    assert variables["outscale_private_ipv4s"] == ["10.0.0.5", "10.0.0.6"]
    assert variables["outscale_tags"] == {"Name": "web01", "env": "prod"}
    assert variables["outscale_vm_type"] == "tinav5.c1r1p2"
    assert variables["outscale_image_id"] == "ami-1"
    assert variables["outscale_keypair_name"] == "admin"
    assert variables["outscale_net_id"] == "vpc-1" and variables["outscale_subnet_id"] == "subnet-1"
    assert variables["outscale_security_group_ids"] == ["sg-1"]
    assert variables["outscale_address_source"] == "public_ipv4"
    assert variables["outscale_raw"] == {"VmId": "i-1"}


def test_une_machine_sans_adresse_a_des_hostvars_nulles_pas_absentes() -> None:
    host = InventoryHost(id="i-1", product="vm")
    variables = InventoryModule._host_variables(host, select_ansible_host(host, AddressPolicy()))
    assert variables["outscale_public_ipv4"] is None and variables["outscale_private_ipv4"] is None
    assert variables["outscale_private_ipv4s"] == [] and "outscale_raw" not in variables


def test_le_fichier_dinventaire_se_reconnait_a_son_suffixe() -> None:
    assert "outscale.yml" in ALLOWED_SUFFIXES and "osc.yml" in ALLOWED_SUFFIXES
    assert "inventaire.outscale.yml".endswith(ALLOWED_SUFFIXES)
    assert not "hosts.yml".endswith(ALLOWED_SUFFIXES)


def test_le_plugin_traduit_ses_options_vers_les_noms_du_coeur() -> None:
    """Le cœur lit `exclude_ids` ; c'est le plugin qui sait que ce sont des Vm."""
    assert OPTION_NAMES == {"exclude_ids": "exclude_vm_ids"}
