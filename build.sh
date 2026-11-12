#!/usr/bin/env bash
# Build the Sunshine OS ISO inside a container; host is not modified.
set -euo pipefail
cd "$(dirname "$0")"
CACHE=${SUNSHINE_CACHE:-$PWD/cache}   # packages and downloads are kept here between builds
mkdir -p "$CACHE/pacman" out build repo
chmod -R a+rwX "$CACHE/pacman" 2>/dev/null || true
docker run --rm --privileged -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -v "$PWD/profile:/profile:ro" -v "$PWD/repo:/repo:ro" -v "$PWD/out:/out" -v "$PWD/build:/work" -v "$CACHE/pacman:/var/cache/pacman/pkg" -v "$PWD/tools:/tools:ro" \
  sunshineos-builder bash -c 'pacman -Sy --noconfirm --needed grub >/dev/null 2>&1; bash /tools/prefetch.sh || true; rm -rf /work/* /work/.[!.]* && mkarchiso -v -w /work -o /out /profile; rc=$?; chown -R "$HOST_UID:$HOST_GID" /out /work; exit $rc'
