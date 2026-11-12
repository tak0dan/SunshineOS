#!/usr/bin/env bash
# Runs inside the builder container before mkarchiso: downloads every package of the profile ONE AT A TIME into the
# shared pacman cache, retrying each (with pauses) until it succeeds. A stalled mirror then costs one retry, not the build.
# Dependencies of each package are fetched along with it; anything already cached is skipped.
set -u
CONF=/profile/pacman.conf
pacman --config "$CONF" -Sy --noconfirm >/dev/null 2>&1 || pacman --config "$CONF" -Sy --noconfirm
mapfile -t PKGS < <(grep -v '^\s*#' /profile/packages.x86_64 | grep -v '^\s*$')
total=${#PKGS[@]}; n=0; failed=()
for p in "${PKGS[@]}"; do
  n=$((n + 1))
  ok=0
  for try in 1 2 3; do
    if pacman --config "$CONF" -Sw --noconfirm --needed --disable-download-timeout "$p" >/tmp/prefetch.log 2>&1; then ok=1; break; fi
    echo "[$n/$total] $p: attempt $try failed, retrying in 10 s (3 tries) ($(grep -m1 -i 'error' /tmp/prefetch.log | cut -c1-90))"
    sleep 10
  done
  if [ $ok = 1 ]; then echo "[$n/$total] $p ok"; else echo "[$n/$total] $p FAILED"; failed+=("$p"); fi
done
if [ ${#failed[@]} -gt 0 ]; then echo "prefetch: failed packages: ${failed[*]}"; exit 1; fi
echo "prefetch: all $total packages cached"
