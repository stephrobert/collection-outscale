#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateVolume
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: volume
short_description: Manage the settings of an Outscale volume
version_added: 0.1.0
description:
- Set the settings of an existing Outscale volume (I(iops), I(size), I(volume_type)), and
  only what differs from what the API returns. Terraform provisions the volume, this module
  operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  iops:
    description: The new number of I/O operations per second (IOPS). This parameter can be
      specified only if you update an C(io1) volume or if you change the type of the volume
      for an C(io1).
    type: int
  size:
    description: The new size of the volume, in gibibytes (GiB). This value must be equal
      to or greater than the current size of the volume. This modification is not instantaneous.
    type: int
  volume_id:
    description: The ID of the volume you want to update.
    type: str
    required: true
  volume_type:
    description: The new type of the volume (C(standard) | C(io1) | C(gp2)). If you update
      to an C(io1) volume, you must also specify the C(Iops) parameter.
    type: str
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the volume by I(volume_id), compares every option you give with what the
  API returns, and sends C(UpdateVolume) only when something differs: a second run reports
  C(changed=false). In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a volume
  stephrobert.outscale.volume:
    region: eu-west-2
    volume_id: example-id
    volume_type: gp2
- name: Preview the change on a volume without writing
  stephrobert.outscale.volume:
    region: eu-west-2
    volume_id: example-id
    volume_type: gp2
  check_mode: true
  diff: true
"""

RETURN = r"""
volume:
  description: The volume, read after the update.
  returned: always
  type: dict
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
    "iops": {"type": "int"},
    "size": {"type": "int"},
    "volume_id": {"type": "str", "required": True},
    "volume_type": {"type": "str"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="volume",
    selector="volume_id",
    operation=Operation(
        id="UpdateVolume",
        method="UpdateVolume",
        body_params={
            "iops": "Iops",
            "size": "Size",
            "volume_id": "VolumeId",
            "volume_type": "VolumeType",
        },
        payload_field="Volume",
    ),
    read_operation=Operation(
        id="ReadVolumes",
        method="ReadVolumes",
        body_params={"filters": "Filters"},
        payload_field="Volumes",
        is_list=True,
        page_token="NextPageToken",
    ),
    read_filter="VolumeIds",
    read_id_field="VolumeId",
    compare={"iops": "Iops", "size": "Size", "volume_type": "VolumeType"},
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
