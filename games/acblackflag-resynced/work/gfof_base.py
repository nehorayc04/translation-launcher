# -*- coding: utf-8 -*-
"""Pin the blob base using a shape prior that IS sensitive to a raster shift:
a tightly-boxed antialiased glyph has LOW mean coverage on its border rows/cols
(partial pixel coverage), while a raster-shifted decode drops bright interior
pixels onto the border."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_faces import walk, rd, ATLAS, REC

RAMP = " .:-=+*#%@"

def border_score(px, w, h):
    c0 = sum(px[y*w] for y in range(h)) / h
    c1 = sum(px[y*w + w - 1] for y in range(h)) / h
    r0 = sum(px[0:w]) / w
    r1 = sum(px[(h-1)*w:h*w]) / w
    return c0 + c1 + r0 + r1

def art(px, w, h, maxw=70):
    step = max(1, (w + maxw - 1)//maxw)
    return "\n".join("".join(RAMP[min(9, px[y*w+x]*10//256)] for x in range(0, w, step))
                     for y in range(0, h, step*2))

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else "70970"
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    faces = walk(data, g + 0x48)
    reach = faces[-1]["reach"]; firstbo = faces[0]["first_bo"]; lastend = faces[-1]["rec_end"]
    lo, hi = max(0, lastend - firstbo), len(data) - reach
    print(f"{fn}: faces={len(faces)} lastRecEnd=0x{lastend:x} firstbo={firstbo} reach={reach} "
          f"size={len(data)} -> base range [{lo},{hi}]")

    sample = []
    for f in faces:
        for i in range(0, f["n"], max(1, f["n"]//10)):
            r = rd(data, f["rec_start"] + i*REC)
            if 8 <= int(r[5]) <= 200 and 8 <= int(r[6]) <= 200:
                sample.append(r)
    sample = sample[:60]
    res = []
    for B in range(lo, hi+1):
        tot, ok = 0.0, True
        for r in sample:
            w, h, bo = int(r[5]), int(r[6]), r[7]
            s = B + bo
            if s + w*h > len(data): ok = False; break
            tot += border_score(data[s:s+w*h], w, h)
        if ok: res.append((tot/len(sample), B))
    res.sort()
    print("border-ink score (LOW = correct alignment):")
    for sc, B in res[:8]:
        print(f"   base={B:>4} (0x{B:x})  score={sc:8.2f}")
    print(f"   ... worst: base={res[-1][1]} score={res[-1][0]:.2f}")
    B = res[0][1]
    print(f"\n>>> BLOB BASE = {B} (0x{B:x})  blobStart=0x{B+firstbo:x}  blobEnd=0x{B+reach:x}  "
          f"EOF=0x{len(data):x}  trailingPad={len(data)-B-reach}")

    want = [int(x, 0) for x in sys.argv[2:]] or [0x41, 0x2E, 0x4F]
    print("\n--- renders ---")
    shown = 0
    for fi, f in enumerate(faces):
        for i in range(f["n"]):
            r = rd(data, f["rec_start"] + i*REC)
            if r[8] in want and int(r[5]) > 4:
                w, h, bo = int(r[5]), int(r[6]), r[7]
                print(f"\nface{fi} U+{r[8]:04X} {w}x{h} adv={r[0]:.2f} "
                      f"box=({r[1]:.2f},{r[2]:.2f})-({r[3]:.2f},{r[4]:.2f}) bo={bo}")
                print(art(data[B+bo:B+bo+w*h], w, h))
                shown += 1
    if not shown:
        r = rd(data, faces[0]["rec_start"])
        w, h, bo = int(r[5]), int(r[6]), r[7]
        print(f"\nface0 glyph0 U+{r[8]:04X} {w}x{h}")
        print(art(data[B+bo:B+bo+w*h], w, h))

if __name__ == "__main__":
    main()
