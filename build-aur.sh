#!/usr/bin/env bash
# Build AUR packages inside the builder container into ./repo (local pacman repo "sunshine").
# Usage: ./build-aur.sh pkg [pkg...]
# Runs ONLY in Docker; nothing is installed on or modified on the host.
set -euo pipefail
cd "$(dirname "$0")"
CACHE=${SUNSHINE_CACHE:-$HOME/Projects/SunshineOS-cache}   # downloads are kept here between builds
mkdir -p repo aur pkgs "$CACHE/pacman" "$CACHE/aur-src"
docker run --rm -v "$CACHE/pacman:/var/cache/pacman/pkg" -v "$CACHE/aur-src:/srcdest" -v "$PWD/repo:/repo" -v "$PWD/aur:/aur" -v "$PWD/pkgs:/pkgs:ro" sunshineos-builder bash -c '
  set -e
  id builder &>/dev/null || useradd -m builder
  echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder
  chown -R builder /aur /repo /srcdest
  for p in "$@"; do
    sudo -u builder bash -c "
      set -e; cd /aur; rm -rf $p
      if [ -d /pkgs/$p ]; then cp -r /pkgs/$p $p; else for i in 1 2 3; do rm -rf $p; git clone -q https://aur.archlinux.org/$p.git && [ -f $p/PKGBUILD ] && break; sleep 5; done; fi
      cd $p
      SRCDEST=/srcdest MAKEFLAGS=-j\$(nproc) makepkg -sCf --noconfirm --needed --skippgpcheck
      cp -f *.pkg.tar.zst /repo/" || echo "### FAILED: $p"
  done
  cd /repo && rm -f sunshine.db* sunshine.files* && repo-add sunshine.db.tar.gz *.pkg.tar.zst
  chown -R 1000:1000 /repo /aur' _ "$@"
