"""Ce que l'artefact d'un run compte comme couvert, et ce qu'il refuse de compter.

Le journal vient d'Ansible, par un plugin de rappel, et pas d'une analyse du
playbook : **joué n'est pas appelé**. Une tâche gardée par un `when` non
satisfait ne touche jamais l'API, et une route que feint décline répond
`feint does not serve` sans rien exercer. Les compter ferait de l'artefact un
compteur de bonnes intentions.
"""

from __future__ import annotations

from typing import Any

import example
import residue


def _journal(*taches: dict[str, Any], **faits: Any) -> dict[str, Any]:
    return {"taches": list(taches), "faits": faits}


def _tache(module: str, verdict: str = "ok", **reste: Any) -> dict[str, Any]:
    return {"module": module, "tache": module, "verdict": verdict, "changed": False, **reste}


def test_un_module_joue_est_compte() -> None:
    resultat = example.artefact(
        _journal(_tache("stephrobert.outscale.vm_info")), "emulateur", "abc", "aucun"
    )
    assert resultat["modules_joues"] == ["vm_info"]
    assert resultat["modules_appeles_sans_reponse"] == []


def test_une_route_que_feint_decline_est_appelee_mais_pas_jouee() -> None:
    """Un 501 `not_emulated` ou un 404 `does not serve` n'exerce rien : le compter
    ferait passer une limite de l'émulateur pour une preuve."""
    resultat = example.artefact(
        _journal(
            _tache(
                "stephrobert.outscale.vm_console_output_info",
                msg="the Outscale API refused ReadConsoleOutput: feint does not serve it",
            ),
            _tache("stephrobert.outscale.vm_admin_password_info", msg="501 not_emulated"),
        ),
        "emulateur",
        "abc",
        "aucun (émulateur)",
    )
    assert resultat["modules_joues"] == []
    assert resultat["modules_appeles_sans_reponse"] == [
        "vm_admin_password_info",
        "vm_console_output_info",
    ]


def test_une_tache_sautee_nest_pas_une_couverture() -> None:
    """Une tâche que `when` a écartée n'a parlé à personne."""
    resultat = example.artefact(
        _journal(_tache("stephrobert.outscale.net_peering_info", verdict="skipped")),
        "emulateur",
        "abc",
        "aucun",
    )
    assert resultat["modules_joues"] == []
    assert resultat["modules_appeles_sans_reponse"] == ["net_peering_info"]


def test_un_module_joue_une_fois_et_saute_ailleurs_compte_comme_joue() -> None:
    """La question posée est « a-t-il tourné », pas « toutes ses tâches ont-elles tourné »."""
    resultat = example.artefact(
        _journal(
            _tache("stephrobert.outscale.vm_action", verdict="skipped"),
            _tache("stephrobert.outscale.vm_action", verdict="changed"),
        ),
        "emulateur",
        "abc",
        "aucun",
    )
    assert resultat["modules_joues"] == ["vm_action"]


def test_les_faits_du_recensement_passent_dans_lartefact() -> None:
    resultat = example.artefact(
        _journal(
            _tache("stephrobert.outscale.vm_action", verdict="changed"),
            non_emules=["net_info"],
            idempotences_prouvees=["vm_action.stop"],
        ),
        "emulateur",
        "abc",
        "aucun (émulateur)",
    )
    assert resultat["routes_non_servies"] == ["net_info"]
    assert resultat["idempotence_prouvee"] == ["vm_action.stop"]
    assert resultat["residu"] == "aucun (émulateur)"


# ---- le résidu ---------------------------------------------------------------


def test_une_ressource_apparue_est_un_residu() -> None:
    """Une adresse publique sans tag survit à une destruction interrompue, et c'est
    ce différentiel qui le dit."""
    avant = {"public-ip": {}, "vm": {"i-1": "web01"}}
    apres = {"public-ip": {"eipalloc-1": "192.0.2.2"}, "vm": {"i-1": "web01"}}
    apparus, disparus = residue.ecarts(avant, apres)
    assert apparus == ["  public-ip  192.0.2.2  (eipalloc-1)"] and disparus == []


def test_une_ressource_disparue_est_plus_grave_quun_residu() -> None:
    avant = {"vm": {"i-1": "web01", "i-9": "de-quelquun-dautre"}}
    apres = {"vm": {"i-1": "web01"}}
    apparus, disparus = residue.ecarts(avant, apres)
    assert apparus == [] and disparus == ["  vm  de-quelquun-dautre  (i-9)"]


def test_un_compte_inchange_na_ni_residu_ni_disparition() -> None:
    etat = {"vm": {"i-1": "web01"}, "keypair": {"cle": "cle"}}
    assert residue.ecarts(etat, dict(etat)) == ([], [])


def test_le_libelle_dune_ressource_est_son_tag_name() -> None:
    assert residue.libelle({"Tags": [{"Key": "Name", "Value": "web"}]}) == "web"
    assert residue.libelle({"LoadBalancerName": "front"}) == "front"
    assert residue.libelle({}) == "sans nom"
