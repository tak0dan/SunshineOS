#!/usr/bin/env bash
# Chained key-rotation proof for Rust Stage A (spec gap G3).
# The package pins OLD only; the signed index carries an OLD->NEW rotation;
# the Core artifact is signed by NEW. Four negative cases must fail closed.
set -euo pipefail
cd "$(dirname "$0")"
cargo build --release --quiet
BIN=$PWD/target/release/sunshine-bootstrap
S=$(mktemp -d /tmp/sunshine-rotation.XXXXXX)
trap 'chmod -R u+w "$S" 2>/dev/null || true; rm -rf "$S"' EXIT
[ -z "${SUNSHINE_KEEP_FIXTURE:-}" ] || trap - EXIT

GNUPG="$S/gnupg"; KEYRING="$S/trust.kbx"
mkdir -p "$GNUPG"; chmod 700 "$GNUPG"
export GNUPGHOME="$GNUPG"

new_key() {
  local uid="$1"
  gpg --batch --yes --passphrase '' --quick-generate-key "$uid" default sign never >/dev/null 2>&1
  gpg --batch --with-colons --list-secret-keys "$uid" 2>/dev/null | awk -F: '/^fpr:/ {print $10; exit}'
}
OLD_FP=$(new_key 'Sunshine rotation OLD <rotation-old@example.invalid>')
NEW_FP=$(new_key 'Sunshine rotation NEW <rotation-new@example.invalid>')
THIRD_FP=$(new_key 'Sunshine rotation THIRD <rotation-third@example.invalid>')
for fp in "$OLD_FP" "$NEW_FP" "$THIRD_FP"; do
  gpg --batch --yes --export "$fp" > "$S/$fp.pub"
done
# The two keys the chain actually uses.
gpg --no-default-keyring --keyring "$KEYRING" --batch --yes \
  --import "$S/$OLD_FP.pub" "$S/$NEW_FP.pub" >/dev/null 2>&1
# The third key is also present in the keyring: keyring membership alone is not trust.
gpg --no-default-keyring --keyring "$KEYRING" --batch --yes \
  --import "$S/$THIRD_FP.pub" >/dev/null 2>&1
chmod 600 "$KEYRING"

cat > "$S/core" <<'EOF'
#!/bin/sh
printf '%s\n' "$@"
EOF
chmod 755 "$S/core"

python3 - "$S" "$OLD_FP" "$NEW_FP" "$THIRD_FP" <<'PY'
import hashlib, json, os, subprocess, sys

root, old_fp, new_fp, third_fp = sys.argv[1:5]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign_file(path, fp):
    sig = path + ".sig"
    subprocess.run([
        "gpg", "--batch", "--yes", "--detach-sign", "--no-armor",
        "--local-user", fp, "--output", sig, path,
    ], check=True, capture_output=True)
    with open(sig, "rb") as handle:
        return handle.read().hex()


def sign_value(value, fp, name):
    path = os.path.join(root, name)
    with open(path, "wb") as handle:
        handle.write(canonical(value))
    return sign_file(path, fp)


def write_json(name, value):
    path = os.path.join(root, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return path


with open(os.path.join(root, "core"), "rb") as handle:
    core_bytes = handle.read()
digest = hashlib.sha256(core_bytes).hexdigest()
core_new_sig = sign_file(os.path.join(root, "core"), new_fp)
core_third_sig = sign_file(os.path.join(root, "core"), third_fp)


def rotation(new, signed_by, signer, name, revokes=()):
    # signed_by and signature live outside the canonical signable payload.
    body = {
        "new_fingerprint": new,
        "valid_after": "2026-01-01",
        "revokes": list(revokes),
        "reason": "scheduled rotation",
    }
    record = dict(body)
    record["signed_by"] = signed_by
    record["signature"] = sign_value(body, signer, name)
    return record


rot_ok = rotation(new_fp, old_fp, old_fp, "rotation-ok.body", [old_fp])
rot_self = rotation(new_fp, new_fp, new_fp, "rotation-self.body", [old_fp])
rot_third = rotation(new_fp, third_fp, third_fp, "rotation-third.body", [old_fp])


def payload(rot, artifact_signer, artifact_sig):
    return {
        "format_version": 1,
        "repository_generation": 7,
        "target": {"release": "1.0-rotation-test"},
        "bootstrap": {"minimum_protocol": 1, "privileged_channel": "polkit"},
        "compatibility": {"minimum_core": "1.0.0"},
        "artifacts": {
            "core": {
                "path": "core",
                "sha256": digest,
                "signature": artifact_sig,
                "signed_by": artifact_signer,
            }
        },
        "handoff": {"artifact": "core", "protocol": 1, "sha256": digest},
        "key_rotations": [rot],
    }


def write_index(name, data):
    # Every index is signed by the one pinned root, including negative cases.
    signature = sign_value(data, old_fp, name + ".payload")
    return write_json(name, {"payload": data, "signature": signature, "signed_by": old_fp})


def write_policy(name, allow_rotation):
    return write_json(name, {
        "pinned_roots": [old_fp],
        "local_protocol": 1,
        "local_bootstrap_version": "1.0.0",
        "require_artifact_signatures": True,
        "allow_key_rotation": allow_rotation,
        "required_privileged_channel": "polkit",
        "receipt_signing": {"fingerprint": new_fp, "gpg_home": os.environ["GNUPGHOME"]},
    })


write_index("index.json", payload(rot_ok, new_fp, core_new_sig))
write_index("index-self.json", payload(rot_self, new_fp, core_new_sig))
write_index("index-third.json", payload(rot_third, new_fp, core_new_sig))
write_index("index-unapproved.json", payload(rot_ok, third_fp, core_third_sig))
write_policy("policy.json", True)
write_policy("policy-no-rotation.json", False)
PY

expect_failure() {
  local report="$1" expected="$2" label="$3"
  python3 - "$report" "$expected" "$label" <<'PY'
import json, sys
report, expected, label = sys.argv[1:4]
data = json.load(open(report))
assert data["passed"] is False, (label, "unexpected pass")
assert any(expected in error for error in data["errors"]), (label, data["errors"])
print(label + ": OK")
PY
}

"$BIN" verify --policy "$S/policy.json" --index "$S/index.json" \
  --keyring "$KEYRING" --report "$S/report.json" >/dev/null
python3 - "$S/report.json" "$NEW_FP" <<'PY'
import json, sys
data, new = json.load(open(sys.argv[1])), sys.argv[2]
assert data["passed"] is True, data.get("errors")
assert new in data["rotated_keys"], data["rotated_keys"]
assert new in data["trusted_keys"], data["trusted_keys"]
assert data["artifacts_verified"] == ["core"], data["artifacts_verified"]
print("chained rotation verify: OK")
PY

if "$BIN" verify --policy "$S/policy.json" --index "$S/index-self.json" \
  --keyring "$KEYRING" --report "$S/self-report.json" >/dev/null 2>&1; then
  echo "self-signed rotation was accepted" >&2; exit 1
fi
expect_failure "$S/self-report.json" "self-signed" "self-signed rotation rejected"

if "$BIN" verify --policy "$S/policy.json" --index "$S/index-third.json" \
  --keyring "$KEYRING" --report "$S/third-report.json" >/dev/null 2>&1; then
  echo "untrusted rotation signer was accepted" >&2; exit 1
fi
expect_failure "$S/third-report.json" \
  "signer $THIRD_FP is not in the pinned trust chain" "untrusted rotation signer rejected"

if "$BIN" verify --policy "$S/policy-no-rotation.json" --index "$S/index.json" \
  --keyring "$KEYRING" --report "$S/no-rotation-report.json" >/dev/null 2>&1; then
  echo "rotation was accepted with allow_key_rotation=false" >&2; exit 1
fi
expect_failure "$S/no-rotation-report.json" \
  "key rotation present but disabled by trust policy" "rotation-disabled policy rejected"

if "$BIN" verify --policy "$S/policy.json" --index "$S/index-unapproved.json" \
  --keyring "$KEYRING" --report "$S/unapproved-report.json" >/dev/null 2>&1; then
  echo "unapproved artifact signer was accepted" >&2; exit 1
fi
expect_failure "$S/unapproved-report.json" \
  "artifact core: signer $THIRD_FP is not in the trust chain" "unapproved artifact signer rejected"
