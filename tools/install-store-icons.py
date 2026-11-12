#!/usr/bin/env python3
"""Store icons chosen by the user: store-basic = the Sunshine Store app icon; store-theme = the icon used in the OS theme
(icon names system-software-install and sunshine-store-theme). Also copied to the store repo's data/ icon."""
import os, shutil
from PIL import Image
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S = f"{P}/overlay/system/usr/share"
for name, src in (("sunshine-store", "store-basic"), ("sunshine-store-theme", "store-theme"), ("system-software-install", "store-theme"), ("sunshine-menu", "menu"), ("start-here", "menu")):
    im = Image.open(f"{P}/branding/logo/store/{src}.png")
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        d = f"{S}/icons/hicolor/{s}x{s}/apps" if name != "system-software-install" else f"{S}/icons/hicolor/{s}x{s}/apps"
        os.makedirs(d, exist_ok=True); im.resize((s, s), Image.LANCZOS).save(f"{d}/{name}.png")
shutil.copy(f"{P}/branding/logo/store/store-basic.png", f"{S}/sunshine/logos/store-basic.png")
shutil.copy(f"{P}/branding/logo/store/store-theme.png", f"{S}/sunshine/logos/store-theme.png")
shutil.copy(f"{P}/branding/logo/store/menu.png", f"{S}/sunshine/logos/menu.png")
Image.open(f"{P}/branding/logo/store/store-basic.png").resize((256, 256), Image.LANCZOS).save(os.path.expanduser("~/Projects/sunshine-store/data/sunshine-store.png"))
print("store icons installed")
