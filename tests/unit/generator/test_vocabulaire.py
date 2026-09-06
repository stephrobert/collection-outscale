"""La page se nomme comme le contrat nomme ses ressources dans ses phrases.

Une ressource déduite d'un identifiant arrive en minuscules, `vm`, `nic`,
`dhcp_option` : c'est un identifiant. Collé dans une phrase, ça donnait « Manage
the settings of an Outscale vm » sur treize pages qui se veulent une référence,
là où le contrat écrit VM, NIC, DHCP, NAT et IP dans ses propres phrases.

Ces tests portent sur les contrats réels : le défaut naît de la rencontre entre
un identifiant abrégé et une phrase publiée, et le laboratoire n'en porte pas.
"""

from __future__ import annotations

import re

import pytest

from generator.ansible.models import (
    DEPRECATED_NOTICE,
    AnsibleModuleSpec,
    _ansible_markup,
    _lisible,
    build_module_specs,
)
from generator.plan import build_plan

from .conftest import LAB_COLLECTION, OUTSCALE_SPECS


def _specs(produit: str) -> dict[str, AnsibleModuleSpec]:
    plan = build_plan(produit, "v1", spec_root=OUTSCALE_SPECS)
    specs, _ = build_module_specs(plan, LAB_COLLECTION)
    return {spec.name: spec for spec in specs}


@pytest.mark.parametrize(
    ("mots", "attendu"),
    [
        ("vm", "VM"),
        ("vms", "VMs"),
        ("vm type", "VM type"),
        ("public ip ranges", "public IP ranges"),
        ("dhcp options", "DHCP options"),
        ("nat service", "NAT service"),
        ("volume", "volume"),
    ],
)
def test_les_abreviations_sortent_en_capitales_et_rien_dautre(mots: str, attendu: str) -> None:
    """Le reste des mots n'est pas capitalisé : « Outscale Volume » ne serait pas mieux."""
    assert _lisible(mots) == attendu


@pytest.mark.parametrize(
    ("produit", "module", "attendu"),
    [
        ("vm", "vm", "Manage the settings of an Outscale VM"),
        ("vm", "vm_info", "Gather information about Outscale VMs"),
        ("vm", "vm_action", "Perform an action on Outscale VMs"),
        ("nic", "nic_info", "Gather information about Outscale NICs"),
        ("dhcp_option", "dhcp_option_info", "Gather information about Outscale DHCP options"),
        ("nat_service", "nat_service_info", "Gather information about Outscale NAT services"),
        ("public_ip", "public_ip_range_info", "Gather information about Outscale public IP ranges"),
    ],
)
def test_la_phrase_courte_ecrit_la_ressource_comme_le_contrat(
    produit: str, module: str, attendu: str
) -> None:
    assert _specs(produit)[module].short_description() == attendu


def test_la_prose_entiere_dun_module_ne_porte_aucun_identifiant_abrege() -> None:
    """Pas seulement la phrase courte : la description, les notes, le retour."""
    spec = _specs("vm")["vm_action"]
    doc = spec.documentation()
    prose = [doc["short_description"], *doc["description"], *doc.get("notes", [])]
    prose += [str(o["description"]) for o in doc["options"].values()]
    prose += [str(v["description"]) for v in spec.return_documentation().values()]
    abrege = re.compile(r"\b(?:vm|Vm|vms|Vms)\b")
    marquage = re.compile(r"\b[A-Z]\([^()]*\)")
    fautives = [p for p in prose if abrege.search(marquage.sub(" ", p))]
    assert fautives == [], fautives


def test_une_barre_echappee_du_contrat_redevient_une_barre() -> None:
    """78 `\\|` dans le contrat, recopiés tels quels sur 18 modules : un tableau
    Markdown échappe la barre, une page Ansible ne le sait pas."""
    assert _ansible_markup("The type (`standard` \\| `io1`).") == "The type (C(standard) | C(io1))."
    assert _ansible_markup("a | b") == "a | b"


def test_une_option_depreciee_le_dit() -> None:
    """`UpdateVm.VmInitiatedShutdownBehavior` est déprécié depuis 1.42.0, et la
    page ne le disait pas : un lecteur bâtissait dessus."""
    spec = _specs("vm")["vm"]
    lignes = spec.option_docs["vm_initiated_shutdown_behavior"]
    assert lignes[-1] == DEPRECATED_NOTICE
    assert spec.documentation()["options"]["vm_initiated_shutdown_behavior"]["description"] == list(
        lignes
    )
