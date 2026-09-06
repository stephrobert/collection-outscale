#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : UpdateLoadBalancer
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: load_balancer
short_description: Manage the settings of an Outscale load balancer
version_added: 0.1.0
description:
- Set the settings of an existing Outscale load balancer (I(access_log), I(health_check),
  I(public_ip), I(secured_cookies), I(security_groups)), and only what differs from what the
  API returns. Terraform provisions the load balancer, this module operates it.
author:
- Stéphane Robert (@stephrobert)
options:
  access_log:
    description: 'Information about access logs. Accepted keys: C(IsEnabled), C(OsuBucketName),
      C(OsuBucketPrefix), C(PublicationInterval).'
    type: dict
  health_check:
    description: 'Information about the health check configuration. Accepted keys: C(CheckInterval),
      C(HealthyThreshold), C(Path), C(Port), C(Protocol), C(Timeout), C(UnhealthyThreshold).'
    type: dict
  load_balancer_name:
    description: The name of the load balancer.
    type: str
    required: true
  public_ip:
    description: (internet-facing only) The public IP you want to associate with the load
      balancer. The former public IP of the load balancer is then disassociated. If you specify
      an empty string and the former public IP belonged to you, it is disassociated and replaced
      by a public IP owned by 3DS OUTSCALE.
    type: str
  secured_cookies:
    description: If true, secure cookies are enabled for the load balancer.
    type: bool
  security_groups:
    description: (Net only) One or more IDs of security groups you want to assign to the load
      balancer. You need to specify the already assigned security groups that you want to
      keep along with the new ones you are assigning. If the list is empty, the default security
      group of the Net is assigned to the load balancer.
    type: list
    elements: str
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The module reads the load balancer by I(load_balancer_name), compares every option you
  give with what the API returns, and sends C(UpdateLoadBalancer) only when something differs:
  a second run reports C(changed=false). In check mode nothing is sent.'
- 'Only the settings the API reads back are exposed: what it cannot read back could not be
  compared, and the module would report a change on every run.'
"""

EXAMPLES = r"""
- name: Set the settings of a load balancer
  stephrobert.outscale.load_balancer:
    region: eu-west-2
    load_balancer_name: example-id
    public_ip: example-id
"""

RETURN = r"""
load_balancer:
  description: The load balancer, read after the update.
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
    "access_log": {"type": "dict"},
    "health_check": {"type": "dict"},
    "load_balancer_name": {"type": "str", "required": True},
    "public_ip": {"type": "str"},
    "secured_cookies": {"type": "bool"},
    "security_groups": {"type": "list", "elements": "str"},
}

#: Ce que le contrat exige pour une action et pas pour une autre.
REQUIRED_IF = []

#: Les paramètres communs viennent du runtime : un module ne les redéclare pas.
ARGUMENT_SPEC: dict = {}
ARGUMENT_SPEC.update(outscale_argument_spec())
ARGUMENT_SPEC.update(MODULE_ARGUMENT_SPEC)

#: Ce que le module exécute, et les décisions que le générateur a prises.
MODULE = ManageModule(
    resource="load_balancer",
    selector="load_balancer_name",
    operation=Operation(
        id="UpdateLoadBalancer",
        method="UpdateLoadBalancer",
        body_params={
            "access_log": "AccessLog",
            "health_check": "HealthCheck",
            "load_balancer_name": "LoadBalancerName",
            "public_ip": "PublicIp",
            "secured_cookies": "SecuredCookies",
            "security_groups": "SecurityGroups",
        },
        payload_field="LoadBalancer",
    ),
    read_operation=Operation(
        id="ReadLoadBalancers",
        method="ReadLoadBalancers",
        body_params={"filters": "Filters"},
        payload_field="LoadBalancers",
        is_list=True,
    ),
    read_filter="LoadBalancerNames",
    read_id_field="LoadBalancerName",
    compare={
        "access_log": "AccessLog",
        "health_check": "HealthCheck",
        "public_ip": "PublicIp",
        "secured_cookies": "SecuredCookies",
        "security_groups": "SecurityGroups",
    },
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_manage_module(module, MODULE)


if __name__ == "__main__":
    main()
