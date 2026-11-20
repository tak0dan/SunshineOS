# Sunshine Evolution Engine

A repository-driven, target-state transformation and reconciliation system that evolves both
supported Arch Linux installations and existing Sunshine OS installations into the currently
published Sunshine OS architecture.

## Core idea

Sunshine OS is a **target state**, not a prerequisite. The same engine must handle:

```
Old Sunshine OS  ──> Current Sunshine OS
Pure Arch Linux  ──> Current Sunshine OS
```

The engine never asks "which Sunshine version is installed?" as its primary question. It asks
"what does this machine actually have, and what must it have?".

## Five principles

1. **Desired-state convergence** — describe the target, reconcile the machine with it.
2. **Capability discovery** — inspect the actual machine; don't assume installation history.
3. **Evolutionary components** — introduce, evolve, replace, reconfigure, retire independently.
4. **Declarative transformation plans** — compute operations, including never-before-seen ones.
5. **Upstream preservation** — Arch stays the foundation; pacman remains the package authority.

## Pipeline

```
Stage A trust → Discover → Resolve target → Plan → Preflight → Execute (journaled) → Validate → Commit
```

Stage A is optional in the offline test CLI but mandatory in production. The Rust bootstrap in
`bootstrap-rust/` verifies signed metadata, artifact digests, chained key rotation, protocol
compatibility and the verified Core handoff, then writes a signed receipt and executes Core.
Core can also verify a Python-side `--trust-index`; with `--trust-report` and `--trust-receipt` it
verifies the Rust receipt instead. Signed Rust adapters are registered only after Stage A passes,
then launched in a narrow `systemd-run` sandbox and journaled. See `docs/SPEC_ALIGNMENT.md` for the
remaining architecture gaps.

## Layout

```
src/
  engine.py            orchestrator + CLI
  core.py              shared typed models (facts, target, ops, plan, journal)
  discovery/           capability & system discovery
  target/              target manifest, profiles, component contracts
  trust/               Stage A: signed index, rotation, artifacts, handoff
  components.py        component contract loader/validator
  adapters.py          signed Rust adapters, registry and sandbox launcher
  fixtures.py          offline host-independent CLI executor
  planner/             DAG planner, typed operations, conflicts
  executor/            transactional executor, primitives, recovery
  validation/          capability and system validators
bootstrap-rust/        std-only Rust Stage A trust root and signed Core handoff
tests/                 unit + integration + idempotency + trust tests
fixtures/              simulated source states (clean Arch, old Sunshine, etc.)
docs/                  architecture, security, testing, threat model
```

## Status

Foundational engine with 117 offline tests, a Rust Stage A bootstrap with signed Core handoff and
chained rotation proof, sandboxed signed Rust adapters, source compatibility profiles,
host-independent fixture CLI and documented break/fix cycles. The next hard steps are the broader
source matrix and live post-migration tamper tests.
See `docs/ARCHITECTURE.md`, `docs/SPEC_ALIGNMENT.md`, `docs/ADAPTERS.md`, `docs/TESTING.md`,
`bootstrap-rust/README.md`, `bootstrap-rust/ROTATION.md` and
`../reports/evolution-engine-breakfix-cycle.md`.
