"""Ce qu'un fichier publié dérive, et ce qu'il ne recopie plus.

Sur Galaxy, la page d'une collection annonce sa version et propose des liens
vers le dépôt. Un lien vers `main` mène aux fichiers d'aujourd'hui, et rien
sur la page ne le dit au lecteur d'une version publiée il y a six mois. Les
nombres et les versions se dérivent de la même façon : une table de
compatibilité qui dit `0.1.x` sur une page en `0.2.0` se lit comme une mesure,
et c'est un texte hérité.

Les fonctions s'exercent sur des textes fabriqués : un test qui lirait l'état
du dépôt resterait vert sur une fonction cassée, puisque les fichiers portent
déjà la bonne valeur. Deux tests lisent le dépôt malgré tout, et le disent.
"""

from __future__ import annotations

from pathlib import Path

import docs_quality
import pytest
import readme_counters

DEPOT = "https://github.com/lab/collection-widget"


def test_un_lien_du_depot_prend_la_version_publiee() -> None:
    reecrit = readme_counters.versionner_les_liens(
        f"voir {DEPOT}/tree/main/docs et {DEPOT}/blob/main/LICENSE\n", DEPOT, "9.9.9"
    )
    assert f"{DEPOT}/tree/9.9.9/docs" in reecrit
    assert f"{DEPOT}/blob/9.9.9/LICENSE" in reecrit


def test_un_lien_vers_un_autre_projet_nest_pas_reecrit() -> None:
    """Un lien vers un autre dépôt désigne une référence qui lui appartient.

    Une substitution qui prendrait toutes les URL GitHub ferait pointer un
    lien d'`ansible-collections` sur un tag de **ce** dépôt, dans un dépôt qui
    ne le porte pas.
    """
    texte = (
        "voir https://github.com/ansible-collections/ansible-inclusion/blob/main/x.md\n"
        f"et {DEPOT}/blob/main/docs/y.md\n"
    )
    reecrit = readme_counters.versionner_les_liens(texte, DEPOT, "9.9.9")
    assert "ansible-inclusion/blob/main/" in reecrit
    assert f"{DEPOT}/blob/9.9.9/" in reecrit


def test_une_cible_sans_liens_laisse_le_texte(tmp_path: Path) -> None:
    fichier = tmp_path / "x.md"
    texte = f"{DEPOT}/tree/main/docs\n"
    assert readme_counters.attendu(fichier, texte, readme_counters.Cible()) == texte


def test_une_cible_reecrit_ses_blocs_nommes_et_ses_liens(tmp_path: Path) -> None:
    """Un fichier, pas une catégorie : chaque fichier dit ce qu'il porte."""
    fichier = tmp_path / "README.md"
    debut, fin = readme_counters._marqueurs("versioning")
    texte = f"# Titre\n\n{debut}\nancien\n{fin}\n\n{DEPOT}/blob/main/LICENSE\n"
    cible = readme_counters.Cible(nommes=(("versioning", "nouveau"),), liens=(DEPOT, "2.0.0"))
    resultat = readme_counters.attendu(fichier, texte, cible)
    assert f"{debut}\nnouveau\n{fin}" in resultat
    assert "ancien" not in resultat
    assert f"{DEPOT}/blob/2.0.0/LICENSE" in resultat


def test_un_bloc_nomme_reclame_a_un_fichier_qui_ne_le_porte_pas_est_une_erreur(
    tmp_path: Path,
) -> None:
    fichier = tmp_path / "README.md"
    cible = readme_counters.Cible(nommes=(("versioning", "x"),))
    with pytest.raises(readme_counters.CompteursError, match="marqueurs"):
        readme_counters.attendu(fichier, "# Sans marqueurs\n", cible)


def test_le_bloc_derive_publie_la_qualite_documentaire() -> None:
    """Un chiffre qui ne sort nulle part est un chiffre que personne ne surveille.

    Cinq filtres publiés que l'API refuse et cinquante-sept identifiants en
    minuscules étaient invisibles depuis le README, qui comptait pourtant les
    modules, les tests et les gardes.
    """
    mesure = docs_quality.Mesure(
        modules=3,
        options=10,
        options_decrites=9,
        retours=4,
        retours_decrits=4,
        retours_composites=4,
        retours_detailles=3,
        champs=40,
        champs_decrits=39,
        exemples=8,
        exemples_copiables=7,
    )
    lignes = "\n".join(readme_counters.lignes_qualite(mesure))
    assert "3 published pages" in lignes
    assert "9/10 options" in lignes
    assert "39/40 returned fields documented" in lignes
    assert "7/8 examples copyable as is" in lignes
    assert "3/4 returned keys list their fields" in lignes


class _Collection:
    def __init__(self, version: str, chemin: Path) -> None:
        self.version = version
        self.path = chemin
        self.fqcn = "lab.widget"


def test_la_table_de_compatibilite_suit_la_version_et_la_matrice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La série vient de `galaxy.yml`, les versions d'ansible-core de la matrice
    dérivée, l'exigence sur le SDK du fragment de documentation : rien n'est
    recopié."""
    fragments = tmp_path / "plugins" / "doc_fragments"
    fragments.mkdir(parents=True)
    (fragments / "outscale.py").write_text(
        'DOCUMENTATION = r"""\nrequirements:\n  - osc-sdk-python >= 0.42 (the SDK)\n"""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(readme_counters, "load_collection", lambda: _Collection("3.4.5", tmp_path))
    monkeypatch.setattr(
        readme_counters.ansible_matrix, "expected", lambda: [">=2.17,<2.18", ">=2.18,<2.19"]
    )
    table = readme_counters.bloc_compatibilite()
    assert "| 3.4.x | 2.17, 2.18 | `osc-sdk-python>=0.42` |" in table


def test_les_exemples_de_versionnement_se_comptent_depuis_la_version_publiee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Illustrer un correctif par `0.1.1` sur une page en 0.2.0 se lit comme un texte hérité."""
    monkeypatch.setattr(readme_counters, "load_collection", lambda: _Collection("3.4.5", tmp_path))
    bloc = readme_counters.bloc_versionnement()
    assert "`3.4.6`" in bloc and "`3.5.0`" in bloc and "`4.0.0`" in bloc


def test_aucun_lien_de_ce_depot_ne_pointe_sur_une_branche() -> None:
    """`main` bouge, une version publiée non : les deux ne peuvent pas coïncider.

    Ce test lit le dépôt, et c'est voulu : il dit ce que les fichiers publiés
    portent aujourd'hui. Le test de la substitution, lui, est au-dessus.
    """
    collection = readme_counters.load_collection()
    motif = readme_counters.lien_du_depot(readme_counters._depot(collection))
    fautifs = [
        f"{fichier.name} : {lien.group(0)}"
        for fichier in readme_counters.fichiers_publies(collection)
        for lien in motif.finditer(fichier.read_text(encoding="utf-8"))
        if lien.group(2) != collection.version
    ]
    assert fautifs == [], f"liens non versionnés : {fautifs}"


def test_chaque_bloc_nomme_a_ses_marqueurs_dans_son_fichier() -> None:
    """Un bloc réclamé au mauvais fichier fait échouer le contrôle pour rien.

    Ce test lit le dépôt : il dit que chaque fichier publié porte les
    marqueurs des blocs qu'on lui réclame, et pas ceux des autres. Il lit le
    listing et non `cibles()`, qui calcule les blocs et a besoin des comptes
    rendus de `build/` : la copie hors dépôt de la falsification ne les
    emporte pas, et le test échouerait faute d'artefact, ce qui ressemble
    exactement à une garde prouvée.
    """
    collection = readme_counters.load_collection()
    for fichier, nommes in readme_counters.fichiers_publies(collection).items():
        texte = fichier.read_text(encoding="utf-8")
        for nom in readme_counters.NOMMES:
            debut, fin = readme_counters._marqueurs(nom)
            porte = debut in texte and fin in texte
            reclame = nom in nommes
            etat = "présent" if porte else "absent"
            attendu = "réclamé" if reclame else "pas réclamé"
            assert porte == reclame, f"le bloc {nom!r} est {etat} dans {fichier.name}, et {attendu}"
