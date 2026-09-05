# Generator architecture

This repository does not contain a hand-written Ansible collection: it
contains the generator that writes it, and the decisions that turn a technical
API into a coherent Ansible interface. The source of the contract and its
measured shape are in [outscale-contract.md](outscale-contract.md).

## The pipeline

```text
specs/outscale/outscale.v1.yml          versioned contract (OpenAPI 3.0), one document for every tag
        |
        v  generator/source/base.py     split by tag (products.txt)
   SpecDocument                          the document, reduced to the product's operations
        |
        v  generator/parser/openapi.py
   ApiService                            canonical IR, without Ansible nor SDK
        |
        v  generator/classifier/rules.py
   Classification                        INFO ACTION MANAGE WORKFLOW LIFECYCLE IGNORE UNKNOWN
        |
        v  generator/overrides/*.yml
   ProductPlan                           decision + target module + reason
        |
        +--> generator/report/render.py  text, JSON, Markdown
        |
        +--> generator/ansible/models.py intermediate model
                    |
                    v  generator/renderer + templates/
             plugins/modules/*.py
                    |
                    v  plugins/module_utils/outscale.py
             execution: official SDK, pagination, state re-read, errors
```

## The structuring decisions

### 1. A product is a tag

Outscale publishes a single document and declares no tag list: every
operation carries exactly one tag, and that tag is the resource (`Vm`,
`NetPeering`, `LoadBalancer`). `products.txt` indexes tags as the contract
writes them, and names the product in snake_case unless told otherwise.
`python -m generator products --classify` counts the whole document, tag by
tag, with the UNKNOWN of each, so that what is not indexed stays counted.

Only the tags the example platform can exercise are indexed: 22 of 50. The
rule is *fewer modules, all exercised*.

### 2. The operation key is stable

`vm.v1.Vm.StartVms`: product, version, resource, contract identifier. It is
the key of the overrides and of the report.

### 3. The resource is derived from the identifier

The path carries nothing but the identifier (`POST /StartVms`), so the
resource is the `operationId` stripped of its verb, each word singularised:
`ReadVms` and `UpdateVm` give `vm`, `ReadVmTypes` gives `vm_type`,
`AcceptNetPeering` gives `net_peering`. The rule is one line, and its defects
are visible in the report: `RegisterVmsInLoadBalancer` gives
`vm_in_load_balancer`, which is LIFECYCLE and carried by no module.

The module name does not repeat the product when the resource already starts
with it: `vm_info`, `vm_type_info`, `load_balancer_info`, and
`vm_admin_password_info` for a resource that needs to say where it comes
from.

### 4. The classification rules are Outscale's

| verb | class |
|---|---|
| `Read` | INFO |
| `Create`, `Delete` | LIFECYCLE |
| `Link`, `Unlink`, `Register`, `Deregister`, `Add`, `Remove` | LIFECYCLE |
| `Update`, `Put`, `Set` | MANAGE |
| `Start`, `Stop`, `Reboot`, `Accept`, `Reject`, `Enable`, `Disable`, `Scale` | ACTION |
| anything else, or any method other than POST | UNKNOWN |

There is no fallback on the HTTP method, and that is the lesson of the
measurement: Scaleway's rules applied to this document render 190 ACTION and
no UNKNOWN, with all 74 reads classified as actions, because their last rule
is "POST outside creation is an action". A rule that decides wrongly is worse
than a rule that does not decide. The Outscale rules leave 1 UNKNOWN on 236
(`CheckAuthentication`, in a tag the generator does not index) and none on
the 22 indexed products. A test plants a witness: a contract carrying an
operation no rule can settle makes `report --strict` exit 2.

### 5. A read is one operation, with its filters

Outscale has no GET/LIST pair: `ReadVms` is the list, and `ReadVms` filtered
on `VmIds` is the unit read. An information module carries **one** operation
and exposes its `Filters` as a dictionary whose accepted keys are the
properties of the referenced schema (`FiltersVm` has 67). 36 reads out of 74
page by `NextPageToken`, and the runtime follows the token to the last page;
the others answer in one response and the report says the contract does not
promise it is complete.

### 6. An action answers at once, and the state comes later

`StopVms` answers `stopping`; the machine reaches `stopped` afterwards. There
is no operation object to wait for. The expected state of each action is a
human decision written in an override `wait` (`State` for a Vm, `State.Name`
for a Net peering), and the module re-reads the resource through the read of
the same resource, filtered on the selector. The filter key is read in the
`Filters` schema, as is (`VmIds`) or pluralised (`NetPeeringIds`), never
guessed. The module reports `changed=false` without sending anything when
every targeted resource already is in the expected state, except for an
action declared `always` such as `reboot`.

### 7. What the example cannot exercise is not generated

A read the emulator declines (`ReadConsoleOutput`, `ReadVmsStopHistory`,
`ReadVmsHealth`, the export tasks) stays classified INFO and counted in the
coverage, but an override `expose: false` with its reason removes it from the
modules. The report lists it under *classified without a module, by
decision*, and the coverage gate of the example has an empty exception list.

### 8. Coverage names its denominator

```text
Day-2 coverage = (AUTO + OVERRIDE) / (INFO + ACTION + MANAGE + WORKFLOW)
```

Measured on vm: 10 Day-2 candidates out of 12 operations, 100% classified
for automatic generation. The generation report publishes next to it the
share carried by a written module, which is lower as long as MANAGE has no
renderer and two reads are hidden by decision.

## Two goldens, two different measurements

* `tests/fixtures/<product>/expected_ir.json` freezes what the parser reads
  from the real contract, for each of the 22 indexed products. It moves when
  Outscale moves;
* `tests/fixtures/widget/expected_modules/` freezes what the renderer writes,
  from the laboratory contract. It must not move the day Outscale adds a
  machine.

## What holds the produced file

The generator is not judged by the generator. `mise run sanity` runs
`ansible-test sanity` in place, and refuses a green obtained on zero examined
file. `mise run package` builds the archive, checks that it carries
everything `plugins/` holds on disk and nothing from the repository, installs
it in a throwaway directory and asks `ansible-doc` for a module's
documentation. A test imports every generated module, builds its
`AnsibleModule` with real arguments, and asks the installed SDK whether it
knows each action and each parameter the module sends: the SDK embeds its
own copy of the contract and refuses what it does not know, so contract and
SDK are released together (`scripts/sync_specs.py` pins the tag).

`mise run example` builds the platform of `examples/stack/` with Terraform
against the feint emulator, discovers it with the dynamic inventory, plays
every module of the collection, destroys everything, and checks that nothing
survived. It is the only behavioural proof of the repository, and it never
talks to a real Outscale account.
