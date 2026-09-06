#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateNet
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: net
short_description: Manage the settings of an Outscale net
version_added: 0.1.0
description:
- Set the settings of an existing Outscale net (I(dhcp_options_set_id)), and only what differs
  from what the API returns. Terraform provisions the net, this module operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  dhcp_options_set_id:
    description: The ID of the DHCP options set (or `default` if you want to associate the
      default one).
    type: str
    required: true
  net_id:
    description: The ID of the Net.
    type: str
    required: true
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the net by I(net_id), compares every option you give with what the API
  returns, and sends C(UpdateNet) only when something differs: a second run reports C(changed=false).
  In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a net
  stephrobert.outscale.net:
    region: eu-west-2
    dhcp_options_set_id: example-id
    net_id: example-id
"""

RETURN = r"""
net:
  description: The net, read after the update.
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
    "dhcp_options_set_id": {"type": "str", "required": True},
    "net_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="net",
    selector="net_id",
    operation=Operation(
        id="UpdateNet",
        method="UpdateNet",
        body_params={"dhcp_options_set_id": "DhcpOptionsSetId", "net_id": "NetId"},
        payload_field="Net",
    ),
    read_operation=Operation(
        id="ReadNets",
        method="ReadNets",
        body_params={"filters": "Filters"},
        payload_field="Nets",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="NetIds",
    read_id_field="NetId",
    compare={"dhcp_options_set_id": "DhcpOptionsSetId"},
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
