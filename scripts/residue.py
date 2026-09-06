"""Prouve qu'un exercice n'a rien laissé derrière lui sur la cible.

La destruction de la plateforme ne suffit pas comme garantie, et ce n'est pas
une opinion : une construction interrompue laisse des ressources que la
destruction n'a pas listées, et un instantané survit à la suppression de son
volume.

La garantie est donc un **différentiel**, et non « le compte doit être vide » :
le compte porte ce qu'il porte, et il doit être **inchangé**.

    python scripts/residue.py capture   avant l'exercice
    python scripts/residue.py verify    après la destruction, sort en 1 s'il reste quelque chose

L'inventaire passe par le SDK, avec les identifiants et l'endpoint de
l'environnement (`OSC_ACCESS_KEY`, `OSC_SECRET_KEY`, `OSC_REGION`,
`OSC_ENDPOINT_API`, ce que `feint env outscale` exporte). **Un appel qui
échoue est une erreur, jamais un zéro** : une liste qui ne répond pas ne
prouve pas qu'il ne reste rien, elle prouve qu'on ne sait pas.

Le fichier de référence vit sous `build/`, jamais dans le dépôt : c'est l'état
d'un compte à un instant, pas un artefact du produit.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from osc_sdk_python import Gateway

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "build" / "residue" / "baseline.json"

#: Ce qu'on inventorie, et comment : le type, l'action du SDK qui le liste,
#: le champ d'enveloppe, le champ d'identifiant, et les filtres. Chaque
#: entrée est un type que la plateforme d'exemple crée, directement ou par
#: effet de bord.
#:
#: `ReadVms` est filtré sur les états vivants : une machine supprimée reste
#: `terminated` quelque temps dans la liste, et elle n'est pas un résidu.
#: `ReadNetPeerings` aussi : un peering supprimé reste listé `deleted`,
#: accepté ou non, mesuré sur feint 0.12.1 après un DeleteNetPeering à 200,
#: et c'est l'état que le contrat énumère (`NetPeeringState.Name`).
#: `ReadImages` et `ReadSnapshots` ne sont pas filtrés sur le compte : feint
#: n'émule pas `AccountAliases` (mesuré le 5 septembre 2026, 400 4001 avec
#: la liste des filtres qu'il sert), et un différentiel n'a pas besoin de
#: filtrer un catalogue public qui ne bouge pas entre avant et après.
SURFACE: tuple[tuple[str, str, str, str, dict[str, Any]], ...] = (
    (
        "vm",
        "ReadVms",
        "Vms",
        "VmId",
        {"VmStateNames": ["pending", "running", "stopping", "stopped", "shutting-down"]},
    ),
    ("net", "ReadNets", "Nets", "NetId", {}),
    ("subnet", "ReadSubnets", "Subnets", "SubnetId", {}),
    ("security-group", "ReadSecurityGroups", "SecurityGroups", "SecurityGroupId", {}),
    ("keypair", "ReadKeypairs", "Keypairs", "KeypairName", {}),
    ("volume", "ReadVolumes", "Volumes", "VolumeId", {}),
    ("snapshot", "ReadSnapshots", "Snapshots", "SnapshotId", {}),
    ("image", "ReadImages", "Images", "ImageId", {}),
    ("public-ip", "ReadPublicIps", "PublicIps", "PublicIpId", {}),
    ("nic", "ReadNics", "Nics", "NicId", {}),
    ("route-table", "ReadRouteTables", "RouteTables", "RouteTableId", {}),
    ("internet-service", "ReadInternetServices", "InternetServices", "InternetServiceId", {}),
    ("nat-service", "ReadNatServices", "NatServices", "NatServiceId", {}),
    (
        "net-peering",
        "ReadNetPeerings",
        "NetPeerings",
        "NetPeeringId",
        {"StateNames": ["pending-acceptance", "active"]},
    ),
    ("dhcp-options", "ReadDhcpOptions", "DhcpOptionsSets", "DhcpOptionsSetId", {}),
    ("load-balancer", "ReadLoadBalancers", "LoadBalancers", "LoadBalancerName", {}),
)


class ResidueError(RuntimeError):
    """L'inventaire n'a pas pu être pris, ou il reste quelque chose."""


def client_from_env() -> Gateway:
    if not os.environ.get("OSC_ACCESS_KEY") or not os.environ.get("OSC_SECRET_KEY"):
        raise ResidueError("OSC_ACCESS_KEY et OSC_SECRET_KEY sont requis")
    return Gateway()


def lister(
    client: Gateway, action: str, enveloppe: str, filtres: dict[str, Any]
) -> list[dict[str, Any]]:
    """Liste un type de ressource, toutes pages comprises. Un échec est une erreur."""
    items: list[dict[str, Any]] = []
    token: str | None = None
    vus: set[str] = set()
    while True:
        kwargs: dict[str, Any] = {}
        if filtres:
            kwargs["Filters"] = filtres
        if token:
            kwargs["NextPageToken"] = token
        try:
            reponse = getattr(client, action)(**kwargs)
        except (requests.RequestException, NotImplementedError) as erreur:
            raise ResidueError(f"`{action}` a échoué : {erreur}") from erreur
        page = reponse.get(enveloppe) if isinstance(reponse, dict) else None
        if not isinstance(page, list):
            raise ResidueError(f"`{action}` n'a pas rendu de liste `{enveloppe}`")
        items.extend(page)
        token = reponse.get("NextPageToken") if isinstance(reponse, dict) else None
        if not token or token in vus:
            return items
        vus.add(token)


def libelle(item: dict[str, Any]) -> str:
    for tag in item.get("Tags") or ():
        if isinstance(tag, dict) and tag.get("Key") == "Name":
            return str(tag.get("Value"))
    return str(
        item.get("LoadBalancerName")
        or item.get("KeypairName")
        or item.get("PublicIp")
        or "sans nom"
    )


def inventaire(client: Gateway) -> dict[str, dict[str, str]]:
    """L'état du compte : par type, les identifiants présents et leur nom."""
    etat: dict[str, dict[str, str]] = {}
    for nom, action, enveloppe, champ_id, filtres in SURFACE:
        etat[nom] = {
            str(item[champ_id]): libelle(item)
            for item in lister(client, action, enveloppe, filtres)
            if item.get(champ_id)
        }
    return etat


def ecarts(
    avant: dict[str, dict[str, str]], apres: dict[str, dict[str, str]]
) -> tuple[list[str], list[str]]:
    """Ce qui est apparu, et ce qui a disparu. Pure, donc testable."""
    apparus = [
        f"  {nom}  {libelle}  ({identifiant})"
        for nom, items in sorted(apres.items())
        for identifiant, libelle in sorted(items.items())
        if identifiant not in avant.get(nom, {})
    ]
    disparus = [
        f"  {nom}  {libelle}  ({identifiant})"
        for nom, items in sorted(avant.items())
        for identifiant, libelle in sorted(items.items())
        if identifiant not in apres.get(nom, {})
    ]
    return apparus, disparus


def capture() -> int:
    etat = inventaire(client_from_env())
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in etat.values())
    print(f"référence prise : {total} ressource(s) préexistante(s), {BASELINE.relative_to(ROOT)}")
    for nom, items in sorted(etat.items()):
        if items:
            print(f"  {nom} : {', '.join(sorted(items.values()))}")
    return 0


def verify() -> int:
    if not BASELINE.is_file():
        raise ResidueError(
            f"{BASELINE.relative_to(ROOT)} est absent : lancer `capture` **avant** "
            "l'exercice. Sans référence, on ne peut rien prouver, et surtout pas "
            "l'absence de quelque chose."
        )
    avant = json.loads(BASELINE.read_text(encoding="utf-8"))
    apres = inventaire(client_from_env())
    apparus, disparus = ecarts(avant, apres)

    if apparus:
        print(f"{len(apparus)} ressource(s) apparue(s) et non détruite(s) :", file=sys.stderr)
        print("\n".join(apparus), file=sys.stderr)
        print(
            "\nLe compte n'est pas revenu à son état d'avant. Les supprimer à la main, "
            "puis comprendre pourquoi la destruction ne les a pas emportées : c'est "
            "cette raison-là qui doit être corrigée, pas seulement la ressource.",
            file=sys.stderr,
        )
        return 1
    if disparus:
        print(f"{len(disparus)} ressource(s) préexistante(s) ont disparu :", file=sys.stderr)
        print("\n".join(disparus), file=sys.stderr)
        print(
            "\nL'exercice a détruit ce qu'il n'avait pas créé. C'est plus grave qu'un résidu.",
            file=sys.stderr,
        )
        return 1

    total = sum(len(v) for v in apres.values())
    print(f"aucun résidu : le compte est revenu à ses {total} ressource(s) d'avant")
    return 0


def main(argv: list[str]) -> int:
    action = argv[1] if len(argv) > 1 else ""
    if action == "capture":
        return capture()
    if action == "verify":
        return verify()
    print("usage : python scripts/residue.py capture|verify", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except ResidueError as erreur:
        print(f"erreur : {erreur}", file=sys.stderr)
        raise SystemExit(1) from erreur
