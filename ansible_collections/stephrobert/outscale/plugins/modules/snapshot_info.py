#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadSnapshots
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: snapshot_info
short_description: Gather information about Outscale snapshots
version_added: 0.1.0
description:
- List Outscale snapshots, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(AccountAliases), C(AccountIds), C(ClientTokens),
      C(Descriptions), C(FromCreationDate), C(PermissionsToCreateVolumeAccountIds), C(PermissionsToCreateVolumeGlobalPermission),
      C(Progresses), C(SnapshotIds), C(States), C(TagKeys), C(TagValues), C(Tags), C(ToCreationDate),
      C(VolumeIds), C(VolumeSizes).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List snapshots
  stephrobert.outscale.snapshot_info:
    region: eu-west-2
  register: result
- name: Read snapshots by ID
  stephrobert.outscale.snapshot_info:
    region: eu-west-2
    filters:
      SnapshotIds:
      - example-id
  register: result
- name: List snapshots matching a tag
  stephrobert.outscale.snapshot_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
snapshots:
  description: The snapshots.
  returned: always
  type: list
  elements: dict
  contains:
    AccountAlias:
      description:
      - The account alias of the owner of the snapshot.
      returned: when the API returns it
      type: str
    AccountId:
      description:
      - The OUTSCALE account ID of the owner of the snapshot.
      returned: when the API returns it
      type: str
    ClientToken:
      description:
      - The idempotency token provided when creating the snapshot.
      returned: when the API returns it
      type: str
    CreationDate:
      description:
      - The date and time (UTC) at which the snapshot was created.
      returned: when the API returns it
      type: str
    Description:
      description:
      - The description of the snapshot.
      returned: when the API returns it
      type: str
    PermissionsToCreateVolume:
      description:
      - Permissions for the resource.
      returned: when the API returns it
      type: dict
    Progress:
      description:
      - The progress of the snapshot, as a percentage.
      returned: when the API returns it
      type: int
    SnapshotId:
      description:
      - The ID of the snapshot.
      returned: when the API returns it
      type: str
    State:
      description:
      - The state of the snapshot (C(in-queue) | C(pending) | C(completed) | C(error) | C(deleting)).
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the snapshot.
      returned: when the API returns it
      type: list
      elements: dict
    VolumeId:
      description:
      - The ID of the volume used to create the snapshot.
      returned: when the API returns it
      type: str
    VolumeSize:
      description:
      - The size of the volume used to create the snapshot, in gibibytes (GiB).
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
    resource="snapshot",
    operation=Operation(
        id="ReadSnapshots",
        method="ReadSnapshots",
        body_params={"filters": "Filters"},
        payload_field="Snapshots",
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
