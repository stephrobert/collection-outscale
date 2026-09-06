"""Le runtime envoie le nom du contrat, déroule les pages, relit l'état, et ne ment pas."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ansible_collections.stephrobert.outscale.plugins.module_utils import (  # noqa: E402
    outscale as runtime,
)


class _Module:
    def __init__(self, params: dict[str, Any], check_mode: bool = False) -> None:
        self.params = params
        self.check_mode = check_mode
        self.exited: dict[str, Any] | None = None
        self.failed: dict[str, Any] | None = None

    def exit_json(self, **kwargs: Any) -> None:
        self.exited = kwargs
        raise SystemExit(0)

    def fail_json(self, **kwargs: Any) -> None:
        self.failed = kwargs
        raise SystemExit(1)


class _Gateway:
    """Un double du SDK : chaque action est un attribut, et les appels sont notés."""

    def __init__(self, states: list[str] | None = None, pages: int = 1) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.states = list(states or ["running"])
        self.reads = 0
        self.pages = pages

    def __getattr__(self, action: str) -> Any:
        def call(**kwargs: Any) -> dict[str, Any]:
            self.calls.append((action, kwargs))
            return self._answer(action, kwargs)

        return call

    def _answer(self, action: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        contexte = {"ResponseContext": {"RequestId": "r"}}
        if action == "ReadVms":
            self.reads += 1
            state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            ids = (kwargs.get("Filters") or {}).get("VmIds") or ["i-1", "i-2"]
            page = kwargs.get("NextPageToken")
            numero = int(page[1:]) if page else 1
            vms = [{"VmId": f"{i}", "State": state, "Page": numero} for i in ids]
            reponse: dict[str, Any] = {**contexte, "Vms": vms}
            if numero < self.pages:
                reponse["NextPageToken"] = f"p{numero + 1}"
            return reponse
        if action in ("StartVms", "StopVms", "RebootVms"):
            return {**contexte, "Vms": [{"VmId": i, "CurrentState": "x"} for i in kwargs["VmIds"]]}
        if action == "ReadAdminPassword":
            return {**contexte, "AdminPassword": "s3cret", "VmId": kwargs["VmId"]}
        return contexte


@pytest.fixture(autouse=True)
def _sans_attente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Attendre pour de vrai ne prouve rien : la pause est neutralisée."""
    monkeypatch.setattr(runtime, "_sleep", lambda seconds: None)


def _use(monkeypatch: pytest.MonkeyPatch, gateway: _Gateway) -> _Gateway:
    monkeypatch.setattr(runtime, "build_client", lambda module: gateway)
    return gateway


READ = runtime.Operation(
    id="ReadVms",
    method="ReadVms",
    body_params={"filters": "Filters"},
    payload_field="Vms",
    is_list=True,
    page_token="NextPageToken",
)


def _action_spec(*, with_state: bool = True) -> runtime.ActionModule:
    start = runtime.Operation(
        id="StartVms", method="StartVms", body_params={"vm_ids": "VmIds"}, payload_field="Vms"
    )
    stop = runtime.Operation(
        id="StopVms",
        method="StopVms",
        body_params={"vm_ids": "VmIds", "force_stop": "ForceStop"},
        payload_field="Vms",
    )
    reboot = runtime.Operation(id="RebootVms", method="RebootVms", body_params={"vm_ids": "VmIds"})
    if not with_state:
        return runtime.ActionModule(
            resource="vm",
            selector="vm_ids",
            actions=(runtime.Action("start", start), runtime.Action("stop", stop)),
        )
    return runtime.ActionModule(
        resource="vm",
        selector="vm_ids",
        actions=(
            runtime.Action("start", start, expected_state="running"),
            runtime.Action("stop", stop, expected_state="stopped"),
            runtime.Action("reboot", reboot, expected_state="running", always=True),
        ),
        state_field="State",
        read_operation=READ,
        read_filter="VmIds",
        read_id_field="VmId",
    )


# ---- les lectures ------------------------------------------------------------


def test_le_runtime_envoie_le_nom_du_contrat_et_non_celui_de_loption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _use(monkeypatch, _Gateway(["stopped", "stopping", "stopped"]))
    module = _Module({"action": "stop", "vm_ids": ["i-1"], "force_stop": True, "wait": True})
    module.params["vm_ids"] = ["i-1"]
    gateway.states = ["running", "stopping", "stopped"]
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert ("StopVms", {"VmIds": ["i-1"], "ForceStop": True}) in gateway.calls


def test_une_liste_rend_le_champ_utile_sous_le_nom_pluriel(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = _use(monkeypatch, _Gateway())
    module = _Module({"filters": None})
    with pytest.raises(SystemExit):
        runtime.run_info_module(module, runtime.InfoModule(resource="vm", operation=READ))
    assert module.exited is not None
    assert module.exited["changed"] is False
    assert [vm["VmId"] for vm in module.exited["vms"]] == ["i-1", "i-2"]
    assert gateway.calls == [("ReadVms", {})]


def test_une_liste_se_deroule_jusqua_la_derniere_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """36 lectures sur 74 paginent : la première page n'est pas la liste."""
    gateway = _use(monkeypatch, _Gateway(pages=3))
    module = _Module({"filters": {"VmIds": ["i-1"]}})
    with pytest.raises(SystemExit):
        runtime.run_info_module(module, runtime.InfoModule(resource="vm", operation=READ))
    assert [kwargs.get("NextPageToken") for _, kwargs in gateway.calls] == [None, "p2", "p3"]
    assert module.exited is not None
    assert [vm["Page"] for vm in module.exited["vms"]] == [1, 2, 3]
    assert all(kwargs["Filters"] == {"VmIds": ["i-1"]} for _, kwargs in gateway.calls)


def test_un_jeton_qui_boucle_arrete_la_lecture(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boucle(_Gateway):
        def _answer(self, action: str, kwargs: dict[str, Any]) -> dict[str, Any]:
            return {"Vms": [{"VmId": "i-1"}], "NextPageToken": "same"}

    gateway = _use(monkeypatch, _Boucle())
    module = _Module({"filters": None})
    with pytest.raises(SystemExit):
        runtime.run_info_module(module, runtime.InfoModule(resource="vm", operation=READ))
    assert len(gateway.calls) == 2
    assert module.exited is not None and len(module.exited["vms"]) == 2


def test_une_charge_utile_indecidable_rend_la_reponse_sans_son_contexte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _Gateway())
    lecture = runtime.Operation(
        id="ReadAdminPassword", method="ReadAdminPassword", body_params={"vm_id": "VmId"}
    )
    module = _Module({"vm_id": "i-1"})
    with pytest.raises(SystemExit):
        runtime.run_info_module(
            module, runtime.InfoModule(resource="admin_password", operation=lecture)
        )
    assert module.exited == {
        "changed": False,
        "admin_password": {"AdminPassword": "s3cret", "VmId": "i-1"},
    }


def test_un_appel_refuse_par_le_sdk_echoue_en_le_nommant(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Refus(_Gateway):
        def _answer(self, action: str, kwargs: dict[str, Any]) -> dict[str, Any]:
            raise NotImplementedError(f"Action {action} does not exists for python sdk")

    _use(monkeypatch, _Refus())
    module = _Module({"filters": None})
    with pytest.raises(SystemExit):
        runtime.run_info_module(module, runtime.InfoModule(resource="vm", operation=READ))
    assert module.failed is not None
    assert module.failed["operation"] == "ReadVms"
    assert "refuses" in module.failed["msg"]


def test_une_erreur_de_lapi_porte_le_statut_et_les_erreurs_du_corps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import requests

    class _Reponse:
        status_code = 400

        def json(self) -> dict[str, Any]:
            return {"Errors": [{"Code": "4025", "Type": "InvalidParameterValue"}]}

    class _Api(_Gateway):
        def _answer(self, action: str, kwargs: dict[str, Any]) -> dict[str, Any]:
            raise requests.HTTPError("Client Error", response=_Reponse())  # type: ignore[arg-type]

    _use(monkeypatch, _Api())
    module = _Module({"filters": None})
    with pytest.raises(SystemExit):
        runtime.run_info_module(module, runtime.InfoModule(resource="vm", operation=READ))
    assert module.failed is not None
    assert module.failed["status"] == 400
    assert module.failed["errors"][0]["Code"] == "4025"


# ---- les actions -------------------------------------------------------------


def test_une_action_dont_letat_est_deja_atteint_ne_change_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`start` sur des machines qui tournent n'a rien à faire, et le dit par `changed=False`."""
    gateway = _use(monkeypatch, _Gateway(["running"]))
    module = _Module({"action": "start", "vm_ids": ["i-1", "i-2"], "wait": True})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert [nom for nom, _ in gateway.calls] == ["ReadVms"]
    assert module.exited is not None
    assert module.exited["changed"] is False
    assert module.exited["states"] == {"i-1": "running", "i-2": "running"}


def test_apres_lacceptation_le_module_relit_jusqua_letat_attendu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _use(monkeypatch, _Gateway(["stopped", "pending", "pending", "running"]))
    module = _Module({"action": "start", "vm_ids": ["i-1"], "wait": True, "wait_timeout": 30})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert ("StartVms", {"VmIds": ["i-1"]}) in gateway.calls
    assert module.exited is not None
    assert module.exited["changed"] is True
    assert module.exited["states"] == {"i-1": "running"}
    assert module.exited["result"] == {"Vms": [{"VmId": "i-1", "CurrentState": "x"}]}
    assert gateway.reads == 4


def test_la_relecture_est_filtree_sur_les_identifiants_vises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _use(monkeypatch, _Gateway(["stopped", "running"]))
    module = _Module({"action": "start", "vm_ids": ["i-7"], "wait": True})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    lectures = [kwargs for nom, kwargs in gateway.calls if nom == "ReadVms"]
    assert lectures and all(k == {"Filters": {"VmIds": ["i-7"]}} for k in lectures)


def test_une_action_always_agit_meme_si_letat_est_atteint(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = _use(monkeypatch, _Gateway(["running"]))
    module = _Module({"action": "reboot", "vm_ids": ["i-1"], "wait": True})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert ("RebootVms", {"VmIds": ["i-1"]}) in gateway.calls
    assert module.exited is not None and module.exited["changed"] is True


def test_un_etat_jamais_atteint_echoue_en_disant_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'action a été acceptée : un échec après coup doit dire que la machine a bougé."""
    _use(monkeypatch, _Gateway(["stopped", "pending"]))
    horloge = iter([0.0, 0.0, 1.0, 100.0, 200.0, 300.0])
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(horloge))
    module = _Module({"action": "start", "vm_ids": ["i-1"], "wait": True, "wait_timeout": 5})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert module.failed is not None
    assert module.failed["changed"] is True
    assert module.failed["states"] == {"i-1": "pending"}
    assert "'running'" in module.failed["msg"]


def test_un_identifiant_que_la_lecture_ne_rend_pas_est_une_erreur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Muet(_Gateway):
        def _answer(self, action: str, kwargs: dict[str, Any]) -> dict[str, Any]:
            if action == "ReadVms":
                return {"Vms": []}
            return super()._answer(action, kwargs)

    _use(monkeypatch, _Muet())
    module = _Module({"action": "start", "vm_ids": ["i-9"], "wait": True})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert module.failed is not None and "i-9" in module.failed["msg"]


def test_sans_attente_lapi_est_appelee_et_letat_nest_pas_relu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _use(monkeypatch, _Gateway(["stopped"]))
    module = _Module({"action": "start", "vm_ids": ["i-1"], "wait": False})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert [nom for nom, _ in gateway.calls] == ["ReadVms", "StartVms"]
    assert module.exited is not None
    assert module.exited["changed"] is True and "states" not in module.exited


def test_sans_etat_attendu_laction_est_envoyee_sans_lecture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _use(monkeypatch, _Gateway())
    module = _Module({"action": "start", "vm_ids": ["i-1"], "wait": True})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec(with_state=False))
    assert [nom for nom, _ in gateway.calls] == ["StartVms"]
    assert module.exited == {
        "changed": True,
        "result": {"Vms": [{"VmId": "i-1", "CurrentState": "x"}]},
    }


def test_le_check_mode_lit_letat_mais_nenvoie_rien(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = _use(monkeypatch, _Gateway(["stopped"]))
    # `wait_timeout` court : une garde neutralisée par la falsification enverrait
    # l'action puis relirait l'état jusqu'au délai, pause comprise ; à 600 s,
    # c'était dix minutes de boucle avant l'échec attendu, mesuré sous `check`.
    module = _Module(
        {"action": "start", "vm_ids": ["i-1"], "wait": True, "wait_timeout": 1},
        check_mode=True,
    )
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert [nom for nom, _ in gateway.calls] == ["ReadVms"]
    assert module.exited is not None and module.exited["changed"] is True


def test_le_check_mode_dit_changed_false_quand_letat_est_deja_la(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _Gateway(["running"]))
    module = _Module(
        {"action": "start", "vm_ids": ["i-1"], "wait": True, "wait_timeout": 1},
        check_mode=True,
    )
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert module.exited is not None and module.exited["changed"] is False


def test_un_etat_imbrique_se_lit_par_un_chemin_pointe() -> None:
    assert runtime._dig({"State": {"Name": "active"}}, "State.Name") == "active"
    assert runtime._dig({"State": "running"}, "State") == "running"
    assert runtime._dig({"State": "running"}, "State.Name") is None


def test_une_action_inconnue_est_refusee(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _Gateway())
    module = _Module({"action": "explode", "vm_ids": ["i-1"]})
    with pytest.raises(SystemExit):
        runtime.run_action_module(module, _action_spec())
    assert module.failed is not None and "explode" in module.failed["msg"]
