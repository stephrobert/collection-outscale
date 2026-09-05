"""Ce que le renderer tient de lui-même, indépendamment du contrat.

`ansible-test sanity` refuse une ligne de plus de 160 caractères (pep8 E501),
mesuré par collection-exoscale sur les cinq versions d'ansible-core de sa
matrice : un en-tête de onze opérations sur une ligne en faisait 240.
"""

from __future__ import annotations

import json
from pathlib import Path

from generator.ansible.models import build_module_specs
from generator.plan import ProductPlan
from generator.renderer.modules import HEADER_WIDTH, operation_header, render_module

from .conftest import FIXTURES, LAB_COLLECTION

#: La limite qu'`ansible-test sanity` applique aux modules.
PEP8_LIMIT = 160

GOLDEN = FIXTURES / "widget" / "expected_modules"


def test_len_tete_des_operations_se_replie_sous_la_limite_de_sanity() -> None:
    identifiants = tuple(f"VeryLongOperationIdentifierNumber{i}" for i in range(30))
    lignes = operation_header(identifiants)
    assert len(lignes) > 1
    assert all(len(ligne) <= HEADER_WIDTH for ligne in lignes)
    assert all(len(ligne) <= PEP8_LIMIT for ligne in lignes)


def test_len_tete_commence_par_le_libelle_et_garde_chaque_operation_entiere() -> None:
    identifiants = tuple(f"RevertInstanceToSnapshot{i}" for i in range(12))
    lignes = operation_header(identifiants)
    assert lignes[0].startswith("# Opérations : ")
    assert all(ligne.startswith("#") for ligne in lignes)
    reconstitue = " ".join(ligne.lstrip("# ").replace("Opérations : ", "") for ligne in lignes)
    for identifiant in identifiants:
        assert identifiant in reconstitue


def test_une_seule_operation_tient_sur_une_ligne() -> None:
    assert operation_header(("ReadVms",)) == ["# Opérations : ReadVms"]


def test_le_rendu_est_celui_du_golden(widget_plan: ProductPlan, gadget_plan: ProductPlan) -> None:
    """Le golden fige ce que le renderer écrit ; un diff se lit, il ne se subit pas."""
    assert GOLDEN.is_dir(), "lancer `mise run golden:update` pour figer les modules"
    for plan in (widget_plan, gadget_plan):
        specs, _ = build_module_specs(plan, LAB_COLLECTION)
        for spec in specs:
            attendu = (GOLDEN / f"{spec.name}.py").read_text(encoding="utf-8")
            rendu = render_module(spec, source="tests/fixtures/widget/input/outscale.v1.yml")
            assert rendu == attendu, f"{spec.name} ne correspond plus au golden"


def test_le_rendu_est_deterministe(widget_plan: ProductPlan) -> None:
    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    premier = [render_module(s, source="x") for s in specs]
    second = [render_module(s, source="x") for s in specs]
    assert premier == second


def test_les_blocs_de_documentation_sont_du_yaml_valide(widget_plan: ProductPlan) -> None:
    import yaml

    specs, _ = build_module_specs(widget_plan, LAB_COLLECTION)
    for spec in specs:
        rendu = render_module(spec, source="x")
        for bloc in ("DOCUMENTATION", "EXAMPLES", "RETURN"):
            debut = rendu.index(f'{bloc} = r"""') + len(f'{bloc} = r"""')
            fin = rendu.index('"""', debut)
            assert yaml.safe_load(rendu[debut:fin]) is not None or bloc == "RETURN"


def test_le_golden_ne_porte_aucune_ligne_trop_longue() -> None:
    for chemin in sorted(Path(GOLDEN).glob("*.py")):
        longues = [
            n
            for n, ligne in enumerate(chemin.read_text().splitlines(), 1)
            if len(ligne) > PEP8_LIMIT
        ]
        assert longues == [], f"{chemin.name} : lignes {longues}"
    assert json.dumps([]) == "[]"
