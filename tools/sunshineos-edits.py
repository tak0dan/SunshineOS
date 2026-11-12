#!/usr/bin/env python3
"""The Sunshine OS defaults for the Sunshine end-4 dots, as edits to a tree that already has end-4's dots + the Sunshine patch.
Used only by tools/build-sunshineos-patch.sh, which turns the result into hyprland/patches/sunshineos.patch.
usage: sunshineos-edits.py <dots-root> <project-root>      (dots-root contains dots/.config/...)"""
import os, re, shutil, sys

root, proj = sys.argv[1:3]
cfg = os.path.join(root, "dots/.config")
QS = os.path.join(cfg, "quickshell/ii")

def put(src, dst):
    shutil.copy(src, dst); os.chmod(dst, 0o644)

def sub(path, old, new, count=1):
    s = open(path).read()
    if old not in s:
        sys.exit(f"edit failed, text not found in {path}: {old[:60]!r}")
    open(path, "w").write(s.replace(old, new, count))

# 1. startup apps: Sunshine Welcome on workspace 1, the browser on 2, foot running btop on 3, then back to workspace 1
p = os.path.join(cfg, "hypr/hyprland/execs.lua"); s = open(p).read()
a = s.index("    -- Startup apps:"); b = s.index("    -- Core components")
s = s[:a] + '''    -- Sunshine OS startup apps, each placed on its workspace at launch only:
    -- 1 Sunshine Welcome, 2 the browser, 3 foot running btop; then back to workspace 1
    hl.exec_cmd("/usr/local/bin/sunshine-welcome --autostart", { workspace = 1 })
    local web = first_available(browser)
    if web then
        hl.exec_cmd(web, { workspace = 2 })
    end
    if on_path("foot") and on_path("btop") then
        hl.exec_cmd("foot -e btop", { workspace = 3 })
    end
    hl.exec_cmd("sleep 7; hyprctl dispatch 'hl.dsp.focus({workspace=1})'")

''' + s[b:]
open(p, "w").write(s)

# 2. window rules for the installer and the Sunshine apps
with open(os.path.join(cfg, "hypr/hyprland/rules.lua"), "a") as f:
    f.write('''
-- Sunshine OS apps
hl.window_rule({match = {class = "^(calamares|Calamares)$" },       float = true})
hl.window_rule({match = {class = "^(calamares|Calamares)$" },       center = true})
hl.window_rule({match = {class = "^(calamares|Calamares)$" },       size = {"(monitor_w*0.55)", "(monitor_h*0.75)"} })
hl.window_rule({match = {class = "^(sunshine-welcome)$" },          float = true})
hl.window_rule({match = {class = "^(sunshine-welcome)$" },          center = true})
hl.window_rule({match = {class = "^(sunshine-welcome)$" },          size = {"700", "600"} })
hl.window_rule({match = {class = "^(sunshine-store)$" },            float = true})
hl.window_rule({match = {class = "^(sunshine-store)$" },            center = true})
hl.window_rule({match = {class = "^(sunshine-store)$" },            size = {"(monitor_w*0.7)", "(monitor_h*0.8)"} })
''')

# 3. the Python virtual environment lives in /opt (installed there by the Sunshine OS installer)
sub(os.path.join(cfg, "hypr/hyprland/env.lua"), 'home_dir .. "/.local/state/quickshell/.venv"', '"/opt/illogical-impulse-venv"')

# 4. first run: the shell colours itself from the default wallpaper; no upstream welcome window (Sunshine Welcome replaces it)
fr = os.path.join(QS, "services/FirstRunExperience.qml")
s = open(fr).read()
s = re.sub(r"\n[^\n]*qs -p '\$\{root\.welcomeQmlPath\}'[^\n]*", "", s)
open(fr, "w").write(s)

# 5. default wallpaper (first run, and the first wallpaper in the picker)
put(os.path.join(proj, "branding/wallpapers/login.png"), os.path.join(QS, "assets/images/default_wallpaper.png"))  # the flower, same as Plasma

# 5b. keyboard layouts: US + Ukrainian (Super+Space / Alt+Shift style switching stays as in the dots)
sub(os.path.join(cfg, "hypr/hyprland/general.lua"), 'kb_layout = "us,es,ua"', 'kb_layout = "us,ua"')

# 6. bar button: the Sunshine menu icon
put(os.path.join(proj, "overlay/quickshell/sunshine-symbolic.svg"), os.path.join(QS, "assets/icons/sunshine-symbolic.svg"))
sub(os.path.join(QS, "modules/common/Config.qml"), 'property string topLeftIcon: "spark"', 'property string topLeftIcon: "sunshine"')

# 7. terminal look: orange prompt, orange fastfetch with the Sunshine logo (no personal dates in the default file)
put(os.path.join(proj, "overlay/skel/.config/starship.toml"), os.path.join(cfg, "starship.toml"))
put(os.path.join(proj, "overlay/fastfetch-logo.txt"), os.path.join(cfg, "fastfetch/SUN_colored.txt"))
ff = os.path.join(cfg, "fastfetch/config.jsonc"); s = open(ff).read()
s = s.replace('"width": 46,', '"width": 34,')
if '"display": {' not in s:
    s = s.replace('    "modules": [', '    "display": { "color": { "keys": "38;2;255;184;107", "title": "38;2;255;150;84", "separator": "38;2;255;209;160" } },\n    "modules": [', 1)
open(ff, "w").write(s)
open(os.path.join(cfg, "fastfetch/custom-info.json"), "w").write('''{
  "entries": [
    {
      "title": "Running Sunshine OS",
      "since": "2026-11-11",
      "units": ["days"],
      "mode": "combined"
    }
  ]
}
''')
print("edits applied")
