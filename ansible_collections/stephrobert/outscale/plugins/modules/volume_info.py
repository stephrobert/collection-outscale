#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadVolumes
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: volume_info
short_description: Gather information about Outscale volumes
version_added: 0.1.0
description:
- List Outscale volumes, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(ClientTokens), C(CreationDates), C(LinkVolumeDeleteOnVmDeletion),
      C(LinkVolumeDeviceNames), C(LinkVolumeLinkDates), C(LinkVolumeLinkStates), C(LinkVolumeVmIds),
      C(SnapshotIds), C(SubregionNames), C(TagKeys), C(TagValues), C(Tags), C(VolumeIds),
      C(VolumeSizes), C(VolumeStates), C(VolumeTypes).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List volumes
  stephrobert.outscale.volume_info:
    region: eu-west-2
  register: result
- name: Read volumes by ID
  stephrobert.outscale.volume_info:
    region: eu-west-2
    filters:
      VolumeIds:
      - example-id
  register: result
- name: List volumes matching a tag
  stephrobert.outscale.volume_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
volumes:
  description: The volumes.
  returned: always
  type: list
  elements: dict
  contains:
    ClientToken:
      description:
      - The idempotency token provided when creating the volume.
      returned: when the API returns it
      type: str
    CreationDate:
      description:
      - The date and time (UTC) at which the volume was created.
      returned: when the API returns it
      type: str
    Iops:
      description:
      - 'The number of I/O operations per second (IOPS): - For C(io1) volumes, the number
        of provisioned IOPS - For C(gp2) volumes, the baseline performance of the volume'
      returned: when the API returns it
      type: int
    LinkedVolumes:
      description:
      - Information about your volume attachment.
      returned: when the API returns it
      type: list
      elements: dict
    Size:
      description:
      - The size of the volume, in gibibytes (GiB).
      returned: when the API returns it
      type: int
    SnapshotId:
      description:
      - The snapshot from which the volume was created.
      returned: when the API returns it
      type: str
    State:
      description:
      - The state of the volume (C(creating) | C(available) | C(in-use) | C(deleting) | C(error)).
      returned: when the API returns it
      type: str
    SubregionName:
      description:
      - The Subregion in which the volume was created.
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the volume.
      returned: when the API returns it
      type: list
      elements: dict
    TaskId:
      description:
      - The ID of the volume update task in progress. Otherwise, it is not returned.
      returned: when the API returns it
      type: str
    VolumeId:
      description:
      - The ID of the volume.
      returned: when the API returns it
      type: str
    VolumeType:
      description:
      - The type of the volume (C(standard) | C(gp2) | C(io1)).
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
    resource="volume",
    operation=Operation(
        id="ReadVolumes",
        method="ReadVolumes",
        body_params={"filters": "Filters"},
        payload_field="Volumes",
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
