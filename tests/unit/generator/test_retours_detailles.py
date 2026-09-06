"""Le RETURN dit ce qu'il y a dans la ressource, pas seulement son nom.

Un module d'information publiait :

    vms:
      description: The vms.
      returned: always
      type: list
      elements: dict

Un lecteur de la page Galaxy ne savait pas ce qu'il pouvait lire dans
`result.vms`. Il fallait appeler le module, ou aller au contrat OpenAPI, ce que
la page publiée doit précisément éviter. Le contrat le disait pourtant : `Vm`
déclare 38 champs, tous décrits. La connaissance existait et s'arrêtait au
parser.
"""

from __future__ import annotations

from generator.ansible.collection import Collection
from generator.ansible.models import (
    DEPRECATED_NOTICE,
    UNDOCUMENTED,
    AnsibleModuleSpec,
    _fields_of,
    build_module_specs,
)
from generator.ir.enums import ApiType
from generator.ir.models import ApiField, ApiObject, ApiService
from generator.overrides.loader import OverrideSet
from generator.plan import ProductPlan, build_plan

from .conftest import LAB_COLLECTION, OUTSCALE_SPECS


def _specs(plan: ProductPlan, collection: Collection) -> dict[str, AnsibleModuleSpec]:
    specs, _ = build_module_specs(plan, collection)
    return {spec.name: spec for spec in specs}


# ---- l'IR ---------------------------------------------------------------------


def test_lir_porte_les_champs_des_ressources_rendues(widget_service: ApiService) -> None:
    """Une fois par schéma, et seulement pour ce qu'une réponse désigne.

    `Tag` est référencé par `Widget.Tags` et n'est rendu par aucune réponse :
    il n'y est pas. Recopier les schémas du contrat ferait un IR que personne
    ne relit en diff, et le golden est ce qui rend la dérive visible.
    """
    noms = {objet.name for objet in widget_service.objects}
    assert {"Widget", "ReadWidgetsResponse", "StartWidgetsResponse", "WidgetState"} <= noms
    assert "Tag" not in noms
    assert "WidgetPerformance" not in noms

    widget = widget_service.object("Widget")
    assert widget is not None
    champs = {champ.name: champ for champ in widget.fields}
    assert champs["State"].description == (
        "The state of the widget (`pending` | `running` | `stopped`)."
    )
    assert champs["Tags"].type is ApiType.ARRAY
    assert champs["Tags"].item_type is ApiType.OBJECT
    assert champs["Tags"].ref == "Tag"


def test_lenveloppe_ne_porte_ni_le_contexte_ni_le_jeton_de_page(
    widget_service: ApiService,
) -> None:
    """`ResponseContext` n'est jamais la ressource, et le runtime déroule les pages."""
    enveloppe = widget_service.object("ReadWidgetsResponse")
    assert enveloppe is not None
    assert [champ.name for champ in enveloppe.fields] == ["Widgets"]


def test_une_ressource_inconnue_ne_produit_aucun_champ(widget_service: ApiService) -> None:
    """Un `contains` inventé décrirait une réponse que personne n'a lue."""
    assert widget_service.object("Inexistant") is None
    assert widget_service.object(None) is None


# ---- ce que chaque classe de module publie -------------------------------------


def test_le_retour_dun_module_dinformation_liste_ses_champs(widget_plan: ProductPlan) -> None:
    spec = _specs(widget_plan, LAB_COLLECTION)["widget_info"]
    champs = {c.name for c in spec.contains["widgets"]}
    assert {"WidgetId", "State", "WidgetType", "Performance", "Tags"} == champs


def test_le_retour_dun_module_de_gestion_liste_ses_champs(widget_plan: ProductPlan) -> None:
    """La ressource écrite est celle qu'on relit : mêmes champs, même schéma."""
    spec = _specs(widget_plan, LAB_COLLECTION)["widget"]
    assert {c.name for c in spec.contains["widget"]} >= {"WidgetId", "State"}
    assert spec.contains.get("changes", ()) == ()


def test_le_retour_dune_action_descend_dun_niveau(widget_plan: ProductPlan) -> None:
    """`result` est l'enveloppe ; la ressource qu'elle porte est un champ.

    C'est un niveau plus bas que le lecteur trouve ce qu'un `WidgetState`
    contient, et chaque champ dit après quelles actions il est rendu :
    `RebootWidgets` ne rend rien.
    """
    spec = _specs(widget_plan, LAB_COLLECTION)["widget_action"]
    (widgets,) = spec.contains["result"]
    assert widgets.name == "Widgets"
    assert widgets.returned == "after C(start), C(stop)"
    assert {c.name for c in widgets.contains} == {"WidgetId", "CurrentState", "PreviousState"}


def test_une_charge_utile_indecidable_liste_les_champs_de_lenveloppe(
    widget_plan: ProductPlan,
) -> None:
    """`ReadWidgetSecret` rend deux propriétés : le module rend la réponse entière,
    et la page dit ce qu'elle contient."""
    spec = _specs(widget_plan, LAB_COLLECTION)["widget_secret_info"]
    assert {c.name for c in spec.contains["widget_secret"]} == {"Secret", "WidgetId"}


def test_le_contains_se_rend_en_documentation_ansible(widget_plan: ProductPlan) -> None:
    """`ansible-test sanity` juge la forme ; ce test juge qu'elle est remplie."""
    rendu = _specs(widget_plan, LAB_COLLECTION)["widget_action"].return_documentation()
    widgets = rendu["result"]["contains"]["Widgets"]
    assert set(widgets) >= {"description", "returned", "type", "elements", "contains"}
    assert set(widgets["contains"]["WidgetId"]) >= {"description", "returned", "type"}
    assert "contains" not in rendu["states"]


# ---- d'où vient la phrase --------------------------------------------------------


def test_la_phrase_vient_du_contrat_puis_de_loverride_puis_du_repli(
    widget_plan: ProductPlan,
) -> None:
    """Trois étages sur le laboratoire : `State` est décrit par le contrat,
    `WidgetType` par un override avec sa raison, `Performance` par personne."""
    spec = _specs(widget_plan, LAB_COLLECTION)["widget_info"]
    champs = {c.name: c.description for c in spec.contains["widgets"]}
    assert champs["State"] == ("The state of the widget (C(pending) | C(running) | C(stopped)).",)
    assert champs["WidgetType"] == ("The type of the widget.",)
    assert champs["Performance"] == (UNDOCUMENTED,)


def test_aucun_champ_publie_par_la_collection_ne_porte_le_repli() -> None:
    """Mesuré sur le contrat 1.42.0 : 258 champs sur 30 schémas, tous décrits.

    Le jour où un champ arrive muet, la porte documentaire refuse la page, et
    la section `returns` des overrides est l'endroit où décider sa phrase.
    """
    from generator.source.base import DEFAULT_SPEC_ROOT, read_products

    fautifs = []
    for entree in read_products(DEFAULT_SPEC_ROOT):
        plan = build_plan(entree.product, entree.version, spec_root=OUTSCALE_SPECS)
        for nom, spec in _specs(plan, LAB_COLLECTION).items():
            for cle, champs in spec.contains.items():
                for champ in champs:
                    if UNDOCUMENTED in champ.description:
                        fautifs.append(f"{nom}.{cle}.{champ.name}")
    assert fautifs == [], fautifs[:10]


def test_un_champ_deprecie_le_dit() -> None:
    """L'information existait pour les paramètres et se perdait pour les champs rendus."""
    service = ApiService(
        name="lab",
        version="v1",
        objects=(
            ApiObject(
                "Thing",
                (ApiField("Old", ApiType.STRING, description="Old field.", deprecated=True),),
            ),
        ),
    )
    (champ,) = _fields_of(service, "Thing", OverrideSet(source=None))
    assert champ.description == ("Old field.", DEPRECATED_NOTICE)


def test_les_phrases_de_deux_enveloppes_sortent_chacune_avec_son_action() -> None:
    """`StartVms` dit « started VMs », `StopVms` dit « stopped VMs ».

    En garder une ferait dire « started » d'un arrêt ; les deux sortent, chacune
    avec son action. Mesuré sur le contrat réel, le laboratoire ne le reproduit
    pas.
    """
    plan = build_plan("vm", "v1", spec_root=OUTSCALE_SPECS)
    (vms,) = _specs(plan, LAB_COLLECTION)["vm_action"].contains["result"]
    assert vms.description == (
        "After C(start): Information about one or more started VMs.",
        "After C(stop): Information about one or more stopped VMs.",
    )


def test_une_liste_de_chaines_est_dite_comme_telle() -> None:
    """`ReadPublicIpRanges` rend des chaînes, et la page disait `elements: dict`."""
    plan = build_plan("public_ip", "v1", spec_root=OUTSCALE_SPECS)
    spec = _specs(plan, LAB_COLLECTION)["public_ip_range_info"]
    assert spec.list_elements == "str"
    assert spec.return_documentation()["public_ip_ranges"]["elements"] == "str"
    assert spec.contains["public_ip_ranges"] == ()
