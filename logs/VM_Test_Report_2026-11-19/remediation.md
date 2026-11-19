# Remediation and fixes — 13.4.7.1.5 test

This is the remediation record for the 2026-11-19 VM run. It distinguishes **what was fixed in the test VM**, **what is already fixed upstream**, and **what still needs a source change**.

---

## 1. Updater false-offline bug (R1)

### What was done during the test

The ISO ships `sunshine-base 0.6-1`, whose updater uses:

```bash
ping -c1 -W3 archlinux.org >/dev/null 2>&1 || {
  bad "No internet connection. Connect to Wi-Fi or a cable and try again."
  finish 1
}
```

I patched the live guest and the source with an HTTPS gate:

```bash
curl -fsS --max-time 8 -o /dev/null https://archlinux.org/feeds/news/ >/dev/null 2>&1 || {
  bad "No HTTPS access to the Arch repositories. Check the network/proxy and try again."
  finish 1
}
```

The source commit was `010cb5a` (“Fix update no-internet false negative: use HTTPS instead of ICMP ping”).

### What superseded it

While the test was running, upstream merged `e7acd96` (“merge origin/main — keep multi-method connectivity check”). The current source and `sunshine-base 0.7-1` use a better implementation in `/usr/local/lib/sunshine/ui.sh`:

```bash
sun_online() {
  SUN_NET_METHOD=; SUN_NET_WHY=
  if sun_online_quick 6; then SUN_NET_METHOD="HTTPS archlinux.org"; return 0; fi
  for u in https://geo.mirror.pkgbuild.com/ http://geo.mirror.pkgbuild.com/ https://www.gnu.org/; do
    if curl -fsI --max-time 6 "$u" >/dev/null 2>&1; then SUN_NET_METHOD="HTTP(S) $u"; return 0; fi
  done
  # captive-portal checks, NetworkManager, raw TCP, ping last
}
```

The installed system upgraded `sunshine-base 0.6-1 → 0.7-1` during `pacman -Syu`; this **replaced the injected patched file** with the upstream implementation, which is the desired outcome. The source tree is clean: no redundant local patch remains.

### Verified result

After the update, the full `sunshine-update` run completed:

```text
✔ Internet reachable (HTTPS archlinux.org)
✔ tools updated: 2026.11.19.217 -> 2026.11.19.219
✔ package keyring is current
✔ System packages are up to date
✔ Restore points are made automatically before and after the update
✔ All good
```

Evidence: [`raw/update-final.log`](raw/update-final.log), [`raw/final-verify.log`](raw/final-verify.log).

### Remaining release action

The **ISO**, not the repo, is still wrong. Rebuild it with `sunshine-base 0.7-1` or add a first-boot migration that runs the HTTPS check. Add a release test:

```bash
# In a NAT VM with ICMP blocked:
ping -c1 -W3 archlinux.org        # must fail (expected in this environment)
curl -fsS https://archlinux.org/  # must be 200
sunshine-update-run               # must pass the network gate
```

Do not ship an ISO whose own updater cannot update itself.

---

## 2. Firewall migration (R2)

The source migration is:

```bash
ufw --force enable >/dev/null && systemctl enable ufw.service >/dev/null 2>&1
echo "firewall on: ..."
exit 0
```

The `&&` is the bug: if `ufw --force enable` fails (e.g. iptables modules not ready, as seen in `raw/installed-update.log`), `systemctl enable` is skipped, but the script still writes the `0004-firewall-on` marker and prints success. The result in this VM: firewall inactive, unit disabled, migration marked `ok`.

### Recommended fix

```bash
#!/usr/bin/env bash
set -u
[ -d /run/archiso ] && exit 0
command -v ufw >/dev/null || exit 0
[ -e /etc/sunshine/no-firewall ] && exit 0
if ufw status 2>/dev/null | grep -q '^Status: active'; then
  systemctl enable ufw.service >/dev/null 2>&1 || true
  exit 0
fi
# ... rules ...
ufw --force enable >/dev/null 2>&1 || { echo "firewall could not be enabled"; exit 1; }
systemctl enable ufw.service >/dev/null 2>&1 || true
ufw status 2>/dev/null | grep -q '^Status: active' || { echo "firewall verification failed"; exit 1; }
echo "firewall on: incoming denied except KDE Connect and discovery"
```

Also add a boot check in `sunshine-doctor`: if `ufw` is installed and `/etc/sunshine/no-firewall` does not exist, require `Status: active` and `systemctl is-enabled ufw`.

### What was done in the test VM

```bash
sudo ufw --force enable
sudo systemctl enable ufw   # required separately; `ufw --force enable` left it disabled
```

Result: `Status: active`, `is-enabled = enabled`. Evidence: [`raw/enterprise-audit.log`](raw/enterprise-audit.log), [`raw/final-verify.log`](raw/final-verify.log).

---

## 3. `sunshine-diagnose` false initramfs alarm (R3)

`/boot/initramfs-linux.img` is `-rw------- root root`. `sunshine-diagnose` runs as the normal user, reads it, gets `EACCES`, and reports:

```text
/boot/initramfs-linux.img: PROBLEM reading it
```

Root `sunshine-doctor` says `All good`.

### Recommended fix

- Prefer `sudo -n`/`pkexec` for the read; if unavailable, stat the file and report “permission denied (run as root to verify)” instead of “problem”.
- Only call `lsinitcpio`/`zstd -t` when the file is readable.
- Add a regression test: run `sunshine-diagnose` as a normal user on a healthy install; assert no “PROBLEM” line.

Evidence: [`raw/final-verify.log`](raw/final-verify.log) (`diagnose as user`).

---

## 4. Design fix for action icons

The reported issue is KDE app toolbar/action icons reading too dark on the dark theme. The global icon SVGs are already `#DEDEDE`; the likely causes are inactive-window dimming, 16 px toolbar icons, and low-contrast disabled/inactive states.

Recommended change:

- Add an `ActionIconNormal = #EAF2FF` token (very light pastel blue) for symbolic action icons; `#FFFFFF` on hover; `#FFD27A` when checked; `#8F93A6` disabled.
- Raise Kvantum `toolbar_icon_size` and `button_icon_size` from 16 to 18–20.
- Test Konsole/Kate/Dolphin in active and inactive windows at 100–200 % scaling.
- Keep the orange app-launcher icons; do not recolour the whole theme.

Details and acceptance criteria: [`design-dissection.md`](design-dissection.md), section 3.

---

## 5. Test-system changes (not product defaults)

These were applied to the VM to make the visual test possible; they are **not** part of the reviewed product defaults:

| Change | Why | Remove? |
|---|---|---|
| `/etc/sddm.conf.d/zz-test-autologin.conf` (`User=sunshine`, `Session=plasma`) | Needed to reach the installed desktop for screenshots/OCR in a headless-driven VM. | Yes, for a clean default; keep for the live demo. |
| `xdotool` installed in the live session | Mouse/keyboard automation for Calamares and Kate. | Not in the installed system by default. |
| `ufw` enabled + unit enabled | Manual remediation of R2. | Keep for a secure demo; the product should do it. |
| Patched `sunshine-update-run` injected before install | Tested R1 before 0.7-1 arrived. | Replaced by the package update; source is clean. |
| Live-view HTTP bridge (`live-view/server.py`) | Host is headless; user wanted to watch/control the VM. | Test tooling only; not shipped. |

---

## 6. Reproducible verification commands

```bash
# Release / ISO
sha256sum -c SunshineOS_13.4.7.1.5_Release_2026-11-19.iso.sha256

# Live baseline
systemctl is-system-running
systemctl --failed
pacman-key --list-keys | grep -A2 8253720323C575207CC781B5DB345EF676CCD13D

# Updater bug (old ISO)
sudo -n /usr/local/bin/sunshine-update-run </dev/null
ping -c1 -W3 archlinux.org; curl -fsS -o /dev/null -w '%{http_code}\n' https://archlinux.org/

# Install
sudo env SUNSHINE_AUTO=1 SUNSHINE_DISK=/dev/sda SUNSHINE_USER=sunshine \
  SUNSHINE_PASS=sunshine SUNSHINE_FS=btrfs /usr/local/bin/sunshine-install

# Installed health
systemctl is-system-running
systemctl --failed
pacman -Dk
sudo /usr/local/bin/sunshine-doctor --quiet
/usr/local/bin/sunshine-diagnose --print

# Firewall
sudo ufw status verbose
systemctl is-enabled ufw

# Update
sudo env SUNSHINE_UPDATE_HERE=1 /usr/local/bin/sunshine-update-run
```

---

## 7. Current source status

- `origin/main` contains the multi-method connectivity check (`e7acd96`), the Calamares `$p` fix, the `sys` import fix, the `tr` shadowing fix, GTK/Kvantum skel defaults, the 4 GiB overlay, and the Hyprland keyring fix.
- The test tree is clean after the report commit; no uncommitted source edits remain.
- The two release actions that still need source work are **R2 (firewall migration fail-closed)** and **R3 (diagnose permission handling)**; R1 is fixed in source but not in the shipped ISO.
