#!/usr/bin/env python3
"""Account for the bytes AFTER the first GFOF blob: are there more GFOF/PHXFD blocks?"""
import os, struct, collections

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
FILES = sorted(f for f in os.listdir(D) if f.endswith(".bin"))
REC, FACE_HDR = 36, 32


def faces_at(buf, g):
    faces, p = [], g + 36
    while p + FACE_HDR <= len(buf):
        cnt, z0, z1, z2, z3, upem, z4, one = struct.unpack_from("<8I", buf, p)
        if cnt == 0 or cnt > 20000 or (z0 | z1 | z2 | z3 | z4) != 0:
            break
        recs = [struct.unpack_from("<I7fI", buf, p + FACE_HDR + i * REC) for i in range(cnt)]
        faces.append(recs)
        p = p + FACE_HDR + cnt * REC
    return faces, p


for name in FILES:
    buf = open(os.path.join(D, name), "rb").read()
    gs = []
    i = buf.find(b"GFOF")
    while i != -1:
        gs.append(i)
        i = buf.find(b"GFOF", i + 1)
    ps = []
    i = buf.find(b"PHXFD")
    while i != -1:
        ps.append(i)
        i = buf.find(b"PHXFD", i + 1)
    print("=" * 92)
    print("%s  size=%d  GFOF@%s  PHXFD@%s" % (name, len(buf), [hex(x) for x in gs], [hex(x) for x in ps]))
    covered = 0
    allcps = collections.Counter()
    for g in gs:
        faces, endp = faces_at(buf, g)
        if not faces:
            print("   GFOF@0x%x -> no faces" % g)
            continue
        allr = sorted([r for f in faces for r in f], key=lambda r: r[8])
        breaks = sum(1 for a, b in zip(allr, allr[1:]) if a[8] + int(a[6]) * int(a[7]) != b[8])
        blob0 = g + allr[0][8]
        blobend = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
        for r in allr:
            allcps[r[0]] += 1
        covered += blobend - g
        print("   GFOF@0x%-6x faces=%-28s glyphs=%-5d breaks=%d  tbl:0x%x-0x%x blob:0x%x-0x%x  (next GFOF/EOF gap=%d)"
              % (g, [len(f) for f in faces], len(allr), breaks, g + 36, endp, blob0, blobend,
                 (gs[gs.index(g) + 1] if gs.index(g) + 1 < len(gs) else len(buf)) - blobend))
    heb = sum(v for k, v in allcps.items() if 0x0590 <= k <= 0x05FF or 0xFB1D <= k <= 0xFB4F)
    print("   TOTAL distinct cps=%d  HEBREW(incl FB1D-FB4F)=%d" % (len(allcps), heb))
