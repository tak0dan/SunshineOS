# Why `sunshine-update` says “No internet connection” while the internet works

## Reproduction (first update attempt in this VM)

Command run very early in the 13.4.7.1.5 live session:

```text
sudo -n /usr/local/bin/sunshine-update-run </dev/null
```

Output (abridged; full evidence in `raw/update-test.log`):

```text
☀ Sunshine OS update
☀ Sunshine tools
✔ tools updated: none -> 2026.11.19.197 (2 files changed)
... migrations applied: 5
✘ No internet connection. Connect to Wi-Fi or a cable and try again.
```

The GUI entry point `/usr/local/bin/sunshine-update` only does:

```bash
exec konsole --hide-menubar -p tabtitle="Sunshine OS Update" \
  -e pkexec /usr/local/bin/sunshine-update-run "$@"
```

so the real decision is in `sunshine-update-run`.

## Root cause

The updater uses an **ICMP echo request (ping)** as its only internet test:

```bash
ping -c1 -W3 archlinux.org >/dev/null 2>&1 || {
  bad "No internet connection. Connect to Wi-Fi or a cable and try again."
  finish 1
}
```

In VirtualBox NAT (and many corporate/captive-portal networks) outbound ICMP is blocked or filtered while TCP/443 works fine. The result is a false negative:

| Check | Result |
|---|---|
| DHCP address / default route | `10.0.2.15/24`, default via `10.0.2.2` — OK |
| DNS `getent hosts archlinux.org` | resolves (`2604:cac0:a104:d::3` / A record available) — OK |
| `curl https://archlinux.org/` | **HTTP 200 in 0.27–0.31 s** |
| `curl https://tak0dan.github.io/sunshineos-site/release.json` | **HTTP 200 in 0.11 s** |
| `curl https://github.com` | **HTTP 200 in 0.66 s** |
| `ping archlinux.org` | **1 transmitted, 0 received, 100% packet loss** |
| `ping 1.1.1.1`, `ping 8.8.8.8`, `ping github.com` | also 100% packet loss — ICMP is blocked globally for this VM |

Evidence: `raw/update-test.log` and `raw/network-gate-diagnosis.log`.

So the message is wrong: the machine **has working HTTPS internet**, but the updater confuses “ICMP blocked” with “offline”. This was not fixed by the older F1 keyring fix; it is a separate, unconditional gate at the top of the updater.

## Fix applied

Replace the ICMP gate with an HTTPS request to a host the update already needs:

```bash
curl -fsS --max-time 8 -o /dev/null https://archlinux.org/feeds/news/ >/dev/null 2>&1 || {
  bad "No HTTPS access to the Arch repositories. Check the network/proxy and try again."
  finish 1
}
```

Benefits:

- Tests the same transport (`TCP/443`) that `pacman`, `checkupdates`, `rate-mirrors`, `curl` news, toolsync and the release check use.
- Works behind NAT networks where ICMP is dropped.
- Still fails clearly when DNS/TLS/proxy is genuinely broken.
- Aligns with `sunshine-update-check`, which already uses `curl` for `release.json`.

The patched script is stored in `fixes/sunshine-update-run`. It was copied into the live guest as `/usr/local/bin/sunshine-update-run` and will also be injected into the installed target before first boot.

## Side observation

Running `/usr/local/bin/sunshine-update` from a headless `guestcontrol` shell with no `DISPLAY` makes `konsole` abort and dump core (rc 134). That is a harness/display issue, not the no-internet bug. The actual updater logic was tested through `sunshine-update-run` as root.

---

## Post-update finding (2026-11-19 16:49 UTC) — the upstream fix is better, and the ISO is stale

After the installed system's first `pacman -Syu`, `sunshine-base` upgraded **0.6-1 → 0.7-1**. The 0.7-1 updater no longer uses a single ping gate. It calls `sun_online()` from `/usr/local/lib/sunshine/ui.sh`, which tries, in order:

1. `curl` HTTPS to `archlinux.org`;
2. HTTP/HTTPS to the Arch mirror network and GNU;
3. captive-portal checks (HTTP 204 vs 30x);
4. NetworkManager's connectivity verdict;
5. raw TCP to `1.1.1.1:443`, `8.8.8.8:53`, `9.9.9.9:443`;
6. **ping only as the last resort.**

This is the correct design and it completely fixes the false-offline failure in NAT/corporate networks. The full run then completed:

```text
☀ Sunshine OS update
✔ tools updated: 2026.11.19.217 -> 2026.11.19.219 (3 files changed)
✔ Internet reachable (HTTPS archlinux.org)
☀ Latest Arch Linux news ...
✔ Package keyring is current
✔ System packages are up to date
✔ Restore points are made automatically before and after the update
☀ Updating Flatpak apps ... Nothing to update.
☀ Final health check ... All good
☀ Tidying up ... Old package cache cleaned
☀ Apps you chose ... (LibreOffice, Zen)
```

Evidence: `raw/update-final.log`, `raw/final-verify.log`.

**However:** the ISO under test ships 0.6-1, so a fresh user still hits the false “No internet connection” before they can reach the package that fixes it. `pacman -Syu` works (it does not use the gate), but a non-technical user will not know that. The release process must rebuild the ISO after `sunshine-base 0.7-1` is published, or add a first-boot HTTPS migration. This is recorded as R1 in the final report.

Our local source patch (`010cb5a`) was superseded by upstream commit `e7acd96` (“keep multi-method connectivity check”). The injection into the installed target was overwritten by the package update — which is the desired outcome. The source tree has no redundant patch.
