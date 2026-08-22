#!/usr/bin/env python3
"""Which loose AvenirNextWorld TTF was each atlas face baked from?
Compare atlas advance (px, at pixel size 40) against ttf advance*40/upem."""
import os, struct, glob
from fontTools.ttLib import TTFont

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
FDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "refmods", "he_fonts")
REC, FH = 36, 32


def parse(buf):
    g = buf.find(b"GFOF")
    faces, p = [], g + 36
    while True:
        cnt = struct.unpack_from("<I", buf, p)[0]
        if cnt > 20000 or buf[p + 4:p + 20] != b"\0" * 16:
            break
        upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
        if upem not in (1000, 1024) or z or one != 1.0:
            break
        faces.append(dict(off=p, cnt=cnt, upem=upem,
                          recs=[struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)]))
        p += FH + cnt * REC
    return g, faces


fonts = {}
for fp in sorted(glob.glob(os.path.join(FDIR, "*.ttf"))):
    f = TTFont(fp, lazy=True)
    cmap = f.getBestCmap()
    hm = f["hmtx"].metrics
    upem = f["head"].unitsPerEm
    fonts[os.path.basename(fp)] = (cmap, hm, upem, f)

HEB = list(range(0x05D0, 0x05EB))
for fn in ("16243_88c2952a.bin", "16245_88c2952b.bin", "16248_88c2952c.bin", "70970_88c902b3.bin"):
    buf = open(os.path.join(D, fn), "rb").read()
    g, faces = parse(buf)
    for fi, fa in enumerate(faces):
        cps = {r[0]: r for r in fa["recs"]}
        test = [c for c in (0x41, 0x42, 0x45, 0x4D, 0x57, 0x61, 0x65, 0x6D, 0x77, 0x30, 0x35) if c in cps]
        if len(test) < 8:
            continue
        best = []
        for name, (cmap, hm, upem, _) in fonts.items():
            errs = []
            for c in test:
                if c not in cmap:
                    continue
                adv_px = hm[cmap[c]][0] * 40.0 / upem
                errs.append(abs(adv_px - cps[c][1]))
            if errs:
                best.append((sum(errs) / len(errs), name))
        best.sort()
        print("%-22s face%d n=%-5d -> %s" % (fn, fi, fa["cnt"],
              "  ".join("%s:%.3f" % (n, e) for e, n in best[:3])))

# does the family carry Hebrew, and at what advances?
name = "AvenirNextWorld-Regular.ttf"
cmap, hm, upem, f = fonts[name]
have = [c for c in HEB if c in cmap]
print("\n%s: Hebrew coverage %d/27 ; upem=%d" % (name, len(have), upem))
print("   alef adv=%.2fpx  bet=%.2fpx  mem=%.2fpx (at px=40)"
      % (hm[cmap[0x05D0]][0] * 40 / upem, hm[cmap[0x05D1]][0] * 40 / upem, hm[cmap[0x05DE]][0] * 40 / upem))
gs = f.getGlyphSet()
from fontTools.pens.boundsPen import BoundsPen
for cp in (0x05D0, 0x05DE, 0x0041, 0x0627):
    if cp in cmap:
        bp = BoundsPen(gs)
        gs[cmap[cp]].draw(bp)
        if bp.bounds:
            x0, y0, x1, y1 = [v * 40.0 / upem for v in bp.bounds]
            print("   U+%04X ink px bbox = (%.2f,%.2f,%.2f,%.2f)  w=%.2f h=%.2f" % (cp, x0, y0, x1, y1, x1 - x0, y1 - y0))
