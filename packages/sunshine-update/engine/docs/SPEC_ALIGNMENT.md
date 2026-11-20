# Alignment with `TODO/TODO_Migration.md`

This document maps the remote architecture specification to the current prototype. It is
intentionally blunt about what is implemented, what is specified but not production-hardened,
and what remains a real gap.

## Summary

| Spec area | Status here | Notes |
|-----------|-------------|-------|
| §1 Target-state construction | Implemented | `src/target/current.toml`, resolver, capability planner. No release-version branching. |
| §2 Bootstrap package `sunshine-update` | Bootstrap implemented | `bootstrap-rust/` is the trust-root executable; packaging stays in `SunshineOS`. |
| §2.2 Pinned trust root | Implemented | `bootstrap-rust` and `src/trust` accept only pinned roots and refuse unsigned metadata. |
| §2.3 Upgradeable bootstrap/handoff | Implemented | Compatibility checks, verified Core artifact, signed receipt and `exec()` handoff. |
| §3 Stage B discovery | Implemented | Typed observations with confidence/evidence, including users/groups/home directories without secrets. |
| §3 Stage C resolution | Implemented | Automatic single-profile selection; one focused question for ambiguity or conflict. |
| §3 Stage D / §4 planning | Implemented | DAG, typed operations, dependency/conflict checks, full-upgrade rule. |
| §4.3 Typed operations | Implemented | No arbitrary shell in plans; adapters are the only extension point. |
| §5 Component lifecycle | Implemented | Introduce/evolve/replace/reconfigure/retire decisions from observed vs target capability state. |
| §5.1 Component contracts | Implemented | `src/target/contracts/*.toml`, validated against the published target on every apply. |
| §6 Arch foundation | Implemented | Pacman authority, foreign-package uncertainty, managed repository fragments, rollback refusal. |
| §7 Kernel/boot | Implemented | Separate kernel, initramfs and boot-entry operations; checkpoints required before boot work. |
| §8 Configuration ownership | Implemented | Three-way merge, ownership registry, non-destructive fresh-install assignment. |
| §9 Execution/journal | Implemented | Append-only fsynced journal, transaction groups, actual-state reconciliation on resume. |
| §9.4 Reconciliation after interruption | Implemented | Journal entries are hints; probes decide what can be skipped. |
| §11 Repository generations | Implemented in planner | Monotonic generation, no silent rollback, coherent `pacman -Syu`. |
| §13.1 Component bundles | Implemented as data | Profiles and component contracts are versioned TOML; adapters are separate signed units. |
| §13.2 Signed adapters | Implemented | Signed manifest and artifact, narrow permissions, typed parameters, systemd-run sandbox, resource limits, journaled invocations. |
| §14 Source-profile limits | Implemented | `arch-standard`, `arch-customized`, `sunshine-installed`, `unsupported`; apply exits 3 for unsupported. |
| §16 Recommended structure | Implemented | Python Core mirrors the module boundaries; `bootstrap-rust/` is the small std-only Rust entrypoint. |

## Detailed gap register

### G1 — CLOSED: Rust bootstrap is now the trust root

`bootstrap-rust/` builds `sunshine-bootstrap`, a std-only Rust binary (SHA-256, canonical JSON,
GPG verification through the system `gpg`). It verifies the signed index, chained rotations,
artifact digests and Core handoff before any transformation. It does not import Python, Nix,
Flatpak or desktop components. `cargo test` and `test-stage-a.sh` prove the flow end to end.

**Remaining hardening:** the binary is dynamically linked; a fully static musl build and a
packaged `sunshine-update` wrapper are deployment work in `SunshineOS`, not an architecture gap.

### G2 — CLOSED: handoff is executed and receipt-verified

`verify` writes a Stage A report. `handoff` writes a signed receipt binding bootstrap version,
Core artifact name/digest, protocol, target release, repository generation and the Stage A report
digest, then `exec()`s the verified Core artifact with `--trust-report` and `--trust-receipt`.
Core verifies the receipt signature and every binding field before discovery or mutation.

**Remaining hardening:** the receipt signing key must be provisioned as a root-only, narrow
machine key by the package/installer. The test fixture uses an ephemeral GPG key; production
key custody is documented in `bootstrap-rust/README.md`.

### G3 — CLOSED: chained rotation is specified, tested and dated

`bootstrap-rust/test-rotation.sh` proves that a package pinning only OLD can follow a rotation signed
by OLD to an artifact signed by NEW. A third key present in the keyring but absent from the signed
chain is rejected, as are self-signed rotations, rotation-disabled policies and unapproved artifact
signers. Future or malformed `valid_after` dates are now rejected by both Rust and Python. See
`bootstrap-rust/ROTATION.md` for the release-pipeline order and the 2026-11-20 rotation record that
must be published for already-installed systems.

**Remaining hardening:** the existing `sunshine-tools` release must actually publish that rotation
document; the protocol and proof now exist, but the old toolsync deployment still needs the
pipeline change described in `docs/SECURITY.md`.

### G4 — CLOSED: adapters run in a verified sandbox

`src/adapters.py` now verifies a signed manifest and artifact, rechecks the artifact immediately
before launch, constrains filesystem paths to the declared permissions, and builds a shell-free
`systemd-run --scope` command with `ProtectSystem=strict`, no capabilities, no network, explicit
read/write paths and CPU/memory/process/time limits. `src/executor/adapter_ops.py` routes adapter
operations only through a validated registry and records the invocation in the journal on success
and failure. See `docs/ADAPTERS.md`.

**Remaining hardening:** the systemd properties are a strong process sandbox, not a formal
seccomp/landlock profile. A future deployment can add a narrow seccomp filter without changing the
manifest contract.

### G5 — CLOSED: source matrix with explicit expected plans

`tests/source-matrix.toml` names each machine shape and its expected convergence: btrfs, ext4,
LUKS, GRUB, systemd-boot, NVIDIA/DKMS and mixed AUR, plus aged Arch and old Sunshine. Two new
fixtures model ext4-on-LUKS with systemd-boot and btrfs with NVIDIA/DKMS/AUR packages. Each case
asserts discovery shape, source profile, required/forbidden operations, preserved foreign packages,
LUKS checkpoint intent, successful apply and idempotency. `./test-source-matrix.sh` runs the CI proof.

Capability-based provider selection keeps `btrfs-progs` off ext4 roots and `os-prober` off
systemd-boot systems, while requiring `cryptsetup` and a LUKS header/`crypttab` checkpoint on
encrypted roots. This is one resolver path for every source, not a source-specific branch.

### G6 — CLOSED: post-migration verification and tamper detection

Fixture apply materializes the source tree into the sandbox and records its origin, so
`--verify --fixture NAME --state-root PATH` probes the **migrated** filesystem rather than the
pristine fixture. `--verify` now emits structured JSON reports (not Python repr strings), probes
active network/audio choices, and validates only activated components. `./test-post-migration.sh`
proves verification passes after apply and that tampering with every managed capability — including
command-backed ones via sandbox tamper markers — fails verification and names the capability.

**Live VM proof:** on `SunshineOS-Audit` a root apply of the same implementation completed 21
operations with no errors, generated its own fallback initramfs, and `--verify` passed 18 of 18
capabilities on the real migrated system. A second apply was a no-op (`changed False`), and
removing `migration/checkpoints` made verification fail with `recovery-checkpoints` before being
restored to a clean pass. There is now one implementation for fixture and live execution:
`ExecutionContext.fs_root` is the sandbox for injected executors and the real `/` for a live apply,
while journal/checkpoints/ownership remain in `state_root`.

**Remaining deployment work:** packaging the Rust bootstrap as the actual `sunshine-update` entry
point and signing repository artifacts; no protocol or convergence gap remains.

## Implemented safeguards that answer earlier gaps

- `src/fixtures.py` routes both discovery and execution through one injected executor. CLI
  fixture mode can no longer mix fake filesystem state with real host command output.
- `--fixture ... --apply` refuses the live `/var/lib/sunshine` state root; an explicit sandbox is
  mandatory.
- A plan carries `source.observed_fingerprint`. If current discovery differs, execution aborts
  before any command (`stale plan`).
- Conflicting observations for bootloader/network/audio produce one user decision instead of a
  silent first-match guess. PipeWire's Pulse compatibility layer no longer looks like a second
  audio daemon.
- A selected desktop profile can no longer add its own capabilities as prerequisites, which used
  to create a `desktop_integration` dependency cycle.
- Repeated CLI apply is proven idempotent with a persistent fixture sandbox.
- Trust failures block check/plan/apply/verify before discovery or execution starts.
- The Rust bootstrap's signed receipt is re-verified by Core, including a digest of the exact
  Stage A report; tampering with either file is rejected.
- Component contracts and adapter manifests are validated as data, not trusted implicitly.
- Signed adapters are verified twice, launched without a shell under resource limits, and journaled.
- Future or malformed key-rotation effective dates are rejected before a key enters the trust chain.
- Recovery/boot tooling is chosen from observed storage and bootloader capabilities.
- `--verify` probes the migrated state, only checks activated components, and detects tampering
  with every managed capability.

## Continuous-loop position

The loop is currently at: **implement → test → break → repair → document → restart with a harder
scenario**. Cycles 12–34 are recorded in `../reports/evolution-engine-breakfix-cycle.md`.
All six architecture gaps G1–G6 are closed, and cycles 29–34 closed the gap between offline proof
and a real GUI-VM apply/verify/tamper run. The next hard scenario is packaging the Rust bootstrap as
the real `sunshine-update` entrypoint, publishing the chained rotation document and repeating the
full loop against that published package rather than the source tree.
