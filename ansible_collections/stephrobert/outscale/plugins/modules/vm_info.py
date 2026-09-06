#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadVms
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm_info
short_description: Gather information about Outscale VMs
version_added: 0.1.0
description:
- List Outscale VMs, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(Architectures), C(BlockDeviceMappingDeleteOnVmDeletion),
      C(BlockDeviceMappingDeviceNames), C(BlockDeviceMappingLinkDates), C(BlockDeviceMappingStates),
      C(BlockDeviceMappingVolumeIds), C(BootModes), C(ClientTokens), C(CreationDates), C(ImageIds),
      C(IsSourceDestChecked), C(KeypairNames), C(LaunchNumbers), C(Lifecycles), C(NetIds),
      C(NicAccountIds), C(NicDescriptions), C(NicIsSourceDestChecked), C(NicLinkNicDeleteOnVmDeletion),
      C(NicLinkNicDeviceNumbers), C(NicLinkNicLinkNicDates), C(NicLinkNicLinkNicIds), C(NicLinkNicStates),
      C(NicLinkNicVmAccountIds), C(NicLinkNicVmIds), C(NicLinkPublicIpAccountIds), C(NicLinkPublicIpLinkPublicIpIds),
      C(NicLinkPublicIpPublicIpIds), C(NicLinkPublicIpPublicIps), C(NicMacAddresses), C(NicNetIds),
      C(NicNicIds), C(NicPrivateIpsLinkPublicIpAccountIds), C(NicPrivateIpsLinkPublicIpIds),
      C(NicPrivateIpsPrimaryIp), C(NicPrivateIpsPrivateIps), C(NicSecurityGroupIds), C(NicSecurityGroupNames),
      C(NicStates), C(NicSubnetIds), C(NicSubregionNames), C(Platforms), C(PrivateIps), C(ProductCodes),
      C(PublicIps), C(ReservationIds), C(RootDeviceNames), C(RootDeviceTypes), C(SecurityGroupIds),
      C(SecurityGroupNames), C(StateReasonCodes), C(StateReasonMessages), C(StateReasons),
      C(SubnetIds), C(SubregionNames), C(TagKeys), C(TagValues), C(Tags), C(Tenancies), C(TpmEnabled),
      C(VmIds), C(VmSecurityGroupIds), C(VmSecurityGroupNames), C(VmStateCodes), C(VmStateNames),
      C(VmTypes).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List VMs
  stephrobert.outscale.vm_info:
    region: eu-west-2
  register: result
- name: Read VMs by ID
  stephrobert.outscale.vm_info:
    region: eu-west-2
    filters:
      VmIds:
      - example-id
  register: result
- name: List VMs matching a tag
  stephrobert.outscale.vm_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
vms:
  description: The VMs.
  returned: always
  type: list
  elements: dict
  contains:
    ActionsOnNextBoot:
      description:
      - The action to perform on the next boot of the VM.
      returned: when the API returns it
      type: dict
    Architecture:
      description:
      - The architecture of the VM (C(i386) | C(x86_64)).
      returned: when the API returns it
      type: str
    BlockDeviceMappings:
      description:
      - The block device mapping of the VM.
      returned: when the API returns it
      type: list
      elements: dict
    BootMode:
      description:
      - The boot mode of the VM.
      returned: when the API returns it
      type: str
    BsuOptimized:
      description:
      - This parameter is not available. It is present in our API for the sake of historical
        compatibility with AWS.
      returned: when the API returns it
      type: bool
    ClientToken:
      description:
      - The idempotency token provided when launching the VM.
      returned: when the API returns it
      type: str
    CreationDate:
      description:
      - The date and time (UTC) at which the VM was created.
      returned: when the API returns it
      type: str
    DeletionProtection:
      description:
      - If true, you cannot delete the VM unless you change this parameter back to false.
      returned: when the API returns it
      type: bool
    Hypervisor:
      description:
      - The hypervisor type of the VMs (C(ovm) | C(xen)).
      returned: when the API returns it
      type: str
    ImageId:
      description:
      - The ID of the OMI used to create the VM.
      returned: when the API returns it
      type: str
    IsSourceDestChecked:
      description:
      - (Net only) If true, the source/destination check is enabled. If false, it is disabled.
      returned: when the API returns it
      type: bool
    KeypairName:
      description:
      - The name of the keypair used when launching the VM.
      returned: when the API returns it
      type: str
    LaunchNumber:
      description:
      - The number for the VM when launching a group of several VMs (for example, C(0), C(1),
        C(2), and so on).
      returned: when the API returns it
      type: int
    NestedVirtualization:
      description:
      - If true, nested virtualization is enabled. If false, it is disabled.
      returned: when the API returns it
      type: bool
    NetId:
      description:
      - The ID of the Net in which the VM is running.
      returned: when the API returns it
      type: str
    Nics:
      description:
      - (Net only) The network interface cards (NICs) the VMs are attached to.
      returned: when the API returns it
      type: list
      elements: dict
    OsFamily:
      description:
      - Indicates the operating system (OS) of the VM.
      returned: when the API returns it
      type: str
    Performance:
      description:
      - The performance of the VM.
      returned: when the API returns it
      type: str
    Placement:
      description:
      - Information about the placement of the VM.
      returned: when the API returns it
      type: dict
    PrivateDnsName:
      description:
      - The name of the private DNS.
      returned: when the API returns it
      type: str
    PrivateIp:
      description:
      - The primary private IP of the VM.
      returned: when the API returns it
      type: str
    ProductCodes:
      description:
      - The product codes associated with the OMI used to create the VM.
      returned: when the API returns it
      type: list
      elements: str
    PublicDnsName:
      description:
      - The name of the public DNS.
      returned: when the API returns it
      type: str
    PublicIp:
      description:
      - The public IP of the VM.
      returned: when the API returns it
      type: str
    ReservationId:
      description:
      - The reservation ID of the VM.
      returned: when the API returns it
      type: str
    RootDeviceName:
      description:
      - The name of the root device for the VM (for example, C(/dev/sda1)).
      returned: when the API returns it
      type: str
    RootDeviceType:
      description:
      - The type of root device used by the VM (always C(bsu)).
      returned: when the API returns it
      type: str
    SecurityGroups:
      description:
      - One or more security groups associated with the VM.
      returned: when the API returns it
      type: list
      elements: dict
    ShutdownBehaviorConfiguration:
      description:
      - Information about the actions performed by the orchestrator when the VM shuts down.
      returned: when the API returns it
      type: dict
    State:
      description:
      - The state of the VM (C(pending) | C(running) | C(stopping) | C(stopped) | C(shutting-down)
        | C(terminated) | C(quarantine)).
      returned: when the API returns it
      type: str
    StateReason:
      description:
      - The reason explaining the current state of the VM. For more information, see L(Creating
        VMs > VM State Reference, https://docs.outscale.com/en/userguide/Creating-VMs.html#_vm_state_reference_statereason_2).
      returned: when the API returns it
      type: str
    SubnetId:
      description:
      - The ID of the Subnet for the VM.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the VM.
      returned: when the API returns it
      type: list
      elements: dict
    TpmEnabled:
      description:
      - If true, a virtual Trusted Platform Module (vTPM) is enabled on the VM. If false,
        it is not. The default behavior for this parameter varies depending on the source
        OMI of the VM. If the C(TpmMandatory) parameter of the source OMI is true, a vTPM
        has to be attached to the VM and it will be created by default. Setting C(TpmEnabled)
        to false will cause the creation request to fail. If the C(TpmMandatory) parameter
        of the source OMI is false, only setting C(TpmEnabled) to true will create and attach
        a vTPM to the VM.
      returned: when the API returns it
      type: bool
    UserData:
      description:
      - The Base64-encoded MIME user data.
      returned: when the API returns it
      type: str
    VmId:
      description:
      - The ID of the VM.
      returned: when the API returns it
      type: str
    VmInitiatedShutdownBehavior:
      description:
      - 'The VM behavior when you stop it. If set to C(stop), the VM stops. If set to C(restart),
        the VM stops then automatically restarts. If set to C(terminate), the VM stops and
        is deleted. Important: This parameter is deprecated in favor of C(ShutDownBeheviorConfiguration)
        and will be removed.'
      returned: when the API returns it
      type: str
    VmType:
      description:
      - The type of VM. For more information, see L(VM Types, https://docs.outscale.com/en/userguide/VM-Types.html).
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
    resource="vm",
    operation=Operation(
        id="ReadVms",
        method="ReadVms",
        body_params={"filters": "Filters"},
        payload_field="Vms",
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
