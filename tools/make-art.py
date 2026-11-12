"""Generate Sunshine OS artwork (logo, icon, wallpaper, installer images). Pure PIL."""
import math, os
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "..", "branding")
os.makedirs(OUT, exist_ok=True)
AMBER, GOLD, DEEP = (255, 196, 61), (255, 226, 130), (30, 27, 46)

def sun(size, rays=14, glow=True, bg=None):
    S = size * 2
    im = Image.new("RGBA", (S, S), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    r = S * 0.19
    if glow:
        g = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([c - r * 1.9, c - r * 1.9, c + r * 1.9, c + r * 1.9], fill=(255, 196, 61, 110))
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(S * 0.05)))
        d = ImageDraw.Draw(im)
    for i in range(rays):
        a = 2 * math.pi * i / rays
        a1, a2 = a - 0.09, a + 0.09
        r1, r2 = r * 1.45, r * (2.35 if i % 2 == 0 else 1.95)
        d.polygon([(c + r1 * math.cos(a1), c + r1 * math.sin(a1)), (c + r2 * math.cos(a), c + r2 * math.sin(a)),
                   (c + r1 * math.cos(a2), c + r1 * math.sin(a2))], fill=AMBER)
    d.ellipse([c - r, c - r, c + r, c + r], fill=GOLD)
    d.ellipse([c - r * 0.8, c - r * 0.8, c + r * 0.8, c + r * 0.8], fill=AMBER)
    return im.resize((size, size), Image.LANCZOS)

def gradient(w, h, top, bottom):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        t = y / (h - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = col
    return im

def wallpaper(w, h):
    im = gradient(w, h, (28, 24, 58), (255, 138, 76)).convert("RGBA")
    horizon = int(h * 0.72)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w * 0.5 - h * 0.5, horizon - h * 0.5, w * 0.5 + h * 0.5, horizon + h * 0.5], fill=(255, 196, 61, 150))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(h * 0.09)))
    s = sun(int(h * 0.42), rays=18, glow=False)
    im.alpha_composite(s, (int(w * 0.5 - s.width / 2), int(horizon - s.height / 2)))
    d = ImageDraw.Draw(im)
    d.rectangle([0, horizon, w, h], fill=(22, 19, 44, 255))      # silhouette ground
    for k in range(4):                                            # soft hill layers
        hill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hill)
        pts = [(0, h)]
        for x in range(0, w + 40, 40):
            pts.append((x, horizon + 20 * k + 40 * math.sin(x / (w / (3 + k)) + k * 1.7)))
        pts.append((w, h))
        hd.polygon(pts, fill=(22 - 3 * k, 19 - 3 * k, 44 - 5 * k, 255))
        im.alpha_composite(hill)
    return im.convert("RGB")

sun(512).save(f"{OUT}/logo.png")
sun(128).save(f"{OUT}/icon.png")
sun(48, rays=12, glow=False).save(f"{OUT}/icon48.png")
wallpaper(3840, 2160).save(f"{OUT}/wallpaper-3840x2160.png", optimize=True)
wallpaper(1920, 1080).save(f"{OUT}/wallpaper-1920x1080.png", optimize=True)
w = gradient(800, 400, (30, 27, 46), (58, 46, 96)).convert("RGBA")
w.alpha_composite(sun(300), (250, 50))
w.convert("RGB").save(f"{OUT}/welcome.png")
print("art generated:", sorted(os.listdir(OUT)))
