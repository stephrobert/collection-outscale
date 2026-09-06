#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateSubnet
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: subnet
short_description: Manage the settings of an Outscale subnet
version_added: 0.1.0
description:
- Set the settings of an existing Outscale subnet (I(map_public_ip_on_launch)), and only what
  differs from what the API returns. Terraform provisions the subnet, this module operates
  it.
author:
- Stéphane Robert (@stephrobert)
options:
  map_public_ip_on_launch:
    description: If true, a public IP is assigned to the network interface cards (NICs) created
      in the specified Subnet.
    type: bool
    required: true
  subnet_id:
    description: The ID of the Subnet.
    type: str
    required: true
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the subnet by I(subnet_id), compares every option you give with what the
  API returns, and sends C(UpdateSubnet) only when something differs: a second run reports
  C(changed=false). In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a subnet
  stephrobert.outscale.subnet:
    region: eu-west-2
    map_public_ip_on_launch: true
    subnet_id: example-id
- name: Preview the change on a subnet without writing
  stephrobert.outscale.subnet:
    region: eu-west-2
    map_public_ip_on_launch: true
    subnet_id: example-id
  check_mode: true
  diff: true
"""

RETURN = r"""
subnet:
  description: The subnet, read after the update.
  returned: always
  type: dict
  contains:
    AvailableIpsCount:
      description:
      - The number of available IPs in the Subnets.
      returned: when the API returns it
      type: int
    IpRange:
      description:
      - The IP range in the Subnet, in CIDR notation (for example, C(10.0.0.0/16)).
      returned: when the API returns it
      type: str
    MapPublicIpOnLaunch:
      description:
      - If true, a public IP is assigned to the network interface cards (NICs) created in
        the specified Subnet. By default, false.
      returned: when the API returns it
      type: bool
    NetId:
      description:
      - The ID of the Net in which the Subnet is.
      returned: when the API returns it
      type: str
    State:
      description:
      - The state of the Subnet (C(pending) | C(available) | C(deleted)).
      returned: when the API returns it
      type: str
    SubnetId:
      description:
      - The ID of the Subnet.
      returned: when the API returns it
      type: str
    SubregionName:
      description:
      - The name of the Subregion in which the Subnet is located.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the Subnet.
      returned: when the API returns it
      type: list
      elements: dict
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
    "map_public_ip_on_launch": {"type": "bool", "required": True},
    "subnet_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="subnet",
    selector="subnet_id",
    operation=Operation(
        id="UpdateSubnet",
        method="UpdateSubnet",
        body_params={"map_public_ip_on_launch": "MapPublicIpOnLaunch", "subnet_id": "SubnetId"},
        payload_field="Subnet",
    ),
    read_operation=Operation(
        id="ReadSubnets",
        method="ReadSubnets",
        body_params={"filters": "Filters"},
        payload_field="Subnets",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="SubnetIds",
    read_id_field="SubnetId",
    compare={"map_public_ip_on_launch": "MapPublicIpOnLaunch"},
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
