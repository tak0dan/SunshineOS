"""G6 proof: post-migration verification passes, and tampering is detected.

Each case applies a fixture into a sandbox (a real filesystem plus an injected
command executor), verifies the migrated state, breaks exactly one managed
capability, and requires ``--verify`` to fail and name that capability.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import main  # noqa: E402

FIXTURE = "clean-arch"

TAMPER_CASES = (
    {"id": "pacman", "capability": "pacman", "kind": "marker",
     "also": ("arch-foundation",)},
    {"id": "arch-foundation", "capability": "arch-foundation", "kind": "marker",
     "marker": "pacman", "also": ("pacman",)},
    {"id": "systemd", "capability": "systemd", "kind": "marker"},
    {"id": "boot", "capability": "boot-entry-management", "kind": "marker"},
    {"id": "bootloader-config", "capability": "bootloader-configuration",
     "kind": "marker_and_remove", "marker": "boot",
     "paths": ("boot/grub/grub.cfg",)},
    {"id": "network", "capability": "network-connection", "kind": "marker"},
    {"id": "audio", "capability": "audio-pipewire", "kind": "marker"},
    {"id": "config-ownership", "capability": "configuration-ownership", "kind": "remove",
     "paths": ("var/lib/sunshine/state/components.toml",)},
    {"id": "unified-config", "capability": "unified-configuration", "kind": "remove",
     "paths": ("etc/sunshine/components",)},
    {"id": "ownership-registry", "capability": "package-ownership-registry", "kind": "remove",
     "paths": ("var/lib/sunshine/ownership",)},
    {"id": "ownership-enforcement", "capability": "ownership-enforcement", "kind": "remove",
     "paths": ("var/lib/sunshine/ownership", "var/lib/sunshine/state/components.toml")},
    {"id": "kernel", "capability": "kernel-installation", "kind": "glob",
     "patterns": ("usr/lib/modules/*",)},
    {"id": "fallback", "capability": "kernel-fallback", "kind": "glob",
     "patterns": ("boot/*-fallback.img",)},
    {"id": "sessions", "capability": "desktop-session-discovery", "kind": "glob",
     "patterns": ("usr/share/xsessions/*.desktop", "usr/share/wayland-sessions/*.desktop")},
    {"id": "profiles", "capability": "sunshine-profile-management", "kind": "remove",
     "paths": ("etc/sunshine/profiles",)},
    {"id": "selected-profile", "capability": "desktop-profile:hyprland", "kind": "remove",
     "paths": ("etc/sunshine/profiles/default.toml",)},
    {"id": "recovery", "capability": "recovery-checkpoints", "kind": "remove",
     "paths": ("migration/checkpoints",)},
    {"id": "migration-journal", "capability": "migration-recovery", "kind": "remove",
     "paths": ("migration/journal",)},
    {"id": "rollback", "capability": "rollback", "kind": "remove",
     "paths": ("migration/journal/journal.jsonl", "migration/transactions")},
)


def run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def verify(state_root: str) -> tuple[int, dict]:
    code, out, err = run_cli(
        "--fixture", FIXTURE, "--state-root", state_root, "--verify"
    )
    payload = json.loads(out[out.index("{"):])
    return code, payload


def apply(state_root: str) -> None:
    code, _out, err = run_cli(
        "--fixture", FIXTURE, "--state-root", state_root,
        "--apply", "--decide", "desktop-profile=hyprland",
    )
    if code != 0:
        raise AssertionError(f"fixture apply failed: {err or code}")


def tamper(state_root: str, case: dict) -> None:
    root = Path(state_root)
    if case["kind"] in ("marker", "marker_and_remove"):
        name = case.get("marker", case["id"])
        marker = root / "migration" / "tamper" / name
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("tampered\n", encoding="utf-8")
        if case["kind"] == "marker":
            return
    for rel in case.get("paths", ()):
        target = root / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
    for pattern in case.get("patterns", ()):
        for target in root.glob(pattern):
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()


class PostMigrationVerifyTests(unittest.TestCase):
    def test_verify_passes_after_real_fixture_apply(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-g6-") as state:
            apply(state)
            code, payload = verify(state)
            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["passed"], [
                r for r in payload["reports"] if not r["passed"]
            ])
            self.assertGreaterEqual(len(payload["reports"]), 18)
            # Reports must be structured JSON, not Python repr strings.
            self.assertIsInstance(payload["reports"][0], dict)

    def test_every_managed_capability_is_detected_when_tampered(self):
        managed = set()
        with tempfile.TemporaryDirectory(prefix="sunshine-g6-baseline-") as state:
            apply(state)
            _code, payload = verify(state)
            managed = {r["capability"] for r in payload["reports"]}
        covered = set()
        for case in TAMPER_CASES:
            covered.add(case["capability"])
            covered.update(case.get("also", ()))
        missing = managed - covered
        self.assertFalse(missing, f"tamper proof missing capabilities: {sorted(missing)}")

    def test_tampering_is_reported_and_fails_verification(self):
        for case in TAMPER_CASES:
            with self.subTest(capability=case["capability"], tamper=case["id"]):
                with tempfile.TemporaryDirectory(prefix="sunshine-g6-tamper-") as state:
                    apply(state)
                    baseline_code, baseline = verify(state)
                    self.assertEqual(baseline_code, 0, baseline)
                    self.assertTrue(baseline["passed"])

                    tamper(state, case)
                    code, payload = verify(state)
                    self.assertEqual(code, 1, payload)
                    self.assertFalse(payload["passed"])
                    failed = {
                        r["capability"] for r in payload["reports"] if not r["passed"]
                    }
                    self.assertIn(case["capability"], failed,
                                  f"{case['id']}: {case['capability']} still passed")
                    for also in case.get("also", ()):
                        self.assertIn(also, failed,
                                      f"{case['id']}: {also} still passed")
                    for report in payload["reports"]:
                        if report["capability"] == case["capability"]:
                            self.assertTrue(report["detail"])
                            break

    def test_verify_refuses_failed_stage_a_before_probing(self):
        from src.engine import cmd_verify
        from src.trust import StageAReport

        def forbidden(_cmd):
            raise AssertionError("no probe may run before Stage A succeeds")

        with tempfile.TemporaryDirectory(prefix="sunshine-g6-trust-") as state:
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                code = cmd_verify(
                    state, forbidden, StageAReport(False, ("bad signature",))
                )
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
