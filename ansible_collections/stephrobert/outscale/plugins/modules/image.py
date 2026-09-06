#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateImage
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: image
short_description: Manage the settings of an Outscale image
version_added: 0.1.0
description:
- Set the settings of an existing Outscale image (I(description), I(permissions_to_launch),
  I(product_codes)), and only what differs from what the API returns. Terraform provisions
  the image, this module operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  description:
    description: A new description for the image.
    type: str
  image_id:
    description: The ID of the OMI you want to modify.
    type: str
    required: true
  permissions_to_launch:
    description: 'Information about the permissions for the resource.<br />

      Specify either the `Additions` or the `Removals` parameter. Accepted keys: C(Additions),
      C(Removals).'
    type: dict
  product_codes:
    description: The product codes associated with the OMI. Any previously set value is deleted.
      Make sure to specify all product codes you want to associate with the OMI.
    type: list
    elements: str
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the image by I(image_id), compares every option you give with what the
  API returns, and sends C(UpdateImage) only when something differs: a second run reports
  C(changed=false). In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a image
  stephrobert.outscale.image:
    region: eu-west-2
    image_id: example-id
    description: example-id
"""

RETURN = r"""
image:
  description: The image, read after the update.
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
    "image_id": {"type": "str", "required": True},
    "permissions_to_launch": {"type": "dict"},
    "product_codes": {"type": "list", "elements": "str"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="image",
    selector="image_id",
    operation=Operation(
        id="UpdateImage",
        method="UpdateImage",
        body_params={
            "description": "Description",
            "image_id": "ImageId",
            "permissions_to_launch": "PermissionsToLaunch",
            "product_codes": "ProductCodes",
        },
        payload_field="Image",
    ),
    read_operation=Operation(
        id="ReadImages",
        method="ReadImages",
        body_params={"filters": "Filters"},
        payload_field="Images",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="ImageIds",
    read_id_field="ImageId",
    compare={
        "description": "Description",
        "permissions_to_launch": "PermissionsToLaunch",
        "product_codes": "ProductCodes",
    },
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
