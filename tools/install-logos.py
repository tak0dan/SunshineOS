#!/usr/bin/env python3
"""Puts the chosen Sunshine OS logos into the profile.
  MAIN    = the OS logo (boot menu, installer, fastfetch, icon theme 'sunshineos')   -> icons/chatgpt-r2-2
  WELCOME = the logo of Sunshine Welcome                                              -> icons/chatgpt-r3-4
  every variant is also kept under /usr/share/sunshine/logos/ for later use."""
import glob, os, shutil
from PIL import Image

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
IC = f"{P}/branding/logo/icons"
MAIN, WELCOME = "chatgpt-r2-2", "chatgpt-r3-4"
SYS = f"{P}/overlay/system/usr/share"
os.makedirs(f"{SYS}/sunshine/logos", exist_ok=True)
for f in glob.glob(f"{IC}/*.png"):
    shutil.copy(f, f"{SYS}/sunshine/logos/")
main = Image.open(f"{IC}/{MAIN}.png"); wel = Image.open(f"{P}/branding/logo/grub-icon.png")   # Sunshine Welcome uses the same icon as GRUB
main.save(f"{SYS}/sunshine/logos/main.png"); wel.save(f"{SYS}/sunshine/logos/welcome.png")
for name, im in (("sunshineos", main), ("sunshine-welcome", wel)):
    for s in (16, 24, 32, 48, 64, 128, 256, 512):
        d = f"{SYS}/icons/hicolor/{s}x{s}/apps"; os.makedirs(d, exist_ok=True)
        im.resize((s, s), Image.LANCZOS).save(f"{d}/{name}.png")
# branding used by import-dots / Calamares / SDDM / fastfetch
main.save(f"{P}/branding/logo.png"); main.resize((256, 256), Image.LANCZOS).save(f"{P}/branding/icon.png")
main.resize((48, 48), Image.LANCZOS).save(f"{P}/branding/icon48.png")
A = f"{P}/profile/airootfs"
main.resize((256, 256), Image.LANCZOS).save(f"{A}/etc/calamares/branding/sunshine/logo.png")
for t in (f"{A}/usr/share/sunshine/logo.png",):
    main.save(t)
w = Image.new("RGBA", (800, 450), (0, 0, 0, 0)); m = main.resize((360, 360), Image.LANCZOS); w.alpha_composite(m, (220, 45))
w.save(f"{P}/branding/welcome.png"); w.save(f"{A}/etc/calamares/branding/sunshine/welcome.png")
print("logos installed")
