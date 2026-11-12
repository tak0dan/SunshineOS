#!/usr/bin/env bash
# Rebuild the Hyprland skeleton in the ISO profile from the Sunshine Hyprland Dots repo + Sunshine overlay.
# Reads the dots repo only; writes inside this project. Usage: tools/import-dots.sh [path-to-dots]
set -euo pipefail
cd "$(dirname "$0")/.."
DOTS=${1:-$HOME/Sunshine_Hyprland_Dots}
A=profile/airootfs
SKEL=$A/etc/skel
[ -d "$DOTS/config/hypr" ] || { echo "not a dots repo: $DOTS" >&2; exit 1; }

rm -rf "$SKEL/.config" "$SKEL/Pictures"
mkdir -p "$SKEL/.config" "$SKEL/Pictures/wallpapers"

# 1. the dots themselves (pruned: big images and duplicate binaries are not needed on the ISO)
rsync -a \
  --exclude='/wlogout/themes/silvia' --exclude='*bg_raw*' \
  --exclude='/hypr/scripts/dots-tui*' --exclude='/fastfetch/images/Arch-Logo-1.png' \
  --exclude='/hypr/wallpaper_effects/.wallpaper_current' \
  "$DOTS/config/" "$SKEL/.config/"
rsync -a "$DOTS/wallpapers/" "$SKEL/Pictures/wallpapers/"

# 2. Sunshine identity: wallpaper, fastfetch logo, starship prompt
cp branding/wallpapers/desktop.png "$SKEL/Pictures/wallpapers/SunshineOS_Wallpaper.png"
cp branding/wallpapers/login.png   "$SKEL/Pictures/wallpapers/SunshineOS_Flower_Bloom.png"
mkdir -p "$SKEL/.config/hypr/wallpaper_effects"
cp branding/wallpapers/desktop.png "$SKEL/.config/hypr/wallpaper_effects/.wallpaper_current"
cp branding/logo.png "$SKEL/.config/fastfetch/images/Arch-Logo-2.png"

# 3. Sunshine overlay (fish/zsh/bash, Plasma settings)
cp -a overlay/skel/. "$SKEL/"
cp -a overlay/system/. "$A/"

# 4. Hyprland tweaks for the installer and the Sunshine apps
python3 -I - "$SKEL/.config/hypr/UserConfigs" <<'PY'
import sys, re, os
d = sys.argv[1]
p = os.path.join(d, "user_startup.lua"); s = open(p).read()
s = s.replace("local startup_commands = {", 'local startup_commands = {\n  "/usr/local/bin/sunshine-welcome --autostart",\n  "nm-applet --indicator",', 1)
open(p, "w").write(s)
p = os.path.join(d, "user_window_rules.lua"); s = open(p).read()
s += '''
-- Sunshine OS: the installer and the Sunshine apps open as tidy floating windows.
apply_window_rule({ name = "sunshine-calamares", match = { class = "calamares|io.calamares.calamares" },
  float = true, center = true, size = "(monitor_w*0.55) (monitor_h*0.75)" })
apply_window_rule({ name = "sunshine-welcome", match = { class = "sunshine-welcome" },
  float = true, center = true, size = "700 600" })
apply_window_rule({ name = "sunshine-store", match = { class = "sunshine-store" },
  float = true, center = true, size = "(monitor_w*0.7) (monitor_h*0.8)" })
'''
open(p, "w").write(s)
PY

# 4b. Waybar menu button shows the Sunshine menu icon (image module) instead of a glyph
python3 -I - "$SKEL/.config/hypr/waybar" <<'PY'
import sys, os, re, glob
w = sys.argv[1]
mc = os.path.join(w, "ModulesCustom"); s = open(mc).read()
m = re.search(r'"custom/menu": \{(.*?)\n\},', s, re.S)
body = m.group(1)
body = re.sub(r'\n\t"format": "[^"]*",', '', body)
img = '"image#menu": {\n\t"path": "/usr/share/icons/hicolor/48x48/apps/sunshine-menu.png",\n\t"size": 22,' + body + '\n},'
s = s.replace(m.group(0), m.group(0) + "\n" + img, 1)
open(mc, "w").write(s)
for f in glob.glob(os.path.join(w, "configs", "*")) + [os.path.join(w, "ModulesGroups")]:
    lines = open(f).read().split("\n")
    lines = [l.replace('"custom/menu"', '"image#menu"') if "children-class" not in l else l for l in lines]
    open(f, "w").write("\n".join(lines))
for f in glob.glob(os.path.join(w, "style", "*.css")):
    open(f, "a").write("\n#image.menu { margin: 0 6px; padding: 2px 4px; }\n")
PY

# 5. Steps the dots' interactive installer (copy.sh) normally performs: default waybar layout/style and rofi links.
#    Relative symlinks, so they work in any user's home.
H="$SKEL/.config/hypr"
ln -sfn "configs/TOP-&-BOT-SummitSplit-v3" "$H/waybar/config"
ln -sfn "style/Wallust-Chroma-Edge.css"    "$H/waybar/style.css"
ln -sfn "../wallpaper_effects/.wallpaper_current" "$H/rofi/.current_wallpaper"
mkdir -p "$SKEL/.local/share/rofi/themes"
for t in "$H"/rofi/themes/*; do
  [ -e "$t" ] && ln -sfn "../../../../.config/hypr/rofi/themes/$(basename "$t")" "$SKEL/.local/share/rofi/themes/$(basename "$t")"
done
for l in "$H/waybar/config" "$H/waybar/style.css"; do
  [ -e "$l" ] || { echo "broken default link: $l" >&2; exit 1; }
done

# 6. Fixes for problems found while booting the ISO (also worth upstreaming to the dots):
#    - initial-boot.sh ran awww-daemon in the foreground and hung the whole first-boot setup (never set the wallpaper/marker)
python3 -I test/patches/fix_initial_boot.py "$H/initial-boot.sh"
#    - UserConfigs/user_startup.lua has a Lua syntax error (bare commas after commented entries) so the user startup list never runs
python3 -I - "$H/UserConfigs/user_startup.lua" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
s = re.sub(r"^(\s*)--\[\[(.*?)\]\],?\s*$", lambda m: f"{m.group(1)}-- {m.group(2)}", s, flags=re.M)
s = re.sub(r"^\s*\[\[hyprctl eval 'hl\.exec_cmd\(\"waybar\"\)'\]\],?\s*$", "  -- (waybar is started by scripts/WaybarStartup.sh with the right layout)", s, flags=re.M)
open(p, "w").write(s)
PY
#    - Hyprland shows its "Hyprland Updated" news dialog on first run; a new user should not meet that
cat >> "$H/UserConfigs/user_settings.lua" <<'LUA'

-- Sunshine OS: no "Hyprland Updated" news dialog on first run.
hl.config({ ecosystem = { no_update_news = true } })
LUA
for f in UserConfigs/user_settings.lua; do
  lua -e "local f,e=loadfile('$H/$f'); if not f then io.stderr:write(e..'\n'); os.exit(1) end" || { echo "Lua syntax error in $f" >&2; exit 1; }
done
for f in UserConfigs/user_startup.lua UserConfigs/user_window_rules.lua; do
  lua -e "local f,e=loadfile('$H/$f'); if not f then io.stderr:write(e..'\n'); os.exit(1) end" || { echo "Lua syntax error in $f" >&2; exit 1; }
done
echo "skeleton ready: $(du -sh "$SKEL" | cut -f1)"
