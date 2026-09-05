# The Outscale contract, measured

Everything the generator decides rests on what the published OpenAPI document
carries. This page records what was **measured** on `outscale/osc-api` at tag
1.42.0 (5 September 2026), so that a design decision can be traced back to a
fact rather than to a guess. When Outscale moves, `mise run drift` says which
of these facts moved.

## Where the contract comes from

| source | what it is | used here |
|---|---|---|
| `github.com/outscale/osc-api`, file `outscale.yaml`, tags without a `v` prefix (`1.42.0`) | the canonical description, BSD-3, "no contribution accepted" | **yes**, versioned byte for byte under `specs/outscale/outscale.v1.yml` |
| `github.com/outscale/osc-api-deploy` | a derived copy with tweaks for SDK generators (`outscale-go.yaml`, `outscale-java.yaml`), tags with a `v` prefix | no: its README points back to `osc-api` for the original |
| `osc-sdk-python` (PyPI), `resources/outscale.yaml` | the same document, embedded in the SDK; version 0.42.0 embeds 1.42.0 | the runtime calls this SDK, and a test requires that both copies agree on every action a module calls |

`scripts/sync_specs.py` pins the tag: the SDK refuses any action or parameter
its own copy does not know, so following the latest tag without following the
SDK would generate modules the SDK rejects. Contract and SDK move together.

## Shape

| measure | value |
|---|---|
| `openapi` | 3.0.0 |
| `info.version` | 1.42.0 |
| paths, operations | 236, 236 |
| HTTP methods | POST only, 236/236 |
| path shape | `/<OperationId>`, and `path == operationId` for 236/236 |
| path or query parameters | none |
| tags | 50, exactly one per operation, none declared at the root, no hierarchy |
| schemas | 655: 236 `<Op>Request`, 237 `<Op>Response` (with `ErrorResponse`), 182 shared |
| servers | one, `https://api.{region}.outscale.com/api/v1`, five regions, `eu-west-2` by default |
| security | `ApiKeyAuth` (AWS Signature v4 `osc4`) on 214 operations; 14 IAM/CA operations accept `BasicAuth`; 8 catalogue reads need no authentication |

## Verbs

The verb is the first CamelCase word of the `operationId`, and it takes 21
values:

| verb | operations | class |
|---|---:|---|
| `Read` | 74 | INFO |
| `Create`, `Delete` | 46, 46 | LIFECYCLE |
| `Update` | 27 | MANAGE |
| `Link`, `Unlink` | 11, 11 | LIFECYCLE |
| `Enable`, `Disable` | 3, 3 | ACTION |
| `Put`, `Scale` | 2, 2 | MANAGE, ACTION |
| `Accept`, `Add`, `Deregister`, `Reboot`, `Register`, `Reject`, `Remove`, `Set`, `Start`, `Stop` | 1 each | see `generator/classifier/rules.py` |
| `Check` | 1 | UNKNOWN (`CheckAuthentication`, tag `Account`, not indexed) |

Applying the Scaleway rules to this document gives 190 ACTION and 0 INFO:
their last rule is "POST outside creation is an action", and every one of the
74 reads lands there. The Exoscale rules give 163 ACTION with the same 74
reads misclassified. Neither renders a single UNKNOWN, which is what makes
them dangerous here: a green report on a wrong classification. The Outscale
rules render 1 UNKNOWN on 236, in a tag the generator does not index.

## Requests

* every request is one `application/json` body referenced as
  `#/components/schemas/<Op>Request`, `additionalProperties: false`;
* `DryRun` on 226 requests out of 236: an authorization probe, never an
  Ansible option;
* `NextPageToken` on 36 requests, always with `ResultsPerPage`; 8 IAM reads
  page differently (`FirstItem`, `HasMoreItems`) and are not indexed;
* `required` declared on 164 request schemas; `requestBody.required` on none;
* `Filters` on 49 of the 74 reads, always a reference to a `Filters<Resource>`
  schema (`FiltersVm` has 67 properties). For every action of an indexed
  product, the selector is found in the filters of the read of the same
  resource, either as is (`VmIds`) or pluralised (`NetPeeringId` to
  `NetPeeringIds`); this is what lets the runtime re-read the resource until
  the expected state;
* 15 `oneOf`, all `string(date) | string(date-time)` on date filters; no
  `allOf`, no `anyOf`, 14 `nullable`, no `readOnly`; `deprecated` on a few
  properties (`VmInitiatedShutdownBehavior` since 1.42.0).

## Responses

Every response carries a `ResponseContext` which is never the resource. Once
it and `NextPageToken` are removed:

| shape | operations | example |
|---|---:|---|
| one object | 86 | `UpdateVm` returns `Vm` |
| one list | 57 | `ReadVms` returns `Vms` |
| nothing | 79 | `LinkVolume` |
| several properties | 14 | `ReadAdminPassword` returns `AdminPassword` and `VmId` |

The fourth shape is undecidable: the module returns the whole response and
the report lists the operation among the contract's limits.

## What the contract does not say

* the state a resource reaches after an action. `Vm.State` is a plain string
  whose description enumerates `pending | running | stopping | stopped |
  shutting-down | terminated | quarantine`; `NetPeering.State` is an object
  `{Name, Message}`. The expected state of each action is a human decision,
  written in an override `wait` with its reason;
* whether a write is idempotent, or what `UpdateVm` compares against: 13 of
  its 14 request properties exist on `Vm` with the same name,
  `SecurityGroupIds` does not (the response carries `SecurityGroups[]`). A
  MANAGE renderer will have to say which fields it can compare;
* which routes an emulator serves. feint 0.12.1 serves 100 of the 236, and
  `specs/outscale/products.txt` indexes only the 22 tags it serves and the
  example platform touches.
