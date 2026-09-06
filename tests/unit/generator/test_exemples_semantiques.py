"""Un exemple par chose que le module sait faire, pas un par opération HTTP.

Lire, lister, filtrer ; écrire, et simuler l'écriture ; déclencher chaque
action. Ce qui manquait est ce qu'un opérateur vient chercher sur la page, et
ce qui était en trop était faux : cinq lectures montraient un filtre `Tags`
que leur schéma `Filters` ne porte pas.
"""

from __future__ import annotations

from generator.ansible.models import (
    EXAMPLE_PUBLIC_IP,
    EXAMPLE_TAG,
    AnsibleModuleSpec,
    _article,
    _id_filter_key,
    _valeur_par_convention,
    build_module_specs,
)
from generator.ir.enums import OperationKind
from generator.plan import ProductPlan, build_plan
from generator.renderer.modules import _yaml_block, render_module

from .conftest import LAB_COLLECTION, OUTSCALE_SPECS


def _specs(plan: ProductPlan) -> dict[str, AnsibleModuleSpec]:
    specs, _ = build_module_specs(plan, LAB_COLLECTION)
    return {spec.name: spec for spec in specs}


def _taches(spec: AnsibleModuleSpec) -> list[dict]:  # type: ignore[type-arg]
    return spec.examples_documentation()


# ---- lire, lister, filtrer -------------------------------------------------------


def test_une_lecture_montre_comment_lire_par_identifiant(widget_plan: ProductPlan) -> None:
    """La clé vient du schéma `Filters`, jamais d'une habitude : `WidgetIds`."""
    taches = _taches(_specs(widget_plan)["widget_info"])
    lecture = next(t for t in taches if t["name"] == "Read widgets by ID")
    assert lecture["lab.widget.widget_info"]["filters"] == {"WidgetIds": ["example-id"]}


def test_un_filtre_par_tag_ne_se_montre_que_si_le_schema_le_porte(
    widget_plan: ProductPlan, gadget_plan: ProductPlan
) -> None:
    """`FiltersWidget` porte `Tags`, `FiltersGadget` et `FiltersWidgetType` non.

    Publier `Tags: [role=web]` sur les trois était copiable et faux pour deux.
    """
    par_nom = {
        nom: [t["name"] for t in _taches(spec)]
        for plan in (widget_plan, gadget_plan)
        for nom, spec in _specs(plan).items()
        if nom.endswith("_info")
    }
    assert "List widgets matching a tag" in par_nom["widget_info"]
    assert par_nom["gadget_info"] == ["List gadgets", "Read gadgets by ID"]
    assert par_nom["widget_type_info"] == ["List widget types"]


def test_les_cles_de_filtre_dun_exemple_sont_celles_de_loption() -> None:
    """Sur les 22 produits réels : aucune tâche ne filtre sur une clé que la page
    ne déclare pas accepter."""
    from generator.source.base import DEFAULT_SPEC_ROOT, read_products

    fautifs = []
    for entree in read_products(DEFAULT_SPEC_ROOT):
        plan = build_plan(entree.product, entree.version, spec_root=OUTSCALE_SPECS)
        for nom, spec in _specs(plan).items():
            for tache in _taches(spec):
                corps = tache[LAB_COLLECTION.module_fqcn(nom)]
                for cle in corps.get("filters", {}):
                    if cle not in spec.filter_keys:
                        fautifs.append(f"{nom} : {cle}")
    assert fautifs == []


def test_la_cle_didentifiant_vient_du_schema_ou_de_rien() -> None:
    assert _id_filter_key("vm", ("Tags", "VmIds", "NetIds")) == "VmIds"
    assert _id_filter_key("vm_state", ("VmIds", "SubregionNames")) == "VmIds"
    assert _id_filter_key("tag", ("Keys", "ResourceIds", "Values")) == "ResourceIds"
    assert _id_filter_key("vm_type", ("VmTypeNames", "Gpus")) is None
    assert _id_filter_key("security_group", ("NetIds", "AccountIds")) is None


# ---- écrire, et simuler ----------------------------------------------------------


def test_un_module_de_gestion_montre_le_mode_simulation(widget_plan: ProductPlan) -> None:
    """Ses notes en parlent depuis le premier module, aucune tâche ne le montrait.

    C'est pourtant ce qu'on fait avant d'écrire sur un parc qu'on ne possède
    pas seul, et `diff` est ce qui rend la comparaison lisible plutôt que de
    rendre un `changed` sans contenu.
    """
    ecriture, simulation = _taches(_specs(widget_plan)["widget"])
    assert simulation["check_mode"] is True and simulation["diff"] is True
    assert "check_mode" not in ecriture


def test_lexemple_de_simulation_porte_les_memes_parametres(widget_plan: ProductPlan) -> None:
    """Une simulation qui n'écrit pas la même chose ne simule rien."""
    ecriture, simulation = _taches(_specs(widget_plan)["widget"])
    assert simulation["lab.widget.widget"] == ecriture["lab.widget.widget"]


def test_le_rendu_nemet_jamais_dancre_yaml(widget_plan: ProductPlan) -> None:
    """La garde vit dans le sérialiseur, donc elle s'éprouve sur lui.

    Deux tâches qui partagent une valeur faisaient écrire `tags: &id001` à la
    première et `tags: *id001` à la seconde chez collection-scaleway : du YAML
    valide que personne ne peut copier séparément. Le modèle copie aujourd'hui
    ses paramètres, donc un module rendu ne suffit pas à prouver la garde : le
    sérialiseur reçoit ici un objet partagé, exprès.
    """
    partage = {"tags": ["production"]}
    bloc = _yaml_block([{"name": "a", "x": partage}, {"name": "b", "x": partage}])
    assert "&id" not in bloc and "*id" not in bloc, bloc
    assert bloc.count("- production") == 2
    rendu = render_module(_specs(widget_plan)["widget"], source="x")
    assert "&id" not in rendu and "*id" not in rendu, rendu


def test_lexemple_dun_module_de_gestion_prefere_un_scalaire_a_un_dictionnaire() -> None:
    """`actions_on_next_boot: {}` n'apprend rien à qui lit l'exemple.

    Quand aucune valeur plus sûre n'existe (override, enum, booléen, convention
    de nom), un entier ou une chaîne passe avant un dictionnaire ou une liste.
    """
    spec = AnsibleModuleSpec(
        name="thing",
        kind=OperationKind.MANAGE,
        product="thing",
        resource="thing",
        collection=LAB_COLLECTION,
        options={
            "thing_id": {"type": "str", "required": True},
            "mappings": {"type": "dict"},
            "size": {"type": "int"},
            "codes": {"type": "list", "elements": "str"},
        },
        option_docs={},
        compare={"mappings": "Mappings", "size": "Size", "codes": "Codes"},
    )
    assert spec._setting_for_example() == "size"


def test_larticle_precede_le_nom_de_la_ressource() -> None:
    """« Set the settings of a image » sortait sur `image`."""
    assert _article("image") == "an"
    assert _article("internet service") == "an"
    assert _article("IP") == "an"
    assert _article("VM") == "a"
    assert _article("NIC") == "a"


def test_une_chaine_libre_prend_une_valeur_par_convention_de_nom() -> None:
    """Ce n'est pas une affirmation sur l'API : ces champs n'ont pas de vocabulaire."""
    assert _valeur_par_convention("public_ip") == EXAMPLE_PUBLIC_IP
    assert _valeur_par_convention("load_balancer_name") == "my-load-balancer"
    assert _valeur_par_convention("keypair_names") == ["my-keypair"]
    assert _valeur_par_convention("description") == "Managed by Ansible"
    assert _valeur_par_convention("volume_type") is None


def test_lexemple_du_load_balancer_reel_ne_publie_plus_example_id_comme_nom() -> None:
    plan = build_plan("load_balancer", "v1", spec_root=OUTSCALE_SPECS)
    ecriture, _ = _taches(_specs(plan)["load_balancer"])
    corps = ecriture[LAB_COLLECTION.module_fqcn("load_balancer")]
    assert corps["load_balancer_name"] == "my-load-balancer"
    assert "example-id" not in corps.values()


# ---- déclencher --------------------------------------------------------------------


def test_un_module_daction_montre_chaque_action(
    widget_plan: ProductPlan, gadget_plan: ProductPlan
) -> None:
    """« Run reboot on a vm » montrait une action sur trois."""
    widgets = [t["name"] for t in _taches(_specs(widget_plan)["widget_action"])]
    assert widgets == ["Reboot widgets", "Start widgets", "Stop widgets"]
    gadgets = [t["name"] for t in _taches(_specs(gadget_plan)["gadget_action"])]
    assert gadgets == ["Accept a gadget", "Reject a gadget"]


def test_aucun_exemple_ne_se_nomme_par_le_verbe_du_sdk(
    widget_plan: ProductPlan, gadget_plan: ProductPlan
) -> None:
    fautifs = [
        f"{nom} : {t['name']}"
        for plan in (widget_plan, gadget_plan)
        for nom, spec in _specs(plan).items()
        for t in _taches(spec)
        if t["name"].startswith("Run ")
    ]
    assert fautifs == []


def test_un_exemple_de_filtre_par_tag_a_la_forme_du_contrat(widget_plan: ProductPlan) -> None:
    """« in the following format: TAGKEY=TAGVALUE », dit le contrat des 21 `Tags`."""
    taches = _taches(_specs(widget_plan)["widget_info"])
    tag = next(t for t in taches if t["name"].endswith("matching a tag"))
    assert tag["lab.widget.widget_info"]["filters"] == {"Tags": [EXAMPLE_TAG]}
    assert "=" in EXAMPLE_TAG
