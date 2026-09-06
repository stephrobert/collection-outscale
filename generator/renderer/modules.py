"""Rendu des modules Ansible depuis le modèle intermédiaire.

Le renderer n'a qu'une responsabilité : **écrire**. Toute décision est déjà
prise dans `generator/ansible/models.py`, et le template ne contient aucun test
autre qu'une présence de valeur.

Deux propriétés sont tenues ici et vérifiées par un test :

* **le rendu est déterministe.** Les littéraux Python et les blocs YAML sont
  produits par ce fichier, pas par `repr()` ni par un `json.dumps` dont l'ordre
  dépendrait d'un dictionnaire ;
* **rien n'est rendu que le modèle n'ait décidé.**
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from generator.ansible.models import ActionBinding, AnsibleModuleSpec, OperationBinding
from generator.ir.enums import OperationKind

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"
MODULE_TEMPLATE = "module.py.j2"

#: Largeur de repli des blocs YAML.
YAML_WIDTH = 88

#: Marque qu'un fichier est produit par le générateur.
GENERATED_HEADER = "# This file is generated.\n# Do not edit manually."

#: Longueur au-delà de laquelle un littéral passe à la ligne.
INLINE_BUDGET = 88

#: Largeur de repli de l'en-tête `# Opérations : ...`. `ansible-test sanity`
#: refuse une ligne de plus de 160 caractères (pep8 E501), mesuré sur
#: collection-exoscale ; replié bien en deçà pour qu'un lecteur n'ait pas à
#: faire défiler.
HEADER_WIDTH = 100


class RenderError(ValueError):
    """Le modèle ne peut pas être rendu tel quel."""


def render_module(spec: AnsibleModuleSpec, *, source: str) -> str:
    """Rend le fichier d'un module, prêt à être écrit sur disque."""
    template = _environment().get_template(MODULE_TEMPLATE)
    rendered = template.render(
        generated_header=GENERATED_HEADER,
        authors=", ".join(spec.collection.authors) or spec.collection.fqcn,
        source=source,
        operation_lines=operation_header(spec.operation_ids),
        documentation=_yaml_block(spec.documentation()),
        examples=_yaml_block(spec.examples_documentation()),
        returns=_yaml_block(spec.return_documentation()),
        module_utils_import=spec.collection.module_utils_import,
        runtime_imports=_runtime_imports(spec),
        common_argument_specs=_common_argument_specs(spec),
        argument_spec=python_literal(spec.argument_spec()),
        required_if=python_literal([list(item) for item in spec.required_if()]),
        module_literal=_module_literal(spec),
        run_call=_run_call(spec),
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def operation_header(operation_ids: tuple[str, ...]) -> list[str]:
    """Les lignes `# Opérations : ...` de l'en-tête, repliées à `HEADER_WIDTH`."""
    prefix = "# Opérations : "
    continuation = "#" + " " * (len(prefix) - 1)
    return textwrap.wrap(
        ", ".join(operation_ids),
        width=HEADER_WIDTH,
        initial_indent=prefix,
        subsequent_indent=continuation,
        break_long_words=False,
        break_on_hyphens=False,
    )


def write_modules(
    specs: tuple[AnsibleModuleSpec, ...],
    output_dir: Path,
    *,
    source: str,
) -> list[Path]:
    """Écrit les modules, et rend les chemins produits, triés."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in sorted(specs, key=lambda item: item.name):
        target = output_dir / f"{spec.name}.py"
        target.write_text(render_module(spec, source=source), encoding="utf-8")
        written.append(target)
    return written


_RUN_FUNCTIONS: dict[OperationKind, str] = {
    OperationKind.INFO: "run_info_module",
    OperationKind.ACTION: "run_action_module",
    OperationKind.MANAGE: "run_manage_module",
}

_SPEC_CLASSES: dict[OperationKind, str] = {
    OperationKind.INFO: "InfoModule",
    OperationKind.ACTION: "ActionModule",
    OperationKind.MANAGE: "ManageModule",
}


def _runtime_imports(spec: AnsibleModuleSpec) -> list[str]:
    noms = {
        "Operation",
        _SPEC_CLASSES[spec.kind],
        _RUN_FUNCTIONS[spec.kind],
        "outscale_argument_spec",
    }
    if spec.kind is OperationKind.ACTION:
        noms.add("Action")
    if spec.waitable:
        noms.add("outscale_waitable_argument_spec")
    return sorted(noms)


def _common_argument_specs(spec: AnsibleModuleSpec) -> list[str]:
    appels = ["outscale_argument_spec()"]
    if spec.waitable:
        appels.append("outscale_waitable_argument_spec()")
    return appels


def _run_call(spec: AnsibleModuleSpec) -> str:
    return f"{_RUN_FUNCTIONS[spec.kind]}(module, MODULE)"


def _module_literal(spec: AnsibleModuleSpec) -> str:
    if spec.kind is OperationKind.ACTION:
        return _action_module_literal(spec)
    if spec.kind is OperationKind.MANAGE:
        return _manage_module_literal(spec)
    return _info_module_literal(spec)


def _info_module_literal(spec: AnsibleModuleSpec) -> str:
    if spec.operation is None:
        raise RenderError(f"{spec.name} : aucune opération à déclarer")
    lines = [
        "InfoModule(",
        f"    resource={quote(spec.resource)},",
        f"    operation={_operation_literal(spec.operation, indent=4)},",
        ")",
    ]
    return "\n".join(lines)


def _action_module_literal(spec: AnsibleModuleSpec) -> str:
    if not spec.actions:
        raise RenderError(f"{spec.name} : module d'action sans action")
    lines = ["ActionModule(", f"    resource={quote(spec.resource)},"]
    selector = quote(spec.selector) if spec.selector is not None else "None"
    lines.append(f"    selector={selector},")
    lines.append("    actions=(")
    for action in spec.actions:
        lines.append(f"        {_action_literal(action, indent=8)},")
    lines.append("    ),")
    if spec.state_field is not None:
        lines.append(f"    state_field={quote(spec.state_field)},")
    if spec.read_operation is not None:
        lines.append(f"    read_operation={_operation_literal(spec.read_operation, indent=4)},")
    if spec.read_filter is not None:
        lines.append(f"    read_filter={quote(spec.read_filter)},")
    if spec.read_id_field is not None:
        lines.append(f"    read_id_field={quote(spec.read_id_field)},")
    lines.append(")")
    return "\n".join(lines)


def _manage_module_literal(spec: AnsibleModuleSpec) -> str:
    if spec.update_operation is None or spec.read_operation is None:
        raise RenderError(f"{spec.name} : module de gestion d'état sans écriture ou sans lecture")
    lines = [
        "ManageModule(",
        f"    resource={quote(spec.resource)},",
        f"    selector={quote(spec.selector or '')},",
        f"    operation={_operation_literal(spec.update_operation, indent=4)},",
        f"    read_operation={_operation_literal(spec.read_operation, indent=4)},",
        f"    read_filter={quote(spec.read_filter or '')},",
    ]
    if spec.read_id_field is not None:
        lines.append(f"    read_id_field={quote(spec.read_id_field)},")
    lines.append(f"    compare={python_literal(spec.compare, indent=4)},")
    lines.append(")")
    return "\n".join(lines)


def _action_literal(action: ActionBinding, *, indent: int) -> str:
    pad = " " * indent
    inner = " " * (indent + 4)
    lines = ["Action(", f"{inner}name={quote(action.name)},"]
    lines.append(f"{inner}operation={_operation_literal(action.operation, indent=indent + 4)},")
    if action.expected_state is not None:
        lines.append(f"{inner}expected_state={quote(action.expected_state)},")
    if action.always_acts:
        lines.append(f"{inner}always=True,")
    lines.append(pad + ")")
    return "\n".join(lines)


def _operation_literal(operation: OperationBinding, *, indent: int) -> str:
    """Rend un appel `Operation(...)`, champs par défaut omis."""
    pad = " " * indent
    inner = " " * (indent + 4)
    fields: list[tuple[str, Any]] = [
        ("id", operation.id),
        ("method", operation.method),
        ("body_params", operation.body_params),
    ]
    if operation.payload_field is not None:
        fields.append(("payload_field", operation.payload_field))
    if operation.is_list:
        fields.append(("is_list", True))
    if operation.page_token is not None:
        fields.append(("page_token", operation.page_token))
    lines = ["Operation("]
    for name, value in fields:
        lines.append(f"{inner}{name}={python_literal(value, indent=indent + 4)},")
    lines.append(pad + ")")
    return "\n".join(lines)


def _environment() -> Environment:
    """`StrictUndefined` : une variable mal orthographiée fait échouer le rendu.

    L'échappement est désactivé, et c'est délibéré : la sortie est du code
    Python écrit sur disque, jamais du HTML servi à un navigateur. Il se
    déclare par `select_autoescape` sans aucune extension activée plutôt que
    par `autoescape=False` : c'est la forme que CodeQL
    (`py/jinja2/autoescape-false`) lit comme une décision et non comme un
    oubli.
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=select_autoescape(
            enabled_extensions=(),
            disabled_extensions=("j2",),
            default_for_string=False,
            default=False,
        ),
    )


class _SansAncre(yaml.SafeDumper):
    """Un sérialiseur qui n'écrit jamais d'ancre YAML.

    **Un exemple se copie tâche par tâche.** La tâche d'écriture d'un module de
    gestion d'état et sa simulation partagent leurs paramètres : `safe_dump`
    écrivait `vm_id: &id001` à la première et `vm_id: *id001` à la seconde, du
    YAML valide que personne ne peut copier séparément, et dont la seconde
    tâche ne dit plus ce qu'elle envoie. Rendre une valeur deux fois coûte
    quelques octets ; une page publiée qu'on ne peut pas copier coûte le
    service qu'elle est censée rendre.
    """

    def ignore_aliases(self, data: Any) -> bool:
        return True


#: Largeurs de repli quand un bloc porte une ligne que sanity refuserait.
#:
#: L'émetteur YAML ne coupe **avant** un mot que si la colonne dépasse déjà la
#: largeur : un jeton long qui suit une ligne courte s'y colle, et un lien du
#: contrat de 145 caractères (mesuré, le plus long) posé après « Physical
#: Zones, » a fait 186 caractères sur `subregion_info`. Une largeur plus
#: étroite force la coupure avant le jeton, à condition d'être plus courte que
#: ce qui le précède sur la ligne ; le bloc entier se resserre, ce qui coûte
#: des lignes et jamais un refus. Sur le contrat 1.42.0, 64 suffit.
YAML_WIDTHS: tuple[int, ...] = (YAML_WIDTH, 64, 48, 32, 24, 16)

#: La limite qu'`ansible-test sanity` applique à chaque ligne d'un module.
SANITY_LINE_LIMIT = 160


def _yaml_block(payload: Any) -> str:
    """Sérialise un bloc de documentation en YAML, sans réordonner les clés."""
    for width in YAML_WIDTHS:
        text = yaml.dump(
            payload,
            Dumper=_SansAncre,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=width,
        )
        if '"""' in text:
            raise RenderError("un bloc de documentation contient une triple quote")
        if all(len(ligne) <= SANITY_LINE_LIMIT for ligne in text.splitlines()):
            return text.rstrip("\n")
    trop_longue = max(text.splitlines(), key=len)
    raise RenderError(
        f"un bloc de documentation porte une ligne de {len(trop_longue)} caractères, que "
        f"sanity refuse au-delà de {SANITY_LINE_LIMIT} : {trop_longue[:80]!r}"
    )


def python_literal(value: Any, *, indent: int = 0) -> str:
    """Rend une valeur Python en littéral déterministe et relisible."""
    pad = " " * indent
    inner = " " * (indent + 4)

    if isinstance(value, dict):
        if not value:
            return "{}"
        inline = _inline_literal(value)
        if inline is not None and indent + len(inline) <= INLINE_BUDGET:
            return inline
        lines = ["{"]
        for key, item in value.items():
            lines.append(f"{inner}{quote(str(key))}: {python_literal(item, indent=indent + 4)},")
        lines.append(pad + "}")
        return "\n".join(lines)

    if isinstance(value, (list, tuple)):
        opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
        if not value:
            return f"{opening}{closing}"
        inline = _inline_literal(value)
        if inline is not None and indent + len(inline) <= INLINE_BUDGET:
            return inline
        lines = [opening]
        for item in value:
            lines.append(f"{inner}{python_literal(item, indent=indent + 4)},")
        lines.append(pad + closing)
        return "\n".join(lines)

    return _scalar_literal(value)


def _scalar_literal(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    return quote(str(value))


def _inline_literal(value: Any) -> str | None:
    if isinstance(value, dict):
        if not all(_is_scalar(item) for item in value.values()):
            return None
        body = ", ".join(
            f"{quote(str(key))}: {_scalar_literal(item)}" for key, item in value.items()
        )
        return "{" + body + "}"
    if not all(_is_scalar(item) for item in value):
        return None
    body = ", ".join(_scalar_literal(item) for item in value)
    if isinstance(value, tuple) and len(value) == 1:
        return f"({body},)"
    opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
    return f"{opening}{body}{closing}"


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def quote(text: str) -> str:
    """Met une chaîne entre guillemets, à la manière de `ruff format`."""
    if '"' in text and "'" not in text:
        return "'" + text.replace("\\", "\\\\") + "'"
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
