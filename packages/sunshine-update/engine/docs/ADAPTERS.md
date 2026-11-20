# Signed Rust adapter runtime

Adapters are the only extension point for privileged operations that cannot be expressed as a
built-in typed primitive. They are not plugins: the engine never imports adapter code into Core and
never runs a shell on its behalf.

## Manifest example

```toml
id = "recovery-adapter"
component = "recovery"
version = "1.0.0"
runtime = "rust"
operation = "MigrateConfiguration"
permissions = ["read-configuration", "write-managed-configuration"]
parameters = ["source_path", "target_path"]
provides = ["recovery-checkpoints"]

[artifact]
name = "recovery-adapter"
path = "recovery-adapter"
sha256 = "<signed SHA-256>"

[schema]
from = 1
to = 3

[signature]
manifest = "<hex detached signature of the canonical manifest payload>"
manifest_signed_by = "<trusted fingerprint>"
artifact = "<hex detached signature of the exact artifact bytes>"
artifact_signed_by = "<trusted fingerprint>"

[sandbox]
memory_mb = 64
cpu_percent = 25
timeout_seconds = 30
max_processes = 32
network = false
read_paths = ["/etc/sunshine"]
write_paths = ["/etc/sunshine/managed"]
```

The manifest signature covers everything except the two signatures and signer fields. The artifact
signature covers the exact binary bytes. Both signers must be in the Stage A trust chain, and the
artifact name must appear in `artifacts_verified` in the Stage A report. Registration verifies the
digest and signature; `verify_invocation()` repeats the check immediately before launch.

## Permission model

`permissions` is a capability allowlist, not decoration. Each declared `read_paths` or `write_paths`
entry must sit under a root authorized by one of the declared permissions. For example,
`write-boot-entry` authorizes only `/boot/loader/entries` and `/boot/EFI`; it does not authorize
writing `/etc`. Forbidden permissions include `modify-trust-root`, `write-sudoers`,
`disable-validation`, `execute-arbitrary-shell` and `bypass-migration-journal`.

Parameters are equally narrow: only keys listed in `parameters` are accepted, and shell/ trust
escape keys such as `command`, `script`, `sudoers` and `trust_root` are always refused. Values are
size-limited and NUL-free.

## Launch boundary

Production launches use `systemd-run --scope` with a shell-free argv:

- `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`
- kernel/control-group/SUID/realtime restrictions and an empty capability bounding set
- `RestrictAddressFamilies=AF_UNIX`; network access is never allowed
- explicit `ReadOnlyPaths` and `ReadWritePaths` from the signed manifest
- `MemoryMax`, `CPUQuota`, `TasksMax` and `RuntimeMaxSec` limits
- parameters passed as one canonical JSON argument after `--sunshine-adapter-params`

The launcher refuses to run unless it is root. Tests inject a launcher callable, so fixture mode
never touches the host systemd or a real adapter binary.

## Journal contract

Every invocation writes an `adapter` object into the journal entry for its typed operation:
invocation ID, adapter ID/version, artifact digest, permission list, sandbox declaration and the
names of supplied parameters. Both successful and failed launches are recorded. A plan that names an
`adapter_id` without an active validated registry is refused before any process starts.

## CLI

```bash
sunshine-evolve --apply \
  --trust-index /var/lib/sunshine/trust/index.json \
  --trust-policy /usr/share/sunshine/trust/trust-policy.json \
  --trust-keyring /usr/share/sunshine/trust/repository-root.gpg \
  --adapter-dir /usr/lib/sunshine/adapters/manifests \
  --adapter-artifact-root /usr/lib/sunshine/adapters/bin
```

`--adapter-dir` is inactive unless Stage A verification passed. Artifacts default to the Stage A
index/report directory when `--adapter-artifact-root` is omitted.
