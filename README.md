# Sunshine OS

Standalone Arch-based distribution, built with archiso inside a container.
Nothing here modifies the build host.

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
