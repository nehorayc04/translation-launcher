# -*- coding: utf-8 -*-
"""Measure the user's side-by-side screenshot: how much BIGGER is the deployed Hebrew than the
game's own English, and how do the stroke weight / letter spacing compare?

The screenshot is the ground truth the user is judging by, and it contains BOTH scripts rendered
by the SAME engine at the same UI scale — so it is a calibrated ruler. Everything is derived from
it; nothing is guessed. See [[minimize-game-restarts]].
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Nehoray_Cohen\Desktop\תמונה1.png"
im = Image.open(SHOT).convert("L")
a = np.array(im, np.int16)
H, W = a.shape
print(f"screenshot {W}x{H}")

# text is DARK on a light parchment.
THRESH = 140
ink = a < THRESH

# ⚠️ The two panels are separated by a FULL-HEIGHT black bar. Left in, it contributes ink to
# EVERY row, so no row ever reads as "blank" and the band splitter returns a single band — that
# is exactly how the first run silently produced one 648 px "letter". Cut the bar out first.
colf = ink.mean(axis=0)
bar = np.where(colf > 0.9)[0]
bar0, bar1 = (int(bar.min()), int(bar.max())) if len(bar) else (W // 2, W // 2)
print(f"separator bar x={bar0}..{bar1}  ->  English [0,{bar0})   Hebrew ({bar1},{W})")


def rows_of(mask):
    """contiguous horizontal bands whose ink fraction looks like a line of text"""
    frac = mask.mean(axis=1)
    r = (frac > 0.004) & (frac < 0.35)
    out, s = [], None
    for y in range(len(r)):
        if r[y] and s is None:
            s = y
        elif not r[y] and s is not None:
            if 12 <= y - s <= 160:
                out.append((s, y))
            s = None
    if s is not None and 12 <= len(r) - s <= 160:
        out.append((s, len(r)))
    return out


def letters(band):
    """split a text band into letter blobs by empty columns; return (height, width, x0, x1)"""
    c = band.any(axis=0)
    out, s = [], None
    for x in range(len(c)):
        if c[x] and s is None:
            s = x
        elif not c[x] and s is not None:
            if x - s >= 2:
                sub = band[:, s:x]
                ys = np.where(sub.any(axis=1))[0]
                out.append((int(ys.max() - ys.min() + 1), x - s, s, x))
            s = None
    return out


def stroke_widths(band):
    runs = []
    for y in range(band.shape[0]):
        c = 0
        for v in band[y]:
            if v:
                c += 1
            elif c:
                runs.append(c); c = 0
    return runs


def analyse(x0, x1, label):
    m = ink[:, x0:x1]
    bands = rows_of(m)
    print(f"\n=== {label}  ({len(bands)} text rows) ===")
    all_h, all_gap, all_sw = [], [], []
    for (y0, y1) in bands:
        band = m[y0:y1]
        ls = letters(band)
        if len(ls) < 3:
            continue
        hs = [l[0] for l in ls]
        # gaps between consecutive blobs, ignoring word spaces (> 2x median letter width)
        mw = np.median([l[1] for l in ls])
        gaps = [ls[i + 1][2] - ls[i][3] for i in range(len(ls) - 1)]
        gaps = [g for g in gaps if 0 <= g <= mw * 1.2]
        sw = stroke_widths(band)
        all_h += hs
        all_gap += gaps
        all_sw += sw
    all_h = np.array(all_h); all_sw = np.array(all_sw)
    med_h = float(np.median(all_h))
    # the tallest decile ~ cap/ascender height, the median ~ x-height (English) / body (Hebrew)
    cap = float(np.percentile(all_h, 90))
    med_sw = float(np.median(all_sw))
    med_gap = float(np.median(all_gap)) if all_gap else 0.0
    print(f"  letter blobs        : {len(all_h)}")
    print(f"  median letter height: {med_h:6.1f} px   (English -> x-height, Hebrew -> body)")
    print(f"  90th pct height     : {cap:6.1f} px   (cap / ascender)")
    print(f"  median stroke width : {med_sw:6.1f} px   -> {med_sw/med_h*100:4.1f}% of the body")
    print(f"  median letter gap   : {med_gap:6.1f} px   -> {med_gap/med_h*100:4.1f}% of the body")
    return med_h, cap, med_sw, med_gap


en_h, en_cap, en_sw, en_gap = analyse(0, bar0, "ENGLISH (the game's own font)")
he_h, he_cap, he_sw, he_gap = analyse(bar1 + 1, W, "HEBREW (deployed, 26 px ink)")

print("\n=== VERDICT ===")
print(f"  Hebrew body / English x-height = {he_h/en_h:.2f}x")
print(f"  Hebrew body / English cap      = {he_h/en_cap:.2f}x")
print(f"  stroke: EN {en_sw/en_h*100:.1f}% vs HE {he_sw/he_h*100:.1f}% of body")
print(f"  gap   : EN {en_gap/en_h*100:.1f}% vs HE {he_gap/he_h*100:.1f}% of body")
for target, name in ((en_h, "English x-height"), (en_cap, "English cap")):
    print(f"  -> to match {name}: HEB_BODY = 26 * {target/he_h:.3f} = {26*target/he_h:.1f} px")
