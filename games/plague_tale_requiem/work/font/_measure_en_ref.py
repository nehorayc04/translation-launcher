# -*- coding: utf-8 -*-
"""Measure the English menu text height DIRECTLY from the user's full-menu reference, so the
Hebrew target is calibrated against the game's OWN render at the same resolution, not an old
side-by-side estimate."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

REF = r"C:\Users\Nehoray_Cohen\Desktop\תמונה1.png"
a = np.array(Image.open(REF).convert("L"), np.int16)
H, W = a.shape
print(f"reference image {W}x{H}")
ink = a < 110
# menu text sits in the left ~55%; ignore the faint watercolour background on the right
ink[:, int(W * 0.55):] = False
frac = ink.mean(axis=1)
thr = max(0.0008, frac[frac > 0].mean() * 0.25) if (frac > 0).any() else 0.001
print(f"row-ink fraction: max={frac.max():.4f} mean(nonzero)={frac[frac>0].mean():.4f} thr={thr:.4f}")
r = (frac > thr) & (frac < 0.5)
bands, s = [], None
for y in range(H):
    if r[y] and s is None:
        s = y
    elif not r[y] and s is not None:
        if 20 <= y - s <= 220:
            bands.append((s, y))
        s = None
print(f"text rows found: {len(bands)}")
caps, xhs = [], []
for (y0, y1) in bands:
    b = ink[y0:y1]
    c = b.any(axis=0)
    hs = []
    x = None
    for xi in range(len(c)):
        if c[xi] and x is None:
            x = xi
        elif not c[xi] and x is not None:
            if xi - x >= 2:
                ys = np.where(b[:, x:xi].any(axis=1))[0]
                hs.append(int(ys.max() - ys.min() + 1))
            x = None
    if len(hs) >= 3:
        hs.sort()
        caps.append(hs[-1])                      # tallest blob ~ a capital
        xhs.append(float(np.median(hs)))         # median blob ~ x-height-ish
print(f"english CAP  (tallest per row) median = {np.median(caps):.0f} px  (rows: {sorted(caps)})")
print(f"english BODY (median blob)     median = {np.median(xhs):.0f} px")
print(f"\nengine magnification for BIG_ARABIC = x3.31, so to match:")
for name, tgt in (("cap", np.median(caps)), ("body/x-height", np.median(xhs))):
    print(f"  {name:14s} {tgt:.0f}px screen  ->  atlas ink {tgt/3.31:.1f}px")
