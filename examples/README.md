# The example platform, and what it proves

This directory carries a **complete platform** built by Terraform and the
official Outscale provider, and the playbook that operates it with the
collection. It does not exist to look nice: it is the bench on which what the
collection can do gets proven, and the gate that refuses a module nothing
exercises.

```text
examples/stack/               the platform, in HCL: three Nets, routing, NAT, machines, a balancer
examples/playbooks/           the dynamic inventory and the modules playbook
examples/callback_plugins/    journal.py, what really ran
```

## Terraform, the same tool as a real user

The Outscale Terraform provider honours `OSC_ENDPOINT_API` end to end since
its 1.7 generation, and the feint emulator proves Terraform on every one of
its own pull requests (`capabilityMatrix`: Outscale / Terraform, supported,
proven in CI). The platform is therefore written in HCL, and the same stack
would apply against a real account with real credentials in the environment:
this repository never does that.

## What the platform contains

* a **workload Net** with two public subnets, one per subregion, and a
  private one; a **services Net** receiving a Net peering that Terraform
  proposes **without accepting it**, so that `net_peering_action` accepts
  it. The `reject` action is not exercised, and that is measured: a rejected
  peering cannot be deleted any more (409 9029 `ResourceConflict`, as the
  API documents), so rejecting a peering Terraform manages made the platform
  impossible to destroy;
* an Internet service, a public route table, a NAT service with its own
  public IP and a private route table, a DHCP options set;
* two **web** machines, one per subregion, each with a public IP, behind a
  **load balancer**; one **app** machine with a second network interface and
  a data volume;
* a golden **image** built from a volume and its snapshot, a keypair, two
  security groups with their rules, and a tag per machine carrying the run.

## What the run does

```bash
mise run example      # feint on 127.0.0.1:4811, free, offline
```

1. the emulator is adopted if it listens and holds nothing, started
   otherwise; the environment comes from `feint env outscale`;
2. a residue baseline is captured through the SDK;
3. `terraform apply`, with a prefix unique to the run;
4. the control plane is verified **through the SDK**, not through the
   collection;
5. the dynamic inventory is compared to what the stack built;
6. `modules.yml` calls **every** module of the collection, twice for the
   actions whose idempotence can be proven, under a callback plugin that
   records what really ran;
7. in a `finally`: `terraform destroy`, the residue check, and the coverage
   artefact under `build/example/`.

The exit code combines the playbook and the teardown: a destroy that fails
after a green playbook is a failure.

## The rule that comes first: the real account is never touched

Nothing here talks to a real Outscale account. `python scripts/example.py
reel` refuses to run without `--compte-reel-accorde`, a flag only the
maintainer passes after being asked, every time. The emulator port, 4811, is
distinct from the ones the sibling repositories use, and the launcher refuses
to adopt an emulator that already holds machines.
