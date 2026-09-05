"""Ce que la dérive de l'API a fait au générateur, en un texte lisible.

Le workflow planifié télécharge le contrat, puis appelle ce script. Il ne
décide rien : il **dit** ce qui a bougé, et laisse l'arbitrage à un humain,
parce qu'une opération apparue en amont demande une décision de classification
que personne ne veut voir prise toute seule.

    python scripts/drift_report.py            # rien n'a bougé : sortie vide, code 0
                                              # quelque chose a bougé : rapport, code 3

Le code 3 est délibérément distinct des trois codes que la CI connaît déjà
(`0` succès, `1` erreur, `2` opération non triée ou override orphelin) : une
dérive n'est pas une erreur du dépôt, c'est une nouvelle du monde extérieur, et
le workflow doit pouvoir la distinguer d'une panne de son propre outillage.

**Un seul document pour cinquante tags, et ça change ce que ce rapport doit
dire.** Le fichier bouge toujours en entier, et le golden ne couvre que les
produits que `products.txt` indexe : une opération apparue dans `VmGroup` ne
ferait rougir aucun golden tant que `VmGroup` n'est pas indexé. Ce rapport
compare donc le **recensement** du document versionné à celui du document
téléchargé, tag par tag, indexé ou non, avant de regarder le golden. C'est la
seule mesure qui voit ce qui n'est pas encore suivi.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from generator.source.base import DEFAULT_SPEC_ROOT, DOCUMENT_STEM, census, read_products

ROOT = Path(__file__).resolve().parents[1]
SPECS = DEFAULT_SPEC_ROOT
GOLDEN = ROOT / "tests" / "fixtures"
VERSION = "v1"

#: Le code de sortie qui dit « quelque chose a bougé ».
EXIT_DRIFT = 3


def _git(*arguments: str) -> str:
    resultat = subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if resultat.returncode not in (0, 1):
        raise SystemExit(f"git {' '.join(arguments)} a échoué :\n{resultat.stderr}")
    return resultat.stdout


def _charger(texte: str) -> dict[str, Any]:
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    document: dict[str, Any] = yaml.load(texte, Loader=loader)
    return document


def contrats_modifies() -> list[str]:
    sortie = _git("status", "--porcelain", "--", str(SPECS.relative_to(ROOT)))
    return [ligne[3:] for ligne in sortie.splitlines() if ligne.strip()]


def document_versionne() -> dict[str, Any] | None:
    """Le document tel que HEAD le porte, sans toucher à l'arbre de travail."""
    chemin = (SPECS / f"{DOCUMENT_STEM}.{VERSION}.yml").relative_to(ROOT)
    texte = _git("show", f"HEAD:{chemin.as_posix()}")
    if not texte.strip():
        return None
    return _charger(texte)


def document_telecharge() -> dict[str, Any]:
    chemin = SPECS / f"{DOCUMENT_STEM}.{VERSION}.yml"
    return _charger(chemin.read_text(encoding="utf-8"))


def ecarts_par_produit(
    avant: dict[str, int], apres: dict[str, int], indexes: frozenset[str]
) -> list[tuple[str, int, int, bool]]:
    """Les tags dont le nombre d'opérations a changé : nom, avant, après, indexé.

    Fonction pure, pour que la lecture d'un tag apparu, disparu ou grossi se
    teste sans git ni document. Un tag absent d'un côté compte zéro.
    """
    ecarts: list[tuple[str, int, int, bool]] = []
    for produit in sorted(set(avant) | set(apres)):
        a, b = avant.get(produit, 0), apres.get(produit, 0)
        if a != b:
            ecarts.append((produit, a, b, produit in indexes))
    return ecarts


def golden_modifie() -> str:
    """Ce que la dérive fait à l'IR, qui est la seule chose actionnable."""
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_golden.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    return _git("diff", "--stat", "--", str(GOLDEN.relative_to(ROOT)))


def _suivi(indexe: bool) -> str:
    return "oui, golden et rapport strict" if indexe else "non"


def rapport(
    contrats: list[str],
    ecarts: list[tuple[str, int, int, bool]],
    diff_golden: str,
    total_avant: int,
    total_apres: int,
    version_avant: str | None = None,
    version_apres: str | None = None,
) -> str:
    """Le texte de l'issue, depuis des mesures déjà faites. Pure, donc testable."""
    lignes = [
        "Le contrat publié par Outscale n'est plus celui que ce dépôt versionne.",
        "C'est la nouvelle que ce mécanisme existe pour donner : toute opération",
        "apparue en amont doit finir **générée**, **écartée avec sa raison** dans",
        "les overrides, ou **UNKNOWN** avec la CI rouge. Jamais dans le silence.",
        "",
        "## Le contrat qui a bougé",
        "",
        "```text",
        *contrats,
        "```",
        "",
    ]
    if version_avant or version_apres:
        lignes += [
            f"Version du document : {version_avant or '?'} -> {version_apres or '?'}. Le SDK",
            "Python embarque sa propre copie du contrat : relever le tag suivi",
            "(`scripts/sync_specs.py`) et `osc-sdk-python` ensemble, jamais l'un sans l'autre.",
            "",
        ]
    lignes += [
        "## Ce que le recensement voit, tag par tag",
        "",
        f"Le document passe de {total_avant} à {total_apres} opérations. Un seul",
        "document porte tous les tags, et le golden ne couvre que ceux que",
        "`products.txt` indexe : cette table est la seule mesure qui voit les autres.",
        "",
    ]
    if ecarts:
        lignes += [
            "| tag | avant | après | suivi par le générateur |",
            "|---|---:|---:|---|",
            *(
                f"| `{produit}` | {a} | {b} | {_suivi(indexe)} |"
                for produit, a, b, indexe in ecarts
            ),
            "",
        ]
    else:
        lignes += [
            "Aucun tag ne change de nombre d'opérations : la dérive porte sur le",
            "contenu d'opérations existantes, ou sur ce que le parser ne lit pas.",
            "",
        ]

    lignes += [
        "## Ce que ça fait à la représentation intermédiaire",
        "",
        "Un contrat qui change de mise en forme sans changer une opération n'est",
        "pas une dérive du produit. C'est le golden qui tranche, pour les produits",
        "indexés.",
        "",
    ]
    if diff_golden:
        lignes += ["```text", diff_golden, "```", ""]
    else:
        lignes += [
            "Aucun changement dans l'IR des produits indexés : la dérive est de mise",
            "en forme, porte sur ce que le parser ne lit pas, ou touche un tag que",
            "le générateur ne suit pas encore. Le diff du contrat reste à lire.",
            "",
        ]

    lignes += [
        "## Ce qu'il reste à faire, et qu'aucune machine ne fera",
        "",
        "1. `mise run sync:api` en local, puis lire le diff du contrat ;",
        "2. `mise run products` : ce que chaque tag compte, indexé ou non ;",
        "3. `mise run check` : le rapport strict sort en 2 sur toute opération",
        "   non classée, et le golden échoue sur tout ce qui a bougé ;",
        "4. classer ce qui est apparu, ou l'écarter **avec sa raison** ;",
        "5. `mise run golden:update`, puis lire le diff avant de le commiter.",
    ]
    return "\n".join(lignes)


def main() -> int:
    contrats = contrats_modifies()
    if not contrats:
        print("aucune dérive : le contrat téléchargé est celui qui est versionné")
        return 0

    avant = document_versionne()
    apres = document_telecharge()
    recensement_apres = census(apres)
    recensement_avant = census(avant) if avant is not None else None
    indexes = frozenset(entree.tag for entree in read_products(SPECS))

    ecarts = ecarts_par_produit(
        recensement_avant.by_tag if recensement_avant is not None else {},
        recensement_apres.by_tag,
        indexes,
    )
    print(
        rapport(
            contrats,
            ecarts,
            golden_modifie().strip(),
            recensement_avant.total if recensement_avant is not None else 0,
            recensement_apres.total,
            str(avant.get("info", {}).get("version")) if avant is not None else None,
            str(apres.get("info", {}).get("version")),
        )
    )
    return EXIT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main())
