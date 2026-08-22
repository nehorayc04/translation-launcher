# -*- coding: utf-8 -*-
"""Measure the REAL in-game Hebrew from an autocheck capture: per-letter ink height,
inter-letter gap, and any stray ink (the 'dots'). Normalised to 1080p so it is comparable
with the offline prediction."""
import sys, os
import numpy as np
from PIL import Image

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
shot = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SC, "AUTOCHECK_vanilla.png")
# region of the start-screen line, and the game window height (for the 1080p normalisation)
X0, X1, Y0, Y1 = (int(v) for v in (sys.argv[2:6] if len(sys.argv) > 5 else (150, 620, 320, 410)))
WIN_H = int(sys.argv[6]) if len(sys.argv) > 6 else 900

im = Image.open(shot).convert("L")
a = np.array(im)[Y0:Y1, X0:X1].astype(np.int16)
# the start screen is bright-on-dark in this area; text is the DARK ink over a light fog,
# so try both polarities and keep whichever gives a compact band
best = None
for pol, arr in (("dark", 255 - a), ("light", a)):
    m = arr > (arr.mean() + 2.2 * arr.std())
    rows = np.where(m.any(axis=1))[0]
    if len(rows) < 4:
        continue
    band = rows.max() - rows.min() + 1
    if best is None or band < best[0]:
        best = (band, pol, m)
if best is None:
    print("no ink found in the region"); sys.exit(0)
band, pol, m = best
rows = np.where(m.any(axis=1))[0]
cols = np.where(m.any(axis=0))[0]
print(f"polarity={pol}  band rows {rows.min()}..{rows.max()} (h={band})  "
      f"cols {cols.min()}..{cols.max()}")

# split into letters on empty columns
runs, cur = [], None
colhas = m.any(axis=0)
for x in range(m.shape[1]):
    if colhas[x] and cur is None:
        cur = x
    elif not colhas[x] and cur is not None:
        runs.append((cur, x - 1)); cur = None
if cur is not None:
    runs.append((cur, m.shape[1] - 1))
runs = [r for r in runs if r[1] - r[0] >= 1]
hs, gaps = [], []
print(f"{'#':>3} {'x0':>4} {'x1':>4} {'w':>3} {'h':>3}")
for i, (x0, x1) in enumerate(runs):
    sub = m[:, x0:x1 + 1]
    ys = np.where(sub.any(axis=1))[0]
    h = ys.max() - ys.min() + 1
    hs.append(h)
    if i:
        gaps.append(x0 - runs[i - 1][1] - 1)
    print(f"{i:>3} {x0:>4} {x1:>4} {x1-x0+1:>3} {h:>3}")
hs = np.array(hs)
k = 1080.0 / WIN_H
med = float(np.median(hs))
print(f"\nblobs={len(runs)}  ink height: median={med:.1f}px  "
      f"p25={np.percentile(hs,25):.1f} p75={np.percentile(hs,75):.1f}  max={hs.max()}")
print(f"normalised to 1080p (x{k:.3f}): median body ~= {med*k:.1f}px   tallest {hs.max()*k:.1f}px")
if gaps:
    print(f"inter-letter gap: median={np.median(gaps):.1f}px = {np.median(gaps)/med*100:.1f}% of body"
          f"   (English reference 17.6%)")
# stray ink = tiny blobs far from the band (the 'dots')
tiny = [(x0, x1) for x0, x1 in runs if (x1 - x0 + 1) <= 2]
print(f"suspicious 1-2px blobs: {len(tiny)}  {tiny[:10]}")
