# -*- coding: utf-8 -*-
"""Why do Hebrew labels WRAP (and then collide with the next row) where English does not?

The visible defect is vertical (overlapping rows), but the cause is HORIZONTAL: the Hebrew
string is wider than the box. The number that decides that is the ADVANCE (start-to-start
distance) per letter, normalised by the body height — not the inter-letter gap.

Compares my own game capture against the user's English reference.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")


def blobs_of(path, x0=0, x1=None, thresh=140):
    a = np.array(Image.open(path).convert("L"), np.int16)
    if x1 is None:
        x1 = a.shape[1]
    a = a[:, x0:x1]
    ink = a < thresh
    colf = ink.mean(axis=0)
    bar = np.where(colf > 0.9)[0]
    if len(bar):
        ink[:, bar.min():bar.max() + 1] = False
    frac = ink.mean(axis=1)
    r = (frac > 0.002) & (frac < 0.35)
    rows, s = [], None
    for y in range(len(r)):
        if r[y] and s is None:
            s = y
        elif not r[y] and s is not None:
            if 10 <= y - s <= 200:
                rows.append((s, y))
            s = None
    out = []
    for (y0, y1) in rows:
        b = ink[y0:y1]
        c = b.any(axis=0)
        bl, s2 = [], None
        for x in range(len(c)):
            if c[x] and s2 is None:
                s2 = x
            elif not c[x] and s2 is not None:
                if x - s2 >= 2:
                    ys = np.where(b[:, s2:x].any(axis=1))[0]
                    bl.append((s2, x, int(ys.max() - ys.min() + 1)))
                s2 = None
        if len(bl) >= 4:
            out.append(((y0, y1), bl))
    return out


def report(path, label, x0=0, x1=None):
    rows = blobs_of(path, x0, x1)
    hs, advs, widths = [], [], []
    for (_, bl) in rows:
        mw = np.median([b[1] - b[0] for b in bl])
        hs += [b[2] for b in bl]
        widths += [b[1] - b[0] for b in bl]
        for i in range(len(bl) - 1):
            adv = bl[i + 1][0] - bl[i][0]          # start-to-start
            if 0 < adv <= mw * 2.2:                # ignore word spaces
                advs.append(adv)
    if not hs:
        print(f"  [{label}] nothing found"); return None
    body = float(np.median(hs)); adv = float(np.median(advs)); w = float(np.median(widths))
    print(f"  [{label:<22}] rows={len(rows):2d}  body={body:5.1f}  glyph_w={w:5.1f} "
          f"({w/body*100:5.1f}%)  ADVANCE={adv:5.1f} ({adv/body*100:5.1f}% of body)")
    return body, w / body * 100, adv / body * 100


print("ADVANCE per letter, as a % of the body height  (this is what decides line width)\n")
EN = r"C:\Users\Nehoray_Cohen\Desktop\תמונה1.png"
# left panel = English, right = Hebrew (bar at x=1434..1463)
report(EN, "ENGLISH (reference)", 0, 1434)
report(EN, "HEBREW 26px build", 1464, None)
mine = os.path.join(SC, "AUTOCHECK_he21.png")
if os.path.exists(mine):
    report(mine, "HEBREW 21px (mine now)")
