"""Runtime proof that signed adapters are sandboxed and journaled."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapters import AdapterLaunch, AdapterRegistry, build_sandbox_command  # noqa: E402
from src.core import OpType, Operation, Plan  # noqa: E402
from src.executor import execute_plan  # noqa: E402

FP = "AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555"


def verifier(fingerprint: str, _payload: bytes, signature: str) -> bool:
    return fingerprint == FP and signature in ("manifest-good", "artifact-good")


class AdapterRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sunshine-adapter-runtime-")
        self.base = Path(self.tmp.name)
        self.manifests = self.base / "manifests"
        self.artifacts = self.base / "artifacts"
        self.manifests.mkdir()
        self.artifacts.mkdir()
        artifact = self.artifacts / "recovery-adapter"
        artifact.write_bytes(b"#!/bin/sh\nexit 0\n")
        artifact.chmod(0o755)
        (self.manifests / "recovery.toml").write_text(f'''\
id = "recovery-adapter"
component = "recovery"
version = "1.0.0"
runtime = "rust"
operation = "MigrateConfiguration"
permissions = ["read-configuration", "write-managed-configuration"]
parameters = ["source_path", "target_path"]
provides = ["recovery-checkpoints"]

[artifact]
name = "recovery-adapter"
path = "recovery-adapter"
sha256 = "__DIGEST__"

[schema]
from = 1
to = 3

[signature]
manifest = "manifest-good"
manifest_signed_by = "{FP}"
artifact = "artifact-good"
artifact_signed_by = "{FP}"

[sandbox]
memory_mb = 64
cpu_percent = 25
timeout_seconds = 30
max_processes = 32
network = false
read_paths = ["/etc/sunshine"]
write_paths = ["/etc/sunshine/managed"]
'''.replace("__DIGEST__", __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()), encoding="utf-8")
        self.registry = AdapterRegistry.load(
            self.manifests,
            verifier=verifier,
            trusted_keys=(FP,),
            artifact_root=self.artifacts,
            stage_artifacts={"recovery-adapter"},
            contract_component_ids={"recovery"},
        )
        self.invocations: list = []

    def tearDown(self):
        self.tmp.cleanup()

    def launcher(self, invocation):
        self.invocations.append(invocation)
        return AdapterLaunch(True, "adapter ok", changed=True, metadata={"exit_code": 0})

    def failing_launcher(self, invocation):
        self.invocations.append(invocation)
        return AdapterLaunch(False, "adapter refused", metadata={"exit_code": 12})

    def make_plan(self):
        op = Operation(
            id="migrate-recovery",
            type=OpType.MIGRATE_CONFIGURATION,
            component="recovery",
            params={
                "adapter_id": "recovery-adapter",
                "source_path": "/etc/sunshine/recovery-v1.toml",
                "target_path": "recovery-v3.toml",
            },
        )
        return Plan("plan-adapter", source={}, target={}, operations=[op])

    def journal_details(self, state_root):
        records = []
        path = Path(state_root) / "migration" / "journal" / "journal.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            obj = json.loads(line)
            if obj.get("id") == "migrate-recovery":
                records.append(obj)
        return records

    def test_registry_verifies_signed_artifact_and_rechecks_it(self):
        adapter = self.registry.verify_invocation("recovery-adapter")
        self.assertEqual(adapter.manifest.runtime, "rust")
        (self.artifacts / "recovery-adapter").write_bytes(b"#!/bin/sh\ntampered\n")
        with self.assertRaises(ValueError) as ctx:
            self.registry.verify_invocation("recovery-adapter")
        self.assertIn("digest mismatch", str(ctx.exception))

    def test_sandbox_command_is_shell_free_and_least_privilege(self):
        adapter = self.registry.get("recovery-adapter")
        invocation = __import__("src.adapters", fromlist=["AdapterInvocation"]).AdapterInvocation(
            adapter=adapter,
            params={"source_path": "/etc/sunshine/a", "target_path": "/etc/sunshine/b"},
            state_root=self.base,
            dry_run=False,
            invocation_id="test-invocation",
        )
        command = build_sandbox_command(invocation)
        self.assertEqual(command[0], "systemd-run")
        self.assertIn("--scope", command)
        self.assertIn("--property=ProtectSystem=strict", command)
        self.assertIn("--property=MemoryMax=64M", command)
        self.assertIn("--property=CPUQuota=25%", command)
        self.assertIn("--property=RuntimeMaxSec=30", command)
        self.assertIn("--property=ReadOnlyPaths=/etc/sunshine", command)
        self.assertIn("--property=ReadWritePaths=/etc/sunshine/managed", command)
        self.assertNotIn("shell", command)
        self.assertNotIn("AF_INET", " ".join(command))
        self.assertTrue(any("recovery-adapter" in part for part in command))

    def test_invocation_is_journaled(self):
        state_root = self.base / "state"
        (state_root).mkdir()
        (state_root / "recovery-v3.toml").write_text("migrated", encoding="utf-8")
        result = execute_plan(
            self.make_plan(), state_root, adapters=self.registry,
            adapter_launcher=self.launcher,
        )
        self.assertEqual(result.status, "success", result.errors)
        self.assertEqual(len(self.invocations), 1)
        details = self.journal_details(state_root)
        self.assertTrue(details)
        self.assertEqual(details[-1]["adapter"]["adapter_id"], "recovery-adapter")
        self.assertEqual(details[-1]["adapter"]["permissions"],
                         ["read-configuration", "write-managed-configuration"])

    def test_failed_invocation_is_journaled(self):
        state_root = self.base / "failed-state"
        state_root.mkdir()
        result = execute_plan(
            self.make_plan(), state_root, adapters=self.registry,
            adapter_launcher=self.failing_launcher,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("adapter refused", result.errors[0])
        details = self.journal_details(state_root)
        self.assertTrue(details)
        self.assertEqual(details[-1]["adapter"]["adapter_id"], "recovery-adapter")

    def test_adapter_operation_without_registry_is_refused(self):
        state_root = self.base / "no-registry"
        state_root.mkdir()
        result = execute_plan(self.make_plan(), state_root)
        self.assertEqual(result.status, "failed")
        self.assertIn("no validated adapter registry", result.errors[0])
        self.assertEqual(self.invocations, [])


if __name__ == "__main__":
    unittest.main()
