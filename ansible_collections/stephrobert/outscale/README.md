# stephrobert.outscale

**Day-2** Ansible modules for the Outscale API, produced by the generator of
the repository that hosts this collection:
<https://github.com/stephrobert/collection-outscale>.

[![ci](https://github.com/stephrobert/collection-outscale/actions/workflows/ci.yml/badge.svg)](https://github.com/stephrobert/collection-outscale/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/stephrobert/collection-outscale?label=OpenSSF%20Scorecard)](https://github.com/stephrobert/collection-outscale/blob/0.1.0/docs/scorecard.md)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/stephrobert/collection-outscale/blob/0.1.0/LICENSE)

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

## Compatibility

The table below is derived from `meta/runtime.yml`, the development lock and
the module documentation by `scripts/readme_counters.py`; a stale table fails
the CI.

<!-- counters:compatibility:start, produced by scripts/readme_counters.py -->
| collection | `ansible-core` | Outscale SDK |
|---|---|---|
| 0.1.x | 2.17, 2.18, 2.19, 2.20, 2.21 | `osc-sdk-python>=0.42` |
<!-- counters:compatibility:end -->

Every `ansible-core` version listed is tested by CI on every change, with
`ansible-test sanity` and the documentation linter. A version declared and
never tested is a promise with no proof.

## Versioning

This collection follows **semantic versioning**, which Ansible requires of
collections:

<!-- counters:versioning:start, produced by scripts/readme_counters.py -->
* **patch** (`0.1.1`): bug fixes only;
* **minor** (`0.2.0`): backward-compatible features and new modules;
* **major** (`1.0.0`): may contain breaking changes.
<!-- counters:versioning:end -->

**Before `1.0.0`, treat the interfaces as evolving.** A module name will not
change silently: a rename goes through a `breaking_changes` fragment, and the
old name keeps working for one minor version with a deprecation notice. The
exact wording of a description, the choice of an example value and the set of
fields a returned key lists are not promises: all three come from the
versioned contract, and they follow it.

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

## Settings, read before they are written

A state module (the ones with no suffix) carries one update and the read that
judges it. It reads the resource, compares every option given with what the
API returns under the same name, sends the update only when something
differs, reads again, and returns `changes` with the value before and after.
In check mode it reports the difference without sending anything. An option
the read does not return is not exposed at all, and the limits of the module
say which and why: an option that cannot be compared would report
`changed=true` on every run.

```yaml
- name: Protect a machine against deletion
  stephrobert.outscale.vm:
    vm_id: i-12345678
    deletion_protection: true
  register: protection
```

`changed=false` is measured, not promised: the example playbook writes every
setting twice and checks that the second pass changes nothing.

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
inventory cache. The full guide, covering how `ansible_host` is chosen, name
collisions and the cache:
[docs/guides/dynamic-inventory.md](https://github.com/stephrobert/collection-outscale/blob/0.1.0/docs/guides/dynamic-inventory.md).

## What is proven, and what is not

Every module is imported and its argument specification accepted by Ansible;
the installed SDK is asked whether it knows every action and parameter a
module sends; `ansible-test sanity` passes; the archive installs and answers
`ansible-doc`. Every module is played by the example playbook of the
repository against the feint emulator on every pull request, with the
platform built by Terraform, then destroyed, then checked for residue.

Every page of this collection is meant to be understood from Galaxy alone,
without the OpenAPI contract: each option, each returned key and each of its
fields carries a description, and each example can be copied as is. A gate
measures it on every pull request and refuses the release otherwise.

**No module has been run against a real Outscale account yet.** The
repository says so rather than claiming otherwise.

## Modules

The table below is derived from the modules on disk by
`scripts/readme_counters.py`; a stale table fails the CI.

<!-- counters:start, produced by scripts/readme_counters.py -->
### dhcp_option (1 module, tag `DhcpOption`)

| module | what it does |
|---|---|
| `dhcp_option_info` | Gather information about Outscale DHCP options |

### image (2 modules, tag `Image`)

| module | what it does |
|---|---|
| `image` | Manage the settings of an Outscale image |
| `image_info` | Gather information about Outscale images |

### internet_service (1 module, tag `InternetService`)

| module | what it does |
|---|---|
| `internet_service_info` | Gather information about Outscale internet services |

### keypair (1 module, tag `Keypair`)

| module | what it does |
|---|---|
| `keypair_info` | Gather information about Outscale keypairs |

### load_balancer (2 modules, tag `LoadBalancer`)

| module | what it does |
|---|---|
| `load_balancer` | Manage the settings of an Outscale load balancer |
| `load_balancer_info` | Gather information about Outscale load balancers |

### nat_service (1 module, tag `NatService`)

| module | what it does |
|---|---|
| `nat_service_info` | Gather information about Outscale NAT services |

### net (2 modules, tag `Net`)

| module | what it does |
|---|---|
| `net` | Manage the settings of an Outscale net |
| `net_info` | Gather information about Outscale nets |

### net_peering (2 modules, tag `NetPeering`)

| module | what it does |
|---|---|
| `net_peering_action` | Perform an action on Outscale net peerings |
| `net_peering_info` | Gather information about Outscale net peerings |

### nic (2 modules, tag `Nic`)

| module | what it does |
|---|---|
| `nic` | Manage the settings of an Outscale NIC |
| `nic_info` | Gather information about Outscale NICs |

### public_ip (2 modules, tag `PublicIp`)

| module | what it does |
|---|---|
| `public_ip_info` | Gather information about Outscale public IPs |
| `public_ip_range_info` | Gather information about Outscale public IP ranges |

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

### subnet (2 modules, tag `Subnet`)

| module | what it does |
|---|---|
| `subnet` | Manage the settings of an Outscale subnet |
| `subnet_info` | Gather information about Outscale subnets |

### subregion (1 module, tag `Subregion`)

| module | what it does |
|---|---|
| `subregion_info` | Gather information about Outscale subregions |

### tag (1 module, tag `Tag`)

| module | what it does |
|---|---|
| `tag_info` | Gather information about Outscale tags |

### vm (6 modules, tag `Vm`)

| module | what it does |
|---|---|
| `vm` | Manage the settings of an Outscale VM |
| `vm_action` | Perform an action on Outscale VMs |
| `vm_admin_password_info` | Read the Outscale admin password |
| `vm_info` | Gather information about Outscale VMs |
| `vm_state_info` | Gather information about Outscale VM states |
| `vm_type_info` | Gather information about Outscale VM types |

### volume (2 modules, tag `Volume`)

| module | what it does |
|---|---|
| `volume` | Manage the settings of an Outscale volume |
| `volume_info` | Gather information about Outscale volumes |

### Inventory plugins

| plugin | what it discovers |
|---|---|
| `vm` | Outscale VM dynamic inventory |
<!-- counters:end -->

## Where to report

This collection is generated: a defect in a module is fixed in the contract,
a classification rule or an override of the generator, never in the module
itself. Issues: <https://github.com/stephrobert/collection-outscale/issues>.
