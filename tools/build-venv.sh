#!/usr/bin/env bash
# Builds end-4's Python virtual environment (colour generation, wallpaper theming) into the ISO at /opt/illogical-impulse-venv.
# Runs ONLY in the builder container. Needs network (PyPI + the uv Python 3.12 download).
set -euo pipefail
cd "$(dirname "$0")/.."
REQ=$PWD/cache/end4-up/sdata/uv/requirements.txt
OUT=$PWD/profile/airootfs/usr/share/sunshine/hyprland/root/opt
CACHE=${SUNSHINE_CACHE:-$HOME/Projects/SunshineOS-cache}
mkdir -p "$OUT" "$CACHE/pacman" "$CACHE/uv"
docker run --rm -e UV_CACHE_DIR=/uvcache -v "$CACHE/uv:/uvcache" -v "$CACHE/pacman:/var/cache/pacman/pkg" -v "$REQ:/requirements.txt:ro" -v "$OUT:/out" sunshineos-builder bash -c '
  set -e
  pacman -Sy --noconfirm --needed uv clang cairo gobject-introspection pkgconf >/dev/null
  rm -rf /out/uv-python /out/illogical-impulse-venv
  UV_PYTHON_INSTALL_DIR=/out/uv-python uv python install 3.12
  UV_PYTHON_INSTALL_DIR=/out/uv-python uv venv --prompt .venv /out/illogical-impulse-venv -p 3.12
  . /out/illogical-impulse-venv/bin/activate
  uv pip install -r /requirements.txt
  # the venv is used from /opt inside the ISO, so rewrite the build-time paths
  sed -i "s|/out/|/opt/|g" /out/illogical-impulse-venv/bin/* /out/illogical-impulse-venv/pyvenv.cfg 2>/dev/null || true
  chown -R 1000:1000 /out'
du -sh "$OUT"/*
