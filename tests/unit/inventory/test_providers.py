"""Le provider Vm traduit sans deviner, et le cœur ne connaît aucun produit.

Quatre preuves ici, et les trois dernières sont structurelles :

* la normalisation d'une machine telle que le contrat la décrit, et le
  déroulé de ses pages région par région ;
* les champs que le provider lit existent dans le schéma `Vm` du contrat
  versionné et dans ceux qu'il référence, lus dans le code par AST plutôt que
  recopiés à côté ;
* aucune couche du cœur ne nomme un produit dans son code ;
* les filtres d'API de l'inventaire d'exemple existent dans `FiltersVm`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory import (
    address,
    filtering,
    groups,
    hostname,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.errors import (
    AuthenticationFailed,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.providers import vm
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.providers.base import (
    DiscoveryContext,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRAT = REPO_ROOT / "specs" / "outscale" / "outscale.v1.yml"
EXEMPLE = REPO_ROOT / "examples" / "playbooks" / "inventaire.outscale.yml"
COLLECTION = REPO_ROOT / "ansible_collections" / "stephrobert" / "outscale" / "plugins"
INVENTAIRE = COLLECTION / "module_utils" / "inventory"


@pytest.fixture(scope="module")
def schemas() -> dict[str, Any]:
    with CONTRAT.open(encoding="utf-8") as handle:
        document = yaml.load(handle, Loader=yaml.CSafeLoader)
    return dict(document["components"]["schemas"])


def _vm(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "VmId": "i-1",
        "State": "running",
        "VmType": "tinav5.c1r1p2",
        "ImageId": "ami-00000003",
        "KeypairName": "admin",
        "NetId": "vpc-1",
        "SubnetId": "subnet-1",
        "PublicIp": "171.33.0.1",
        "PrivateIp": "10.0.0.5",
        "Placement": {"SubregionName": "eu-west-2a", "Tenancy": "default"},
        "Tags": [{"Key": "Name", "Value": "web01"}, {"Key": "env", "Value": "prod"}],
        "SecurityGroups": [{"SecurityGroupId": "sg-1", "SecurityGroupName": "default"}],
        "Nics": [
            {
                "NicId": "eni-1",
                "PrivateIps": [
                    {"PrivateIp": "10.0.0.5", "IsPrimary": True},
                    {"PrivateIp": "10.0.0.6", "IsPrimary": False},
                ],
                "SecurityGroups": [{"SecurityGroupId": "sg-2"}, {"SecurityGroupId": "sg-1"}],
            }
        ],
        "UserData": "",
    }
    base.update(extra)
    return base


UNE_REGION = DiscoveryContext(regions=("eu-west-2",))


def test_vm_normalise_ce_que_lapi_rend() -> None:
    host = vm.normalize(_vm(), "eu-west-2", UNE_REGION)
    assert (host.id, host.product, host.name, host.region, host.subregion, host.state) == (
        "i-1",
        "vm",
        "web01",
        "eu-west-2",
        "eu-west-2a",
        "running",
    )
    assert host.public_ipv4 == ("171.33.0.1",)
    assert host.private_ipv4 == ("10.0.0.5", "10.0.0.6")
    assert dict(host.tags) == {"Name": "web01", "env": "prod"}
    assert host.tag_pairs == ("Name=web01", "env=prod")
    assert (host.net_id, host.subnet_id) == ("vpc-1", "subnet-1")
    assert host.security_group_ids == ("sg-1", "sg-2")
    assert dict(host.metadata) == {
        "vm_type": "tinav5.c1r1p2",
        "image_id": "ami-00000003",
        "keypair_name": "admin",
    }
    assert host.raw is None


def test_sans_interface_ladresse_privee_de_la_machine_sert_de_repli() -> None:
    host = vm.normalize(_vm(Nics=[]), "eu-west-2", UNE_REGION)
    assert host.private_ipv4 == ("10.0.0.5",)


def test_une_machine_hors_net_reste_un_host_sans_adresse() -> None:
    """Mesuré contre feint : ni Nics, ni PublicIp, ni PrivateIp, ni NetId."""
    nue = {"VmId": "i-2", "State": "running", "Placement": {"SubregionName": "eu-west-2a"}}
    host = vm.normalize(nue, "eu-west-2", UNE_REGION)
    assert host.public_ipv4 == () and host.private_ipv4 == ()
    assert host.name is None and host.net_id is None and dict(host.tags) == {}
    assert host.metadata == {}


def test_une_chaine_vide_de_lapi_nest_pas_une_valeur() -> None:
    host = vm.normalize(_vm(PublicIp="", KeypairName=""), "eu-west-2", UNE_REGION)
    assert host.public_ipv4 == () and "keypair_name" not in host.metadata


def test_la_reponse_brute_nest_gardee_que_si_on_la_demande() -> None:
    contexte = DiscoveryContext(regions=("eu-west-2",), include_raw=True)
    assert vm.normalize(_vm(), "eu-west-2", contexte).raw == _vm()


class _Client:
    """Un SDK figé : des pages par région, ou une erreur."""

    def __init__(
        self,
        pages: dict[str, list[dict[str, Any]]] | None = None,
        erreur: Exception | None = None,
    ) -> None:
        self.pages = pages or {}
        self.erreur = erreur
        self.appels: list[dict[str, Any]] = []

    def ReadVms(self, **kwargs: Any) -> dict[str, Any]:
        self.appels.append(kwargs)
        if self.erreur is not None:
            raise self.erreur
        jeton = kwargs.get("NextPageToken") or "p1"
        return self.pages.get(jeton, {"Vms": []})


def test_vm_deroule_les_pages_et_passe_les_filtres_tels_quels() -> None:
    client = _Client(
        {
            "p1": {"Vms": [_vm(VmId="i-2")], "NextPageToken": "p2"},
            "p2": {"Vms": [_vm(VmId="i-1")]},
        }
    )
    contexte = DiscoveryContext(regions=("eu-west-2",), api_filters={"VmStateNames": ["running"]})
    resultat = vm.VmProvider(lambda r: client).discover(contexte)
    assert [h.id for h in resultat.hosts] == ["i-1", "i-2"]
    assert resultat.api_calls == 2 and resultat.errors == ()
    assert client.appels == [
        {"Filters": {"VmStateNames": ["running"]}},
        {"Filters": {"VmStateNames": ["running"]}, "NextPageToken": "p2"},
    ]


def test_vm_nenvoie_rien_de_plus_que_ce_quon_lui_donne() -> None:
    client = _Client({"p1": {"Vms": []}})
    vm.VmProvider(lambda r: client).discover(UNE_REGION)
    assert client.appels == [{}]


def test_vm_interroge_une_region_par_client_et_trie_par_region_puis_identifiant() -> None:
    clients = {
        "eu-west-2": _Client({"p1": {"Vms": [_vm(VmId="i-9"), _vm(VmId="i-1")]}}),
        "cloudgouv-eu-west-1": _Client({"p1": {"Vms": [_vm(VmId="i-5")]}}),
    }
    resultat = vm.VmProvider(lambda r: clients[r or ""]).discover(
        DiscoveryContext(regions=("eu-west-2", "cloudgouv-eu-west-1"))
    )
    assert [(h.region, h.id) for h in resultat.hosts] == [
        ("cloudgouv-eu-west-1", "i-5"),
        ("eu-west-2", "i-1"),
        ("eu-west-2", "i-9"),
    ]


class _HTTPError(Exception):
    def __init__(self, status: int, body: dict[str, Any] | None = None) -> None:
        super().__init__(f"HTTP {status}")
        from types import SimpleNamespace

        self.response = SimpleNamespace(status_code=status, json=lambda: body or {})


def test_un_refus_dauthentification_est_fatal() -> None:
    client = _Client(erreur=_HTTPError(401))
    with pytest.raises(AuthenticationFailed, match="identifiants refusés"):
        vm.VmProvider(lambda r: client).discover(UNE_REGION)


def test_un_droit_manquant_une_requete_fausse_et_une_panne_sont_des_erreurs_dites() -> None:
    """Un ReadVms qui échoue est une erreur, pas un zéro, et chacune a son mot."""
    corps = {"Errors": [{"Code": "4001", "Type": "InvalidParameterValue", "Details": "Mars"}]}
    messages = []
    for erreur in (_HTTPError(403), _HTTPError(400, corps), _HTTPError(503)):
        resultat = vm.VmProvider(lambda r, e=erreur: _Client(erreur=e)).discover(UNE_REGION)
        assert resultat.hosts == () and len(resultat.errors) == 1
        messages.append(resultat.errors[0])
    assert all("ReadVms dans eu-west-2" in m for m in messages)
    assert "droit manquant" in messages[0]
    assert "requête rejetée" in messages[1] and "Mars" in messages[1]
    assert "panne" in messages[2]
    assert len(set(messages)) == 3


def test_une_region_en_panne_ne_cache_pas_les_autres() -> None:
    clients = {
        "eu-west-2": _Client({"p1": {"Vms": [_vm()]}}),
        "us-east-2": _Client(erreur=ConnectionError("réseau")),
    }
    resultat = vm.VmProvider(lambda r: clients[r or ""]).discover(
        DiscoveryContext(regions=("eu-west-2", "us-east-2"))
    )
    assert [h.id for h in resultat.hosts] == ["i-1"]
    assert len(resultat.errors) == 1 and "us-east-2" in resultat.errors[0]


def test_un_jeton_repete_est_un_avertissement() -> None:
    client = _Client({"p1": {"Vms": [_vm()], "NextPageToken": "p1"}})
    resultat = vm.VmProvider(lambda r: client).discover(UNE_REGION)
    assert len(resultat.hosts) == 2 and "incomplète" in resultat.warnings[0]


# ---- les preuves structurelles ---------------------------------------------


def _cles_lues(chemin: Path) -> set[str]:
    """Les chaînes en CamelCase que le provider passe à `.get` ou lit par index."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    cles: set[str] = set()
    for noeud in ast.walk(arbre):
        if (
            isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == "get"
        ):
            for argument in noeud.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    cles.add(argument.value)
        if (
            isinstance(noeud, ast.Subscript)
            and isinstance(noeud.slice, ast.Constant)
            and isinstance(noeud.slice.value, str)
        ):
            cles.add(noeud.slice.value)
    return {cle for cle in cles if re.fullmatch(r"[A-Z][A-Za-z0-9]*", cle)}


def _proprietes(schemas: dict[str, Any], nom: str, profondeur: int = 3) -> set[str]:
    """Les propriétés d'un schéma et de ceux qu'il référence, jusqu'à `profondeur`."""
    connues: set[str] = set()
    schema = schemas.get(nom) or {}
    for propriete, spec in (schema.get("properties") or {}).items():
        connues.add(propriete)
        if profondeur <= 0:
            continue
        reference = spec.get("$ref") or (spec.get("items") or {}).get("$ref")
        if reference:
            connues |= _proprietes(schemas, reference.rsplit("/", 1)[-1], profondeur - 1)
    return connues


def test_les_champs_que_le_provider_lit_existent_dans_le_contrat(schemas: dict[str, Any]) -> None:
    """Lu dans le code par AST plutôt que recopié à côté : un champ renommé en
    amont rendrait `None`, et l'inventaire un parc muet."""
    # Ce que le provider lit vient de `Vm` ; ce qu'il écrit dans la requête
    # (`Filters`) vient de la requête de l'action.
    connus = _proprietes(schemas, "Vm") | set(schemas[f"{vm.ACTION}Request"]["properties"])
    lues = _cles_lues(INVENTAIRE / "providers" / "vm.py")
    lues.update(cle for _, cle in vm.METADATA_FIELDS)
    inconnues = sorted(lues - connus)
    assert inconnues == [], f"le provider lit des champs absents du contrat : {inconnues}"
    assert "VmId" in lues and "SubregionName" in lues and "PrivateIp" in lues


def test_laction_et_sa_reponse_sont_celles_du_contrat(schemas: dict[str, Any]) -> None:
    assert f"{vm.ACTION}Request" in schemas
    reponse = schemas[f"{vm.ACTION}Response"]["properties"]
    assert vm.PAYLOAD_FIELD in reponse and vm.TOKEN_FIELD in reponse
    assert "Filters" in schemas[f"{vm.ACTION}Request"]["properties"]


def test_les_axes_du_provider_portent_des_cles_quil_ecrit() -> None:
    noms = {nom for nom, _ in vm.METADATA_FIELDS}
    assert set(vm.GROUP_AXES.values()) <= noms


def test_les_filtres_de_lexemple_existent_dans_le_contrat(schemas: dict[str, Any]) -> None:
    """L'inventaire d'exemple parle au contrat avec ses mots, et le contrat en juge."""
    with EXEMPLE.open(encoding="utf-8") as handle:
        exemple = yaml.load(handle, Loader=yaml.CSafeLoader)
    assert exemple["plugin"] == "stephrobert.outscale.vm"
    filtres = set(exemple.get("filters") or {})
    assert filtres, "l'exemple doit exercer au moins un filtre d'API"
    inconnus = sorted(filtres - set(schemas["FiltersVm"]["properties"]))
    assert inconnus == [], f"l'exemple filtre sur des noms absents de FiltersVm : {inconnus}"


#: Les couches que l'ajout d'un produit ne doit pas toucher.
COEUR = (
    "models.py",
    "address.py",
    "groups.py",
    "hostname.py",
    "filtering.py",
    "paging.py",
    "errors.py",
    "config.py",
    "providers/base.py",
)

#: Les noms de produits, en mot entier ou en segment de snake_case
#: (`exclude_vm_ids` est interdit autant que `vm`).
PRODUITS_EN_MOT = ("vm", "Vm", "nic", "Nic", "load_balancer", "LoadBalancer")

#: Les noms de produits tels qu'ils apparaissent collés dans le CamelCase du contrat.
PRODUITS_EN_SUBSTRING = ("ReadVms", "VmId", "VmType", "Vms", "Nics", "Placement")

PORTEURS_DE_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _code_sans_prose(chemin: Path) -> str:
    """Le code seul : ni commentaire, ni docstring, mais toutes les chaînes.

    La prose nomme les produits pour expliquer ses décisions, et c'est très
    bien. Ce qui est interdit, c'est qu'une **instruction** les nomme.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, PORTEURS_DE_DOCSTRING):
            continue
        corps = noeud.body
        if (
            corps
            and isinstance(corps[0], ast.Expr)
            and isinstance(corps[0].value, ast.Constant)
            and isinstance(corps[0].value.value, str)
        ):
            noeud.body = corps[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(arbre))


@pytest.mark.parametrize("fichier", COEUR)
def test_aucune_couche_du_coeur_ne_nomme_un_produit(fichier: str) -> None:
    """Si cette assertion tombe un jour, c'est qu'un produit a fuité hors de son
    provider, et que le suivant coûtera une modification du cœur."""
    code = _code_sans_prose(INVENTAIRE / fichier)
    for produit in PRODUITS_EN_MOT:
        motif = rf"(?<![A-Za-z0-9]){produit}(?![A-Za-z0-9])"
        assert re.search(motif, code) is None, f"{fichier} nomme '{produit}'"
    for produit in PRODUITS_EN_SUBSTRING:
        assert produit not in code, f"{fichier} nomme '{produit}'"


def test_le_provider_et_le_plugin_sont_les_seuls_a_nommer_le_produit() -> None:
    """Le témoin du test précédent : la garde doit mordre là où le nom est légitime."""
    for fichier in (INVENTAIRE / "providers" / "vm.py", COLLECTION / "inventory" / "vm.py"):
        code = _code_sans_prose(fichier)
        assert re.search(r"(?<![A-Za-z0-9])vm(?![A-Za-z0-9])", code) is not None, fichier


def test_le_meme_pipeline_traite_un_host_sans_cas_particulier() -> None:
    """Filtrage, nom d'hôte, groupes et adresse : aucune couche ne demande le produit."""
    host = vm.normalize(_vm(), "eu-west-2", UNE_REGION)
    garde, _ = filtering.keep(host.id, host.tags, host.state, filtering.Filters(tags={"env": ""}))
    attribues, _ = hostname.assign_hostnames((host,), ("tag:Name", "id"))
    noms = groups.group_names(host, ("region", "vm_type"), vm.GROUP_AXES)
    choix = address.select_ansible_host(host, address.AddressPolicy())
    assert garde and attribues[0][1] == "web01" and choix.address == "171.33.0.1"
    assert noms == ("osc_region_eu_west_2", "osc_vm_type_tinav5_c1r1p2")
