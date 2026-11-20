#!/usr/bin/env bash
# Regenerate the signed Stage A trust material for sunshine-update.
#
# Usage:
#   GNUPGHOME=/secure/gnupghome SUNSHINE_SIGNING_FP=2FEC... \
#     tools/provision-stage-a.sh [package-root]
#
# The private signing key must be supplied by the release operator. This script
# never writes a private key into the package tree; it only signs the public
# index/artifact and exports the public keyring.
set -euo pipefail
ROOT=${1:-$(cd "$(dirname "$0")/.." && pwd)}
FP=${SUNSHINE_SIGNING_FP:-}
[ -n "$FP" ] || { echo "SUNSHINE_SIGNING_FP is required" >&2; exit 2; }
command -v gpg >/dev/null || { echo "gpg is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 2; }
[ -f "$ROOT/trust/core" ] || { echo "missing signed core wrapper: $ROOT/trust/core" >&2; exit 2; }
chmod 755 "$ROOT/trust/core"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
sign_hex() { # path -> prints lowercase hex detached signature
  local target=$1 sig="$TMP/sig"
  rm -f "$sig"
  gpg --batch --yes --detach-sign --no-armor --local-user "$FP" --output "$sig" "$target"
  od -An -tx1 -v "$sig" | tr -d ' \n'
}

python3 - "$ROOT" "$FP" "$TMP" <<'PY'
import hashlib, json, os, subprocess, sys
root, fp, tmp = sys.argv[1], sys.argv[2], sys.argv[3]
core = os.path.join(root, "trust", "core")
digest = hashlib.sha256(open(core, "rb").read()).hexdigest()

def sign(data: bytes) -> str:
    payload = os.path.join(tmp, "payload.bin")
    signature = os.path.join(tmp, "payload.sig")
    with open(payload, "wb") as handle:
        handle.write(data)
    subprocess.run([
        "gpg", "--batch", "--yes", "--detach-sign", "--no-armor",
        "--local-user", fp, "--output", signature, payload,
    ], check=True)
    return open(signature, "rb").read().hex()

artifact_sig = sign(open(core, "rb").read())
payload = {
    "format_version": 1,
    "repository_generation": 1,
    "target": {"release": "sunshine-2026.11"},
    "bootstrap": {"minimum_protocol": 1, "privileged_channel": "polkit"},
    "compatibility": {"minimum_core": "1.2.0"},
    "artifacts": {
        "core": {
            "path": "core",
            "sha256": digest,
            "signature": artifact_sig,
            "signed_by": fp,
        }
    },
    "handoff": {"artifact": "core", "protocol": 1, "sha256": digest},
    "key_rotations": [],
}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
with open(os.path.join(root, "trust", "payload.json"), "wb") as handle:
    handle.write(canonical + b"\n")
envelope = {
    "payload": payload,
    "signature": sign(canonical),
    "signed_by": fp,
}
with open(os.path.join(root, "trust", "index.json"), "w", encoding="utf-8") as handle:
    json.dump(envelope, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    handle.write("\n")
policy = {
    "pinned_roots": [fp],
    "local_protocol": 1,
    "local_bootstrap_version": "1.2.0",
    "require_artifact_signatures": True,
    "allow_key_rotation": False,
    "required_privileged_channel": "polkit",
    "receipt_signing": {
        "fingerprint": fp,
        "gpg_home": "/etc/sunshine/trust/receipt-home",
    },
}
with open(os.path.join(root, "trust", "trust-policy.json"), "w", encoding="utf-8") as handle:
    json.dump(policy, handle, indent=2)
    handle.write("\n")
PY

gpg --batch --yes --export "$FP" > "$TMP/public.asc"
gpg --no-default-keyring --keyring "$ROOT/trust/repository-root.gpg" --batch --yes --import "$TMP/public.asc" >/dev/null 2>&1
chmod 644 "$ROOT/trust/repository-root.gpg" "$ROOT/trust/index.json" "$ROOT/trust/payload.json" "$ROOT/trust/trust-policy.json"
chmod 755 "$ROOT/trust/core"
echo "Stage A material signed by $FP"
