"""Ce que la porte documentaire mesure, et ce qu'elle refuse de laisser publier.

`ansible-test sanity` dit qu'un bloc `DOCUMENTATION` est bien formé. Il ne dit
rien de ce qu'il apprend à quelqu'un : un module dont l'exemple filtre sur une
clé que le schéma ne porte pas, ou qui écrit « vm » dans une phrase de
référence, passe la sanity sans une remarque et se publie tel quel.

Ces tests portent sur des pages écrites ici, pas sur celles du dépôt : une
porte qui ne mesurerait plus rien le jour où la collection change n'est pas
une porte. Deux tests lisent le dépôt, et le disent.
"""

from __future__ import annotations

from pathlib import Path

import docs_quality
import pytest

from generator.ansible.collection import load_collection

EN_TETE = '#!/usr/bin/python\n"""Module de test."""\n\n'

BON_EXEMPLE = """
- name: List things
  demo.demo.demo_thing_info:
    region: eu-west-2
  register: result
"""

BON_RETOUR = """
things:
  description: The things.
  returned: always
  type: list
  elements: dict
  contains:
    ThingId:
      description:
      - The ID of the thing.
      returned: when the API returns it
      type: str
"""

BONNE_DOC = """
module: demo_thing_info
short_description: Gather information about Outscale things
description:
- List Outscale things, optionally filtered. This module never changes anything.
options:
  filters:
    description: 'One or more filters. Accepted keys: C(Tags), C(ThingIds).'
    type: dict
"""


def _page(
    dossier: Path,
    nom: str,
    documentation: str = BONNE_DOC,
    exemples: str = BON_EXEMPLE,
    retour: str = BON_RETOUR,
    operations: str = "",
) -> Path:
    chemin = dossier / f"{nom}.py"
    en_tete = EN_TETE + (f"# Opérations : {operations}\n\n" if operations else "")
    chemin.write_text(
        f'{en_tete}DOCUMENTATION = r"""{documentation}"""\n\n'
        f'EXAMPLES = r"""{exemples}"""\n\n'
        f'RETURN = r"""{retour}"""\n',
        encoding="utf-8",
    )
    return chemin


def _genres(chemin: Path) -> set[str]:
    _, defauts = docs_quality.examiner(chemin)
    return {d.genre for d in defauts if d.bloquant}


def test_une_page_sans_defaut_ne_bloque_rien(tmp_path: Path) -> None:
    """Une porte qui refuse tout ne mesure plus rien : elle mesure sa panne."""
    assert _genres(_page(tmp_path, "demo_thing_info")) == set()


def test_un_repli_de_description_est_bloquant(tmp_path: Path) -> None:
    """La phrase de repli est publiée telle quelle, et Galaxy ne se reprend pas."""
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        documentation=f"""
module: demo_thing_info
short_description: Gather information about Outscale things
description:
- List Outscale things.
options:
  thing_id:
    description: {docs_quality.REPLI}
    type: str
""",
    )
    assert "option-sans-description" in _genres(chemin)


def test_un_exemple_a_trou_est_bloquant(tmp_path: Path) -> None:
    """`vm_id: <vm_id>` n'est pas du YAML qu'on copie, c'est un formulaire vide."""
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        exemples="""
- name: List things
  demo.demo.demo_thing_info:
    region: <region>
  register: result
""",
    )
    assert "exemple-non-copiable" in _genres(chemin)


def test_une_page_qui_ne_dit_pas_ce_quelle_fait_est_bloquante(tmp_path: Path) -> None:
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        documentation="""
module: demo_thing_info
short_description: Gather information about Outscale things
options: {}
""",
    )
    assert "description-absente" in _genres(chemin)


def test_une_action_que_le_module_refuse_ne_doit_pas_etre_citee(tmp_path: Path) -> None:
    """L'`argument_spec` fait foi : citer davantage promet ce qu'il refuse."""
    chemin = _page(
        tmp_path,
        "demo_thing_action",
        documentation="""
module: demo_thing_action
short_description: Perform an action on Outscale things
description:
- 'Trigger one of the following actions on existing things: C(reboot), C(terminate).'
options:
  action:
    description: The action to trigger on the things.
    type: str
    choices: [reboot]
""",
    )
    _, defauts = docs_quality.examiner(chemin)
    fautes = [d for d in defauts if d.genre == "action-exclue-documentee"]
    assert fautes and fautes[0].bloquant
    assert "terminate" in fautes[0].detail


def test_le_vocabulaire_des_identifiants_dans_une_phrase_est_bloquant(tmp_path: Path) -> None:
    """« Manage the settings of an Outscale vm » : `vm` est un identifiant, pas un mot.

    Le contrat écrit VM dans ses propres phrases, et une page de référence
    doit faire pareil.
    """
    chemin = _page(
        tmp_path,
        "demo_thing",
        documentation="""
module: demo_thing
short_description: Manage the settings of an Outscale vm
description:
- Set the settings of a thing.
options: {}
""",
    )
    _, defauts = docs_quality.examiner(chemin)
    fautes = [d for d in defauts if d.genre == "vocabulaire-du-contrat"]
    assert fautes and fautes[0].bloquant
    assert "attendu : VM" in fautes[0].detail


def test_un_nom_dans_le_marquage_dansible_nest_pas_du_vocabulaire(tmp_path: Path) -> None:
    """`C(id)` cite la valeur d'une option : la juger comme un mot serait un faux positif.

    Mesuré sur le plugin d'inventaire, dont `hostnames` accepte la valeur
    `id` : le premier détecteur l'a signalée, à tort.
    """
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        documentation="""
module: demo_thing_info
short_description: Gather information about Outscale things
description:
- Accepts C(id), I(vm_id) and L(VM Types, https://docs.example.invalid/vm-types.html).
options: {}
""",
    )
    assert "vocabulaire-du-contrat" not in _genres(chemin)


def test_un_exemple_nomme_par_le_contrat_est_bloquant(tmp_path: Path) -> None:
    """`Run ReadVms` nomme l'appel du SDK, pas ce que la tâche fait.

    Le nom reste dans la sortie d'Ansible de qui copie la tâche. Les
    identifiants viennent de l'en-tête que le renderer écrit, jamais d'une
    liste tenue ici.
    """
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        exemples="""
- name: Call ReadThings
  demo.demo.demo_thing_info:
    region: eu-west-2
  register: result
""",
        operations="ReadThings",
    )
    assert "exemple-nomme-par-le-contrat" in _genres(chemin)


def test_un_exemple_nomme_par_le_verbe_du_sdk_est_bloquant(tmp_path: Path) -> None:
    """« Run reboot on a thing » : c'est ce que les modules d'action publiaient."""
    chemin = _page(
        tmp_path,
        "demo_thing_action",
        exemples="""
- name: Run reboot on a thing
  demo.demo.demo_thing_action:
    region: eu-west-2
    action: reboot
""",
    )
    assert "exemple-nomme-par-le-contrat" in _genres(chemin)


def test_une_cle_de_filtre_que_loption_naccepte_pas_est_bloquante(tmp_path: Path) -> None:
    """Cinq lectures publiaient `Tags` sur un schéma `Filters` qui ne le porte pas.

    Copiable, et refusé par l'API. La page porte les deux, l'exemple et la
    liste des clés acceptées : elle peut se juger seule.
    """
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        documentation="""
module: demo_thing_info
short_description: Gather information about Outscale things
description:
- List Outscale things.
options:
  filters:
    description: 'One or more filters. Accepted keys: C(ThingIds), C(ThingNames).'
    type: dict
""",
        exemples="""
- name: List things matching a tag
  demo.demo.demo_thing_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
""",
    )
    _, defauts = docs_quality.examiner(chemin)
    fautes = [d for d in defauts if d.genre == "exemple-cle-de-filtre-inconnue"]
    assert fautes and fautes[0].bloquant
    assert "Tags" in fautes[0].detail


def test_un_champ_de_retour_sans_description_est_bloquant_a_tous_les_niveaux(
    tmp_path: Path,
) -> None:
    """La surface publiée s'est élargie aux champs ; la mesure aussi.

    collection-scaleway a laissé partir cent replis dans ses `RETURN` parce
    que sa porte ne regardait que les clés de premier niveau. Ici les
    enveloppes d'action descendent d'un niveau de plus, et il se compte.
    """
    chemin = _page(
        tmp_path,
        "demo_thing_action",
        retour=f"""
result:
  description: The API response of the action.
  returned: when the action was sent
  type: dict
  contains:
    Things:
      description:
      - Information about the things.
      returned: after C(start)
      type: list
      elements: dict
      contains:
        ThingId:
          description:
          - The ID of the thing.
          returned: when the API returns it
          type: str
        Colour:
          description:
          - {docs_quality.REPLI}
          returned: when the API returns it
          type: str
""",
    )
    mesure, defauts = docs_quality.examiner(chemin)
    assert mesure.champs == 3 and mesure.champs_decrits == 2
    fautes = [d for d in defauts if d.genre == "champ-de-retour-sans-description"]
    assert fautes and fautes[0].bloquant
    assert "result.Things.Colour" in fautes[0].detail


def test_une_liste_de_chaines_na_rien_a_detailler(tmp_path: Path) -> None:
    """`ReadPublicIpRanges` rend des chaînes : lui reprocher l'absence de champs
    reprocherait au module d'être correct."""
    chemin = _page(
        tmp_path,
        "demo_thing_info",
        retour="""
things:
  description: The things.
  returned: always
  type: list
  elements: str
""",
    )
    mesure, _ = docs_quality.examiner(chemin)
    assert mesure.retours == 1
    assert mesure.retours_composites == 0
    assert mesure.sans_detail == []


def test_les_exemples_dun_plugin_sont_des_fichiers_entiers(tmp_path: Path) -> None:
    """On copie un fichier d'inventaire, pas une tâche.

    Ils sont donc séparés par `---`, et `safe_load` ne rend que le premier :
    mesurer avec lui laisserait les autres hors de la mesure.
    """
    chemin = tmp_path / "demo.py"
    chemin.write_text(
        EN_TETE + 'DOCUMENTATION = r"""\nname: demo\nshort_description: Read things\n'
        'description:\n  - Read things.\noptions: {}\n"""\n\n'
        'EXAMPLES = r"""\nplugin: demo.demo.demo\n\n---\nplugin: demo.demo.demo\n'
        'regions:\n  - eu-west-2\n"""\n\nRETURN = r"""\n"""\n',
        encoding="utf-8",
    )
    mesure, _ = docs_quality.examiner(chemin)
    assert mesure.exemples == 2, "le second document d'exemple n'est pas mesuré"


def test_une_mesure_sur_zero_page_est_une_erreur(tmp_path: Path) -> None:
    """Zéro défaut sur zéro page est un vert qui ne dit rien.

    C'est le défaut qui a rendu un `ansible-test sanity` vert sur zéro fichier
    examiné : le compte rendu ne distinguait pas « rien à redire » de « rien
    mesuré ».
    """
    (tmp_path / "plugins" / "modules").mkdir(parents=True)
    with pytest.raises(docs_quality.QualiteError, match="aucune page"):
        docs_quality.mesurer(tmp_path)


def test_la_porte_mesure_bien_la_collection_livree() -> None:
    """La collection publiée ne porte aucun défaut bloquant.

    Ce test regarde le dépôt et pas une fixture, et c'est voulu : les autres
    prouvent que la porte sait refuser ; celui-ci dit ce qu'elle mesure
    aujourd'hui sur ce qui partirait chez Galaxy.
    """
    mesure, defauts = docs_quality.mesurer()
    bloquants = [f"{d.module} : {d.genre} ({d.detail})" for d in defauts if d.bloquant]
    assert bloquants == [], "\n".join(bloquants)
    assert mesure.modules > 0


def test_le_plugin_dinventaire_entre_dans_la_mesure() -> None:
    """C'est la page qu'un utilisateur lit en premier.

    Le nombre attendu vient du disque, pas d'un chiffre écrit ici : un module
    de plus ne doit pas rougir ce test, un plugin oublié doit le rougir.
    """
    collection = load_collection()
    modules = [p for p in collection.modules_dir.glob("*.py") if not p.stem.startswith("_")]
    plugins = [
        p
        for p in (collection.path / "plugins" / "inventory").glob("*.py")
        if not p.stem.startswith("_")
    ]
    assert plugins, "aucun plugin d'inventaire : la mesure ne prouverait rien"
    mesure, _ = docs_quality.mesurer()
    assert mesure.modules == len(modules) + len(plugins)
