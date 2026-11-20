# Engine packaging notes

The vendored engine is the canonical implementation published in
`tak0dan/SunshineOS_Development-Testing` under `evolution-engine/`. Packaging
must not fork it: copy the tree verbatim, build the Rust bootstrap from the
vendored source, and sign only the small Core wrapper in `trust/core`.

Two host-level hardening fixes are included in this package and mirrored in the
canonical engine:

- `bootstrap-rust/src/gpg.rs` and `src/trust/model.py` set an empty `GNUPGHOME`
  for detached verification so keyboxd configuration cannot make `--keyring`
  be ignored. Both also require a `VALIDSIG` line naming the declared signer.
- The receipt signing key is checked at wrapper startup; a missing key is a hard
  failure rather than a silent fallback to an unsigned handoff.

The signed index has `key_rotations: []` and `allow_key_rotation: false` because
the production OLD private key is unavailable. Existing OLD-pinned installs need
the chained OLD-signed rotation described in `ROTATION.md` before they can use
NEW-signed artifacts. Fresh installs can verify this index immediately.
