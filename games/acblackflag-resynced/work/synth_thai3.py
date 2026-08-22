#!/usr/bin/env python3
"""Third-party reference file (Thai mod, engine-accepted, REBUILT + GROWN):
 (a) do the outer-header size relations hold the way they do in vanilla?  -> how to fix them when we grow
 (b) are its 52 Hebrew glyphs real Hebrew shapes?                          -> render one
 (c) what order are records in, and what does its face header look like?
"""
import os, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "atlas")
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


for tag, fn in (("VANILLA-latin", "16243_88c2952a.bin"), ("THAI-latin", "TH_88c2952a.bin"),
                ("VANILLA-arabic", "70970_88c902b3.bin")):
    buf = open(os.path.join(D, fn), "rb").read()
    ver, fid, ftype, dsize = struct.unpack_from("<IIII", buf, 0)[0], None, None, None
    v = struct.unpack_from("<H", buf, 0)[0]
    fid = struct.unpack_from("<I", buf, 2)[0]
    ftype = struct.unpack_from("<I", buf, 6)[0]
    dsize = struct.unpack_from("<I", buf, 10)[0]
    ch, recsize, namelen = struct.unpack_from("<III", buf, 0x14)
    nend = 0x20 + namelen
    inner = struct.unpack_from("<I", buf, nend + 51)[0]
    print("=" * 96)
    print("%-15s size=%-9d ver=%d fileID=%08x type=%d dataSize=%d (size-20=%d %s)"
          % (tag, len(buf), v, fid, ftype, dsize, len(buf) - 20, "OK" if dsize == len(buf) - 20 else "MISMATCH"))
    print("   classHash=%08x recSize=%d nameLen=%d  -> 0x21+nameLen+recSize=%d %s"
          % (ch, recsize, namelen, 0x21 + namelen + recsize, "OK" if 0x21 + namelen + recsize == len(buf) else "MISMATCH"))
    print("   innerSize@nend+51=%d -> (nend+55)+inner=%d vs size-24=%d %s"
          % (inner, nend + 55 + inner, len(buf) - 24, "OK" if nend + 55 + inner == len(buf) - 24 else "MISMATCH"))
    g, faces = parse(buf)
    print("   GFOF@0x%x faces=%s ; face0 hdr bytes=%s"
          % (g, [(f["cnt"], f["upem"]) for f in faces], buf[faces[0]["off"]:faces[0]["off"] + FH].hex()))
    recs = faces[0]["recs"]
    hs = [int(r[7]) for r in recs]
    print("   face0 record order: sorted-by-H-desc=%s ; sorted-by-cp=%s ; first cps=%s"
          % (all(a >= b for a, b in zip(hs, hs[1:])),
             all(recs[i][0] <= recs[i + 1][0] for i in range(len(recs) - 1)),
             [hex(r[0]) for r in recs[:6]]))

buf = open(os.path.join(D, "TH_88c2952a.bin"), "rb").read()
g, faces = parse(buf)
allr = [r for f in faces for r in f["recs"]]
heb = sorted([r for r in allr if 0x0590 <= r[0] <= 0x05FF], key=lambda r: r[0])
print("\nTHAI file Hebrew codepoints (%d): %s" % (len(heb), [hex(r[0]) for r in heb]))
ramp = " .:-=+*#%@"
for r in heb:
    if r[0] in (0x05D0, 0x05DE, 0x05E9):
        cp, adv, x0, y0, x1, y1, W, H, off = r
        W, H = int(W), int(H)
        bm = buf[g + off:g + off + W * H]
        print("\nU+%04X adv=%.2f bbox=(%.2f,%.2f,%.2f,%.2f) W=%d H=%d" % (cp, adv, x0, y0, x1, y1, W, H))
        for y in range(0, H, max(1, H // 22)):
            print("   |" + "".join(ramp[min(9, bm[y * W + x] * 10 // 256)] for x in range(W)) + "|")
