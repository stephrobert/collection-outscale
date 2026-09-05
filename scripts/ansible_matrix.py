"""La matrice ansible-core de la CI, dérivée de ce que la collection déclare.

`meta/runtime.yml` promet `requires_ansible: ">=2.17.0"`. Une version promise
et jamais éprouvée est une promesse sans preuve, donc la CI éprouve chaque
version mineure de la borne basse jusqu'à celle que le verrou porte. Chez
collection-exoscale, cette liste était tenue à la main à trois endroits
(`ci.yml`, le ruleset, un commentaire de `runtime.yml`) sans mécanisme de
cohérence. Ici elle se dérive, et `--check` exige que `ci.yml` et le ruleset
la portent telle quelle.

    python scripts/ansible_matrix.py            la matrice, une plage par ligne
    python scripts/ansible_matrix.py --check    échoue si ci.yml ou le ruleset diffèrent
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

from generator.ansible.collection import load_collection

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-dev.lock"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RULESET = ROOT / ".github" / "rulesets" / "main.json"

#: Le nom du job de la matrice, tel que le ruleset le cite comme contexte.
JOB_NAME = "collection (ansible-core {plage})"

_REQUIRES = re.compile(r">=\s*(\d+)\.(\d+)")
_LOCKED = re.compile(r"^ansible-core==(\d+)\.(\d+)\.", re.MULTILINE)


class MatrixError(RuntimeError):
    """La matrice ne peut pas être dérivée, ou la CI ne la porte pas."""


def matrix(requires_ansible: str, locked: tuple[int, int]) -> list[str]:
    """Les plages, de la borne basse de `requires_ansible` à la mineure du verrou.

    Fonction pure, pour que la dérivation se teste sans fichier.
    """
    borne = _REQUIRES.search(requires_ansible)
    if borne is None:
        raise MatrixError(f"requires_ansible={requires_ansible!r} ne porte pas de borne `>=`")
    major, minor = int(borne.group(1)), int(borne.group(2))
    if (major, minor) > locked:
        raise MatrixError(
            f"requires_ansible exige {major}.{minor}, et le verrou porte "
            f"{locked[0]}.{locked[1]} : la borne n'a jamais été éprouvée"
        )
    if major != locked[0]:
        raise MatrixError("la matrice ne sait dériver qu'au sein d'une même version majeure")
    return [f">={major}.{m},<{major}.{m + 1}" for m in range(minor, locked[1] + 1)]


def declared() -> str:
    runtime = load_collection().path / "meta" / "runtime.yml"
    document = yaml.safe_load(runtime.read_text(encoding="utf-8")) or {}
    valeur = document.get("requires_ansible")
    if not valeur:
        raise MatrixError(f"{runtime} ne déclare pas requires_ansible")
    return str(valeur)


def locked_version() -> tuple[int, int]:
    trouve = _LOCKED.search(LOCK.read_text(encoding="utf-8"))
    if trouve is None:
        raise MatrixError(f"{LOCK.name} ne verrouille pas ansible-core")
    return int(trouve.group(1)), int(trouve.group(2))


def expected() -> list[str]:
    return matrix(declared(), locked_version())


def check(plages: list[str]) -> list[str]:
    """Les écarts entre la matrice dérivée et ce que la CI porte."""
    ecarts: list[str] = []
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    portee = workflow["jobs"]["collection"]["strategy"]["matrix"]["ansible"]
    if list(portee) != plages:
        ecarts.append(f"ci.yml porte {portee}, la matrice dérivée est {plages}")
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    contextes = {
        check["context"]
        for rule in ruleset["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    }
    attendus = {JOB_NAME.format(plage=plage) for plage in plages}
    manquants = sorted(attendus - contextes)
    en_trop = sorted(c for c in contextes if c.startswith("collection (") and c not in attendus)
    if manquants:
        ecarts.append(f"le ruleset n'exige pas {manquants}")
    if en_trop:
        ecarts.append(f"le ruleset exige {en_trop}, que la matrice ne porte pas")
    return ecarts


def main(argv: list[str]) -> int:
    plages = expected()
    if "--check" not in argv[1:]:
        print("\n".join(plages))
        return 0
    ecarts = check(plages)
    if ecarts:
        for ecart in ecarts:
            print(f"erreur : {ecart}", file=sys.stderr)
        print(
            "La matrice se dérive de meta/runtime.yml et du verrou ; ci.yml et "
            ".github/rulesets/main.json doivent la porter telle quelle.",
            file=sys.stderr,
        )
        return 1
    print(f"matrice ansible-core : {', '.join(plages)} ; ci.yml et le ruleset la portent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except MatrixError as erreur:
        print(f"erreur : {erreur}", file=sys.stderr)
        raise SystemExit(1) from erreur
