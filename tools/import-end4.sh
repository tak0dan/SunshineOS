#!/usr/bin/env bash
# Builds the Hyprland skeleton (/etc/skel) from the user's Sunshine_end4_Dots:
#   end-4's illogical-impulse dots at the pinned commit + the Sunshine patch, then Sunshine OS' own touches.
# Replaces tools/import-dots.sh (the older Waybar based dots).
set -euo pipefail
cd "$(dirname "$0")/.."
SUNSHINE_CACHE_DIR=${SUNSHINE_CACHE:-$PWD/cache}; mkdir -p "$SUNSHINE_CACHE_DIR/pacman"; chmod -R a+rwX "$SUNSHINE_CACHE_DIR/pacman" 2>/dev/null || true
PIN=2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8
UP=cache/end4-up; SU=cache/sunshine-end4
A=profile/airootfs; PAY=$A/usr/share/sunshine/hyprland; SKEL=$PAY/root/etc/skel; QS="$SKEL/.config/quickshell/ii"

# 1. sources: the user's repo (latest) and end-4 at the pinned commit with the patch applied
if [ -d $SU/.git ]; then git -C $SU pull -q --ff-only || true; else git clone -q --depth 1 https://github.com/tak0dan/Sunshine_end4_Dots $SU; fi
if [ ! -d $UP/.git ]; then mkdir -p $UP && git -C $UP init -q && git -C $UP remote add origin https://github.com/end-4/dots-hyprland; fi
git -C $UP fetch -q --depth 1 origin $PIN 2>/dev/null || true
git -C $UP checkout -q -f $PIN && git -C $UP clean -fdxq
git -C $UP submodule update --init --recursive -q   # modules/common/widgets/shapes (rounded-polygon-qmljs)
git -C $UP apply --whitespace=nowarn ../../$SU/patch/dots-hyprland.patch
# ... and the Sunshine OS defaults (startup apps, wallpaper, bar icon, prompt/fastfetch look, venv path, first run).
# Regenerate it after changing tools/sunshineos-edits.py with tools/build-sunshineos-patch.sh.
git -C $UP apply --whitespace=nowarn ../../hyprland/patches/sunshineos.patch

# 2. the Hyprland payload. The live session is Plasma only; this tree is copied onto the TARGET system by the installer
#    (sunshine-hyprland-install): dotfiles (/etc/skel), the Python venv (/opt), session files, a small offline repo of
#    the AUR-built packages, and the list of packages to install.
rm -rf "$PAY/root/etc" "$PAY/root/usr" "$PAY/root/var" "$PAY/packages.txt"
mkdir -p "$PAY/root"
cp -a hyprland/root/. "$PAY/root/"
cp hyprland/packages.txt "$PAY/packages.txt"
# live skeleton (Plasma session): the Sunshine overlay only
rm -rf "$A/etc/skel"; mkdir -p "$A/etc/skel"; cp -a overlay/skel/. "$A/etc/skel/"
# end-4's dots as shipped by ./setup install
mkdir -p "$SKEL/.config" "$SKEL/.local/bin" "$SKEL/Pictures/Wallpapers"
rsync -a --exclude='/fish/conf.d' $UP/dots/.config/ "$SKEL/.config/"
rsync -a $UP/dots/.local/ "$SKEL/.local/"
[ -f "$SKEL/.config/hypr/hyprland.conf" ] && mv "$SKEL/.config/hypr/hyprland.conf" "$SKEL/.config/hypr/hyprland.conf.old"
install -Dm755 $SU/extras/cpmatrix "$SKEL/.local/bin/cpmatrix"
install -Dm644 $SU/systemd/tak0-per-window-switch.service "$SKEL/.config/systemd/user/tak0-per-window-switch.service"
mkdir -p "$SKEL/.config/systemd/user/default.target.wants"
ln -sf ../tak0-per-window-switch.service "$SKEL/.config/systemd/user/default.target.wants/tak0-per-window-switch.service"
# end-4: the user ydotool service (virtual keyboard for the on-screen keyboard and widgets)
ln -sf /usr/lib/systemd/user/ydotool.service "$SKEL/.config/systemd/user/default.target.wants/ydotool.service"

# 2b. offline repo with the AUR-built packages of the payload list (everything else comes from the mirrors during install)
rm -rf "$PAY/repo"; mkdir -p "$PAY/repo"
for f in repo/*.pkg.tar.zst; do
  n=$(basename "$f" | sed -E 's/-[^-]+-[^-]+-[^-]+\.pkg\.tar\.zst$//')
  grep -qx "$n" hyprland/packages.txt && cp "$f" "$PAY/repo/"
done
# the icon font is an official package, but the installer keeps a copy of the tested revision (see sunshine-doctor): ship it in the payload repo
docker run --rm -v "$SUNSHINE_CACHE_DIR/pacman:/var/cache/pacman/pkg" -v "$PWD/$PAY/repo:/r" sunshineos-builder bash -c 'pacman -Sy >/dev/null 2>&1; pacman -Sw --noconfirm --needed ttf-material-symbols-variable && cp /var/cache/pacman/pkg/ttf-material-symbols-variable-*.pkg.tar.zst /r/'
docker run --rm -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" -v "$PWD/$PAY/repo:/r" sunshineos-builder bash -c 'cd /r && repo-add sunshine-hypr.db.tar.gz *.pkg.tar.zst >/dev/null 2>&1; chown -R "$HOST_UID:$HOST_GID" /r'
echo "payload repo: $(ls "$PAY/repo"/*.pkg.tar.zst | wc -l) packages, $(du -sh "$PAY/repo" | cut -f1)"

# 3. Sunshine identity: wallpapers, logo, then the overlay (fish extras, prompt, mime, ...)
cp branding/wallpapers/desktop.png "$SKEL/Pictures/Wallpapers/SunshineOS_Wallpaper.png"
cp branding/wallpapers/login.png   "$SKEL/Pictures/Wallpapers/SunshineOS_Flower_Bloom.png"
cp -a overlay/skel/. "$SKEL/"
cp -a overlay/system/. "$A/"

find "$SKEL" -name .git -prune -exec rm -rf {} +

# 4. validate every Lua file
if command -v lua >/dev/null; then
  find "$SKEL/.config/hypr" -name '*.lua' -print0 | while IFS= read -r -d '' f; do
    lua -e "assert(loadfile('$f'))" 2>&1 | grep -v "^$" | sed "s|^|LUA SYNTAX: $f: |" || true
  done
fi
echo "skeleton ready: $(du -sh "$SKEL" | cut -f1)"
