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
short_description: Gather information about Outscale vms
version_added: 0.1.0
description:
- List Outscale vms, optionally filtered. This module never changes anything.
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
- name: List vms
  stephrobert.outscale.vm_info:
    region: eu-west-2
  register: result
- name: List vms matching a filter
  stephrobert.outscale.vm_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
vms:
  description: The vms.
  returned: always
  type: list
  elements: dict
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
