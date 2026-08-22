#!/usr/bin/env python3
"""FULL parse: a face with count==0 is NOT a terminator, the list continues.
Termination = the next 32 bytes stop looking like a face header.
face header = [u32 count][16B zero][u32 upem in {1000,1024}][u32 0][f32 1.0]
"""
import os, struct, collections, json

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
REC, FH = 36, 32


def is_face_hdr(buf, p):
    if p + FH > len(buf):
        return None
    cnt = struct.unpack_from("<I", buf, p)[0]
    if cnt > 20000:
        return None
    if buf[p + 4:p + 20] != b"\0" * 16:
        return None
    upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
    if upem not in (1000, 1024) or z != 0 or one != 1.0:
        return None
    return cnt, upem


def parse(buf):
    g = buf.find(b"GFOF")
    faces, p = [], g + 36
    while True:
        h = is_face_hdr(buf, p)
        if h is None:
            break
        cnt, upem = h
        recs = [struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)]
        # sanity: codepoints must be plausible, W/H integral & sane
        ok = all(r[0] <= 0x10FFFF and 0 <= r[6] < 4096 and 0 <= r[7] < 4096
                 and r[6] == int(r[6]) and r[7] == int(r[7]) for r in recs)
        if not ok:
            break
        faces.append(dict(off=p, cnt=cnt, upem=upem, recs=recs))
        p += FH + cnt * REC
    return g, faces, p


ranges = [("Latin", 0x20, 0x24F), ("Greek", 0x370, 0x3FF), ("Cyril", 0x400, 0x52F),
          ("HEBREW", 0x590, 0x5FF), ("Arabic", 0x600, 0x6FF), ("ArabSup", 0x750, 0x77F),
          ("Thai", 0xE00, 0xE7F), ("HebPres", 0xFB1D, 0xFB4F), ("ArPresA", 0xFB50, 0xFDFF),
          ("ArPresB", 0xFE70, 0xFEFF), ("CJK", 0x2E80, 0x9FFF), ("Hangul", 0xAC00, 0xD7AF)]

summary = {}
for name in sorted(f for f in os.listdir(D) if f.endswith(".bin")):
    buf = open(os.path.join(D, name), "rb").read()
    g, faces, endp = parse(buf)
    allr = sorted([r for f in faces for r in f["recs"]], key=lambda r: r[8])
    breaks = [(a, b) for a, b in zip(allr, allr[1:]) if a[8] + int(a[6]) * int(a[7]) != b[8]]
    blob0 = g + allr[0][8]
    blobend = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
    cps = collections.Counter(r[0] for r in allr)
    cnt = {n: sum(v for k, v in cps.items() if lo <= k <= hi) for n, lo, hi in ranges}
    print("=" * 100)
    print("%-22s size=%-9d GFOF=0x%-5x faces=%-2d glyphs=%-5d tableEnd=0x%-6x blob=0x%x..0x%x tail=%d breaks=%d"
          % (name, len(buf), g, len(faces), len(allr), endp, blob0, blobend, len(buf) - blobend, len(breaks)))
    print("   faces: %s" % [(f["cnt"], f["upem"]) for f in faces])
    print("   scripts: %s" % {k: v for k, v in cnt.items() if v})
    other = sum(v for k, v in cps.items() if not any(lo <= k <= hi for _, lo, hi in ranges))
    print("   other/unclassified glyphs: %d ; blob bytes = %d ; sum(W*H) = %d"
          % (other, blobend - blob0, sum(int(r[6]) * int(r[7]) for r in allr)))
    summary[name] = dict(glyphs=len(allr), faces=[f["cnt"] for f in faces], scripts={k: v for k, v in cnt.items() if v},
                         tail=len(buf) - blobend, breaks=len(breaks))

json.dump(summary, open(os.path.join(os.path.dirname(D), "synth_full.json"), "w"), indent=1)
print("\nHEBREW total across all 11 files:", sum(s["scripts"].get("HEBREW", 0) + s["scripts"].get("HebPres", 0) for s in summary.values()))
