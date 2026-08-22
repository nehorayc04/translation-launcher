#!/usr/bin/env python3
"""Brute-force the AC Shadows record array: which base offset + field layout makes the
W*H offset chain close? Layout A = [cp,adv,x0,y0,x1,y1,W,H,off]; Layout B = [adv..H,off,cp]."""
import os, struct, glob

REC = 36


def try_base(buf, base, n, layout):
    recs = []
    for i in range(n):
        o = base + i * REC
        if o + REC > len(buf):
            return None
        if layout == "A":
            cp = struct.unpack_from("<I", buf, o)[0]
            adv, x0, y0, x1, y1, W, H = struct.unpack_from("<7f", buf, o + 4)
            off = struct.unpack_from("<I", buf, o + 32)[0]
        else:
            adv, x0, y0, x1, y1, W, H = struct.unpack_from("<7f", buf, o)
            off, cp = struct.unpack_from("<2I", buf, o + 28)
        if not (0 <= W < 4096 and 0 <= H < 4096 and W == int(W) and H == int(H) and cp <= 0x10FFFF):
            return None
        recs.append((cp, int(W), int(H), off))
    ok = sum(1 for a, b in zip(recs, recs[1:]) if a[3] + a[1] * a[2] == b[3])
    return ok, recs


for f in sorted(glob.glob(os.path.join(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acshadows\work", "_atlasbak_*.bin")))[:3]:
    buf = open(f, "rb").read()
    g = buf.find(b"GFOF")
    print("=" * 90)
    print(os.path.basename(f), "size", len(buf), "GFOF@", hex(g))
    print("  GFOF+4 dump:", [hex(x) for x in struct.unpack_from("<20I", buf, g + 4)])
    best = []
    for base in range(g + 32, g + 200, 4):
        for layout in ("A", "B"):
            r = try_base(buf, base, 30, layout)
            if r and r[0] >= 25:
                best.append((r[0], base - g, layout, r[1][:3]))
    for b in sorted(best, reverse=True)[:6]:
        print("   chain-ok=%d/29  base=GFOF+%d layout=%s  first3=%s" % b)
