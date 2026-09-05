#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadImages
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: image_info
short_description: Gather information about Outscale images
version_added: 0.1.0
description:
- List Outscale images, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(AccountAliases), C(AccountIds), C(Architectures),
      C(BlockDeviceMappingDeleteOnVmDeletion), C(BlockDeviceMappingDeviceNames), C(BlockDeviceMappingSnapshotIds),
      C(BlockDeviceMappingVolumeSizes), C(BlockDeviceMappingVolumeTypes), C(BootModes), C(Descriptions),
      C(FileLocations), C(Hypervisors), C(ImageIds), C(ImageNames), C(PermissionsToLaunchAccountIds),
      C(PermissionsToLaunchGlobalPermission), C(ProductCodeNames), C(ProductCodes), C(RootDeviceNames),
      C(RootDeviceTypes), C(SecureBoot), C(States), C(TagKeys), C(TagValues), C(Tags), C(TpmMandatory),
      C(VirtualizationTypes).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List images
  stephrobert.outscale.image_info:
    region: eu-west-2
  register: result
- name: List images matching a filter
  stephrobert.outscale.image_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
images:
  description: The images.
  returned: always
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
    resource="image",
    operation=Operation(
        id="ReadImages",
        method="ReadImages",
        body_params={"filters": "Filters"},
        payload_field="Images",
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
