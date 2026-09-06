#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadInternetServices
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: internet_service_info
short_description: Gather information about Outscale internet services
version_added: 0.1.0
description:
- List Outscale internet services, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(InternetServiceIds), C(LinkNetIds),
      C(LinkStates), C(TagKeys), C(TagValues), C(Tags).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List internet services
  stephrobert.outscale.internet_service_info:
    region: eu-west-2
  register: result
- name: Read internet services by ID
  stephrobert.outscale.internet_service_info:
    region: eu-west-2
    filters:
      InternetServiceIds:
      - example-id
  register: result
- name: List internet services matching a tag
  stephrobert.outscale.internet_service_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
internet_services:
  description: The internet services.
  returned: always
  type: list
  elements: dict
  contains:
    InternetServiceId:
      description:
      - The ID of the internet service.
      returned: when the API returns it
      type: str
    NetId:
      description:
      - The ID of the Net attached to the internet service.
      returned: when the API returns it
      type: str
    State:
      description:
      - The state of the attachment of the internet service to the Net (always C(available)).
      returned: when the API returns it
      type: str
    Tags:
      description:
      - One or more tags associated with the internet service.
      returned: when the API returns it
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
    resource="internet_service",
    operation=Operation(
        id="ReadInternetServices",
        method="ReadInternetServices",
        body_params={"filters": "Filters"},
        payload_field="InternetServices",
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
