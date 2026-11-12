#!/usr/bin/env python3
"""Maintainer tool: builds the Sunshine Win11 Plasma theme (overlay/system/usr/share/...) from Win11OS-kde
(https://github.com/yeyushengfan258/Win11OS-kde, GPL-3.0): its layout/skeleton (Plasma theme shapes, Aurorae window
decoration, look-and-feel) with the Sunshine palette (SunshineDark colours, orange accent). Re-run after changing the palette.
usage: tools/make-win11-theme.py <path to Win11OS-kde checkout>"""
import os, re, shutil, sys, gzip, glob
src = sys.argv[1]; proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(proj, "overlay/system/usr/share")
NAME = "SunshineWin11"; LAF = "com.sunshineos.win11"
# upstream blues/greys -> Sunshine palette
MAP = {"3daee9":"ff9654","3daee6":"ff9654","4bc8ff":"ffb07a","93cee9":"ffcba8","5294e2":"ff9654","00a0ff":"ff9654",
       "0078d4":"ff9654","006eff":"ff9654","4285f4":"ff9654","315bef":"ff9654",
       "31363b":"1a202d","232629":"0e1422","1e1e1e":"0e1422","282828":"141a2a","eff0f1":"efe5d0"}
pat = re.compile("#(" + "|".join(MAP) + ")(?![0-9a-fA-F])", re.I)
def recolor(t): return pat.sub(lambda m: "#" + MAP[m.group(1).lower()], t)

def copy_tree(s, d):
    if os.path.exists(d): shutil.rmtree(d)
    for r, _, fs in os.walk(s):
        o = os.path.join(d, os.path.relpath(r, s)); os.makedirs(o, exist_ok=True)
        for f in fs:
            p = os.path.join(r, f); q = os.path.join(o, f)
            if f.endswith((".svg", ".qml", ".json")) :
                open(q, "w").write(recolor(open(p, encoding="utf-8", errors="surrogateescape").read()))
            elif f.endswith(".svgz"):
                with gzip.open(q, "wt") as g: g.write(recolor(gzip.open(p, "rt", encoding="utf-8", errors="replace").read()))
            else: shutil.copy2(p, q)

# 1. Plasma theme
pt = os.path.join(out, "plasma/desktoptheme", NAME)
copy_tree(os.path.join(src, "plasma/desktoptheme/Win11OS-dark"), pt)
md = open(os.path.join(pt, "metadata.desktop")).read().replace("Win11OS-dark", NAME)
md = re.sub(r"(?m)^Comment=.*", "Comment=Sunshine OS: Windows 11 layout in Sunshine colours (based on Win11OS-kde)", md)
open(os.path.join(pt, "metadata.desktop"), "w").write(md)
# colours of the Plasma theme = the Sunshine colour scheme
sc = open(os.path.join(out, "color-schemes/SunshineDark.colors")).read()
sc = re.sub(r"(?m)^\[General\][\s\S]*?(?=^\[|\Z)", "", sc)  # keep only colour groups
open(os.path.join(pt, "colors"), "w").write(sc)

# 2. Aurorae window decoration
au = os.path.join(out, "aurorae/themes", NAME)
copy_tree(os.path.join(src, "aurorae/Win11OS-dark"), au)
os.rename(os.path.join(au, "Win11OS-darkrc"), os.path.join(au, NAME + "rc"))
p = os.path.join(au, "metadata.desktop"); open(p, "w").write(open(p).read().replace("Win11OS-dark", NAME))

# 3. Look-and-feel (global theme)
lf = os.path.join(out, "plasma/look-and-feel", LAF)
copy_tree(os.path.join(src, "plasma/look-and-feel/com.github.yeyushengfan258.Win11OS-dark"), lf)
for f in ("metadata.json", "metadata.desktop"):
    p = os.path.join(lf, f); s = open(p).read()
    s = s.replace("com.github.yeyushengfan258.Win11OS-dark", LAF).replace("Win11OS-dark", NAME)
    if f.endswith(".json"):
        import json; j = json.loads(s); j.pop("X-KPackage-Dependencies", None)
        j["KPlugin"]["Website"] = "https://github.com/yeyushengfan258/Win11OS-kde"
        j["KPlugin"]["Description"] = "Sunshine OS: Windows 11 layout in Sunshine colours (based on Win11OS-kde)"
        s = json.dumps(j, indent=4)
    open(p, "w").write(s)
open(os.path.join(lf, "contents/defaults"), "w").write(f"""[kdeglobals][General]
ColorScheme=SunshineDark

[kwinrc][org.kde.kdecoration2]
ButtonsOnLeft=
ButtonsOnRight=IAX
library=org.kde.kwin.aurorae
theme=__aurorae__svg__{NAME}

[plasmarc][Theme]
name={NAME}
""")
for f in glob.glob(os.path.join(lf, "contents/previews/*")): os.remove(f)  # upstream screenshots show blue Windows colours
print("built", NAME, "->", out)
