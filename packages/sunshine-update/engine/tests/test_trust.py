"""Stage A trust-chain tests (protocol-level, no crypto dependency)."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.trust import (  # noqa: E402
    TrustPolicy,
    canonical_bytes,
    gpg_verifier,
    validsig_matches,
    verify_stage_a,
)

OLD = "8253720323C575207CC781B5DB345EF676CCD13D"
NEW = "2FEC611A7F97ED9A37294C90D16F3BE763A4B6BE"
EVIL = "DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"


def sign(fingerprint: str, payload: bytes) -> str:
    """Deterministic stand-in for a real signature, used only by tests."""
    return f"sig:{fingerprint}:{hashlib.sha256(payload).hexdigest()}"


def verifier(fingerprint: str, payload: bytes, signature: str) -> bool:
    return signature == sign(fingerprint, payload)


def index_dict(artifact_digest: str, artifact_sig: str, *, rotation_signer=OLD,
               privileged_channel="polkit", handoff_artifact="core.tar.gz") -> dict:
    rotation_payload = {
        "new_fingerprint": NEW,
        "valid_after": "2026-01-01",
        "revokes": [],
        "reason": "scheduled rotation",
    }
    return {
        "format_version": 1,
        "repository_generation": 7,
        "target": {"release": "sunshine-2026.1"},
        "bootstrap": {
            "minimum_protocol": 1,
            "privileged_channel": privileged_channel,
        },
        "compatibility": {"minimum_core": "1.0.0"},
        "handoff": {
            "artifact": handoff_artifact,
            "entrypoint": "sunshine-core-evolve",
            "protocol": 1,
            "core_version": "5.0.0",
        },
        "key_rotations": [{
            **rotation_payload,
            "signed_by": rotation_signer,
            "signature": sign(rotation_signer, canonical_bytes(rotation_payload)),
        }],
        "artifacts": {
            "core.tar.gz": {
                "path": "core.tar.gz",
                "sha256": artifact_digest,
                "signed_by": OLD,
                "signature": artifact_sig,
            }
        },
    }


class TrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sunshine-trust-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.artifact = self.dir / "core.tar.gz"
        self.artifact.write_bytes(b"verified core artifact\n")
        digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.index = index_dict(digest, sign(OLD, self.artifact.read_bytes()))
        self.policy = TrustPolicy(
            pinned_roots=(OLD,),
            local_protocol=1,
            local_bootstrap_version="1.2.0",
        )

    def write_index(self, data: dict) -> Path:
        payload = dict(data)
        envelope = {
            "payload": payload,
            "signed_by": OLD,
            "signature": sign(OLD, canonical_bytes(payload)),
        }
        path = self.dir / "index.json"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        return path

    def test_valid_chain_rotation_digest_and_handoff(self):
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertTrue(report.passed, report.errors)
        self.assertIn(NEW, report.rotated_keys)
        self.assertEqual(report.artifacts_verified, ("core.tar.gz",))
        self.assertEqual(report.target_release, "sunshine-2026.1")

    def test_future_rotation_date_is_rejected(self):
        payload = {
            "new_fingerprint": NEW,
            "valid_after": "2999-01-01",
            "revokes": [],
            "reason": "future rotation",
        }
        self.index["key_rotations"][0].update({
            **payload,
            "signed_by": OLD,
            "signature": sign(OLD, canonical_bytes(payload)),
        })
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("not effective yet" in e for e in report.errors), report.errors)

    def test_key_downloaded_from_same_server_is_not_trusted(self):
        self.index["key_rotations"][0]["signed_by"] = EVIL
        self.index["key_rotations"][0]["signature"] = sign(
            EVIL, canonical_bytes({
                "new_fingerprint": NEW,
                "valid_after": "2026-01-01",
                "revokes": [],
                "reason": "scheduled rotation",
            })
        )
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("not in the pinned trust chain" in e for e in report.errors))

    def test_self_signed_rotation_is_rejected(self):
        self.index["key_rotations"][0].update({
            "new_fingerprint": EVIL,
            "signed_by": EVIL,
            "signature": sign(EVIL, canonical_bytes({
                "new_fingerprint": EVIL,
                "valid_after": "2026-01-01",
                "revokes": [],
                "reason": "scheduled rotation",
            })),
        })
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("self-signed" in e for e in report.errors))

    def test_artifact_digest_mismatch_blocks_handoff(self):
        self.index["artifacts"]["core.tar.gz"]["sha256"] = "0" * 64
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("digest mismatch" in e for e in report.errors))
        self.assertTrue(any("not verified" in e for e in report.errors))

    def test_missing_privileged_channel_policy_is_enforced(self):
        self.index["bootstrap"]["privileged_channel"] = "broad-sudoers"
        report = verify_stage_a(
            self.write_index(self.index), self.policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("privileged channel" in e for e in report.errors))

    def test_old_bootstrap_is_refused_before_transformation(self):
        policy = TrustPolicy(pinned_roots=(OLD,), local_protocol=0)
        self.index["bootstrap"]["minimum_protocol"] = 1
        report = verify_stage_a(
            self.write_index(self.index), policy, verifier,
            artifact_root=self.dir,
        )
        self.assertFalse(report.passed)
        self.assertTrue(any("bootstrap protocol" in e for e in report.errors))

    def test_tampered_index_signature_fails_closed(self):
        path = self.write_index(self.index)
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["payload"]["target"]["release"] = "evil"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        report = verify_stage_a(path, self.policy, verifier, artifact_root=self.dir)
        self.assertFalse(report.passed)
        self.assertTrue(any("invalid signature" in e for e in report.errors))


class GpgVerifierHardeningTests(unittest.TestCase):
    def test_validsig_matches_signer_field_only(self):
        good = f"[GNUPG:] VALIDSIG {NEW} 2026-11-20 0 1 2 3 4 1 8 00"
        self.assertTrue(validsig_matches(good, NEW))
        wrong_signer = (
            "[GNUPG:] VALIDSIG 1111111111111111111111111111111111111111 "
            f"2026-11-20 {NEW} 1 2 3 4 1 8 00"
        )
        self.assertFalse(validsig_matches(wrong_signer, NEW))
        self.assertFalse(validsig_matches("[GNUPG:] GOODSIG deadbeef", NEW))
        self.assertFalse(validsig_matches("", NEW))

    def test_gpg_verifier_rejects_writable_keyring(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-keyring-test-") as tmp:
            keyring = Path(tmp) / "repository-root.gpg"
            keyring.write_bytes(b"public key")
            os.chmod(keyring, 0o666)
            with self.assertRaises(PermissionError):
                gpg_verifier(keyring)
            os.chmod(keyring, stat.S_IRUSR | stat.S_IWUSR)
            self.assertTrue(callable(gpg_verifier(keyring)))


if __name__ == "__main__":
    unittest.main()
