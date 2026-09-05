# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le provider Vm.

Il traduit ce que `ReadVms` rend en `InventoryHost`, et rien d'autre. Il ne
connaît ni Ansible, ni le cache, ni les groupes, et il n'importe pas le SDK :
il reçoit une fabrique de clients, ce qui permet de le tester avec des
réponses figées.

**Ce qu'il lit, il le lit dans le contrat.** Les clés ci-dessous sont celles
du schéma `Vm` du contrat versionné et des schémas qu'il référence
(`Placement`, `NicLight`, `PrivateIpLightForVm`, `SecurityGroupLight`,
`ResourceTag`), et un test les y confronte : un champ renommé en amont fait
rougir la CI plutôt que rendre un parc muet. Le SDK rend des dictionnaires,
pas des objets, donc tout se lit par `.get`.

**Ce que le contrat dit des adresses, mesuré.** `PublicIp` et `PrivateIp` sont
sur la machine ; les adresses privées complètes sont sur ses interfaces
(`Nics[].PrivateIps[].PrivateIp`), et une machine hors Net n'a ni `Nics` ni
`PrivateIp` (mesuré contre feint). La liste des privées vient donc des
interfaces, et `PrivateIp` n'est qu'un repli quand elles manquent.

**Une région, un client.** L'hôte de l'API porte la région : il n'existe pas
d'appel qui liste tout le compte, et le provider interroge chaque région
demandée avec le client de cette région.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import AuthenticationFailed, classify, describe
from ..models import InventoryHost, ProviderResult
from ..paging import paginate
from .base import ClientFactory, DiscoveryContext

#: L'action du contrat que ce provider appelle, le champ de sa réponse qui
#: porte les machines, et celui qui porte le jeton de page suivante. Un test
#: exige que le contrat versionné les déclare.
ACTION = "ReadVms"
PAYLOAD_FIELD = "Vms"
TOKEN_FIELD = "NextPageToken"

#: Ce qui n'appartient qu'à Vm, exposé à plat sous le préfixe des hostvars
#: (`outscale_vm_type`). Chaque entrée : le nom de la variable, et la clé du
#: contrat qui la porte.
METADATA_FIELDS: tuple[tuple[str, str], ...] = (
    ("vm_type", "VmType"),
    ("image_id", "ImageId"),
    ("keypair_name", "KeypairName"),
)

#: Les axes de groupes que Vm ajoute au cœur : l'axe de `group_by`, et la clé
#: de `metadata` qui le porte. Un test exige que chaque clé soit un nom de
#: `METADATA_FIELDS`.
GROUP_AXES: Mapping[str, str] = {"vm_type": "vm_type", "keypair": "keypair_name"}

#: Le tag qui porte le nom d'une machine. C'est une convention de la console
#: et des outils Outscale, pas un champ du contrat : le contrat ne connaît
#: que des paires `{Key, Value}`.
NAME_TAG = "Name"


def _text(value: Any) -> str | None:
    """Une chaîne non vide, ou `None` : l'API rend `""` pour ce qu'elle n'a pas."""
    if value is None:
        return None
    texte = str(value)
    return texte or None


def _tags(vm: dict[str, Any]) -> dict[str, str]:
    """`[{Key, Value}]` en dictionnaire, dans l'ordre de l'API."""
    resultat: dict[str, str] = {}
    for tag in vm.get("Tags") or ():
        if not isinstance(tag, dict):
            continue
        cle = _text(tag.get("Key"))
        if cle is None:
            continue
        resultat[cle] = str(tag.get("Value") or "")
    return resultat


def _private_ips(vm: dict[str, Any]) -> tuple[str, ...]:
    """Les adresses privées des interfaces, sinon celle de la machine."""
    adresses: list[str] = []
    for nic in vm.get("Nics") or ():
        if not isinstance(nic, dict):
            continue
        for ip in nic.get("PrivateIps") or ():
            if not isinstance(ip, dict):
                continue
            adresse = _text(ip.get("PrivateIp"))
            if adresse and adresse not in adresses:
                adresses.append(adresse)
    if not adresses:
        repli = _text(vm.get("PrivateIp"))
        if repli:
            adresses.append(repli)
    return tuple(adresses)


def _security_group_ids(vm: dict[str, Any]) -> tuple[str, ...]:
    """Les groupes de la machine, puis ceux de ses interfaces, sans doublon."""
    identifiants: list[str] = []
    porteurs: list[Any] = [vm, *(vm.get("Nics") or ())]
    for porteur in porteurs:
        if not isinstance(porteur, dict):
            continue
        for groupe in porteur.get("SecurityGroups") or ():
            if not isinstance(groupe, dict):
                continue
            identifiant = _text(groupe.get("SecurityGroupId"))
            if identifiant and identifiant not in identifiants:
                identifiants.append(identifiant)
    return tuple(identifiants)


def normalize(vm: dict[str, Any], region: str, context: DiscoveryContext) -> InventoryHost:
    """Traduit une machine en modèle normalisé."""
    tags = _tags(vm)
    placement = vm.get("Placement")
    sous_region = _text(placement.get("SubregionName")) if isinstance(placement, dict) else None

    metadata: dict[str, Any] = {}
    for variable, cle in METADATA_FIELDS:
        valeur = _text(vm.get(cle))
        if valeur is not None:
            metadata[variable] = valeur

    publique = _text(vm.get("PublicIp"))
    return InventoryHost(
        id=str(vm["VmId"]),
        product="vm",
        name=_text(tags.get(NAME_TAG)),
        region=region,
        subregion=sous_region,
        state=_text(vm.get("State")),
        tags=tags,
        public_ipv4=(publique,) if publique else (),
        private_ipv4=_private_ips(vm),
        net_id=_text(vm.get("NetId")),
        subnet_id=_text(vm.get("SubnetId")),
        security_group_ids=_security_group_ids(vm),
        metadata=metadata,
        raw=vm if context.include_raw else None,
    )


class VmProvider:
    """Découvre les machines des régions demandées."""

    name = "vm"
    group_axes = GROUP_AXES

    def __init__(self, client_for: ClientFactory) -> None:
        self._client_for = client_for

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        """Une lecture paginée par région, avec les filtres de l'API tels quels.

        Un échec de lecture est une erreur, jamais un zéro : un `ReadVms` qui
        échoue ne dit pas que la région est vide, il dit qu'on ne sait pas.
        Le refus d'authentification est fatal partout : aucune région ne peut
        aboutir, et continuer produirait un inventaire vide qui se présente
        comme complet.
        """
        hosts: list[InventoryHost] = []
        avertissements: list[str] = []
        erreurs: list[str] = []
        appels = 0

        base: dict[str, Any] = {}
        if context.api_filters:
            base["Filters"] = dict(context.api_filters)

        for region in context.regions:
            client = self._client_for(region)
            lecture = getattr(client, ACTION)
            try:
                pages = paginate(
                    lambda payload, lire=lecture: lire(**payload), base, PAYLOAD_FIELD, TOKEN_FIELD
                )
            except Exception as erreur:
                message = f"{ACTION} dans {region} : {describe(erreur)}"
                if classify(erreur) is AuthenticationFailed:
                    raise AuthenticationFailed(message) from erreur
                erreurs.append(message)
                continue

            appels += pages.calls
            if pages.truncated:
                avertissements.append(
                    f"{ACTION} dans {region} : jeton de page répété, la liste peut être incomplète"
                )
            hosts.extend(
                normalize(vm, region, context) for vm in pages.items if isinstance(vm, dict)
            )

        # Trié par région puis identifiant : l'ordre décide de la
        # désambiguïsation des noms, donc il doit être le même d'une exécution
        # à l'autre.
        return ProviderResult(
            hosts=tuple(sorted(hosts, key=lambda h: (h.region or "", h.id))),
            warnings=tuple(avertissements),
            errors=tuple(erreurs),
            api_calls=appels,
        )
