# The Outscale dynamic inventory

`stephrobert.outscale.vm` builds an Ansible inventory from the virtual
machines of an Outscale account. It discovers them region by region with
`ReadVms`, page after page, with the OAPI filters you give, then names,
addresses, filters and groups them.

Everything this document claims is measured by the unit tests in
[tests/unit/inventory/](https://github.com/stephrobert/collection-outscale/blob/main/tests/unit/inventory/),
on doubles, and the plugin has been played against
[feint](https://github.com/stephrobert/feint), the local emulator. Nothing
has been played against a real account yet: that is written here rather than
implied.

## The configuration file

Ansible recognises an inventory plugin by the **file name**. It must end in
`outscale.yml` or `osc.yml`, otherwise it is silently ignored:

```bash
ansible-inventory -i production.outscale.yml --graph
```

The minimum fits on one line, and the SDK provides the rest:

```yaml
plugin: stephrobert.outscale.vm
```

## Credentials and region

Nothing is required. The SDK reads `~/.osc/config.json` and the `OSC_*`
environment by itself, exactly as the Outscale CLIs and the Terraform
provider do:

```bash
export OSC_ACCESS_KEY=... OSC_SECRET_KEY=... OSC_REGION=eu-west-2
```

The options `access_key`, `secret_key`, `profile` and `api_url` take
precedence when set, and each reads its environment variable
(`OSC_ACCESS_KEY`, `OSC_SECRET_KEY`, `OSC_PROFILE`, `OSC_ENDPOINT_API` then
`OUTSCALE_API_URL`).

The API host carries the region (`api.{region}.outscale.com`), so the plugin
builds one client per region. Without `regions`, the region the SDK resolves
is queried: `OSC_REGION`, then the profile, then `eu-west-2`. The plugin asks
the SDK rather than guessing.

```yaml
regions:
  - eu-west-2
  - cloudgouv-eu-west-1
```

`OSC_ENDPOINT_API` is honoured end to end: with an explicit URL, a single
client serves every region, which is what a local emulator expects.
`eval "$(feint env outscale --endpoint http://127.0.0.1:4811)"` is enough
to build an inventory without an account.

## API filters

`filters` is sent to `ReadVms` as it is, with the names of the `FiltersVm`
schema of the contract:

```yaml
filters:
  VmStateNames:
    - running
  Tags:
    - env=production
```

The plugin does not validate these names: validating them would require a
copy of the contract in the plugin, which would age. A name the API does not
know comes back as a `400` whose message names it, and the plugin reports the
API's message. A test requires that the filters of the example inventory
exist in the versioned contract.

Every page is read: a `NextPageToken` is followed until the API stops
returning one. A token returned twice in a row stops the loop and is
reported as a warning, because an endless loop is worse than a truncated
list that says so.

## Machine names

`hostnames` gives the sources of `inventory_hostname`, in order:

```yaml
hostnames:
  - tag:Name       # the value of the "Name" tag (the default)
  - tag:role       # any tag, by its key
  - public_ipv4
  - id
```

`name` reads the `Name` tag as well. Two machines may share a name: the
plugin never lets the second overwrite the first. The region is appended,
then the machine ID, and the collision is reported.

## Addresses

`ansible_host` is chosen by family, in the order of `address_priority`,
public first by default:

```yaml
address_priority:
  - public_ipv4
  - private_ipv4
require_address: false
```

In the Outscale API the public address is on the machine (`PublicIp`) and
the private addresses are on its network interfaces
(`Nics[].PrivateIps[].PrivateIp`); `PrivateIp` on the machine is only a
fallback when the interfaces are missing. A machine created outside a Net
has none of them, and it stays in the inventory without `ansible_host`,
which is still useful for tasks delegated to localhost that act through the
collection's modules. `require_address: true` drops it instead.

`entry_role` reproduces a pattern of a typical Outscale estate: one bastion
reachable from outside and the rest behind it.

```yaml
entry_role: bastion   # read in the "role" tag, or in entry_tag
```

The machine whose `role` tag is `bastion` gets its public address; every
other machine gets its private address, to be reached through a `ProxyJump`
set in `group_vars`. This replaces the conditional `compose` everyone used
to rewrite. `outscale_address_source` says which family was chosen, and the
`-vvvv` output says by which rule.

## Local filters

These apply after the API filters, on the normalised model, and the
exclusions come first:

```yaml
states:
  - running
tags:
  env: production
  role: ""            # the key exists, whatever its value
tags_match: any       # or all
exclude_tags:
  managed_by: talos   # machines Ansible will never reach over SSH
exclude_vm_ids:
  - i-0123456789
```

The `-vvv` output names each machine set aside, and why.

## Groups

`group_by` builds the native `osc_*` groups:

| axis | group |
|---|---|
| `region` | `osc_region_eu_west_2` |
| `subregion` | `osc_subregion_eu_west_2a` |
| `state` | `osc_state_running` |
| `tags` | `osc_tag_env_production`, one per key and value |
| `net` | `osc_net_vpc_12345678` |
| `subnet` | `osc_subnet_subnet_12345678` |
| `vm_type` | `osc_vm_type_tinav5_c1r1p2` |
| `keypair` | `osc_keypair_admin` |

The default is `[region, subregion, state, tags]`. Names are sanitised the
same way everywhere: accents are unfolded, anything else becomes `_`, and a
leading digit is prefixed.

`compose`, `groups` and `keyed_groups` are the standard Ansible mechanisms,
applied on the host variables below.

## Host variables

```text
outscale_id, outscale_name, outscale_state
outscale_region, outscale_subregion
outscale_net_id, outscale_subnet_id
outscale_vm_type, outscale_image_id, outscale_keypair_name
outscale_public_ipv4                 the public address, or null
outscale_private_ipv4                the first private address, or null
outscale_private_ipv4s               every private address
outscale_tags                        the tags as a mapping
outscale_security_group_ids          the groups of the machine and of its interfaces
outscale_address_source              which family gave ansible_host, or why none did
outscale_raw                         the API object, only with include_raw: true
```

`outscale_id` and `outscale_region` are what lets a playbook chain on the
Day-2 modules of the collection without a lookup. `include_raw` is off by
default because the raw object carries `UserData`, which may hold secrets,
and the raw object goes into the cache.

## Cache

`cache: true` uses the cache plugin Ansible is configured with. The cache key
carries a fingerprint of everything that changes the result: the API URL,
the account identity (hashed, never the key itself), the regions, the API
and local filters, the naming and grouping options. Two accounts never share
a cached estate.

## Failures are said, never swallowed

A failed `ReadVms` is an error, never an empty region. Three failures give
three messages, and the API's own `Code`, `Type` and `Details` are quoted:

| what happened | what the plugin does |
|---|---|
| refused credentials (`401`) | stops at once: continuing would produce an empty inventory that presents itself as complete |
| missing permission (`403`) | an error for that region: the estate is unknown, not empty |
| rejected request (`400`, typically an unknown filter) | an error that quotes the API's message |
| API or network failure (`5xx`, unreachable host) | an error for that region |

With `strict: true` (the default), any error fails the inventory. With
`strict: false`, it is reported as a warning and the other regions are kept.

The `-vvv` output of `ansible-inventory` lists what happened: API calls,
hosts per provider, and the reason each filtered machine was set aside.

## How the engine is built

`plugins/module_utils/inventory/` is layered: `config`, `models`, `hostname`,
`groups`, `filtering`, `address`, `paging`, `errors`, `discovery`, and one
provider per product under `providers/`. A test walks the code of every core
layer and refuses any product name in it: adding a product costs a provider
file and one line in the discovery table, never a change to the core. A
second test reads, by AST, the fields the provider reads from the API and
requires that each exists in the `Vm` schema of the versioned contract, or
in the schemas it references: a field renamed upstream fails the CI instead
of leaving an estate mute.
