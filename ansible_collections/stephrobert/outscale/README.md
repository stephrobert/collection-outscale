# stephrobert.outscale

**Day-2** Ansible modules for the Outscale API, produced by the generator of
the repository that hosts this collection:
<https://github.com/stephrobert/collection-outscale>.

> Terraform provisions resources. Ansible operates existing ones.

Information modules read; action modules change the state of an existing
resource and read it back until it reaches the expected state. No module
creates, deletes or links resources.

## Installation

```bash
ansible-galaxy collection install stephrobert.outscale
pip install "osc-sdk-python>=0.42"
```

The official Python SDK `osc-sdk-python` is the only runtime dependency: it
signs the requests (AWS Signature v4) and embeds the same OpenAPI contract
these modules were generated from, and it refuses any action or parameter its
copy does not know.

Requires ansible-core 2.17 or later; the CI matrix runs `ansible-test sanity`
on every minor version from 2.17 to the one the development lock carries.

## Authentication

Every module accepts `access_key`, `secret_key`, `region` and `profile`, and
none of them is required: the SDK reads `OSC_ACCESS_KEY`, `OSC_SECRET_KEY`,
`OSC_REGION`, `OSC_PROFILE` and `~/.osc/config.json` on its own. `api_url`
(or `OSC_ENDPOINT_API`, the name `octl`, the Terraform provider and the feint
emulator use) replaces the host built from the region, `/api/v1` included.

```yaml
- name: Stop a machine and wait until it is stopped
  stephrobert.outscale.vm_action:
    region: eu-west-2
    action: stop
    vm_ids: [i-12345678]

- name: The machines of a role
  stephrobert.outscale.vm_info:
    filters:
      Tags: ["role=web"]
  register: web
```

## Reads and pages

An information module carries one read and its `filters`, whose accepted keys
are those of the contract. When the API answers by pages (`NextPageToken`),
the module follows them to the last one and returns everything the API
knows; when it answers in one response, the documentation of the module says
the contract does not promise it is complete.

## Actions and states

The Outscale API answers an action at once, and the resource changes state
afterwards. When an expected state is declared for an action (`stop` leads
to `stopped`, `accept` leads to `active`), the module reads the resource
until it gets there when `wait` is true (the default), reports
`changed=false` without sending anything when every targeted resource
already is in that state, and fails saying `changed=true` if the state is
not reached within `wait_timeout`. `reboot` always acts.

## Dynamic inventory

```yaml
# production.outscale.yml
plugin: stephrobert.outscale.vm
filters:
  VmStateNames: [running]
group_by: [region, subregion, state, tags]
```

`stephrobert.outscale.vm` discovers the machines region by region through
`ReadVms`, page after page, names them by their `Name` tag, gives each an
`ansible_host` by `address_priority`, exposes `outscale_*` hostvars and
`osc_*` groups, and supports `compose`, `keyed_groups`, `groups` and the
inventory cache.

## What is proven, and what is not

Every module is imported and its argument specification accepted by Ansible;
the installed SDK is asked whether it knows every action and parameter a
module sends; `ansible-test sanity` passes; the archive installs and answers
`ansible-doc`. Every module is played by the example playbook of the
repository against the feint emulator on every pull request, with the
platform built by Terraform, then destroyed, then checked for residue.

**No module has been run against a real Outscale account yet.** The
repository says so rather than claiming otherwise.

## Modules

The table below is derived from the modules on disk by
`scripts/readme_counters.py`; a stale table fails the CI.

<!-- counters:start, produced by scripts/readme_counters.py -->
### dhcp_option (1 module, tag `DhcpOption`)

| module | what it does |
|---|---|
| `dhcp_option_info` | Gather information about Outscale dhcp options |

### image (1 module, tag `Image`)

| module | what it does |
|---|---|
| `image_info` | Gather information about Outscale images |

### internet_service (1 module, tag `InternetService`)

| module | what it does |
|---|---|
| `internet_service_info` | Gather information about Outscale internet services |

### keypair (1 module, tag `Keypair`)

| module | what it does |
|---|---|
| `keypair_info` | Gather information about Outscale keypairs |

### load_balancer (1 module, tag `LoadBalancer`)

| module | what it does |
|---|---|
| `load_balancer_info` | Gather information about Outscale load balancers |

### nat_service (1 module, tag `NatService`)

| module | what it does |
|---|---|
| `nat_service_info` | Gather information about Outscale nat services |

### net (1 module, tag `Net`)

| module | what it does |
|---|---|
| `net_info` | Gather information about Outscale nets |

### net_peering (2 modules, tag `NetPeering`)

| module | what it does |
|---|---|
| `net_peering_action` | Perform an action on Outscale net peerings |
| `net_peering_info` | Gather information about Outscale net peerings |

### nic (1 module, tag `Nic`)

| module | what it does |
|---|---|
| `nic_info` | Gather information about Outscale nics |

### public_ip (2 modules, tag `PublicIp`)

| module | what it does |
|---|---|
| `public_ip_info` | Gather information about Outscale public ips |
| `public_ip_range_info` | Gather information about Outscale public ip ranges |

### region (1 module, tag `Region`)

| module | what it does |
|---|---|
| `region_info` | Gather information about Outscale regions |

### route_table (1 module, tag `RouteTable`)

| module | what it does |
|---|---|
| `route_table_info` | Gather information about Outscale route tables |

### security_group (1 module, tag `SecurityGroup`)

| module | what it does |
|---|---|
| `security_group_info` | Gather information about Outscale security groups |

### snapshot (1 module, tag `Snapshot`)

| module | what it does |
|---|---|
| `snapshot_info` | Gather information about Outscale snapshots |

### subnet (1 module, tag `Subnet`)

| module | what it does |
|---|---|
| `subnet_info` | Gather information about Outscale subnets |

### subregion (1 module, tag `Subregion`)

| module | what it does |
|---|---|
| `subregion_info` | Gather information about Outscale subregions |

### tag (1 module, tag `Tag`)

| module | what it does |
|---|---|
| `tag_info` | Gather information about Outscale tags |

### vm (5 modules, tag `Vm`)

| module | what it does |
|---|---|
| `vm_action` | Perform an action on Outscale vms |
| `vm_admin_password_info` | Read the Outscale admin password |
| `vm_info` | Gather information about Outscale vms |
| `vm_state_info` | Gather information about Outscale vm states |
| `vm_type_info` | Gather information about Outscale vm types |

### volume (1 module, tag `Volume`)

| module | what it does |
|---|---|
| `volume_info` | Gather information about Outscale volumes |

### Inventory plugins

| plugin | what it discovers |
|---|---|
| `vm` | Outscale Vm dynamic inventory |
<!-- counters:end -->

## Where to report

This collection is generated: a defect in a module is fixed in the contract,
a classification rule or an override of the generator, never in the module
itself. Issues: <https://github.com/stephrobert/collection-outscale/issues>.
