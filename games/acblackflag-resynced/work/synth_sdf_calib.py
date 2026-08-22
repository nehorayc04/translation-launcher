#!/usr/bin/env python3
"""Calibrate the SDF encoding so Hebrew glyphs can be authored to match.
Tests: (1) is the edge value 128?  -> the first column/row with value>=T must sit ~pad px
from the bitmap border, since bbox = ink + pad on every side.
(2) what is the ramp slope (value units per pixel)?  -> mode of |delta| along rows.
"""
import os, struct, collections

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
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
        faces.append([struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)])
        p += FH + cnt * REC
    return g, faces


for fn, label in (("70970_88c902b3.bin", "ARABIC w0"), ("16243_88c2952a.bin", "LATIN w0")):
    buf = open(os.path.join(D, fn), "rb").read()
    g, faces = parse(buf)
    recs = [r for f in faces for r in f]
    print("=" * 96)
    print(label, fn)
    for T in (100, 110, 120, 128, 136, 144):
        margins = []
        for r in recs[:400]:
            cp, adv, x0, y0, x1, y1, W, H, off = r
            W, H = int(W), int(H)
            if W < 12 or H < 12:
                continue
            bm = buf[g + off:g + off + W * H]
            cols = [x for x in range(W) if any(bm[y * W + x] >= T for y in range(H))]
            rows = [y for y in range(H) if any(bm[y * W + x] >= T for x in range(W))]
            if not cols or not rows:
                continue
            margins += [cols[0], W - 1 - cols[-1], rows[0], H - 1 - rows[-1]]
        c = collections.Counter(margins)
        print("   threshold=%3d -> ink margin from bitmap edge: mode=%s  mean=%.2f  (expect ~8 = pad)"
              % (T, c.most_common(3), sum(margins) / len(margins)))
    # ramp slope
    dc = collections.Counter()
    for r in recs[:300]:
        cp, adv, x0, y0, x1, y1, W, H, off = r
        W, H = int(W), int(H)
        if W < 12:
            continue
        bm = buf[g + off:g + off + W * H]
        for y in range(0, H, 3):
            row = bm[y * W:(y + 1) * W]
            for a, b in zip(row, row[1:]):
                if a and b:
                    dc[abs(a - b)] += 1
    print("   |delta| between adjacent nonzero px: %s" % dc.most_common(8))
    vals = collections.Counter()
    for r in recs[:300]:
        cp, adv, x0, y0, x1, y1, W, H, off = r
        bm = buf[g + off:g + off + int(W) * int(H)]
        vals.update(bm)
    top = vals.most_common(10)
    print("   most common byte values: %s" % top)
    print("   max byte value seen: %d ; odd-value share: %.2f%%"
          % (max(vals), 100 * sum(v for k, v in vals.items() if k % 2) / sum(vals.values())))
    # metrics sanity: does W == ceil(x1-x0) and is ink box = W-2*pad?
    ex = [r for r in recs if r[0] == 0x41 or r[0] == 0x627 or r[0] == 0x645][:3]
    for cp, adv, x0, y0, x1, y1, W, H, off in ex:
        print("   U+%04X adv=%.2f bbox=(%.2f,%.2f,%.2f,%.2f) W=%d H=%d  x1-x0=%.2f y1-y0=%.2f  ink=%.1fx%.1f"
              % (cp, adv, x0, y0, x1, y1, W, H, x1 - x0, y1 - y0, x1 - x0 - 16, y1 - y0 - 16))
