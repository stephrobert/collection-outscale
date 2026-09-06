# collection-outscale

A generator of **Day-2** Ansible modules for the Outscale API, and the
`stephrobert.outscale` collection it produces.

> Terraform provisions resources. Ansible operates existing ones.

The generator therefore produces neither `create` nor `delete`: it produces
information modules and one-shot action modules on existing resources.

## Why this repository exists

Outscale publishes a complete, single OpenAPI 3.0 contract
(`github.com/outscale/osc-api`, `outscale.yaml`, tag 1.42.0): 236 operations,
all `POST` on a path that is the operation name, one tag per operation, 50
tags. That contract is versioned here, and it is what gets measured rather
than followed by hand. The official Python SDK (`osc-sdk-python`) embeds the
same document and refuses any call its copy does not know, so the contract
and the SDK are pinned together.

The shape of that API is not the shape of Scaleway's nor Exoscale's, and the
measurement decided the classifier: the Scaleway rules, which decide on the
HTTP verb, classify all 74 reads as actions here and render no UNKNOWN at
all. The rules of this repository decide on the verb of the operation name,
leave 1 UNKNOWN on 236 (in a tag the generator does not index) and 0 on the
22 indexed products. [docs/architecture/outscale-contract.md](docs/architecture/outscale-contract.md)
carries every measured fact.

## Fewer modules, all exercised

Only the tags the example platform can touch are indexed: 22 of 50. Every
module the collection ships is called by the example playbook, against the
feint emulator, on every pull request, and the coverage gate has an **empty**
exception list. What the emulator cannot serve is not generated: an override
removes it from the modules with its reason, and the report lists it. The
repository grows when the example grows, never before. A state module earns
its place the same way: the playbook writes each setting twice, and the second
pass must report `changed=false`.

Nothing here has been run against a real Outscale account: the maintainer's
credentials are never used by this repository, and the emulator is free.

## State, measured

The block below is **derived**, not written: `scripts/readme_counters.py`
reads the strict report, the generation report, the produced modules, the
example playbooks, the test collection, the falsification specs and the CI
workflow, and `mise run readme:check` fails the CI when a number has aged.

<!-- counters:start, produced by scripts/readme_counters.py -->
```text
outscale v1 (document 1.42.0): 236 operations in a single document, 50 tags counted, 22 indexed
  vm v1: 12 operations, 4 paginated, 2 classified without a module
    INFO 6 · ACTION 3 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 10 · AUTO 10 · OVERRIDE 0 · classified for automatic generation 100.0% (10/10)
  volume v1: 7 operations, 2 paginated, 1 classified without a module
    INFO 2 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 4 · IGNORE 0 · UNKNOWN 0
    Day-2 3 · AUTO 3 · OVERRIDE 0 · classified for automatic generation 100.0% (3/3)
  snapshot v1: 6 operations, 2 paginated, 2 classified without a module
    INFO 2 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 3 · IGNORE 0 · UNKNOWN 0
    Day-2 3 · AUTO 3 · OVERRIDE 0 · classified for automatic generation 100.0% (3/3)
  image v1: 6 operations, 2 paginated, 1 classified without a module
    INFO 2 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 3 · IGNORE 0 · UNKNOWN 0
    Day-2 3 · AUTO 3 · OVERRIDE 0 · classified for automatic generation 100.0% (3/3)
  keypair v1: 3 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  net v1: 4 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  subnet v1: 4 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  security_group v1: 3 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  security_group_rule v1: 2 operations, 0 paginated, 0 classified without a module
    INFO 0 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 0 · AUTO 0 · OVERRIDE 0 · classified for automatic generation n/a (0/0)
  public_ip v1: 6 operations, 2 paginated, 0 classified without a module
    INFO 2 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 4 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  nic v1: 8 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 6 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  route_table v1: 6 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 4 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  route v1: 3 operations, 0 paginated, 0 classified without a module
    INFO 0 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  internet_service v1: 5 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 4 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  nat_service v1: 3 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  net_peering v1: 5 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 2 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 3 · AUTO 3 · OVERRIDE 0 · classified for automatic generation 100.0% (3/3)
  dhcp_option v1: 3 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  load_balancer v1: 12 operations, 0 paginated, 2 classified without a module
    INFO 3 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 8 · IGNORE 0 · UNKNOWN 0
    Day-2 4 · AUTO 4 · OVERRIDE 0 · classified for automatic generation 100.0% (4/4)
  listener v1: 6 operations, 0 paginated, 2 classified without a module
    INFO 1 · ACTION 0 · MANAGE 1 · WORKFLOW 0 · LIFECYCLE 4 · IGNORE 0 · UNKNOWN 0
    Day-2 2 · AUTO 2 · OVERRIDE 0 · classified for automatic generation 100.0% (2/2)
  tag v1: 3 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 2 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  region v1: 1 operations, 0 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 0 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)
  subregion v1: 1 operations, 1 paginated, 0 classified without a module
    INFO 1 · ACTION 0 · MANAGE 0 · WORKFLOW 0 · LIFECYCLE 0 · IGNORE 0 · UNKNOWN 0
    Day-2 1 · AUTO 1 · OVERRIDE 0 · classified for automatic generation 100.0% (1/1)

collection stephrobert.outscale: 32 modules written, 34 planned, 2 set aside with their reason
  32 of 32 modules called by the example playbooks (100.0%)
  dhcp_option_info                         Gather information about Outscale dhcp options
  image                                    Manage the settings of an Outscale image
  image_info                               Gather information about Outscale images
  internet_service_info                    Gather information about Outscale internet services
  keypair_info                             Gather information about Outscale keypairs
  load_balancer                            Manage the settings of an Outscale load balancer
  load_balancer_info                       Gather information about Outscale load balancers
  nat_service_info                         Gather information about Outscale nat services
  net                                      Manage the settings of an Outscale net
  net_info                                 Gather information about Outscale nets
  net_peering_action                       Perform an action on Outscale net peerings
  net_peering_info                         Gather information about Outscale net peerings
  nic                                      Manage the settings of an Outscale nic
  nic_info                                 Gather information about Outscale nics
  public_ip_info                           Gather information about Outscale public ips
  public_ip_range_info                     Gather information about Outscale public ip ranges
  region_info                              Gather information about Outscale regions
  route_table_info                         Gather information about Outscale route tables
  security_group_info                      Gather information about Outscale security groups
  snapshot_info                            Gather information about Outscale snapshots
  subnet                                   Manage the settings of an Outscale subnet
  subnet_info                              Gather information about Outscale subnets
  subregion_info                           Gather information about Outscale subregions
  tag_info                                 Gather information about Outscale tags
  vm                                       Manage the settings of an Outscale vm
  vm_action                                Perform an action on Outscale vms
  vm_admin_password_info                   Read the Outscale admin password
  vm_info                                  Gather information about Outscale vms
  vm_state_info                            Gather information about Outscale vm states
  vm_type_info                             Gather information about Outscale vm types
  volume                                   Manage the settings of an Outscale volume
  volume_info                              Gather information about Outscale volumes
  vm (inventory)                           dynamic inventory
  480 unit tests · 61 guards proven by mise run falsify
  CI: 4 jobs, Générateur · collection · Archive · Plateforme d'exemple
  ansible-test sanity: reported by `mise run sanity`, not counted here
```
<!-- counters:end -->

## How it works

```text
specs/outscale/outscale.v1.yml    the contract, versioned byte for byte
        |
        v  generator/               source -> parser -> IR -> classifier -> overrides -> plan
        |                            -> report, and -> Ansible model -> renderer
        v
ansible_collections/stephrobert/outscale/   the collection, where Ansible expects it
        |
        v  examples/                 a Terraform platform, the dynamic inventory, one playbook
                                     that calls every module, against the emulator
```

[docs/architecture/generator.md](docs/architecture/generator.md) explains
each stage and the decisions behind it.

## Using the repository

```bash
mise install && mise run setup   # tools and the locked development environment
mise run check                   # what a pull request must pass, offline, deterministic
mise run example                 # the platform against feint, every module played, destroyed
mise run sanity                  # ansible-test sanity, in place
```

`mise tasks` lists everything. The collection's own README is
[ansible_collections/stephrobert/outscale/README.md](ansible_collections/stephrobert/outscale/README.md).

## Following the upstream

```bash
python scripts/sync_specs.py --tag <latest>   # download another tag of osc-api
mise run drift                                # what moved, tag by tag, indexed or not
mise run check                                # golden and strict report fail on what moved
```

The tag is pinned in `scripts/sync_specs.py` and follows `osc-sdk-python`:
the SDK refuses what its embedded copy does not know, so the two are raised
together. A weekly workflow measures the drift and opens an issue; it never
decides anything.

## Language

Published content is in English: this file, `docs/`, the collection, its
changelog. Everything that produces it is in French: code, comments, tests,
commit messages, reports.

## License

GPL-3.0-or-later. The contract under `specs/outscale/` is Outscale's, under
its own license (BSD-3-Clause).
