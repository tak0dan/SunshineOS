"""CLI-level tests: fixture mode must never read host command state."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import cmd_apply, main  # noqa: E402
from src.trust import StageAReport  # noqa: E402


def run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def parse_json(text: str) -> dict:
    start = text.index("{")
    return json.loads(text[start:])


class CliFixtureTests(unittest.TestCase):
    def test_check_uses_fixture_distribution_not_host(self):
        code, out, err = run_cli("--fixture", "clean-arch", "--check")
        self.assertEqual(code, 0, err)
        report = parse_json(out)
        self.assertEqual(report["observed"]["distribution"], "arch")
        self.assertEqual(report["source_compatibility"]["profile"], "arch-standard")
        self.assertEqual([u["name"] for u in report["observed"]["users"]], ["sunshine"])

    def test_old_sunshine_fixture_uses_same_cli(self):
        code, out, err = run_cli("--fixture", "old-sunshine", "--check")
        self.assertEqual(code, 0, err)
        report = parse_json(out)
        self.assertEqual(report["observed"]["distribution"], "sunshineos")
        self.assertEqual(report["source_compatibility"]["profile"], "sunshine-installed")

    def test_plan_is_faithful_without_host_subprocess_leakage(self):
        code, out, err = run_cli("--fixture", "arch-hyprland", "--plan")
        self.assertEqual(code, 0, err)
        plan = parse_json(out)
        self.assertEqual(plan["source"]["distribution"], "arch")
        self.assertGreater(len(plan["operations"]), 0)

    def test_dry_run_apply_completes_offline(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-cli-") as tmp:
            code, out, err = run_cli(
                "--fixture", "clean-arch", "--state-root", tmp,
                "--apply", "--dry-run", "--decide", "desktop-profile=hyprland",
            )
        self.assertEqual(code, 0, err)
        result = parse_json(out)
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(result["changed"])
        self.assertEqual(result["errors"], [])
        self.assertGreater(len(result["completed_ops"]), 0)

    def test_real_apply_and_repeat_are_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-cli-apply-") as tmp:
            args = ("--fixture", "clean-arch", "--state-root", tmp,
                    "--apply", "--decide", "desktop-profile=hyprland")
            code, out, err = run_cli(*args)
            self.assertEqual(code, 0, err)
            first = parse_json(out)
            self.assertEqual(first["status"], "success")
            self.assertTrue(first["changed"])

            code, out, err = run_cli(*args)
            self.assertEqual(code, 0, err)
            second = parse_json(out)
            self.assertEqual(second["status"], "success")
            self.assertFalse(second["changed"], "repeated apply must make no changes")

            code, out, err = run_cli(*args)
            self.assertEqual(code, 0, err)
            third = parse_json(out)
            self.assertEqual(third["status"], "success")
            self.assertFalse(third["changed"], "every later apply must remain a no-op")

    def test_dry_run_does_not_create_state(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-cli-dry-") as tmp:
            code, out, err = run_cli(
                "--fixture", "clean-arch", "--state-root", tmp,
                "--apply", "--dry-run", "--decide", "desktop-profile=hyprland",
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_fixture_apply_refuses_live_state_root(self):
        code, out, err = run_cli("--fixture", "clean-arch", "--apply")
        self.assertEqual(code, 2)
        self.assertIn("refusing to run a fixture apply", err)

    def test_unknown_fixture_is_rejected(self):
        code, out, err = run_cli("--fixture", "does-not-exist", "--check")
        self.assertNotEqual(code, 0)
        self.assertIn("unknown fixture", err)

    def test_failed_stage_a_blocks_apply_before_discovery(self):
        def forbidden(_cmd):
            raise AssertionError("no command may run before Stage A succeeds")

        with tempfile.TemporaryDirectory(prefix="sunshine-cli-trust-") as tmp:
            with contextlib.redirect_stderr(io.StringIO()):
                code = cmd_apply(
                    "/", tmp, False, True,
                    trust=StageAReport(False, ("invalid signature",)),
                    execute=forbidden,
                )
        self.assertEqual(code, 3)

    def test_trust_report_requires_signed_receipt(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-cli-report-") as tmp:
            report = Path(tmp) / "report.json"
            report.write_text('{"passed": true}', encoding="utf-8")
            code, _out, err = run_cli(
                "--trust-report", str(report),
                "--trust-policy", "/tmp/policy.json",
                "--trust-keyring", "/tmp/keyring.gpg",
                "--check",
            )
        self.assertEqual(code, 3)
        self.assertIn("--trust-report requires --trust-receipt", err)

    def test_trust_index_requires_policy_and_keyring(self):
        code, out, err = run_cli("--trust-index", "/tmp/index.json", "--check")
        self.assertEqual(code, 3)
        self.assertIn("requires --trust-policy and --trust-keyring", err)

    def test_fixture_and_root_are_mutually_exclusive(self):
        code, out, err = run_cli("--fixture", "clean-arch", "--root", "/", "--check")
        self.assertNotEqual(code, 0)
        self.assertIn("mutually exclusive", err)


if __name__ == "__main__":
    unittest.main()
