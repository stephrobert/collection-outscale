"""Le parser traduit le contrat sans rien perdre ni rien inventer."""

from __future__ import annotations

from generator.ir.enums import ApiType, HTTPMethod, ParameterLocation
from generator.ir.models import ApiService
from generator.parser.openapi import derive_resource, parse_document
from generator.source.base import VendoredSpecSource

from .conftest import WIDGET_SPECS


def test_toutes_les_operations_du_produit_sont_dans_lir(widget_service: ApiService) -> None:
    assert {operation.id for operation in widget_service.operations} == {
        "ReadWidgets",
        "ReadWidgetTypes",
        "ReadWidgetSecret",
        "ReadWidgetConsole",
        "CreateWidget",
        "DeleteWidgets",
        "UpdateWidget",
        "StartWidgets",
        "StopWidgets",
        "RebootWidgets",
        "LinkGadget",
    }


def test_les_regions_se_lisent_dans_lurl_du_serveur(widget_service: ApiService) -> None:
    """Le chemin ne porte pas la région : l'hôte la porte."""
    assert widget_service.regions == ("eu-west-2", "cloudgouv-eu-west-1")


def test_la_version_du_document_est_portee_par_le_service(widget_service: ApiService) -> None:
    assert widget_service.document_version == "9.9.9"


def test_tout_est_un_post_dont_le_corps_porte_les_parametres(widget_service: ApiService) -> None:
    operation = widget_service.operation("StartWidgets")
    assert operation is not None
    assert operation.http_method is HTTPMethod.POST
    assert operation.path == "/StartWidgets"
    assert {p.location for p in operation.parameters} == {ParameterLocation.BODY}


def test_required_du_corps_est_lu(widget_service: ApiService) -> None:
    """Le contrat déclare `required` sur 164 corps sur 236 : le parser s'en sert."""
    operation = widget_service.operation("StartWidgets")
    assert operation is not None
    ids = operation.parameter("WidgetIds")
    assert ids is not None
    assert ids.required is True
    assert ids.type is ApiType.ARRAY
    assert ids.item_type is ApiType.STRING
    assert operation.parameter("DryRun") is not None, "le parser ne décide pas : DryRun reste"


def test_un_objet_reference_porte_ses_proprietes(widget_service: ApiService) -> None:
    """Les 67 filtres de `FiltersVm` sont ce qui relie un sélecteur à sa lecture."""
    operation = widget_service.operation("ReadWidgets")
    assert operation is not None
    filters = operation.parameter("Filters")
    assert filters is not None
    assert filters.type is ApiType.OBJECT
    assert filters.ref == "FiltersWidget"
    assert filters.properties == ("CreationDates", "States", "Tags", "WidgetIds")


def test_la_pagination_est_portee_par_lir(widget_service: ApiService) -> None:
    """36 lectures sur 74 paginent par `NextPageToken`, requête et réponse ensemble."""
    paginee = widget_service.operation("ReadWidgets")
    entiere = widget_service.operation("ReadWidgetTypes")
    assert paginee is not None and entiere is not None
    assert paginee.is_paginated is True
    assert paginee.response is not None and paginee.response.page_token == "NextPageToken"
    assert entiere.is_paginated is False


def test_une_liste_sans_jeton_de_page_est_signalee_et_non_inventee(
    widget_service: ApiService,
) -> None:
    assert any("ReadWidgetTypes" in w and "jeton de page" in w for w in widget_service.warnings)


def test_le_contexte_de_reponse_nest_jamais_la_charge_utile(widget_service: ApiService) -> None:
    liste = widget_service.operation("ReadWidgets")
    assert liste is not None and liste.response is not None
    assert liste.response.payload_field == "Widgets"
    assert liste.response.payload_schema == "Widget"
    assert liste.response.is_list is True
    assert "Performance" in liste.response.payload_fields
    assert "ResponseContext" not in liste.response.payload_fields


def test_une_reponse_a_un_objet_est_la_ressource(widget_service: ApiService) -> None:
    update = widget_service.operation("UpdateWidget")
    assert update is not None and update.response is not None
    assert update.response.payload_field == "Widget"
    assert update.response.is_list is False
    assert update.response.payload_fields == (
        "Performance",
        "State",
        "Tags",
        "WidgetId",
        "WidgetType",
    )


def test_une_reponse_sans_charge_utile_ne_rend_que_laccuse(widget_service: ApiService) -> None:
    link = widget_service.operation("LinkGadget")
    assert link is not None and link.response is not None
    assert link.response.payload_field is None
    assert link.response.payload_fields == ()


def test_une_reponse_a_plusieurs_proprietes_est_signalee(widget_service: ApiService) -> None:
    """Reproduit `ReadAdminPassword` : deux propriétés, charge utile indécidable."""
    secret = widget_service.operation("ReadWidgetSecret")
    assert secret is not None and secret.response is not None
    assert secret.response.payload_field is None
    assert secret.response.payload_fields == ("Secret", "WidgetId")
    assert any("ReadWidgetSecret" in w and "2 propriétés" in w for w in widget_service.warnings)


def test_un_oneof_de_dates_est_une_chaine(widget_service: ApiService) -> None:
    """Les 15 `oneOf` du contrat réel sont tous `string(date) | string(date-time)` :
    des variantes d'un même type scalaire se lisent comme ce type, sans un mot.
    Un `oneOf` de types différents, lui, reste inconnu et se nomme."""
    assert not any("CreationDates" in w for w in widget_service.warnings)
    console = widget_service.operation("ReadWidgetConsole")
    assert console is not None
    weird = console.parameter("Weird")
    assert weird is not None and weird.type is ApiType.UNKNOWN
    assert any("ReadWidgetConsole.Weird" in w and "oneOf" in w for w in widget_service.warnings)


def test_un_enum_reference_est_enregistre_une_fois(widget_service: ApiService) -> None:
    names = [enum.name for enum in widget_service.enums]
    assert names == ["WidgetPerformance"]
    update = widget_service.operation("UpdateWidget")
    assert update is not None
    performance = update.parameter("Performance")
    assert performance is not None
    assert performance.type is ApiType.ENUM
    assert performance.enum_name == "WidgetPerformance"
    assert performance.enum_values == ("medium", "high", "highest")


def test_un_enum_inline_devient_des_choix(widget_service: ApiService) -> None:
    create = widget_service.operation("CreateWidget")
    assert create is not None
    boot = create.parameter("BootMode")
    assert boot is not None
    assert boot.type is ApiType.ENUM
    assert boot.enum_values == ("uefi", "legacy")
    assert boot.enum_name is None


def test_une_map_est_reconnue_et_un_champ_nullable_garde_son_type(
    widget_service: ApiService,
) -> None:
    update = widget_service.operation("UpdateWidget")
    assert update is not None
    options = update.parameter("Options")
    user_data = update.parameter("UserData")
    assert options is not None and options.type is ApiType.MAP
    assert user_data is not None and user_data.type is ApiType.STRING


def test_une_propriete_depreciee_porte_son_drapeau(widget_service: ApiService) -> None:
    update = widget_service.operation("UpdateWidget")
    assert update is not None
    legacy = update.parameter("LegacyFlag")
    assert legacy is not None and legacy.deprecated is True


def test_la_description_garde_le_premier_paragraphe(widget_service: ApiService) -> None:
    assert widget_service.description == "Un produit de test."


def test_la_ressource_se_deduit_de_lidentifiant_prive_de_son_verbe() -> None:
    assert derive_resource("ReadVms") == "vm"
    assert derive_resource("StartVms") == "vm"
    assert derive_resource("UpdateVm") == "vm"
    assert derive_resource("ReadVmTypes") == "vm_type"
    assert derive_resource("ReadVmsState") == "vm_state"
    assert derive_resource("CreateLoadBalancerListeners") == "load_balancer_listener"
    assert derive_resource("ReadAdminPassword") == "admin_password"
    assert derive_resource("AcceptNetPeering") == "net_peering"
    assert derive_resource("ReadDhcpOptions") == "dhcp_option"
    assert derive_resource("ReadPublicIpRanges") == "public_ip_range"


def test_un_identifiant_sans_ressource_ne_devient_pas_vide() -> None:
    assert derive_resource("Read") == "unknown"


def test_la_ressource_est_stable_entre_lecture_et_action(widget_service: ApiService) -> None:
    par_operation = {operation.id: operation.resource for operation in widget_service.operations}
    assert par_operation["ReadWidgets"] == "widget"
    assert par_operation["StartWidgets"] == "widget"
    assert par_operation["UpdateWidget"] == "widget"
    assert par_operation["ReadWidgetTypes"] == "widget_type"
    assert par_operation["ReadWidgetSecret"] == "widget_secret"


def test_la_cle_porte_produit_version_ressource_et_identifiant(
    widget_service: ApiService,
) -> None:
    operation = widget_service.operation("StartWidgets")
    assert operation is not None
    assert operation.key == "widget.v1.Widget.StartWidgets"


def test_le_parsing_est_deterministe() -> None:
    source = VendoredSpecSource(root=WIDGET_SPECS)
    premier = parse_document(source.load("widget", "v1")).to_json()
    second = parse_document(source.load("widget", "v1")).to_json()
    assert premier == second


def test_un_etat_imbrique_est_une_propriete_de_la_ressource(gadget_service: ApiService) -> None:
    """`NetPeering.State` est un objet `{Name, Message}` : la ressource le porte tel quel."""
    liste = gadget_service.operation("ReadGadgets")
    assert liste is not None and liste.response is not None
    assert liste.response.payload_fields == ("GadgetId", "State")
