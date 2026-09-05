# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le runtime commun des modules générés : client, appel, pagination, état, erreurs.

Un module généré ne contient aucune logique : il déclare ce qu'il appelle
(`InfoModule`, `ActionModule`) et confie l'exécution à ce fichier.

Cinq décisions, et ce qu'elles coûtent :

1. **Le SDK officiel est le client d'exécution.** `osc_sdk_python.Gateway`
   embarque sa copie du contrat, dispatche `gateway.ReadVms(...)` vers
   l'action du même nom, refuse une action ou un paramètre que sa copie ne
   connaît pas, et signe les requêtes (AWS Signature v4, `osc4`). Le
   générateur ne devine aucun nom : une garde de test vérifie que le SDK
   installé connaît chaque action qu'un module appelle ;
2. **Les arguments partent sous le nom du contrat.** Le module porte, pour
   chaque option, le nom du contrat (`VmIds`) à côté du nom Ansible
   (`vm_ids`), et c'est le nom du contrat qui part ;
3. **Une liste se déroule jusqu'à la dernière page.** 36 lectures sur 74
   paginent par `NextPageToken` ; rendre la première page serait mentir. Le
   runtime enchaîne les pages et rend tout ce que l'API sait ;
4. **Une action répond tout de suite, et la ressource change d'état ensuite.**
   `StopVms` rend `stopping`. Quand un état est attendu, le runtime relit la
   ressource par la lecture de la même ressource, filtrée sur les
   identifiants, jusqu'à l'état visé, et n'envoie rien quand l'état est déjà
   là ;
5. **L'URL de l'API reste honorée de bout en bout.** `api_url`, puis
   `OSC_ENDPOINT_API`, remplacent l'hôte construit depuis la région, ce qui
   rend possible un émulateur local sans identifiants réels. C'est le nom que
   `feint env outscale`, `octl` et le fournisseur Terraform 1.7+ emploient.
"""

from __future__ import annotations

import time
import traceback
from collections import namedtuple

from ansible.module_utils.basic import env_fallback, missing_required_lib

try:
    import requests
    from osc_sdk_python import Gateway
    from osc_sdk_python.credentials import Endpoint

    HAS_OSC_SDK = True
    OSC_SDK_IMPORT_ERROR = None
except ImportError:
    HAS_OSC_SDK = False
    OSC_SDK_IMPORT_ERROR = traceback.format_exc()
    Gateway = None  # type: ignore[assignment,misc]
    Endpoint = None  # type: ignore[assignment,misc]
    requests = None  # type: ignore[assignment]


#: Ce qu'un module généré déclare pour une opération. `body_params` va de
#: l'option Ansible au nom du contrat.
Operation = namedtuple(
    "Operation",
    ["id", "method", "body_params", "payload_field", "is_list", "page_token"],
    defaults=({}, None, False, None),
)

#: Une action d'un module d'action, l'état attendu une fois faite, et si elle
#: agit même quand cet état est déjà atteint (`reboot` vise `running` et doit
#: redémarrer une machine qui tourne).
Action = namedtuple(
    "Action", ["name", "operation", "expected_state", "always"], defaults=(None, False)
)

#: Un module d'information : une lecture, et ses filtres.
InfoModule = namedtuple("InfoModule", ["resource", "operation"])

#: Un module d'action : le sélecteur commun, les actions qu'il regroupe, et
#: quand un état est attendu, le champ qui le porte, la lecture qui le rend,
#: la clé de `Filters` qui la restreint au sélecteur, et le champ qui
#: identifie chaque élément lu.
ActionModule = namedtuple(
    "ActionModule",
    [
        "resource",
        "selector",
        "actions",
        "state_field",
        "read_operation",
        "read_filter",
        "read_id_field",
    ],
    defaults=(None, None, None, None),
)

#: Le champ que toute réponse porte et qui n'est jamais la ressource.
RESPONSE_CONTEXT = "ResponseContext"

DEFAULT_WAIT_TIMEOUT = 600

#: Intervalle entre deux lectures de l'état, en secondes.
POLL_INTERVAL = 2

#: Remplaçable par un test : attendre pour de vrai n'y prouve rien.
_sleep = time.sleep


def outscale_argument_spec():
    """Les paramètres communs : identifiants, région, profil, URL.

    Aucun n'est obligatoire : le SDK lit `~/.osc/config.json` et
    l'environnement (`OSC_ACCESS_KEY`, `OSC_SECRET_KEY`, `OSC_REGION`,
    `OSC_ENDPOINT_API`, `OSC_PROFILE`), et un module qui exigerait ce que le
    SDK sait déjà trouver forcerait à recopier des secrets dans un playbook.
    """
    return {
        "access_key": {
            "type": "str",
            "no_log": False,
            "fallback": (env_fallback, ["OSC_ACCESS_KEY"]),
        },
        "secret_key": {
            "type": "str",
            "no_log": True,
            "fallback": (env_fallback, ["OSC_SECRET_KEY"]),
        },
        "region": {
            "type": "str",
            "fallback": (env_fallback, ["OSC_REGION"]),
        },
        "profile": {
            "type": "str",
            "fallback": (env_fallback, ["OSC_PROFILE"]),
        },
        "api_url": {
            "type": "str",
            # `OSC_ENDPOINT_API` est le nom que l'écosystème emploie, `feint
            # env outscale`, `octl` et le fournisseur Terraform 1.7+ compris :
            # un `eval $(feint env outscale)` doit suffire à viser l'émulateur.
            "fallback": (env_fallback, ["OSC_ENDPOINT_API", "OUTSCALE_API_URL"]),
        },
    }


def outscale_waitable_argument_spec():
    """Les paramètres d'attente d'un état."""
    return {
        "wait": {"type": "bool", "default": True},
        "wait_timeout": {"type": "int", "default": DEFAULT_WAIT_TIMEOUT},
    }


def build_client(module):
    """Construit l'unique client : l'environnement et le profil d'abord, les
    paramètres du module par-dessus, et l'URL explicite gagne."""
    if not HAS_OSC_SDK:
        module.fail_json(msg=missing_required_lib("osc-sdk-python"), exception=OSC_SDK_IMPORT_ERROR)
    params = module.params
    kwargs = {}
    if params.get("profile"):
        kwargs["profile"] = params["profile"]
    if params.get("access_key"):
        kwargs["access_key"] = params["access_key"]
    if params.get("secret_key"):
        kwargs["secret_key"] = params["secret_key"]
    if params.get("region"):
        kwargs["region"] = params["region"]
    if params.get("api_url"):
        kwargs["endpoints"] = Endpoint(api=params["api_url"])
    try:
        return Gateway(**kwargs)
    except Exception as error:  # le SDK lève TypeError, KeyError, OSError selon la cause
        module.fail_json(msg=f"the Outscale SDK could not build its client: {error}")


def arguments_for(module, operation):
    """Les mots-clés que le SDK attend, depuis les options renseignées.

    La clé envoyée est le nom du contrat, jamais le nom de l'option.
    """
    kwargs = {}
    for option, api_name in operation.body_params.items():
        value = module.params.get(option)
        if value is not None:
            kwargs[api_name] = value
    return kwargs


def _errors_of(response):
    """Les erreurs que l'API a écrites dans son corps, quand il y en a."""
    try:
        body = response.json()
    except ValueError:
        return []
    if not isinstance(body, dict):
        return []
    errors = body.get("Errors")
    return errors if isinstance(errors, list) else []


def call(module, client, operation, kwargs):
    """Appelle une action du SDK, et traduit son échec en `fail_json`.

    Une erreur dit quoi diagnostiquer : l'opération, le statut HTTP, et les
    erreurs que l'API a écrites (`Code`, `Type`, `Details`), sans jamais
    recopier ce que le module a envoyé.
    """
    try:
        method = getattr(client, operation.method)
        return method(**kwargs)
    except NotImplementedError as error:
        # `ActionNotExists`, `ParameterNotValid`, `ParameterIsRequired` et
        # `ParameterHasWrongType` héritent toutes de NotImplementedError : le
        # SDK refuse l'appel avant de l'envoyer, d'après sa copie du contrat.
        module.fail_json(
            msg=f"the installed osc-sdk-python refuses this call: {error}",
            operation=operation.id,
        )
    except requests.HTTPError as error:
        response = error.response
        status = response.status_code if response is not None else None
        module.fail_json(
            msg=f"the Outscale API refused {operation.id}: {error}",
            operation=operation.id,
            status=status,
            errors=_errors_of(response) if response is not None else [],
        )
    except requests.RequestException as error:
        module.fail_json(
            msg=f"the Outscale API could not be reached for {operation.id}: {error}",
            operation=operation.id,
        )


def strip_context(result):
    """La réponse sans son `ResponseContext`, qui n'est jamais la ressource."""
    if not isinstance(result, dict):
        return result
    return {key: value for key, value in result.items() if key != RESPONSE_CONTEXT}


def read_all(module, client, operation, kwargs):
    """Appelle une lecture, et déroule ses pages jusqu'à la dernière.

    Un jeton rendu deux fois de suite arrête la boucle : l'API ne le promet
    pas, et une boucle sans fin vaut moins qu'une liste tronquée dite.
    """
    if operation.page_token is None:
        return call(module, client, operation, kwargs)
    items = []
    token = None
    last = None
    seen = set()
    while True:
        page = dict(kwargs)
        if token:
            page[operation.page_token] = token
        result = call(module, client, operation, page)
        last = result if isinstance(result, dict) else {}
        if operation.payload_field is not None:
            items.extend(last.get(operation.payload_field) or [])
        token = last.get(operation.page_token)
        if not token or token in seen:
            break
        seen.add(token)
    merged = dict(last)
    merged.pop(operation.page_token, None)
    if operation.payload_field is not None:
        merged[operation.payload_field] = items
    return merged


def run_info_module(module, spec):
    """Lit une ressource, ou les liste, et rend tout ce que l'API sait."""
    client = build_client(module)
    operation = spec.operation
    result = read_all(module, client, operation, arguments_for(module, operation))
    payload = strip_context(result)
    if operation.payload_field is not None and isinstance(result, dict):
        payload = result.get(operation.payload_field)
        if operation.is_list and payload is None:
            payload = []
    key = _plural(spec.resource) if operation.is_list else spec.resource
    module.exit_json(changed=False, **{key: payload})


def _dig(item, path):
    """La valeur d'un chemin pointé (`State.Name`) dans un dictionnaire."""
    value = item
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return None if value is None else str(value)


def _ids(value):
    """Les identifiants d'un sélecteur, qu'il soit une liste ou une valeur seule."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def read_states(module, client, spec, ids):
    """L'état courant de chaque ressource visée, par identifiant.

    Un identifiant que la lecture ne rend pas est une erreur : le module ne
    devine pas l'état d'une ressource qu'il n'a pas vue.
    """
    read = spec.read_operation
    result = read_all(module, client, read, {"Filters": {spec.read_filter: list(ids)}})
    items = result.get(read.payload_field) or [] if isinstance(result, dict) else []
    states = {}
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        identifier = item.get(spec.read_id_field) if spec.read_id_field else None
        states[str(identifier) if identifier is not None else f"#{position}"] = _dig(
            item, spec.state_field
        )
    if spec.read_id_field:
        missing = sorted(set(ids) - set(states))
        if missing:
            module.fail_json(
                msg=f"the {spec.resource} {missing} could not be read by {read.id}",
                operation=read.id,
            )
    return states


def poll_states(module, client, spec, ids, expected, timeout):
    """Relit les ressources jusqu'à l'état attendu, et échoue en disant l'état lu.

    L'échec dit `changed=True` : l'action a été envoyée et acceptée, et un
    playbook rejoué doit le savoir.
    """
    deadline = time.monotonic() + timeout
    states = read_states(module, client, spec, ids)
    while any(state != expected for state in states.values()):
        if time.monotonic() >= deadline:
            module.fail_json(
                changed=True,
                msg=(
                    f"the action was accepted, but after {timeout} seconds some "
                    f"{_plural(spec.resource)} are not {expected!r}: "
                    + ", ".join(f"{k}={v!r}" for k, v in sorted(states.items()) if v != expected)
                ),
                states=states,
            )
        _sleep(POLL_INTERVAL)
        states = read_states(module, client, spec, ids)
    return states


def run_action_module(module, spec):
    """Déclenche une action, puis attend l'état attendu s'il est déclaré.

    Quatre choses qu'un module d'action doit tenir, et que celui-ci tient :

    * **ne rien envoyer quand l'état visé est déjà là**, et le dire par
      `changed=False` : `start` sur une machine qui tourne n'a rien à faire.
      Sauf pour une action déclarée `always`, comme `reboot` ;
    * **en check mode, ne rien envoyer**, mais lire l'état quand on le peut,
      pour annoncer le bon `changed` ;
    * **`changed` est vrai dès que l'API a accepté** : tout échec ultérieur de
      l'attente le dit ;
    * **attendre l'état, si on sait quoi attendre.** L'état visé vient d'un
      override, jamais du contrat, qui ne le dit pas.
    """
    wanted = module.params["action"]
    action = next((item for item in spec.actions if item.name == wanted), None)
    if action is None:
        module.fail_json(msg=f"unknown action {wanted!r}")
        return
    operation = action.operation
    kwargs = arguments_for(module, operation)
    wait = bool(module.params.get("wait", True))
    timeout = module.params.get("wait_timeout") or DEFAULT_WAIT_TIMEOUT

    # La vérification d'état demande ce que le générateur ne fournit
    # qu'ensemble : une lecture filtrée de la ressource, le champ qui porte
    # l'état, l'état attendu de cette action, et le sélecteur à relire.
    verifies = (
        spec.read_operation is not None
        and spec.read_filter is not None
        and spec.state_field is not None
        and action.expected_state is not None
        and spec.selector is not None
    )
    ids = _ids(module.params.get(spec.selector)) if verifies else []

    client = build_client(module)

    current = {}
    if verifies and not action.always:
        current = read_states(module, client, spec, ids)
        if all(state == action.expected_state for state in current.values()):
            module.exit_json(
                changed=False,
                msg=f"every {spec.resource} already is {action.expected_state!r}: nothing was sent",
                states=current,
            )

    if module.check_mode:
        extra = {"states": current} if current else {}
        module.exit_json(changed=True, msg="check mode: the action was not sent", **extra)

    result = call(module, client, operation, kwargs)

    extra = {}
    if verifies and wait:
        extra["states"] = poll_states(module, client, spec, ids, action.expected_state, timeout)
    module.exit_json(changed=True, result=strip_context(result), **extra)


def _plural(resource):
    """`vm_type` -> `vm_types`, pour la clé de retour d'une liste."""
    words = resource.split("_")
    last = words[-1]
    if last.endswith("y") and len(last) > 1 and last[-2] not in "aeiou":
        last = last[:-1] + "ies"
    elif last.endswith(("s", "sh", "ch", "x", "z")):
        last = last + "es"
    else:
        last = last + "s"
    return "_".join([*words[:-1], last])
