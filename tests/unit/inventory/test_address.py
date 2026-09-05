"""Le choix de `ansible_host`, et l'explication de ce choix."""

from __future__ import annotations

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.address import (
    AddressPolicy,
    select_ansible_host,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.models import (
    InventoryHost,
)


def _host(**champs: object) -> InventoryHost:
    return InventoryHost(id="i-1", product="vm", **champs)  # type: ignore[arg-type]


def test_lordre_des_familles_decide() -> None:
    host = _host(public_ipv4=("171.33.0.1",), private_ipv4=("10.0.0.5",))
    assert select_ansible_host(host, AddressPolicy()).address == "171.33.0.1"
    privee = AddressPolicy(priority=("private_ipv4", "public_ipv4"))
    assert select_ansible_host(host, privee).address == "10.0.0.5"


def test_la_famille_absente_est_sautee_pour_la_suivante() -> None:
    host = _host(private_ipv4=("10.0.0.5",))
    choix = select_ansible_host(host, AddressPolicy())
    assert (choix.address, choix.source) == ("10.0.0.5", "private_ipv4")


def test_la_selection_dit_dou_vient_ladresse_et_par_quelle_regle() -> None:
    host = _host(public_ipv4=("171.33.0.1",))
    choix = select_ansible_host(host, AddressPolicy())
    assert (choix.source, choix.rule) == ("public_ipv4", "address_priority")
    assert "171.33.0.1" in choix.explain("web01") and "public_ipv4" in choix.explain("web01")


def test_le_point_dentree_prend_le_public_et_les_autres_le_prive() -> None:
    """L'idée du plugin antérieur : un bastion joint de dehors, le reste derrière."""
    politique = AddressPolicy(entry_role="bastion")
    bastion = _host(
        tags={"role": "bastion"}, public_ipv4=("171.33.0.1",), private_ipv4=("10.0.0.1",)
    )
    web = _host(tags={"role": "web"}, public_ipv4=("171.33.0.2",), private_ipv4=("10.0.0.2",))
    assert select_ansible_host(bastion, politique).address == "171.33.0.1"
    assert select_ansible_host(web, politique).address == "10.0.0.2"
    assert "point d'entrée" in select_ansible_host(bastion, politique).rule


def test_derriere_le_point_dentree_sans_prive_on_se_rabat_sur_le_public() -> None:
    politique = AddressPolicy(entry_role="bastion")
    seul = _host(tags={"role": "web"}, public_ipv4=("171.33.0.2",))
    assert select_ansible_host(seul, politique).address == "171.33.0.2"


def test_le_tag_du_role_est_configurable() -> None:
    politique = AddressPolicy(entry_role="edge", entry_tag="tier")
    edge = _host(tags={"tier": "edge"}, public_ipv4=("171.33.0.1",), private_ipv4=("10.0.0.1",))
    assert select_ansible_host(edge, politique).address == "171.33.0.1"


def test_aucune_adresse_est_un_resultat_pas_une_erreur() -> None:
    choix = select_ansible_host(_host(), AddressPolicy())
    assert not choix.found
    assert choix.considered == ("public_ipv4", "private_ipv4")
    assert "aucune adresse" in choix.explain("web01")


def test_une_famille_inconnue_est_ignoree_par_la_politique() -> None:
    assert AddressPolicy(priority=("private_ipv4", "mars")).families() == ("private_ipv4",)
