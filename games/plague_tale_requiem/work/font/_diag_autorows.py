# -*- coding: utf-8 -*-
"""Auto-locate each settings-list row by horizontal ink bands (no guessed y),
then per row correlate the LEFTMOST glyph blob (= LAST char, RTL) against the
atlas to check whether it renders at FULL width or is missing pixels — ground
truth, not a guess at coordinates.
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
THR = 60


def latest_shot():
    files = sorted(glob.glob(os.path.join(SHOTS, "*.png")), key=os.path.getmtime)
    return files[-1]


def atlas():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, out = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        ys = np.where((g > THR).any(axis=1))[0]
        xs = np.where((g > THR).any(axis=0))[0]
        out[c] = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float) / 255.0
    return out


def norm(a):
    a = np.asarray(a, float); a = a - a.min(); m = a.max()
    return a / m if m else a


def score(A, B):
    Bi = np.asarray(Image.fromarray((np.clip(B, 0, 1) * 255).astype(np.uint8), "L")
                    .resize((A.shape[1], A.shape[0]), Image.BILINEAR), float) / 255.0
    return float(((norm(A) - norm(Bi)) ** 2).mean())


def find_rows(col, y0, min_gap=6, min_h=5):
    """col: 2D dark-on-light array (already background-subtracted, ink>0)."""
    has_ink = (col > THR).any(axis=1)
    bands, s = [], None
    for i, v in enumerate(has_ink):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s >= min_h:
                bands.append((s, i))
            s = None
    if s is not None and len(has_ink) - s >= min_h:
        bands.append((s, len(has_ink)))
    # merge bands separated by < min_gap (diacritics / descenders)
    merged = []
    for a, b in bands:
        if merged and a - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append([a, b])
    return [(y0 + a, y0 + b) for a, b in merged]


def last_char(text):
    for c in reversed(text):
        if c != " ":
            return c
    return None


def main():
    shot = latest_shot()
    print("screenshot:", shot)
    im = Image.open(shot).convert("L")
    W, H = im.size
    print("size", (W, H))
    inks = atlas()

    # locate the settings-list column: search a wide x band on the left half
    x0, x1 = int(W * 0.20), int(W * 0.32)
    col = np.asarray(im.crop((x0, int(H * 0.25), x1, int(H * 0.95))), float)
    col = 255 - col
    col = np.clip((col - 40) * 3, 0, 255)
    bands = find_rows(col, int(H * 0.25))
    print(f"detected {len(bands)} row bands in column x[{x0}:{x1}]:")
    labels = ["החלפת ג'ויסטיק", "הפוך ציר אופקי של מצלמה", "הפוך את ציר המצלמה האנכי",
              "רגישות המצלמה", "רגישות כוונון", "רגישות תנועה", "השתמש בסיוע כיוון",
              "ביצוע אוטומטי של קלטים בזמן", "מוגדר"]
    for i, (a, b) in enumerate(bands):
        lab = labels[i] if i < len(labels) else "?"
        print(f"  band {i}: y[{a}:{b}] h={b-a}   guess='{lab}'")

    # now for each band, grab the WHOLE row width (wider x range) and find the
    # leftmost ink blob = last character in RTL
    x0w, x1w = int(W * 0.19), int(W * 0.34)
    results = []
    for i, (ya, yb) in enumerate(bands):
        if i >= len(labels):
            break
        text = labels[i]
        lc = last_char(text)
        if lc is None or lc not in inks:
            continue
        pad = 2
        raw = np.asarray(im.crop((x0w, ya - pad, x1w, yb + pad)), float)
        raw = 255 - raw
        raw = np.clip((raw - 40) * 3, 0, 255)
        cols = (raw > THR).any(axis=0)
        xs = np.where(cols)[0]
        if not len(xs):
            continue
        left = xs.min()
        # walk right from the left edge until a >=3px gap (end of first blob)
        x = left
        while x < raw.shape[1] - 3 and not (not cols[x + 1] and not cols[x + 2] and not cols[x + 3]):
            x += 1
        blob = raw[:, left:x + 1]
        ys2 = np.where((blob > THR).any(axis=1))[0]
        blob = blob[ys2.min():ys2.max() + 1] if len(ys2) else blob
        h = blob.shape[0]
        # score against the KNOWN last char, and its neighbours (sanity)
        cand = sorted(((score(blob, inks[c]), c) for c in inks), key=lambda t: t[0])
        rank = [c for _, c in cand].index(lc) if lc in [c for _, c in cand] else -1
        best_s, best_c = cand[0]
        exp_w = inks[lc].shape[1] * (h / inks[lc].shape[0])
        got_w = blob.shape[1]
        d = got_w - exp_w
        flag = "  *** SHORT (clipped) ***" if d < -1.5 else "  full width"
        print(f"  row{i} '{text}'  last-char expected '{lc}'  blob {got_w}x{h}  "
              f"expected_w={exp_w:.1f}  delta={d:+.1f}{flag}")
        print(f"      best atlas match = '{best_c}' (mse={best_s:.3f});  "
              f"'{lc}' itself ranks #{rank+1} of {len(cand)} (mse={dict(zip([c for _,c in cand],[s for s,_ in cand]))[lc]:.3f})")
        results.append(d)
    if results:
        print(f"\nline-end deltas: {[round(x,1) for x in results]}")


main()
