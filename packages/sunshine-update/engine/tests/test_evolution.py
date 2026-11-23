"""Tests for the evolutionary milestone subsystem and audited stability tools."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evolution import (  # noqa: E402
    EvolutionUpdater,
    HookOutcome,
    HookSpec,
    MilestoneRegistry,
    MilestoneRepository,
    MilestoneVersion,
    load_scheme,
    run_hooks,
)
from src.evolution.artifacts import (  # noqa: E402
    ArtifactRecord,
    ContentAddressedArchive,
)
from src.evolution.baseline import (  # noqa: E402
    ARCH_2026_BASELINE,
    BASELINE_ID,
    replace_baseline,
)
from src.evolution.compatibility import (  # noqa: E402
    CompatibilityEngine,
    SourceProfile,
    SupportPolicy,
)
from src.evolution.events import EventCatalog, EvolutionEvent  # noqa: E402
from src.evolution.inventory import (  # noqa: E402
    INVENTORY_SCHEMA,
    Inventory,
    from_observed,
    upgrade_inventory,
)
from src.evolution.hooks import HookRunner  # noqa: E402
from src.evolution.invariants import check_invariants  # noqa: E402
from src.evolution.ledger import (  # noqa: E402
    ConfigResourceChange,
    EvolutionChanges,
    EvolutionLedger,
    EvolutionRecord,
)
from src.evolution.milestones import HOOK_PHASES  # noqa: E402
from src.evolution.qualification import (  # noqa: E402
    REQUIRED_RELEASE_ARTIFACTS,
    QualificationRecord,
    SourceCapabilities,
    release_gate,
)
from src.evolution.recovery import (  # noqa: E402
    BRIDGE_ID,
    RECOVERY_BASELINE_ID,
    DataPreservationPlan,
    RecoveryBridge,
    qualification_from_results,
    recovery_path,
    reconstruction_spec,
)
from src.evolution.release import ReleaseIdentity, content_digest  # noqa: E402
from src.evolution.scheme import Scheme  # noqa: E402
from src.evolution.staging import (  # noqa: E402
    PHASES,
    WorkflowRun,
    assess_staging,
)
from src.evolution.target_resolver import TargetResolver  # noqa: E402
from src.evolution.tools.transaction_log import Differential  # noqa: E402
from src.evolution.tools import (  # noqa: E402
    ChannelPolicy,
    Seal,
    ServiceSpec,
    ServiceSupervisor,
    SnapshotManager,
    TransactionLog,
    build_seal,
    guard_update,
    sign_seal,
    verify_seal,
    verify_seal_signature,
)
from src.evolution.transitions import TransitionRegistry, TransitionSpec  # noqa: E402
from src.evolution.versions import VersionSet  # noqa: E402
from src.milestone_cli import main as milestone_main  # noqa: E402

SIGNER = "TESTFINGERPRINT0001"


def fake_sign(fingerprint: str, payload: bytes) -> str:
    return hashlib.sha256((fingerprint + "|" + payload.hex()).encode("utf-8")).hexdigest()


def fake_verify(fingerprint: str, payload: bytes, signature: str) -> bool:
    return fake_sign(fingerprint, payload) == signature


def record(
    index: int,
    release_id: str,
    *,
    desired: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
    services: tuple[str, ...] = (),
    disabled: tuple[str, ...] = (),
    resources: tuple[ConfigResourceChange, ...] = (),
    policies: dict[str, bool] | None = None,
    transitions: tuple[str, ...] = (),
    validations: tuple[str, ...] = (),
    parent: str | None = None,
) -> EvolutionRecord:
    if parent is not None:
        actual_parent: str | None = parent
    elif index > 1:
        actual_parent = f"e{index - 1:03d}"
    else:
        actual_parent = None
    return EvolutionRecord(
        evolution=index,
        release_id=release_id,
        release_version=str(index),
        parent=actual_parent,
        baseline_epoch=BASELINE_ID,
        manifest_schema=1,
        changes=EvolutionChanges(
            packages_desired=desired,
            packages_removed=removed,
            services_desired=services,
            services_disabled=disabled,
            configuration=resources,
            policies=frozenset((policies or {}).items()),
        ),
        transitions=transitions,
        validations=validations,
    )


def ledger() -> EvolutionLedger:
    return EvolutionLedger([
        record(1, "e001", desired=("sunshine-base",), services=("sunshine-apps.service",),
               policies={"preserve_user_configuration": False},
               resources=(ConfigResourceChange("sunshine-config", path="/etc/sunshine.toml", schema=2),)),
        record(2, "e002", desired=("sunshine-update",), removed=("sunshine-base",),
               services=("sunshine-apps.service", "sunshine-update.service"),
               policies={"require_signed_packages": False}),
        record(3, "e003", desired=("sunshine-base",), resources=(
            ConfigResourceChange("sunshine-config", state="absent"),)),
    ])


class VersionAndSchemeTests(unittest.TestCase):
    def test_version_parsing_and_ordering(self) -> None:
        self.assertEqual(str(MilestoneVersion.parse("v1.10")), "1.10")
        self.assertEqual(MilestoneVersion.parse("sunshine-2026.1"), MilestoneVersion((2026, 1)))
        self.assertLess(MilestoneVersion.parse("0.9"), MilestoneVersion.parse("1.0"))
        for bad in ("", "abc", "1.x"):
            with self.assertRaises(ValueError):
                MilestoneVersion.parse(bad)

    def test_chain_resolution_and_fail_closed_errors(self) -> None:
        registry = MilestoneRegistry.from_dict({
            "current": "1.0",
            "aliases": {"old-sunshine": "0.9"},
            "milestones": [
                {"version": "0", "predecessor": ""},
                {"version": "0.9", "predecessor": "0"},
                {"version": "1.0", "predecessor": "0.9"},
            ],
        })
        self.assertEqual([str(m.version) for m in registry.chain("0", "1.0")], ["0.9", "1.0"])
        self.assertEqual([str(m.version) for m in registry.chain("0.5", "0.9")], ["0.9"])
        self.assertEqual(registry.chain("old-sunshine", "0.9"), [])
        with self.assertRaisesRegex(ValueError, "downgrade"):
            registry.chain("1.0", "0.9")
        with self.assertRaisesRegex(ValueError, "unknown milestone or release"):
            registry.chain("not-a-release", "1.0")

    def test_bad_registries_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MilestoneRegistry.from_dict({"current": "1.0", "milestones": [
                {"version": "0", "predecessor": ""},
                {"version": "1.0", "predecessor": "0.5"},
            ]})
        with self.assertRaises(ValueError):
            MilestoneRegistry.from_dict({"current": "1.0", "milestones": [
                {"version": "0", "predecessor": ""},
                {"version": "1.0", "predecessor": "1.0"},
            ]})

    def test_bundled_scheme_and_scheme_cli(self) -> None:
        scheme = load_scheme()
        self.assertEqual(scheme.registry.current, MilestoneVersion((0, 9)))
        self.assertEqual(scheme.versions.migration_engine, "ME12")
        self.assertEqual(scheme.validate(), [])

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(milestone_main(["--milestones"]), 0)
        self.assertIn("sunshine-current", buffer.getvalue())

        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                rc = milestone_main([
                    "--state-root", tmp, "--from", "0", "--upgrade-to", "0.9", "--dry-run",
                ])
            self.assertEqual(rc, 0)
            self.assertIn("dry run", buffer.getvalue())

    def test_version_set_validation(self) -> None:
        good = VersionSet("E040", "ME12", "INV7", "EVS4", "TC18", BASELINE_ID)
        self.assertEqual(good.validate(), [])
        self.assertEqual(len(good.digest), 64)
        bad = VersionSet("40", "ME12", "INV7", "EVS4", "TC18", BASELINE_ID)
        self.assertTrue(any("os_evolution" in error for error in bad.validate()))

    def test_invariants_fail_closed_on_missing_evidence(self) -> None:
        good = {
            "target_state_driven": True, "mandatory_sequential_replay": False,
            "ledger_immutable": True, "ledger_digest": "abc", "ledger_mutated": False,
            "engine_version": "ME12", "os_evolution": "E040",
            "installation_authoritative": True, "inventory_hash": "abc",
            "staging_when_possible": True, "all_operations_recoverable": True,
            "historical_artifacts_archived": True, "support_qualified": True,
            "support_assumed": False, "repeatable": True, "idempotency_policies": True,
            "user_data_separate": True,
        }
        self.assertTrue(check_invariants(good).passed)
        self.assertFalse(check_invariants({}).passed)
        self.assertEqual(len(check_invariants(good).results), 10)


class ResolverAndLedgerTests(unittest.TestCase):
    def test_ledger_rejects_gaps_and_contradictions(self) -> None:
        self.assertEqual(ledger().validate(), [])
        with self.assertRaisesRegex(ValueError, "contiguous"):
            EvolutionLedger([record(2, "e002"), record(3, "e003")])
        with self.assertRaisesRegex(ValueError, "both desired and removed"):
            EvolutionLedger([record(
                1, "e001", desired=("a",), removed=("a",),
            )])

    def test_target_resolution_is_deterministic_and_cumulative(self) -> None:
        resolver = TargetResolver(ledger())
        first = resolver.resolve(evolution=1)
        second = resolver.resolve(evolution=2)
        third = resolver.resolve(evolution=3)
        self.assertEqual(first.to_dict(), resolver.resolve(evolution=1).to_dict())
        self.assertIn("sunshine-base", first.packages)
        self.assertNotIn("sunshine-base", second.packages)
        self.assertIn("sunshine-update", second.packages)
        self.assertIn("sunshine-base", third.packages)
        self.assertNotIn("sunshine-config", third.resources)
        self.assertFalse(first.policies["preserve_user_configuration"])
        self.assertFalse(second.policies["require_signed_packages"])
        self.assertTrue(second.policies["preserve_user_packages"])
        self.assertEqual(TargetResolver.validate_resolved(third), [])
        self.assertEqual(len(resolver.resolve_all()), 3)

    def test_resolved_target_rejects_contradictions(self) -> None:
        target = TargetResolver(ledger()).resolve(evolution=2)
        bad = target.__class__(**{
            **target.__dict__,
            "packages": frozenset({"both"}),
            "removed_packages": frozenset({"both"}),
        })
        self.assertTrue(any("both present and removed" in e
                            for e in TargetResolver.validate_resolved(bad)))

    def test_release_identity_is_content_addressed(self) -> None:
        identity = ReleaseIdentity.create(
            release_id="sunshine-2026.2", evolution_index=2,
            baseline_epoch=BASELINE_ID, manifest_schema=1,
            metadata={"channel": "stable"}, release_version="2026.2",
        )
        self.assertEqual(identity.validate(), [])
        self.assertEqual(len(identity.content_digest), 64)
        changed = ReleaseIdentity.create(
            release_id="sunshine-2026.2", evolution_index=2,
            baseline_epoch=BASELINE_ID, manifest_schema=1,
            metadata={"channel": "testing"}, release_version="2026.2",
        )
        self.assertNotEqual(identity.content_digest, changed.content_digest)
        self.assertEqual(str(identity.milestone), "2")

    def test_event_catalog_from_ledger_is_stable(self) -> None:
        catalog = EventCatalog.from_ledger(ledger())
        self.assertEqual(catalog.digest(), EventCatalog.from_ledger(ledger()).digest())
        self.assertTrue(catalog.events)
        with self.assertRaises(ValueError):
            EventCatalog([EvolutionEvent.create(
                release_id="e001", domain="packages", entity_id="x", operation="teleport",
            )])


class InventoryCompatibilityTests(unittest.TestCase):
    def test_inventory_schema_conversion_is_forward_only(self) -> None:
        inv = Inventory(schema=1, repositories={"configured": ["sunshine[signed]"]})
        upgraded = upgrade_inventory(inv, 2)
        self.assertEqual(upgraded.schema, 2)
        self.assertEqual(upgraded.repositories["signing"]["verified"], ["sunshine[signed]"])
        with self.assertRaisesRegex(ValueError, "downgrade"):
            upgrade_inventory(upgraded, 1)
        with self.assertRaisesRegex(ValueError, "no inventory converter"):
            upgrade_inventory(upgraded, 9)

    def test_from_observed_is_lossless_about_capabilities(self) -> None:
        class Observation:
            detected = "yes"
            confidence = "high"
            status = "present"
            evidence = ["pacman -Q"]

        class Observed:
            distribution = "archlinux"
            architecture = "x86_64"
            init_system = "systemd"
            package_manager = "pacman"
            packages = {"linux": "6.1"}
            foreign_packages = ["cargo"]
            repositories = ["core"]
            repository_generation = 1
            capabilities = {"signed", "boot-systemd"}
            observations = {"kernel": Observation()}
            users = ["sunshine"]
            groups = {"wheel": ["sunshine"]}
            home_directories = ["/home/sunshine"]

        inv = from_observed(Observed())
        self.assertEqual(inv.schema, INVENTORY_SCHEMA)
        self.assertEqual(inv.identity["distribution"], "archlinux")
        self.assertEqual(inv.runtime["capabilities"], ["boot-systemd", "signed"])
        self.assertEqual(inv.runtime["observations"]["kernel"]["confidence"], "high")
        self.assertEqual(inv.users["groups"], {"wheel": ["sunshine"]})

    def test_compatibility_mode_and_tiers(self) -> None:
        bootstrap = Inventory(identity={"distribution": "archlinux", "package_manager": "pacman"},
                              repositories={"configured": ["core"]})
        evolving = Inventory(
            identity={"distribution": "SunshineOS", "package_manager": "pacman"},
            migration_metadata={"sunshine_adopted": True},
        )
        engine = CompatibilityEngine()
        self.assertEqual(engine.select_mode(bootstrap), "bootstrap")
        self.assertEqual(engine.select_mode(evolving), "evolution")
        report = engine.classify(bootstrap, age_years=5, evolution_count=12)
        self.assertTrue(report.supported)
        self.assertEqual(report.profile, "arch")
        self.assertEqual(report.support_tier, "qualified")

        unsupported_pm = Inventory(identity={"package_manager": "apt"})
        self.assertFalse(engine.classify(unsupported_pm).supported)

        beyond = engine.classify(bootstrap, age_years=30, evolution_count=120)
        self.assertFalse(beyond.supported)
        self.assertTrue(any("architectural horizon" in reason for reason in beyond.reasons))

        policy = SupportPolicy()
        self.assertTrue(policy.within_minimum(9, 100))
        self.assertTrue(policy.within_architectural(20, 100))
        self.assertFalse(policy.within_architectural(21, 100))

        low = SourceCapabilities()
        self.assertEqual(low.tier(), "unsupported")
        good = SourceCapabilities(
            package_database="compatible", package_manager="compatible",
            boot_architecture="supported", filesystem="supported",
            repository_trust="reconstructable", inventory="complete",
            configuration_schema="identified", migration_workspace="available",
        )
        self.assertEqual(good.tier(), "qualified")
        no_workspace = good.__class__(**{**good.__dict__, "migration_workspace": "unavailable"})
        self.assertEqual(no_workspace.tier(), "qualified_with_intervention")

        hint = SourceProfile("arch", ("archlinux",), ("core",)).confidence_for(bootstrap)
        self.assertEqual(hint, "high")

    def test_transition_registry_preserves_retired_knowledge(self) -> None:
        registry = TransitionRegistry([
            TransitionSpec("net-1-2", "network", 1, 2, ("convert",)),
            TransitionSpec("net-2-3", "network", 2, 3, ("migrate",)),
            TransitionSpec("net-1-3-direct", "network", 1, 3, ("direct",)),
            TransitionSpec("boot-old", "boot", 1, 2, (), supported=False,
                           retired_reason="replaced by declarative boot profile"),
        ])
        self.assertEqual(registry.validate(), [])
        chain = registry.chain("network", 1, 3)
        self.assertEqual([step.id for step in chain], ["net-1-3-direct"])
        self.assertEqual([step.id for step in registry.chain("network", 1, 2)], ["net-1-2"])
        self.assertIsNone(registry.find("boot", 1, 2))
        self.assertEqual(registry.any_for("boot", 1, 2).retired_reason,
                         "replaced by declarative boot profile")
        with self.assertRaises(ValueError):
            TransitionRegistry([
                TransitionSpec("a", "net", 1, 2, ("x",)),
                TransitionSpec("b", "net", 1, 2, ("y",)),
            ])


class HookRepositoryUpdaterTests(unittest.TestCase):
    def test_hooks_are_ordered_journaled_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seen: list[str] = []
            def executor(argv: list[str], _env: dict[str, str], _timeout: int):
                seen.extend(argv)
                return 0, "", ""

            runner = HookRunner(tmp, executor=executor)
            hooks = [
                HookSpec("a", "pre_upgrade", "echo a", required=True),
                HookSpec("b", "pre_upgrade", "true"),
                HookSpec("c", "post_milestone", "true"),
            ]
            outcomes = runner.run(hooks, "pre_upgrade")
            self.assertEqual([o.hook_id for o in outcomes], ["a", "b"])
            self.assertEqual(len(runner.history()), 2)
            self.assertEqual(set(HOOK_PHASES), {"pre_upgrade", "post_milestone", "on_failure"})

            self.assertTrue(any("network" in e for e in runner.validate_command("curl https://x")))
            self.assertTrue(any("allowlist" in e for e in runner.validate_command("rm -rf /")))
            adapter = HookSpec("adapt", "pre_upgrade", adapter="signed-adapter", required=True)
            self.assertFalse(runner.run_one(adapter).ok)

            failing = HookRunner(tmp, executor=lambda *_: (1, "", "boom"))
            stopped = failing.run([
                HookSpec("bad", "pre_upgrade", "echo bad", required=True),
                HookSpec("later", "pre_upgrade", "echo later"),
            ], "pre_upgrade")
            self.assertEqual([o.hook_id for o in stopped], ["bad"])

    def test_repository_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scheme = load_scheme()
            path = Path(tmp) / "manifest.json"
            MilestoneRepository.publish(
                path, scheme, 1, signed_by=SIGNER, sign=fake_sign,
                artifacts={"scheme.toml": "digest"},
            )
            repo = MilestoneRepository(path)
            _manifest, report = repo.verify_file(
                trusted_keys={SIGNER}, verifier=fake_verify, expected_scheme=scheme,
            )
            self.assertTrue(report.passed, report.errors)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["payload"]["current"] = "9.9"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            _manifest, report = repo.verify_file(
                trusted_keys={SIGNER}, verifier=fake_verify, expected_scheme=scheme,
            )
            self.assertFalse(report.passed)
            self.assertTrue(any("signature" in e for e in report.errors))

    def test_updater_success_dry_run_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scheme = load_scheme()
            def runner(state_root: str):
                return HookRunner(state_root, executor=lambda *_: (0, "", ""))

            updater = EvolutionUpdater(
                scheme, tmp, hook_runner=runner(tmp),
                apply_fn=lambda: (True, "applied"),
                verify_fn=lambda: (True, "verified"),
                checkpoint_fn=lambda: "checkpoint-ref",
                restore_fn=lambda ref: (True, f"restored {ref}"),
            )
            report = updater.upgrade("0", "0.9")
            self.assertTrue(report.ok, report.error)
            self.assertEqual(report.chain, ("0.9",))
            self.assertFalse(report.rolled_back)
            self.assertEqual(len(report.journal_id), 64)
            self.assertTrue(list(Path(tmp).glob("journal-*.json")))

            dry = updater.upgrade("0", "0.9", dry_run=True)
            self.assertTrue(dry.dry_run)
            self.assertEqual(dry.hook_outcomes, [])

            failing = EvolutionUpdater(
                scheme, tmp, hook_runner=runner(tmp),
                apply_fn=lambda: (False, "apply failed"),
                verify_fn=lambda: (True, "unused"),
                checkpoint_fn=lambda: "cp",
                restore_fn=lambda ref: (True, "restored"),
            )
            bad = failing.upgrade("0", "0.9")
            self.assertFalse(bad.ok)
            self.assertTrue(bad.rolled_back)
            self.assertTrue(any(o["phase"] == "on_failure" for o in bad.hook_outcomes))
            journal_payload = json.loads(
                (Path(tmp) / f"journal-{bad.journal_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(journal_payload["state"], "RolledBack")

            restored: list[str] = []
            guarded = EvolutionUpdater(
                scheme, tmp, hook_runner=runner(tmp),
                apply_fn=lambda: (False, "apply failed"),
                verify_fn=lambda: (True, "unused"),
                checkpoint_fn=lambda: "cp",
                checkpoint_verify_fn=lambda ref: (False, "tampered checkpoint"),
                restore_fn=lambda ref: (restored.append(ref) or (True, "restored")),
            )
            guard_report = guarded.upgrade("0", "0.9")
            self.assertFalse(guard_report.rolled_back)
            self.assertEqual(restored, [])
            self.assertIn("checkpoint integrity", guard_report.error)

            no_apply = EvolutionUpdater(
                scheme, tmp, hook_runner=runner(tmp),
                verify_fn=lambda: (True, "verified"),
                checkpoint_fn=lambda: "cp", restore_fn=lambda ref: (True, "restored"),
            )
            dry_bad = no_apply.upgrade("0", "0.9", dry_run=True)
            self.assertFalse(dry_bad.ok)
            self.assertIn("apply function", dry_bad.error)
            self.assertEqual(dry_bad.hook_outcomes, [])

            downgrade = updater.upgrade("1.0", "0.9")
            self.assertFalse(downgrade.ok)
            self.assertIn("downgrade", downgrade.error)


class ArtifactRecoveryQualificationTests(unittest.TestCase):
    def test_artifact_archive_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "artifact.bin"
            source.write_bytes(b"sunshine artifact")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            record = ArtifactRecord(
                artifact_id="baseline-iso", artifact_type="baseline_iso",
                content_hash=digest, size=source.stat().st_size,
                signature="sig", signer=SIGNER, retention_class="A",
            )
            archive = ContentAddressedArchive(Path(tmp) / "archive")
            destination = archive.store(source, record)
            self.assertEqual(destination.name, digest)
            self.assertTrue(archive.verify(record)["passed"])
            self.assertTrue(archive.verify(record, require_signature=True)["passed"])
            unsigned = record.__class__(**{**record.__dict__, "signature": ""})
            self.assertFalse(archive.verify(unsigned, require_signature=True)["passed"])
            destination.write_bytes(b"tampered")
            self.assertFalse(archive.verify(record)["passed"])
            self.assertTrue(archive.manifest([record])["artifacts"])

    def test_baseline_fail_closed_and_epoch_replacement(self) -> None:
        self.assertTrue(ARCH_2026_BASELINE.validate())
        with tempfile.TemporaryDirectory() as tmp:
            iso = Path(tmp) / "arch.iso"
            iso.write_bytes(b"iso")
            self.assertFalse(ARCH_2026_BASELINE.verify_iso(iso).passed)
        with self.assertRaisesRegex(ValueError, "new epoch id"):
            replace_baseline(ARCH_2026_BASELINE, ARCH_2026_BASELINE)

    def test_recovery_lineage_and_bridge_validation(self) -> None:
        path = recovery_path(RECOVERY_BASELINE_ID, "E040")
        self.assertEqual(path[1], BRIDGE_ID)
        self.assertEqual(path[2], BASELINE_ID)
        self.assertEqual(path[-1], "E040")
        self.assertEqual(len(reconstruction_spec()), 12)

        invalid = RecoveryBridge()
        self.assertTrue(invalid.validate())
        valid = RecoveryBridge(
            independent_toolchain=True, artifact_manifest_hash="a" * 64,
            supported_conditions=("offline-media",), qualified=True,
        )
        self.assertEqual(valid.validate(), [])

        plan = DataPreservationPlan(include=("/home",), exclude=("/home/.cache",), home_separate=True)
        self.assertEqual(plan.validate(), [])
        bad_plan = DataPreservationPlan(include=("/home",), exclude=("/home",), home_separate=False)
        self.assertTrue(bad_plan.validate())

        qualification = qualification_from_results(
            RECOVERY_BASELINE_ID,
            [(step.domain, True, "ok") for step in reconstruction_spec()],
            True,
        )
        self.assertTrue(qualification.qualified)

    def test_qualification_gate_requires_evidence(self) -> None:
        good = SourceCapabilities(
            package_database="compatible", package_manager="compatible",
            boot_architecture="supported", filesystem="supported",
            repository_trust="verified", inventory="complete",
            configuration_schema="identified", migration_workspace="available",
        )
        self.assertEqual(good.tier(), "qualified")
        record = QualificationRecord(
            source_identity="B0", source_inventory_hash="a" * 64,
            target_identity="E040", target_manifest_hash="b" * 64,
            engine_version="ME12", transition_catalog_version="TC18",
            artifact_manifest_hash="c" * 64, support_tier="qualified",
            layers=("unit", "vm_migration", "fault_injection", "recovery"),
            validation_result="passed", failure_recovery_result="passed",
            execution_result="passed",
        )
        self.assertEqual(record.validate(), [])
        qualifications = []
        for source in ("B0", "E001", "E039", "external-arch"):
            clone = QualificationRecord(**{**record.__dict__, "source_identity": source})
            qualifications.append(clone)
        artifacts = {name: "present" for name in REQUIRED_RELEASE_ARTIFACTS}
        report = release_gate(artifacts, qualifications, load_scheme().versions)
        self.assertTrue(report.passed, report.to_dict())

        missing = dict(artifacts)
        missing.pop("artifact_integrity_manifest")
        self.assertFalse(release_gate(missing, qualifications, load_scheme().versions).passed)
        self.assertFalse(release_gate(artifacts, qualifications[:2], load_scheme().versions).passed)

    def test_static_qualification_fixtures_drive_the_release_gate(self) -> None:
        fixture_dir = ROOT / "fixtures" / "qualification"
        qualified = SourceCapabilities.from_dict(json.loads(
            (fixture_dir / "source-capabilities.qualified.json").read_text(encoding="utf-8")
        ))
        intervention = SourceCapabilities.from_dict(json.loads(
            (fixture_dir / "source-capabilities.intervention.json").read_text(encoding="utf-8")
        ))
        self.assertEqual(qualified.tier(), "qualified")
        self.assertEqual(intervention.tier(), "qualified_with_intervention")

        artifacts = json.loads(
            (fixture_dir / "release-artifacts.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(artifacts), set(REQUIRED_RELEASE_ARTIFACTS))
        records = [
            QualificationRecord(**item)
            for item in json.loads(
                (fixture_dir / "qualification-records.json").read_text(encoding="utf-8")
            )
        ]
        self.assertEqual([record.validate() for record in records], [[]] * len(records))
        gate = release_gate(artifacts, records, load_scheme().versions)
        self.assertTrue(gate.passed, gate.to_dict())

        tampered = [record.__class__(**{
            **record.__dict__, "failure_recovery_result": "skipped"
        }) for record in records]
        self.assertFalse(release_gate(artifacts, tampered, load_scheme().versions).passed)

    def test_staging_and_workflow_phases(self) -> None:
        btrfs = Inventory(storage={"filesystem": "btrfs", "can_subvolume": True})
        self.assertEqual(assess_staging(btrfs, mode="bootstrap").strategy, "staged_root")
        ext4 = Inventory(storage={"filesystem": "ext4"})
        self.assertEqual(assess_staging(ext4, mode="evolution").strategy, "in_place")
        self.assertEqual(assess_staging(btrfs, recovery_needed=True).strategy,
                         "recovery_reconstruction")
        with self.assertRaises(ValueError):
            assess_staging(ext4, forced="btrfs")

        workflow = WorkflowRun("staged_root")
        for phase in PHASES:
            workflow.advance(phase)
        self.assertTrue(workflow.done)
        with self.assertRaises(ValueError):
            WorkflowRun("staged_root").advance("Commit")
        workflow2 = WorkflowRun("in_place")
        workflow2.abort("ValidateStaged")
        self.assertFalse(workflow2.done)
        with self.assertRaises(ValueError):
            workflow2.advance("ValidateStaged")


class StabilityToolsTests(unittest.TestCase):
    def test_sealed_state_detects_additions_and_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            root.mkdir()
            target = root / "policy.toml"
            target.write_text("require_signatures = true\n", encoding="utf-8")
            seal = build_seal(root)
            self.assertTrue(verify_seal(root, seal).passed)

            signed = sign_seal(seal, SIGNER, fake_sign)
            self.assertTrue(verify_seal_signature(signed, {SIGNER}, fake_verify).passed)
            self.assertFalse(verify_seal_signature(signed, set(), fake_verify).passed)

            target.write_text("require_signatures = false\n", encoding="utf-8")
            report = verify_seal(root, signed)
            self.assertFalse(report.passed)
            self.assertIn("policy.toml", report.modified)

            (root / "extra").write_text("x", encoding="utf-8")
            self.assertTrue(verify_seal(root, seal).added)

    def test_snapshot_manager_uses_argv_and_journals_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls: list[list[str]] = []
            def executor(argv):
                calls.append(list(argv))
                if argv[:4] == ["btrfs", "subvolume", "snapshot", "-r"] or (
                    argv[0] == "tar" and "-cf" in argv
                ):
                    destination = Path(argv[argv.index("-cf") + 1] if "-cf" in argv else argv[-1])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(b"snapshot")
                elif argv[0] == "rm":
                    Path(argv[-1]).unlink(missing_ok=True)
                return 0, "", ""

            manager = SnapshotManager(Path(tmp) / "state", executor=executor, can_snapshot=True)
            first = manager.create("/target", "before", backend="btrfs",
                                   metadata={"reason": "pre-upgrade"})
            second = manager.create("/target", "after", backend="tar")
            self.assertEqual(first.backend, "btrfs")
            self.assertEqual(second.backend, "tar")
            self.assertEqual(calls[0][:5], ["btrfs", "subvolume", "snapshot", "-r", "/target"])
            self.assertEqual(manager.restore("before", "/restored")[0:3],
                             ["btrfs", "subvolume", "snapshot"])
            self.assertEqual(manager.prune(keep=1), ["before"])
            self.assertEqual([r.name for r in manager.list()], ["after"])
            self.assertTrue(manager.space_report(1).enough)

            with self.assertRaisesRegex(ValueError, "duplicate"):
                manager.create("/target", "after")
            with self.assertRaisesRegex(ValueError, "not available"):
                SnapshotManager(Path(tmp) / "state2", executor=executor).create(
                    "/target", "x", backend="btrfs"
                )

    def test_channel_guard_fails_closed(self) -> None:
        context = {
            "channel": "stable", "signed": True, "verification_passed": True,
            "artifact_age_days": 7, "recovery_available": True,
            "rollback_available": True, "support_tier": "qualified",
        }
        self.assertTrue(guard_update(context).allowed)
        self.assertFalse(guard_update({**context, "signed": False}).allowed)
        self.assertFalse(guard_update({**context, "artifact_age_days": 0}).allowed)
        self.assertFalse(guard_update({**context, "channel": "nightly"}).allowed)
        permissive = ChannelPolicy(
            allowed_channels=("stable", "testing"), minimum_age_days=0,
            require_qualified_support=False,
        )
        self.assertTrue(guard_update({**context, "channel": "testing",
                                      "artifact_age_days": 0}, permissive).allowed)

    def test_transaction_log_commit_open_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            compensated: list[str] = []
            log = TransactionLog(
                tmp,
                compensate_fn=lambda name, diff: (compensated.append(name) or True, "ok"),
            )
            session = log.begin("migrate-1", {"target": "E040"})
            log.record(session, Differential(
                "op1", "/etc/a", "old", "new", True, "restore-a"
            ))
            log.record(session, Differential(
                "op2", "/etc/b", "old", "new", True, "restore-b"
            ))
            self.assertEqual(len(log.open_sessions()), 1)
            self.assertEqual(log.rollback(session), ["op2", "op1"])
            self.assertEqual(compensated, ["restore-b", "restore-a"])
            self.assertEqual(log.open_sessions(), [])
            self.assertTrue(any(e["event"] == "ROLLBACK_COMPLETE" for e in log.events()))

            committed = log.begin("migrate-2")
            log.commit(committed)
            self.assertEqual(log.open_sessions(), [])
            with self.assertRaises(ValueError):
                log.record(committed, Differential("op3", "/etc/c", "old", "new"))

            crash = log.begin("crash")
            log.record(crash, Differential(
                "op4", "/etc/d", "old", "new", False, "irreversible"
            ))
            self.assertEqual([s.transaction_id for s in log.open_sessions()], ["crash"])

    def test_service_supervision_plans_are_deterministic(self) -> None:
        spec = ServiceSpec(
            unit="sunshine-apps.service", desired="enabled", classification="essential",
            environment={"SUNSHINE_PROFILE": "hyprland"},
        )
        supervisor = ServiceSupervisor()
        plans = supervisor.plan([spec])
        self.assertEqual(plans[0].commands, (
            ("systemctl", "enable", "sunshine-apps.service"),
            ("systemctl", "start", "sunshine-apps.service"),
        ))
        self.assertIn("Restart=on-failure", plans[0].drop_in)
        self.assertEqual(supervisor.validate_coverage(
            ["sunshine-apps.service"], plans, essential_services=["sunshine-apps.service"]
        ), [])
        self.assertTrue(supervisor.validate_coverage(["missing.service"], plans))
        with self.assertRaises(ValueError):
            supervisor.plan([ServiceSpec(unit="../../etc/passwd")])


if __name__ == "__main__":
    unittest.main()
