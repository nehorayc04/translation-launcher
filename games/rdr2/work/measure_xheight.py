#!/usr/bin/env python3
"""measure_xheight.py — per face: Latin CAP, Latin X-HEIGHT, current Hebrew, and the k that
would move the Hebrew onto the cap/x-height MIDPOINT.

WHY (2026-08-07, user: "הטקסט גדול מדי"): rescaling every face's Hebrew onto its own Latin CAP
is arithmetically defensible and reads OVERSIZED, because running Latin is mostly LOWERCASE — a
reader compares the Hebrew block to the x-height, not to the cap. Hebrew is unicase, so at equal
cap height it also carries far more ink per line. The same lesson already cost a round on
A Plague Tale, where the shipped value ended up at the cap/x-height midpoint.

SELF-ADJUSTING BY DESIGN: a display face whose lowercase is nearly as tall as its caps (or which
is used all-caps, e.g. the death headline) has x/cap ≈ 1, so its midpoint ≈ its cap and it barely
moves. Body faces, whose x/cap ≈ 0.7, shrink. That is exactly the split the user reported —
"מת" correct, menus too big.

Reuses scan_faces' PROVEN slicing/measurement (a hand-rolled re-implementation produced
identical numbers for eight different faces, which is the signature of reading the wrong region).

    python measure_xheight.py [path/to/full.xml]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import scan_faces as sf  # noqa: E402

# FLAT-topped only, both rows: a round cap (O C G) overshoots the cap line and a round x-height
# letter (o e c) overshoots the x-line, which would inflate both references unevenly.
CAPS = set(ord(c) for c in "EFHILT")
XS = set(ord(c) for c in "xzvwrn")
HEB = set(range(0x05D0, 0x05EB))


def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else 0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "_fontinspect", "rescaled_full.xml")
    print(f"reading {path} ({os.path.getsize(path)/1e6:.0f} MB) ...", flush=True)
    txt = open(path, encoding="utf-8", errors="replace").read()
    print(f"loaded {len(txt)/1e6:.0f} M chars\n", flush=True)
    print(f"{'face':32} {'cap':>5} {'x-ht':>5} {'x/cap':>6} {'HEB':>5} {'he/cap':>7} "
          f"{'target':>7} {'k':>6}")
    print("-" * 88)
    for name, a, b in sf.face_slices(txt):
        boxes, codes = sf.measure(txt, a, b)
        n = min(len(boxes), len(codes))
        cap, xs, hb = [], [], []
        for i in range(n):
            bx, c = boxes[i], codes[i]
            if bx is None:
                continue
            h = bx[3] - bx[1]
            if c in CAPS:
                cap.append(h)
            elif c in XS:
                xs.append(h)
            elif c in HEB:
                hb.append(h)
        c0, x0, h0 = med(cap), med(xs), med(hb)
        if not (c0 > 0 and h0 > 0):
            print(f"{name[:32]:32} {c0:>5} {x0:>5} {'-':>6} {h0:>5}   (no usable Latin reference)")
            continue
        tgt = (c0 + x0) / 2 if x0 else c0 * 0.86
        print(f"{name[:32]:32} {c0:>5} {x0:>5} {x0/c0:6.2f} {h0:>5} {h0/c0:7.2f} "
              f"{tgt:7.0f} {tgt/h0:6.3f}")


if __name__ == "__main__":
    main()
