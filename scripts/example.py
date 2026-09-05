"""Bâtit la plateforme d'exemple, l'exploite avec la collection, la détruit.

    python scripts/example.py emulateur     # feint sur 127.0.0.1:4811, gratuit, hors ligne
    python scripts/example.py reel          # refusé sans --compte-reel-accorde

Une exécution enchaîne, dans cet ordre :

1. l'émulateur, adopté s'il écoute déjà **et** qu'il n'héberge rien, démarré
   sinon ; l'environnement vient de `feint env outscale` ;
2. la référence de résidu (`scripts/residue.py capture`) ;
3. `terraform apply` sur `examples/stack/`, avec un préfixe propre au run, et
   ses sorties en JSON ;
4. le plan de contrôle vérifié **par le SDK**, pas par la collection : un
   contrôle qui se sert de la collection pour juger la collection ne mesure
   plus rien ;
5. l'inventaire dynamique, dont le graphe est comparé à ce que la stack a bâti ;
6. le playbook `modules.yml`, sous un plugin de rappel qui journalise ce qui
   s'est **réellement** joué ;
7. **dans un `finally`** : `terraform destroy`, puis `residue.py verify`, puis
   l'artefact de couverture sous `build/example/`.

**La cible réelle ne se lance pas sans l'accord du mainteneur, demandé à
chaque fois.** Le drapeau `--compte-reel-accorde` est la trace de cet accord ;
sans lui, refus. Ce dépôt n'a jamais parlé au compte Outscale réel, et ne le
fera pas de lui-même.

**Le port.** feint est développé sur cette machine, collection-scaleway écoute
sur 4877 et collection-exoscale sur 4993 : cet exercice écoute sur **4811**,
et refuse d'adopter un émulateur qui héberge déjà des machines.

**Le code de sortie.** Une destruction ratée après un playbook vert est un
échec : le verdict du `finally` est combiné à celui du `try`, plutôt que
perdu dans un `return` déjà fixé, ce qui était le défaut mesuré chez
collection-exoscale.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "examples" / "stack"
PLAYBOOKS = ROOT / "examples" / "playbooks"
RAPPELS = ROOT / "examples" / "callback_plugins"
TRAVAIL = ROOT / "build" / "example"

#: Le port de cet exercice : ni le 4599 par défaut de feint, ni le 4877 de
#: collection-scaleway, ni le 4993 de collection-exoscale.
ADRESSE = "127.0.0.1:4811"
ENDPOINT = f"http://{ADRESSE}"

PREFIXE_COLLECTION = "stephrobert.outscale."

#: Ce que feint répond sur une route qu'il décline. Une tâche dont le message
#: porte ça a été appelée, pas jouée.
NON_SERVI = re.compile(r"does not serve|not_emulated|resource not found", re.IGNORECASE)

CIBLES: dict[str, dict[str, Any]] = {
    "emulateur": {"emulateur": True},
    "reel": {"emulateur": False},
}


class ExempleError(RuntimeError):
    """L'exercice ne peut pas continuer, et il vaut mieux le dire que continuer."""


def binaire(nom: str) -> str:
    trouve = shutil.which(nom)
    if trouve is None:
        raise ExempleError(f"`{nom}` est introuvable sur le PATH")
    return trouve


def lancer(
    commande: list[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        commande, env=env, capture_output=capture, text=True, check=False, cwd=cwd
    )


def environnement_emulateur() -> dict[str, str]:
    """Ce que `feint env outscale` exporte, lu plutôt que recopié."""
    resultat = lancer([binaire("feint"), "env", "outscale", "--endpoint", ENDPOINT], capture=True)
    if resultat.returncode != 0:
        raise ExempleError(f"`feint env outscale` a échoué :\n{resultat.stderr}")
    valeurs: dict[str, str] = {}
    for ligne in resultat.stdout.splitlines():
        if ligne.startswith("export "):
            nom, _, valeur = ligne.removeprefix("export ").partition("=")
            valeurs[nom.strip()] = valeur.strip().strip("'\"")
    attendu = f"{ENDPOINT}/api/v1"
    if valeurs.get("OSC_ENDPOINT_API") != attendu:
        raise ExempleError(
            f"`feint env` n'a pas donné OSC_ENDPOINT_API={attendu}. L'exercice s'arrête : "
            "sans cette variable, la plateforme et les playbooks parleraient à l'API réelle."
        )
    return valeurs


def refuser_emulateur_habite(env: dict[str, str]) -> None:
    """Un émulateur qui héberge déjà des machines est la session de quelqu'un d'autre."""
    from osc_sdk_python import Gateway

    gateway = Gateway(
        access_key=env["OSC_ACCESS_KEY"],
        secret_key=env["OSC_SECRET_KEY"],
        region=env["OSC_REGION"],
    )
    vms = gateway.ReadVms().get("Vms") or []
    vivantes = [vm for vm in vms if vm.get("State") != "terminated"]
    if vivantes:
        raise ExempleError(
            f"l'émulateur sur {ADRESSE} héberge déjà {len(vivantes)} machine(s) : ce n'est "
            "pas le nôtre, et l'exercice le détruirait. L'arrêter, ou changer de port."
        )


def terraform(
    action: str, env: dict[str, str], run_id: str, *, region: str
) -> subprocess.CompletedProcess[str]:
    """Un `terraform` dans la stack, avec l'état de ce run sous build/."""
    etat = TRAVAIL / f"terraform-{run_id}.tfstate"
    commande = [binaire("terraform"), f"-chdir={STACK}", action]
    if action in ("apply", "destroy"):
        commande += [
            "-auto-approve",
            "-input=false",
            f"-state={etat}",
            f"-var=prefix={run_id}",
            f"-var=region={region}",
        ]
    if action == "output":
        commande += ["-json", f"-state={etat}"]
    if action == "init":
        commande += ["-input=false"]
    return lancer(commande, env={**env, "TF_IN_AUTOMATION": "1"}, capture=True)


def sorties_de(run_id: str, env: dict[str, str], region: str) -> dict[str, Any]:
    resultat = terraform("output", env, run_id, region=region)
    if resultat.returncode != 0:
        raise ExempleError(f"`terraform output` a échoué :\n{resultat.stderr}")
    brut = json.loads(resultat.stdout or "{}")
    return {nom: valeur["value"] for nom, valeur in brut.items()}


def inventaire(env: dict[str, str]) -> dict[str, Any]:
    """Le graphe que le plugin construit sur la plateforme bâtie."""
    binaire_ansible = str(Path(sys.executable).parent / "ansible-inventory")
    resultat = lancer(
        [binaire_ansible, "-i", str(PLAYBOOKS / "inventaire.outscale.yml"), "--list"],
        env=env,
        capture=True,
    )
    if resultat.returncode != 0:
        raise ExempleError(f"`ansible-inventory` a échoué :\n{resultat.stderr}")
    graphe = json.loads(resultat.stdout or "{}")
    if not isinstance(graphe, dict):
        raise ExempleError("`ansible-inventory` a rendu autre chose qu'un objet")
    return graphe


def _valeur(brut: Any) -> Any:
    if isinstance(brut, dict) and set(brut) == {"__ansible_unsafe"}:
        return brut["__ansible_unsafe"]
    if isinstance(brut, list):
        return [_valeur(item) for item in brut]
    return brut


def controler_inventaire(graphe: dict[str, Any], sorties: dict[str, Any]) -> None:
    """Ce que l'inventaire doit avoir trouvé, comparé à ce que la stack a bâti.

    C'est le contrôle qui refuse un vert obtenu sur rien : un plugin qui ne
    trouve aucune machine construit un inventaire parfaitement valide.
    """
    attendu = sorties["expected"]
    prefixe = sorties["prefix"]
    hostvars = {
        nom: variables
        for nom, variables in graphe.get("_meta", {}).get("hostvars", {}).items()
        if str(nom).startswith(prefixe)
    }
    if len(hostvars) != attendu["total"]:
        raise ExempleError(
            f"l'inventaire rend {len(hostvars)} machine(s) de la plateforme, "
            f"elle en a bâti {attendu['total']}"
        )
    for role in ("web", "app"):
        groupe = [
            h
            for h in graphe.get(f"osc_tag_role_{role}", {}).get("hosts", [])
            if h.startswith(prefixe)
        ]
        if len(groupe) != attendu[role]:
            raise ExempleError(
                f"le groupe osc_tag_role_{role} porte {len(groupe)} machine(s), "
                f"la plateforme en a bâti {attendu[role]}"
            )
    sans_adresse = sorted(
        nom for nom, variables in hostvars.items() if not _valeur(variables.get("ansible_host"))
    )
    if sans_adresse:
        raise ExempleError(f"{len(sans_adresse)} machine(s) sans ansible_host : {sans_adresse}")
    ids_stack = set(sorties["vm_ids"].values())
    ids_inventaire = {_valeur(v.get("outscale_id")) for v in hostvars.values()}
    if ids_stack != ids_inventaire:
        raise ExempleError(
            f"l'inventaire découvre {sorted(ids_inventaire)}, la stack a bâti {sorted(ids_stack)}"
        )
    print(
        f"inventaire : {len(hostvars)} machines, "
        f"{len([c for c in graphe if c.startswith('osc_')])} groupes natifs, "
        "chaque machine de la plateforme retrouvée par son identifiant, avec une adresse"
    )


def controler_plan_de_controle(env: dict[str, str], sorties: dict[str, Any]) -> None:
    """Tout ce que la plateforme déclare, vérifié auprès de l'API par le SDK."""
    from osc_sdk_python import Gateway

    gateway = Gateway()
    prefixe = sorties["prefix"]
    constats: list[str] = []

    def exige(condition: bool, message: str) -> None:
        constats.append(("ok  " if condition else "ÉCHEC ") + message)
        if not condition:
            raise ExempleError(f"plan de contrôle : {message}")

    def nom_de(item: dict[str, Any]) -> str:
        return next(
            (str(t.get("Value")) for t in item.get("Tags") or () if t.get("Key") == "Name"), ""
        )

    vms = [
        vm
        for vm in gateway.ReadVms(Filters={"VmIds": list(sorties["vm_ids"].values())}).get("Vms")
        or []
    ]
    exige(len(vms) == sorties["expected"]["total"], f"{sorties['expected']['total']} machines")
    nets = [n for n in gateway.ReadNets().get("Nets") or [] if nom_de(n).startswith(prefixe)]
    exige(len(nets) == 3, f"trois Nets ({len(nets)} trouvés)")
    peerings = (
        gateway.ReadNetPeerings(
            Filters={"NetPeeringIds": list(sorties["net_peering_ids"].values())}
        ).get("NetPeerings")
        or []
    )
    exige(len(peerings) == 2, "deux peerings proposés")
    etats = {p["NetPeeringId"]: (p.get("State") or {}).get("Name") for p in peerings}
    exige(
        all(etat == "pending-acceptance" for etat in etats.values()),
        f"les deux peerings sont en attente d'acceptation ({etats})",
    )
    lbs = (
        gateway.ReadLoadBalancers(
            Filters={"LoadBalancerNames": [sorties["load_balancer_name"]]}
        ).get("LoadBalancers")
        or []
    )
    exige(len(lbs) == 1, "un load balancer")
    exige(len(lbs[0].get("BackendVmIds") or []) == 2, "deux machines derrière le load balancer")
    print("plan de contrôle vérifié :")
    for constat in constats:
        print(f"  {constat}")


def artefact(journal: dict[str, Any], cible: str, run_id: str, residu: str) -> dict[str, Any]:
    """Ce que cette exécution a couvert, dérivé de ce qui s'est réellement joué.

    **Joué n'est pas appelé.** Une tâche gardée par un `when` non satisfait ne
    touche jamais l'API, et une route que feint décline répond sans rien
    faire : ni l'une ni l'autre ne compte. Un module joué une fois et sauté
    ailleurs compte comme joué : la question est « a-t-il tourné contre cette
    API », pas « toutes ses tâches ont-elles tourné ».
    """
    joues: set[str] = set()
    vus: set[str] = set()
    for tache in journal.get("taches", []):
        module = str(tache.get("module", ""))
        if not module.startswith(PREFIXE_COLLECTION):
            continue
        court = module[len(PREFIXE_COLLECTION) :]
        vus.add(court)
        if tache.get("verdict") in ("ok", "changed") and not NON_SERVI.search(
            str(tache.get("msg", ""))
        ):
            joues.add(court)
    faits = journal.get("faits", {})
    return {
        "cible": cible,
        "run_id": run_id,
        "horodatage": datetime.now(UTC).isoformat(timespec="seconds"),
        "modules_joues": sorted(joues),
        "modules_appeles_sans_reponse": sorted(vus - joues),
        "taches_jouees": len(journal.get("taches", [])),
        "routes_non_servies": sorted(faits.get("non_emules", [])),
        "idempotence_prouvee": sorted(faits.get("idempotences_prouvees", [])),
        "residu": residu,
    }


def ecrire_artefact(chemin_journal: Path, cible: str, run_id: str, residu: str) -> Path | None:
    """Écrit l'artefact à côté du journal. `None` quand rien n'a été journalisé :
    un artefact vide se lirait comme une exécution qui n'a rien couvert."""
    if not chemin_journal.is_file():
        return None
    journal = json.loads(chemin_journal.read_text(encoding="utf-8"))
    destination = TRAVAIL / f"{cible}-{run_id}.json"
    contenu = artefact(journal, cible, run_id, residu)
    destination.write_text(
        json.dumps(contenu, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (TRAVAIL / f"dernier-{cible}.json").write_text(
        destination.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return destination


def jouer(playbook: str, env: dict[str, str], variables: dict[str, str], extra_file: Path) -> int:
    binaire_ansible = str(Path(sys.executable).parent / "ansible-playbook")
    commande = [
        binaire_ansible,
        "-i",
        str(PLAYBOOKS / "inventaire.outscale.yml"),
        str(PLAYBOOKS / playbook),
        "-e",
        f"@{extra_file}",
    ]
    for nom, valeur in variables.items():
        commande += ["-e", f"{nom}={valeur}"]
    print(f"\n--- {playbook} ---", flush=True)
    code: int = lancer(commande, env=env).returncode
    return code


def main(argv: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("cible", choices=sorted(CIBLES))
    parseur.add_argument(
        "--garder", action="store_true", help="ne pas détruire à la fin (émulateur seulement)"
    )
    parseur.add_argument(
        "--compte-reel-accorde",
        action="store_true",
        help="la trace, dans la commande, de l'accord du mainteneur pour dépenser sur son compte",
    )
    arguments = parseur.parse_args(argv[1:])
    cible = CIBLES[arguments.cible]

    if not cible["emulateur"] and not arguments.compte_reel_accorde:
        raise ExempleError(
            "la cible réelle crée des ressources facturées sur le compte Outscale du "
            "mainteneur, et ne se lance pas sans son accord, demandé à chaque fois. "
            "Le drapeau --compte-reel-accorde est la trace de cet accord ; sans lui, refus."
        )
    if arguments.garder and not cible["emulateur"]:
        raise ExempleError(
            "`--garder` contre le compte réel laisse des ressources facturées debout."
        )

    run_id = f"ex{int(time.time()) % 100000}{secrets.token_hex(2)}"
    env = dict(os.environ)
    adopte = False

    if cible["emulateur"]:
        sonde = lancer(
            [binaire("feint"), "wait", "--addr", ADRESSE, "--timeout", "2s"], capture=True
        )
        adopte = sonde.returncode == 0
        if not adopte:
            demarrage = lancer(
                [
                    binaire("feint"),
                    "start",
                    "--addr",
                    ADRESSE,
                    "--vm",
                    "off",
                    "--cleanup",
                    "--timeout",
                    "180s",
                ],
                capture=True,
            )
            if demarrage.returncode != 0:
                raise ExempleError(f"feint n'a pas démarré :\n{demarrage.stderr}")
            print(demarrage.stdout.strip())
        env.update(environnement_emulateur())
        env.pop("OUTSCALE_API_URL", None)
        if adopte:
            refuser_emulateur_habite(env)
    else:
        print("cible : le compte Outscale réel.")
    region = env.get("OSC_REGION", "eu-west-2")

    # Tout ce qui suit est sous un `finally` qui arrête l'émulateur qu'on a
    # démarré : un échec avant la plateforme (la référence de résidu, par
    # exemple) le laissait debout, mesuré au premier run.
    try:
        return _exercice(arguments, cible, env, region, run_id)
    finally:
        if cible["emulateur"] and not adopte and not arguments.garder:
            lancer([binaire("feint"), "stop", "--addr", ADRESSE], capture=True)


def _exercice(
    arguments: argparse.Namespace,
    cible: dict[str, Any],
    env: dict[str, str],
    region: str,
    run_id: str,
) -> int:
    """La référence de résidu, la plateforme, les contrôles, le playbook, la destruction."""
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    print("prise de la référence de résidu.")
    residu_cmd = [sys.executable, str(ROOT / "scripts" / "residue.py"), "capture"]
    if lancer(residu_cmd, env=env).returncode != 0:
        raise ExempleError("la référence de résidu n'a pas pu être prise")

    journal = TRAVAIL / f"journal-{run_id}.json"
    journal.unlink(missing_ok=True)
    env["ANSIBLE_CALLBACK_PLUGINS"] = str(RAPPELS)
    env["ANSIBLE_CALLBACKS_ENABLED"] = "journal"
    env["EXEMPLE_JOURNAL"] = str(journal)
    env["ANSIBLE_COLLECTIONS_PATH"] = str(ROOT)
    env["ANSIBLE_LOCALHOST_WARNING"] = "False"
    # Une source d'inventaire qui ne se parse pas est un avertissement pour
    # Ansible, pas un échec : `ansible-inventory --list` rend alors un graphe
    # vide et sort en 0. Cette variable en fait une erreur.
    env["ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED"] = "True"

    init = terraform("init", env, run_id, region=region)
    if init.returncode != 0:
        raise ExempleError(f"`terraform init` a échoué :\n{init.stderr}")

    verdict_residu = "non vérifié"
    code = 0
    echec_final = 0
    try:
        print("\n--- terraform apply ---", flush=True)
        applique = terraform("apply", env, run_id, region=region)
        if applique.returncode != 0:
            raise ExempleError(
                f"`terraform apply` a échoué :\n{applique.stdout[-3000:]}{applique.stderr[-3000:]}"
            )
        sorties = sorties_de(run_id, env, region)
        sorties_fichier = TRAVAIL / f"plateforme-{run_id}.json"
        sorties_fichier.write_text(json.dumps(sorties, indent=2), encoding="utf-8")
        print(f"plateforme bâtie : {sorties['expected']['total']} machines, préfixe {run_id}")

        controler_plan_de_controle(env, sorties)
        controler_inventaire(inventaire(env), sorties)

        extra = {"cible": arguments.cible}
        code = jouer("modules.yml", env, extra, sorties_fichier)
    finally:
        if arguments.garder:
            print(
                "\nplateforme conservée. La détruire avec :\n"
                "  terraform -chdir=examples/stack destroy "
                f"-state=build/example/terraform-{run_id}.tfstate "
                f"-var=prefix={run_id} -var=region={region}"
            )
        else:
            print("\n--- terraform destroy ---", flush=True)
            detruit = terraform("destroy", env, run_id, region=region)
            if detruit.returncode != 0:
                print(
                    f"LA DESTRUCTION A ÉCHOUÉ. Ne pas en rester là :\n{detruit.stderr[-3000:]}",
                    file=sys.stderr,
                )
                echec_final = 1
            verifier = [sys.executable, str(ROOT / "scripts" / "residue.py"), "verify"]
            if lancer(verifier, env=env).returncode != 0:
                echec_final = 1
                verdict_residu = "non vérifié"
            else:
                verdict_residu = "aucun (émulateur)" if cible["emulateur"] else "aucun"
        ecrit = ecrire_artefact(journal, arguments.cible, run_id, verdict_residu)
        if ecrit is not None:
            print(f"\ncouverture de cette exécution : {ecrit.relative_to(ROOT)}")
    return max(code, echec_final)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except ExempleError as erreur:
        print(f"erreur : {erreur}", file=sys.stderr)
        raise SystemExit(1) from erreur
