#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Contrat de laboratoire (@lab)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : tests/fixtures/widget/input/outscale.v1.yml
# Opérations : AcceptGadget, RejectGadget
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: gadget_action
short_description: Perform an action on Outscale gadgets
version_added: 9.9.9
description:
- 'Trigger one of the following actions on existing gadgets: C(accept), C(reject).'
author:
- Contrat de laboratoire (@lab)
options:
  action:
    description: The action to trigger on the gadgets.
    type: str
    required: true
    choices:
    - accept
    - reject
  gadget_id:
    description: The ID of the gadget you want to accept.
    type: str
    required: true
extends_documentation_fragment:
- lab.widget.outscale
- lab.widget.outscale.wait
notes:
- 'Every action answers at once: the API response is returned under RV(result), and the resource
  changes state afterwards.'
- When I(wait) is true, the module reads the gadget until its C(State.Name) reaches the expected
  value (C(accept) leads to C(active), C(reject) leads to C(rejected)), and reports C(changed=false)
  without sending anything when every gadget already is in that state.
"""

EXAMPLES = r"""
- name: Accept a gadget
  lab.widget.gadget_action:
    region: eu-west-2
    action: accept
    gadget_id: example-id
- name: Reject a gadget
  lab.widget.gadget_action:
    region: eu-west-2
    action: reject
    gadget_id: example-id
"""

RETURN = r"""
result:
  description: The API response of the action, without the response context.
  returned: when the action was sent
  type: dict
  contains:
    Gadget:
      description:
      - Not documented by the Outscale API contract.
      returned: after C(accept), C(reject)
      type: dict
      contains:
        GadgetId:
          description:
          - Not documented by the Outscale API contract.
          returned: when the API returns it
          type: str
        State:
          description:
          - Not documented by the Outscale API contract.
          returned: when the API returns it
          type: dict
states:
  description: The C(State.Name) of each gadget, by identifier, read after the action.
  returned: when an expected state is declared for the action
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.lab.widget.plugins.module_utils.outscale import (  # noqa: E402
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
    "gadget_id": {"type": "str", "required": True},
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
    resource="gadget",
    selector="gadget_id",
    actions=(
        Action(
            name="accept",
            operation=Operation(
                id="AcceptGadget",
                method="AcceptGadget",
                body_params={"gadget_id": "GadgetId"},
                payload_field="Gadget",
            ),
            expected_state="active",
        ),
        Action(
            name="reject",
            operation=Operation(
                id="RejectGadget",
                method="RejectGadget",
                body_params={"gadget_id": "GadgetId"},
                payload_field="Gadget",
            ),
            expected_state="rejected",
        ),
    ),
    state_field="State.Name",
    read_operation=Operation(
        id="ReadGadgets",
        method="ReadGadgets",
        body_params={"filters": "Filters"},
        payload_field="Gadgets",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="GadgetIds",
    read_id_field="GadgetId",
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_action_module(module, MODULE)


if __name__ == "__main__":
    main()
