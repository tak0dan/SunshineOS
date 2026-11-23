"""Tests for component contracts and signed adapter interfaces."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapters import (  # noqa: E402
    AdapterManifest,
    load_manifest,
    validate_adapter,
)
from src.components import (  # noqa: E402
    load_contracts,
    validate_contract,
    validate_contract_set,
)
from src.core import OpType  # noqa: E402
from src.target import load_target  # noqa: E402

CONTRACT = '''format_version = 1
id = "recovery"
name = "Recovery"
[version]
software = "2.1.0"
schema = 3
[provides]
capabilities = ["recovery-checkpoints"]
[requires]
capabilities = ["systemd"]
[ownership]
managed_paths = ["/etc/sunshine/recovery.toml", "/var/lib/sunshine/recovery"]
[lifecycle]
installable = true
upgradeable = true
replaceable = true
removable = true
'''

ADAPTER = '''id = "btrfs-recovery-v3"
component = "recovery"
version = "1.0.0"
runtime = "rust"
operation = "MigrateConfiguration"
signature = "sig"
signed_by = "2FEC611A7F97ED9A37294C90D16F3BE763A4B6BE"
permissions = ["read-configuration", "write-managed-configuration"]
parameters = ["source_path", "target_path"]
provides = ["recovery-checkpoints"]
[artifact]
name = "btrfs-adapter"
sha256 = "abc"
[schema]
from = 1
to = 3
'''


class ComponentContractTests(unittest.TestCase):
    def test_bundled_contracts_cover_published_target(self):
        directory = ROOT / "src" / "target" / "contracts"
        contracts = load_contracts(directory)
        self.assertTrue(contracts)
        self.assertEqual(validate_contract_set(contracts, load_target().components), [])

    def test_malformed_contract_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-contract-") as tmp:
            path = Path(tmp) / "bad.toml"
            path.write_text(CONTRACT.replace('managed_paths = ["/etc/sunshine/recovery.toml", "/var/lib/sunshine/recovery"]',
                                             'managed_paths = ["relative/path"]'), encoding="utf-8")
            from src.components import load_contract
            self.assertTrue(any("absolute" in e for e in validate_contract(load_contract(path))))

    def test_missing_target_contract_is_reported(self):
        errors = validate_contract_set({}, load_target().components)
        self.assertTrue(any("missing component contract" in e for e in errors))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory(prefix="sunshine-adapter-") as tmp:
            path = Path(tmp) / "adapter.toml"
            path.write_text(ADAPTER, encoding="utf-8")
            self.manifest = load_manifest(path)
        self.components = {"recovery"}
        self.artifacts = {"btrfs-adapter"}

    def test_valid_rust_adapter(self):
        self.assertEqual(
            validate_adapter(self.manifest, verified_artifacts=self.artifacts,
                             contract_component_ids=self.components),
            [],
        )
        operation = self.manifest.to_operation({
            "source_path": "/etc/sunshine/recovery-v1.toml",
            "target_path": "/etc/sunshine/recovery.toml",
        })
        self.assertEqual(operation.type, OpType.MIGRATE_CONFIGURATION)
        self.assertEqual(operation.params["adapter_id"], "btrfs-recovery-v3")
        self.assertEqual(operation.params["source_schema"], 1)

    def test_python_privileged_adapter_is_rejected(self):
        data = ADAPTER.replace('runtime = "rust"', 'runtime = "python"')
        manifest = AdapterManifest.from_dict(__import__("tomllib").loads(data))
        errors = validate_adapter(manifest, verified_artifacts=self.artifacts,
                                  contract_component_ids=self.components)
        self.assertTrue(any("Rust" in e for e in errors))

    def test_forbidden_permissions_are_rejected(self):
        data = ADAPTER.replace('permissions = ["read-configuration", "write-managed-configuration"]',
                               'permissions = ["read-configuration", "write-sudoers"]')
        manifest = AdapterManifest.from_dict(__import__("tomllib").loads(data))
        errors = validate_adapter(manifest, verified_artifacts=self.artifacts,
                                  contract_component_ids=self.components)
        self.assertTrue(any("forbidden permissions" in e for e in errors))

    def test_unverified_artifact_is_rejected(self):
        errors = validate_adapter(self.manifest, verified_artifacts=set(),
                                  contract_component_ids=self.components)
        self.assertTrue(any("not verified" in e for e in errors))

    def test_operation_cannot_smuggle_shell_commands(self):
        with self.assertRaises(ValueError) as ctx:
            self.manifest.to_operation({"command": "rm -rf /"})
        self.assertIn("privileged escape keys", str(ctx.exception))

    def test_undeclared_parameters_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.manifest.to_operation({"unexpected": True})
        self.assertIn("undeclared parameters", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
