#!/usr/bin/env python3
"""Cross-check: does the BFR (v50) GFOF model parse the AC SHADOWS (v42) atlas backups?
Tests both record bases and both offset conventions (relative-to-GFOF vs absolute)."""
import os, struct, glob

REC, FH = 36, 32


def is_face_hdr(buf, p):
    if p + FH > len(buf):
        return None
    cnt = struct.unpack_from("<I", buf, p)[0]
    if cnt > 20000 or buf[p + 4:p + 20] != b"\0" * 16:
        return None
    upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
    if upem not in (1000, 1024) or z != 0 or one != 1.0:
        return None
    return cnt, upem


def parse(buf, delta):
    g = buf.find(b"GFOF")
    if g < 0:
        return None, [], 0
    faces, p = [], g + delta
    while True:
        h = is_face_hdr(buf, p)
        if h is None:
            break
        cnt, upem = h
        recs = [struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)]
        if not all(r[0] <= 0x10FFFF and 0 <= r[6] < 4096 and r[6] == int(r[6]) and 0 <= r[7] < 4096 for r in recs):
            break
        faces.append(dict(cnt=cnt, upem=upem, recs=recs))
        p += FH + cnt * REC
    return g, faces, p


for f in sorted(glob.glob(os.path.join(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acshadows\work", "_atlasbak_*.bin"))):
    buf = open(f, "rb").read()
    g = buf.find(b"GFOF")
    print("=" * 96)
    print("%s size=%d GFOF@%s PHXFD@%s" % (os.path.basename(f), len(buf), hex(g) if g >= 0 else None,
                                           hex(buf.find(b"PHXFD"))))
    if g < 0:
        print("   no GFOF -> probably still Oodle/CFD-compressed")
        continue
    print("   GFOF+4..+36:", struct.unpack_from("<I2f5I", buf, g + 4))
    for delta, tag in ((36, "base GFOF+68"), (40, "base GFOF+72")):
        gg, faces, endp = parse(buf, delta)
        if not faces:
            print("   %s -> NO valid faces" % tag)
            continue
        allr = sorted([r for fa in faces for r in fa["recs"]], key=lambda r: r[8])
        breaks = sum(1 for a, b in zip(allr, allr[1:]) if a[8] + int(a[6]) * int(a[7]) != b[8])
        span = sum(int(r[6]) * int(r[7]) for r in allr)
        rel_end = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
        abs_end = allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
        cps = [r[0] for r in allr]
        heb = sum(1 for c in cps if 0x590 <= c <= 0x5FF)
        arab = sum(1 for c in cps if 0x600 <= c <= 0x6FF or 0xFB50 <= c <= 0xFEFF)
        print("   %s: faces=%s glyphs=%d breaks=%d sum(W*H)=%d | REL tail=%d ABS tail=%d | heb=%d arab=%d"
              % (tag, [fa["cnt"] for fa in faces], len(allr), breaks, span,
                 len(buf) - rel_end, len(buf) - abs_end, heb, arab))
