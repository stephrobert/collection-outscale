"""Le mapping traduit sans deviner : un type inconnu remonte, un secret se masque."""

from __future__ import annotations

import pytest

from generator.ansible.mapping import (
    REQUEST_FLAGS,
    UnmappedType,
    argument_spec_entry,
    is_sensitive,
    module_name,
    sdk_method,
)
from generator.ir.enums import ApiType, OperationKind, ParameterLocation
from generator.ir.models import ApiParameter


def _parameter(name: str, type: ApiType, **kwargs: object) -> ApiParameter:
    return ApiParameter(
        name=name, type=type, required=False, location=ParameterLocation.BODY, **kwargs
    )  # type: ignore[arg-type]


def test_le_nom_du_module_ne_porte_jamais_de_verbe() -> None:
    assert module_name("vm", "vm", OperationKind.INFO) == "vm_info"
    assert module_name("vm", "vm", OperationKind.ACTION) == "vm_action"
    assert module_name("vm", "vm", OperationKind.MANAGE) == "vm"
    assert module_name("vm", "vm", OperationKind.LIFECYCLE) is None


def test_le_produit_nest_pas_redouble_dans_le_nom_du_module() -> None:
    """`Vm.ReadVmTypes` donnerait `vm_vm_type_info` : le nom est la ressource seule."""
    assert module_name("vm", "vm_type", OperationKind.INFO) == "vm_type_info"
    assert module_name("load_balancer", "load_balancer", OperationKind.INFO) == "load_balancer_info"
    assert module_name("net_peering", "net_peering", OperationKind.ACTION) == "net_peering_action"


def test_une_ressource_qui_ne_commence_pas_par_le_produit_garde_le_prefixe() -> None:
    """`Vm.ReadAdminPassword` a besoin de dire d'où il vient, et `vmx` n'est pas `vm_`."""
    assert module_name("vm", "admin_password", OperationKind.INFO) == "vm_admin_password_info"
    assert module_name("vm", "vmx_thing", OperationKind.INFO) == "vm_vmx_thing_info"


def test_la_methode_du_sdk_est_loperation_id() -> None:
    assert sdk_method("StartVms") == "StartVms"
    assert sdk_method("ReadVms") == "ReadVms"


def test_required_du_contrat_devient_required_de_largument_spec() -> None:
    entry = argument_spec_entry(
        ApiParameter(
            name="VmIds",
            type=ApiType.ARRAY,
            required=True,
            location=ParameterLocation.BODY,
            item_type=ApiType.STRING,
        )
    )
    assert entry == {"type": "list", "required": True, "elements": "str"}


def test_un_enum_devient_des_choix() -> None:
    entry = argument_spec_entry(
        _parameter("BootMode", ApiType.ENUM, enum_values=("uefi", "legacy"))
    )
    assert entry == {"type": "str", "choices": ["uefi", "legacy"]}


def test_un_objet_devient_un_dict() -> None:
    entry = argument_spec_entry(_parameter("Filters", ApiType.OBJECT, properties=("VmIds",)))
    assert entry == {"type": "dict"}


def test_un_champ_sensible_recoit_no_log() -> None:
    assert is_sensitive(_parameter("Password", ApiType.STRING)) is True
    assert argument_spec_entry(_parameter("SecretKey", ApiType.STRING))["no_log"] is True


def test_un_identifiant_ou_un_nom_nest_jamais_le_secret_quil_designe() -> None:
    """`KeypairName` désigne une clé, `AccessKeyId` désigne une clé d'accès.

    Le contrat 1.42.0 ne porte aucun identifiant dont le nom contienne un
    fragment sensible ; `ClientTokenId` est synthétique, et c'est lui qui
    mesure la garde : sans elle, `token` le masquerait. `KeypairName` seul
    passait avec ou sans la règle, et la falsification l'a dit.
    """
    assert is_sensitive(_parameter("ClientTokenId", ApiType.STRING)) is False
    assert is_sensitive(_parameter("PasswordPolicyName", ApiType.STRING)) is False
    assert is_sensitive(_parameter("KeypairName", ApiType.STRING)) is False
    assert is_sensitive(_parameter("AccessKeyId", ApiType.STRING)) is False
    assert is_sensitive(_parameter("AdminPassword", ApiType.STRING)) is True


def test_un_nom_que_sanity_soupconne_sans_etre_un_secret_le_dit_explicitement() -> None:
    """`validate-modules` refuse tout nom qui ressemble à un secret sans `no_log` explicite."""
    assert argument_spec_entry(_parameter("KeypairName", ApiType.STRING)) == {
        "type": "str",
        "no_log": False,
    }
    assert argument_spec_entry(_parameter("VmType", ApiType.STRING)) == {"type": "str"}


def test_un_type_inconnu_leve_plutot_que_de_devenir_une_chaine() -> None:
    with pytest.raises(UnmappedType):
        argument_spec_entry(_parameter("Name", ApiType.UNKNOWN))


def test_les_drapeaux_de_requete_ne_sont_pas_des_options() -> None:
    """`DryRun`, `NextPageToken` et `ResultsPerPage` sont l'affaire du runtime."""
    assert {"dry_run", "next_page_token", "results_per_page"} == REQUEST_FLAGS
