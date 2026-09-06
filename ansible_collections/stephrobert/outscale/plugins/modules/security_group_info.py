#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadSecurityGroups
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: security_group_info
short_description: Gather information about Outscale security groups
version_added: 0.1.0
description:
- List Outscale security groups, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(Descriptions), C(InboundRuleAccountIds),
      C(InboundRuleFromPortRanges), C(InboundRuleIpRanges), C(InboundRuleProtocols), C(InboundRuleSecurityGroupIds),
      C(InboundRuleSecurityGroupNames), C(InboundRuleToPortRanges), C(NetIds), C(OutboundRuleAccountIds),
      C(OutboundRuleFromPortRanges), C(OutboundRuleIpRanges), C(OutboundRuleProtocols), C(OutboundRuleSecurityGroupIds),
      C(OutboundRuleSecurityGroupNames), C(OutboundRuleToPortRanges), C(SecurityGroupIds),
      C(SecurityGroupNames), C(TagKeys), C(TagValues), C(Tags).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List security groups
  stephrobert.outscale.security_group_info:
    region: eu-west-2
  register: result
- name: Read security groups by ID
  stephrobert.outscale.security_group_info:
    region: eu-west-2
    filters:
      SecurityGroupIds:
      - example-id
  register: result
- name: List security groups matching a tag
  stephrobert.outscale.security_group_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
security_groups:
  description: The security groups.
  returned: always
  type: list
  elements: dict
  contains:
    AccountId:
      description:
      - The OUTSCALE account ID that has been granted permission.
      returned: when the API returns it
      type: str
    Description:
      description:
      - The description of the security group.
      returned: when the API returns it
      type: str
    InboundRules:
      description:
      - The inbound rules associated with the security group.
      returned: when the API returns it
      type: list
      elements: dict
    NetId:
      description:
      - The ID of the Net for the security group.
      returned: when the API returns it
      type: str
    OutboundRules:
      description:
      - The outbound rules associated with the security group.
      returned: when the API returns it
      type: list
      elements: dict
    SecurityGroupId:
      description:
      - The ID of the security group.
      returned: when the API returns it
      type: str
    SecurityGroupName:
      description:
      - The name of the security group.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the security group.
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
    resource="security_group",
    operation=Operation(
        id="ReadSecurityGroups",
        method="ReadSecurityGroups",
        body_params={"filters": "Filters"},
        payload_field="SecurityGroups",
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
