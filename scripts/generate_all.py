"""Écrit les modules de chaque produit indexé, dans une seule collection.

`python -m generator generate` prend un produit, et c'est juste. Mais
`products.txt` en indexe plusieurs, et une tâche qui n'en génère qu'un
laisserait `check:generated` mesurer un arbre à moitié régénéré. **La liste
des produits n'est pas recopiée ici** : elle vient de l'index, comme pour
`report_all.py`.

Le code de sortie est le plus sévère rencontré, pas celui du dernier produit.

    python scripts/generate_all.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generator.ansible.collection import load_collection
from generator.cli import main as generator_main
from generator.source.base import DEFAULT_SPEC_ROOT, VendoredSpecSource

ROOT = Path(__file__).resolve().parents[1]


def clear_modules(modules_dir: Path) -> list[Path]:
    """Retire les modules de la génération précédente, et rend ce qu'il a retiré.

    Le générateur écrit sans jamais retirer. Mesuré : une règle de dérivation
    corrigée a fait disparaître douze modules fantômes du plan, et les douze
    fichiers sont restés sur le disque, dans l'archive et dans le README. Un
    module que la génération n'écrit plus n'existe plus ; le retirer avant de
    régénérer est ce qui rend `check:generated` capable de le voir.
    """
    removed = sorted(path for path in modules_dir.glob("*.py") if not path.name.startswith("_"))
    for path in removed:
        path.unlink()
    return removed


def main() -> int:
    produits = list(VendoredSpecSource(root=DEFAULT_SPEC_ROOT).available())
    if not produits:
        print(
            f"aucun produit dans {DEFAULT_SPEC_ROOT.relative_to(ROOT)}/products.txt : "
            "une génération qui n'écrit rien passerait pour une génération réussie.",
            file=sys.stderr,
        )
        return 1

    modules_dir = load_collection().modules_dir
    removed = clear_modules(modules_dir)
    print(f"{len(removed)} module(s) de la génération précédente retiré(s) avant de régénérer\n")

    pire = 0
    for produit, version in produits:
        code = generator_main(["generate", produit, "--api-version", version])
        pire = max(pire, code)
        print()
    return pire


if __name__ == "__main__":
    raise SystemExit(main())
