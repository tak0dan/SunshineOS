# The Sunshine OS Manifesto

*A hybrid operating system. Stability as an engineering priority. One integrated experience.*

Architectural manifesto, revised 19 November 2026. The technical consequences are specified in [ARCHITECTURE.md](ARCHITECTURE.md).

## Preamble

Sunshine OS exists to make a powerful, flexible Linux system dependable and approachable without taking away the freedom that makes Linux worth using.

It is built on Arch Linux and benefits from its packages, tools, documentation, and rolling-release ecosystem. It does not seek to replace that foundation or maintain an unnecessary fork of it. Instead, Sunshine develops the integration, policies, tooling, defaults, and user experience that turn the foundation into a coherent operating system.

Sunshine is not a theme applied to Arch, nor a bundle of unrelated utilities. It is an operating-system project with its own engineering standards and responsibility for the complete experience it delivers.

Its direction is defined by four commitments:

1. **Hybrid by architecture:** use established ecosystems where they are strong, and build Sunshine-owned infrastructure where integration and consistency require it.
2. **Stability by priority:** prefer predictable behaviour, recoverability, and tested changes over novelty and feature count.
3. **Integrated by design:** deliver one coherent operating system whose components share common policies, state, and interfaces.
4. **User-owned by principle:** provide useful defaults and management tools without taking ownership of the user's configuration or choices.

## I. The foundation is a strength, not a limitation

Sunshine OS builds upon Arch Linux rather than pretending it must reinvent everything.

Arch provides the package foundation and much of the underlying system. Sunshine must respect upstream conventions, avoid needless divergence, and keep its customizations maintainable.

Sunshine will not fork the entire Arch ecosystem merely to claim independence. It will own the parts that define the Sunshine experience: system integration, configuration policy, maintenance workflows, recovery tooling, release engineering, and desktop integration.

Upstream improvements should be preferred over permanent local patches. Where patches are necessary, they should be limited, documented, and maintained with a clear reason for existing.

Pacman remains the native package manager and the authority for the Arch foundation. Sunshine must preserve compatibility with the Arch ecosystem rather than quietly replacing its conventions with proprietary equivalents.

## II. One operating system, not a collection of scripts

Sunshine's tools must operate as parts of one system.

Updates, diagnostics, recovery, configuration, hardware management, package management, and desktop utilities should share common definitions of system state and common rules for changing it.

A feature is not complete merely because its command works in isolation. It must also behave correctly alongside the rest of the operating system.

Shared logic should have one authoritative implementation and multiple appropriate interfaces. Command-line tools, graphical applications, installer components, and background services must not each invent their own version of the same system behaviour.

Sunshine should remain usable without a graphical session. Essential maintenance and recovery must not depend on Plasma, Hyprland, XFCE, GNOME, Sway, or any other running desktop.

## III. The core is Rust; the interfaces are flexible

Sunshine Core will use Rust for core system operations and Python for higher-level interfaces and workflows.

Rust is responsible for the components where correctness, predictable execution, safe system interaction, and carefully controlled privileges are especially important. This includes transaction handling, package and service adapters, filesystem capabilities, update validation, configuration inspection, and recovery operations.

Python is responsible for higher-level orchestration and user-facing tools, including command-line workflows, the Toolbox, Welcome, Store integration, and desktop-facing applications.

The language boundary is an architectural responsibility boundary, not a requirement to rewrite every small utility. Harmless presentation logic does not need to be moved into Rust merely for consistency. Privileged system modifications, however, must go through narrowly scoped and validated core operations.

Interfaces must communicate through documented, versioned contracts. A local D-Bus API is the preferred interface for privileged operations used by desktop applications, complemented by a command-line interface for scripting, diagnostics, and recovery environments.

Graphical applications must not run as root. The core must validate every request independently, enforce authorization, record system-changing operations, and expose structured results rather than relying on terminal text as an API.

Sunshine should not introduce a daemon or a new protocol without a demonstrated need. Where a library and command-line interface are sufficient, they should be preferred.

## IV. The user's system remains the user's system

Sunshine provides defaults, utilities, integration, and recommendations. Users own their system configuration.

Sunshine must not treat the configuration shipped with an installation as permanently authoritative. A user may change a service, replace a desktop component, edit a configuration file, or choose a different workflow without having to fight the distribution.

Sunshine-specific policy belongs in a documented configuration hierarchy. Application-specific configuration remains with the application that owns it. User preferences remain user-owned.

Sunshine may inspect configuration, explain differences, validate settings, offer recommended defaults, and provide tools to apply or restore changes. It must not silently overwrite user modifications during an update or routine maintenance.

Configuration changes and migrations must be deliberate, validated, and explainable. Where practical, Sunshine should preserve backups and provide a clear way to reverse its own supported changes.

Good defaults reduce work. They do not justify hiding decisions.

## V. Package and service ownership must be explicit

A system with multiple package managers needs clear ownership boundaries.

Pacman owns the Arch foundation and packages installed through the Arch package ecosystem. Nix owns packages and environments explicitly assigned to Nix. Flatpak owns its application installations. AppImage remains independently managed. AUR packages are community build recipes and must be treated according to their actual trust model, not as equivalent to signed official binaries.

Sunshine must maintain an inspectable ownership model for managed components. It must prevent conflicting managers from independently controlling the same system files, services, or configuration paths.

Ownership is not determined by package name alone. Two managers may install separate copies of software without conflict, while two different packages may still collide by attempting to provide the same service, executable path, or configuration.

The Sunshine Store is an interface to supported software ecosystems, not a replacement package manager. It should identify each application's source, installation method, update owner, trust level, and removal procedure.

The Sunshine repository must follow strict packaging and signing practices. It must not silently replace upstream packages through accidental name collisions or repository precedence.

## VI. Nix is first-class, optional, and available everywhere

Nix is a first-class optional backend available across all Sunshine editions.

During installation, users may choose a pure Arch experience or enable Nix as an additional management tool. The choice must remain available after installation: users should be able to enable Nix later without reinstalling Sunshine.

In Arch-native mode, Sunshine must not install or enable Nix unnecessarily. All core Sunshine functionality must remain available without Nix.

In Arch + Nix mode, Arch remains responsible for the operating-system foundation. Nix can manage selected applications, development environments, user packages, and explicitly supported services. Users may choose declarative Nix configurations where they provide value.

Nix must not be presented as turning an Arch installation into NixOS. Sunshine must provide a clear and tested integration model rather than attempting to reproduce the NixOS module system through ad hoc generation of host configuration.

The initial integration should prioritize user-level packages and services. System-level Nix-managed services may be supported through explicit Sunshine adapters with defined rules for installation, service generation, dependencies, upgrades, rollback, removal, and failure handling.

Enabling or disabling Nix must be an inspectable operation. Disabling it must not silently delete the Nix store or remove user-installed packages. Sunshine must inspect dependencies and explain consequences before making changes.

Nix is optional in installation, but it is not an afterthought in architecture, testing, or tooling.

## VII. Updates must be validated and honestly described

Sunshine will validate package updates and publish recommended update windows.

The project will not impose a mandatory update schedule or prevent users from updating when they choose. Instead, Sunshine will provide information that helps users make an informed decision.

Validation should include package metadata and dependency checks, compatibility checks, automated virtual-machine testing, desktop integration testing, supported-filesystem testing, and representative Arch-only and Arch + Nix configurations.

Sunshine should publish validation results, known issues, recommendation status, and recommended update windows. Users should be able to see what was tested, what passed, what remains untested, and which limitations apply to their configuration.

Update recommendations should distinguish at least:

- **Recommended:** passed the relevant Sunshine validation process.
- **Caution:** available, but has known risks or incomplete validation.
- **Deferred:** a significant issue has been identified and waiting is recommended.
- **Critical:** a security or operational issue warrants urgent attention.

These classifications are guidance, not guarantees. Sunshine cannot test every hardware combination or promise that upstream packages never introduce regressions.

Sunshine should prefer validation metadata and transparent recommendations over maintaining an unnecessary fork of Arch repositories. Packages should not be held back merely to create the appearance of stability. Where a package must be delayed or constrained because of a known integration failure, the reason and scope must be visible.

The project must distinguish a validated installation image from the continuously changing state of rolling package repositories.

## VIII. Every system-changing operation must be accountable

Operations that modify the host system must be understandable before, during, and after execution.

Updates, migrations, driver changes, kernel changes, desktop installation, service changes, and repairs should use explicit pre-flight checks, record what they intend to do, report what they actually did, and expose failures clearly.

Where appropriate, they should create a recovery point before making changes. Recovery points must never be presented as universal backups or as guarantees of atomic rollback.

Sunshine should use a shared transaction model for significant operations. A transaction should record its identity, initiating user, requested changes, selected backend, affected components, progress, recovery references, and final result.

Pacman, Nix, Flatpak, and other software systems do not share one transaction mechanism. Sunshine may coordinate them, but it must not pretend that a multi-backend operation is atomic. If one backend succeeds and another fails, the system must report the partial result and identify the next safe action.

Interrupted operations must be treated as uncertain until their state has been inspected. Sunshine should preserve enough information to diagnose what happened and determine a safe next step.

## IX. Recovery is part of the operating system

A system is not dependable merely because it works when everything goes right.

Sunshine must treat diagnosis and recovery as core capabilities, not optional extras. The live environment should be able to identify supported installations, provide useful diagnostics, and offer carefully scoped repair operations.

Snapshots, backups, boot repair, and rescue tools must have explicit capabilities and limitations. A snapshot on the same disk is not protection against disk failure. A root filesystem snapshot does not necessarily include the EFI system partition, separate home partitions, external data, or application-consistent databases.

Sunshine must communicate these distinctions clearly. It should never give users a false sense of security.

Filesystem support must be described honestly:

- **Btrfs and ext4** are officially supported filesystems. Sunshine will test and maintain its installation, management, and recovery workflows for both.
- **ZFS** support already exists and will remain available. Sunshine will not remove existing ZFS compatibility merely to narrow its official support scope. However, ZFS will not be actively maintained, developed, or guaranteed by Sunshine. Users who continue to use it do so with the understanding that compatibility may regress and Sunshine-specific support may be limited.
- **Other filesystems** are best-effort. Sunshine may work with them where existing tools and upstream support permit, but it makes no full support or maintenance commitment.

Official support means an ongoing engineering obligation, not simply that an installer can format a partition. Sunshine must test the capabilities it advertises, including installation, upgrades, snapshots where applicable, boot integration, and recovery.

Filesystem-specific behaviour should be exposed through capability-based interfaces. Core tools must not assume that every filesystem supports snapshots, subvolumes, or the same recovery operations.

## X. Desktop environments are profiles of one operating system

Sunshine offers multiple preconfigured desktop environments and window managers without turning each one into a separate, unrelated distribution.

The installer should allow users to choose one primary desktop experience. Additional environments should be selectable during installation where practical and installable later through Sunshine Tools.

The initial supported profiles are:

- **KDE Plasma:** a flexible, feature-rich, highly customizable general-purpose desktop.
- **Hyprland:** a keyboard-oriented tiling Wayland experience with extensive customization.
- **XFCE:** a lightweight, conventional desktop with minimal, performance-oriented customization.
- **GNOME:** an integrated, opinionated desktop that should remain close to its upstream workflow.
- **Sway:** a lightweight, keyboard-driven Wayland compositor with a conservative configuration model.

These are profiles over one shared operating system. They must share the same core maintenance, package ownership, update, diagnostic, and recovery infrastructure.

Each profile should declare its required and optional packages, services, defaults, integrations, session identity, display-manager compatibility, conflicts, and removal behaviour in a maintainable manifest. Installer scripts must not become the only source of truth for desktop package lists.

XFCE should be treated according to its purpose. Sunshine's XFCE profile should be minimal and performance-oriented: conservative panel and window-manager defaults, limited effects, a restrained theme, a shared icon and cursor identity, and only necessary background services. It should not receive heavyweight visual customization or unnecessary dependencies simply to imitate Plasma or GNOME.

GNOME should remain close to upstream. Sunshine should avoid excessive extensions and shell modifications that create compatibility burdens across GNOME releases.

Sway and Hyprland should share Sunshine utilities where appropriate, but they must retain compositor-specific configurations and integrations. Their configuration models and capabilities are not interchangeable.

Multiple desktop environments may coexist. Sunshine should maintain an inspectable desktop registry, detect actual installed sessions, designate a primary desktop, and handle shared packages and services safely. Installing or removing one desktop must not remove components required by another.

The display manager must be handled deliberately. Installing a desktop must not silently replace the user's existing display manager. Sunshine should detect the current setup and explain any required changes before applying them.

## XI. One integrated desktop experience

Plasma, Hyprland, XFCE, GNOME, and Sway may offer different ways to interact with Sunshine, but they remain interfaces to the same operating system.

Core capabilities must not be duplicated or behave differently without a clear reason. Application management, update status, diagnostics, recovery, and system settings should share common underlying services and policies.

Desktop-specific adapters may present notifications, settings, or workflows in ways appropriate to each environment. They must not become independent implementations of core system logic.

The terminal remains a first-class interface. The graphical environment should make the system more accessible, not become a prerequisite for maintaining it.

Visual identity matters, but appearance must never take precedence over usability, accessibility, performance, or reliability. Each desktop should be treated according to its own design philosophy and intended use.

## XII. Editions must share one foundation

Sunshine editions may differ in included packages, defaults, and supported workflows. They must not become unrelated distributions with incompatible infrastructure.

Sol and Sirius should share core concepts, package ownership rules, management interfaces, desktop profiles, and release standards.

Optional capabilities must remain optional. A system should not acquire unnecessary complexity simply because another edition needs a particular tool.

Nix availability, desktop profile management, update validation, and recovery standards should not be restricted to a single edition.

## XIII. Security must be built into the architecture

Security cannot be reduced to a firewall toggle or a status screen.

Privileged tools, update mechanisms, repository metadata, signing keys, services, migrations, and recovery environments all belong to the security boundary.

Sunshine must minimize unnecessary privileges, verify software before executing it, protect signing material, audit enabled services, and document the trust assumptions of its integrations.

The core service must validate requests and enforce authorization independently of the user interface. Graphical tools should run without root privileges and request only the specific elevated operations they need.

Tools that can modify privileged system paths deserve particular scrutiny. Their own integrity, update process, rollback behaviour, and downgrade protections must be considered part of the system's security design.

Features such as Secure Boot must not be advertised as supported until the complete signing, enrollment, boot, update, and recovery workflows have been implemented and tested.

## XIV. Releases must earn trust

Sunshine releases must pass a defined acceptance process.

That process should cover ISO build integrity, boot, installation, first login, desktop startup, networking, audio, system management tools, upgrades, migrations, snapshots, rescue workflows, and update failure handling.

Testing should combine automated checks, virtual machines, and physical hardware. The test matrix should include all official desktop profiles, both officially supported filesystems, and both package-management modes: Arch-native and Arch + Nix.

A successful build is only the beginning of validation. A release must be tested through the workflows users are expected to rely on.

Sunshine must distinguish between a validated installation image and the continuing state of rolling package repositories. The project should describe what was tested, on which configurations, and what remains outside its guarantees.

Known limitations should be documented rather than concealed by release language. ZFS and other best-effort filesystems must not be represented as equivalent to the officially supported btrfs and ext4 configurations.

## XV. Complexity must justify itself

Every new component creates maintenance obligations: code, tests, documentation, compatibility, security review, and future migrations.

Sunshine should not add a daemon where a library and command-line interface are sufficient. It should not create a custom subsystem where an established interface already solves the problem. It should not duplicate functionality merely to give it a Sunshine name.

New technology should be introduced to solve a demonstrated problem, not to satisfy novelty.

The project should consolidate before it expands. It should prefer a small number of well-defined components over a large collection of overlapping tools.

## XVI. The user's system remains the user's system

Sunshine exists to help users operate and maintain their computers, not to take ownership away from them.

Users choose their package-management mode, primary desktop, additional environments, and system configuration. Sunshine provides the tools to make those choices understandable and workable.

Automation should be transparent and configurable. Destructive operations should require appropriate confirmation. Diagnostics should explain what they collect. Support reports should not upload information without the user's explicit action.

Users should be able to understand what Sunshine changes, why it changes it, which component owns it, and how to reverse supported changes.

Sunshine must respect the user's right to depart from its defaults. The project may explain the risks and limitations of an unsupported configuration, but it should not confuse recommendation with control.

## Our commitment

Sunshine OS will use the strength of established Linux ecosystems without surrendering responsibility for the experience it creates.

It will build its own infrastructure where integration demands it, preserve user control where choice matters, and treat reliability as a property that must be demonstrated through engineering and testing.

It will support multiple desktop experiences without fragmenting its foundation. It will make Nix available without making it mandatory. It will validate updates without taking away the user's choice of when to install them. It will maintain official support for btrfs and ext4 while remaining honest about the limited commitment attached to existing ZFS compatibility and other best-effort filesystems.

It will not measure progress by the number of utilities, services, themes, or features it ships.

It will measure progress by how consistently the system works, how clearly it explains itself, how much control it leaves in the user's hands, and how reliably it recovers when things go wrong.

**Sunshine OS: one integrated system, built on proven foundations, engineered for confidence.**
