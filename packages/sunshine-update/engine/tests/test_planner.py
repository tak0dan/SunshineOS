"""Unit tests for the transformation planner.

Run from the evolution-engine directory with::

    python3 -m unittest discover -s tests -v

The tests use only stdlib and construct simulated observations in memory; the
planner never touches the real machine.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core import (  # noqa: E402
    ComponentSpec,
    Confidence,
    Lifecycle,
    ObservedState,
    OpType,
    Status,
    TargetSpec,
    observation,
)
from src.planner import (  # noqa: E402
    DependencyGraph,
    build_plan,
    capability_deltas,
    create_checkpoint,
    create_configuration,
    disable_service,
    enable_service,
    generate_initramfs,
    install_boot_entry,
    install_kernel,
    install_packages,
    migrate_configuration,
    plan,
    register_component,
    remove_packages,
    transfer_ownership,
    validate_capability,
)


COMPONENT_CAPABILITIES: dict[str, list[str]] = {
    "core": ["systemd", "pacman"],
    "configuration": ["configuration-ownership"],
    "ownership": ["package-ownership-registry"],
    "kernel_management": ["kernel-installation", "kernel-fallback"],
    "boot_integration": ["boot-entry-management"],
    "recovery": ["recovery-checkpoints", "migration-recovery"],
    "desktop_integration": ["desktop-session-discovery", "sunshine-profile-management"],
    "nix_integration": ["nix-integration"],
}

PACKAGE_SETS: dict[str, list[str]] = {
    "core": ["base", "systemd", "pacman"],
    "configuration": ["sunshine-config"],
    "ownership": ["sunshine-ownership"],
    "kernel_management": ["linux", "mkinitcpio"],
    "boot_integration": ["efibootmgr", "grub"],
    "recovery": ["sunshine-recovery"],
    "desktop_integration": ["sunshine-desktop"],
    "nix_integration": ["nix"],
}


def make_target(schema: int = 2, *, requires: dict[str, list[str]] | None = None) -> TargetSpec:
    requires = requires or {}
    components = {
        cid: ComponentSpec(
            id=cid,
            schema=schema,
            required=True,
            software_version="6.6.1" if cid == "kernel_management" else "",
            provides=list(caps),
            requires=list(requires.get(cid, [])),
        )
        for cid, caps in COMPONENT_CAPABILITIES.items()
    }
    return TargetSpec(
        format_version=1,
        release="current",
        repository_generation=7,
        components=components,
        package_sets=copy.deepcopy(PACKAGE_SETS),
        policies={"dry_run_safe": True},
    )


def make_pure_arch() -> ObservedState:
    """A plain Arch machine: systemd/pacman/linux exist, no Sunshine at all."""
    observed = ObservedState(
        distribution="arch",
        architecture="x86_64",
        init_system="systemd",
        package_manager="pacman",
        packages={
            "base": "1",
            "systemd": "255",
            "pacman": "6",
            "linux": "6.6.1",
            "mkinitcpio": "38",
            "efibootmgr": "18",
            "grub": "2.12",
        },
    )
    observed.observe(observation("systemd", "systemd", "high", "running", ["pid1"]))
    observed.observe(observation("pacman", "pacman", "high", "functional", ["--version"]))
    return observed


def make_old_sunshine(schema: int = 1, *, converged: bool = False) -> ObservedState:
    """An existing Sunshine installation, optionally already at the target.

    ``schema`` is the schema actually observed on the machine; callers pass the
    target schema as well when the machine is already converged.
    """
    observed = make_pure_arch()
    observed.distribution = "sunshine"
    for cid, caps in COMPONENT_CAPABILITIES.items():
        observed.capabilities.update(caps)
        observed.capabilities.add(f"sunshine-component:{cid}")
        observed.packages.update(
            {package: "1" for package in PACKAGE_SETS.get(cid, [])}
        )
        observed.observe(observation(
            cid,
            f"sunshine-component:{cid}",
            "high",
            "enabled",
            [f"schema={schema}", "sunshine component registry"],
        ))
    return observed


def ops_of(plan_result, op_type: OpType, component: str | None = None) -> list:
    return [
        op for op in plan_result.operations
        if op.type is op_type and (component is None or op.component == component)
    ]


class PlannerTests(unittest.TestCase):
    # ------------------------------------------------------------------ #
    # Pure Arch -> introduce everything
    # ------------------------------------------------------------------ #
    def test_pure_arch_introduces_all_components(self) -> None:
        observed = make_pure_arch()
        target = make_target()
        decisions = [{"id": "select-profile", "prompt": "desktop or server?"}]

        result = plan(observed, target, decisions=decisions)

        self.assertEqual(result.decisions, decisions)
        self.assertEqual(result.deltas["outdated"], [])  # absent, not stale
        self.assertIn("configuration-ownership", result.deltas["missing"])
        for cid in target.components:
            registrations = ops_of(result, OpType.REGISTER_COMPONENT, cid)
            self.assertEqual(len(registrations), 1, cid)
            self.assertEqual(registrations[0].params["component_id"], cid)
            self.assertEqual(registrations[0].params["lifecycle"], "introduce")
            self.assertEqual(len(ops_of(result, OpType.VALIDATE_CAPABILITY, cid)), 1, cid)

        self.assertEqual(ops_of(result, OpType.REMOVE_PACKAGES), [])
        self.assertTrue(ops_of(result, OpType.CREATE_CONFIGURATION))
        self.assertTrue(ops_of(result, OpType.TRANSFER_OWNERSHIP))
        self.assertTrue(ops_of(result, OpType.INSTALL_KERNEL))
        self.assertTrue(ops_of(result, OpType.GENERATE_INITRAMFS))
        self.assertTrue(ops_of(result, OpType.INSTALL_BOOT_ENTRY))
        self.assertTrue(ops_of(result, OpType.ENABLE_SERVICE))

        # The resulting plan must itself be a valid DAG.
        graph = DependencyGraph()
        graph.add_all(result.operations)
        graph.validate()
        self.assertEqual(len(graph.topological_sort()), len(result.operations))

    def test_pure_arch_plan_is_json_serializable(self) -> None:
        result = plan(make_pure_arch(), make_target())
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(payload["plan_id"], result.id)
        self.assertTrue(payload["operations"])

    def test_component_requires_are_honoured(self) -> None:
        target = make_target(requires={"configuration": ["core"]})
        result = plan(make_pure_arch(), target)

        core_last = ops_of(result, OpType.REGISTER_COMPONENT, "core")[0].id
        config_first_candidates = [
            op for op in result.operations if op.component == "configuration"
        ]
        self.assertTrue(config_first_candidates)
        self.assertIn(core_last, config_first_candidates[0].requires)

    # ------------------------------------------------------------------ #
    # Old Sunshine -> evolve only
    # ------------------------------------------------------------------ #
    def test_old_sunshine_only_evolves(self) -> None:
        observed = make_old_sunshine(schema=1)
        target = make_target(schema=2)

        result = plan(observed, target)

        self.assertFalse(result.deltas["outdated"] == [])
        self.assertEqual(ops_of(result, OpType.REGISTER_COMPONENT), [])
        self.assertEqual(ops_of(result, OpType.CREATE_CONFIGURATION), [])
        self.assertEqual(ops_of(result, OpType.INSTALL_PACKAGES), [])
        self.assertTrue(ops_of(result, OpType.MIGRATE_CONFIGURATION))

        for operation in result.operations:
            self.assertEqual(operation.params["lifecycle"], "evolve", operation.id)

        mutation_types = set(OpType) - {OpType.VALIDATE_CAPABILITY, OpType.CREATE_CHECKPOINT}
        for operation in result.operations:
            if operation.type in mutation_types:
                self.assertIn(
                    operation.params["planning_reason"],
                    {decision["reason"] for decision in result.planning_decisions
                     if decision["kind"] == "component"},
                )

    # ------------------------------------------------------------------ #
    # Idempotency
    # ------------------------------------------------------------------ #
    def test_converged_state_yields_validation_only(self) -> None:
        observed = make_old_sunshine(schema=2, converged=True)
        target = make_target(schema=2)

        result = plan(observed, target)

        self.assertEqual(
            {op.type for op in result.operations},
            {OpType.VALIDATE_CAPABILITY},
        )
        self.assertFalse(any(op.destructive for op in result.operations))
        self.assertEqual(result.deltas["missing"], [])
        self.assertEqual(result.deltas["outdated"], [])
        self.assertEqual(
            {op.component for op in result.operations},
            set(target.components),
        )

    def test_planning_is_pure_and_repeatable(self) -> None:
        observed = make_pure_arch()
        target = make_target()
        before_observed = copy.deepcopy(observed)
        before_target = copy.deepcopy(target)

        first = build_plan(observed, target)
        second = build_plan(observed, target)

        self.assertEqual(observed, before_observed)
        self.assertEqual(target, before_target)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            [op.id for op in first.operations],
            [op.id for op in second.operations],
        )

    def test_dry_run_has_no_side_effects(self) -> None:
        observed = make_pure_arch()
        target = make_target()
        before_observed = copy.deepcopy(observed)
        before_target = copy.deepcopy(target)

        result = plan(observed, target, dry_run=True)

        self.assertEqual(observed, before_observed)
        self.assertEqual(target, before_target)
        self.assertTrue(result.dry_run)
        self.assertTrue(all(op.params.get("dry_run") is True for op in result.operations))

    def test_desktop_profile_enables_only_a_published_service(self) -> None:
        # sunshine-profiles.service is not shipped by any published package.
        # The profile tree is declarative; the published sunshine-base package
        # provides sunshine-apps.service for finishing chosen app setup.
        result = plan(make_pure_arch(), make_target())
        services = ops_of(result, OpType.ENABLE_SERVICE)
        self.assertTrue(services)
        for operation in services:
            self.assertNotEqual(operation.params.get("unit"), "sunshine-profiles")
            self.assertNotEqual(operation.params.get("service"), "sunshine-profiles")
        self.assertTrue(any(
            operation.params.get("service") == "sunshine-apps"
            or operation.params.get("unit") == "sunshine-apps"
            for operation in services
        ))

    def test_kernel_preset_is_real_kernel_package_not_release_version(self) -> None:
        # The release version (e.g. 2026.1) is not a mkinitcpio preset. On a
        # real Arch machine only /etc/mkinitcpio.d/<package>.preset exists.
        result = plan(make_pure_arch(), make_target())
        kernels = ops_of(result, OpType.INSTALL_KERNEL)
        initramfs = ops_of(result, OpType.GENERATE_INITRAMFS)
        self.assertTrue(kernels and initramfs)
        for operation in initramfs:
            self.assertEqual(operation.params.get("preset"), "linux")
            self.assertNotEqual(operation.params.get("preset"), "6.6.1")
        for operation in kernels:
            self.assertEqual(operation.params.get("package"), "linux")

    # ------------------------------------------------------------------ #
    # Checkpoints for destructive operations
    # ------------------------------------------------------------------ #
    def test_destructive_operation_gets_checkpoint_before_it(self) -> None:
        observed = make_pure_arch()
        # An existing Sunshine tree makes ownership transfer genuinely
        # destructive; a fresh install's ownership assignment is not.
        observed.observe(observation(
            "sunshine.config", "sunshine-configuration", "high", "configured",
            ["/etc/sunshine/config.toml"],
        ))
        observed.observe(observation(
            "sunshine.state", "sunshine-state", "high", "configured",
            ["/var/lib/sunshine/state/components.toml"],
        ))
        result = plan(observed, make_target())

        # One planner checkpoint protects all destructive operations; the
        # recovery strategy may additionally emit its own baseline checkpoint.
        checkpoints = ops_of(result, OpType.CREATE_CHECKPOINT)
        planner_checkpoints = [op for op in checkpoints if not op.component]
        self.assertEqual(len(planner_checkpoints), 1)
        checkpoint = planner_checkpoints[0]
        destructive = [op for op in result.operations if op.destructive]
        self.assertTrue(destructive)

        for operation in destructive:
            self.assertIn(checkpoint.id, operation.requires)
            self.assertLess(
                result.operations.index(checkpoint),
                result.operations.index(operation),
            )

        transfer = ops_of(result, OpType.TRANSFER_OWNERSHIP)[0]
        self.assertTrue(transfer.destructive)
        self.assertIn(checkpoint.id, transfer.requires)

    def test_converged_plan_has_no_checkpoint(self) -> None:
        result = plan(make_old_sunshine(schema=2, converged=True), make_target(schema=2))
        self.assertEqual(ops_of(result, OpType.CREATE_CHECKPOINT), [])

    # ------------------------------------------------------------------ #
    # Graph behaviour
    # ------------------------------------------------------------------ #
    def test_cycle_detection(self) -> None:
        graph = DependencyGraph()
        first = install_packages(["a"], component="x")
        second = enable_service("daemon", component="x", requires=[first.id])
        graph.add(first, allow_pending=True)
        graph.add(second, allow_pending=True)
        graph.get(first.id).requires.append(second.id)

        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.topological_sort()
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.validate()
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.parallel_layers()

    def test_missing_dependency_raises(self) -> None:
        graph = DependencyGraph()
        operation = install_packages(["a"], component="x", requires=["does-not-exist"])
        graph.add(operation, allow_pending=True)
        with self.assertRaisesRegex(ValueError, "missing dependency"):
            graph.topological_sort()

    def test_parallel_layers_and_conflicts(self) -> None:
        graph = DependencyGraph()
        first = install_packages(["x"], component="a")
        dependent = validate_capability(["cap"], component="a", requires=[first.id])
        independent = install_packages(["y"], component="b")
        graph.add(first)
        graph.add(dependent)
        graph.add(independent)

        layers = graph.parallel_layers()
        self.assertEqual([op.id for op in layers[0]], sorted([first.id, independent.id]))
        self.assertEqual([op.id for op in layers[1]], [dependent.id])

        conflicting = DependencyGraph()
        conflicting.add(install_packages(["x"], component="a"))
        conflicting.add(remove_packages(["x"], component="a"))
        self.assertEqual(len(conflicting.detect_conflicts()), 1)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            conflicting.validate()

    def test_recalculate_removes_satisfied_operations_and_rewires(self) -> None:
        graph = DependencyGraph()
        already = install_packages(["present"], component="x")
        dependent = install_packages(["missing"], component="x", requires=[already.id])
        graph.add(already)
        graph.add(dependent)

        observed = make_pure_arch()
        observed.packages["present"] = "1"
        removed = graph.recalculate(observed)

        self.assertEqual(removed, [already.id])
        self.assertEqual(graph.operation_ids, [dependent.id])
        self.assertEqual(graph.get(dependent.id).requires, [])

    # ------------------------------------------------------------------ #
    # Operation factories validate their parameters
    # ------------------------------------------------------------------ #
    def test_factories_validate_parameters(self) -> None:
        with self.assertRaises(ValueError):
            install_packages([])
        with self.assertRaises(ValueError):
            install_packages("single-package")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            remove_packages([])
        with self.assertRaises(ValueError):
            transfer_ownership([], "root", "sunshine")
        with self.assertRaises(ValueError):
            transfer_ownership(["/etc/sunshine"], "", "sunshine")
        with self.assertRaises(ValueError):
            create_configuration("")
        with self.assertRaises(ValueError):
            migrate_configuration("/etc/x", 2, 1)
        with self.assertRaises(ValueError):
            migrate_configuration("/etc/x", -1, 2)
        with self.assertRaises(ValueError):
            register_component("")
        with self.assertRaises(ValueError):
            register_component(None)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            register_component("core", schema=-1)
        with self.assertRaises(ValueError):
            enable_service("")
        with self.assertRaises(ValueError):
            disable_service("")
        with self.assertRaises(ValueError):
            install_kernel("")
        with self.assertRaises(ValueError):
            generate_initramfs("")
        with self.assertRaises(ValueError):
            install_boot_entry("")
        with self.assertRaises(ValueError):
            create_checkpoint("")
        with self.assertRaises(ValueError):
            validate_capability([])
        with self.assertRaises(ValueError):
            install_packages(["x"], lifecycle="not-a-lifecycle")
        with self.assertRaises(ValueError):
            install_packages(["x"], requires=123)  # type: ignore[arg-type]

    def test_operation_risk_flags(self) -> None:
        self.assertTrue(remove_packages(["x"]).destructive)
        self.assertTrue(transfer_ownership(["/x"], "a", "b").destructive)
        self.assertTrue(disable_service("svc").destructive)
        self.assertTrue(migrate_configuration("/x", 1, 2).destructive)
        self.assertTrue(install_kernel("6.6").needs_reboot)
        self.assertTrue(install_boot_entry("grub").needs_reboot)
        self.assertFalse(validate_capability(["cap"]).destructive)
        self.assertEqual(
            register_component("core").params["component_id"],
            "core",
        )
        self.assertEqual(
            register_component("core").params["lifecycle"],
            Lifecycle.INTRODUCE.value,
        )

    def test_capability_deltas_reports_missing_and_outdated(self) -> None:
        target = make_target()
        deltas = capability_deltas(make_pure_arch(), target)
        self.assertIn("configuration-ownership", deltas["missing"])
        self.assertEqual(deltas["outdated"], [])  # nothing registered yet

        stale = capability_deltas(make_old_sunshine(schema=1), target)
        self.assertEqual(stale["missing"], [])
        self.assertEqual(len(stale["outdated"]), len(COMPONENT_CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
