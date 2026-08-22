# -*- coding: utf-8 -*-
"""Is the width loss POSITIONAL (only the line's last glyph) or GLYPH-specific?

'tav' is the last char of the title, of matarot and of bakarot — but the FIRST
char of 'tdirut hasiyua'. Measure it in both roles.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from _diag_lineend import atlas, ORD_INK

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")


def run(im, box, txt, label, info, thr=110, merge=1):
    a = 255 - np.asarray(im.crop(box), dtype=np.int16)
    ink = a > thr
    cols = ink.any(axis=0)
    sp, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        elif not v and s is not None:
            sp.append([s, i]); s = None
    if s is not None:
        sp.append([s, len(cols)])
    m = []
    for x0, x1 in sp:
        if m and x0 - m[-1][1] <= merge:
            m[-1][1] = x1
        else:
            m.append([x0, x1])
    rows = np.where(ink.any(axis=1))[0]
    lh = rows.max() - rows.min() + 1
    sc = lh / ORD_INK
    letters = [c for c in txt if c != " "]
    exp = [(c, round(info[c]["inkw"] * sc, 1)) for c in reversed(letters)]
    print(f"\n{label}   line_h={lh}  scale={sc:.3f}  blobs={len(m)} vs chars={len(letters)}")
    print(f"   expected (L->R, i.e. last char first): {exp}")
    print(f"   rendered (L->R): {[(b[0], b[1]-b[0]) for b in m]}")
    if len(m) == len(letters):
        print("   MATCHED per-glyph:")
        for i, (c, e) in enumerate(exp):
            w = m[i][1] - m[i][0]
            role = "LAST" if i == 0 else ("FIRST" if i == len(exp) - 1 else "")
            print(f"     '{c}' rendered {w:3d}  expected {e:5.1f}  delta {w-e:+5.1f}  {role}")


def main():
    info = atlas()
    im = Image.open(os.path.join(SC, "AUTOCHECK_weight.png")).convert("L")
    run(im, (352, 344, 496, 382), "תדירות הסיוע", "row2 tdirut-hasiyua", info)
    run(im, (352, 274, 496, 312), "רמת קושי", "row1 ramat-kushi", info)
    run(im, (352, 414, 496, 452), "רעידה", "row3 reida", info)
    run(im, (352, 764, 496, 806), "מטרות", "row8 matarot", info)


main()
