#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadAdminPassword
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm_admin_password_info
short_description: Read the Outscale admin password
version_added: 0.1.0
description:
- Read the Outscale admin password. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  vm_id:
    description: The ID of the VM.
    type: str
    required: true
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The returned value is a secret: do not log the task output.'
"""

EXAMPLES = r"""
- name: Read the admin password
  stephrobert.outscale.vm_admin_password_info:
    region: eu-west-2
    vm_id: example-id
  register: result
"""

RETURN = r"""
admin_password:
  description: The admin password, as the API answers it, without the response context.
  returned: always
  type: dict
  contains:
    AdminPassword:
      description:
      - The password of the VM. After the first boot, returns an empty string.
      returned: when the API returns it
      type: str
    VmId:
      description:
      - The ID of the VM.
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
    "vm_id": {"type": "str", "required": True},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = InfoModule(
    resource="admin_password",
    operation=Operation(
        id="ReadAdminPassword",
        method="ReadAdminPassword",
        body_params={"vm_id": "VmId"},
    ),
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_info_module(module, MODULE)


if __name__ == "__main__":
    main()
