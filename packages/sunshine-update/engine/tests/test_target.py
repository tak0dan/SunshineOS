"""Unit tests for target manifest loading and desired-state resolution.

Run from the engine root with::

    python3 -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.core import Confidence, ObservedState, Observation, Status
from src.target import load_target, resolve_target
from src.target.manifest import parse_target_toml
from src.target.profiles import load_profiles

EXPECTED_SCHEMAS = {
    "core": 3,
    "configuration": 4,
    "ownership": 2,
    "kernel_management": 2,
    "boot_integration": 2,
    "recovery": 3,
    "desktop_integration": 4,
    "nix_integration": 2,
}
SUPPORTED_PROFILES = {"plasma", "hyprland", "xfce", "gnome", "sway"}


def _observation(component, detected, confidence=Confidence.HIGH, status=Status.RUNNING, evidence=None):
    return Observation(component, detected, confidence, status, evidence or [])


def _decisions_of(decisions, kind):
    return [d for d in decisions if d["kind"] == kind]


class TargetManifestTests(unittest.TestCase):
    def test_load_default_target(self):
        target = load_target()
        self.assertEqual(target.format_version, 1)
        self.assertEqual(target.release, "sunshine-2026.1")
        self.assertGreater(target.repository_generation, 0)
        self.assertEqual(
            {cid: component.schema for cid, component in target.components.items()},
            EXPECTED_SCHEMAS,
        )

        for cid, component in target.components.items():
            self.assertTrue(component.provides, f"{cid} must provide capabilities")
            self.assertEqual(component.id, cid)
            if cid == "nix_integration":
                self.assertFalse(component.required)
            else:
                self.assertTrue(component.required, f"{cid} should be required")

        # Every required capability must be offered by some component.
        provided = {cap for c in target.components.values() for cap in c.provides}
        for cid, component in target.components.items():
            for capability in component.requires:
                self.assertIn(capability, provided, f"{cid} requires unknown {capability}")

        for policy in (
            "preserve_user_configuration",
            "preserve_user_packages",
            "require_signed_packages",
        ):
            self.assertTrue(target.policies[policy])

        self.assertIn("base", target.package_sets)
        self.assertIn("kernel_management", target.package_sets)
        self.assertEqual(target.package_sets["desktop_integration"], [])

    def test_embedded_default_matches_current_toml(self):
        embedded = load_target()
        from_file = parse_target_toml(
            (ENGINE_ROOT / "src" / "target" / "current.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(embedded, from_file)
        self.assertEqual(load_target(ENGINE_ROOT / "src" / "target" / "current.toml"), embedded)

    def test_target_packages_exist_in_the_published_repository(self):
        # Names that were never published by the [sunshine] repo make a real
        # migration fail with "target not found". Manage that state with the
        # real package that owns /etc/sunshine and the ownership tooling.
        phantom = {"sunshine-config", "sunshine-ownership", "sunshine-recovery", "sunshine-agent"}
        declared = set()
        for packages in load_target().package_sets.values():
            declared.update(packages)
        self.assertFalse(phantom & declared, f"unpublished packages: {sorted(phantom & declared)}")
        self.assertIn("sunshine-base", declared)

    def test_profiles_declare_capabilities_packages_and_conflicts(self):
        profiles = load_profiles()
        self.assertEqual(set(profiles), SUPPORTED_PROFILES)
        for profile in profiles.values():
            self.assertTrue(profile.required_capabilities, profile.id)
            self.assertTrue(profile.packages, profile.id)
            self.assertTrue(profile.conflicts, profile.id)
            self.assertFalse(set(profile.conflicts) & {profile.id})


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.target = load_target()

    def test_resolve_with_one_desktop(self):
        observed = ObservedState()
        observed.observe(
            _observation(
                "desktop_session",
                "plasma",
                Confidence.HIGH,
                Status.RUNNING,
                ["/usr/share/xsessions/plasma.desktop"],
            )
        )

        resolved, decisions = resolve_target(observed, self.target)
        desktop = _decisions_of(decisions, "desktop_profile")
        self.assertEqual(len(desktop), 1)
        self.assertEqual(desktop[0]["selected"], "plasma")
        self.assertTrue(desktop[0]["auto"])
        self.assertFalse(desktop[0]["requires_user_input"])
        self.assertIn("plasma-desktop", resolved.package_sets["desktop_integration"])
        self.assertIn(
            "desktop-profile:plasma", resolved.components["desktop_integration"].provides
        )

        # The published target must stay untouched for the next machine.
        self.assertEqual(self.target.package_sets["desktop_integration"], [])
        self.assertNotIn("desktop-profile:plasma", self.target.components["desktop_integration"].provides)

    def test_profile_capabilities_do_not_create_self_dependency(self):
        """A selected profile must not make its own component a prerequisite."""
        from src.planner import plan as build_plan
        observed = ObservedState(distribution="arch", init_system="systemd",
                                 package_manager="pacman", architecture="x86_64")
        observed.packages["hyprland"] = "0.42.0-1"
        observed.observe(_observation("desktop_session", "hyprland", Confidence.HIGH, Status.RUNNING))

        resolved, decisions = resolve_target(observed, self.target)
        spec = resolved.components["desktop_integration"]
        for capability in spec.provides:
            self.assertNotIn(capability, spec.requires)
        # Planning must not raise "component dependency cycle detected".
        result = build_plan(observed, resolved, decisions=decisions)
        self.assertTrue(result.operations)

    def test_resolve_with_multiple_desktops_requires_one_decision(self):
        observed = ObservedState()
        observed.observe(_observation("desktop_session", "plasma", Confidence.HIGH, Status.RUNNING))
        observed.observe(_observation("desktop_session", "gnome", Confidence.HIGH, Status.RUNNING))

        resolved, decisions = resolve_target(observed, self.target)
        desktop = _decisions_of(decisions, "desktop_profile")
        self.assertEqual(len(desktop), 1)
        self.assertTrue(desktop[0]["requires_user_input"])
        self.assertIsNone(desktop[0]["selected"])
        self.assertEqual(set(desktop[0]["options"]), {"plasma", "gnome"})
        self.assertEqual(resolved.package_sets["desktop_integration"], [])

    def test_configured_default_breaks_multi_desktop_tie(self):
        observed = ObservedState()
        observed.observe(_observation("desktop_session", "plasma", Confidence.HIGH, Status.RUNNING))
        observed.observe(_observation("desktop_session", "gnome", Confidence.HIGH, Status.RUNNING))
        observed.observe(
            _observation(
                "desktop.default",
                "plasma",
                Confidence.HIGH,
                Status.CONFIGURED,
                ["/etc/sddm.conf: Session=plasma"],
            )
        )

        resolved, decisions = resolve_target(observed, self.target)
        desktop = _decisions_of(decisions, "desktop_profile")
        self.assertEqual(desktop[0]["selected"], "plasma")
        self.assertFalse(desktop[0]["requires_user_input"])
        self.assertIn("plasma-desktop", resolved.package_sets["desktop_integration"])

    def test_low_confidence_desktop_is_not_auto_selected(self):
        observed = ObservedState()
        observed.observe(_observation("desktop_session", "sway", Confidence.LOW, Status.INSTALLED))

        _, decisions = resolve_target(observed, self.target)
        desktop = _decisions_of(decisions, "desktop_profile")
        self.assertTrue(desktop[0]["requires_user_input"])
        self.assertEqual(set(desktop[0]["options"]), SUPPORTED_PROFILES)

    def test_optional_nix_is_activated_only_when_present(self):
        plain, decisions = resolve_target(ObservedState(), self.target)
        self.assertFalse(plain.components["nix_integration"].required)
        self.assertEqual(plain.package_sets["nix_integration"], [])
        self.assertEqual(_decisions_of(decisions, "nix"), [])

        absent = ObservedState()
        absent.observe(_observation("nix_integration", "absent", Confidence.HIGH, Status.ABSENT))
        plain_again, _ = resolve_target(absent, self.target)
        self.assertFalse(plain_again.components["nix_integration"].required)

        with_nix = ObservedState(packages={"nix": "2.24.0"})
        resolved, decisions = resolve_target(with_nix, self.target)
        self.assertTrue(resolved.components["nix_integration"].required)
        self.assertIn("nix", resolved.package_sets["nix_integration"])
        nix = _decisions_of(decisions, "nix")
        self.assertEqual(len(nix), 1)
        self.assertEqual(nix[0]["selected"], "enabled")
        self.assertTrue(nix[0]["auto"])

    def test_preserves_user_choices(self):
        observed = ObservedState()
        observed.observe(_observation("desktop_session", "plasma", Confidence.HIGH, Status.RUNNING))
        observed.observe(_observation("bootloader", "grub", Confidence.HIGH, Status.CONFIGURED))
        observed.observe(_observation("network", "NetworkManager", Confidence.HIGH, Status.ENABLED))
        observed.observe(_observation("audio", "pipewire", Confidence.HIGH, Status.RUNNING))

        resolved, decisions = resolve_target(observed, self.target)
        self.assertIn("grub", resolved.package_sets["bootloader"])
        self.assertIn("networkmanager", resolved.package_sets["network"])
        self.assertIn("pipewire", resolved.package_sets["audio"])

        expected = {"bootloader": "grub", "network": "networkmanager", "audio": "pipewire"}
        for kind, choice in expected.items():
            records = _decisions_of(decisions, kind)
            self.assertEqual(len(records), 1, kind)
            self.assertEqual(records[0]["selected"], choice)
            self.assertEqual(records[0]["action"], "preserve")
            self.assertTrue(records[0]["auto"])
        self.assertFalse(any(d["requires_user_input"] for d in decisions))

    def test_conflicting_bootloaders_ask_one_question(self):
        observed = ObservedState()
        observed.observe(_observation("bootloader.grub", "grub", Confidence.HIGH, Status.RUNNING))
        observed.observe(
            _observation("bootloader.systemd-boot", "systemd-boot", Confidence.HIGH, Status.RUNNING)
        )
        _, decisions = resolve_target(observed, self.target)
        choices = _decisions_of(decisions, "bootloader")
        self.assertEqual(len(choices), 1)
        self.assertTrue(choices[0]["requires_user_input"])
        self.assertEqual(set(choices[0]["options"]), {"grub", "systemd-boot"})

    def test_installed_only_alternative_does_not_create_conflict(self):
        """An unused package is weaker evidence than a running backend."""
        observed = ObservedState()
        observed.observe(_observation(
            "bootloader.grub", "grub", Confidence.HIGH, Status.RUNNING,
            ["config: /boot/grub/grub.cfg", "EFI boot entry: Boot0002 GRUB"],
        ))
        observed.observe(_observation(
            "bootloader.refind", "refind", Confidence.MEDIUM, Status.INSTALLED,
            ["installed package: refind", "no firmware boot entry corroboration"],
        ))
        _, decisions = resolve_target(observed, self.target)
        choices = _decisions_of(decisions, "bootloader")
        self.assertEqual(len(choices), 1)
        self.assertFalse(choices[0]["requires_user_input"])
        self.assertEqual(choices[0]["selected"], "grub")

    def test_unsupported_choice_asks_exactly_one_question(self):
        observed = ObservedState()
        observed.observe(_observation("bootloader", "syslinux", Confidence.HIGH, Status.CONFIGURED))

        _, decisions = resolve_target(observed, self.target)
        bootloader = _decisions_of(decisions, "bootloader")
        self.assertEqual(len(bootloader), 1)
        self.assertTrue(bootloader[0]["requires_user_input"])
        self.assertEqual(set(bootloader[0]["options"]), {"grub", "systemd-boot", "refind"})

    def test_resolution_is_isolated_between_machines(self):
        plasma = ObservedState()
        plasma.observe(_observation("desktop_session", "plasma", Confidence.HIGH, Status.RUNNING))
        gnome = ObservedState()
        gnome.observe(_observation("desktop_session", "gnome", Confidence.MEDIUM, Status.RUNNING))

        first, _ = resolve_target(plasma, self.target)
        second, _ = resolve_target(gnome, self.target)
        self.assertIn("plasma-desktop", first.package_sets["desktop_integration"])
        self.assertNotIn("plasma-desktop", second.package_sets["desktop_integration"])
        self.assertIn("gnome-shell", second.package_sets["desktop_integration"])
        self.assertEqual(self.target.package_sets["desktop_integration"], [])


if __name__ == "__main__":
    unittest.main()
