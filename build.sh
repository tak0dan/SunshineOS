#!/usr/bin/env bash
# Build the Sunshine OS ISO inside a container; host is not modified.
#   ./build.sh          release build (xz compression, slow) -> out/
#   FAST=1 ./build.sh   test build (light compression, much faster, larger) -> out/fast/ ; check it with test/smoke.sh
#
# Two things keep the result independent of the host it is built on:
#  - the profile is copied inside the container and its file modes are normalised (dirs 755, files 644/755 by owner exec bit).
#    Without this a restrictive host umask or default ACL (770/660 checkouts) ends up in the image: services such as dbus-broker
#    then cannot read or run their own files and the live system does not boot properly.
#  - the work directory is a Docker volume, not a host directory, so host ACLs cannot strip the permissions of the files that
#    pacman installs into the image.
set -euo pipefail
cd "$(dirname "$0")"
CACHE=${SUNSHINE_CACHE:-$PWD/cache}   # packages and downloads are kept here between builds
mkdir -p "$CACHE/pacman" out repo
chmod -R a+rwX "$CACHE/pacman" 2>/dev/null || true
docker run --rm --privileged -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" -e FAST="${FAST:-}" \
  -v "$PWD/profile:/profile-src:ro" -v "$PWD/repo:/repo:ro" -v "$PWD/out:/out" -v sunshineos-work:/work \
  -v "$CACHE/pacman:/var/cache/pacman/pkg" -v "$PWD/tools:/tools:ro" \
  sunshineos-builder bash -c '
    set -u
    umask 022
    for i in 1 2 3; do pacman -Sy --noconfirm --needed grub >/tmp/grub-install.log 2>&1 && break; echo "grub install failed (try $i/3)"; sleep 5; done
    command -v grub-install >/dev/null || { cat /tmp/grub-install.log; echo "ERROR: grub could not be installed in the builder"; exit 1; }
    rm -rf /profile && cp -r /profile-src /profile && chown -R root:root /profile && chmod -R go=u /profile && chmod -R go-w /profile
    bash /tools/prefetch.sh || true
    rm -rf /work/* /work/.[!.]*
    out=/out
    if [ -n "$FAST" ]; then   # test build: light compression (minutes, not an hour), bigger image, written to out/fast/
      sed -i "s|^airootfs_image_tool_options=.*|airootfs_image_tool_options=(\x27-comp\x27 \x27zstd\x27 \x27-Xcompression-level\x27 \x271\x27 \x27-b\x27 \x271M\x27 \x27-processors\x27 \x276\x27)|" /profile/profiledef.sh
      out=/out/fast; mkdir -p $out; rm -f $out/*.iso
    fi
    mkarchiso -v -w /work -o $out /profile; rc=$?
    chown -R "$HOST_UID:$HOST_GID" /out
    exit $rc'
