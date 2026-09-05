#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Contrat de laboratoire (@lab)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : tests/fixtures/widget/input/outscale.v1.yml
# Opérations : RebootWidgets, StartWidgets, StopWidgets
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: widget_action
short_description: Perform an action on Outscale widgets
version_added: 9.9.9
description:
- 'Trigger one of the following actions on existing widgets: C(reboot), C(start), C(stop).'
author:
- Contrat de laboratoire (@lab)
options:
  action:
    description: The action to trigger on the widgets.
    type: str
    required: true
    choices:
    - reboot
    - start
    - stop
  widget_ids:
    description: Not documented by the Outscale API contract.
    type: list
    required: true
    elements: str
  force_stop:
    description: Forces the widget to stop.
    type: bool
extends_documentation_fragment:
- lab.widget.outscale
- lab.widget.outscale.wait
notes:
- 'Every action answers at once: the API response is returned under RV(result), and the resource
  changes state afterwards.'
- When I(wait) is true, the module reads the widget until its C(State) reaches the expected
  value (C(reboot) leads to C(running), C(start) leads to C(running), C(stop) leads to C(stopped)),
  and reports C(changed=false) without sending anything when every widget already is in that
  state, except for C(reboot), which always acts.
"""

EXAMPLES = r"""
- name: Run reboot on a widget
  lab.widget.widget_action:
    region: eu-west-2
    action: reboot
    widget_ids:
    - example-id
"""

RETURN = r"""
result:
  description: The API response of the action, without the response context.
  returned: when the action was sent
  type: dict
states:
  description: The C(State) of each widget, by identifier, read after the action.
  returned: when an expected state is declared for the action
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.lab.widget.plugins.module_utils.outscale import (  # noqa: E402
    Action,
    ActionModule,
    Operation,
    outscale_argument_spec,
    outscale_waitable_argument_spec,
    run_action_module,
)

#: Options propres au module, traduites depuis le contrat.
MODULE_ARGUMENT_SPEC = {
    "action": {
        "type": "str",
        "required": True,
        "choices": ["reboot", "start", "stop"],
    },
    "widget_ids": {"type": "list", "elements": "str", "required": True},
    "force_stop": {"type": "bool"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(outscale_waitable_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ActionModule(
    resource="widget",
    selector="widget_ids",
    actions=(
        Action(
            name="reboot",
            operation=Operation(
                id="RebootWidgets",
                method="RebootWidgets",
                body_params={"widget_ids": "WidgetIds"},
            ),
            expected_state="running",
            always=True,
        ),
        Action(
            name="start",
            operation=Operation(
                id="StartWidgets",
                method="StartWidgets",
                body_params={"widget_ids": "WidgetIds"},
                payload_field="Widgets",
                is_list=True,
            ),
            expected_state="running",
        ),
        Action(
            name="stop",
            operation=Operation(
                id="StopWidgets",
                method="StopWidgets",
                body_params={"widget_ids": "WidgetIds", "force_stop": "ForceStop"},
                payload_field="Widgets",
                is_list=True,
            ),
            expected_state="stopped",
        ),
    ),
    state_field="State",
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
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_action_module(module, MODULE)


if __name__ == "__main__":
    main()
