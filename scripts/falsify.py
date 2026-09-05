"""Prouve qu'un test échoue quand la garde qu'il mesure disparaît.

Un test qui passe ne prouve rien à lui seul : il peut affirmer quelque chose
qui était déjà vrai. Ce harnais neutralise une garde dans une **copie du dépôt
hors de l'arbre de travail**, lance le seul test censé la mesurer, et exige
qu'il rougisse.

Les mutations sont déclarées dans `tests/falsify/specs.json`, à côté de la
garde qu'elles neutralisent.

    python scripts/falsify.py              # rejoue toutes les mutations
    python scripts/falsify.py no_log       # une seule, par son nom
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "tests" / "falsify" / "specs.json"

#: Ce qui n'a pas à être copié pour lancer les tests.
IGNORED = shutil.ignore_patterns(
    ".git",
    ".venv",
    "build",
    "__pycache__",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # Le fournisseur Terraform téléchargé pèse 51 Mo, mesuré : le copier
    # cinquante fois faisait de la falsification une tâche de dix minutes.
    ".terraform",
    "*.tfstate",
    "*.tfstate.*",
)


@dataclass(frozen=True)
class Mutation:
    """Une garde, la façon de la neutraliser, et le test qui doit le voir."""

    name: str
    file: str
    find: str
    replace: str
    test: str
    why: str


@dataclass(frozen=True)
class Verdict:
    """Ce que la mutation a produit. Une seule valeur est une preuve."""

    mutation: Mutation
    outcome: str
    detail: str = ""

    @property
    def proves(self) -> bool:
        return self.outcome == "le test a mordu"


def load_mutations() -> list[Mutation]:
    document = json.loads(SPECS.read_text(encoding="utf-8"))
    return [Mutation(**entry) for entry in document["mutations"]]


def run_pytest(cwd: Path, target: str) -> subprocess.CompletedProcess[str]:
    # PYTHONDONTWRITEBYTECODE : un `.pyc` réutilisé entre deux copies a déjà
    # fait mentir un harnais de ce genre.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-x",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(cwd)},
    )


def falsify(mutation: Mutation, source: Path, parent: Path) -> Verdict:
    """Joue une mutation dans une copie neuve du dépôt, une copie par mutation."""
    workdir = parent / f"repo-{mutation.name}"
    shutil.copytree(source, workdir, ignore=IGNORED)

    target = workdir / mutation.file
    original = target.read_text(encoding="utf-8")

    occurrences = original.count(mutation.find)
    if occurrences == 0:
        # Le fragment n'est plus dans le fichier : rien n'a été mesuré. Ce
        # verdict est un échec, pas une absence de résultat.
        return Verdict(mutation, "la mutation ne s'applique pas", mutation.find[:60])
    if occurrences > 1:
        # Un motif ambigu mute le premier endroit, pas celui qu'on visait.
        return Verdict(mutation, f"motif ambigu, {occurrences} occurrences", mutation.find[:60])

    target.write_text(original.replace(mutation.find, mutation.replace, 1), encoding="utf-8")
    result = run_pytest(workdir, mutation.test)

    if "ImportError" in result.stdout or "SyntaxError" in result.stdout:
        return Verdict(mutation, "le module ne s'importe plus", "mutation destructive")
    if result.returncode == 0:
        return Verdict(mutation, "le test est resté vert", "garde non prouvée")
    return Verdict(mutation, "le test a mordu")


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    mutations = [m for m in load_mutations() if not wanted or m.name in wanted]
    if not mutations:
        print("aucune mutation à jouer", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="falsify-") as temporary:
        parent = Path(temporary)
        reference = parent / "repo-baseline"
        shutil.copytree(ROOT, reference, ignore=IGNORED)

        # Exiger le vert d'abord : une copie déjà rouge rendrait tous les
        # verdicts suivants ininterprétables.
        baseline = run_pytest(reference, "tests/unit")
        if baseline.returncode != 0:
            print("la copie de référence est rouge avant toute mutation :", file=sys.stderr)
            print(baseline.stdout[-2000:], file=sys.stderr)
            return 1

        verdicts = [falsify(mutation, ROOT, parent) for mutation in mutations]

    largeur = max(len(v.mutation.name) for v in verdicts)
    for verdict in verdicts:
        marque = "prouvée" if verdict.proves else "NON PROUVÉE"
        detail = f" ({verdict.detail})" if verdict.detail else ""
        print(f"  {verdict.mutation.name:<{largeur}}  {marque:<12} {verdict.outcome}{detail}")

    manquees = [v for v in verdicts if not v.proves]
    print(f"\n{len(verdicts) - len(manquees)} garde(s) prouvée(s) sur {len(verdicts)}")
    return 1 if manquees else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
