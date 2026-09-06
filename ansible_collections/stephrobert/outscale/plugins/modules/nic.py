#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateNic
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: nic
short_description: Manage the settings of an Outscale nic
version_added: 0.1.0
description:
- Set the settings of an existing Outscale nic (I(description), I(link_nic)), and only what
  differs from what the API returns. Terraform provisions the nic, this module operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  description:
    description: A new description for the NIC.
    type: str
  link_nic:
    description: 'Information about the NIC attachment. If you are modifying the `DeleteOnVmDeletion`
      attribute, you must specify the ID of the NIC attachment. Accepted keys: C(DeleteOnVmDeletion),
      C(LinkNicId).'
    type: dict
  nic_id:
    description: The ID of the NIC you want to modify.
    type: str
    required: true
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the nic by I(nic_id), compares every option you give with what the API
  returns, and sends C(UpdateNic) only when something differs: a second run reports C(changed=false).
  In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a nic
  stephrobert.outscale.nic:
    region: eu-west-2
    nic_id: example-id
    description: example-id
"""

RETURN = r"""
nic:
  description: The nic, read after the update.
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
    "description": {"type": "str"},
    "link_nic": {"type": "dict"},
    "nic_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="nic",
    selector="nic_id",
    operation=Operation(
        id="UpdateNic",
        method="UpdateNic",
        body_params={"description": "Description", "link_nic": "LinkNic", "nic_id": "NicId"},
        payload_field="Nic",
    ),
    read_operation=Operation(
        id="ReadNics",
        method="ReadNics",
        body_params={"filters": "Filters"},
        payload_field="Nics",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="NicIds",
    read_id_field="NicId",
    compare={"description": "Description", "link_nic": "LinkNic"},
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
