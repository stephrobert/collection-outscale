#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Contrat de laboratoire (@lab)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : tests/fixtures/widget/input/outscale.v1.yml
# Opérations : UpdateWidget
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: widget
short_description: Manage the settings of an Outscale widget
version_added: 9.9.9
description:
- Set the settings of an existing Outscale widget (I(widget_type), I(performance)), and only
  what differs from what the API returns. Terraform provisions the widget, this module operates
  it.
author:
- Contrat de laboratoire (@lab)
options:
  widget_id:
    description: Not documented by the Outscale API contract.
    type: str
    required: true
  widget_type:
    description: Not documented by the Outscale API contract.
    type: str
  performance:
    description: Not documented by the Outscale API contract.
    type: str
    choices:
    - medium
    - high
    - highest
extends_documentation_fragment:
- lab.widget.outscale
notes:
- 'The module reads the widget by I(widget_id), compares every option you give with what the
  API returns, and sends C(UpdateWidget) only when something differs: a second run reports
  C(changed=false). In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a widget
  lab.widget.widget:
    region: eu-west-2
    widget_id: example-id
    widget_type: example-id
"""

RETURN = r"""
widget:
  description: The widget, read after the update.
  returned: always
  type: dict
changes:
  description: 'What differed, by option: the value the API returned before, and the value
    you asked for.'
  returned: when something differed
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.lab.widget.plugins.module_utils.outscale import (  # noqa: E402
    ManageModule,
    Operation,
    outscale_argument_spec,
    run_manage_module,
)

#: Options propres au module, traduites depuis le contrat.
MODULE_ARGUMENT_SPEC = {
    "widget_id": {"type": "str", "required": True},
    "widget_type": {"type": "str"},
    "performance": {
        "type": "str",
        "choices": ["medium", "high", "highest"],
    },
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="widget",
    selector="widget_id",
    operation=Operation(
        id="UpdateWidget",
        method="UpdateWidget",
        body_params={
            "widget_id": "WidgetId",
            "widget_type": "WidgetType",
            "performance": "Performance",
        },
        payload_field="Widget",
    ),
    read_operation=Operation(
        id="ReadWidgets",
        method="ReadWidgets",
        body_params={"filters": "Filters"},
        payload_field="Widgets",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="WidgetIds",
    read_id_field="WidgetId",
    compare={"widget_type": "WidgetType", "performance": "Performance"},
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
