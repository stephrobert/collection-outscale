# Contributing

## The one rule

**The generated code is not the product.** The product is the versioned
contract, the classification rules, and the handful of explicit overrides that
turn a technical API into a coherent Ansible interface.

So a change that edits a file under `ansible_collections/` by hand is almost
always the wrong change. `mise run check:generated` regenerates everything and
fails on `git diff`, so the edit would not survive anyway, but the point is not
the check. The point is that thirty-two modules share one fix, and a hand edit
fixes one.

## Getting started

```bash
mise install && mise run setup   # the toolchain and the locked environment
mise run check                   # what a pull request must pass
```

`check` is deterministic and offline. It needs no Outscale account and no
credentials, and it takes a couple of minutes: lint, types, tests, the strict
report, the golden drift, the changelog fragments, the documentation linter,
the falsification of every guard, the CI matrix, the README counters, the
example coverage gate, the archive, and the documentation gate.

### Before you push

`mise run check` is the floor, not the ceiling. What else to run depends on what
you touched:

| what the change touches | run in addition | what it proves |
|---|---|---|
| a classification or naming rule | `mise run report`, read the diff | the decision changes where you think, and nowhere else |
| a guard, a validation, a refusal | `mise run falsify` | the test bites without the fix |
| the parser, the IR | `mise run golden:update`, read the diff | what the change really does to the operations |
| a generated module, a template, the runtime | `mise run sanity` | Ansible accepts the produced file |
| anything a reader sees | `mise run docs:quality` | the published page still explains itself |
| a module, a plugin, an inventory option | `mise run example` | it works against the emulator: platform built, inventory discovered, module played, everything destroyed |
| the contract | `python scripts/sync_specs.py --tag <latest>`, `mise run drift`, `mise run check` | what moved, tag by tag |
| a workflow, an action, `.github/` | `mise run security` | actionlint, zizmor and poutine accept the pipeline |
| `pyproject.toml` | `mise run lock`, read the diff | which dependency really appears, and under which hash |
| `meta/runtime.yml` | `mise run matrix:check` | the ansible-core bound is measured, not estimated |

**A golden regenerated without anyone reading its diff cancels the whole
mechanism.** It is a drift detector; refreshing it without looking turns it into
a rubber stamp.

## The real account is never touched

Nothing in this repository talks to a real Outscale account, and nothing may
without the maintainer's explicit agreement, asked for every time. The example
platform, the inventory, every module and the residue check run against the
[feint](https://github.com/stephrobert/feint) emulator, which is free. A run
against the real cloud costs money on the maintainer's account, and a resource
that survives a failed run is a paid residue.

`osc-cli` has no dry-run mode, and a call without parameters is already a call:
on 30 April 2026, a syntax check with `osc-cli api CreateAccessKey` created
three access keys on the root account. Do not validate a syntax against the
API.

## Falsifying a guard

A guard whose removal leaves every test green is a comment.

```bash
mise run falsify
```

It neutralises each declared guard in a copy outside the repository and requires
the named test to fail. Declared mutations live in `tests/falsify/specs.json`.

Two ways to write one that proves nothing, both met in the sibling
repositories:

* **deleting the term instead of neutralising the condition.** The import
  breaks, every test goes red, and it looks exactly like a proven guard. Keep
  every name evaluated: `if x is None and False:`, never `if False:`;
* **pointing the mutation at a test that reads the repository's state.** The
  files already carry the right content, so the test stays green while the
  function is broken. Exercise the function.

Add a mutation whenever you add a guard, and always after fixing a defect a
review named.

## Overrides

An override is a human decision, and it carries its reason:

```yaml
volume.v1.Volume.UpdateVolume:
  parameters:
    VolumeType:
      example: gp2
      reason: >-
        Le contrat cite les trois valeurs dans sa phrase, « The new type of
        the volume (`standard` | `io1` | `gp2`) », sans les déclarer en enum.
```

The loader refuses a decision without a `reason`, refuses an unknown field (a
typo would otherwise produce a silently inert override), and refuses a key
declared twice: YAML keeps the last one without a word, and that once erased a
`resource` decision in a sibling repository with nothing turning red.

Three things an override must never do:

* **fix a rule that is wrong everywhere.** A correction repeated across ten
  operations is a missing rule in `generator/classifier/rules.py`, not ten
  overrides;
* **cover a sentence the contract already carries.** A `description` override
  fills a gap and nothing else; the day Outscale documents the field, the
  override is reported as orphaned and `report --strict` exits 2;
* **invent.** A description written from memory is a claim about an API nobody
  checked. Transpose what the same contract says of the same field elsewhere,
  and name the source in the reason.

## What belongs here, and what does not

```text
Terraform provisions resources. Ansible operates existing resources.
```

An operation that creates, deletes or links resources has no place in this
collection, even when the generator can produce it. That is the boundary that
settles every design ambiguity, and it is why every `Create*`, `Delete*`,
`Link*` and `Unlink*` operation is LIFECYCLE, with no module.

**No operation ever disappears.** One that no rule settles is `UNKNOWN` and
fails `report --strict`. Never filter it out, never widen a rule to make it fit
somewhere. And an operation outside the indexed tags is counted by
`mise run products`, never forgotten.

**Fewer modules, all exercised.** A tag enters `products.txt` when the example
platform can touch it and the emulator serves it, never before. Every shipped
module is called by the example playbook, and the coverage gate has an empty
exception list.

## Issues

Before opening one about a missing module, run `mise run report` and look: the
operation is either generated, excluded with its reason, or `UNKNOWN`; and if
its tag is not indexed, `mise run products` counts it. Which of the states it is
changes the whole conversation.

The most useful report is **a playbook that failed**, with what Ansible printed.
This project's claim is that a generated module is the one an operator would
have written by hand; a playbook that says otherwise is a fact.

## Commits

Commit messages are in French. They say what changed and **why**, and they name
what was measured. The repository's history is the design record: a subject line
of "fix" tells a future reader nothing.

Everything published is in English: both READMEs, `docs/`, `galaxy.yml`,
changelog fragments, and whatever `DOCUMENTATION`, `EXAMPLES` and `RETURN`
carry. Code, comments, docstrings, test names, override reasons, workflows and
program output are in French, with the accents. The full table is in
`CLAUDE.md`.

Never use an em dash, in either language.

## AI-assisted contributions

The bar is the same as for everyone. What is added is disclosure and one extra
question.

**Disclose it** with an `Assisted-by:` trailer naming the tool and the model.

**Run it before you send it.** `mise run check`, yourself, not "it should pass".

**Every field name in the diff comes from the versioned contract, the Outscale
SDK, or a run against the emulator, and you can say which.** "The model produced
it" is not a source. This is the one failure mode this repository is built
against: a plausible, wrong translation that looks correct until a playbook
fails in production.

What gets refused on sight: a generated file edited by hand, a golden refreshed
without its diff being read, an override without a reason, a guard with no
mutation proving it, and any call to the real account.

## Security

Report a vulnerability privately rather than in a public issue. See
[SECURITY.md](SECURITY.md).
