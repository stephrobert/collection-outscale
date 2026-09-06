"""Mesure ce que la documentation publiée vaut, et refuse ce qui n'est pas publiable.

**Le générateur industrialise le code ; rien n'industrialisait la documentation
qu'il produit.** `ansible-test sanity` dit qu'un bloc est bien formé, pas qu'il
apprend quelque chose à quelqu'un. Mesuré sur les 33 pages de la collection
avant cette porte : cinq lectures publiaient un filtre `Tags` que leur schéma
`Filters` ne porte pas, copiable et refusé par l'API ; un module d'action
montrait une action sur trois ; treize pages écrivaient « vm », « nic »,
« dhcp » en minuscules dans une phrase ; et aucune clé rendue ne disait ce
qu'on y trouve.

Le critère, et il est plus exigeant que la syntaxe :

    Chaque module publié doit pouvoir être compris et utilisé depuis sa seule
    page Galaxy, sans lire le contrat OpenAPI ni le code source.

    python scripts/docs_quality.py            la mesure, par défaut
    python scripts/docs_quality.py --check    échoue sur un défaut bloquant
    python scripts/docs_quality.py --json     pour un script

**Ce que ce contrôle n'est pas.** Il ne juge pas le style. Il cherche des
défauts nommés, chacun trouvé sur une page réelle, et chacun réparable dans le
générateur plutôt que dans le fichier produit. Un défaut qui ne se répare qu'à
la main n'a rien à faire ici : il retomberait au produit suivant.

**Un défaut ne devient bloquant que le jour où il passe à zéro.** Tant qu'il
en reste, bloquer ferme la publication sans rien réparer ; une fois corrigé,
le laisser passant garantit qu'il revient sans qu'on s'en aperçoive. Les huit
genres ci-dessous sont à zéro, donc tous bloquants.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from generator.ansible.collection import load_collection
from generator.ansible.models import ACRONYMES, UNDOCUMENTED

ROOT = Path(__file__).resolve().parents[1]

#: Le texte que le générateur pose quand le contrat ne décrit rien. Une seule
#: source, celle du générateur : une copie ici dériverait en silence.
REPLI = UNDOCUMENTED

#: Un exemple dont les valeurs sont des chevrons ne se copie pas : il montre la
#: forme et cache ce qu'on doit y mettre.
PLACEHOLDER = re.compile(r"<[a-z_]+>")

#: Le début de l'en-tête que le renderer écrit sur chaque module généré, et
#: qui nomme les opérations du contrat que le module appelle.
EN_TETE_OPERATIONS = "# Opérations : "

#: Un nom de tâche qui commence par le verbe du SDK plutôt que par ce que la
#: tâche fait : « Run reboot on a vm ».
NOM_PAR_LE_VERBE = re.compile(r"^Run\b")

#: Les clés qu'un `filters` accepte, telles que la description de l'option
#: les liste : « Accepted keys: C(Tags), C(VmIds). »
CLES_ACCEPTEES = re.compile(r"Accepted keys: (.*?)\.\s*$")
CONSTANTE = re.compile(r"C\(([A-Za-z0-9_.-]+)\)")

#: Une valeur d'action citée dans une phrase : `C(reboot)`. Minuscule, comme
#: les noms d'actions ; `C(State)` et `C(changed=false)` ne sont pas des
#: actions.
ACTION_CITEE = re.compile(r"C\(([a-z][a-z0-9_]*)\)")

#: Le vocabulaire des identifiants, quand il se glisse dans une phrase : `vm`,
#: `Vm`, `dhcp`. Le contrat écrit VM, NIC, DHCP, NAT, IP dans ses propres
#: phrases, et le générateur le fait aussi depuis `ACRONYMES` ; ce détecteur
#: est ce qui l'y oblige. Il ne regarde que la prose : un nom d'option ou une
#: clé rendue s'écrit `vm_id`, et c'est correct.
JARGON = re.compile(
    r"\b(?:" + "|".join(f"{mot}|{mot.capitalize()}" for mot in sorted(ACRONYMES)) + r")\b"
)

#: Le marquage d'Ansible dans une phrase : `C(id)`, `I(vm_id)`, `L(texte, url)`.
#: Ce qu'il enferme est un nom ou une adresse, pas de la prose : `C(id)` cite
#: la valeur d'une option, et le juger comme un mot serait un faux positif.
MARQUAGE = re.compile(r"\b[A-Z]\([^()]*\)")

#: Les genres de défaut, et ce qu'un lecteur y perd. Tous bloquants : chacun
#: est passé à zéro sur la collection avant d'entrer ici.
BLOQUANTS: frozenset[str] = frozenset(
    {
        "description-absente",
        "option-sans-description",
        "retour-sans-description",
        "champ-de-retour-sans-description",
        "exemple-non-copiable",
        "exemple-nomme-par-le-contrat",
        "exemple-cle-de-filtre-inconnue",
        "action-exclue-documentee",
        "vocabulaire-du-contrat",
    }
)


class QualiteError(RuntimeError):
    """Une source manque, et un chiffre faux serait pire qu'une erreur."""


@dataclass
class Defaut:
    """Un défaut nommé, sur une page nommée, avec ce qu'il faut corriger."""

    module: str
    genre: str
    detail: str

    @property
    def bloquant(self) -> bool:
        return self.genre in BLOQUANTS


@dataclass
class Mesure:
    """Ce que la documentation publiée vaut, en nombres."""

    modules: int = 0
    options: int = 0
    options_decrites: int = 0
    retours: int = 0
    retours_decrits: int = 0
    #: Clés de retour `dict` ou `list`, les seules qui puissent porter des
    #: champs, et celles qui les portent vraiment.
    retours_composites: int = 0
    retours_detailles: int = 0
    #: Les clés composites sans champs, nommées une par une. Le module les
    #: compose lui-même (`changes`, `states`) ou l'API ne rend rien derrière
    #: (`result` d'un redémarrage) : ce n'est pas un défaut, et un ratio dont
    #: on ignore ce que le reste contient ne dit rien à personne.
    sans_detail: list[str] = field(default_factory=list)
    #: Champs publiés sous un `contains`, à tous les niveaux, et ceux décrits.
    champs: int = 0
    champs_decrits: int = 0
    exemples: int = 0
    exemples_copiables: int = 0

    def ajouter(self, autre: Mesure) -> None:
        self.modules += autre.modules
        self.options += autre.options
        self.options_decrites += autre.options_decrites
        self.retours += autre.retours
        self.retours_decrits += autre.retours_decrits
        self.retours_composites += autre.retours_composites
        self.retours_detailles += autre.retours_detailles
        self.sans_detail.extend(autre.sans_detail)
        self.champs += autre.champs
        self.champs_decrits += autre.champs_decrits
        self.exemples += autre.exemples
        self.exemples_copiables += autre.exemples_copiables

    def ratio(self, numerateur: int, denominateur: int) -> str:
        """Un ratio sans dénominateur est indéfini, pas nul."""
        if denominateur == 0:
            return "n/a"
        return f"{numerateur / denominateur * 100:.1f} %"


def _bloc(source: str, nom: str) -> Any:
    motif = re.compile(rf'^{nom} = r?"""(.*?)"""', re.S | re.M)
    trouve = motif.search(source)
    if not trouve:
        return None
    try:
        return yaml.safe_load(trouve.group(1))
    except yaml.YAMLError:
        return None


def _exemples(source: str) -> list[Any]:
    """Les exemples d'un fichier, quelle que soit la forme qu'ils prennent.

    Un module publie **une liste de tâches** ; un plugin d'inventaire publie
    **plusieurs fichiers**, séparés par `---`, parce que c'est un fichier
    d'inventaire entier qu'on copie et pas une tâche. `safe_load` ne rend que
    le premier document : mesurer avec lui laisserait les autres hors de la
    mesure, sur la page qu'un utilisateur lit en premier.
    """
    motif = re.compile(r'^EXAMPLES = r?"""(.*?)"""', re.S | re.M)
    trouve = motif.search(source)
    if not trouve:
        return []
    try:
        documents = [d for d in yaml.safe_load_all(trouve.group(1)) if d is not None]
    except yaml.YAMLError:
        return []
    if len(documents) == 1 and isinstance(documents[0], list):
        return documents[0]
    return documents


def _lignes(valeur: Any) -> list[str]:
    """Une `description` d'Ansible est une chaîne ou une liste de chaînes."""
    if isinstance(valeur, str):
        return [valeur]
    if isinstance(valeur, list):
        return [str(x) for x in valeur]
    return []


def _decrite(valeur: Any) -> bool:
    lignes = _lignes(valeur)
    return bool(lignes) and REPLI not in " ".join(lignes)


def operations_du_module(source: str) -> set[str]:
    """Les identifiants du contrat que l'en-tête du module nomme.

    Le renderer les écrit, repliés sur plusieurs lignes de commentaire quand
    ils sont nombreux. Un plugin écrit à la main n'en porte pas, et n'en a
    pas besoin : son exemple n'a aucun identifiant de SDK à reprendre.
    """
    lignes = source.splitlines()
    for rang, ligne in enumerate(lignes):
        if not ligne.startswith(EN_TETE_OPERATIONS):
            continue
        texte = ligne[len(EN_TETE_OPERATIONS) :]
        for suite in lignes[rang + 1 :]:
            if suite.startswith("#  "):
                texte += " " + suite.lstrip("# ")
            else:
                break
        return {mot.strip() for mot in texte.split(",") if mot.strip()}
    return set()


def _cles_acceptees(doc: dict[str, Any]) -> set[str]:
    """Les clés que l'option `filters` déclare accepter, lues sur la page."""
    corps = (doc.get("options") or {}).get("filters") or {}
    for ligne in _lignes(corps.get("description")):
        trouve = CLES_ACCEPTEES.search(ligne)
        if trouve:
            return set(CONSTANTE.findall(trouve.group(1)))
    return set()


def _prose(doc: dict[str, Any], retour: dict[str, Any], exemples: list[Any]) -> list[str]:
    """Tout ce qu'un lecteur lit comme une phrase, et rien de ce qui est un nom."""
    phrases: list[str] = [str(doc.get("short_description") or "")]
    phrases += _lignes(doc.get("description"))
    phrases += _lignes(doc.get("notes"))
    for corps in (doc.get("options") or {}).values():
        phrases += _lignes((corps or {}).get("description"))
    phrases += _prose_des_retours(retour)
    for tache in exemples:
        if isinstance(tache, dict) and tache.get("name"):
            phrases.append(str(tache["name"]))
    return [p for p in phrases if p]


def _prose_des_retours(retour: dict[str, Any]) -> list[str]:
    phrases: list[str] = []
    for corps in (retour or {}).values():
        phrases += _lignes((corps or {}).get("description"))
        phrases += _prose_des_retours((corps or {}).get("contains") or {})
    return phrases


def _champs(mesure: Mesure, defauts: list[Defaut], nom: str, chemin: str, contains: Any) -> None:
    """Compte les champs d'un `contains`, à tous les niveaux.

    La surface publiée s'est élargie aux champs des ressources : la mesure
    doit s'élargir avec elle, sinon cent replis partent sur Galaxy sans que
    rien ne les compte. C'est exactement ce qui est arrivé à
    collection-scaleway sur sa 0.2.0.
    """
    for champ, detail in (contains or {}).items():
        mesure.champs += 1
        if _decrite((detail or {}).get("description")):
            mesure.champs_decrits += 1
        else:
            defauts.append(Defaut(nom, "champ-de-retour-sans-description", f"`{chemin}.{champ}`"))
        _champs(mesure, defauts, nom, f"{chemin}.{champ}", (detail or {}).get("contains"))


def examiner(chemin: Path) -> tuple[Mesure, list[Defaut]]:
    """Mesure une page publiée, et nomme ses défauts."""
    nom = chemin.stem
    source = chemin.read_text(encoding="utf-8")
    mesure = Mesure(modules=1)
    defauts: list[Defaut] = []

    doc = _bloc(source, "DOCUMENTATION") or {}
    retour = _bloc(source, "RETURN") or {}
    exemples = _exemples(source)

    # --- ce que la page dit d'elle-même -----------------------------------
    if not doc.get("description"):
        defauts.append(Defaut(nom, "description-absente", "la page ne dit pas ce qu'elle fait"))

    # --- les options publiques --------------------------------------------
    for option, corps in (doc.get("options") or {}).items():
        mesure.options += 1
        if _decrite((corps or {}).get("description")):
            mesure.options_decrites += 1
        else:
            defauts.append(Defaut(nom, "option-sans-description", f"option `{option}`"))

    # --- les clés de retour, et leurs champs ------------------------------
    for cle, corps in (retour or {}).items():
        mesure.retours += 1
        if _decrite((corps or {}).get("description")):
            mesure.retours_decrits += 1
        else:
            defauts.append(Defaut(nom, "retour-sans-description", f"clé `{cle}`"))
        # **Nommer la clé ne dit pas ce qu'on y trouve.** Le dénominateur ne
        # compte que les clés `dict` et les listes de `dict` : une clé `str`
        # ou une liste de chaînes n'a rien à contenir, et l'y ranger
        # reprocherait au module d'être correct.
        composite = (corps or {}).get("type") == "dict" or (
            (corps or {}).get("type") == "list" and (corps or {}).get("elements") == "dict"
        )
        if composite:
            mesure.retours_composites += 1
            if (corps or {}).get("contains"):
                mesure.retours_detailles += 1
            else:
                mesure.sans_detail.append(f"{nom}.{cle}")
        _champs(mesure, defauts, nom, cle, (corps or {}).get("contains"))

    # --- les exemples -------------------------------------------------------
    identifiants = operations_du_module(source)
    acceptees = _cles_acceptees(doc)
    for rang, tache in enumerate(exemples, start=1):
        if not isinstance(tache, dict):
            continue
        mesure.exemples += 1
        titre = str(tache.get("name") or f"exemple {rang}")
        rendu = yaml.safe_dump(tache, allow_unicode=True)
        if PLACEHOLDER.search(rendu):
            defauts.append(Defaut(nom, "exemple-non-copiable", f"« {titre} »"))
        else:
            mesure.exemples_copiables += 1
        mots = set(re.findall(r"[A-Za-z0-9_]+", titre))
        if NOM_PAR_LE_VERBE.match(titre) or mots & identifiants:
            defauts.append(Defaut(nom, "exemple-nomme-par-le-contrat", f"« {titre} »"))
        # **Une clé de filtre que la page ne déclare pas accepter.** Cinq
        # lectures publiaient `Tags` sur un schéma `Filters` qui ne le porte
        # pas : copiable, et refusé par l'API. La page porte les deux, l'exemple
        # et la liste des clés, donc elle peut se juger seule.
        for corps_tache in tache.values():
            filtres = corps_tache.get("filters") if isinstance(corps_tache, dict) else None
            if not isinstance(filtres, dict) or not acceptees:
                continue
            for inconnue in sorted(set(map(str, filtres)) - acceptees):
                defauts.append(
                    Defaut(
                        nom,
                        "exemple-cle-de-filtre-inconnue",
                        f"« {titre} » filtre sur `{inconnue}`, que l'option n'accepte pas",
                    )
                )

    # --- une action citée que le module refuse ------------------------------
    action = (doc.get("options") or {}).get("action") or {}
    choix = {str(x) for x in (action.get("choices") or [])}
    if choix:
        citees: set[str] = set()
        for ligne in _lignes(doc.get("description")) + _lignes(action.get("description")):
            citees.update(ACTION_CITEE.findall(ligne))
        for valeur in sorted(citees - choix):
            defauts.append(
                Defaut(
                    nom,
                    "action-exclue-documentee",
                    f"`{valeur}` est citée alors que le module la refuse",
                )
            )

    # --- le vocabulaire des identifiants dans une phrase --------------------
    for phrase in _prose(doc, retour, exemples):
        trouve = JARGON.search(MARQUAGE.sub(" ", phrase))
        if trouve:
            attendu = ACRONYMES[trouve.group(0).lower()]
            defauts.append(
                Defaut(
                    nom,
                    "vocabulaire-du-contrat",
                    f"« {trouve.group(0)} » dans « {phrase[:60]} », attendu : {attendu}",
                )
            )

    return mesure, defauts


def pages_publiees(collection_path: Path) -> list[Path]:
    """Les pages qu'un lecteur de Galaxy ouvre : les modules, et l'inventaire.

    **Le plugin d'inventaire est publié comme les modules.** Il a sa page sur
    Galaxy, ses options, et il est la porte d'entrée de la collection : c'est
    le premier fichier qu'un utilisateur écrit. Le laisser hors de la mesure
    reviendrait à surveiller les pages qu'on lit après, pas celle qu'on lit
    d'abord.
    """
    modules_dir = collection_path / "plugins" / "modules"
    if not modules_dir.is_dir():
        raise QualiteError(f"{modules_dir} n'existe pas : lancer `mise run generate`.")
    inventaire_dir = collection_path / "plugins" / "inventory"
    a_examiner = sorted(modules_dir.glob("*.py")) + sorted(inventaire_dir.glob("*.py"))
    return [chemin for chemin in a_examiner if not chemin.stem.startswith("_")]


def mesurer(collection_path: Path | None = None) -> tuple[Mesure, list[Defaut]]:
    racine = collection_path if collection_path is not None else load_collection().path
    total = Mesure()
    tous: list[Defaut] = []
    for chemin in pages_publiees(racine):
        mesure, defauts = examiner(chemin)
        total.ajouter(mesure)
        tous.extend(defauts)
    if total.modules == 0:
        raise QualiteError("aucune page examinée : une mesure vide passerait pour un vert.")
    return total, tous


def rendre(mesure: Mesure, defauts: list[Defaut]) -> str:
    bloquants = [d for d in defauts if d.bloquant]
    lignes = [
        f"{mesure.modules} pages publiées",
        f"  options décrites   {mesure.options_decrites:4d} / {mesure.options:<4d} "
        f"{mesure.ratio(mesure.options_decrites, mesure.options)}",
        f"  retours décrits    {mesure.retours_decrits:4d} / {mesure.retours:<4d} "
        f"{mesure.ratio(mesure.retours_decrits, mesure.retours)}",
        f"  retours détaillés  {mesure.retours_detailles:4d} / {mesure.retours_composites:<4d} "
        f"{mesure.ratio(mesure.retours_detailles, mesure.retours_composites)}"
        + (
            f"   (aucun schéma derrière : {', '.join(sorted(mesure.sans_detail))})"
            if mesure.sans_detail
            else ""
        ),
        f"  champs décrits     {mesure.champs_decrits:4d} / {mesure.champs:<4d} "
        f"{mesure.ratio(mesure.champs_decrits, mesure.champs)}",
        f"  exemples copiables {mesure.exemples_copiables:4d} / {mesure.exemples:<4d} "
        f"{mesure.ratio(mesure.exemples_copiables, mesure.exemples)}",
        "",
        f"  {len(bloquants)} défaut(s) bloquant(s), {len(defauts) - len(bloquants)} à corriger",
    ]
    par_genre: dict[str, list[Defaut]] = {}
    for defaut in defauts:
        par_genre.setdefault(defaut.genre, []).append(defaut)
    for genre, liste in sorted(par_genre.items(), key=lambda x: (-len(x[1]), x[0])):
        marque = "bloquant" if liste[0].bloquant else "        "
        modules = sorted({d.module for d in liste})
        lignes.append(
            f"  {marque}  {genre:34s} {len(liste):3d}  {', '.join(modules[:3])}"
            + (" ..." if len(modules) > 3 else "")
        )
    return "\n".join(lignes) + "\n"


def main(argv: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--check", action="store_true", help="échouer sur un défaut bloquant")
    parseur.add_argument("--json", action="store_true", help="sortir la mesure en JSON")
    parseur.add_argument(
        "--details", action="store_true", help="nommer chaque défaut, page par page"
    )
    arguments = parseur.parse_args(argv[1:])

    try:
        mesure, defauts = mesurer()
    except QualiteError as erreur:
        print(f"erreur : {erreur}", file=sys.stderr)
        return 1

    if arguments.json:
        print(
            json.dumps(
                {
                    "modules": mesure.modules,
                    "options": [mesure.options_decrites, mesure.options],
                    "retours": [mesure.retours_decrits, mesure.retours],
                    "retours_detailles": [mesure.retours_detailles, mesure.retours_composites],
                    "champs": [mesure.champs_decrits, mesure.champs],
                    "exemples": [mesure.exemples_copiables, mesure.exemples],
                    "defauts": [{**vars(d), "bloquant": d.bloquant} for d in defauts],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(rendre(mesure, defauts))
    if arguments.details:
        for defaut in defauts:
            print(f"  {defaut.module:32s} {defaut.genre:34s} {defaut.detail}")

    if arguments.check:
        bloquants = [d for d in defauts if d.bloquant]
        if bloquants:
            print(
                f"{len(bloquants)} défaut(s) bloquant(s) : cette documentation n'est pas\n"
                "publiable. Un lecteur de Galaxy doit comprendre le module depuis sa\n"
                "seule page, sans lire le contrat ni le code.\n"
                "Chacun se répare dans le générateur, jamais dans le fichier produit ;\n"
                "`python scripts/docs_quality.py --details` les nomme un par un.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
