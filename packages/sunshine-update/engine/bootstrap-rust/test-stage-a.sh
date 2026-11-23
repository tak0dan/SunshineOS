#!/usr/bin/env bash
# End-to-end Stage A proof: ephemeral GPG key -> signed index/artifact -> Rust bootstrap -> Core receipt.
set -euo pipefail
cd "$(dirname "$0")"
cargo build --release --quiet
BIN=$PWD/target/release/sunshine-bootstrap
S=$(mktemp -d /tmp/sunshine-stage-a.XXXXXX)
trap 'chmod -R u+w "$S" 2>/dev/null || true; rm -rf "$S"' EXIT
[ -z "${SUNSHINE_KEEP_FIXTURE:-}" ] || trap - EXIT
GNUPG="$S/gnupg"; KEYRING="$S/trust.kbx"; INDEX="$S/index.json"; REPORT="$S/report.json"
RECEIPT="$S/receipt.json"; HANDOFF_REPORT="$S/handoff-report.json"; ARGS="$S/core-args"
mkdir -p "$GNUPG"; chmod 700 "$GNUPG"
export GNUPGHOME="$GNUPG"
PREFIX="Sunshine Stage A test <stage-a@example.invalid>"
gpg --batch --yes --passphrase '' --quick-generate-key "$PREFIX" default sign never >/dev/null 2>&1
FP=$(gpg --batch --with-colons --list-secret-keys "$PREFIX" | awk -F: '/^fpr:/ {print $10; exit}')
[ -n "$FP" ] || { echo "could not create test key" >&2; exit 1; }
gpg --batch --yes --export "$FP" > "$S/public.asc"
gpg --no-default-keyring --keyring "$KEYRING" --batch --yes --import "$S/public.asc" >/dev/null 2>&1
chmod 600 "$KEYRING"

cat > "$S/core" <<EOF
#!/bin/sh
printf '%s\n' "\$@" > "$ARGS"
exit 0
EOF
chmod 755 "$S/core"

python3 - "$S" "$FP" <<'PY'
import hashlib, json, os, subprocess, sys
root, fp = sys.argv[1], sys.argv[2]
core = os.path.join(root, "core")
digest = hashlib.sha256(open(core, "rb").read()).hexdigest()
def sign(path):
    sig = path + ".sig"
    subprocess.run([
        "gpg", "--batch", "--yes", "--detach-sign", "--no-armor",
        "--local-user", fp, "--output", sig, path,
    ], check=True, capture_output=True)
    return open(sig, "rb").read().hex()
payload = {
    "format_version": 1,
    "repository_generation": 7,
    "target": {"release": "1.0-stage-a-test"},
    "bootstrap": {"minimum_protocol": 1, "privileged_channel": "polkit"},
    "compatibility": {"minimum_core": "1.0.0"},
    "artifacts": {
        "core": {
            "path": "core",
            "sha256": digest,
            "signature": sign(core),
            "signed_by": fp,
        }
    },
    "handoff": {"artifact": "core", "protocol": 1, "sha256": digest},
    "key_rotations": [],
}
payload_path = os.path.join(root, "payload.json")
with open(payload_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
with open(os.path.join(root, "index.json"), "w", encoding="utf-8") as handle:
    json.dump({
        "payload": payload,
        "signature": sign(payload_path),
        "signed_by": fp,
    }, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
with open(os.path.join(root, "policy.json"), "w", encoding="utf-8") as handle:
    json.dump({
        "pinned_roots": [fp],
        "local_protocol": 1,
        "local_bootstrap_version": "1.0.0",
        "require_artifact_signatures": True,
        "allow_key_rotation": True,
        "required_privileged_channel": "polkit",
        "receipt_signing": {"fingerprint": fp, "gpg_home": os.environ["GNUPGHOME"]},
    }, handle, indent=2)
PY

"$BIN" verify --policy "$S/policy.json" --index "$INDEX" --keyring "$KEYRING" --report "$REPORT"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["passed"]; assert d["artifacts_verified"]==["core"]; print("Rust Stage A verify: OK")' "$REPORT"

"$BIN" handoff --policy "$S/policy.json" --index "$INDEX" --keyring "$KEYRING" \
  --report "$HANDOFF_REPORT" --receipt "$RECEIPT" -- --check
python3 -c 'import sys; a=open(sys.argv[1]).read().split(); assert len(a)==5 and a[0]=="--trust-report" and a[2]=="--trust-receipt" and a[4]=="--check", a; print("signed Core handoff: OK")' "$ARGS"

ENGINE=$(cd .. && pwd)/src/engine.py
python3 "$ENGINE" --fixture clean-arch --check \
  --trust-report "$HANDOFF_REPORT" --trust-receipt "$RECEIPT" \
  --trust-policy "$S/policy.json" --trust-keyring "$KEYRING" >/dev/null
echo "Core receipt verification: OK"

cp "$RECEIPT" "$S/tampered.json"
python3 - "$S/tampered.json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["payload"]["core_sha256"] = "0" * 64
with open(path, "w") as handle:
    json.dump(data, handle, sort_keys=True, separators=(",", ":"))
PY
if python3 "$ENGINE" --fixture clean-arch --check \
  --trust-report "$HANDOFF_REPORT" --trust-receipt "$S/tampered.json" \
  --trust-policy "$S/policy.json" --trust-keyring "$KEYRING" >/dev/null 2>&1; then
  echo "tampered receipt was accepted" >&2
  exit 1
fi
echo "tampered receipt rejected: OK"
