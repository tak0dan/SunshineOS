# Sunshine OS: technical architecture and implementation specification

Architecture baseline, version 1.0, 19 November 2026. The principles behind it are in [MANIFESTO.md](MANIFESTO.md).

Sunshine OS evolves into a modular operating system with a shared management core, multiple desktop environments, and selectable package-management strategies. Sunshine manages the **integration** of the system, not the **ownership** of the user's system.

Arch remains the foundation. Nix becomes an optional, first-class management backend. Users decide how their software and services are managed, which desktop they use, and how their system is configured.

> Status: this is a target architecture. What exists today is a set of shell and Python tools (`overlay/system/usr/local/bin/sunshine-*`), delivered through the signed tools release (`sunshine-toolsync`) and the `[sunshine]` pacman repository. The Rust core, the D-Bus API, the ownership registry and the transaction journal do not exist yet; see the roadmap in section 13.

## 1. Architectural principles

1. **Arch remains the foundation.** Pacman, systemd, the Arch kernel ecosystem, and upstream repositories remain fundamental.
2. **Sunshine provides integration, not configuration ownership.** Defaults, utilities, automation and recommendations, without treating user configuration as disposable.
3. **Management is modular.** Package management, service management, desktops, updates, recovery and configuration are independently manageable.
4. **Nix is optional, but not second-class.** Every edition supports the same Nix integration.
5. **One component, one authoritative owner.** Pacman and Nix must not independently manage the same system files or software installation.
6. **Updates are validated, not blindly trusted.** Sunshine tests and classifies updates and recommends installation windows.
7. **Desktop environments are profiles, not separate operating systems.**
8. **Recovery is a core capability.** Every system-changing operation has an appropriate recovery strategy.

Logical layers (not a mandatory process hierarchy):

```
Sunshine Experience      Settings · Welcome · Store · Toolbox · Desktop integration
Sunshine Management      Updates · Diagnostics · Recovery · Applications · Profiles · Configuration
Rust Core                Privileged operations · Transactions · Validation · System APIs
Python Interfaces        CLI · GUI adapters · Workflows · Integration
Arch Backend             Pacman · systemd · mkinitcpio · Arch repositories
Nix Backend              Nix store · profiles · Nix packages · Nix-managed services
Arch Linux + Hardware    Kernel · Filesystems · systemd · NetworkManager · PipeWire · GPU drivers
```

Rust and Python communicate through explicit APIs, not arbitrary shell execution.

## 2. Sunshine Core: Rust and Python

### 2.1 Responsibilities

| Component | Language | Responsibilities |
|---|---|---|
| Sunshine Core | Rust | Core system operations |
| Transaction engine | Rust | Operation state, locking, journaling |
| Package adapters | Rust | Pacman / Nix interaction |
| Filesystem adapter | Rust | Filesystem detection and capabilities |
| Service manager | Rust | systemd integration |
| Update validator | Rust | Package metadata and policy checks |
| Configuration engine | Rust | Configuration inspection and validation |
| Recovery engine | Rust | Recovery operations and safeguards |
| CLI | Python | User-facing commands |
| Toolbox | Python | Higher-level workflows |
| Welcome | Python | Installation and first-run integration |
| GUI integrations | Python | Desktop-specific interfaces |
| Store integration | Python | Application catalogue and workflows |

This is not a rule that every Python component calls Rust. A Python application may perform harmless operations itself. Any privileged system modification goes through the appropriate Rust API.

### 2.2 Proposed layout

A monorepo (or clearly separated packages); not every directory must become its own Git repository.

```
sunshine/
├── core/          sunshine-core, -transaction, -package, -config, -service,
│                  -filesystem, -update, -recovery, -hardware
├── interfaces/    sunshine-cli, -toolbox, -welcome, -store, -settings
├── backends/      arch, nix, flatpak, appimage
├── desktops/      plasma, hyprland, xfce, gnome, sway
├── installer/     calamares, profiles, post-install
├── packaging/  tests/  documentation/  releases/
```

### 2.3 Core communication interface

Python does not directly manipulate privileged files or execute arbitrary privileged commands.

- Rust exposes a **local D-Bus API** for privileged operations.
- Rust also exposes a **CLI** for diagnostics, scripting, and recovery environments.
- Python consumes the API through a typed client library.
- JSON is used for structured data interchange; operations return structured results, not just exit codes and terminal output.
- The API schema is versioned. The JSON below illustrates the contract.

```json
{ "operation": "package.install", "backend": "arch", "packages": ["firefox"], "options": { "confirm": true } }
```
```json
{ "status": "completed", "operation_id": "txn-20261119-0001", "backend": "arch",
  "changes": { "installed": ["firefox"], "removed": [] } }
```

**Security requirement:** the privileged service validates every request independently. A GUI or CLI is never trusted to enforce authorization or validate package names.

### 2.4 Privilege model

A dedicated system service, `sunshine-core.service`, that: validates incoming requests; checks authorization through polkit; acquires operation locks; creates transaction records; executes approved operations; reports progress and results; preserves audit logs.

The user interface never runs as root. Only narrowly scoped operations require elevation.

## 3. System configuration: users own their systems

### 3.1 Three categories

| Category | Ownership | Examples |
|---|---|---|
| Sunshine defaults | Sunshine | Default service presets, recommended settings |
| System configuration | User / administrator | NetworkManager, systemd, bootloader, kernel parameters |
| Application configuration | User / application | KDE settings, Hyprland config, GNOME preferences |

Sunshine can inspect all three but respects their ownership.

### 3.2 Configuration directories

```
/etc/sunshine/
├── system.toml  updates.toml  security.toml  hardware.toml
├── recovery.toml  package-management.toml  profiles/
```

These files hold Sunshine-specific preferences and policy, not copies of every system configuration file. Example:

```toml
[updates]
notifications = true
recommended_window = "user-defined"
automatic_updates = false

[recovery]
snapshot_before_system_updates = true
require_confirmation = true

[package_management]
primary_backend = "arch"
nix_enabled = false
```

### 3.3 Modification policy

1. Never overwrite a user's configuration without explicit authorization.
2. Never assume a file is unmodified because Sunshine installed it.
3. Offer differences between the current configuration and the recommended defaults.
4. Provide reversible changes whenever possible.

For example, `sunshine-plasma-setup` must not blindly replace the user's Plasma configuration on every update. Target interface:

```
sunshine-config inspect plasma
sunshine-config compare plasma
sunshine-config apply-defaults plasma      # a deliberate configuration operation
sunshine-config restore-backup plasma      # restores a previous state
```

## 4. Package and service management: Arch + optional Nix

Nix is a selectable system-management **backend**, not just another source in the Store.

### 4.1 Installation modes

**Arch-native (default):** pacman owns system packages; systemd manages services; AUR support through the configured Sunshine integration; no Nix daemon or store.

**Arch + Nix (optional):** pacman keeps the Arch foundation; Nix manages selected packages and services; declarative Nix configurations where appropriate; Sunshine coordinates ownership. Nix does not take over the Arch installation; it is an additional management system with explicitly defined responsibilities.

### 4.2 What Nix manages

| Class | Examples | Recommended owner |
|---|---|---|
| Foundation | Kernel, systemd, bootloader, NetworkManager | Pacman |
| Essential optional services | Selected user services, development tools, optional system utilities | User-selected backend |
| Applications | CLI utilities, development environments, standalone software | Pacman, Nix, Flatpak, or AppImage |

PipeWire: Arch by default. Nix daemon: installed and managed through the bootstrap mechanism, then maintained through a documented Nix integration.

**Constraint.** Nix on Arch does not have NixOS's system-management capabilities. Do not imitate the NixOS module system by generating arbitrary system configuration from Nix expressions without a tested integration model. For Nix-managed system services define: how the package is installed; how its executable path is resolved; how its systemd unit is generated or installed; how dependencies are handled; how upgrades and rollbacks work; what happens when the Nix store is unavailable; how the service is removed without leaving unmanaged system files. The first implementation supports **Nix-managed user services** before arbitrary system services.

### 4.3 Ownership registry

Every managed component has an ownership record:

```toml
[[components]]
name = "networkmanager"
owner = "arch"
scope = "system"
critical = true

[[components]]
name = "development-tools"
owner = "nix"
scope = "user"
critical = false
```

The registry is maintained by Sunshine; users can inspect and change ownership through supported operations. It prevents: pacman and Nix installing competing copies of a system component; multiple managers controlling the same systemd service; a Sunshine update silently replacing a Nix-managed application; removing a package another managed component depends on. Ownership is enforced at the **component** level, not the package-name level: a `foo` in `/nix/store` does not conflict with an Arch `foo` unless both provide the same system service or write the same configuration path.

### 4.4 Nix installation and migration

The installer asks about Nix before applying the final package-management profile.

Arch-native: do not install Nix, do not enable `nix-daemon`, create no Nix-specific configuration, keep all Sunshine tools functional.

Arch + Nix: install Nix; configure the daemon; initialize the Sunshine Nix backend; create the ownership registry; install the supported integration tools; verify the store and daemon; offer optional Nix profiles.

Also after installation:

```
sunshine-nix enable | status | disable | doctor
```

Disabling Nix does not delete the Nix store or remove user-installed packages; it inspects dependencies and asks for confirmation first. Nix is optional at installation but available on every edition; there is no Nix-only edition.

## 5. Desktop architecture: one system, multiple experiences

The installer lets the user pick **one primary desktop**; other environments are available later through Sunshine Tools.

### 5.1 Profiles

| Profile | Status | Character |
|---|---|---|
| KDE Plasma | Primary desktop | Flexible, feature-rich, visually customizable; the main general-purpose desktop |
| Hyprland | Primary desktop | Keyboard-oriented tiling, extensive customization, Sunshine integration |
| XFCE | New | Lightweight, traditional, minimal visual customization, low overhead |
| GNOME | New | Integrated, opinionated, consistent workflow, minimal reliance on extensions |
| Sway | New | Lightweight, keyboard-driven Wayland compositor, conservative and predictable |

### 5.2 Installer selection

Two decisions: **primary desktop** (installed and configured as the primary experience) and **additional software** (other desktops/window managers, alternative terminals, additional display managers, development tools, gaming components).

### 5.3 Profile manifests

```
desktops/<id>/  packages.toml  services.toml  defaults.toml  integrations.toml  setup.py
```

A profile describes: required and optional packages; services to enable and disable; recommended configuration; desktop-specific utilities; display-manager requirements; known conflicts; uninstallation behaviour. Package lists are not embedded in installer scripts.

### 5.4 XFCE: performance-first

| Area | Treatment |
|---|---|
| GTK theme | Dark, neutral, low-contrast |
| Icons / cursor | Shared Sunshine icon set and cursor theme |
| Panel | One conventional bottom panel |
| Window manager | Xfwm4 defaults with sensible behaviour |
| Compositor | Conservative defaults |
| Animations / effects | Minimal / none unnecessary |
| Background | Simple dark wallpaper |
| File manager / terminal | Thunar / a lightweight terminal |
| Startup services | Only necessary ones |

Targets: fast startup, low memory, minimal background services, familiar workflow. No heavyweight Plasma or GNOME components just for visual consistency; a common icon theme and wallpaper are enough to make XFCE recognizable as Sunshine.

### 5.5 GNOME: upstream-oriented

Upstream GNOME Shell; a consistent dark appearance where supported; a limited set of extensions, preferably none by default; no needless replacement of standard applications; the GNOME workflow stays intact; Sunshine integrations through Settings and dedicated applications rather than shell modifications. Extensions break across major Shell updates, so dependence on them is minimized.

### 5.6 Sway: predictable tiling

Defaults: Waybar, Wofi (or another lightweight launcher), Mako, Foot (or another lightweight terminal), Swaylock, Swayidle, NetworkManager, PipeWire, XDG desktop portal support. Do not copy the Hyprland configuration and rename the compositor; share Sunshine utilities, not configuration assumptions.

### 5.7 Coexistence and display managers

A desktop registry, detecting installed sessions from the actual system and not trusting its own records:

```toml
[[desktops]]
id = "plasma"
display_name = "KDE Plasma"
type = "desktop"
display_manager = "sddm"
session = "plasma"
installed = true
```

Display managers: SDDM is the default for Plasma and the initial Sunshine configuration; GDM is the preferred native GNOME integration; SDDM is supported for the other sessions; no requirement to run several display managers. Installing GNOME does not automatically replace SDDM: Sunshine detects the existing display manager and offers a deliberate choice.

## 6. Update architecture: validation and recommended windows

Availability of an update is distinct from the recommendation to install it. Sunshine validates updates against its own integration, publishes results, and recommends windows.

### 6.1 Validation pipeline

1. **Upstream package detection:** new packages and versions from Arch repositories and supported secondary sources.
2. **Metadata and compatibility checks:** dependencies, conflicts, replacements, integrity, known incompatibilities.
3. **Automated testing:** installation, upgrades, desktop startup, services and Sunshine integrations in VMs.
4. **Integration testing:** Plasma, Hyprland, XFCE, GNOME, Sway; btrfs, ext4; Arch-only and Arch + Nix.
5. **Release classification:** publish results and the update window.
6. **User notification:** recommended windows and relevant risks.

### 6.2 Classification

| Class | Meaning |
|---|---|
| Recommended | Passed Sunshine validation |
| Caution | Available, but known risks or incomplete validation |
| Deferred | Significant issue identified; waiting is recommended |
| Critical | Security or operational urgency warrants immediate attention |

These labels never imply complete knowledge of every upstream package or hardware combination.

### 6.3 Recommended windows

Recommendations are published, not imposed. The metadata is **versioned and signed**:

```toml
[release]
channel = "stable"
recommendation = "recommended"
published_at = "2026-11-19T12:00:00Z"

[update_window]
recommended_start = "2026-11-20T10:00:00Z"
recommended_end = "2026-11-22T22:00:00Z"

[validation]
arch = "passed"  plasma = "passed"  hyprland = "passed"  xfce = "passed"
gnome = "passed"  sway = "passed"  btrfs = "passed"  ext4 = "passed"  nix_backend = "passed"
```

The client shows: available updates; validation status; the recommended window; known issues; required reboot; snapshot availability; last successful update; whether the installed system differs from tested configurations. Users can still update outside the window.

### 6.4 Validation is not repository freezing

Do not hold back every Arch package until approved; that turns Sunshine into a partial fork. Keep upstream packages available, validate representative combinations, publish recommendations, maintain explicit compatibility constraints where necessary, and delay only packages with known integration problems, visibly. "Stable" means validated integration, not frozen packages.

## 7. Filesystem architecture

| Filesystem | Policy |
|---|---|
| **Btrfs** | Officially supported, tested and maintained: snapshot integration, Snapper, GRUB snapshot integration, subvolume-aware recovery |
| **ext4** | Officially supported, tested and maintained: Timeshift support, standard filesystem recovery, conventional layout |
| **ZFS** | Existing support remains available and is not removed, but is **not maintained or guaranteed** by Sunshine; users continue at their own discretion and compatibility may regress |
| **Other** | Best-effort compatibility, no official support commitment |

### 7.1 Capability model

No scattered `if [ "$filesystem" = "btrfs" ]` checks. A capability interface that recovery tools query:

```rust
pub trait FilesystemBackend {
    fn detect(&self) -> bool;
    fn supports_snapshots(&self) -> bool;
    fn supports_subvolumes(&self) -> bool;
    fn create_snapshot(&self) -> Result<Snapshot>;
    fn restore_snapshot(&self, id: &str) -> Result<()>;
}
```

The real interface also needs mountpoints, permissions, boot integration and snapshot consistency.

### 7.2 Support matrix

| Feature | Btrfs | ext4 | ZFS / other |
|---|---|---|---|
| Installation | Yes | Yes | Best-effort (existing, unmaintained for ZFS) |
| Health inspection | Yes | Yes | Best-effort |
| Snapshot integration | Yes | Yes, via supported tooling | Not guaranteed |
| Boot snapshot integration | Yes, where configured | Not generally applicable | Not guaranteed |
| Automated recovery | Supported workflows | Supported workflows | Limited |
| Sunshine testing | Required | Required | None committed |

Timeshift on ext4 generally uses rsync mode rather than native filesystem snapshots; the two must not be presented as equivalent.

## 8. Transaction and recovery architecture

The shared foundation for updates, package installation, desktop changes, configuration changes and service modifications.

### 8.1 Lifecycle

```
CREATED → PREFLIGHT → PREPARED → SNAPSHOTTED (when supported and configured) → APPLYING → VERIFYING → COMPLETED
failure states: FAILED · RECOVERY_REQUIRED · CANCELLED
```

Not every operation needs a filesystem snapshot; a user-level configuration change may need only a backup of the affected files.

### 8.2 Journal

```
/var/lib/sunshine/transactions/  active/  completed/  failed/  recovery/
```

```toml
id = "txn-20261119-0001"
operation = "desktop.install"
status = "completed"
[backend]
package_manager = "arch"
[system]
filesystem = "btrfs"
desktop = "plasma"
[recovery]
snapshot_created = true
snapshot_id = "sunshine-20261119-0001"
```

The journal records: operation identity, initiating user, timestamp, requested changes, backend, preflight results, files and services affected, snapshot or backup references, execution progress, final result, recovery instructions.

### 8.3 No false atomicity

Pacman, Nix, Flatpak and AppImage share no transaction system. Sunshine coordinates operations and records exactly what succeeded. If a transaction fails after pacman updated but before Nix completed, it reports a partially completed operation and offers recovery steps.

## 9. Desktop installation and lifecycle

Desktops are managed by the same transaction system; installing XFCE is not a blind package install. The operation: inspect the existing desktop; inspect the display manager; resolve dependencies; detect conflicting or duplicate components; show the proposed changes; create a recovery point; install packages; configure desktop-specific services; register the session; verify the session is available; report completion.

Removal distinguishes packages used exclusively by that desktop, shared packages, user configuration, and services used by other components. Shared components are never removed because one profile is uninstalled.

```
sunshine-desktops list | status
sunshine-desktops install xfce|gnome|sway
sunshine-desktops remove xfce
```

The Toolbox exposes the active desktop, installed sessions, display manager, and desktop-specific diagnostics.

## 10. Application and package integration

| Ecosystem | Purpose | Ownership |
|---|---|---|
| Arch repositories | Base system, native packages | Pacman |
| Sunshine repository | Sunshine-specific packages | Pacman |
| AUR | Community build recipes | Pacman / build tools |
| Nix | Optional declarative package and service management | Nix |
| Flatpak | Sandboxed desktop applications | Flatpak |
| AppImage | Portable standalone applications | User / Sunshine tooling |
| Web applications | Browser-based applications | User / browser |

The Store is an interface over these ecosystems, not a new package manager. Every entry specifies: available installation methods; source; package identity; security/trust level; update owner; removal procedure; known conflicts. The Store prefers the user's configured backend but always shows the source and ownership.

## 11. Desktop-independent integration

One implementation, thin per-desktop adapters:

```
sunshine-update-check → Sunshine Core → Notification Interface
    → Plasma | Hyprland | XFCE | GNOME | Sway adapters
```

The same applies to update notifications, Store integration, system health reporting, recovery notifications, the Welcome experience, session management, desktop settings and system information. An adapter is as small as possible.

## 12. Testing and release engineering

Minimum matrix:

| Dimension | Required configurations |
|---|---|
| Desktop | Plasma, Hyprland, XFCE, GNOME, Sway |
| Filesystem | Btrfs, ext4 |
| Package management | Arch-only, Arch + Nix |
| Boot | UEFI |
| Installation | Fresh install, upgrade |
| Recovery | Snapshot restore, rescue environment |
| Update | Successful, interrupted, failed |
| Display manager | SDDM, GDM where supported |

That is 20 desktop/filesystem/package-mode combinations (5 × 2 × 2) before hardware, installer options and update states are considered. Most are covered by automated VM testing, plus a smaller physical-hardware suite for GPU, Wi-Fi, audio, suspend and firmware.

### 12.1 Release gates

A release is promoted to stable only if: the ISO builds; installation succeeds on supported configurations; first boot succeeds; the selected desktop starts; network and audio work; the package manager functions; Nix integration works when enabled; desktop installation/removal works; recovery tooling detects supported installations; update validation completes; failed operations are correctly reported; no critical regression is unresolved. "Stable" means a tested release.

## 13. Roadmap

1. **Architectural foundation (first priority).** Rust core API; transaction engine; configuration ownership model; package and service ownership registry; desktop profile manifest format; filesystem capability detection. *Deliverable: a stable foundation.*
2. **Backend integration.** Arch backend; optional Nix backend; service ownership rules; Flatpak; package source identification; Nix enable/disable. *Deliverable: a unified, inspectable package and service management system.*
3. **Desktop profiles.** Formalize Plasma and Hyprland; add XFCE, GNOME, Sway profiles; desktop registry; install/remove workflows; display manager handling. *Deliverable: several desktops managed by one system.*
4. **Update validation.** Metadata service; compatibility checks; VM testing pipelines; published validation reports; recommended windows; notifications. *Deliverable: a transparent, predictable update process.*
5. **Unified interfaces.** CLI on the Rust core; Toolbox; Welcome; desktop adapters; Store; unified settings and diagnostics. *Deliverable: a coherent Sunshine experience across all desktops.*
6. **Release hardening.** Regression testing; recovery on btrfs and ext4; Nix-enabled and Arch-only installs; audit of privileged operations; documented supported configurations; stable release criteria. *Deliverable: a reliable Sunshine OS 1.0 foundation.*

## 14. Decisions register

| Area | Established decision | Implementation direction |
|---|---|---|
| Foundation | Arch Linux | Preserve upstream conventions |
| Core / interfaces | Rust core, Python interfaces | Privileged operations in Rust; CLI, GUI, orchestration in Python |
| Configuration | User-owned | Sunshine defaults and utilities |
| Updates | Validated, recommended windows | Validation metadata and advisory scheduling |
| Nix | First-class optional backend | Selectable at installation and afterwards |
| Filesystems | Btrfs and ext4 official; ZFS existing, unmaintained; others best-effort | Capability-based adapters |
| Desktops | Multiple preconfigured profiles | Manifest-based profiles; XFCE minimal; GNOME upstream; Sway lightweight |
| Recovery | Core capability | Transaction journal and recovery engine |
| Package ownership | Explicit | Prevent conflicting managers |
| Releases | Stability-first | Automated validation gates |

## 15. Open decisions (recommendations pending approval)

1. **Nix system-service scope.** Recommendation: start with user services and applications, then add system services through explicitly supported adapters.
2. **Desktop installation model.** Recommendation: allow multiple desktops, with one designated primary.
3. **XFCE identity.** Recommendation: same ISO, selectable profile; no extra edition.
4. **Update validation infrastructure.** Recommendation: start with validation metadata and automated testing while users receive packages directly from Arch; add package promotion only if testing shows a real reliability gain.
5. **Rust/Python interface.** Recommendation: D-Bus API as the primary interface, CLI as the secondary one.

## 16. Position

Sunshine OS is neither an Arch distribution with a pile of scripts nor NixOS with an Arch package manager attached. It is a modular management and integration layer built on Arch Linux. The first engineering priority is the shared Rust core, the ownership model, the transaction system and the desktop profile specification; those four determine whether the growing feature set stays one coherent operating system or turns into five desktops, three package managers and a collection of scripts arguing over `/etc`.
