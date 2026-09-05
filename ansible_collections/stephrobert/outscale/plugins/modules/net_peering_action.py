#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : AcceptNetPeering, RejectNetPeering
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: net_peering_action
short_description: Perform an action on Outscale net peerings
version_added: 0.1.0
description:
- 'Trigger one of the following actions on existing net peerings: C(accept), C(reject).'
author:
- Stéphane Robert (@stephrobert)
options:
  action:
    description: The action to trigger on the net peerings.
    type: str
    required: true
    choices:
    - accept
    - reject
  net_peering_id:
    description: The ID of the Net peering you want to accept.
    type: str
    required: true
extends_documentation_fragment:
- stephrobert.outscale.outscale
- stephrobert.outscale.outscale.wait
notes:
- 'Every action answers at once: the API response is returned under RV(result), and the resource
  changes state afterwards.'
- When I(wait) is true, the module reads the net peering until its C(State.Name) reaches the
  expected value (C(accept) leads to C(active), C(reject) leads to C(rejected)), and reports
  C(changed=false) without sending anything when every net peering already is in that state.
"""

EXAMPLES = r"""
- name: Run accept on a net peering
  stephrobert.outscale.net_peering_action:
    region: eu-west-2
    action: accept
    net_peering_id: example-id
"""

RETURN = r"""
result:
  description: The API response of the action, without the response context.
  returned: when the action was sent
  type: dict
states:
  description: The C(State.Name) of each net peering, by identifier, read after the action.
  returned: when an expected state is declared for the action
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.stephrobert.outscale.plugins.module_utils.outscale import (  # noqa: E402
    Action,
    ActionModule,
    Operation,
    outscale_argument_spec,
    outscale_waitable_argument_spec,
    run_action_module,
)

#: Options propres au module, traduites depuis le contrat.
MODULE_ARGUMENT_SPEC = {
    "action": {
        "type": "str",
        "required": True,
        "choices": ["accept", "reject"],
    },
    "net_peering_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(outscale_waitable_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ActionModule(
    resource="net_peering",
    selector="net_peering_id",
    actions=(
        Action(
            name="accept",
            operation=Operation(
                id="AcceptNetPeering",
                method="AcceptNetPeering",
                body_params={"net_peering_id": "NetPeeringId"},
                payload_field="NetPeering",
            ),
            expected_state="active",
        ),
        Action(
            name="reject",
            operation=Operation(
                id="RejectNetPeering",
                method="RejectNetPeering",
                body_params={"net_peering_id": "NetPeeringId"},
            ),
            expected_state="rejected",
        ),
    ),
    state_field="State.Name",
    read_operation=Operation(
        id="ReadNetPeerings",
        method="ReadNetPeerings",
        body_params={"filters": "Filters"},
        payload_field="NetPeerings",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="NetPeeringIds",
    read_id_field="NetPeeringId",
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_action_module(module, MODULE)


if __name__ == "__main__":
    main()
