#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadVmTypes
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: vm_type_info
short_description: Gather information about Outscale VM types
version_added: 0.1.0
description:
- List Outscale VM types, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(BsuOptimized), C(EphemeralsTypes),
      C(Eths), C(Gpus), C(MemorySizes), C(VcoreCounts), C(VmTypeNames), C(VolumeCounts), C(VolumeSizes).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List VM types
  stephrobert.outscale.vm_type_info:
    region: eu-west-2
  register: result
"""

RETURN = r"""
vm_types:
  description: The VM types.
  returned: always
  type: list
  elements: dict
  contains:
    BsuOptimized:
      description:
      - This parameter is not available. It is present in our API for the sake of historical
        compatibility with AWS.
      returned: when the API returns it
      type: bool
    EphemeralsType:
      description:
      - The type of ephemeral storage disk.
      returned: when the API returns it
      type: str
    Eth:
      description:
      - The number of Ethernet interface available.
      returned: when the API returns it
      type: int
    Gpu:
      description:
      - The number of GPU available.
      returned: when the API returns it
      type: int
    MaxPrivateIps:
      description:
      - The maximum number of private IPs per network interface card (NIC).
      returned: when the API returns it
      type: int
    MemorySize:
      description:
      - The amount of memory, in gibibytes.
      returned: when the API returns it
      type: float
    VcoreCount:
      description:
      - The number of vCores.
      returned: when the API returns it
      type: int
    VmTypeName:
      description:
      - The name of the VM type.
      returned: when the API returns it
      type: str
    VolumeCount:
      description:
      - The maximum number of ephemeral storage disks.
      returned: when the API returns it
      type: int
    VolumeSize:
      description:
      - The size of one ephemeral storage disk, in gibibytes (GiB).
      returned: when the API returns it
      type: int
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
    resource="vm_type",
    operation=Operation(
        id="ReadVmTypes",
        method="ReadVmTypes",
        body_params={"filters": "Filters"},
        payload_field="VmTypes",
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
