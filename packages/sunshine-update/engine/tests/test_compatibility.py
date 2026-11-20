"""Tests for source compatibility profiles (TODO_Migration.md §14)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core import Confidence, ObservedState, Status, observation  # noqa: E402
from src.target.compatibility import (  # noqa: E402
    classify_source,
    preflight_source,
)


def _obs(component, detected, confidence, status):
    return observation(component, detected, confidence, status, [f"{component}: fixture"])


def _arch(**overrides) -> ObservedState:
    state = ObservedState(
        distribution=overrides.get("distribution", "arch"),
        architecture=overrides.get("architecture", "x86_64"),
        init_system=overrides.get("init_system", "systemd"),
        package_manager=overrides.get("package_manager", "pacman"),
    )
    state.observe(_obs("pacman.query", "pacman-database-ok", "high", "functional"))
    state.observe(_obs("bootloader", "grub", "high", "configured"))
    state.observe(_obs("kernel.running", "6.10.1-arch1-1", "high", "running"))
    state.observe(_obs("kernel.installed", "6.10.1-arch1-1", "high", "installed"))
    if overrides.get("foreign"):
        state.foreign_packages = ["custom-aur-tool"]
    if overrides.get("luks"):
        state.observe(_obs("capability.luks", "luks", "medium", "configured"))
    if overrides.get("partial"):
        state.observe(_obs("sunshine.partial-installation", "partial", "medium", "installed"))
    if overrides.get("broken_db"):
        state.observe(_obs("pacman.query", "broken", "high", "absent"))
    if overrides.get("no_bootloader"):
        state.observations.pop("bootloader", None)
        state.observe(_obs("bootloader", "none", "high", "absent"))
    return state


class CompatibilityTests(unittest.TestCase):
    def test_clean_arch_is_official(self):
        report = classify_source(_arch())
        self.assertEqual(report.profile, "arch-standard")
        self.assertEqual(report.support_level, "official")
        self.assertTrue(report.supported)
        self.assertEqual(report.blockers, [])

    def test_foreign_packages_make_conditional_not_unsupported(self):
        report = classify_source(_arch(foreign=True))
        self.assertEqual(report.profile, "arch-customized")
        self.assertEqual(report.support_level, "conditional")
        self.assertTrue(report.supported)
        self.assertTrue(any("foreign" in w for w in report.warnings))

    def test_luks_and_partial_sunshine_are_conditional(self):
        report = classify_source(_arch(luks=True, partial=True))
        self.assertEqual(report.profile, "arch-customized")
        self.assertTrue(report.supported)
        self.assertGreaterEqual(len(report.warnings), 2)

    def test_installed_sunshine_is_supported(self):
        state = _arch(distribution="sunshineos")
        state.observe(_obs("sunshine.installation", "complete", "high", "configured"))
        report = classify_source(state)
        self.assertEqual(report.profile, "sunshine-installed")
        self.assertTrue(report.supported)

    def test_non_arch_distribution_is_blocked(self):
        report = classify_source(_arch(distribution="debian"))
        self.assertFalse(report.supported)
        self.assertTrue(any("unsupported distribution" in b for b in report.blockers))

    def test_non_systemd_is_blocked(self):
        report = classify_source(_arch(init_system="openrc"))
        self.assertFalse(report.supported)
        self.assertTrue(any("init system" in b for b in report.blockers))

    def test_non_pacman_is_blocked(self):
        report = classify_source(_arch(package_manager="apt"))
        self.assertFalse(report.supported)
        self.assertTrue(any("package manager" in b for b in report.blockers))

    def test_unsupported_architecture_is_blocked(self):
        report = classify_source(_arch(architecture="riscv64"))
        self.assertFalse(report.supported)
        self.assertTrue(any("architecture" in b for b in report.blockers))

    def test_broken_database_is_blocked(self):
        report = classify_source(_arch(broken_db=True))
        self.assertFalse(report.supported)
        self.assertTrue(any("database" in b for b in report.blockers))

    def test_no_bootloader_is_blocked(self):
        report = classify_source(_arch(no_bootloader=True))
        self.assertFalse(report.supported)
        self.assertTrue(any("bootloader" in b for b in report.blockers))

    def test_strict_policy_rejects_conditional_source(self):
        report = preflight_source(_arch(foreign=True), allow_conditional=False)
        self.assertFalse(report.supported)
        self.assertTrue(any("conditional source" in b for b in report.blockers))

    def test_report_is_json_serialisable(self):
        import json
        json.dumps(classify_source(_arch()).to_dict())

    def test_repository_rollback_is_refused(self):
        from dataclasses import replace
        from src.target import load_target
        from src.planner import plan
        state = _arch()
        state.repository_generation = 99
        target = replace(load_target(), repository_generation=7)
        with self.assertRaises(ValueError) as ctx:
            plan(state, target)
        self.assertIn("repository rollback refused", str(ctx.exception))

    def test_same_generation_is_accepted(self):
        from dataclasses import replace
        from src.target import load_target
        from src.planner import plan
        state = _arch()
        state.repository_generation = 7
        target = replace(load_target(), repository_generation=7)
        result = plan(state, target)
        self.assertTrue(result.operations)


if __name__ == "__main__":
    unittest.main()
