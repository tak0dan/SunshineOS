# Baseline epoch: Arch Linux 2026

Identifier: `arch-2026-baseline-01`
Implementation: `evolution-engine/src/evolution/baseline.py::ARCH_2026_BASELINE`
Role: milestone 0, the frozen Arch reference point from which SunshineOS evolution
is measured. It is not a floating "latest Arch" target and not an image the
engine boots.

## Why this exists

A migration that only understands today's Arch installer will rot. The engine
therefore preserves the *knowledge* needed to interpret a 2026 Arch installation:
package state, repository state, configuration ownership, installation procedure,
and a content-addressed archive of the ISO and manifests. Twenty years later the
engine observes the machine, resolves a desired target, and replays semantic
transitions from this frozen epoch instead of guessing from a release number.

## Identity assumptions

- Distribution family: Arch Linux, `ID=arch` or a nearly pure derivative with a
  compatible pacman database.
- Architecture: `x86_64` for the published baseline; other architectures require a
  new qualified baseline epoch.
- Init: systemd.
- Package manager: pacman, with a reconstructable `core`/`extra`/`multilib`
  repository set.
- Kernel preset: real `linux`, never the fictional `2026.1`.
- Boot: GRUB or systemd-boot are first-class; other bootloaders are assessment
  only until qualified.
- Filesystem: btrfs or ext4 (including LUKS-backed ext4) are qualified shapes.

The engine does not assume these from a label. They are discovered into
`Inventory` by `evolution-engine/src/evolution/inventory.py::from_observed` and
classified by `CompatibilityEngine.classify`.

## Required evidence

A baseline epoch is valid only when all of these are present:

1. `iso_name`, `iso_sha256`, `iso_signature` and `manifest_digest`.
2. `archived_at` and a preserved `installation_procedure`.
3. Non-empty `package_state` and `configuration_state`.
4. Artifacts registered in the content-addressed archive.
5. A successful `verify_iso()` against the archived ISO.

`ARCH_2026_BASELINE` currently has empty digest/signature fields on purpose. That
makes `verify_iso()` fail closed until the release archive pipeline freezes the
epoch. The audit ISO currently on hand is a *SunshineOS* release, not the vanilla
Arch baseline, and must not be substituted:

- `SunshineOS_13.4.7.1.6_Release_2026-11-19.iso`
- SHA-256 `fca813a623eada74a2f15ff5295082c87eae37fd014016c1c6f90bd01d453a97`

## Freeze procedure

```sh
# In the release archive pipeline, after obtaining the canonical Arch 2026 ISO:
sha256sum archlinux-2026.01.01-x86_64.iso
gpg --detach-sign --armor archlinux-2026.01.01-x86_64.iso
# Store those values plus the manifest digest in a NEW epoch; never mutate
# arch-2026-baseline-01. replace_baseline() enforces a new epoch id.
```

The new epoch must then be re-qualified through the release gate in
`evolution-engine/src/evolution/qualification.py`. An edited old epoch is not a
valid baseline.

## Recovery lineage

The recovery path is deliberately independent of the primary migration:

```
B-1 (Arch 2015) -> M bridge -> B0 (Arch 2026) -> target evolution
```

- `B-1`: an older Arch installation that predates the frozen epoch.
- `M bridge`: semantic transitions that interpret historical package, boot and
  configuration shapes without executing old installer scripts.
- `B0`: this frozen Arch 2026 baseline.
- `target`: the resolved SunshineOS desired state for the chosen milestone.

Implementation: `evolution-engine/src/evolution/recovery.py`, specifically
`recovery_path()`, `RecoveryBridge`, `reconstruction_spec()` and
`qualification_from_results()`. A bridge without independent toolchain,
artifact manifest hash, supported conditions and qualification fails validation.

## Operator invariants

- Discovery is repeatable and read-only.
- A plan is bound to an inventory hash; a stale plan is refused.
- Any apply is preceded by a checkpoint and followed by `--verify`.
- Failure runs `on_failure` hooks and restores the checkpoint.
- User data is preserved by a separate `DataPreservationPlan`; OS reconstruction
  never treats `/home` as disposable.
- Tampering with snapshots, sealed state, signed manifests or checkpoints fails
  closed.
