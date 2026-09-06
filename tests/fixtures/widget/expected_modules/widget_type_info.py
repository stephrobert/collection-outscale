#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Contrat de laboratoire (@lab)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : tests/fixtures/widget/input/outscale.v1.yml
# Opérations : ReadWidgetTypes
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: widget_type_info
short_description: Gather information about Outscale widget types
version_added: 9.9.9
description:
- List Outscale widget types, optionally filtered. This module never changes anything.
author:
- Contrat de laboratoire (@lab)
options:
  filters:
    description: 'Not documented by the Outscale API contract. Accepted keys: C(WidgetTypeNames).'
    type: dict
extends_documentation_fragment:
- lab.widget.outscale
notes:
- 'The API answers in one response, and the contract does not promise it is complete: there
  is no page token on this operation.'
"""

EXAMPLES = r"""
- name: List widget types
  lab.widget.widget_type_info:
    region: eu-west-2
  register: result
"""

RETURN = r"""
widget_types:
  description: The widget types.
  returned: always
  type: list
  elements: dict
  contains:
    WidgetTypeName:
      description:
      - Not documented by the Outscale API contract.
      returned: when the API returns it
      type: str
    VcoreCount:
      description:
      - Not documented by the Outscale API contract.
      returned: when the API returns it
      type: int
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.lab.widget.plugins.module_utils.outscale import (  # noqa: E402
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
    resource="widget_type",
    operation=Operation(
        id="ReadWidgetTypes",
        method="ReadWidgetTypes",
        body_params={"filters": "Filters"},
        payload_field="WidgetTypes",
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
