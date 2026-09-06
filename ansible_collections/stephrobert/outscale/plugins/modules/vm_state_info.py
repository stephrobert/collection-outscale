#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadVmsState
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm_state_info
short_description: Gather information about Outscale VM states
version_added: 0.1.0
description:
- List Outscale VM states, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  all_vms:
    description: If true, includes the status of all VMs. If false, only includes the status
      of running VMs.
    type: bool
    default: false
  filters:
    description: 'One or more filters. Accepted keys: C(MaintenanceEventCodes), C(MaintenanceEventDescriptions),
      C(MaintenanceEventsNotAfter), C(MaintenanceEventsNotBefore), C(SubregionNames), C(VmIds),
      C(VmStates).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List VM states
  stephrobert.outscale.vm_state_info:
    region: eu-west-2
  register: result
- name: List VM states filtered by VmIds
  stephrobert.outscale.vm_state_info:
    region: eu-west-2
    filters:
      VmIds:
      - example-id
  register: result
"""

RETURN = r"""
vm_states:
  description: The VM states.
  returned: always
  type: list
  elements: dict
  contains:
    MaintenanceEvents:
      description:
      - One or more scheduled events associated with the VM.
      returned: when the API returns it
      type: list
      elements: dict
    SubregionName:
      description:
      - The name of the Subregion of the VM.
      returned: when the API returns it
      type: str
    VmId:
      description:
      - The ID of the VM.
      returned: when the API returns it
      type: str
    VmState:
      description:
      - The state of the VM (C(pending) | C(running) | C(stopping) | C(stopped) | C(shutting-down)
        | C(terminated) | C(quarantine)).
      returned: when the API returns it
      type: str
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.stephrobert.outscale.plugins.module_utils.outscale import (  # noqa: E402
    InfoModule,
    Operation,
    outscale_argument_spec,
    run_info_module,
)

#: Options propres au module, traduites depuis le contrat.
MODULE_ARGUMENT_SPEC = {
    "all_vms": {"type": "bool", "default": False},
    "filters": {"type": "dict"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = InfoModule(
    resource="vm_state",
    operation=Operation(
        id="ReadVmsState",
        method="ReadVmsState",
        body_params={"all_vms": "AllVms", "filters": "Filters"},
        payload_field="VmStates",
        is_list=True,
        page_token="NextPageToken",
    ),
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_info_module(module, MODULE)


if __name__ == "__main__":
    main()
