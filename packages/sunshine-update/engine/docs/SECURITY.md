# Security model and threat analysis

## Trust chain

1. The user obtains and installs a genuine, signed `sunshine-update` package through pacman.
   Package authenticity comes from Arch's existing signature trust — not from anything downloaded
   later.
2. That package contains a pinned Sunshine repository trust root (`repository-root.pub`).
3. The bootstrap verifies signed repository metadata before retrieving anything else.
4. The metadata names the current target and required artifacts with digests.
5. Every artifact is hash- and signature-verified before installation or execution.
6. Key rotation is chained: a new key is signed by the previous root, or by an out-of-band
   verified procedure recorded in the repository. **A key is never fetched from the same
   unauthenticated server that serves the code it signs.**

`bootstrap-rust/` enforces the protocol: a downloaded key is only trusted after a rotation record
verifies against an already-trusted key, self-signed rotations are rejected, artifacts must match
signed SHA-256 digests, and the Core handoff must name a verified artifact. Stage A writes a signed
receipt binding the Core digest and Stage A report digest; Core refuses to start without a valid
receipt. Future or malformed `valid_after` dates are rejected before a new key joins the chain.
`src/trust` is the Python reference implementation used by direct `--trust-index` runs.

> Known production gap: the current `sunshine-toolsync` fetches its manifest and signature from
> the same GitHub release and trusts a local GPG keyring file. The 2026-11-20 rotation replaced that
> keyring out-of-band. `bootstrap-rust/ROTATION.md` and `test-rotation.sh` now define and prove the
> chained document the release must publish, but the toolsync release pipeline still needs to ship
> it. The Rust bootstrap supplies the pinned root, but still needs to be packaged as the
> `sunshine-update` entrypoint.

## Privilege model

- Avoid broad sudoers rules. Use narrow, polkit-authorized privileged helpers.
- The bootstrap Critical logic must not depend on Python/Nix/Flatpak/desktop components it is
  supposed to install.
- Components cannot modify the trust root, bypass journaling, or self-authorize privileged
  operations. Typed operations run under the executor's security model; signed Rust adapters may
  extend primitives but remain inside the same authorization and validation boundaries.
- Adapters launch only from a Stage A-validated registry, with a re-check of the artifact digest,
  no shell, no network, an empty capability set, explicit paths and enforced resource limits.

## Threats and mitigations

| Threat | Mitigation |
|--------|------------|
| Malicious repository serves trojaned tools | Detached signature + per-file SHA-256 from signed manifest; path allow-list; rollback refusal |
| Downgrade to vulnerable release | Repository generation monotonicity; version comparison refuses older releases |
| Key substitution | Pinned root in package; chained rotation; keyring updated only out-of-band |
| TOCTOU on downloaded archive | Extract to private temp dir, verify each file before install, use realpath checks, reject symlinks |
| Privilege escalation via component metadata | Metadata signed; operation parameters validated; no arbitrary shell in manifests |
| Malicious or escaped adapter | Signed manifest + artifact, Stage A trust chain, re-check before launch, shell-free systemd-run sandbox, no network, explicit paths, resource limits, journaled invocation |
| Destructive action from bad discovery | Confidence levels; low-confidence observations cannot authorize destructive ops |
| Interrupted transformation corrupts system | Append-only fsynced journal, transaction checkpoints, re-discovery before resume |
| Partial-upgrade breakage | Coherent full-upgrade transactions; refuse partial upgrades |
| Loss of user configuration | Ownership classification; three-way merge; preserve user/system/unknown conservatively |
| Boot failure after kernel migration | Install alongside existing kernel, keep previous entry, validate before committing |
| Reviewed plan executed against mutated machine | `source.observed_fingerprint` mismatch aborts as `stale plan` before any command |
| Contradictory discovery guesses user intent | Distinct bootloader/network/audio signals force one focused decision |
| Fixture/demo leaks real host state | Single injected executor for discovery and execution; live state root refused |

## Fail-closed rules

- Unknown capability → validation failure.
- Missing provider or dependency cycle → plan rejected.
- Invalid/unsigned metadata → abort before any transformation.
- Ambiguous source profile → preflight failure with precise explanation.
- Low-confidence destructive operation → refused.
