#!/usr/bin/env python3
"""Cuts the AI-generated logo grids (branding/logo/drafts/*-grid.png, 3x2 each) into one transparent PNG per variant
and writes them to branding/logo/icons/<source>-r<round>-<n>.png (n = 1..6, row by row)."""
import glob, os, re
from PIL import Image
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "branding", "logo")
OUT = os.path.join(ROOT, "icons"); os.makedirs(OUT, exist_ok=True)

def cut(cell):
    a = np.asarray(cell.convert("RGB")).astype(float)
    bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3)]), axis=0)
    dist = np.abs(a - bg).max(axis=2)
    alpha = np.clip((dist - 10) / 45, 0, 1)
    col = bg + (a - bg) / np.maximum(alpha, 1e-3)[..., None]
    rgba = np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")
    box = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    im = im.crop(box)
    side = int(max(im.size) * 1.12)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return sq.resize((512, 512), Image.LANCZOS)

for g in sorted(glob.glob(os.path.join(ROOT, "drafts", "*-grid.png"))):
    name = os.path.basename(g)[:-9]            # e.g. chatgpt-r2
    im = Image.open(g); w, h = im.size
    for n in range(6):
        r, c = divmod(n, 3)
        cut(im.crop((c * w // 3, r * h // 2, (c + 1) * w // 3, (r + 1) * h // 2))).save(f"{OUT}/{name}-{n+1}.png")
    print("cut", name)
