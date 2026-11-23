"""Unit/integration tests for the transactional executor (stdlib unittest only)."""
from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.core import Confidence, JournalEntry, OpType, Operation, Plan, Status  # noqa: E402
from src.executor import ExecutionContext, Journal, execute_plan, dispatch  # noqa: E402
from src.executor.primitives import Result, three_way_merge  # noqa: E402


MUTATING = ("pacman -S", "pacman -R", "systemctl enable", "systemctl disable",
            "mkinitcpio", "efibootmgr -c")


class FakeSystem:
    """Injected execute() implementing just enough Arch/systemd behaviour."""

    def __init__(self):
        self.commands: list[str] = []
        self.packages: set[str] = set()
        self.services: dict[str, str] = {}
        self.boot_entries: set[str] = set()
        self.upgraded = False
        self.fail_on: list[tuple[str, int, str, str]] = []
        self.root: Path | None = None

    def fail(self, needle: str, rc: int = 1, err: str = "injected failure"):
        self.fail_on.append((needle, rc, "", err))

    def __call__(self, cmd: str) -> tuple[int, str, str]:
        self.commands.append(cmd)
        for needle, rc, out, err in self.fail_on:
            if needle in cmd:
                return rc, out, err
        args = shlex.split(cmd)
        if cmd.startswith("pacman -Syu"):
            self.upgraded = True
            return 0, ":: Synchronizing package databases...\n", ""
        if cmd.startswith("pacman -Rs"):
            for pkg in args[3:]:
                self.packages.discard(pkg)
            return 0, "removed " + " ".join(args[3:]) + "\n", ""
        if cmd.startswith("pacman -S --needed"):
            for pkg in args[3:]:
                self.packages.add(pkg)
            return 0, "installing " + " ".join(args[3:]) + "\n", ""
        if cmd.startswith("pacman -Q "):
            pkg = args[2]
            if pkg in self.packages:
                return 0, f"{pkg} 1.0-1\n", ""
            return 1, "", f"package '{pkg}' not found"
        if cmd.startswith("pacman --version"):
            return 0, "Pacman v6.1.0", ""
        if cmd.startswith("systemctl is-enabled"):
            unit = args[2]
            state = self.services.get(unit, "disabled")
            return (0 if state == "enabled" else 1), state + "\n", ""
        if cmd.startswith("systemctl enable ") and len(args) == 3:
            self.services[args[2]] = "enabled"
            return 0, f"Created symlink for {args[2]}\n", ""
        if cmd.startswith("systemctl disable ") and len(args) == 3:
            self.services[args[2]] = "disabled"
            return 0, f"Removed symlink for {args[2]}\n", ""
        if cmd.startswith("systemctl is-system-running"):
            return 0, "running\n", ""
        if cmd.startswith("mkinitcpio"):
            if self.root is not None:
                if "-g" in args:
                    image = self.root / Path(args[args.index("-g") + 1].lstrip("/"))
                else:
                    preset = args[3] if len(args) > 3 else "linux"
                    image = self.root / "boot" / f"initramfs-{preset}.img"
                image.parent.mkdir(parents=True, exist_ok=True)
                image.write_bytes(b"initramfs")
            return 0, "Image generation complete.\n", ""
        if cmd.startswith("efibootmgr -v"):
            lines = [f"Boot000{i}* {label}" for i, label in enumerate(sorted(self.boot_entries), 1)]
            return 0, "\n".join(lines) + "\n", ""
        if cmd.startswith("efibootmgr -c"):
            label = args[args.index("-L") + 1]
            self.boot_entries.add(label)
            return 0, "Boot0009 created\n", ""
        if cmd.startswith("ls /boot/initramfs"):
            return (0, "/boot/initramfs-linux-fallback.img\n", "") if self.root and \
                list((self.root / "boot").glob("initramfs-*-fallback.img")) else (1, "", "")
        return 0, "", ""


def op(oid: str, kind: OpType, **kwargs) -> Operation:
    return Operation(id=oid, type=kind, **kwargs)


def standard_plan() -> Plan:
    """Bootstrap -> foundation -> core -> finalization (all safe operations)."""
    return Plan(
        id="std-plan",
        source={"distribution": "arch", "repository_generation": 1},
        target={"repository_generation": 2},
        operations=[
            op("cp", OpType.CREATE_CHECKPOINT, params={"label": "before-upgrade"}),
            op("upgrade", OpType.INSTALL_PACKAGES, params={"foundation": True}, requires=["cp"]),
            op("pkgs", OpType.INSTALL_PACKAGES, params={"packages": ["base", "linux"]}, requires=["upgrade"]),
            op("comp", OpType.REGISTER_COMPONENT, component="sunshine-core",
               params={"schema": 2}, requires=["pkgs"]),
            op("svc", OpType.ENABLE_SERVICE, component="sunshine-core",
               params={"unit": "sunshine.service"}, requires=["comp"]),
            op("check", OpType.VALIDATE_CAPABILITY, params={"capability": "pacman"}, requires=["svc"]),
        ],
    )


def removal_plan() -> Plan:
    return Plan(
        id="remove-plan",
        source={
            "distribution": "arch",
            "observations": {
                "vim": {"component": "vim", "detected": "vim", "confidence": "high",
                        "status": "installed", "evidence": ["pacman -Q vim"]},
            },
        },
        target={},
        operations=[op("rm", OpType.REMOVE_PACKAGES, destructive=True,
                       params={"packages": ["vim"]})],
    )


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sunshine-exec-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "state"
        self.root.mkdir(parents=True)
        self.fake = FakeSystem()
        self.fake.root = self.root

    def mutating_commands(self, fake: FakeSystem) -> list[str]:
        return [c for c in fake.commands if any(c.startswith(m) for m in MUTATING)]

    # ---------------------------------------------------------------- tests
    def test_successful_plan(self):
        result = execute_plan(standard_plan(), self.root, self.fake)

        self.assertEqual(result.status, "success", result.recovery_report)
        self.assertEqual(result.failed_op, "")
        self.assertEqual(set(result.completed_ops), {"cp", "upgrade", "pkgs", "comp", "svc", "check"})
        self.assertTrue(result.changed)
        self.assertEqual(self.fake.commands.count("pacman -Syu --noconfirm"), 1)
        self.assertIn("pacman -S --needed --noconfirm base linux", self.fake.commands)
        self.assertIn("systemctl enable sunshine.service", self.fake.commands)
        self.assertTrue((self.root / "etc/sunshine/components/sunshine-core.json").exists())
        self.assertTrue((self.root / "var/lib/sunshine/state/components.toml").exists())

        journal_file = self.root / "migration/journal/journal.jsonl"
        self.assertTrue(journal_file.exists())
        lines = journal_file.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 8)
        self.assertTrue(all(json.loads(line)["status"] for line in lines))
        self.assertTrue((self.root / "migration/transactions/completed/std-plan.json").exists())
        self.assertIn("No recovery required", result.recovery_report)
        self.assertIsNotNone(Journal(self.root, "std-plan").last_committed())

    def test_injected_failure_mid_plan(self):
        plan = standard_plan()
        self.fake.fail("systemctl enable", err="unit not found")
        result = execute_plan(plan, self.root, self.fake)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failed_op, "svc")
        self.assertIn("unit not found", result.errors[0])
        self.assertNotIn("check", result.completed_ops)
        self.assertIn("disable sunshine.service", " ".join(result.recovery_actions))
        self.assertIn("Recovery report for plan 'std-plan'", result.recovery_report)
        self.assertTrue((self.root / "migration/transactions/failed/std-plan.json").exists())
        state = Journal(self.root, plan.id).load()
        self.assertEqual(state.status, "failed")
        self.assertIn("svc", state.failed)
        self.assertGreaterEqual(len(state.entries), 6)

    def test_resume_after_interruption_reprobes_actual_state(self):
        plan = standard_plan()
        journal = Journal(self.root, plan.id)
        journal.start(plan)
        # Crash simulation: journal says two ops completed, but only one effect exists.
        journal.complete("upgrade", Result(True, "upgraded"), {
            "operation": "InstallPackages",
            "verify": {"kind": "packages", "targets": [], "expected_present": True},
        })
        journal.complete("pkgs", Result(True, "installed"), {
            "operation": "InstallPackages", "params": {"packages": ["base", "linux"]},
            "verify": {"kind": "packages", "targets": ["base", "linux"], "expected_present": True},
        })
        self.fake.packages.add("base")  # 'linux' is genuinely missing

        result = execute_plan(plan, self.root, self.fake, resume=True)

        self.assertEqual(result.status, "success", result.recovery_report)
        self.assertIn("upgrade", result.skipped_ops)
        self.assertNotIn("pkgs", result.skipped_ops)
        self.assertNotIn("pacman -Syu --noconfirm", self.fake.commands)
        self.assertIn("pacman -S --needed --noconfirm linux", self.fake.commands)
        self.assertTrue(any(e.operation == "Reconcile" for e in Journal(self.root, plan.id).load().entries))

    def test_resume_skips_only_effects_still_present(self):
        plan = standard_plan()
        first = execute_plan(plan, self.root, self.fake)
        self.assertEqual(first.status, "success")
        baseline = list(self.fake.commands)
        self.fake.commands.clear()

        second = execute_plan(plan, self.root, self.fake, resume=True)

        self.assertEqual(second.status, "success")
        self.assertEqual(set(second.skipped_ops), set(first.completed_ops))
        self.assertEqual(self.mutating_commands(self.fake), [])
        self.assertFalse(second.changed)
        self.assertEqual(baseline.count("pacman -Syu --noconfirm"), 1)

    def test_dry_run_changes_nothing(self):
        plan = removal_plan()
        plan.operations += [
            op("cp", OpType.CREATE_CHECKPOINT),
            op("kern", OpType.INSTALL_KERNEL, params={"version": "linux"}, requires=["cp"]),
            op("init", OpType.GENERATE_INITRAMFS, params={"preset": "linux"}, requires=["kern"]),
            op("boot", OpType.INSTALL_BOOT_ENTRY, params={"label": "Sunshine", "loader": "/EFI/linux.efi"},
               requires=["init"]),
        ]
        calls = []

        def callback(label):
            calls.append(label)
            return "should-not-be-called"

        result = execute_plan(plan, self.root, self.fake, checkpoint=callback, dry_run=True)

        self.assertEqual(result.status, "dry_run")
        self.assertFalse(result.changed)
        self.assertEqual(result.failed_op, "")
        self.assertEqual(self.mutating_commands(self.fake), [])
        self.assertEqual(calls, [])
        self.assertFalse((self.root / "migration").exists())
        self.assertFalse(list(self.root.rglob("*.json")))

    def test_idempotent_rerun_makes_no_changes(self):
        plan = standard_plan()
        first = execute_plan(plan, self.root, self.fake)
        self.assertTrue(first.changed)
        first_commands = list(self.fake.commands)
        self.fake.commands.clear()

        second = execute_plan(plan, self.root, self.fake)

        self.assertEqual(second.status, "success")
        self.assertFalse(second.changed)
        self.assertEqual(self.mutating_commands(self.fake), [])
        self.assertEqual(first_commands.count("pacman -Syu --noconfirm"), 1)

    def test_checkpoint_created_before_destructive_operation(self):
        plan = removal_plan()
        self.fake.packages.add("vim")
        events = []

        def callback(label):
            events.append(("checkpoint", label))
            return "snapshot-42"

        def tracked(cmd):
            events.append(("cmd", cmd))
            return self.fake(cmd)

        result = execute_plan(plan, self.root, tracked, checkpoint=callback)

        self.assertEqual(result.status, "success", result.recovery_report)
        self.assertIn("pacman -Rs --noconfirm vim", [c for kind, c in events if kind == "cmd"])
        cp_index = next(i for i, (kind, _) in enumerate(events) if kind == "checkpoint")
        rm_index = next(i for i, (kind, cmd) in enumerate(events)
                        if kind == "cmd" and cmd.startswith("pacman -Rs"))
        self.assertLess(cp_index, rm_index)
        entries = Journal(self.root, plan.id).load().entries
        cp_pos = next(i for i, e in enumerate(entries) if e.operation == "CreateCheckpoint")
        rm_pos = next(i for i, e in enumerate(entries) if e.operation == "RemovePackages")
        self.assertLess(cp_pos, rm_pos)

    def test_low_confidence_destructive_refused(self):
        plan = removal_plan()
        plan.source["observations"]["vim"]["confidence"] = "low"
        self.fake.packages.add("vim")

        result = execute_plan(plan, self.root, self.fake)

        self.assertEqual(result.status, "failed")
        self.assertIn("low-confidence", result.errors[0])
        self.assertFalse(any(c.startswith("pacman -R") for c in self.fake.commands))

    def test_partial_upgrade_refused(self):
        plan = Plan(
            id="partial", source={"repository_generation": 1}, target={"repository_generation": 2},
            operations=[op("pkgs", OpType.INSTALL_PACKAGES, params={"packages": ["base"]})],
        )
        result = execute_plan(plan, self.root, self.fake)
        self.assertEqual(result.status, "failed")
        self.assertIn("partial upgrade", result.errors[0])
        self.assertEqual(self.mutating_commands(self.fake), [])

    def test_user_config_preserved_with_merge_record(self):
        plan = Plan(id="cfg", source={}, target={}, operations=[
            op("cfg1", OpType.CREATE_CONFIGURATION,
               params={"name": "sunshine", "content": {"setting": 1}}),
        ])
        first = execute_plan(plan, self.root, self.fake)
        self.assertEqual(first.status, "success")
        target = self.root / "etc/sunshine/config/sunshine.conf"
        target.write_text(target.read_text(encoding="utf-8") + "# user note\n", encoding="utf-8")

        second = execute_plan(plan, self.root, self.fake)

        self.assertEqual(second.status, "success")
        self.assertIn("# user note", target.read_text(encoding="utf-8"))
        merges = list((self.root / "migration/merges").glob("*.json"))
        self.assertTrue(merges)
        self.assertTrue(any("preserve-ours" in p.read_text(encoding="utf-8") for p in merges))

    def test_three_way_merge_conflict_is_reported(self):
        ok, merged, strategy = three_way_merge("a\nb\nc\n", "a\nours\nc\n", "a\ntheirs\nc\n")
        self.assertFalse(ok)
        self.assertIn("overlapping", merged)

    def test_journal_entries_are_append_only(self):
        journal = Journal(self.root, "append")
        plan = Plan(id="append", source={}, target={}, operations=[
            op("a", OpType.CREATE_CHECKPOINT),
        ])
        journal.start(plan)
        journal.complete("a", Result(True, "done"), {"operation": "CreateCheckpoint"})
        before = journal.journal_file.read_text(encoding="utf-8")
        journal.complete("a", Result(True, "done again"), {"operation": "CreateCheckpoint"})
        after = journal.journal_file.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before))
        self.assertEqual(len(after.splitlines()), len(before.splitlines()) + 1)

    def test_dispatch_returns_result_for_every_op_type(self):
        context = ExecutionContext(state_root=self.root, execute=self.fake, dry_run=True)
        for kind in OpType:
            operation = op("x-" + kind.value, kind, component="demo",
                           params={"packages": ["base"], "unit": "demo.service", "capability": "pacman",
                                   "source_path": "etc/sunshine/old.conf"})
            result = dispatch(operation, context)
            self.assertIsInstance(result, Result, kind.value)
            self.assertTrue(result.ok, f"{kind.value}: {result.output}")

    def test_fallback_image_is_generated_when_preset_omits_it(self):
        # Upstream Sunshine/Arch presets declare only the default image, but
        # the target promises kernel-fallback. The executor must build it
        # explicitly without the autodetect hook.
        plan = removal_plan()
        plan.operations += [
            op("cp", OpType.CREATE_CHECKPOINT),
            op("kern", OpType.INSTALL_KERNEL, params={"version": "linux", "package": "linux"},
               requires=["cp"]),
            op("init", OpType.GENERATE_INITRAMFS, params={"preset": "linux", "fallback": True},
               requires=["kern"]),
        ]
        result = execute_plan(plan, self.root, self.fake)
        self.assertEqual(result.status, "success", result.errors)
        self.assertTrue(any("-g /boot/initramfs-linux-fallback.img" in c and "-S autodetect" in c
                            for c in self.fake.commands))
        self.assertTrue((self.root / "boot/initramfs-linux-fallback.img").exists())

    def test_system_root_separates_file_mutations_from_engine_state(self):
        # A live apply writes config into the real filesystem while keeping
        # journal/checkpoints in the state root. Both must be verifiable.
        system_root = Path(self.tmp.name) / "system"
        system_root.mkdir()
        state_root = Path(self.tmp.name) / "state2"
        state_root.mkdir()
        fake = FakeSystem()
        fake.root = system_root
        plan = Plan(id="root-split", source={}, target={}, operations=[
            op("cp", OpType.CREATE_CHECKPOINT),
            op("cfg", OpType.CREATE_CONFIGURATION,
               params={"name": "demo", "path": "etc/sunshine/config/demo.conf", "content": "ok\n"},
               requires=["cp"]),
        ])
        result = execute_plan(plan, state_root, fake, system_root=system_root)
        self.assertEqual(result.status, "success", result.errors)
        self.assertTrue((system_root / "etc/sunshine/config/demo.conf").exists())
        self.assertFalse((state_root / "etc/sunshine/config/demo.conf").exists())
        self.assertTrue((state_root / "migration/journal/journal.jsonl").exists())

    def test_initramfs_probe_uses_executor_not_state_root(self):
        # A live mkinitcpio writes to the real /boot, so a state-root-relative
        # path check would always report a false failure. Command probes are
        # answered by the injected executor (fixtures read their sandbox).
        journal = Journal(self.root, "initramfs-probe")
        journal.complete("init", Result(True, "generated"), {
            "operation": "GenerateInitramfs",
            "params": {"preset": "linux"},
            "verify": {"kind": "initramfs", "path": "boot/initramfs-linux.img",
                       "command": "ls /boot/initramfs-linux*.img", "expected_present": True},
        })
        self.assertFalse((self.root / "boot/initramfs-linux.img").exists())

        def present(cmd):
            self.assertEqual(cmd, "ls /boot/initramfs-linux*.img")
            return 0, "/boot/initramfs-linux.img\n/boot/initramfs-linux-fallback.img\n", ""

        actual = journal.read_actual_state(execute=present, op_ids=["init"])
        check = actual.checks["init"]
        self.assertTrue(check.present)
        self.assertEqual(check.expected_present, True)
        self.assertEqual(check.confidence, "high")
        self.assertTrue(any("ls /boot/initramfs-linux" in line for line in check.evidence))

        def absent(cmd):
            return 1, "", "no such file"

        check = journal.read_actual_state(execute=absent, op_ids=["init"]).checks["init"]
        self.assertFalse(check.present)  # fail closed when the image is really missing


if __name__ == "__main__":
    unittest.main()
