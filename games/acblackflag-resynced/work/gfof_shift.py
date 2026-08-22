# -*- coding: utf-8 -*-
"""Decide the record field alignment: does the codepoint dword sit BEFORE the
metrics (record = cp,adv,x0,y0,x1,y1,w,h,boff) or AFTER them?
Test: pair each bitmap with cp[i] vs cp[i-1] and see which gives sane ASCII."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_faces import walk, rd, ATLAS, REC

RAMP = " .:-=+*#%@"
def art(px, w, h, maxw=60):
    step = max(1, (w + maxw - 1)//maxw)
    return "\n".join("".join(RAMP[min(9, px[y*w+x]*10//256)] for x in range(0, w, step))
                     for y in range(0, h, step*2))

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else "70970"
    shift = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    faces = walk(data, g + 0x48)
    B = g  # blob base == GFOF offset (proved)
    f = [x for x in faces if x["n"] > 200][-1]
    recs = [rd(data, f["rec_start"] + i*REC) for i in range(f["n"])]
    print(f"{fn} face rec@0x{f['rec_start']:x} n={f['n']}  cp shift={shift}")
    print(f"{'cp':>6} {'ch':2} {'w':>4} {'h':>4} {'adv':>7} {'inkW':>7}")
    rows = []
    for i, r in enumerate(recs):
        j = i - shift
        if j < 0 or j >= len(recs): continue
        cp = recs[j][8]
        if not (0x20 <= cp < 0x7F): continue
        adv, x0, y0, x1, y1, w, h, bo, _ = r
        rows.append((cp, int(w), int(h), adv, (x1 - x0) - 2*(-x0)))
    rows.sort()
    for cp, w, h, adv, ink in rows:
        print(f"U+{cp:04X} {chr(cp):2} {w:>4} {h:>4} {adv:>7.2f} {ink:>7.2f}")
    # renders of distinctive chars
    want = [0x2E, 0x49, 0x57, 0x41, 0x4F]
    for i, r in enumerate(recs):
        j = i - shift
        if j < 0: continue
        cp = recs[j][8]
        if cp in want and int(r[5]) > 3:
            w, h, bo = int(r[5]), int(r[6]), r[7]
            print(f"\n== U+{cp:04X} '{chr(cp)}' {w}x{h} adv={r[0]:.2f} ==")
            print(art(data[B+bo:B+bo+w*h], w, h))

if __name__ == "__main__":
    main()
