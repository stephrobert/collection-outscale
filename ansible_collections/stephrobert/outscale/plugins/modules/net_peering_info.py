#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadNetPeerings
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: net_peering_info
short_description: Gather information about Outscale net peerings
version_added: 0.1.0
description:
- List Outscale net peerings, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(AccepterNetAccountIds), C(AccepterNetIpRanges),
      C(AccepterNetNetIds), C(ExpirationDates), C(NetPeeringIds), C(SourceNetAccountIds),
      C(SourceNetIpRanges), C(SourceNetNetIds), C(StateMessages), C(StateNames), C(TagKeys),
      C(TagValues), C(Tags).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List net peerings
  stephrobert.outscale.net_peering_info:
    region: eu-west-2
  register: result
- name: Read net peerings by ID
  stephrobert.outscale.net_peering_info:
    region: eu-west-2
    filters:
      NetPeeringIds:
      - example-id
  register: result
- name: List net peerings matching a tag
  stephrobert.outscale.net_peering_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
net_peerings:
  description: The net peerings.
  returned: always
  type: list
  elements: dict
  contains:
    AccepterNet:
      description:
      - Information about the accepter Net.
      returned: when the API returns it
      type: dict
    ExpirationDate:
      description:
      - The date and time (UTC) at which the Net peerings expire.
      returned: when the API returns it
      type: str
    NetPeeringId:
      description:
      - The ID of the Net peering.
      returned: when the API returns it
      type: str
    SourceNet:
      description:
      - Information about the source Net.
      returned: when the API returns it
      type: dict
    State:
      description:
      - Information about the state of the Net peering.
      returned: when the API returns it
      type: dict
    Tags:
      description:
      - One or more tags associated with the Net peering.
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
    resource="net_peering",
    operation=Operation(
        id="ReadNetPeerings",
        method="ReadNetPeerings",
        body_params={"filters": "Filters"},
        payload_field="NetPeerings",
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
