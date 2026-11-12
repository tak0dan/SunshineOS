#!/usr/bin/env python3
"""GRUB menu icon: gold ring with a four-point star (cleaned-up version of the user's sketch). Output: branding/logo/grub-icon.png"""
import math, os
from PIL import Image, ImageDraw
S = 1024; C = S / 2
img = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
# dark disc
d.ellipse((C - 0.97*C, C - 0.97*C, C + 0.97*C, C + 0.97*C), fill=(38, 36, 40, 235))
# ring
d.ellipse((C - 0.96*C, C - 0.96*C, C + 0.96*C, C + 0.96*C), outline=(247, 176, 60, 255), width=int(0.055*S))
# star: astroid, bulging a little so the arms are not too thin
R = 0.74 * C
pts = []
for i in range(361):
    t = math.radians(i)
    pts.append((C + R * math.cos(t) ** 3, C + R * math.sin(t) ** 3))
mask = Image.new("L", (S, S), 0); ImageDraw.Draw(mask).polygon(pts, fill=255)
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    k = y / S
    gd.line((0, y, S, y), fill=(int(255 - 8*k), int(205 - 55*k), int(70 - 25*k), 255))
img.paste(grad, (0, 0), mask)
# four little dots
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y, r = C + sx * 0.5 * C, C + sy * 0.5 * C, 0.045 * C
        d.ellipse((x - r, y - r, x + r, y + r), fill=(247, 176, 60, 255))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "branding", "logo", "grub-icon.png")
img.resize((256, 256), Image.LANCZOS).save(out)
print(out)
