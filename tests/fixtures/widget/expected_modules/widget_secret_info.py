#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Contrat de laboratoire (@lab)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : tests/fixtures/widget/input/outscale.v1.yml
# Opérations : ReadWidgetSecret
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: widget_secret_info
short_description: Read the Outscale widget secret
version_added: 9.9.9
description:
- Read the Outscale widget secret. This module never changes anything.
author:
- Contrat de laboratoire (@lab)
options:
  widget_id:
    description: The ID of the widget.
    type: str
    required: true
extends_documentation_fragment:
- lab.widget.outscale
notes:
- 'The returned value is a secret: do not log the task output.'
"""

EXAMPLES = r"""
- name: Read the widget secret
  lab.widget.widget_secret_info:
    region: eu-west-2
    widget_id: example-id
  register: result
"""

RETURN = r"""
widget_secret:
  description: The widget secret, as the API answers it, without the response context.
  returned: always
  type: dict
  contains:
    Secret:
      description:
      - Not documented by the Outscale API contract.
      returned: when the API returns it
      type: str
    WidgetId:
      description:
      - Not documented by the Outscale API contract.
      returned: when the API returns it
      type: str
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
    "widget_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = InfoModule(
    resource="widget_secret",
    operation=Operation(
        id="ReadWidgetSecret",
        method="ReadWidgetSecret",
        body_params={"widget_id": "WidgetId"},
    ),
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_info_module(module, MODULE)


if __name__ == "__main__":
    main()
