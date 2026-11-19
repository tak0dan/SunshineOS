# Sunshine OS 13.4.7.1.5 — VM test, enterprise diagnosis, and design review

**Test date:** 2026-11-19  
**Release under test:** Sunshine OS 13.4.7.1.5 (`v13.4.7.1.5-release-2026-11-19`)  
**ISO:** `SunshineOS_13.4.7.1.5_Release_2026-11-19.iso` (SHA-256 verified)  
**VM:** `SuOS-1.5-Test` — 4 vCPU, 5120 MiB RAM, BIOS, NAT, 20 GiB SATA disk, VirtualBox GUI  
**Previous test:** `logs/VM_Test_Report_2026-11-18/` on 13.4.7.1.4

---

## Verdict

**This is a real improvement over 13.4.7.1.4, and the first Sunshine ISO whose installed system I would hand to a non-technical user for a pilot.** The old release-breaking bugs are gone: the live keyring works, the Calamares `$p` failure is structurally removed, Welcome/Toolbox start, doctor no longer mangles its output, the live overlay is 4 GiB, GTK/Kvantum defaults ship in `/etc/skel`, the CLI installer completes on a 20 GiB disk, all 114 Hyprland packages install, the system boots with zero failed units, and a full update succeeds.

**It is not yet enterprise-ready.** Two release-process/security defects still matter, and the platform has no story for identity, fleet management, Secure Boot, compliance, or support lifecycle. Treat 13.4.7.1.5 as a strong **consumer / small-business pilot**, not as a corporate desktop replacement.

| Audience | Readiness | Why |
|---|---|---|
| Enthusiast / home user | **Good** | Coherent theme, friendly tools, working installer, snapshots, curated app catalogue. |
| Small business (5–50 seats), technical owner | **Pilot-ready after two fixes** | Install/update/recovery work; but updater is broken on the ISO until the first `pacman -Syu`, and the firewall migration can silently leave the firewall off. |
| Mid-size / regulated enterprise (500+ seats) | **Not ready (3–6 months of platform work)** | No AD/LDAP, MDM, fleet update rings, Secure Boot, MAC, audit policy, LTS lifecycle, or vendor support. |

The detailed enterprise case is in [`enterprise-readiness.md`](enterprise-readiness.md); the visual review is in [`design-dissection.md`](design-dissection.md); the patch history is in [`remediation.md`](remediation.md).

---

## What was tested

1. Downloaded the two-part ISO from the official release, joined it, verified SHA-256.
2. Booted a fresh VM and captured the live session: kernel, Plasma, storage, keyring, services, credentials.
3. Reproduced and diagnosed the `sunshine-update` false “no internet” failure.
4. Ran the complete system update and database checks.
5. Exercised OS-specific tools with real arguments: `sunshine-identity`, `sunshine-info`, `sunshine-diagnose`, `sunshine-doctor` / `--fix`, `sunshine-snapshot`, `sunshine-fix-pacman`, `sunshine-restore-visuals`, `sunshine-apps`, `uni`.
6. Opened Welcome, Toolbox, Store, Kate and the Calamares installer with a real Wayland session.
7. Installed to the 20 GiB disk with the non-interactive CLI path (btrfs, GRUB, Hyprland layer, 114/114 packages).
8. Injected the updater fix, removed the ISO, rebooted from disk, enabled autologin for the visual pass, and verified the installed system.
9. Ran a full `pacman -Syu` (kernel 7.3.4 → 7.3.5), rebooted, and re-verified.
10. Ran the fixed `sunshine-update` end to end, including tools sync, Arch news, mirrors, Flatpak and first-update apps.
11. Audited the installed system for enterprise capabilities and visual consistency.

Evidence: [`raw/`](raw/), [`screenshots/`](screenshots/) (OCR in [`screenshots/ocr.txt`](screenshots/ocr.txt)), [`live-session.md`](live-session.md), [`update-internet-gate.md`](update-internet-gate.md).

---

## Release-blocking findings

### R1 — The ISO ships an updater that falsely reports “no internet” (critical, release process)

The ISO contains `sunshine-base 0.6-1`, whose updater gate is an ICMP ping:

```bash
ping -c1 -W3 archlinux.org || { bad "No internet connection..."; exit 1; }
```

In VirtualBox NAT — and in many corporate networks — ICMP is dropped while HTTPS works. The VM had HTTP 200 from `archlinux.org`, GitHub and the release JSON, but 100 % ICMP loss. The GUI therefore refused to update on a working connection.

The repository already contains the proper fix in `sunshine-base 0.7-1`: `sun_online()` tries HTTPS first, then HTTP mirrors, captive-portal checks, NetworkManager, raw TCP, and only falls back to ping last. After the first `pacman -Syu` (which works, because pacman does not use the gate), the installed system has 0.7-1 and the updater completes normally:

```text
✔ Internet reachable (HTTPS archlinux.org)
... full system upgrade, Flatpak, health check, first-update apps
```

**The problem is the release pipeline, not the current source.** The ISO was built before 0.7-1 was published, so the release is broken out of the box and the user has to know to bypass the GUI with `pacman -Syu`. Rebuild the ISO after the repo freeze, or add a tiny first-boot migration that uses HTTPS and does not depend on the package update.

Full diagnosis: [`update-internet-gate.md`](update-internet-gate.md); evidence: [`raw/update-test.log`](raw/update-test.log), [`raw/network-gate-diagnosis.log`](raw/network-gate-diagnosis.log), [`raw/update-final.log`](raw/update-final.log).

### R2 — Firewall migration can report success while leaving the firewall disabled (critical, security)

`/usr/share/sunshine/migrations/0004-firewall-on.sh` runs:

```bash
ufw --force enable >/dev/null && systemctl enable ufw.service >/dev/null 2>&1
echo "firewall on: ..."
exit 0
```

On the installed system the migration marker was `ok`, but:

- `ufw status` was **inactive**;
- `systemctl is-enabled ufw` was **disabled**;
- the earlier update log was full of `iptables-restore ... Could not fetch rule set generation id`.

The `&&` means a failed `ufw --force enable` also skips `systemctl enable ufw.service`, while the script still prints success and writes the “done” marker. In this VM I enabled it manually:

```bash
sudo ufw --force enable
sudo systemctl enable ufw   # required separately; the first command left the unit disabled
```

Now `Status: active` and `is-enabled = enabled`. For an enterprise desktop, “firewall installed but off, and the migration says it is on” is not acceptable. Make the migration fail closed, check both commands, do not write the marker on failure, and add a boot-time verification.

Evidence: [`raw/enterprise-audit.log`](raw/enterprise-audit.log), [`raw/installed-update.log`](raw/installed-update.log), [`raw/final-verify.log`](raw/final-verify.log).

### R3 — `sunshine-diagnose` reports a false initramfs corruption as a normal user (high, trust)

Running the user-facing diagnostic:

```text
/boot/initramfs-linux.img: PROBLEM reading it
```

The file is `-rw------- root root`; the checker reads it without privilege and treats `EACCES` as corruption. Root's `sunshine-doctor` correctly says `All good`. A user will read this as “my boot image is broken” and may run a repair that is not needed. Either run the read-only check through `pkexec`/`sudo -n`, stat the file and report “permission denied” separately, or validate with `lsinitcpio` only as root.

Evidence: [`raw/final-verify.log`](raw/final-verify.log) (`diagnose as user` section).

---

## Comparison with 13.4.7.1.4

| Old finding | Status in 13.4.7.1.5 | Evidence |
|---|---|---|
| F1 `pacman-init.service` bad-setting; keyring unknown | **Fixed** — `active (exited)`, key `8253720323C575207CC781B5DB345EF676CCD13D` trusted, no failed units. | `raw/live-tests.log` |
| F2 Calamares `Missing variables are: p,p` | **Fixed in source** — the loop moved to `/usr/local/bin/sunshine-register-base`; no `$p` remains in the module. Calamares opens and advances past Welcome/Location. | `09-calamares-location.png`, `/etc/calamares/modules/shellprocess-ownbase.conf` |
| F3 `sunshine-welcome` / `sunshine-toolbox` `NameError: sys` | **Fixed** — `import sys` precedes `sys.path.insert`; both windows open. | `03-welcome.png`, `04-toolbox.png` |
| F4 `tr()` shadowing / dishonest doctor repair | **Fixed** — no `tr()` helper; doctor output is coherent and `--fix` completes with root. | `raw/tools-tests.log`, `raw/installed-deep-check.log` |
| F5 rsync broken pipe / 8 GiB disk | **Resolved by correct sizing** — 20 GiB disk, install `INSTALL_RC=0`; `--info=progress2` still present but works in a TTY. | `raw/install-auto.log` |
| F6 / F17 GTK/Kvantum missing from skel | **Fixed** — `/etc/skel` and the created user have GTK3/GTK4 + Kvantum Sunshine; fastfetch reports Sunshine Qt + Breeze-Dark GTK. | `raw/installed-deep-check.log` |
| F7 256 MiB cowspace | **Fixed** — 4 GiB live overlay. | `raw/live-tests.log` |
| F8 `sunshine-fix-pacman` false success | **Fixed in this run** — keyring/sync repair completes with rc 0 and no busy-device error. | `raw/tools-tests.log` |
| F9 Calamares warnings | **Not exhaustively re-tested**; the fatal `$p` path is gone and the GUI opens cleanly. | `09-calamares-location.png` |
| F10 harness `VERR_TOO_MUCH_DATA` | **Still an environment issue**; short scripts avoid it. | — |
| F11 VM-only journal noise (`kwin_wayland Modeset`, `VBoxService pam_loginuid`, `librepods` BLE) | **Still present, non-fatal.** | `raw/final-verify.log` |
| F12 Store opens / headless core dump | **Store opens** (onboarding visible); first load still heavy and `--help` still not implemented. | `05-store.png` |
| F13 inconsistent package DB | **Fixed** — `pacman -Dk` clean after update. | `raw/installed-update.log` |
| F14 / F16 undersized disk, stale btrfs | **Not reproduced** — fresh 20 GiB disk installed first time. | `raw/install-auto.log` |
| F15 live changes lost on reboot | **Expected live-ISO behavior**; installed system persists. | — |
| F18 all 114 Hyprland packages skipped | **Fixed** — `[1/114]` … `[114/114] ok`, `failed packages: none`. | `raw/install-auto.log` |
| F19 `systemd-networkd-wait-online` stuck | **Fixed** — `systemctl is-system-running = running`, zero failed units. | `raw/final-verify.log` |
| F20 `sunshine-base` not registered | **Fixed** — installed `sunshine-base 0.7-1`. | `raw/installed-update.log` |
| N1 GTK remains Breeze-Dark | **Still true** — no Sunshine GTK theme. | `raw/design-audit.log` |
| N2 fastfetch icon mismatch | **Live only**; installed system reports `Sunshine-orange-dark` for Qt and GTK. | `raw/final-verify.log` |
| N3 `--help` not implemented on several tools | **Still true.** | `raw/tools-tests.log` |
| N5 `--info=progress2` | **Still true**; low risk in a real terminal. | `/usr/local/bin/sunshine-install:217` |

**Net:** most of the substantive old findings are fixed or no longer reproducible. The remaining old issues are cosmetic, environment-specific, or intentionally deferred.

---

## Installed-system verification

| Check | Result |
|---|---|
| Boot from disk, ISO detached | `sunshine-os`, kernel `7.3.5-arch1-1` after update, btrfs `/dev/sda2[/@]` |
| `systemctl is-system-running` | `running` |
| Failed units | **0** |
| SDDM / VBoxService / NetworkManager | active |
| User session | `sunshine` on `seat0`, Plasma Wayland |
| Package DB | `pacman -Dk` → no errors |
| Disk | 11 GiB used of 20 GiB (55 %) |
| `sunshine-doctor --quiet` | `All good` (root) |
| `sunshine-snapshot status` | btrfs → snapper, configured |
| `uni detect` | Sunshine OS, pacman + flatpak + AUR sources |
| Theme | Qt `Sunshine (Dark)` / `Sunshine-orange-dark`; GTK `Breeze-Dark` |
| Boot time | 45.1 s in the VM (15.0 s is `systemd-time-wait-sync`) |

Evidence: [`raw/installed-verify.log`](raw/installed-verify.log), [`raw/installed-deep-check.log`](raw/installed-deep-check.log), [`raw/installed-update.log`](raw/installed-update.log), [`raw/final-verify.log`](raw/final-verify.log).

---

## Other observations

| ID | Severity | Observation |
|---|---|---|
| N1 | Medium | GTK apps still use `Breeze-Dark`, not a Sunshine GTK theme. The Qt/Kvantum/Plasma surface is branded; the GTK surface is not. |
| N2 | Medium | Boot is 45 s in the VM; `systemd-time-wait-sync.service` alone takes 15 s. A desktop should not block on time sync. |
| N3 | Medium | First boot/offline has **no office suite, mail client, or conferencing app**. `sunshine-apps first-update` installs LibreOffice and Zen on the first online update, but an offline install is not office-ready. |
| N4 | Medium | Only `en_US.UTF-8` is generated; 371 locale definitions exist but are not built. `noto-fonts-cjk` is absent. This is a hard blocker for international enterprises. |
| N5 | Medium | No accessibility stack: `orca`, `speech-dispatcher` and screen magnification are absent. |
| N6 | Low | `sunshine-restore-visuals --offline` coredumps `plasma-apply-colorscheme`/`plasma-apply-desktoptheme` when invoked from a headless shell without a Qt platform; it still prints “visuals restored”. In a real desktop session the theme applies. The tool should detect no display and say so. |
| N7 | Low | Several tools do not implement `--help` and run their normal job instead (`sunshine-fix-pacman`, `sunshine-restore-visuals`, `sunshine-hyprland-install`, `sunshine-install`). |
| N8 | Low | `sunshine-update` installs “Apps you chose” at the end of the first update. Useful, but it can add hundreds of MB and time without a clear size/confirmation prompt. |
| N9 | Low | The health timer and snapper timers are good defaults (`sunshine-health.timer` weekly + 15 min after boot; snapper pre/post snapshots). |
| N10 | Info | `sunshine-secureboot` is explicitly **read-only/planned**; it does not enroll keys or sign boot files. |
| N11 | Info | `journald` is not persistent (`#Storage=persistent`), and `auditd` is installed but disabled. Enterprise forensics/support would lose logs at reboot. |

---

## Enterprise and design documents

- **[`enterprise-readiness.md`](enterprise-readiness.md)** — the sales diagnosis: what to sell, what to fix, what is missing, what can be better, readiness scorecard, 90-day plan, TCO model, objection handling.
- **[`design-dissection.md`](design-dissection.md)** — theme, icons, typography, layout, copy, installer/store, accessibility, and the requested “action icons too dark” fix.
- **[`remediation.md`](remediation.md)** — source patches, what is already upstream, and the recommended fixes for R1–R3.

---

## Evidence index

| File | Contents |
|---|---|
| `release-info.md` | Release, assets, checksums, join/verify commands |
| `test-plan.md` | Test matrix and method |
| `live-session.md` | Live baseline and fixed/remaining findings |
| `update-internet-gate.md` | Full false-offline diagnosis and patch history |
| `raw/live-tests.log` | Live hardware/OS/services/tools baseline |
| `raw/update-test.log` | Unpatched updater failure |
| `raw/network-gate-diagnosis.log` | ICMP vs HTTPS evidence |
| `raw/pacman-update.log` | First full live update |
| `raw/tools-tests.log` | OS tool battery |
| `raw/install-auto.log` | Full CLI install (condensed) |
| `raw/installed-verify.log` | Post-install verification |
| `raw/installed-deep-check.log` | Boot files, doctor, theme |
| `raw/installed-update.log` | Kernel/package update |
| `raw/final-verify.log` | Final health, firewall, updater smoke |
| `raw/update-final.log` | Fixed updater end-to-end |
| `raw/enterprise-audit.log` | Identity, security, apps, lifecycle audit |
| `raw/design-audit.log` | Theme, icons, contrast, config |
| `screenshots/` | Live, installer, installed desktop, Kate action icons |
| `screenshots/ocr.txt` | OCR for every screenshot |
| `live-view/` | Headless live-view/input bridge used during testing |

---

## Bottom line

**Ship 13.4.7.1.5 to enthusiasts and small businesses after rebuilding the ISO with `sunshine-base 0.7-1` and fixing the firewall migration.** Do not sell it as an enterprise desktop yet: the product’s differentiators are real (repair-first tooling, snapshots, curated apps, coherent design, no telemetry), but the enterprise control plane — identity, policy, patching, Secure Boot, compliance, support — is missing. The fastest credible path is a 90-day “Sunshine for Small Business” pilot with a frozen snapshot, a curated repo, and an honest support contract, not a head-on Windows/Ubuntu enterprise replacement.
