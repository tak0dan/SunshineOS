"""Builds sunshine-a.svg: a flame-edged yellow 'A' (like Arch's) with a little sun in the gap between its legs."""
import math

def edge(p0, p1, tongues, amp, side):
    """Points from p0 (apex) to p1 (base) with flame tongues: slow rise, sharp fall, pointing up-and-out."""
    pts = []
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    L = math.hypot(dx, dy); ux, uy = dx/L, dy/L
    nx, ny = side*uy, -side*ux   # outward normal
    N = tongues*14
    for i in range(N+1):
        t = i/N
        ph = (t*tongues) % 1.0
        # tongue profile: ramps up to a tip at ph=0.78, then falls back
        prof = (ph/0.78)**1.6 if ph < 0.78 else max(0.0, (1-ph)/0.22)
        a = amp*(0.35+0.65*t) * prof if t > 0.10 else 0
        x = p0[0]+dx*t + nx*a - ux*a*0.9
        y = p0[1]+dy*t + ny*a - uy*a*0.9
        pts.append((x, y))
    return pts

apex = (256, 16)
outerL = edge(apex, (28, 498), 4, 34, -1)
outerR = edge(apex, (484, 498), 4, 34, 1)
outer = outerR + [(484, 498), (384, 498)]
inner = [(384, 498), (256, 222), (128, 498)]
path = outer + inner + [(28, 498)] + outerL[::-1]
d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in path) + " Z"
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="fl" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff2b8"/><stop offset="0.4" stop-color="#ffd25c"/>
      <stop offset="0.8" stop-color="#ffab3d"/><stop offset="1" stop-color="#ff8a3a"/>
    </linearGradient>
    <radialGradient id="sun" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#fffbe6"/><stop offset="0.6" stop-color="#ffe27a"/><stop offset="1" stop-color="#ffb82e"/>
    </radialGradient>
  </defs>
  <path d="{d}" fill="url(#fl)" stroke="url(#fl)" stroke-width="6" stroke-linejoin="round"/>
  <g transform="translate(256 424)">
    <g stroke="#ffd36a" stroke-width="7" stroke-linecap="round">'''
for k in range(12):
    a = math.radians(k*30)
    r1, r2 = 50, 68 if k % 2 == 0 else 62
    svg += f'<line x1="{r1*math.cos(a):.1f}" y1="{r1*math.sin(a):.1f}" x2="{r2*math.cos(a):.1f}" y2="{r2*math.sin(a):.1f}"/>'
svg += '''</g>
    <circle r="38" fill="url(#sun)"/>
  </g>
</svg>
'''
open("sunshine-a.svg", "w").write(svg)
