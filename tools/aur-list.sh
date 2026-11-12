#!/usr/bin/env bash
# Prints the packages the ISO needs that are NOT in the official Arch repos (so they must be built from the AUR),
# computed from profile/packages.x86_64 + hyprland/packages.txt, plus anything that has a local PKGBUILD in pkgs/.
# Runs inside the builder container (read-only); needs the sunshineos-builder image.
set -euo pipefail
cd "$(dirname "$0")/.."
{ cat profile/packages.x86_64 hyprland/packages.txt | sed 's/#.*//' | awk 'NF{print $1}'; } | sort -u > "${TMPDIR:-/tmp}/sunshine-all-pkgs.$$"
trap 'rm -f "${TMPDIR:-/tmp}/sunshine-all-pkgs.$$"' EXIT
{
  docker run --rm -i sunshineos-builder bash -c '
    pacman -Sy >/dev/null 2>&1
    mapfile -t all
    # one call finds everything not found as a package name; then drop groups and virtual provides
    pacman -Si "${all[@]}" 2>&1 >/dev/null | grep -oP "package .\K[^'"'"']+" | while read -r p; do
      pacman -Sg "$p" 2>/dev/null | grep -q . || pacman -Ssq "^$p\$" >/dev/null 2>&1 || echo "$p"
    done' < "${TMPDIR:-/tmp}/sunshine-all-pkgs.$$"
  for d in pkgs/*/PKGBUILD; do [ -f "$d" ] && basename "$(dirname "$d")"; done
} | sort -u
