#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadNics
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: nic_info
short_description: Gather information about Outscale NICs
version_added: 0.1.0
description:
- List Outscale NICs, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(Descriptions), C(IsSourceDestCheck),
      C(LinkNicDeleteOnVmDeletion), C(LinkNicDeviceNumbers), C(LinkNicLinkNicIds), C(LinkNicStates),
      C(LinkNicVmAccountIds), C(LinkNicVmIds), C(LinkPublicIpAccountIds), C(LinkPublicIpLinkPublicIpIds),
      C(LinkPublicIpPublicDnsNames), C(LinkPublicIpPublicIpIds), C(LinkPublicIpPublicIps),
      C(MacAddresses), C(NetIds), C(NicIds), C(PrivateDnsNames), C(PrivateIpsLinkPublicIpAccountIds),
      C(PrivateIpsLinkPublicIpPublicIps), C(PrivateIpsPrimaryIp), C(PrivateIpsPrivateIps),
      C(SecurityGroupIds), C(SecurityGroupNames), C(States), C(SubnetIds), C(SubregionNames),
      C(TagKeys), C(TagValues), C(Tags).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List NICs
  stephrobert.outscale.nic_info:
    region: eu-west-2
  register: result
- name: Read NICs by ID
  stephrobert.outscale.nic_info:
    region: eu-west-2
    filters:
      NicIds:
      - example-id
  register: result
- name: List NICs matching a tag
  stephrobert.outscale.nic_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
nics:
  description: The NICs.
  returned: always
  type: list
  elements: dict
  contains:
    AccountId:
      description:
      - The OUTSCALE account ID of the owner of the NIC.
      returned: when the API returns it
      type: str
    Description:
      description:
      - The description of the NIC.
      returned: when the API returns it
      type: str
    IsSourceDestChecked:
      description:
      - (Net only) If true, the source/destination check is enabled. If false, it is disabled.
      returned: when the API returns it
      type: bool
    LinkNic:
      description:
      - Information about the NIC attachment.
      returned: when the API returns it
      type: dict
    LinkPublicIp:
      description:
      - Information about the public IP association.
      returned: when the API returns it
      type: dict
    MacAddress:
      description:
      - The Media Access Control (MAC) address of the NIC.
      returned: when the API returns it
      type: str
    NetId:
      description:
      - The ID of the Net for the NIC.
      returned: when the API returns it
      type: str
    NicId:
      description:
      - The ID of the NIC.
      returned: when the API returns it
      type: str
    PrivateDnsName:
      description:
      - The name of the private DNS.
      returned: when the API returns it
      type: str
    PrivateIps:
      description:
      - The private IPs of the NIC.
      returned: when the API returns it
      type: list
      elements: dict
    SecurityGroups:
      description:
      - One or more IDs of security groups for the NIC.
      returned: when the API returns it
      type: list
      elements: dict
    State:
      description:
      - The state of the NIC (C(available) | C(attaching) | C(in-use) | C(detaching)).
      returned: when the API returns it
      type: str
    SubnetId:
      description:
      - The ID of the Subnet.
      returned: when the API returns it
      type: str
    SubregionName:
      description:
      - The Subregion in which the NIC is located.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the NIC.
      returned: when the API returns it
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
    resource="nic",
    operation=Operation(
        id="ReadNics",
        method="ReadNics",
        body_params={"filters": "Filters"},
        payload_field="Nics",
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
