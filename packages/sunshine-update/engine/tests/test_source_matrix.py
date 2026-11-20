"""G5 CI matrix: every supported source shape converges with an explicit plan.

The matrix is data (``source-matrix.toml``) so adding a machine shape does not
require a new code path. Each case asserts what discovery must observe and what
the resulting desired-state plan must (and must not) do.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import main  # noqa: E402

MATRIX = tomllib.loads(
    (ROOT / "tests" / "source-matrix.toml").read_text(encoding="utf-8")
)
CASES = MATRIX["cases"]
CONVERGENCE = MATRIX["convergence"]
ALL_AXES = {axis for case in CASES for axis in case["axes"]}


def run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def as_json(text: str) -> dict:
    return json.loads(text[text.index("{"):])


def installed_package_names(plan: dict) -> set[str]:
    names: set[str] = set()
    for op in plan.get("operations", []):
        if op["type"] == "InstallPackages":
            names.update(op.get("params", {}).get("packages", []))
    return names


class SourceMatrixTests(unittest.TestCase):
    def test_matrix_covers_every_required_axis(self):
        required = {"btrfs", "ext4", "luks", "grub", "systemd-boot", "nvidia", "dkms", "mixed-aur"}
        missing = required - ALL_AXES
        self.assertFalse(missing, f"source matrix is missing axes: {sorted(missing)}")
        self.assertGreaterEqual(len(CASES), 5)
        self.assertEqual(len({case["fixture"] for case in CASES}), len(CASES))

    def test_all_matrix_fixtures_exist(self):
        from src.fixtures import fixture_root
        for case in CASES:
            with self.subTest(fixture=case["fixture"]):
                self.assertTrue(fixture_root(case["fixture"]).is_dir())

    def test_discovery_matches_declared_source_shape(self):
        for case in CASES:
            fixture = case["fixture"]
            with self.subTest(fixture=fixture, axes=case["axes"]):
                code, out, err = run_cli("--fixture", fixture, "--check")
                self.assertEqual(code, 0, err)
                report = as_json(out)
                self.assertEqual(
                    report["source_compatibility"]["profile"], case["source_profile"]
                )
                self.assertTrue(report["source_compatibility"]["supported"])

                observations = report["observed"]["observations"]
                filesystems = observations["storage.filesystems"]
                self.assertTrue(
                    any(case["filesystem"] in line for line in filesystems["evidence"]),
                    f"{fixture}: {case['filesystem']} missing from {filesystems['evidence']}",
                )
                luks = observations["storage.luks"]
                self.assertEqual(luks["status"] != "absent", case["luks"], luks)
                btrfs = observations["storage.btrfs"]
                self.assertEqual(btrfs["status"] != "absent", case["btrfs"], btrfs)

                bootloader = observations["bootloader"]
                self.assertEqual(bootloader["detected"], case["bootloader"], bootloader)
                selected = [
                    d.get("selected") for d in report["decisions_required"]
                    if d["id"] == "bootloader-choice"
                ]
                self.assertEqual(selected, [case["bootloader"]])

                aur = observations["packages.aur"]
                self.assertEqual(
                    aur["status"] == "installed", case["aur"], aur
                )
                foreign = report["observed"]["foreign_packages"]
                self.assertEqual(sorted(foreign), sorted(case["foreign_packages"]))

    def test_each_source_shape_has_expected_convergence_plan(self):
        for case in CASES:
            fixture = case["fixture"]
            with self.subTest(fixture=fixture, axes=case["axes"]):
                code, out, err = run_cli("--fixture", fixture, "--plan")
                self.assertEqual(code, 0, err)
                plan = as_json(out)
                types = [op["type"] for op in plan["operations"]]
                for required in CONVERGENCE["required_operation_types"]:
                    self.assertIn(required, types, f"{fixture}: missing {required}")
                for forbidden in CONVERGENCE["forbidden_operation_types"]:
                    self.assertNotIn(forbidden, types, f"{fixture}: emitted {forbidden}")

                packages = installed_package_names(plan)
                op_ids = {op["id"] for op in plan["operations"]}
                for name in CONVERGENCE["required_package_names"]:
                    # A full-upgrade is an operation, not a package name; it
                    # must be present as the coherent foundation transition.
                    self.assertTrue(
                        any(op_id.endswith(name) or op_id == name for op_id in op_ids),
                        f"{fixture}: missing full-upgrade operation {name}",
                    )
                for name in case["forbidden_install_packages"]:
                    self.assertNotIn(name, packages, f"{fixture}: installed {name}")
                for name in case["foreign_packages"]:
                    self.assertNotIn(name, packages,
                                     f"{fixture}: foreign package {name} must not be replaced")

                reasons = " ".join(
                    str(op.get("params", {}).get("reason", ""))
                    for op in plan["operations"]
                    if op["type"] == "CreateCheckpoint"
                )
                for marker in case["expected_checkpoint_markers"]:
                    self.assertIn(marker, reasons, f"{fixture}: checkpoint lacks {marker}")

    def test_every_source_shape_applies_and_is_idempotent(self):
        for case in CASES:
            fixture = case["fixture"]
            with self.subTest(fixture=fixture, axes=case["axes"]):
                with tempfile.TemporaryDirectory(prefix="sunshine-matrix-") as tmp:
                    args = ("--fixture", fixture, "--state-root", tmp, "--apply",
                            "--decide", "desktop-profile=hyprland")
                    code, out, err = run_cli(*args)
                    self.assertEqual(code, 0, err)
                    first = as_json(out)
                    self.assertEqual(first["status"], "success", first["errors"])
                    self.assertTrue(first["changed"])

                    code, out, err = run_cli(*args)
                    self.assertEqual(code, 0, err)
                    second = as_json(out)
                    self.assertEqual(second["status"], "success", second["errors"])
                    self.assertFalse(second["changed"], f"{fixture}: repeat apply changed state")


if __name__ == "__main__":
    unittest.main()
