#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateVm
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm
short_description: Manage the settings of an Outscale vm
version_added: 0.1.0
description:
- Set the settings of an existing Outscale vm (I(actions_on_next_boot), I(block_device_mappings),
  I(bsu_optimized), I(deletion_protection), I(is_source_dest_checked), I(keypair_name), I(nested_virtualization),
  I(performance), I(shutdown_behavior_configuration), I(user_data), I(vm_initiated_shutdown_behavior),
  I(vm_type)), and only what differs from what the API returns. Terraform provisions the vm,
  this module operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  actions_on_next_boot:
    description: 'The action to perform on the next boot of the VM. Accepted keys: C(SecureBoot).'
    type: dict
  block_device_mappings:
    description: One or more block device mappings of the VM.
    type: list
    elements: dict
  bsu_optimized:
    description: This parameter is not available. It is present in our API for the sake of
      historical compatibility with AWS.
    type: bool
  deletion_protection:
    description: If true, you cannot delete the VM unless you change this parameter back to
      false.
    type: bool
  is_source_dest_checked:
    description: (Net only) If true, the source/destination check is enabled. If false, it
      is disabled.
    type: bool
  keypair_name:
    description: The name of a keypair you want to associate with the VM. When you replace
      the keypair of a VM with another one, the metadata of the VM is modified to reflect
      the new public key, but the replacement is still not effective in the operating system
      of the VM. To complete the replacement and effectively apply the new keypair, you need
      to perform other actions inside the VM. For more information, see L(Modifying the Keypair
      of a VM, https://docs.outscale.com/en/userguide/Modifying-the-Keypair-of-a-VM.html).
    type: str
  nested_virtualization:
    description: (dedicated tenancy only) If true, nested virtualization is enabled. If false,
      it is disabled.
    type: bool
  performance:
    description: The performance of the VM.
    type: str
    choices:
    - medium
    - high
    - highest
  shutdown_behavior_configuration:
    description: 'Information about the actions performed by the orchestrator when the VM
      shuts down. Accepted keys: C(GuestAction), C(HostAction).'
    type: dict
  user_data:
    description: The Base64-encoded MIME user data, limited to 500 kibibytes (KiB).
    type: str
  vm_id:
    description: The ID of the VM.
    type: str
    required: true
  vm_initiated_shutdown_behavior:
    description: The VM behavior when you stop it. If set to `stop`, the VM stops. If set
      to `restart`, the VM stops then automatically restarts. If set to `terminate`, the VM
      stops and is terminated.
    type: str
  vm_type:
    description: The type of VM. For more information, see L(VM Types, https://docs.outscale.com/en/userguide/VM-Types.html).
    type: str
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the vm by I(vm_id), compares every option you give with what the API returns,
  and sends C(UpdateVm) only when something differs: a second run reports C(changed=false).
  In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a vm
  stephrobert.outscale.vm:
    region: eu-west-2
    vm_id: example-id
    bsu_optimized: true
"""

RETURN = r"""
vm:
  description: The vm, read after the update.
  returned: always
  type: dict
changes:
  description: 'What differed, by option: the value the API returned before, and the value
    you asked for.'
  returned: when something differed
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.stephrobert.outscale.plugins.module_utils.outscale import (  # noqa: E402
    ManageModule,
    Operation,
    outscale_argument_spec,
    run_manage_module,
)

#: Options propres au module, traduites depuis le contrat.
MODULE_ARGUMENT_SPEC = {
    "actions_on_next_boot": {"type": "dict"},
    "block_device_mappings": {"type": "list", "elements": "dict"},
    "bsu_optimized": {"type": "bool"},
    "deletion_protection": {"type": "bool"},
    "is_source_dest_checked": {"type": "bool"},
    "keypair_name": {"type": "str", "no_log": False},
    "nested_virtualization": {"type": "bool"},
    "performance": {
        "type": "str",
        "choices": ["medium", "high", "highest"],
    },
    "shutdown_behavior_configuration": {"type": "dict"},
    "user_data": {"type": "str"},
    "vm_id": {"type": "str", "required": True},
    "vm_initiated_shutdown_behavior": {"type": "str"},
    "vm_type": {"type": "str"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="vm",
    selector="vm_id",
    operation=Operation(
        id="UpdateVm",
        method="UpdateVm",
        body_params={
            "actions_on_next_boot": "ActionsOnNextBoot",
            "block_device_mappings": "BlockDeviceMappings",
            "bsu_optimized": "BsuOptimized",
            "deletion_protection": "DeletionProtection",
            "is_source_dest_checked": "IsSourceDestChecked",
            "keypair_name": "KeypairName",
            "nested_virtualization": "NestedVirtualization",
            "performance": "Performance",
            "shutdown_behavior_configuration": "ShutdownBehaviorConfiguration",
            "user_data": "UserData",
            "vm_id": "VmId",
            "vm_initiated_shutdown_behavior": "VmInitiatedShutdownBehavior",
            "vm_type": "VmType",
        },
        payload_field="Vm",
    ),
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
    compare={
        "actions_on_next_boot": "ActionsOnNextBoot",
        "block_device_mappings": "BlockDeviceMappings",
        "bsu_optimized": "BsuOptimized",
        "deletion_protection": "DeletionProtection",
        "is_source_dest_checked": "IsSourceDestChecked",
        "keypair_name": "KeypairName",
        "nested_virtualization": "NestedVirtualization",
        "performance": "Performance",
        "shutdown_behavior_configuration": "ShutdownBehaviorConfiguration",
        "user_data": "UserData",
        "vm_initiated_shutdown_behavior": "VmInitiatedShutdownBehavior",
        "vm_type": "VmType",
    },
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
