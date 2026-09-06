#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadRegions
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: region_info
short_description: Gather information about Outscale regions
version_added: 0.1.0
description:
- List Outscale regions, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options: {}
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers in one response, and the contract does not promise it is complete: there
  is no page token on this operation.'
"""

EXAMPLES = r"""
- name: List regions
  stephrobert.outscale.region_info:
    region: eu-west-2
  register: result
"""

RETURN = r"""
regions:
  description: The regions.
  returned: always
  type: list
  elements: dict
  contains:
    Endpoint:
      description:
      - The hostname of the gateway to access the Region.
      returned: when the API returns it
      type: str
    RegionName:
      description:
      - The administrative name of the Region.
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
MODULE_ARGUMENT_SPEC = {}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = InfoModule(
    resource="region",
    operation=Operation(
        id="ReadRegions",
        method="ReadRegions",
        body_params={},
        payload_field="Regions",
        is_list=True,
    ),
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_info_module(module, MODULE)


if __name__ == "__main__":
    main()
