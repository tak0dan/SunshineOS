# Sunshine OS

### 🌐 **[Open the website → tak0dan.github.io/sunshineos-site](https://tak0dan.github.io/sunshineos-site/)**

[![Download](https://img.shields.io/badge/Download-latest%20ISO-ff6a1a?style=for-the-badge)](https://github.com/tak0dan/SunshineOS/releases/latest)

![Sunshine OS](docs/screenshots/hero.png)

## A beautiful desktop. A system built to work.

Sunshine OS combines the freedom and freshness of Arch Linux with the convenience of a carefully configured desktop
experience. Get the latest packages, a unified software store, an intuitive Hyprland desktop and a complete set of tools for
system maintenance and recovery. From graphical application management to Btrfs snapshots and dedicated repair utilities,
everything is designed to make your everyday computing experience both enjoyable and dependable.

**Beautiful on the surface. Thoughtfully engineered underneath.**

Sunshine OS is a standalone Arch-based distribution, built with archiso and installed with Calamares. It can be used from the
terminal as well as from a graphical desktop.

## Install

Write the ISO to a USB stick and boot it. Nothing on your computer changes until you press Install.

1. **Download the ISO** from the [website](https://tak0dan.github.io/sunshineos-site/#install) or the
   [releases page](https://github.com/tak0dan/SunshineOS/releases/latest).
2. **Write it to a USB stick.** Any tool works. On Linux, with `dd`:
   ```sh
   cd ~/Downloads
   sudo dd if=SunshineOS_<version>_Release_<date>.iso of=/dev/sdX bs=4M status=progress oflag=sync
   ```
3. **Boot and install.** The Welcome window opens by itself. Choose "Install Sunshine OS" and pick restore points. A graphical
   installer (Calamares) and a text installer are included.

![Install](docs/screenshots/install.png)

## What is included

- **Two environments:** KDE Plasma in the live session; the installer adds Hyprland with a Quickshell desktop.
- **Btrfs snapshots:** snapper takes timeline snapshots, `snap-pac` one before and after every package update, and
  `grub-btrfs` lists them in the GRUB menu.
- **Repair tools:** `sunshine-doctor`, `sunshine-boot-repair`, `sunshine-fix-pacman`, `sunshine-identity`.
- **Sunshine Store:** one application for pacman, the AUR and Flatpak.
- **Disk encryption, wallpaper-derived colours, terminal workflow, updates, phone and AirPods support.**

![What is included](docs/screenshots/features.png)

## System tools

`sunshine-doctor` checks identity, package manager, boot files, services and snapshots, and `--fix` repairs what is safe to
repair. See also `sunshine-snapshot`, `sunshine-cleanup`, `sunshine-update`, `sunshine-info`.

![System tools](docs/screenshots/tools.png)

## Specifications

Arch Linux (rolling) with the Arch kernel, systemd, GRUB on UEFI and legacy BIOS, btrfs, Wayland with Xwayland, PipeWire,
NetworkManager and the fish shell. Architecture: x86_64.

![Specifications](docs/screenshots/specs.png)

## Themes

The desktop takes its colours from the wallpaper, and the website follows the same palette. Sunrise, Noon, Ember, Dusk and
Midnight.

![Themes](docs/screenshots/themes.png)

## Build

Needs: Docker (your user in the `docker` group), `git`, `rsync`, about 25 GB free disk and a network connection.

```
./make-iso.sh          # clean checkout -> ISO in out/ (resumes where it stopped if re-run)
./make-iso.sh --clean  # rebuild image, AUR packages and the Hyprland payload from scratch
```

`make-iso.sh` runs these steps, each of which can also be run on its own:

| step | script | result |
|------|--------|--------|
| 1. builder image | `docker build -t sunshineos-builder .` | Arch container with archiso |
| 2. AUR packages | `build-aur.sh` (list from `tools/aur-list.sh`) | local pacman repo in `repo/` |
| 3. Hyprland payload | `tools/import-end4.sh`, `tools/build-venv.sh` | dotfiles, offline package repo and Python venv under `profile/airootfs/usr/share/sunshine/hyprland/` |
| 4. the ISO | `build.sh` | `out/*.iso` |

Some packages in `profile/packages.x86_64` and `hyprland/packages.txt` are not in the official repos. `tools/aur-list.sh`
works out which, and `build-aur.sh` builds them from the AUR (or from `pkgs/<name>/PKGBUILD` when there is a local one).
Packages and downloads are cached in `cache/` (override with `SUNSHINE_CACHE`); logs go to `logs/`.
The scripts hand all output back to your own user, so no `sudo` is needed.

If an AUR dependency disappears upstream, add a replacement to `DEAD_DEP` at the top of `make-iso.sh`
(or fix the PKGBUILD in `pkgs/`).

## Testing before the slow build

The release ISO takes a long time because of the `xz` compression. Most problems show up without it:

```
FAST=1 ./build.sh     # test image, light compression, written to out/fast/
test/smoke.sh         # boots it headless in QEMU with no network (about 3 minutes)
```

`test/smoke.sh` checks that the system boots and settles offline, has no failed units, that package files kept their permissions,
that D-Bus, NetworkManager and the display manager run, and that the desktop session starts (screenshot in `test/tmp/smoke/`).
Run it before every release build.

## Publishing

The ISO is stored on GitHub Releases in parts (GitHub refuses files of 2 GiB or more) and a Cloudflare Worker serves the newest
release as one file, so the website's download button is an ordinary link.

```
tools/release-github.sh     # split out/*.iso into parts and create the GitHub Release (DRY=1 to preview)
SITE_DIR=<clone of the site repo> DOWNLOAD_URL=<Worker URL> JSON_ONLY=1 tools/release-github.sh   # write the release into the site's release.json
```

- `worker/iso-download.js` is the Worker's code (deploy it in the Cloudflare dashboard; it reads the site's `release.json`).
- The published name is `SunshineOS_<D>.<M>.<months>.<big>.<small>_<Release|Beta|Testing>_<date>.iso`:
  `<D>.<M>` and `<months>` come from a numbering anchor date kept in a local, git-ignored `ANCHOR` file (`<D>.<M>` is its day and
  month, `<months>` the whole months from it to the release date); `<big>.<small>` are the generation counters in the `VERSION`
  file; the channel is `Release` unless `SUNSHINE_CHANNEL=Beta|Testing`. Only `Release` files are served by the download button.
- To join the parts by hand: `cat SunshineOS_*.iso.part* > SunshineOS.iso`, then `sha256sum -c` against the `.sha256` file.

## Layout

- `profile/`  archiso profile (packages, airootfs, boot configs)
- `pkgs/`     local PKGBUILDs for AUR packages that need changes
- `hyprland/` Hyprland payload sources (installed on the target by the installer)
- `build.sh`  builds the ISO in a Docker container into `out/`
- `test/`     QEMU (UEFI + BIOS) boot and install tests using throwaway disks

## Terminal start-up animation

`sunshine-term` starts a terminal emulator (kitty, foot or konsole) that plays the Sunshine OS logo animation, runs
fastfetch and then drops into your normal shell. It is only a wrapper: no `.bashrc`, `.zshrc` or fish config and no emulator
is modified, so it works the same with bash, zsh and fish.

```
sunshine-term                              # first of foot, kitty, konsole (or $TERMINAL / $SUNSHINE_TERMINAL)
sunshine-term --emulator konsole           # pick one
sunshine-term --emulator kitty --class foo # everything else goes to the emulator unchanged
sunshine-term --no-splash --no-fastfetch   # skip parts
sunshine-term -- htop                      # run something after the animation instead of the shell
```

`sunshine-session` is the part that runs inside the window. Use `sunshine-term` wherever a terminal is launched (key binding,
launcher, `$TERMINAL`); "Terminal (Sunshine)" is also in the application menu. The animation (`/usr/share/sunshine/logo-anim`)
draws through the kitty graphics protocol, sixel (foot, konsole) or half-block characters, and is skipped silently if Python
with Pillow and numpy is missing.

## Repository layout

| Path | Purpose |
| --- | --- |
| `profile/` | archiso profile (packages, airootfs, boot configs) |
| `build.sh`, `make-iso.sh` | build the ISO in a Docker container into `out/` |
| `test/` | QEMU (UEFI + BIOS) boot and install tests using throwaway disks |
| `tools/` | helper scripts (branding, release publishing) |
| `worker/` | Cloudflare Worker that serves the ISO as one file |

Website source: [tak0dan/sunshineos-site](https://github.com/tak0dan/sunshineos-site).
