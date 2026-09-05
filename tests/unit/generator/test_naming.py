"""Les noms se traduisent par des règles courtes, lisibles sans exécuter le code."""

from __future__ import annotations

from generator.ansible.models import action_name
from generator.parser.naming import (
    option_name,
    pluralize_phrase,
    singularize,
    singularize_phrase,
    snake_case,
    split_words,
)


def test_le_camel_case_se_decoupe_en_mots() -> None:
    assert split_words("ReadVmTypes") == ["read", "vm", "types"]
    assert split_words("VmId") == ["vm", "id"]
    assert split_words("DryRun") == ["dry", "run"]
    assert snake_case("SecurityGroup") == "security_group"


def test_les_majuscules_consecutives_et_les_chiffres_restent_ensemble() -> None:
    """Mesuré : `CO2EmissionEntries`, `VRam`, `Phase1DhGroupNumbers`, `Ipv6Ranges`."""
    assert split_words("CO2EmissionEntries") == ["co2", "emission", "entries"]
    assert split_words("VRam") == ["v", "ram"]
    assert split_words("Phase1DhGroupNumbers") == ["phase1", "dh", "group", "numbers"]
    assert split_words("Ipv6Ranges") == ["ipv6", "ranges"]


def test_le_snake_et_le_kebab_se_decoupent_aussi() -> None:
    assert split_words("security_group_rules") == ["security", "group", "rules"]
    assert split_words("net-peering") == ["net", "peering"]


def test_une_option_ansible_est_en_snake_case() -> None:
    assert option_name("VmIds") == "vm_ids"
    assert option_name("BlockDeviceMappings") == "block_device_mappings"
    assert option_name("Filters") == "filters"


def test_les_mots_invariables_ne_se_depluralisent_pas() -> None:
    assert singularize("dns") == "dns"
    assert singularize("status") == "status"
    assert singularize("iops") == "iops"
    assert singularize("vms") == "vm"
    assert singularize("gpus") == "gpu"
    assert singularize("policies") == "policy"
    assert singularize("addresses") == "address"


def test_une_expression_se_singularise_mot_a_mot() -> None:
    assert singularize_phrase("vms_state") == "vm_state"
    assert singularize_phrase("public_ip_ranges") == "public_ip_range"
    assert pluralize_phrase("vm_type") == "vm types"
    assert pluralize_phrase("net_peering") == "net peerings"


def test_le_nom_dune_action_retire_les_mots_de_la_ressource() -> None:
    assert action_name("StartVms", "vm") == "start"
    assert action_name("StopVms", "vm") == "stop"
    assert action_name("AcceptNetPeering", "net_peering") == "accept"
    assert action_name("ScaleUpVmGroup", "vm_group") == "scale_up"
    assert action_name("EnableOutscaleLogin", "outscale_login") == "enable"
