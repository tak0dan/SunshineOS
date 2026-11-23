# Sunshine Evolution Engine — Architecture

## Formal definition

> **Sunshine Evolution Engine** — a repository-driven, target-state transformation and
> reconciliation system responsible for evolving supported Arch Linux installations and existing
> Sunshine OS installations into the currently published Sunshine OS architecture.
>
> The engine discovers the installed system, resolves the current target, calculates the required
> component transformations, executes them through validated operations and commits the resulting
> system state.
>
> It supports introduction, evolution, replacement, reconfiguration and retirement of components
> independently of Sunshine release history. It preserves the Arch foundation and delegates
> standard package management to pacman.

## The central decision

**Migrations depend on what the machine currently is, not which Sunshine version it came from.**

This gives one engine for both:

- `Old Sunshine OS → Current Sunshine OS`
- `Pure Arch Linux → Current Sunshine OS`

## Three separated data models

| Model | Meaning | Lifecycle |
|-------|---------|-----------|
| Observed state | Factual inventory of the machine | Rebuilt on every run |
| Desired state | Versioned target specification | Published in the repository |
| Transformation state | Generated execution plan | Created per run, journaled |

They are never combined into one configuration file. They have different trust requirements and
lifecycles.

## Pipeline stages

### A — Bootstrap and trust verification
`bootstrap-rust/` is the small std-only trust root. It verifies repository signatures, artifact
hashes, chained key rotation, protocol compatibility and the signed Core handoff. It writes a
signed receipt and `exec()`s the verified Core with `--trust-report` and `--trust-receipt`. Core
re-verifies the receipt before discovery or mutation. `src/trust` keeps a Python reference
implementation for tests and direct `--trust-index` runs. See `SPEC_ALIGNMENT.md` and
`bootstrap-rust/README.md`.

### B — Discovery
Inspect distribution, packages, kernel, boot, storage, services, network, audio, desktop, users,
existing Sunshine components. Every observation carries confidence and evidence. A GRUB package
alone is MEDIUM confidence; an EFI boot entry plus configuration is HIGH. Low confidence never
authorizes destructive operations.

### C — Target resolution
Load the versioned target manifest. Choose desktop profile. Preserve compatible existing choices
(bootloader, desktop, network, audio). Ask the user only when intent cannot be safely determined.

### D — Planning
Compute missing/outdated capabilities. Build a DAG of typed operations. Detect cycles, conflicts
and missing providers. Add checkpoints before destructive operations. The planner never branches
on release versions; it compares observed state to target state.

### E — Execution
Topological execution in transaction groups, each with preflight, checkpoint, journal, validation
and commit condition. The journal is append-only and fsynced. After interruption the engine
re-discovers the machine and reconciles journal intent with actual state before resuming.

### F — Validation
Capabilities are validated with active probes, not package presence alone. Unknown capabilities
fail closed.

## Component lifecycle

| Operation | Meaning |
|-----------|---------|
| Introduce | Component absent → install and initialize |
| Evolve | Schema/capability outdated |
| Replace | Swap implementation, preserve contract |
| Reconfigure | Current component, wrong configuration |
| Retire | Remove safely after data migration |

## Typed operations

`InstallPackages`, `RemovePackages`, `TransferOwnership`, `CreateConfiguration`,
`MigrateConfiguration`, `RegisterComponent`, `EnableService`, `DisableService`, `InstallKernel`,
`GenerateInitramfs`, `InstallBootEntry`, `CreateCheckpoint`, `ValidateCapability`.

Migration manifests never contain arbitrary shell scripts. Complex cases use versioned signed
Rust adapters running under the executor's authorization, journaling and validation model.
`src/adapters.py` verifies the manifest and artifact signatures, rejects forbidden permissions and
parameter keys that could smuggle a shell command, and launches through a shell-free `systemd-run`
scope with explicit paths, no network and CPU/memory/process/time limits. Every invocation is
journaled. See `docs/ADAPTERS.md`.

Component contracts in `src/target/contracts/*.toml` declare capabilities, dependencies, managed
paths and lifecycle. They are validated against the published target before every apply, so the
planner never relies on a component's internals.

## Arch foundation rules

- Pacman remains the authority. No second package manager.
- A coherent full-upgrade (`pacman -Syu`) is used when repository databases change — partial
  upgrades are refused.
- Foreign/AUR packages are classified with uncertainty, never auto-removed.
- Sunshine repository config uses managed fragments; user repos, mirrors, signature settings and
  custom options are preserved. Blockers are reported, not silently deleted.
- Kernel package migration, kernel management migration and boot integration migration are
  separate components with separate schemas.

## Configuration ownership

Four categories: Sunshine-owned (auto-migrate), system-owned (explicit adapters), user-owned
(preserve), unknown (conservative). Three-way merge (old default, user current, new default)
preserves user changes and asks only on conflict.

## Security invariants

1. Trust root is pinned in the bootstrap package; keys are never fetched from the same
   unauthenticated server that serves the code.
2. Key rotation follows a verifiable chain from the previous root.
3. Every downloaded artifact is hash- and signature-verified before execution.
4. Privileged operations are narrow, authorized, journaled and validated.
5. Low-confidence observations cannot authorize destructive operations.
6. The executor, not components, controls authorization and journaling.

## Supported source profiles

A five-year guarantee applies to **supported source profiles and supported Sunshine states**, not
arbitrary Linux systems. Clean Arch with systemd/pacman/supported bootloader/filesystem is the
primary conversion target. Customized Arch is conditional. Unsupported arrangements fail preflight
with a precise explanation.

## Idempotency

Running the engine twice against an unchanged target must produce no mutating operations — only
validation. This is a fundamental property and is covered by tests, including a CLI-level
two-apply fixture test with a persistent sandbox.

## Stale-plan protection

A plan contains a fingerprint of the state it was built from. If discovery changes before
execution, the engine aborts with `stale plan` and runs no command. This closes the gap between
a reviewed plan and a mutated machine.

## Host-independent fixtures

`--fixture NAME` swaps both the filesystem root and the command executor. It never calls the host
`subprocess`, never uses the live `/var/lib/sunshine` state root, and unknown commands fail closed.
This makes test and demo output reproducible on any machine.
