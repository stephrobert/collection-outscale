"""Les nombres publiés dans les README, dérivés plutôt que recopiés.

**Un nombre recopié à la main vieillit en silence, et se lit exactement comme
une mesure.** `collection-scaleway` l'a mesuré quatre fois le même jour. Ce
dépôt part avec le mécanisme plutôt que d'attendre la même journée.

Ce script produit le bloc entre les deux marqueurs de chaque README depuis les
sources qui font foi. Deux modes, et la CI se sert du second :

    python scripts/readme_counters.py --write    réécrit les blocs
    python scripts/readme_counters.py --check    échoue si un bloc a vieilli

**Aucun nom de produit, de module ni de plugin n'est écrit ici.** Les produits
viennent de `products.txt`, les modules et les plugins du disque, les tags du
contrat. Un produit ajouté à l'index apparaît dans les deux README sans qu'une
ligne de ce fichier change.

Ce qui n'est pas mesurable hors ligne n'entre pas dans le bloc. Le compte de
`ansible-test sanity` demande de lancer autre chose ; il est dit sans nombre.

**Deux publics, deux langues.** Les README sont publiés, donc le bloc est en
anglais, point décimal compris. Le code et les messages d'erreur de ce script
restent en français.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from generator.ansible.collection import Collection, load_collection
from generator.source.base import (
    DEFAULT_SPEC_ROOT,
    DOCUMENT_STEM,
    ProductEntry,
    census,
    read_products,
)

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RAPPORTS = ROOT / "build" / "reports"
MUTATIONS = ROOT / "tests" / "falsify" / "specs.json"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PLAYBOOKS = ROOT / "examples" / "playbooks"

DEBUT = "<!-- counters:start, produced by scripts/readme_counters.py -->"
FIN = "<!-- counters:end -->"


class CompteursError(RuntimeError):
    """Une source manque, et il vaut mieux le dire que publier un nombre faux."""


def _affichable(chemin: Path) -> str:
    """Un chemin lisible, même hors du dépôt : `relative_to` lève sinon."""
    try:
        return str(chemin.relative_to(ROOT))
    except ValueError:
        return str(chemin)


def _produits() -> list[ProductEntry]:
    produits = read_products(DEFAULT_SPEC_ROOT)
    if not produits:
        raise CompteursError("products.txt n'indexe aucun produit : rien à compter")
    return produits


def _document() -> dict[str, Any]:
    chemin = DEFAULT_SPEC_ROOT / f"{DOCUMENT_STEM}.{_produits()[0].version}.yml"
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    donnees: dict[str, Any] = yaml.load(chemin.read_text(encoding="utf-8"), Loader=loader)
    return donnees


def _rapport(entree: ProductEntry) -> dict[str, Any]:
    chemin = RAPPORTS / f"{entree.product}.{entree.version}.json"
    if not chemin.is_file():
        raise CompteursError(
            f"{_affichable(chemin)} manque : lancer `mise run report` avant. "
            "Un compteur sans sa source n'est pas un compteur."
        )
    donnees: dict[str, Any] = json.loads(chemin.read_text(encoding="utf-8"))
    return donnees


def _modules_ecrits(entree: ProductEntry) -> tuple[int, int]:
    """Modules écrits et écartés d'un produit, lus dans son compte rendu."""
    chemin = RAPPORTS / f"{entree.product}.{entree.version}.generation.md"
    if not chemin.is_file():
        raise CompteursError(
            f"{_affichable(chemin)} manque : lancer `mise run generate` avant. "
            "Un bloc qui annonce zéro module passerait pour un dépôt vide."
        )
    ligne = next(
        (
            ligne
            for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.startswith("Modules écrits :")
        ),
        None,
    )
    if ligne is None:
        raise CompteursError(f"{_affichable(chemin)} ne porte pas sa ligne de modules")
    return int(ligne.split("**")[1]), int(ligne.split("**")[3])


def _tests() -> int:
    """Le nombre de tests que pytest collecte, demandé à pytest."""
    resultat = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", str(ROOT / "tests")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    for ligne in reversed(resultat.stdout.splitlines()):
        mots = ligne.split()
        if len(mots) >= 3 and mots[1] in {"test", "tests"} and mots[2] == "collected":
            return int(mots[0])
    raise CompteursError(
        f"pytest n'a pas dit combien de tests il collecte :\n{resultat.stdout[-500:]}"
    )


def _mutations() -> int:
    donnees = json.loads(MUTATIONS.read_text(encoding="utf-8"))
    return len(donnees["mutations"])


def _jobs() -> tuple[int, tuple[str, ...]]:
    if not WORKFLOW.is_file():
        raise CompteursError(f"{_affichable(WORKFLOW)} manque : le bloc annonce les jobs de la CI")
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    noms = tuple(str(details.get("name", cle)).split(" (")[0] for cle, details in jobs.items())
    return len(jobs), noms


def _short_description(fichier: Path) -> str:
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("short_description:"):
            return ligne.split(":", 1)[1].strip().strip("\"'")
    return ""


def _modules_par_produit(collection: Collection) -> dict[str, list[tuple[str, str]]]:
    """Les modules livrés, groupés par produit, avec leur `short_description`.

    Le produit d'un module est le plus long préfixe de son nom qui est un
    produit de l'index : `net_peering_info` appartient à `net_peering`, pas à
    `net`. Aucun nom n'est écrit ici.
    """
    produits = sorted((entree.product for entree in _produits()), key=len, reverse=True)
    par_produit: dict[str, list[tuple[str, str]]] = {}
    for fichier in sorted(collection.modules_dir.glob("*.py")):
        if fichier.name.startswith("_"):
            continue
        produit = next((p for p in produits if fichier.stem.startswith(p + "_")), None)
        if produit is None:
            raise CompteursError(
                f"{fichier.stem} ne porte le préfixe d'aucun produit indexé : "
                "le bloc ne saurait pas où le ranger"
            )
        par_produit.setdefault(produit, []).append((fichier.stem, _short_description(fichier)))
    if not par_produit:
        raise CompteursError(
            f"{_affichable(collection.modules_dir)} ne porte aucun module : lancer "
            "`mise run generate`. Un bloc qui annonce zéro module est un bloc faux."
        )
    return par_produit


def _plugins_dinventaire(collection: Collection) -> list[str]:
    """Les plugins d'inventaire livrés, lus sur le disque."""
    dossier = collection.path / "plugins" / "inventory"
    if not dossier.is_dir():
        return []
    return sorted(p.stem for p in dossier.glob("*.py") if not p.stem.startswith("_"))


def _modules_appeles(collection: Collection) -> int:
    """Combien de modules livrés l'exemple appelle, lu dans les clés de tâches.

    C'est la même lecture que `scripts/example_coverage.py` : les clés de
    tâches, jamais le texte. Ce nombre entre dans le README parce qu'il se
    dérive hors ligne ; ce qu'un run a joué n'y entre pas.
    """
    prefixe = f"{collection.fqcn}."
    ecrits = {p.stem for p in collection.modules_dir.glob("*.py") if not p.stem.startswith("_")}
    appeles: set[str] = set()
    for chemin in sorted(PLAYBOOKS.glob("*.yml")) if PLAYBOOKS.is_dir() else []:
        document = yaml.safe_load(chemin.read_text(encoding="utf-8"))
        for tache in _taches(document):
            for cle in tache:
                nom = str(cle)
                if nom.startswith(prefixe) and nom[len(prefixe) :] in ecrits:
                    appeles.add(nom[len(prefixe) :])
    return len(appeles)


def _taches(noeud: Any) -> list[dict[str, Any]]:
    if isinstance(noeud, list):
        return [t for element in noeud for t in _taches(element)]
    if not isinstance(noeud, dict):
        return []
    trouvees = [noeud]
    for cle in ("tasks", "pre_tasks", "post_tasks", "handlers", "block", "rescue", "always"):
        if cle in noeud:
            trouvees.extend(_taches(noeud[cle]))
    return trouvees


def _pourcent(valeur: float | None) -> str:
    """Le point décimal de l'anglais : ce nombre atterrit dans un README publié."""
    if valeur is None:
        return "n/a"
    return f"{valeur * 100:.1f}%"


def bloc() -> str:
    """Le bloc du README racine, tel qu'il doit être aujourd'hui."""
    collection = load_collection()
    produits = _produits()
    document = _document()
    recensement = census(document)
    version = produits[0].version
    version_document = document.get("info", {}).get("version", "?")

    lignes = [
        "```text",
        f"outscale {version} (document {version_document}): {recensement.total} operations "
        f"in a single document, {len(recensement.by_tag)} tags counted, {len(produits)} indexed",
    ]
    ecrits_total = ecartes_total = 0
    for entree in produits:
        rapport = _rapport(entree)
        totaux = rapport["totals"]
        genres = totaux["by_kind"]
        modes = totaux["by_mode"]
        ecrits, ecartes = _modules_ecrits(entree)
        ecrits_total += ecrits
        ecartes_total += ecartes
        lignes += [
            f"  {entree.product} {entree.version}: {totaux['operations']} operations, "
            f"{totaux['paginated']} paginated, {totaux['hidden']} classified without a module",
            f"    INFO {genres['info']} · ACTION {genres['action']} · "
            f"MANAGE {genres['manage']} · WORKFLOW {genres['workflow']} · "
            f"LIFECYCLE {genres['lifecycle']} · IGNORE {genres['ignore']} · "
            f"UNKNOWN {genres['unknown']}",
            f"    Day-2 {totaux['day2_candidates']} · AUTO {modes['auto']} · "
            f"OVERRIDE {modes['override']} · classified for automatic generation "
            f"{_pourcent(rapport['day2_automation_coverage'])} "
            f"({modes['auto'] + modes['override']}/{totaux['day2_candidates']})",
        ]

    nb_jobs, noms_jobs = _jobs()
    appeles = _modules_appeles(collection)
    lignes += [
        "",
        f"collection {collection.fqcn}: {ecrits_total} modules written, "
        f"{ecrits_total + ecartes_total} planned, {ecartes_total} set aside with their reason",
        f"  {appeles} of {ecrits_total} modules called by the example playbooks "
        f"({_pourcent(appeles / ecrits_total if ecrits_total else None)})",
    ]
    for _, modules in sorted(_modules_par_produit(collection).items()):
        lignes += [f"  {nom:<40s} {courte}" for nom, courte in modules]
    lignes += [
        f"  {nom + ' (inventory)':<40s} dynamic inventory"
        for nom in _plugins_dinventaire(collection)
    ]
    lignes += [
        f"  {_tests()} unit tests · {_mutations()} guards proven by mise run falsify",
        f"  CI: {nb_jobs} jobs, {' · '.join(noms_jobs)}",
        "  ansible-test sanity: reported by `mise run sanity`, not counted here",
        "```",
    ]
    return "\n".join(lignes)


def table_des_modules() -> str:
    """La table du README de la collection, par produit, même source que le bloc.

    C'est le fichier que `galaxy.yml` désigne, donc celui que Galaxy publie.
    Une seconde source recopiée à la main aurait exactement le défaut qu'on
    évite : deux dérivations pour une même chose, une seule tenue à jour.
    """
    collection = load_collection()
    entrees = {entree.product: entree for entree in _produits()}
    lignes: list[str] = []
    for produit, modules in sorted(_modules_par_produit(collection).items()):
        pluriel = "module" if len(modules) == 1 else "modules"
        lignes += [
            "",
            f"### {produit} ({len(modules)} {pluriel}, tag `{entrees[produit].tag}`)",
            "",
            "| module | what it does |",
            "|---|---|",
            *(f"| `{nom}` | {courte} |" for nom, courte in modules),
        ]
    plugins = _plugins_dinventaire(collection)
    if plugins:
        lignes += [
            "",
            "### Inventory plugins",
            "",
            "| plugin | what it discovers |",
            "|---|---|",
            *(f"| `{nom}` | {_short_description_of_plugin(collection, nom)} |" for nom in plugins),
        ]
    return "\n".join(lignes[1:])


def _short_description_of_plugin(collection: Collection, nom: str) -> str:
    """La `short_description` du plugin, lue dans sa `DOCUMENTATION`."""
    fichier = collection.path / "plugins" / "inventory" / f"{nom}.py"
    return _short_description(fichier)


def _remplace(fichier: Path, texte: str, nouveau: str) -> str:
    if DEBUT not in texte or FIN not in texte:
        raise CompteursError(
            f"les marqueurs manquent dans {_affichable(fichier)}. Encadrer le bloc par :\n"
            f"{DEBUT}\n...\n{FIN}"
        )
    avant = texte[: texte.index(DEBUT) + len(DEBUT)]
    apres = texte[texte.index(FIN) :]
    return f"{avant}\n{nouveau}\n{apres}"


def blocs() -> dict[Path, str]:
    """Les blocs dérivés, et le fichier de chacun."""
    collection = load_collection()
    return {
        README: bloc(),
        collection.path / "README.md": table_des_modules(),
    }


def main(argv: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    groupe = parseur.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--write", action="store_true", help="réécrire les blocs")
    groupe.add_argument("--check", action="store_true", help="échouer si un bloc a vieilli")
    arguments = parseur.parse_args(argv[1:])

    perimes: list[str] = []
    for fichier, contenu in blocs().items():
        texte = fichier.read_text(encoding="utf-8")
        attendu = _remplace(fichier, texte, contenu)
        nom = _affichable(fichier)
        if arguments.write:
            if attendu == texte:
                print(f"{nom} : déjà à jour")
                continue
            fichier.write_text(attendu, encoding="utf-8")
            print(f"{nom} : réécrit")
            continue
        if attendu != texte:
            perimes.append(nom)
        else:
            print(f"{nom} : conforme à la mesure")

    if perimes:
        print(
            f"ces blocs ne correspondent plus à ce qui est mesuré : {', '.join(perimes)}.\n"
            "Lancer `mise run readme` puis relire le diff : un nombre recopié à la\n"
            "main vieillit en silence, et se lit exactement comme une mesure.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except CompteursError as erreur:
        print(f"erreur : {erreur}", file=sys.stderr)
        raise SystemExit(1) from erreur
