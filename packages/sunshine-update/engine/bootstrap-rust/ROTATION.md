# Key rotation runbook (Stage A)

## Trust anchors

- The signed `sunshine-update` package ships **only the first root** as the pinned trust root
  (`pinned_roots` in `trust-policy.json`, `repository-root.gpg` keyring). Later roots are never
  added to the shipped policy or promoted by dropping their public keys into the keyring.
- Later roots arrive **inside the signed repository index** as `key_rotations` records. A record is
  `{"new_fingerprint", "valid_after", "revokes", "reason", "signed_by", "signature"}`; the detached
  signature covers only the canonical JSON of the first four fields, and it must be made by a key
  that is already trusted at that point in the chain.
- **Same-server key download is not automatic trust.** A public key fetched from the release
  server, a keyserver, or a CDN is inert until a rotation record signed by an already-trusted key
  promotes it. `test-rotation.sh` deliberately puts the untrusted third key in the keyring and the
  bootstrap still rejects it. A rotated keyring alone is not a rotation.

## Release pipeline order

1. Generate the new key offline; keep its private key off the release server.
2. Publish a rotation record `signed_by` the currently trusted key, with `revokes` naming the old
   key when it is retired. For 2026-11-20 that signer is OLD
   (`8253720323C575207CC781B5DB345EF676CCD13D`).
3. **Sign the rotation (and publish the signed index) before publishing any artifact signed by the
   new key.** Artifacts signed by a key that is not yet in the chain are rejected; the index also
   carries each artifact's SHA-256, and the artifact signature must cover the exact artifact bytes.
4. The bootstrap verifies in this order: index signature (OLD) → rotation chain → artifact digest
   and signature (NEW) → signed Core handoff. Records are processed in array order; a rotation
   signed by a key introduced by a *later* record is rejected.
5. `allow_key_rotation: false` turns any rotation record into a hard failure. Use it only for
   frozen or air-gapped installs that must never learn a new key.
6. `valid_after` is signed and checked against the UTC calendar date by both the Rust bootstrap and
   the Python reference. A future or malformed date is rejected before the key joins the trust chain;
   the release pipeline must still choose the correct effective date.

## Revocation

`revokes` is a list of fingerprints inside the signed rotation payload. When a rotation verifies,
the new key is added and each listed fingerprint is removed from the in-memory trusted set. Artifacts
signed only by the revoked key then fail with `not in the trust chain`. The index that carries the
rotation was verified under the old key *before* the removal, so the handoff can still complete when
Core itself is signed by the new key. Revocation is not a file deletion: trust is recomputed on every
verify from the pinned root plus the signed rotation chain.

## 2026-11-20 rotation (OLD → NEW)

- **OLD:** `8253720323C575207CC781B5DB345EF676CCD13D` — the root pinned by earlier
  `sunshine-update` packages and still listed in both `sunshine-trusted` files as `:4`.
- **NEW:** `2FEC611A7F97ED9A37294C90D16F3BE763A4B6BE` — the RSA-4096 tools key created
  2026-11-20 and installed as `sunshine.gpg`.
- What happened: `sunshine.gpg` was swapped to NEW out-of-band, while `sunshine-trusted` kept only
  OLD and the release repository shipped no OLD-signed rotation record. `sunshine-toolsync` imports
  `sunshine.gpg` directly for tool manifests, so NEW-signed artifacts could not be derived from the
  root an existing install actually trusts. That missing chained document is spec gap G3.
- Correct production form: one rotation record with `new_fingerprint=2FEC…`,
  `signed_by=8253…`, `revokes=["8253720323C575207CC781B5DB345EF676CCD13D"]`, signed by the **OLD**
  private key and published with the index before NEW-signed artifacts. Do not "fix" it by merely
  pinning NEW in a newly built policy: already-installed boxes must be able to reach NEW from the
  root they already have.
- `bootstrap-rust/test-rotation.sh` is the regression proof: OLD signs the index and the rotation,
  NEW signs Core, the policy pins only OLD, and self-signed, untrusted-signer, rotation-disabled
  and unapproved-artifact cases all fail closed.
