#!/usr/bin/env bash
# Maintainer tool: rebuild hyprland/patches/sunshineos.patch.
# The patch sits on top of end-4's dots (pinned commit) + the Sunshine_end4_Dots patch and rewrites the defaults for
# Sunshine OS: startup apps, window rules, default wallpaper, bar icon, prompt/fastfetch look, venv path, first-run.
# The edits themselves are in tools/sunshineos-edits.py. The result is verified by applying both patches to a clean
# checkout and comparing it with the edited tree.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJ=$PWD; UP=$PWD/cache/end4-up; SU=$PWD/cache/sunshine-end4
PIN=2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8
[ -d $UP/.git ] && [ -d $SU/patch ] || { echo "run tools/import-end4.sh once first (it prepares cache/)"; exit 1; }
work=$(mktemp -d)
cleanup() { git -C $UP worktree remove --force "$work/base" 2>/dev/null; git -C $UP worktree remove --force "$work/check" 2>/dev/null; rm -rf "$work"; }
trap cleanup EXIT
# base = pinned end-4 + the Sunshine patch
git -C $UP worktree add -q --detach "$work/base" $PIN
git -C "$work/base" apply --whitespace=nowarn $SU/patch/dots-hyprland.patch
git -C "$work/base" add -A
git -C "$work/base" -c user.name=sunshine -c user.email=sunshine@localhost commit -q -m "end-4 + Sunshine patch"
# edits -> patch
python3 -I tools/sunshineos-edits.py "$work/base" "$PROJ"
git -C "$work/base" add -A
git -C "$work/base" diff --cached --binary HEAD > "$work/sunshineos.patch"
# verify on a clean checkout
git -C $UP worktree add -q --detach "$work/check" $PIN
git -C "$work/check" apply --whitespace=nowarn $SU/patch/dots-hyprland.patch
git -C "$work/check" add -A
git -C "$work/check" apply --whitespace=nowarn "$work/sunshineos.patch"
for f in $(git -C "$work/base" diff --cached --name-only HEAD); do
  cmp -s "$work/check/$f" "$work/base/$f" || { echo "mismatch: $f" >&2; exit 1; }
done
mkdir -p hyprland/patches; cp "$work/sunshineos.patch" hyprland/patches/sunshineos.patch
git -C "$work/base" diff --cached --stat HEAD | tail -14
echo "hyprland/patches/sunshineos.patch rebuilt and verified ($(wc -c < hyprland/patches/sunshineos.patch) bytes)"
