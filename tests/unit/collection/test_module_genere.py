"""Un module généré se vérifie en l'important et en construisant son argument_spec.

Le compiler ne prouve rien : `ast.parse` accepte un module dont une
substitution a supprimé une variable. Ici chaque module est importé, son
`AnsibleModule` construit avec des arguments réels, et le SDK installé
interrogé sur chaque action que le module appelle.
"""

from __future__ import annotations

import ast
import functools
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from ansible.module_utils import basic

from generator.ansible.collection import load_collection

REPO_ROOT = Path(__file__).resolve().parents[3]
COLLECTION = load_collection()
MODULES = sorted(COLLECTION.modules_dir.glob("*.py"))

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: Les paramètres communs, portés par le runtime : ils ne sont pas exigés.
COMMUNS = {"access_key", "secret_key", "region", "profile", "api_url", "wait", "wait_timeout"}


def _import(path: Path) -> ModuleType:
    name = f"ansible_collections.{COLLECTION.fqcn}.plugins.modules.{path.stem}"
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def _arguments(**extra: object) -> None:
    payload = {"ANSIBLE_MODULE_ARGS": {"region": "eu-west-2", **extra}}
    basic._ANSIBLE_ARGS = json.dumps(payload).encode()
    # ansible-core 2.19 et plus exige un profil de sérialisation à côté des
    # arguments ; `legacy` est celui que le débogage d'un module pose par défaut.
    basic._ANSIBLE_PROFILE = "legacy"


def _valeur_acceptable(entry: dict[str, object]) -> object:
    """Une valeur que l'argument_spec accepte : du type déclaré, ou un choix du contrat."""
    choices = entry.get("choices")
    if choices:
        return choices[0]
    return {"int": 1, "float": 1.0, "bool": True, "list": ["x"], "dict": {}}.get(
        str(entry.get("type", "str")), "x"
    )


@functools.lru_cache(maxsize=1)
def _gateway() -> Any:
    """Le SDK, construit une fois : il charge son contrat en 1,3 s, mesuré."""
    from osc_sdk_python import Gateway

    return Gateway(access_key="x", secret_key="y", region="eu-west-2")


@pytest.fixture(autouse=True)
def _reset_ansible_args() -> None:
    basic._ANSIBLE_ARGS = None
    basic._ANSIBLE_PROFILE = None


def test_des_modules_ont_ete_generes() -> None:
    assert MODULES, "lancer `mise run generate` avant les tests de la collection"


@pytest.mark.parametrize("path", MODULES, ids=[p.stem for p in MODULES])
def test_le_module_simporte_et_son_argument_spec_est_accepte(path: Path) -> None:
    module = _import(path)
    extra: dict[str, object] = {}
    if hasattr(module.MODULE, "actions"):
        first = module.MODULE.actions[0]
        extra["action"] = first.name
        for option in module.REQUIRED_IF:
            if option[1] == first.name:
                for name in option[2]:
                    extra.setdefault(name, _valeur_acceptable(module.ARGUMENT_SPEC[name]))
    for name, entry in module.ARGUMENT_SPEC.items():
        if entry.get("required") and name not in extra and name not in COMMUNS:
            extra[name] = _valeur_acceptable(entry)
    _arguments(**extra)
    ansible_module = basic.AnsibleModule(
        argument_spec=module.ARGUMENT_SPEC,
        required_if=module.REQUIRED_IF,
        supports_check_mode=True,
    )
    assert ansible_module.params["region"] == "eu-west-2"


@pytest.mark.parametrize("path", MODULES, ids=[p.stem for p in MODULES])
def test_un_module_daction_refuse_une_action_sans_son_selecteur(path: Path) -> None:
    module = _import(path)
    if not hasattr(module.MODULE, "actions"):
        pytest.skip("module d'information")
    if module.MODULE.selector is None:
        pytest.skip("aucun sélecteur commun")
    _arguments(action=module.MODULE.actions[0].name)
    with pytest.raises(SystemExit):
        basic.AnsibleModule(
            argument_spec=module.ARGUMENT_SPEC,
            required_if=module.REQUIRED_IF,
            supports_check_mode=True,
        )


@pytest.mark.parametrize("path", MODULES, ids=[p.stem for p in MODULES])
def test_le_sdk_installe_connait_chaque_action_du_module(path: Path) -> None:
    """Le SDK embarque le contrat : s'il ne connaît pas une action, l'un des deux a dérivé."""
    gateway = _gateway()
    module = _import(path)
    spec = module.MODULE
    operations = [
        op for op in (getattr(spec, "operation", None), getattr(spec, "read_operation", None)) if op
    ]
    operations.extend(action.operation for action in getattr(spec, "actions", ()))
    assert operations, f"{path.stem} ne déclare aucune opération"
    for operation in operations:
        assert operation.method in gateway.gateway_structure, (
            f"{operation.id} : {operation.method} absent du SDK"
        )
        # Chaque nom de contrat que le module envoie est un paramètre que le
        # SDK accepte pour cette action.
        connus = set(gateway.gateway_structure[operation.method])
        assert set(operation.body_params.values()) <= connus, (
            f"{operation.id} : {set(operation.body_params.values()) - connus} inconnus du SDK"
        )


@pytest.mark.parametrize("path", MODULES, ids=[p.stem for p in MODULES])
def test_le_module_ne_porte_aucune_logique(path: Path) -> None:
    """Il ne définit que `main`, et `main` ne contient ni condition ni boucle."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fonctions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert [f.name for f in fonctions] == ["main"]
    for node in ast.walk(fonctions[0]):
        assert not isinstance(node, (ast.If, ast.For, ast.While, ast.Try)), (
            "une décision s'est glissée"
        )


@pytest.mark.parametrize("path", MODULES, ids=[p.stem for p in MODULES])
def test_aucune_ligne_dun_module_ne_depasse_la_limite_de_sanity(path: Path) -> None:
    """`ansible-test sanity` refuse une ligne de plus de 160 caractères (pep8 E501)."""
    trop_longues = [
        (numero, len(ligne))
        for numero, ligne in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if len(ligne) > 160
    ]
    assert trop_longues == [], f"{path.name} : lignes trop longues {trop_longues}"
