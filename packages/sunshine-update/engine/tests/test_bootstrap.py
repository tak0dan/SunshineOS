"""Core-side verification of the Rust Stage A report and signed receipt."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.trust import (  # noqa: E402
    StageAReport,
    TrustPolicy,
    canonical_bytes,
    verify_receipt,
)

FP = "AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555"


class BootstrapHandoffTests(unittest.TestCase):
    def setUp(self):
        self.policy = TrustPolicy(
            pinned_roots=(FP,),
            local_protocol=1,
            local_bootstrap_version="1.0.0",
            required_privileged_channel="polkit",
        )
        self.report = StageAReport(
            passed=True,
            trusted_keys=(FP,),
            artifacts_verified=("core",),
            target_release="1.0-test",
            repository_generation=7,
            handoff={"artifact": "core", "protocol": 1, "sha256": "a" * 64},
        )

    def receipt_payload(self, **overrides):
        payload = {
            "bootstrap_version": "1.0.0",
            "protocol": 1,
            "target_release": "1.0-test",
            "repository_generation": 7,
            "core_artifact": "core",
            "core_sha256": "a" * 64,
            "core_signed_by": FP,
            "trusted_keys": [FP],
            "stage_a_digest": hashlib.sha256(
                canonical_bytes(self.report.to_dict())
            ).hexdigest(),
        }
        payload.update(overrides)
        return payload

    def write_receipt(self, directory, payload, signature="good"):
        path = Path(directory) / "receipt.json"
        path.write_text(json.dumps({
            "payload": payload,
            "signature": signature,
            "signed_by": FP,
        }), encoding="utf-8")
        return path

    def verifier(self, fingerprint, payload, signature):  # noqa: ARG002
        return signature == "good" and fingerprint == FP

    def test_report_from_rust_dict_round_trips(self):
        restored = StageAReport.from_dict(self.report.to_dict())
        self.assertEqual(restored, self.report)

    def test_signed_receipt_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_receipt(tmp, self.receipt_payload())
            ok, payload, errors = verify_receipt(path, self.policy, self.verifier, self.report)
            self.assertTrue(ok, errors)
            self.assertEqual(payload["core_artifact"], "core")

    def test_tampered_receipt_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_receipt(tmp, self.receipt_payload(core_sha256="b" * 64))
            ok, _payload, errors = verify_receipt(path, self.policy, self.verifier, self.report)
            self.assertFalse(ok)
            self.assertTrue(any("Core digest" in e for e in errors), errors)

    def test_unsigned_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_receipt(tmp, self.receipt_payload(), signature="")
            ok, _payload, errors = verify_receipt(path, self.policy, self.verifier, self.report)
            self.assertFalse(ok)
            self.assertTrue(any("signature" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
