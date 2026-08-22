#!/usr/bin/env python3
"""Characterise the two unexplained regions: (a) table-end..blob-start gap, (b) blob-end..EOF tail."""
import os, struct, math, collections

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
REC, FACE_HDR = 36, 32


def faces_at(buf, g):
    faces, p = [], g + 36
    while True:
        cnt, z0, z1, z2, z3, upem, z4, one = struct.unpack_from("<8I", buf, p)
        if cnt == 0 or cnt > 20000 or (z0 | z1 | z2 | z3 | z4) != 0:
            return faces, p
        faces.append([struct.unpack_from("<I7fI", buf, p + FACE_HDR + i * REC) for i in range(cnt)])
        p = p + FACE_HDR + cnt * REC


def ent(b):
    if not b:
        return 0
    c = collections.Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


for name in sorted(f for f in os.listdir(D) if f.endswith(".bin")):
    buf = open(os.path.join(D, name), "rb").read()
    g = buf.find(b"GFOF")
    faces, endp = faces_at(buf, g)
    allr = sorted([r for f in faces for r in f], key=lambda r: r[8])
    blob0 = g + allr[0][8]
    blobend = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
    gap = buf[endp:blob0]
    tail = buf[blobend:]
    print("%-22s gap=%-7d tail=%-9d | gapEnt=%.2f gapZero=%.0f%% | tailEnt=%.2f tailZero=%.0f%% tailEven=%.0f%%"
          % (name, len(gap), len(tail), ent(gap[:65536]), 100 * gap[:65536].count(0) / max(1, len(gap[:65536])),
             ent(tail[:65536]), 100 * tail[:65536].count(0) / max(1, len(tail[:65536])),
             100 * sum(1 for b in tail[:65536] if b % 2 == 0) / max(1, len(tail[:65536]))))
    if len(tail) > 64:
        print("      tail head: %s" % tail[:64].hex())
        print("      tail  end: %s" % tail[-32:].hex())
    if len(gap) > 64:
        print("      gap  head: %s" % gap[:64].hex())

a = open(os.path.join(D, "70971_88c902b5.bin"), "rb").read()
b = open(os.path.join(D, "70972_88c902b1.bin"), "rb").read()
print("\n70971 vs 70972 tails identical? ", a[-1165079:] == b[-1165079:])
print("70971 tail all-zero? ", a[-1165079:].count(0) == 1165079)
c = open(os.path.join(D, "16243_88c2952a.bin"), "rb").read()
print("16243 tail all-zero? ", c[-1337995:].count(0) == 1337995)
