"""End-to-end integration tests: discover → resolve → plan → execute → validate.

These tests exercise the CLI's helper functions across fixtures with a single
ObservedState class identity, and prove the two source paths converge on the
same target with one engine.
"""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import ObservedState  # noqa: E402
from src.discovery import discover  # noqa: E402
from src.target import load_target, resolve_target  # noqa: E402
from src.planner import plan as build_plan  # noqa: E402
from src.executor import execute_plan  # noqa: E402
from src.validation import validate_system  # noqa: E402

BASE = Path(__file__).resolve().parent.parent


class FakeExec:
    """Minimal injected executor that records commands and reports success."""

    def __init__(self):
        self.commands: list[str] = []

    def __call__(self, cmd: str) -> tuple[int, str, str]:
        self.commands.append(cmd)
        c = cmd.strip()
        if c == "pacman -Q":
            return 0, "base 1.1-1\nsystemd 255.8-1\npacman 7.1.0-1\nlinux 6.10.1-arch1-1\ngrub 2.12-1\n", ""
        if c.startswith("pacman -Q "):
            return 0, "1.0-1", ""
        if c.startswith("pacman -Qqdt"):
            return 0, "", ""
        if c.startswith("pacman -Qqm"):
            return 0, "", ""
        if c.startswith("systemctl is-enabled"):
            return 0, "enabled", ""
        if c.startswith("systemctl is-active"):
            return 0, "active", ""
        if c == "pacman --version":
            return 0, "Pacman v7.1.0", ""
        if c.startswith("uname"):
            return 0, "x86_64" if " -m" in c else "6.10.1-arch1-1", ""
        if c == "cat /proc/1/comm":
            return 0, "systemd", ""
        if c.startswith("systemctl --version"):
            return 0, "systemd 255 (255.8-1-arch)", ""
        # Unknown commands fail: a fake that succeeds for everything makes a
        # clean Arch fixture look like it has `sunshine --version` available.
        return 1, "", "command not available in fixture"


def _fixture_pipeline(name: str, packages: dict[str, str] | None = None):
    root = BASE / "fixtures" / name
    fx = FakeExec()
    state = discover(root=str(root), execute=fx)
    target = load_target()
    target, decisions = resolve_target(state, target)
    plan = build_plan(state, target, decisions=decisions)
    return state, target, plan, decisions, fx


class IntegrationTests(unittest.TestCase):
    def test_single_class_identity(self):
        state = discover(root=str(BASE / "fixtures" / "clean-arch"), execute=FakeExec())
        self.assertIsInstance(state, ObservedState)

    def test_clean_arch_pipeline_introduces_every_required_component(self):
        state, target, plan, decisions, fx = _fixture_pipeline("clean-arch", {"base": "1"})
        self.assertGreater(len(plan.operations), 0)
        registered = [o for o in plan.operations if o.type.value == "RegisterComponent"]
        self.assertGreaterEqual(len(registered), len(target.required_components()),
                                "every required component must be introduced on pure Arch")
        self.assertTrue(any(o.type.value == "CreateCheckpoint" for o in plan.operations))

    def test_old_sunshine_and_clean_arch_share_one_pipeline(self):
        old = _fixture_pipeline("old-sunshine")
        new = _fixture_pipeline("clean-arch")
        types_old = Counter(o.type.value for o in old[2].operations)
        types_new = Counter(o.type.value for o in new[2].operations)
        self.assertEqual(
            set(types_old), set(types_new),
            "both source paths must use the same operation vocabulary",
        )

    def test_decisions_are_focused_not_a_questionnaire(self):
        for fixture in ("clean-arch", "old-sunshine", "arch-plasma"):
            _, _, _, decisions, _ = _fixture_pipeline(fixture)
            user_questions = [d for d in decisions if d.get("requires_user_input")]
            self.assertLessEqual(len(user_questions), 3,
                                 f"{fixture} asked {len(user_questions)} questions")

    def test_dry_run_execution_changes_nothing(self):
        import tempfile
        from src.core import Plan, Operation, OpType
        # Use a minimal non-destructive plan: a plan built from sparse fixture
        # observations correctly refuses destructive ops, which is a feature.
        op = Operation(id="dry-register", type=OpType.REGISTER_COMPONENT,
                       component="core",
                       params={"component_id": "core", "schema": 3})
        plan = Plan(id="dry-plan", source={}, target={}, operations=[op])
        root = Path(tempfile.mkdtemp())
        result = execute_plan(plan, root, FakeExec(), dry_run=True)
        self.assertEqual(result.status, "dry_run", result.errors)
        self.assertFalse(result.changed)
        self.assertEqual(list(root.iterdir()), [], "dry-run must not create state files")

    def test_validation_fails_closed_for_unknown_capability(self):
        from src.validation import validate_capability
        r = validate_capability("totally-made-up-capability", "/", lambda c: (0, "", ""))
        self.assertFalse(r.passed)

    # ---- Regressions found during live VM dry-run ------------------------ #

    def test_boot_entry_loader_is_an_efi_path_with_valid_label(self):
        """software_version must never be used as a boot loader path."""
        import re
        for fixture in ("clean-arch", "old-sunshine", "arch-plasma"):
            _, _, plan, _, _ = _fixture_pipeline(fixture)
            entries = [o for o in plan.operations if o.type.value == "InstallBootEntry"]
            self.assertTrue(entries, f"{fixture} emitted no boot entry")
            for entry in entries:
                self.assertTrue(entry.params["loader"].startswith("/"),
                                f"{fixture}: loader={entry.params['loader']!r}")
                self.assertRegex(entry.params["label"], r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")

    def test_generic_arch_capabilities_do_not_count_as_registration(self):
        """GRUB/kernel capabilities must not skip component introduction."""
        from src.core import ComponentSpec, Lifecycle
        from src.planner.strategies import _detect_presence
        from src.discovery import discover
        state = discover(str(BASE / "fixtures" / "clean-arch"), execute=FakeExec())
        spec = ComponentSpec(id="boot_integration", schema=2, required=True,
                             software_version="2026.1", lifecycle=Lifecycle.EVOLVE,
                             provides=["boot-entry-management", "bootloader-configuration"],
                             requires=[])
        self.assertFalse(_detect_presence(state, spec),
                         "generic Arch boot capability was mistaken for a Sunshine component")

    def test_full_clean_arch_plan_dry_runs_end_to_end(self):
        """The whole fixture pipeline must survive a dry-run apply."""
        import tempfile
        state, target, plan, decisions, fx = _fixture_pipeline("clean-arch")
        result = execute_plan(plan, Path(tempfile.mkdtemp()), fx, dry_run=True)
        self.assertEqual(result.status, "dry_run", result.errors)
        self.assertEqual(len(result.completed_ops), len(plan.operations))
        self.assertFalse(result.changed)

    def test_discovery_survives_empty_command_output(self):
        """A command exiting 0 with no stdout must not crash discovery."""
        class EmptyExec(FakeExec):
            def __call__(self, cmd):
                return 0, "", ""
        discover(str(BASE / "fixtures" / "clean-arch"), execute=EmptyExec())

    def test_network_choice_not_inferred_from_unrelated_service(self):
        """services.systemd evidence must not become a 'systemd' network choice."""
        from src.target.resolver import _observed_choice
        from src.discovery import discover
        state = discover(str(BASE / "fixtures" / "clean-arch"), execute=FakeExec())
        choice = _observed_choice(state, "network")
        self.assertIsNotNone(choice)
        self.assertEqual(choice[0], "networkmanager")

    def test_source_profiles_are_classified_per_fixture(self):
        from src.target.compatibility import classify_source
        expected = {
            "clean-arch": "arch-standard",
            "arch-plasma": "arch-standard",
            "old-sunshine": "sunshine-installed",
        }
        for fixture, profile in expected.items():
            state, _, _, _, _ = _fixture_pipeline(fixture)
            report = classify_source(state)
            self.assertEqual(report.profile, profile, fixture)
            self.assertTrue(report.supported, f"{fixture}: {report.blockers}")

    def test_stale_plan_is_refused_after_state_changes(self):
        """A plan built for one machine must not execute against another state."""
        import tempfile
        state, target, plan, decisions, fx = _fixture_pipeline("clean-arch")
        state.packages["newly-installed-package"] = "9.9-1"  # state changed after planning
        fx.commands.clear()  # discovery commands happened before planning

        result = execute_plan(plan, Path(tempfile.mkdtemp()), fx,
                              resume=True, observed=state)

        self.assertEqual(result.status, "failed")
        self.assertTrue(any("stale plan" in e for e in result.errors), result.errors)
        self.assertEqual(fx.commands, [], "stale plan must not run any command")

    def test_all_source_matrix_fixtures_converge(self):
        """Spec §15 source-state matrix: every fixture must plan and dry-run."""
        from src.target.compatibility import classify_source
        import tempfile
        fixtures = (
            "clean-arch", "arch-plasma", "arch-hyprland", "arch-gnome",
            "arch-xfce", "arch-sway", "arch-five-year-old", "old-sunshine",
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                state, target, plan, decisions, fx = _fixture_pipeline(fixture)
                report = classify_source(state)
                self.assertTrue(report.supported, f"{fixture}: {report.blockers}")
                self.assertGreater(len(plan.operations), 0, fixture)
                result = execute_plan(plan, Path(tempfile.mkdtemp()), fx, dry_run=True)
                self.assertEqual(result.status, "dry_run", f"{fixture}: {result.errors}")

    def test_repeated_planning_is_idempotent(self):
        """A second plan against converged state must not repeat mutations."""
        from src.core import OpType
        from src.target.compatibility import classify_source
        state, target, plan, decisions, fx = _fixture_pipeline("clean-arch")
        # Converged state: mark all components registered and all capabilities
        # present, then confirm planning emits validation but no mutations.
        from src.core import observation
        for spec in target.components.values():
            marker = f"sunshine-component:{spec.id}"
            state.capabilities.add(marker)
            state.observe(observation(marker, marker, "high", "enabled", ["converged fixture"]))
            for cap in spec.provides:
                state.capabilities.add(cap)
        for packages in target.package_sets.values():
            for package in packages:
                state.packages[package] = "1.0-1"
        from src.planner import plan as build_plan
        second = build_plan(state, target, decisions=decisions)
        mutations = [o for o in second.operations
                     if o.type is not OpType.VALIDATE_CAPABILITY]
        self.assertEqual(mutations, [],
                         f"repeated run produced {len(mutations)} mutations")
        self.assertEqual(classify_source(state).supported, True)

    def test_executor_group_promotion_preserves_dag_order(self):
        """A RegisterComponent depending on InstallBootEntry must run after it."""
        import tempfile
        _, _, plan, _, fx = _fixture_pipeline("clean-arch")
        result = execute_plan(plan, Path(tempfile.mkdtemp()), fx, dry_run=True)
        self.assertEqual(result.status, "dry_run", result.errors)
        positions = {oid: i for i, oid in enumerate(result.completed_ops)}
        for op in plan.operations:
            for dep in op.requires:
                self.assertIn(dep, positions, f"{op.id} ran without dependency {dep}")
                self.assertLess(positions[dep], positions[op.id],
                                f"{op.id} ran before its dependency {dep}")


if __name__ == "__main__":
    unittest.main()
