# -*- coding: utf-8 -*-
"""Pin the glyph-bitmap blob base by total-variation minimisation, then render."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_faces import walk, rd, ATLAS, REC

RAMP = " .:-=+*#%@"

def tv(px, w, h):
    """total variation of an 8-bit image; a wrong base creates a wrap seam."""
    t = 0
    for y in range(h):
        row = px[y*w:(y+1)*w]
        for x in range(w-1):
            t += abs(row[x+1]-row[x])
    for y in range(h-1):
        a = px[y*w:(y+1)*w]; b = px[(y+1)*w:(y+2)*w]
        for x in range(w):
            t += abs(b[x]-a[x])
    return t

def art(px, w, h, maxw=64):
    step = max(1, (w + maxw - 1)//maxw)
    out = []
    for y in range(0, h, step*2):
        line = ""
        for x in range(0, w, step):
            v = px[y*w+x]
            line += RAMP[min(9, v*10//256)]
        out.append(line)
    return "\n".join(out)

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else "70970"
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    faces = walk(data, g + 0x48)
    reach = faces[-1]["reach"]
    firstbo = faces[0]["first_bo"]
    lastend = faces[-1]["rec_end"]
    loB = max(0, lastend - firstbo)
    hiB = len(data) - reach
    print(f"{fn}: base range [{loB}, {hiB}]")

    # sample glyphs from several faces
    sample = []
    for f in faces:
        for i in range(0, f["n"], max(1, f["n"]//6)):
            r = rd(data, f["rec_start"] + i*REC)
            if int(r[5]) >= 8 and int(r[6]) >= 8 and int(r[5])*int(r[6]) < 20000:
                sample.append(r)
        if len(sample) > 25: break
    sample = sample[:25]

    scores = []
    for B in range(loB, hiB+1):
        t = 0
        ok = True
        for r in sample:
            w, h, bo = int(r[5]), int(r[6]), r[7]
            s = B + bo
            if s + w*h > len(data): ok = False; break
            t += tv(data[s:s+w*h], w, h)
        if ok: scores.append((t, B))
    scores.sort()
    print("lowest total-variation bases (best first):")
    for t, B in scores[:6]:
        print(f"   base={B} (0x{B:x})  TV={t}")
    print(f"   worst: base={scores[-1][1]} TV={scores[-1][0]}")
    B = scores[0][1]
    print(f"\n>>> BLOB BASE = {B} (0x{B:x});  blob spans 0x{B+firstbo:x} .. 0x{B+reach:x}; "
          f"EOF=0x{len(data):x} pad={len(data)-B-reach}")

    print("\n--- sample renders (face0 first 2, plus latin face) ---")
    todo = [(0, 0), (0, 1), (0, 2)]
    if len(faces) > 2:
        todo += [(2, i) for i in range(3)]
    for fi, gi in todo:
        if fi >= len(faces) or gi >= faces[fi]["n"]: continue
        r = rd(data, faces[fi]["rec_start"] + gi*REC)
        w, h, bo, cp = int(r[5]), int(r[6]), r[7], r[8]
        if w == 0 or h == 0: continue
        px = data[B+bo:B+bo+w*h]
        print(f"\nface{fi} glyph{gi}  U+{cp:04X}  {w}x{h}  adv={r[0]:.2f} box=({r[1]:.2f},{r[2]:.2f})-({r[3]:.2f},{r[4]:.2f}) bo={bo}")
        print(art(px, w, h))

if __name__ == "__main__":
    main()
