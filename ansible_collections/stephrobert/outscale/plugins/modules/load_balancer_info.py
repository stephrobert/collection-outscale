#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This file is generated.
# Do not edit manually.
#
# Contrat    : specs/outscale/outscale.v1.yml
# Opérations : ReadLoadBalancers
# Régénérer  : mise run generate

from __future__ import annotations

DOCUMENTATION = r"""
module: load_balancer_info
short_description: Gather information about Outscale load balancers
version_added: 0.1.0
description:
- List Outscale load balancers, optionally filtered. This module never changes anything.
author:
- Stéphane Robert (@stephrobert)
options:
  filters:
    description: 'One or more filters. Accepted keys: C(LoadBalancerNames), C(States).'
    type: dict
extends_documentation_fragment:
- stephrobert.outscale.outscale
notes:
- 'The API answers in one response, and the contract does not promise it is complete: there
  is no page token on this operation.'
"""

EXAMPLES = r"""
- name: List load balancers
  stephrobert.outscale.load_balancer_info:
    region: eu-west-2
  register: result
"""

RETURN = r"""
load_balancers:
  description: The load balancers.
  returned: always
  type: list
  elements: dict
  contains:
    AccessLog:
      description:
      - Information about access logs.
      returned: when the API returns it
      type: dict
    ApplicationStickyCookiePolicies:
      description:
      - The stickiness policies defined for the load balancer.
      returned: when the API returns it
      type: list
      elements: dict
    BackendIps:
      description:
      - One or more public IPs of backend VMs.
      returned: when the API returns it
      type: list
      elements: str
    BackendVmIds:
      description:
      - One or more IDs of backend VMs for the load balancer.
      returned: when the API returns it
      type: list
      elements: str
    DnsName:
      description:
      - The DNS name of the load balancer.
      returned: when the API returns it
      type: str
    HealthCheck:
      description:
      - Information about the health check configuration.
      returned: when the API returns it
      type: dict
    Listeners:
      description:
      - The listeners for the load balancer.
      returned: when the API returns it
      type: list
      elements: dict
    LoadBalancerName:
      description:
      - The name of the load balancer.
      returned: when the API returns it
      type: str
    LoadBalancerStickyCookiePolicies:
      description:
      - The policies defined for the load balancer.
      returned: when the API returns it
      type: list
      elements: dict
    LoadBalancerType:
      description:
      - The type of load balancer. Valid only for load balancers in a Net. If C(LoadBalancerType)
        is C(internet-facing), the load balancer has a public DNS name that resolves to a
        public IP. If C(LoadBalancerType) is C(internal), the load balancer has a public DNS
        name that resolves to a private IP.
      returned: when the API returns it
      type: str
    NetId:
      description:
      - The ID of the Net for the load balancer.
      returned: when the API returns it
      type: str
    PrivateIp:
      description:
      - The primary private IP of the load balancer.
      returned: when the API returns it
      type: str
    PublicIp:
      description:
      - (internet-facing only) The public IP associated with the load balancer.
      returned: when the API returns it
      type: str
    SecuredCookies:
      description:
      - Whether secure cookies are enabled for the load balancer.
      returned: when the API returns it
      type: bool
    SecurityGroups:
      description:
      - One or more IDs of security groups for the load balancers. Valid only for load balancers
        in a Net.
      returned: when the API returns it
      type: list
      elements: str
    SourceSecurityGroup:
      description:
      - Information about the source security group of the load balancer, which you can use
        as part of your inbound rules for your registered VMs. To only allow traffic from
        load balancers, add a security group rule that specifies this source security group
        as the inbound source.
      returned: when the API returns it
      type: dict
    State:
      description:
      - The state of the load balancer (C(provisioning) | C(starting) | C(reloading) | C(active)
        | C(reconfiguring) | C(deleting) | C(deleted)).
      returned: when the API returns it
      type: str
    Subnets:
      description:
      - The ID of the Subnet in which the load balancer was created.
      returned: when the API returns it
      type: list
      elements: str
    SubregionNames:
      description:
      - The ID of the Subregion in which the load balancer was created.
      returned: when the API returns it
      type: list
      elements: str
    Tags:
      description:
      - One or more tags associated with the load balancer.
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
    resource="load_balancer",
    operation=Operation(
        id="ReadLoadBalancers",
        method="ReadLoadBalancers",
        body_params={"filters": "Filters"},
        payload_field="LoadBalancers",
        is_list=True,
    ),
)


def main() -> None:
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC, required_if=REQUIRED_IF, supports_check_mode=True
    )
    run_info_module(module, MODULE)


if __name__ == "__main__":
    main()
