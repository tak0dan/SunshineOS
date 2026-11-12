#!/usr/bin/env python3
"""Sunshine OS logo animation for the terminal: kitty, foot, konsole (and anything with truecolor).

  play.py --lite --splash     start-up splash (build-up, then back to the prompt) - use before fastfetch
  play.py --lite              build-up, then the idle loop until a key is pressed
  options: --once (leave after one idle loop)   --mode=kitty|sixel|blocks (default: auto-detect)

Renderers
  kitty   kitty graphics protocol with native animation frames
  sixel   sixel graphics (foot, konsole, xterm, mlterm, wezterm ...), auto-detected through the DA1 reply
  blocks  half-block characters in truecolor, works everywhere, keeps the terminal background
"""
import sys, os, io, json, base64, struct, fcntl, termios, time, tty, select, re
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
LITE = '--lite' in ARGS
SPLASH = '--splash' in ARGS
ONCE = '--once' in ARGS
MODE = next((a.split('=', 1)[1] for a in ARGS if a.startswith('--mode=')), None)
M = json.load(open(os.path.join(HERE, 'sprite-lite.json' if LITE else 'sprite.json')))
FPS, FW, FH, COLS = M['fps'], M['frame_w'], M['frame_h'], M['cols']
INTRO_N, LOOP_N = M['intro']['frames'], M['loop']['frames']
INTRO_DUR = INTRO_N / FPS
SPLASH_END = 6.0 if LITE else 5.2            # seconds of the build-up shown by --splash
TITLE_AT = 4.4
TITLE, SUB = 'S U N S H I N E   O S', 'Arch-based. Terminal and desktop.'
out = sys.stdout.buffer
IN = sys.stdin.fileno()

def w(s): out.write(s.encode() if isinstance(s, str) else s)

# ---------------------------------------------------------------- terminal helpers
def winsize():
    rows, cols, wpx, hpx = struct.unpack('HHHH', fcntl.ioctl(1, termios.TIOCGWINSZ, b'\0' * 8))
    return rows, cols, wpx, hpx

def query(seq, pattern, timeout=0.5):
    """Send a control sequence and read the terminal's reply (needs cbreak mode)."""
    try: termios.tcflush(IN, termios.TCIFLUSH)
    except Exception: pass
    w(seq); out.flush()
    buf = b''; end = time.time() + timeout
    while time.time() < end:
        if select.select([IN], [], [], 0.05)[0]:
            buf += os.read(IN, 256)
            m = re.search(pattern, buf)
            if m: return m
    return None

def cell_px(rows, cols):
    _, _, wpx, hpx = winsize()
    if wpx and hpx: return wpx / cols, hpx / rows
    m = query('\x1b[16t', rb'\x1b\[6;(\d+);(\d+)t')
    if m: return int(m.group(2)), int(m.group(1))
    return 9.0, 18.0

def detect_mode():
    if MODE: return MODE
    if os.environ.get('KITTY_WINDOW_ID') or os.environ.get('TERM') == 'xterm-kitty': return 'kitty'
    m = query('\x1b[c', rb'\x1b\[\?([0-9;]*)c')
    if m and '4' in m.group(1).decode().split(';'): return 'sixel'
    return 'blocks'

def terminal_bg():
    m = query('\x1b]11;?\x1b\\', rb'rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)', 0.3)
    if m:
        try: return tuple(int(g[:2], 16) for g in m.groups())
        except Exception: pass
    return (14, 10, 26)

# ---------------------------------------------------------------- frames
def sheet_frames(key):
    sh = np.array(Image.open(os.path.join(HERE, M[key]['file'])).convert('RGBA'))
    fr = []
    for i in range(M[key]['frames']):
        x, y = (i % COLS) * FW, (i // COLS) * FH
        fr.append(sh[y:y + FH, x:x + FW])
    return fr

def crop_box(frames):
    a = np.zeros((FH, FW), bool)
    for f in frames: a |= f[..., 3] > 0
    ys, xs = np.nonzero(a)
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1

def key_frame(frames_i, frames_l, key):
    return frames_i[key[1]] if key[0] == 0 else frames_l[key[1]]

def timeline(now):
    return (0, min(int(now * FPS), INTRO_N - 1)) if now < INTRO_DUR else (1, int((now - INTRO_DUR) * FPS) % LOOP_N)

def title_chars(now):
    return max(0, min(len(TITLE), int((now - TITLE_AT) / 0.03) + 1)) if now >= TITLE_AT else 0

def draw_title(row, cols, k, sub):
    if k <= 0: return
    w(f'\x1b[{row};{(cols - len(TITLE)) // 2 + 1}H\x1b[0;1;38;2;255;196;61m{TITLE[:k]}\x1b[0m')
    if sub: w(f'\x1b[{row + 1};{(cols - len(SUB)) // 2 + 1}H\x1b[0;38;2;170;150;125m{SUB}\x1b[0m')

# ---------------------------------------------------------------- sixel renderer
class Sixel:
    def __init__(s, frames, bg):
        s.bg = bg; s.cache = {}
        allpx = np.concatenate([f[f[..., 3] > 0][:, :3].reshape(-1, 3) for f in frames])
        packed = np.unique((allpx[:, 0].astype(np.int64) << 16) | (allpx[:, 1].astype(np.int64) << 8) | allpx[:, 2])
        s.reduced = None
        if len(packed) > 250:                      # sixel terminals keep at most 256 colour registers (konsole: 256)
            sample = Image.fromarray(allpx[:: max(1, len(allpx) // 60000)].reshape(1, -1, 3).astype(np.uint8))
            q = sample.quantize(colors=240, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            pal = np.array(q.getpalette()[:240 * 3], np.int32).reshape(-1, 3)
            orig = packed
            oc = np.stack([(orig >> 16) & 255, (orig >> 8) & 255, orig & 255], 1).astype(np.int32)
            s.orig = orig
            s.lut = ((oc[:, None, :] - pal[None, :, :]) ** 2).sum(-1).argmin(-1).astype(np.int16)   # nearest register for every original colour
            s.reduced = pal
            packed = np.array([(int(r) << 16) | (int(g) << 8) | int(b) for r, g, b in pal], np.int64)
        s.pal = [((p >> 16) & 255, (p >> 8) & 255, p & 255) for p in packed] + [bg]
        s.packed = packed; s.bgi = len(s.pal) - 1
        s.head = ''.join(f'#{i};2;{round(r*100/255)};{round(g*100/255)};{round(b*100/255)}' for i, (r, g, b) in enumerate(s.pal))
    def index(s, f):
        if s.reduced is not None:
            q = (f[..., 0].astype(np.int64) << 16) | (f[..., 1].astype(np.int64) << 8) | f[..., 2]
            idx = s.lut[np.clip(np.searchsorted(s.orig, q), 0, len(s.orig) - 1)]
            return np.where(f[..., 3] > 0, idx, s.bgi).astype(np.int16)
        p = (f[..., 0].astype(np.int64) << 16) | (f[..., 1].astype(np.int64) << 8) | f[..., 2]
        idx = np.searchsorted(s.packed, p)
        idx = np.clip(idx, 0, len(s.packed) - 1)
        return np.where(f[..., 3] > 0, idx, s.bgi).astype(np.int16)
    def encode(s, f, scale):
        key = (f.tobytes(), scale)
        hit = s.cache.get(key)
        if hit is not None: return hit
        img = np.repeat(np.repeat(s.index(f), scale, 0), scale, 1)
        H, W = img.shape
        pieces = [f'\x1bP0;0;0q"1;1;{W};{H}', s.head]
        bits = (1 << np.arange(6))[None, :, None]
        for y0 in range(0, H, 6):
            band = img[y0:y0 + 6]
            if band.shape[0] < 6: band = np.vstack([band, np.full((6 - band.shape[0], W), -1, np.int16)])
            present = np.unique(band); present = present[present >= 0]
            chars = ((band[None] == present[:, None, None]) * bits).sum(1) + 63         # (colors, W)
            first = True
            for k, c in enumerate(present):
                row = chars[k]
                chg = np.flatnonzero(row[1:] != row[:-1]) + 1
                st = [0] + chg.tolist(); en = chg.tolist() + [W]
                seg = []
                for a_, b_ in zip(st, en):
                    n = b_ - a_; ch = chr(int(row[a_]))
                    seg.append(f'!{n}{ch}' if n > 3 else ch * n)
                if len(st) == 1 and row[0] == 63: continue
                pieces.append(('' if first else '$') + f'#{int(c)}' + ''.join(seg)); first = False
            if y0 + 6 < H: pieces.append('-')                      # no band separator after the last band
        pieces.append('\x1b\\')
        res = ''.join(pieces); s.cache[key] = res
        return res

# ---------------------------------------------------------------- half-block renderer
class Blocks:
    def __init__(s): s.prev = None
    def reset(s): s.prev = None
    def render(s, f, top, left):
        H, W, _ = f.shape
        if H % 2: f = np.vstack([f, np.zeros((1, W, 4), np.uint8)]); H += 1
        t, b = f[0::2], f[1::2]
        ta, ba = t[..., 3] > 0, b[..., 3] > 0
        kind = ta.astype(np.int8) | (ba.astype(np.int8) << 1)            # 0 empty, 1 upper, 2 lower, 3 both
        tc = (t[..., 0].astype(np.int32) << 16) | (t[..., 1].astype(np.int32) << 8) | t[..., 2]
        bc = (b[..., 0].astype(np.int32) << 16) | (b[..., 1].astype(np.int32) << 8) | b[..., 2]
        tc = np.where(ta, tc, 0); bc = np.where(ba, bc, 0)
        cur = np.stack([kind.astype(np.int32), tc, bc])
        changed = np.ones(kind.shape, bool) if s.prev is None else (cur != s.prev).any(0)
        s.prev = cur
        buf = ['\x1b[?2026h']
        for y in range(changed.shape[0]):
            xs = np.flatnonzero(changed[y])
            if not len(xs): continue
            run_start = None; last = None
            for x in xs:
                if last is None or x != last + 1:
                    buf.append(f'\x1b[{top + y};{left + x}H'); 
                last = x
                k = kind[y, x]; c1 = int(tc[y, x]); c2 = int(bc[y, x])
                if k == 0: buf.append('\x1b[0m ')
                elif k == 1: buf.append(f'\x1b[0;38;2;{c1>>16};{(c1>>8)&255};{c1&255}m▀')
                elif k == 2: buf.append(f'\x1b[0;38;2;{c2>>16};{(c2>>8)&255};{c2&255}m▄')
                else: buf.append(f'\x1b[0;38;2;{c1>>16};{(c1>>8)&255};{c1&255};48;2;{c2>>16};{(c2>>8)&255};{c2&255}m▀')
        buf.append('\x1b[0m\x1b[?2026l')
        w(''.join(buf)); out.flush()

# ---------------------------------------------------------------- kitty renderer (native animation frames)
IMG_A, IMG_B = 7, 8
def gr(ctrl, payload=b''):
    data = base64.standard_b64encode(payload)
    if not data:
        out.write(b'\x1b_G' + ctrl.encode() + b'\x1b\\'); return
    chunks = [data[i:i + 4096] for i in range(0, len(data), 4096)]
    for i, ch in enumerate(chunks):
        c = (ctrl + ',' if i == 0 else '') + f'm={1 if i < len(chunks) - 1 else 0}'
        out.write(b'\x1b_G' + c.encode() + b';' + ch + b'\x1b\\')

def kitty_upload(img_id, frames, scale, display, c, r, last_gap_ms, flush_every=8):
    gap = int(1000 / FPS); n = len(frames)
    for i, f in enumerate(frames):
        im = Image.fromarray(f, 'RGBA').resize((f.shape[1] * scale, f.shape[0] * scale), Image.NEAREST)
        b = io.BytesIO(); im.save(b, 'PNG', compress_level=1); png = b.getvalue()
        if i == 0:
            gr(f'a={"T" if display else "t"},f=100,i={img_id},c={c},r={r},q=2,C=1', png)
            gr(f'a=a,i={img_id},r=1,z={gap},q=2')
        else:
            gr(f'a=f,i={img_id},f=100,z={last_gap_ms if i == n - 1 else gap},X=1,q=2', png)
        if i % flush_every == 0: out.flush()
    out.flush()

def run_kitty(rows, cols, cw, ch):
    fi, fl = sheet_frames('intro'), sheet_frames('loop')
    scale = 4 if LITE else 2                       # kitty keeps ~320 MB of images
    px_w, px_h = FW * scale, FH * scale
    c = max(8, round(px_w / cw)); r = max(4, round(px_h / ch))
    top = max(1, (rows - r - 3) // 2 + 1); left = max(1, (cols - c) // 2 + 1)
    w(f'\x1b[{top};{left}H')
    kitty_upload(IMG_A, fi, scale, True, c, r, 600)
    gr(f'a=a,i={IMG_A},s=3,v=2,q=2'); out.flush()
    t0 = time.time()
    if not SPLASH:
        w(f'\x1b[{top};{left}H'); kitty_upload(IMG_B, fl, scale, False, c, r, int(1000 / FPS), flush_every=4)
    row = top + r + 1; swapped = False; shown = 0
    def cleanup(): w('\x1b_Ga=d,d=A,q=2\x1b\\')
    while True:
        now = time.time() - t0
        k = title_chars(now)
        if k != shown: shown = k; draw_title(row, cols, k, k >= len(TITLE)); out.flush()
        if SPLASH and now >= SPLASH_END: break
        if not SPLASH and not swapped and now >= INTRO_DUR:
            swapped = True
            w(f'\x1b[{top};{left}H')
            gr(f'a=p,i={IMG_B},c={c},r={r},z=2,C=1,q=2'); gr(f'a=d,d=I,i={IMG_A},q=2'); gr(f'a=a,i={IMG_B},s=3,v=1,q=2'); out.flush()
        if select.select([IN], [], [], 0.02)[0]: os.read(IN, 64); break
        if ONCE and now > INTRO_DUR + 10.5: break
    return cleanup

# ---------------------------------------------------------------- client-side player (sixel / blocks)
def run_client(mode, rows, cols, cw, ch):
    fi, fl = sheet_frames('intro'), sheet_frames('loop')
    y0, y1, x0, x1 = crop_box(fi + fl)
    fi = [f[y0:y1, x0:x1] for f in fi]; fl = [f[y0:y1, x0:x1] for f in fl]
    h, wd = y1 - y0, x1 - x0
    keep = 3                                          # lines kept for title + subtitle
    if mode == 'sixel':
        scale = max(1, min(int((cols * cw) // wd), int(((rows - keep - 1) * ch) // h), 8))
        r_cells = -(-h * scale // int(ch)); c_cells = -(-wd * scale // int(cw))
        bg = terminal_bg(); sx = Sixel(fi + fl, bg)
        cleanup = lambda: None
    else:
        d = 1
        while (-(-h // d) + 1) // 2 + keep + 1 > rows or -(-wd // d) > cols:
            d += 1
            if d > 4: raise SystemExit('terminal too small for the animation')
        if d > 1:
            fi = [f[::d, ::d] for f in fi]; fl = [f[::d, ::d] for f in fl]; h, wd = fi[0].shape[:2]
        r_cells = (h + 1) // 2; c_cells = wd
        bl = Blocks(); cleanup = lambda: w('\x1b[0m')
    top = max(1, (rows - r_cells - keep) // 2 + 1); left = max(1, (cols - c_cells) // 2 + 1)
    row = top + r_cells + 1
    t0 = time.time(); last = None; shown = 0
    while True:
        now = time.time() - t0
        if SPLASH and now >= SPLASH_END: break
        key = timeline(now)
        if key != last:
            last = key; f = key_frame(fi, fl, key)
            if mode == 'sixel':
                w(f'\x1b[{top};{left}H' + sx.encode(f, scale))
            else:
                bl.render(f, top, left)
            k = title_chars(now)
            if k != shown: shown = k; draw_title(row, cols, k, k >= len(TITLE))
            out.flush()
        nxt = (int(now * FPS) + 1) / FPS - (time.time() - t0)
        if select.select([IN], [], [], max(0.001, min(0.05, nxt)))[0]: os.read(IN, 64); break
        if ONCE and now > INTRO_DUR + 10.5: break
    return cleanup

# ---------------------------------------------------------------- main
def main():
    if not sys.stdout.isatty():
        print('run this in a terminal'); return
    rows, cols, _, _ = winsize()
    old = termios.tcgetattr(IN); tty.setcbreak(IN)
    cleanup = lambda: None
    try:
        mode = detect_mode()
        cw, ch = cell_px(rows, cols)
        w('\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H'); out.flush()
        cleanup = run_kitty(rows, cols, cw, ch) if mode == 'kitty' else run_client(mode, rows, cols, cw, ch)
    finally:
        try: cleanup()
        except Exception: pass
        termios.tcsetattr(IN, termios.TCSADRAIN, old)
        w('\x1b[0m\x1b[?25h\x1b[?1049l'); out.flush()

if __name__ == '__main__':
    main()
