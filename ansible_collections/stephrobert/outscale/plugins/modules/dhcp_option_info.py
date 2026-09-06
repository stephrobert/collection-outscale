#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadDhcpOptions
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: dhcp_option_info
short_description: Gather information about Outscale DHCP options
version_added: 0.1.0
description:
- List Outscale DHCP options, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(Default), C(DhcpOptionsSetIds), C(DomainNameServers),
      C(DomainNames), C(LogServers), C(NtpServers), C(TagKeys), C(TagValues), C(Tags).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers by pages: the module follows the C(NextPageToken) until the last page and
  returns everything the API knows.'
"""

EXAMPLES = r"""
- name: List DHCP options
  stephrobert.outscale.dhcp_option_info:
    region: eu-west-2
  register: result
- name: List DHCP options filtered by DhcpOptionsSetIds
  stephrobert.outscale.dhcp_option_info:
    region: eu-west-2
    filters:
      DhcpOptionsSetIds:
      - example-id
  register: result
- name: List DHCP options matching a tag
  stephrobert.outscale.dhcp_option_info:
    region: eu-west-2
    filters:
      Tags:
      - role=web
  register: result
"""

RETURN = r"""
dhcp_options:
  description: The DHCP options.
  returned: always
  type: list
  elements: dict
  contains:
    Default:
      description:
      - If true, the DHCP options set is a default one. If false, it is not.
      returned: when the API returns it
      type: bool
    DhcpOptionsSetId:
      description:
      - The ID of the DHCP options set.
      returned: when the API returns it
      type: str
    DomainName:
      description:
      - The domain name.
      returned: when the API returns it
      type: str
    DomainNameServers:
      description:
      - One or more IPs for the domain name servers.
      returned: when the API returns it
      type: list
      elements: str
    LogServers:
      description:
      - One or more IPs for the log servers.
      returned: when the API returns it
      type: list
      elements: str
    NtpServers:
      description:
      - One or more IPs for the NTP servers.
      returned: when the API returns it
      type: list
      elements: str
    Tags:
      description:
      - One or more tags associated with the DHCP options set.
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
    resource="dhcp_option",
    operation=Operation(
        id="ReadDhcpOptions",
        method="ReadDhcpOptions",
        body_params={"filters": "Filters"},
        payload_field="DhcpOptionsSets",
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
