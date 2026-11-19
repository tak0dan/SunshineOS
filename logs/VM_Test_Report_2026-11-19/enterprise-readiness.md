# Enterprise readiness diagnosis — Sunshine OS 13.4.7.1.5

**Question:** can this be sold to an enterprise as the new desktop OS for employees and users?

**Short answer:** not yet as an enterprise replacement. It can be sold **now** as a low-cost, design-led, self-healing desktop for small businesses, schools, labs, and technical teams — provided two release defects are fixed and the buyer accepts a curated rolling-release model. For a 500+ seat regulated enterprise, the missing control plane is the product, and it does not exist yet.

This document is deliberately written as a sales/engineering diagnosis: what to lead with, what blocks the deal, what is missing, and what to build next.

---

## 1. The pitch that is actually true

> **“The desktop your helpdesk can actually fix.”**
>
> Sunshine OS is a complete, beautifully consistent Linux desktop with built-in diagnostics, one-click repair, automatic restore points, a curated app catalogue, and no telemetry. It installs in minutes, rolls back a bad update from the boot menu, and gives non-technical users a friendly first-run hub instead of a terminal.

That is a credible, differentiated pitch because the product actually does those things. It is **not** credible to pitch “Windows replacement for the whole enterprise” yet, because the things enterprises buy — identity, policy, fleet patching, compliance, support — are exactly the things Sunshine does not have.

### Best-fit buyers

| Segment | Fit | Why |
|---|---|---|
| Small business 5–50 seats, one technical owner | **Strong pilot** | Low license cost, easy install, snapshots, repair tools, curated apps. |
| Schools / training labs / libraries | **Strong** | Reset-friendly, offline install, kiosk potential, low cost. |
| Software teams / privacy-sensitive SMB | **Good** | Full Arch/AUR/Flatpak access, no telemetry, modern kernel, containers/dev tools. |
| Call centres / task workers | **Conditional** | Needs kiosk mode, browser policy, VDI/RDP clients, central management. |
| Regulated enterprise 500+ seats | **Not ready** | No AD/LDAP, MDM, Secure Boot chain, MAC, audit policy, LTS, or vendor SLA. |
| Public sector / defence | **Not ready** | Certification, reproducible builds, secure supply chain, accessibility compliance. |

---

## 2. What to sell (the genuine selling points)

### 2.1 Repair-first UX — the strongest differentiator

Most Linux distros ship a desktop and leave recovery to the community. Sunshine ships a full first-party toolbox:

- `sunshine-doctor` / `--fix` — checks packages, services, boot files, disk, theme, and repairs common breakage.
- `sunshine-diagnose` — one-screen health report.
- `sunshine-fix-pacman` — repairs keyring, databases, partial upgrades, AUR helpers.
- `sunshine-snapshot` — btrfs/snapper restore points.
- `sunshine-rescue`, `sunshine-boot-repair`, `sunshine-backup`.
- `sunshine-health.timer` — silent weekly + post-boot health scan.

For a small business without a Linux admin, this is the difference between “a project” and “a product”.

**Demo script:** break a package database, run `sunshine-fix-pacman`, show the green result; roll back an update from the GRUB snapshot menu. That demo closes SMB deals.

### 2.2 Snapshot-first updates

On btrfs, snapper creates pre/post snapshots around updates and `grub-btrfs` exposes them in the boot menu. The updater explicitly tells the user: “go back from the boot menu if anything breaks.” This is a credible safety net that Windows 10/11 and many Linux distros do not offer out of the box.

### 2.3 Coherent, distinctive design

The warm amber-on-graphite identity is consistent across Plasma, SDDM, GRUB, Calamares, Kvantum, the panel, the wallpaper and the icon set. It looks like a product, not a remix. For buyers tired of “default GNOME” or “default KDE”, this is a real differentiator — with one visible gap (GTK apps, see the design review).

### 2.4 Curated app catalogue without a walled garden

`sunshine-app-*` metapackages (322-1) wrap the official packages, AUR packages, setup scripts and web apps:

- one command installs a working app with its services, groups, firewall rules and theme;
- first-update apps (LibreOffice, Zen) are installed automatically on the installed system;
- the same catalogue offers alternative desktops (GNOME, Cinnamon, XFCE, LXQt, MATE, i3, Sway);
- users can still use pacman, AUR, Flatpak, AppImage and web apps.

This is a good “best of both” story: curated for normal users, open for power users.

### 2.5 No telemetry, no account, offline install

The ISO installs from local squashfs; no Microsoft/Google account, no telemetry agent, no activation server. For privacy-sensitive SMBs, schools and public institutions, this is a strong compliance-adjacent selling point.

### 2.6 Fast, lean install

- 3.3 GB ISO, ~11 GB installed, 345 explicit packages, 1,295 total.
- 20 GiB disk is enough; 4 GiB live overlay.
- Installed system: zero failed units, `systemd is-system-running = running`.

### 2.7 Full Arch ecosystem

Modern kernel, Mesa, PipeWire, Plasma 6, Hyprland option, AUR/Flatpak, containers and dev tooling. This appeals to technical teams and creators, and avoids the “old packages” problem of LTS distros.

### 2.8 Honest engineering culture

`sunshine-secureboot` says “planned, read-only, do not brick your machine” instead of pretending. The updater reads Arch news and stops on “manual intervention required” items. The tools explain what they do. That honesty is a selling point — if it is matched by release discipline.

---

## 3. What must be fixed before a paid pilot (P0)

These are not “nice to have”. They will lose a pilot on day one.

### P0.1 Rebuild the ISO with `sunshine-base 0.7-1`

The ISO ships 0.6-1, whose updater uses ping as the only internet test. In NAT/corporate networks it says “No internet connection” while HTTPS works. The repo already has the fix (multi-method `sun_online`, HTTPS first). Rebuild the ISO after the repo freeze; add a release gate that installs the ISO's own updater and runs it against a network with ICMP blocked.

**Acceptance:** fresh ISO in a NAT VM with ICMP dropped → `sunshine-update` reaches “Checking for updates” without manual `pacman -Syu`.

### P0.2 Make the firewall migration fail closed

`0004-firewall-on.sh` writes `ok` even when `ufw --force enable` fails, and `&& systemctl enable ufw.service` is skipped. The installed system ended with firewall inactive and unit disabled.

**Fix:** run both commands independently, verify `ufw status` and `systemctl is-enabled ufw`, retry once, and do not write the marker on failure. Add a boot check that reports “firewall off” in `sunshine-doctor`.

**Acceptance:** fresh install → reboot → `ufw status` active, `systemctl is-enabled ufw` enabled, doctor green.

### P0.3 Fix the false initramfs alarm in `sunshine-diagnose`

The user-facing diagnostic reads `/boot/initramfs-linux.img` as an unprivileged user and reports “PROBLEM reading it” because the file is mode 600. Root doctor says “All good”.

**Fix:** use `pkexec`/`sudo -n` for the read, or separate `EACCES` from corruption; never show a red “problem” for a permission boundary.

**Acceptance:** `sunshine-diagnose` as a normal user on a healthy install → no boot-image problem.

### P0.4 Make the first update predictable

`sunshine-update` installs “Apps you chose” at the end (LibreOffice, Zen) and may run for many minutes. Show the download size, the list of apps, and a confirmation/“skip for now” path; or move first-update apps to a separate first-login wizard with progress.

**Acceptance:** the user sees what will be installed and how large it is before the long step.

---

## 4. What is missing for enterprise (P1)

### 4.1 Identity and access

- No `sssd`, `realmd`, `adcli`, `samba`/`winbind`; no AD/LDAP join, no Kerberos ticket UI.
- No SSO for the browser, no certificate auto-enrollment, no smart-card/PIV stack.
- Local user is in `wheel` with password sudo; no sudo policy/role separation beyond that.

**Build:** `sunshine-enroll` (realm join, SSSD, sudo rules, home dir policy), a KCM for identity, and a tested offline/online join flow.

### 4.2 Fleet management and policy

- No MDM/Intune-like agent, no Ansible/Puppet/Chef/Salt, no Cockpit, no remote inventory.
- SSH is installed but disabled; there is no supported remote-management channel.
- No configuration profiles (browser homepage/extensions, proxy, power, updates, screen lock).

**Build:** a small `sunshine-fleet` agent with signed policy bundles, inventory, compliance status and remote actions; or publish supported Ansible roles and a Cockpit module. Do not invent a proprietary protocol if the buyer already has Ansible.

### 4.3 Patch management and lifecycle

- Rolling Arch, no LTS branch, no CVE SLA, no staged rollout rings.
- `sunshine-update` is interactive and desktop-bound; no maintenance windows, no “update at 02:00 and reboot”, no fleet reporting.
- `chaotic-aur` is enabled by default — a community binary repo, unacceptable in many enterprises.
- `[sunshine]` repo is a GitHub Releases URL; fine for SMB, weak for enterprise mirroring.

**Build:** a frozen “Enterprise” snapshot repo (signed, mirrored, pinned), `linux-lts` default, update rings (canary → IT → pilot → broad), a `sunshine-update --unattended --max-wait` mode, and a patch report. Disable `chaotic-aur` in the enterprise profile or mirror it internally.

### 4.4 Boot integrity and encryption

- `sunshine-secureboot` is read-only/planned; no `shim`, `sbctl`, `sbsigntools`.
- The test install is BIOS/GRUB; no Secure Boot chain, no TPM measured boot.
- Disk encryption is optional (`sunshine-crypt-setup`), not default, and there is no recovery-key escrow.

**Build:** UEFI + shim + signed GRUB/kernel, `sbctl` enrollment, LUKS2 + TPM2 unlock with escrow, and a documented recovery flow. This is a hard requirement for regulated buyers and lost/stolen-laptop policy.

### 4.5 Host hardening and audit

- No SELinux/AppArmor.
- `auditd` installed but disabled; no audit rules.
- `journald` not persistent; logs vanish at reboot.
- Firewall rules are minimal and, as shipped, not reliably enabled.
- `firefox` has no enterprise `policies.json`; Flathub is enabled by default.

**Build:** an “Enterprise hardening” profile: MAC (AppArmor at minimum), audit rules, persistent journal, firewall on, Firefox/Chromium policy templates, curated Flatpak remote, USB/port policy.

### 4.6 Support and observability

- No `--json` output for inventory/health; no metrics/logs agent.
- `sunshine-support` exists but is not a signed, redacted, uploadable bundle with a case ID.
- No lifecycle/SLA documentation, no security contact, no CVE process.

**Build:** machine-readable health (`sunshine-doctor --json`), a support bundle with redaction, opt-in telemetry (or none), a security policy, and an SLA.

### 4.7 Accessibility and internationalization

- No Orca/screen reader, no magnification, no on-screen keyboard out of the box.
- Only `en_US.UTF-8` generated; no CJK fonts.
- This alone disqualifies public-sector and multinational deals.

**Build:** accessibility meta package, locale/font selection in the installer, and a11y testing in CI.

---

## 5. What can be better (P2, differentiators)

1. **“Sunshine for Business” edition** — same desktop, enterprise repo, LTS kernel, no chaotic-aur, firewall/hardening profile, fleet agent, support. Price per seat/year, not per device.
2. **One-command pilot** — `sunshine-pilot` creates a signed inventory, joins a domain, applies policy, and produces a readiness report.
3. **Kiosk / shared-device mode** — browser lock-down, auto-reset home, guest session, asset tag.
4. **VDI/RDP bundle** — FreeRDP/Remmina, VMware Horizon, Citrix Workspace, Chrome Remote Desktop, with working smart-card/SSO.
5. **Hardware certification** — Dell/Lenovo/HP business laptops, fwupd, dock support, fingerprint, TPM. Publish a compatibility list.
6. **App compatibility story** — LibreOffice/OnlyOffice/WPS, Teams/Slack/Zoom (Flatpak/web), SAP/legacy via Wine/Bottles, and a tested browser policy.
7. **Migration assistant** — import bookmarks, files, printers, Wi-Fi, and (where legally possible) a Windows user profile.
8. **Better boot performance** — 45 s in a VM is not terrible, but 15 s of `systemd-time-wait-sync` is avoidable; target < 20 s on business hardware.
9. **Read-only root / immutable option** — for kiosks and task workers, an immutable image with a writable home is a strong enterprise story.
10. **Brand the cursor and GTK** — finish the visual system; today the pointer and GTK apps break the illusion.
11. **Professional tone option** — keep the cozy consumer voice, but offer a “business” copy set without coffee/emoji for enterprise images.
12. **Better first-run** — the Store onboarding “pick anything that sounds like you” is consumer-friendly but odd in a managed fleet; add “managed by IT” and skip.

---

## 6. Readiness scorecard

Scores are 1–5 (1 = absent, 5 = enterprise-grade).

| Dimension | Score | Notes |
|---|---:|---|
| Install & first boot | **4** | CLI install clean, Calamares fixed, 20 GiB enough; GUI install not completed end-to-end in this run. |
| Desktop quality | **4** | Coherent Plasma, good defaults, Hyprland option; GTK gap and action-icon contrast. |
| Updates & rollback | **3** | Snapper/GRUB rollback is excellent; updater broken on the ISO, no fleet rings/LTS. |
| Security baseline | **2** | Root locked, faillock, signed repos; firewall off by default, no MAC, no Secure Boot, audit off. |
| Identity & access | **1** | Local accounts only. |
| Fleet management | **1** | No agent, no policy, no inventory, SSH off. |
| App compatibility | **3** | Huge catalogue, LibreOffice/Zen first-update; no preinstalled office/mail/VDI, no browser policy. |
| Accessibility & i18n | **1** | No screen reader, one locale, no CJK fonts. |
| Support & lifecycle | **2** | Honest tools and docs; no SLA, no LTS, no CVE process. |
| Supply chain | **2** | Signed `[sunshine]` repo, but chaotic-aur by default and GitHub-hosted repo. |
| **Overall for SMB pilot** | **7/10** | Fix P0.1–P0.3 and it is a credible paid pilot. |
| **Overall for regulated enterprise** | **2.5/10** | Control plane, compliance and lifecycle are missing. |

---

## 7. 90-day plan to a sellable enterprise pilot

### Days 0–30 — make the release trustworthy

- Rebuild ISO with `sunshine-base 0.7-1`; add NAT/ICMP-blocked release test.
- Fix firewall migration and add doctor check.
- Fix `sunshine-diagnose` permission false positive.
- Add `--json` to doctor/diagnose/info; add exit codes.
- Publish a security policy and a CVE contact.
- Freeze a signed “pilot” repo snapshot; document rollback.

### Days 31–60 — make it manageable

- `sunshine-enroll` for AD/LDAP (SSSD/realmd), sudo rules, home policy.
- `sunshine-fleet` agent or supported Ansible roles: inventory, policy, patch status, remote actions.
- Update rings + unattended update mode + maintenance window.
- Firefox/Chromium policy templates; curated Flatpak remote; disable chaotic-aur in business profile.
- Persistent journal, auditd profile, AppArmor baseline.

### Days 61–90 — make it sellable

- UEFI Secure Boot (shim + sbctl) and LUKS2 + TPM2 with escrow.
- Accessibility + locale/font selection.
- Hardware compatibility list (3–5 business laptop models).
- Pilot kit: 25-seat deployment guide, success metrics, support SLA, rollback runbook.
- TCO model and reference customer.

---

## 8. TCO model (use a formula, not a fake number)

Do **not** promise “70 % cheaper” without a customer-specific model. Use this:

```text
annual cost per seat =
    hardware amortisation
  + OS licence (0 for Sunshine)
  + management/tooling (fleet agent, repo mirror, monitoring)
  + support contract
  + IT labour (deployment, patching, incidents)
  + app licences (Office/Teams/VDI)
  - avoided Windows/AV/management licences
```

The Sunshine advantage is in **licence avoidance + lower incident labour** (snapshots, repair tools, no malware-focused AV tax). The risk is **maturity labour** (pilot hardening, domain join, packaging exceptions). Be honest: the first 6 months cost more in engineering than they save; the break-even is in years 2–3 at 100+ seats.

---

## 9. Objection handling

| Objection | Response |
|---|---|
| “Arch is unstable.” | “The desktop is Arch, the *product* is a frozen, signed snapshot with staged update rings and boot-menu rollback. Pilot customers stay on a curated snapshot; power users can opt into rolling.” |
| “We need Active Directory.” | “Not in 13.4.7.1.5. AD/LDAP enrollment is the first item in the 90-day plan; until it ships, we only sell to environments that can use local accounts or a separate IdP for apps.” |
| “Where is Office/Teams?” | “LibreOffice and Zen install on first update; Teams/Zoom run as Flatpak/web apps; OnlyOffice/WPS are in the catalogue. For document-heavy regulated users, validate macros/add-ins first.” |
| “Who supports it?” | “A per-seat support subscription with a named escalation path, a signed repo, and a rollback runbook. Without that contract, do not deploy.” |
| “Is it secure?” | “Signed packages, locked root, faillock, firewall, no telemetry. Secure Boot, MAC and audit are on the roadmap; regulated buyers should wait for the hardening profile.” |
| “Will our hardware work?” | “We certify 3–5 business laptop models per release and publish the list; fwupd handles firmware. Test docks, fingerprint and TPM before committing.” |
| “We can just use Ubuntu LTS.” | “Ubuntu gives you a stable base and a management ecosystem; Sunshine gives you a design-led desktop with repair/snapshot UX and a curated app catalogue. If you need the ecosystem today, Ubuntu wins. If you want lower support touch and a distinctive desktop, pilot Sunshine.” |

---

## 10. Deal shape that fits the product

**Offer:** “Sunshine Business Pilot — 25 seats, 90 days.”

- Frozen signed repo snapshot, LTS kernel, business profile (firewall on, chaotic-aur off, persistent logs, browser policy).
- 10 business laptops, one site, one IT owner.
- Success criteria: install time, first-line ticket volume, update success rate, rollback time, user satisfaction, app compatibility blockers.
- Exit criteria: if AD join or Office macros block, document and defer; do not force a bad fit.

**Do not sell:** 500-seat replacement, regulated compliance, VDI-heavy call centres, or “we support everything” — until the control plane exists.

---

## 11. Bottom line for the sales team

Lead with **repair, rollback, design and no telemetry**. Sell to **small businesses and schools** first. Be explicit that **enterprise management is a roadmap, not a feature**. Fix the ISO updater and firewall before any demo. The product is charming and technically credible; the missing piece is not the desktop, it is the **enterprise operating model** around it.
