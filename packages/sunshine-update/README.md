# sunshine-update

Dedicated package for the Sunshine evolutionary migration system. It installs:

- the Python Core (`/usr/share/sunshine/evolution`),
- the small Rust Stage A verifier (`/usr/lib/sunshine/evolution/sunshine-bootstrap`),
- the signed trust index and pinned public keyring (`/usr/share/sunshine/trust`),
- a privileged wrapper (`sunshine-evolution`) that uses polkit, not a broad sudoers rule.

## Runtime chain

`sunshine-evolution` → Rust Stage A verify → signed receipt → verified Core wrapper → evolution engine.

Stage A refuses to hand off tampered artifacts, unsigned or untrusted keys, a wrong privileged channel,
a stale bootstrap, or an invalid receipt. Core independently re-verifies the receipt against the same
policy and keyring.

## Key custody (required before first use)

The package ships **public trust material only**. A root-owned receipt signing key must be provisioned
out of band:

```bash
install -d -m 0700 /etc/sunshine/trust/receipt-home
GNUPGHOME=/etc/sunshine/trust/receipt-home gpg --batch --import /secure/path/private-key.asc
chmod 0700 /etc/sunshine/trust/receipt-home
systemd-tmpfiles --create /usr/lib/tmpfiles.d/sunshine-evolution.conf
```

The fingerprint in `trust/trust-policy.json` must match the installed private key.
`sunshine-evolution` checks this at startup and fails closed when it is missing.

## 2026-11-20 rotation status

The shipped index pins the NEW key `2FEC611A7F97ED9A37294C90D16F3BE763A4B6BE` for **fresh** installs.
Older installs pin OLD `8253720323C575207CC781B5DB345EF676CCD13D`. Reaching NEW from those installs
requires a rotation record signed by the **OLD private key**, as specified in
`engine/bootstrap-rust/ROTATION.md`. That private key is not available in this workspace, so no
production OLD→NEW rotation record is shipped. Do not work around it by re-pinning NEW: that would
leave existing installations unable to validate the chain. The regression proof with ephemeral keys
is `engine/bootstrap-rust/test-rotation.sh`.

## Regression checks

```bash
cd engine && python3 -m unittest discover -s tests -v
cd engine/bootstrap-rust && cargo test --offline --locked && ./test-stage-a.sh && ./test-rotation.sh
```

`tools/provision-stage-a.sh` regenerates the signed material when the signing key and rotation
policy are available. It never writes private key material into the package tree.
