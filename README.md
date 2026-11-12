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
