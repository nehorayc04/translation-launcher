# -*- coding: utf-8 -*-
"""Sweep (font weight x sub-pixel WEIGHT_SS) and report stroke/body against the English ruler."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import build_hebrew_font as B

TARGET = 0.167          # measured from the vanilla English label in the same widget


def runs_of(m):
    out = []
    for y in range(m.shape[0]):
        n = 0
        for v in m[y]:
            if v:
                n += 1
            elif n:
                out.append(n); n = 0
        if n:
            out.append(n)
    return out


print(f"{'font':<40} {'W':>2} {'body':>4} {'stroke':>6} {'ratio':>6} {'mid/sol':>7}   target {TARGET}")
for name in ("opensanshebrew-light-webfont.ttf", "opensanshebrew-regular-webfont.ttf"):
    p = os.path.join(r"C:\Windows\Fonts", name)
    for w in (0, 2, 3, 4, 5, 6):
        B.WEIGHT_SS = w
        gs = B.cap_span(B.render_set(p, B.fit_body(p, B.LADDER_INK[0]), B.HEBREW))
        body = gs["נ"][0].shape[0]
        runs, solid, mid = [], 0, 0
        for ch, (g, _a) in gs.items():
            runs += [v for v in runs_of(g > 128) if v <= 12]
            solid += int((g > 200).sum()); mid += int(((g > 30) & (g <= 200)).sum())
        sw = float(np.median(runs)) if runs else 0.0
        r = sw / max(body, 1)
        tag = "  <== in band" if 0.145 <= r <= 0.175 else ""
        print(f"{name:<40} {w:>2} {body:>4} {sw:>6.1f} {r:>6.3f} "
              f"{mid/max(solid,1):>7.2f}{tag}")
