#!/usr/bin/env bash
# Build AUR packages inside the builder container into ./repo (local pacman repo "sunshine").
# Usage: ./build-aur.sh [pkg ...]     with no arguments: every AUR-only package the ISO needs (tools/aur-list.sh)
#        FORCE=1 ./build-aur.sh       rebuild even if a package is already in ./repo
# Runs ONLY in Docker; nothing is installed on or modified on the host. Needs the sunshineos-builder image (see ./make-iso.sh).
set -euo pipefail
cd "$(dirname "$0")"
CACHE=${SUNSHINE_CACHE:-$PWD/cache}   # downloads are kept here between builds
mkdir -p repo aur pkgs "$CACHE/pacman" "$CACHE/aur-src"
chmod -R a+rwX "$CACHE/pacman" 2>/dev/null || true   # the container's unprivileged download user must be able to write here
if [ $# -eq 0 ]; then mapfile -t pk < <(tools/aur-list.sh); set -- "${pk[@]}"; fi
if [ -z "${FORCE:-}" ]; then   # skip what is already built (file name: <name>-<ver>-<rel>-<arch>.pkg.tar.zst)
  todo=(); for p in "$@"; do ls repo | grep -qE "^$p-[^-]+-[0-9]+-(any|x86_64)\.pkg\.tar\.zst$" || todo+=("$p"); done
  set -- ${todo[@]+"${todo[@]}"}
fi
[ $# -gt 0 ] || { echo "build-aur: nothing to build"; exit 0; }
echo "build-aur: $*"
docker run --rm -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -v "$CACHE/pacman:/var/cache/pacman/pkg" -v "$CACHE/aur-src:/srcdest" -v "$PWD/repo:/repo" -v "$PWD/aur:/aur" -v "$PWD/pkgs:/pkgs:ro" \
  sunshineos-builder bash -c '
  pacman -Sy --noconfirm >/dev/null 2>&1
  id builder &>/dev/null || useradd -m builder
  echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder
  chown -R builder /aur /repo /srcdest
  failed=()
  for p in "$@"; do
    sudo -u builder bash -c "
      set -e; cd /aur; rm -rf $p
      if [ -d /pkgs/$p ]; then cp -r /pkgs/$p $p; else for i in 1 2 3; do rm -rf $p; git clone -q https://aur.archlinux.org/$p.git && [ -f $p/PKGBUILD ] && break; sleep 5; done; fi
      cd $p
      SRCDEST=/srcdest MAKEFLAGS=-j\$(nproc) makepkg -sCf --noconfirm --needed --skippgpcheck
      cp -f *.pkg.tar.zst /repo/" || { echo "### FAILED: $p"; failed+=("$p"); }
  done
  cd /repo && rm -f sunshine.db* sunshine.files* && repo-add sunshine.db.tar.gz $(ls *.pkg.tar.zst | grep -v -- "-debug-")
  chown -R "$HOST_UID:$HOST_GID" /repo /aur /srcdest
  [ ${#failed[@]} -eq 0 ] || { echo "build-aur: failed: ${failed[*]}"; exit 1; }' _ "$@"
