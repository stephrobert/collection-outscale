"""Pilote `antsibull-changelog` depuis la collection.

L'outil veut être lancé dans le répertoire qui contient `changelogs/`,
c'est-à-dire la collection. Ce script l'y emmène en **découvrant** son chemin
plutôt qu'en le codant en dur : le namespace n'a qu'une source, `galaxy.yml`,
et le chemin en est déduit.

    python scripts/changelog.py lint                  # juger les fragments
    python scripts/changelog.py release --version X   # rassembler et publier
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from generator.ansible.collection import load_collection

ROOT = Path(__file__).resolve().parents[1]


def commande(argv: list[str], executable: str = sys.executable) -> list[str]:
    """La commande, avec l'`ansible-doc` qui vit à côté de l'interpréteur.

    `antsibull-changelog release` lit les modules par `ansible-doc`, qu'il
    prend sur le PATH. Mesuré : une session ouverte dans un dépôt voisin
    composait ce changelog avec l'`ansible-doc` du voisin, et le disait
    seulement par un avertissement. Celui d'à côté de l'interpréteur est
    celui de ce dépôt, et il est nommé explicitement.
    """
    command = [executable, "-m", "antsibull_changelog", *argv[1:]]
    if len(argv) > 1 and argv[1] == "release" and "--ansible-doc-bin" not in argv:
        command += ["--ansible-doc-bin", str(Path(executable).parent / "ansible-doc")]
    return command


def main(argv: list[str]) -> int:
    collection = load_collection()
    command = commande(argv)
    print(
        f"$ {' '.join(command[2:])}\n  dans {os.path.relpath(collection.path, ROOT)}\n",
        flush=True,
    )
    return subprocess.run(command, cwd=collection.path, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
