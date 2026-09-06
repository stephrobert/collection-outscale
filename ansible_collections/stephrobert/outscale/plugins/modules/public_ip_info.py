#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadPublicIps
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: public_ip_info
short_description: Gather information about Outscale public IPs
version_added: 0.1.0
description:
- List Outscale public IPs, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(LinkPublicIpIds), C(NicAccountIds),
      C(NicIds), C(Placements), C(PrivateIps), C(PublicIpIds), C(PublicIps), C(TagKeys), C(TagValues),
      C(Tags), C(VmIds).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List public IPs
  stephrobert.outscale.public_ip_info:
    region: eu-west-2
  register: result
- name: Read public IPs by ID
  stephrobert.outscale.public_ip_info:
    region: eu-west-2
    filters:
      PublicIpIds:
      - example-id
  register: result
- name: List public IPs matching a tag
  stephrobert.outscale.public_ip_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
public_ips:
  description: The public IPs.
  returned: always
  type: list
  elements: dict
  contains:
    LinkPublicIpId:
      description:
      - (Required in a Net) The ID representing the association of the public IP with the
        VM or the NIC.
      returned: when the API returns it
      type: str
    NatServiceId:
      description:
      - The ID of the NAT service associated with the public IP (if any).
      returned: when the API returns it
      type: str
    NetAccessPointIds:
      description:
      - The IDs of the Net access points associated with the public IP (if any).
      returned: when the API returns it
      type: list
      elements: str
    NicAccountId:
      description:
      - The OUTSCALE account ID of the owner of the NIC.
      returned: when the API returns it
      type: str
    NicId:
      description:
      - The ID of the NIC the public IP is associated with (if any).
      returned: when the API returns it
      type: str
    PrivateIp:
      description:
      - The private IP associated with the NIC or load balancer.
      returned: when the API returns it
      type: str
    PublicIp:
      description:
      - The public IP.
      returned: when the API returns it
      type: str
    PublicIpId:
      description:
      - The allocation ID of the public IP.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the public IP.
      returned: when the API returns it
      type: list
      elements: dict
    VmId:
      description:
      - The ID of the VM the public IP is associated with (if any).
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
    resource="public_ip",
    operation=Operation(
        id="ReadPublicIps",
        method="ReadPublicIps",
        body_params={"filters": "Filters"},
        payload_field="PublicIps",
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
