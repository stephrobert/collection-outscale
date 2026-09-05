# Security policy

## Reporting a vulnerability

Open a **private security advisory** on GitHub, through `Security` then
`Report a vulnerability`, rather than a public issue.

Committed deadlines:

| step | deadline |
|---|---|
| acknowledgement | 3 working days |
| first assessment, with the retained severity and its reason | 10 working days |
| fix, or a reasoned decision not to fix | 90 days |

The repository is maintained by one person. These deadlines are the ones a
single person can hold, and they are written for that reason rather than
copied from a template: a 24-hour commitment nobody can honour is worth less
than a 3-day commitment that is kept.

## Scope, and what it excludes

This repository produces a **generator** and an **Ansible collection**. It
hosts no service, stores no data, and holds no credential.

In scope:

* a flaw in the generated code or in the module runtime
  (`ansible_collections/stephrobert/outscale/plugins/`), notably anything that
  would write a secret to a log, bypass `no_log`, or execute data coming from
  the API;
* a flaw in the generator (`generator/`) that would produce a dangerous
  module from a hostile OpenAPI contract;
* a supply-chain weakness: exploitable workflow, unpinned dependency,
  compromised action.

Out of scope:

* vulnerabilities in the Outscale API itself, to be reported to Outscale;
* vulnerabilities in `ansible-core` or in the Outscale SDK
  (`osc-sdk-python`), to be reported to their respective projects. Report
  them here anyway if this repository **worsens** them, for instance by
  pinning a version known to be vulnerable.

## What the repository already does, and which is verified

The statements below are held by a CI gate, not by this page. A sentence
describing a control nobody applies reads exactly like the control.

| statement | what holds it |
|---|---|
| no third-party action referenced by a mutable tag | `zizmor` and `poutine`, in `Sécurité des workflows` |
| no third-party action outside the allowed list | `plumber`, which reads `.plumber.yaml`: an action missing from the list fails the analysis |
| no default rights on the `GITHUB_TOKEN` | `permissions: {}` at the top of every workflow, checked by `poutine` |
| no unpinned Python dependency | `requirements-dev.lock` with hashes, installed by `uv pip install --require-hashes` |
| no secret in the repository | `TruffleHog` in `--results=verified --fail` mode |
| the applied branch protection is the declared one | the job `La protection de branche est celle qui est déclarée` compares the live ruleset to `.github/rulesets/main.json` |
| no Outscale credential needed by CI | the contract is versioned, and no CI job talks to the Outscale API: the example platform runs against the feint emulator with placeholder keys |
| the ansible-core matrix is the one the collection declares | `scripts/ansible_matrix.py --check` derives it from `meta/runtime.yml` and the lock, and fails on any drift in `ci.yml` or the ruleset |

## What the repository does not do

* **No signed release, no provenance yet.** The collection is not published
  on Ansible Galaxy. The day it is, signature and provenance attestation will
  be a condition of that publication, not an afterthought.
* **No review by a second reader.** There is one maintainer. What this
  repository substitutes for a second reader is machinery, described in
  `docs/scorecard.md`: it does not replace a reviewer, and both sentences are
  true at once.
* **No run against a real Outscale account.** Every module is exercised
  against the emulator only, and the repository says so rather than claiming
  otherwise.
