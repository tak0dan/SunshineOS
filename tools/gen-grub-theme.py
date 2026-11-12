#!/usr/bin/env python3
"""Builds the Sunshine GRUB theme from the Graphite grub2 theme assets (gray + dark + pastel orange).
usage: gen-grub-theme.py <graphite-checkout> <out-dir> <logo.png> [menu-icon.png]
Only the images of the Graphite checkout are read; nothing from it is executed."""
import os, shutil, sys
from PIL import Image, ImageEnhance

src, out, logo = sys.argv[1:4]
icon = sys.argv[4] if len(sys.argv) > 4 else logo
os.makedirs(out + "/icons", exist_ok=True)
ORANGE = (255, 184, 107)
DARK = (43, 40, 46)

# wallpaper: Graphite's dark waves, outlines tinted pastel orange
bg = Image.open(f"{src}/backgrounds/1080p/wave-dark.png").convert("RGB")
px = bg.load()
for y in range(bg.height):
    for x in range(bg.width):
        r, g, b = px[x, y]
        if r > 150:                         # the thin light wave outlines
            k = (r - 150) / 105
            px[x, y] = (int(r*(1-k)+ORANGE[0]*k), int(g*(1-k)+ORANGE[1]*k*0.95), int(b*(1-k)+ORANGE[2]*k*0.8))
        else:
            px[x, y] = (int(r*0.92), int(g*0.9), int(b*0.9))   # slightly warmer, darker grays
bg.save(out + "/background.png")

def recolor(name, rgb, only_flat=False):
    im = Image.open(f"{src}/assets/assets/1080p/{name}").convert("RGBA")
    a = im.getchannel("A")
    flat = Image.new("RGBA", im.size, rgb + (255,))
    flat.putalpha(a)
    flat.save(f"{out}/{name}")

recolor("viewbox.png", DARK)                 # menu panel: dark charcoal
for n in ("select_c.png", "select_e.png", "select_w.png"):
    recolor(n, ORANGE)                       # selected row: pastel orange
shutil.copy(f"{src}/assets/assets/1080p/info.png", out + "/info.png")
for f in os.listdir(f"{src}/common"):
    if f.endswith(".pf2") or f.startswith("terminal_box"):
        shutil.copy(f"{src}/common/{f}", out + "/" + f)

# menu icons: Graphite's set, with the Sunshine logo for our own entries
for f in os.listdir(f"{src}/assets/logos/1080p"):
    shutil.copy(f"{src}/assets/logos/1080p/{f}", f"{out}/icons/{f}")
lg = Image.open(logo).convert("RGBA")
ic = Image.open(icon).convert("RGBA")
for alias in ("sunshineos.png", "sunshine.png", "gnu-linux.png", "linux.png", "os.png", "arch.png", "archlinux.png"):
    ic.resize((32, 32), Image.LANCZOS).save(out + "/icons/" + alias)
lg.resize((150, 150), Image.LANCZOS).save(out + "/logo.png")

open(out + "/theme.txt", "w").write('''# Sunshine OS GRUB theme (layout after Graphite by vinceliuice; gray, charcoal and pastel orange)
title-text: ""
desktop-image: "background.png"
desktop-color: "#2b282e"
terminal-font: "Unifont Regular 16"
terminal-box: "terminal_box_*.png"
terminal-left: "0"
terminal-top: "0"
terminal-width: "100%"
terminal-height: "100%"
terminal-border: "0"

+ image { left = 50%-75  top = 5%  width = 150  height = 150  file = "logo.png" }

+ boot_menu {
  left = 22%
  top = 49%
  width = 56%
  height = 34%
  item_font = "Unifont Regular 16"
  item_color = "#e8dcc8"
  selected_item_color = "#2a1a0e"
  icon_width = 32
  icon_height = 32
  item_icon_space = 20
  item_height = 40
  item_padding = 6
  item_spacing = 8
  selected_item_pixmap_style = "select_*.png"
}

# panel behind the menu (components listed later are drawn underneath)
+ image { left = 21%  top = 47%  width = 58%  height = 38%  file = "viewbox.png" }

+ image { top = 100%-50  left = 50%-240  width = 480  height = 42  file = "info.png" }

+ label {
  top = 87%
  left = 21%
  width = 58%
  align = "center"
  id = "__timeout__"
  text = "Starting in %d seconds"
  color = "#ffcba0"
  font = "Unifont Regular 16"
}
''')
