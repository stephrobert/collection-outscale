#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : RebootVms, StartVms, StopVms
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm_action
short_description: Perform an action on Outscale VMs
version_added: 0.1.0
description:
- 'Trigger one of the following actions on existing VMs: C(reboot), C(start), C(stop).'
author:
- Stéphane Robert (@stephrobert)
options:
  action:
    description: The action to trigger on the VMs.
    type: str
    required: true
    choices:
    - reboot
    - start
    - stop
  vm_ids:
    description: One or more IDs of the VMs you want to reboot.
    type: list
    required: true
    elements: str
  force_stop:
    description: Forces the VM to stop.
    type: bool
extends_documentation_fragment:
- stephrobert.outscale.outscale
- stephrobert.outscale.outscale.wait
notes:
- 'Every action answers at once: the API response is returned under RV(result), and the resource
  changes state afterwards.'
- When I(wait) is true, the module reads the VM until its C(State) reaches the expected value
  (C(reboot) leads to C(running), C(start) leads to C(running), C(stop) leads to C(stopped)),
  and reports C(changed=false) without sending anything when every VM already is in that state,
  except for C(reboot), which always acts.
"""

EXAMPLES = r"""
- name: Reboot VMs
  stephrobert.outscale.vm_action:
    region: eu-west-2
    action: reboot
    vm_ids:
    - example-id
- name: Start VMs
  stephrobert.outscale.vm_action:
    region: eu-west-2
    action: start
    vm_ids:
    - example-id
- name: Stop VMs
  stephrobert.outscale.vm_action:
    region: eu-west-2
    action: stop
    vm_ids:
    - example-id
"""

RETURN = r"""
result:
  description: The API response of the action, without the response context.
  returned: when the action was sent
  type: dict
  contains:
    Vms:
      description:
      - 'After C(start): Information about one or more started VMs.'
      - 'After C(stop): Information about one or more stopped VMs.'
      returned: after C(start), C(stop)
      type: list
      elements: dict
      contains:
        CurrentState:
          description:
          - The current state of the VM (C(InService) | C(OutOfService) | C(Unknown)).
          returned: when the API returns it
          type: str
        PreviousState:
          description:
          - The previous state of the VM (C(InService) | C(OutOfService) | C(Unknown)).
          returned: when the API returns it
          type: str
        VmId:
          description:
          - The ID of the VM.
          returned: when the API returns it
          type: str
states:
  description: The C(State) of each VM, by identifier, read after the action.
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
        "choices": ["reboot", "start", "stop"],
    },
    "vm_ids": {"type": "list", "elements": "str", "required": True},
    "force_stop": {"type": "bool"},
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
    resource="vm",
    selector="vm_ids",
    actions=(
        Action(
            name="reboot",
            operation=Operation(
                id="RebootVms",
                method="RebootVms",
                body_params={"vm_ids": "VmIds"},
            ),
            expected_state="running",
            always=True,
        ),
        Action(
            name="start",
            operation=Operation(
                id="StartVms",
                method="StartVms",
                body_params={"vm_ids": "VmIds"},
                payload_field="Vms",
                is_list=True,
            ),
            expected_state="running",
        ),
        Action(
            name="stop",
            operation=Operation(
                id="StopVms",
                method="StopVms",
                body_params={"force_stop": "ForceStop", "vm_ids": "VmIds"},
                payload_field="Vms",
                is_list=True,
            ),
            expected_state="stopped",
        ),
    ),
    state_field="State",
    read_operation=Operation(
        id="ReadVms",
        method="ReadVms",
        body_params={"filters": "Filters"},
        payload_field="Vms",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="VmIds",
    read_id_field="VmId",
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_action_module(module, MODULE)


if __name__ == "__main__":
    main()
