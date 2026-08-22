# -*- coding: utf-8 -*-
"""Render each known settings line from the DEPLOYED atlas at a fitted scale,
correlate it against the newest real screenshot, and report MISSING ink
specifically near the LINE END (left edge, RTL) vs elsewhere.

This sidesteps blob-splitting entirely (which breaks on touching/kerned
letters) by comparing whole-line rasters via 2D correlation, same method as
_diag_lineoverlay.py but generalized to N known rows and this screenshot.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG

SHOTS = r"C:\Users\Nehoray_Cohen\Pictures\Screenshots"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"


def latest_shot():
    files = sorted(glob.glob(os.path.join(SHOTS, "*.png")), key=os.path.getmtime)
    return files[-1]


def load_glyphs():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, g = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g[c] = dict(img=cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)],
                    bw=float(e.x1 - e.x0), adv=float(e.x1 - e.x0) + float(e.bx))
    return g


SPACE = 14.0
NARROW = 6.0     # geresh/apostrophe etc — not in our Hebrew set, thin filler


def render(text, g, s, box_h=70.0, pad=6):
    total = sum(SPACE if ch == " " else (g[ch]["adv"] if ch in g else NARROW) for ch in text)
    W = int(round(total * s)) + 2 * pad
    H = int(round(box_h * s)) + 2 * pad
    cv = np.zeros((H, W), float)
    pen = W - pad
    for ch in text:
        if ch == " ":
            pen -= SPACE * s
            continue
        if ch not in g:
            pen -= NARROW * s
            continue
        e = g[ch]
        w = max(1, int(round(e["bw"] * s)))
        h = max(1, int(round(box_h * s)))
        im = np.asarray(Image.fromarray(e["img"], "L").resize((w, h), Image.BILINEAR), float)
        x = int(round(pen - e["adv"] * s))
        x0 = max(0, x)
        cv[pad:pad + h, x0:x0 + w] = np.maximum(cv[pad:pad + h, x0:x0 + w], im[:, x0 - x:cv.shape[1] - x])
        pen -= e["adv"] * s
    return cv


def fit_and_diff(real, g, text, s_range=(0.35, 1.1), label=""):
    real = np.clip(real, 0, 255)
    best = None
    for s100 in range(int(s_range[0] * 100), int(s_range[1] * 100), 2):
        s = s100 / 100.0
        exp = render(text, g, s)
        if exp.shape[0] > real.shape[0] + 30 or exp.shape[1] > real.shape[1] + 30:
            continue
        for dy in range(-8, 9, 2):
            for dx in range(-15, 16, 2):
                A = np.zeros_like(real)
                H = min(exp.shape[0], real.shape[0]); W = min(exp.shape[1], real.shape[1])
                A[:H, :W] = exp[:H, :W]
                A = np.roll(np.roll(A, dy, 0), dx, 1)
                num = float((A * real).sum())
                den = float(np.sqrt((A * A).sum() * (real * real).sum())) or 1.0
                sc = num / den
                if best is None or sc > best[0]:
                    best = (sc, s, dy, dx)
    sc, s, dy0, dx0 = best
    # refine locally
    for dy in range(dy0 - 2, dy0 + 3):
        for dx in range(dx0 - 2, dx0 + 3):
            exp = render(text, g, s)
            A = np.zeros_like(real)
            H = min(exp.shape[0], real.shape[0]); W = min(exp.shape[1], real.shape[1])
            A[:H, :W] = exp[:H, :W]
            A = np.roll(np.roll(A, dy, 0), dx, 1)
            num = float((A * real).sum())
            den = float(np.sqrt((A * A).sum() * (real * real).sum())) or 1.0
            scv = num / den
            if scv > sc:
                sc, dy0, dx0 = scv, dy, dx
    exp = render(text, g, s)
    A = np.zeros_like(real)
    H = min(exp.shape[0], real.shape[0]); W = min(exp.shape[1], real.shape[1])
    A[:H, :W] = exp[:H, :W]
    A = np.roll(np.roll(A, dy0, 0), dx0, 1)
    miss = np.clip(A - real, 0, 255)
    Aenergy = max(A.sum(), 1)
    miss_pct = miss.sum() / Aenergy * 100
    # is the missing ink concentrated in the LEFT quarter (line end)?
    q = real.shape[1] // 4
    left_miss = miss[:, :q].sum()
    total_miss = miss.sum() or 1
    left_frac = left_miss / total_miss
    verdict = "CLIPPED AT LINE END" if (miss_pct > 12 and left_frac > 0.5) else \
              ("noisy fit" if miss_pct > 12 else "OK")
    print(f"  {label:34} corr={sc:.3f} scale={s:.2f}  missing={miss_pct:5.1f}%  "
          f"left-quarter-share={left_frac:.2f}   -> {verdict}")
    return real, A, miss


def main():
    shot = latest_shot()
    print("screenshot:", shot)
    im = Image.open(shot).convert("L")
    W, H = im.size
    sx, sy = W / 1600.0, H / 900.0
    g = load_glyphs()

    def box(x0, y0, x1, y1):
        return (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))

    tests = [
        (box(320, 270, 500, 330), "החלפת ג'ויסטיק", "row1"),
        (box(320, 340, 500, 400), "הפוך ציר אופקי של מצלמה", "row2"),
        (box(320, 410, 500, 470), "הפוך את ציר המצלמה האנכי", "row3"),
        (box(320, 480, 500, 535), "רגישות המצלמה", "row4"),
        (box(320, 550, 500, 605), "רגישות כוונון", "row5"),
        (box(320, 618, 500, 675), "רגישות תנועה", "row6"),
        (box(320, 688, 500, 745), "השתמש בסיוע כיוון", "row7"),
        (box(320, 745, 500, 835), "ביצוע אוטומטי של קלטים בזמן מוגדר", "row8"),
        (box(940, 270, 1410, 330), "החלפת ג'ויסטיק", "detail-title"),
    ]
    outs = []
    for b, text, lab in tests:
        raw = 255 - np.asarray(im.crop(b), float)
        raw = np.clip((raw - 60) * (255 / 130), 0, 255)   # kill background haze
        r, a, m = fit_and_diff(raw, g, text, label=lab)
        outs.append((lab, r, a, m))

    rowh = max(x[1].shape[0] for x in outs)
    W2 = max(x[1].shape[1] for x in outs)
    canvas = []
    for lab, r, a, m in outs:
        block = np.vstack([
            np.pad(r, ((0, rowh - r.shape[0]), (0, W2 - r.shape[1]))),
            np.pad(a, ((0, rowh - a.shape[0]), (0, W2 - a.shape[1]))),
            np.pad(m, ((0, rowh - m.shape[0]), (0, W2 - m.shape[1]))),
            np.full((4, W2), 128.0),
        ])
        canvas.append(block)
    out = np.vstack(canvas)
    Image.fromarray((255 - np.clip(out, 0, 255)).astype(np.uint8), "L").save(
        os.path.join(SC, "FULLVERIFY_overlay.png"))
    print("saved FULLVERIFY_overlay.png (per row: real / expected(fit) / missing)")


main()
