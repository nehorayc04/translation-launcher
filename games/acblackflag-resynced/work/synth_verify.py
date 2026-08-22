#!/usr/bin/env python3
"""Independent re-verification of the GFOF/PHXFD atlas format claims.

Resolves the contradictions between the four investigation reports:
  1. glyph record base = GFOF+68 (codepoint first)  vs  GFOF+72 (codepoint last)
  2. "3334 = fixed table capacity"                  vs  "3334 = constant field, per-face counts"
  3. payload = 8-bit alpha coverage                 vs  8-bit SDF
Everything is checked arithmetically over all 11 cached .bin files.
"""
import os, struct, json, collections

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
FILES = sorted(f for f in os.listdir(D) if f.endswith(".bin"))

REC = 36
FACE_HDR = 32


def parse(buf, rec_base_delta):
    """Parse the face chain. rec_base_delta = offset of first face header from GFOF."""
    g = buf.find(b"GFOF")
    faces = []
    p = g + rec_base_delta
    while True:
        if p + FACE_HDR > len(buf):
            return g, faces, p, "ran off end"
        cnt, z0, z1, z2, z3, upem, z4, one = struct.unpack_from("<8I", buf, p)
        onef = struct.unpack_from("<f", buf, p + 28)[0]
        if cnt == 0 or cnt > 20000 or (z0 | z1 | z2 | z3 | z4) != 0:
            return g, faces, p, ("terminator cnt=%d" % cnt)
        recs = []
        rp = p + FACE_HDR
        for i in range(cnt):
            f = struct.unpack_from("<I7fI", buf, rp + i * REC)
            recs.append(f)
        faces.append(dict(hdr=p, cnt=cnt, upem=upem, one=onef, recs=recs))
        p = rp + cnt * REC


def chain_check(g, faces, size):
    """Verify offset[i+1] == offset[i] + W*H over the concatenation of all faces."""
    allr = [r for f in faces for r in f["recs"]]
    allr.sort(key=lambda r: r[8])
    bad = 0
    for a, b in zip(allr, allr[1:]):
        if a[8] + int(a[6]) * int(a[7]) != b[8]:
            bad += 1
    last = allr[-1]
    end = g + last[8] + int(last[6]) * int(last[7])
    return bad, len(allr), g + allr[0][8], end, size - end


print("=" * 100)
print("A) DECIDE THE RECORD BASE:  GFOF+68 (codepoint-first) vs GFOF+72 (codepoint-last)")
print("=" * 100)
for name in FILES:
    buf = open(os.path.join(D, name), "rb").read()
    row = [name]
    for delta, tag in ((36, "+68"), (40, "+72")):
        g, faces, endp, why = parse(buf, delta)
        if not faces:
            row.append("%s: NO FACES (%s)" % (tag, why))
            continue
        bad, n, blob0, blobend, tail = chain_check(g, faces, len(buf))
        cps = [r[0] for f in faces for r in f["recs"]]
        sane = sum(1 for c in cps if 0x20 <= c <= 0x10FFFF)
        row.append("%s: faces=%d glyphs=%d chainbreaks=%d tail=%d saneCP=%d/%d" %
                   (tag, len(faces), n, bad, tail, sane, len(cps)))
    print(row[0])
    for r in row[1:]:
        print("      ", r)

print()
print("=" * 100)
print("B) FULL MAP @ base GFOF+68 : per-file faces, scripts, Hebrew count, closure")
print("=" * 100)
SUM = {}
for name in FILES:
    buf = open(os.path.join(D, name), "rb").read()
    g, faces, endp, why = parse(buf, 36)
    bad, n, blob0, blobend, tail = chain_check(g, faces, len(buf))
    cps = [r[0] for f in faces for r in f["recs"]]
    heb = sum(1 for c in cps if 0x0590 <= c <= 0x05FF or 0xFB1D <= c <= 0xFB4F)
    arab = sum(1 for c in cps if 0x0600 <= c <= 0x06FF)
    presA = sum(1 for c in cps if 0xFB50 <= c <= 0xFDFF)
    presB = sum(1 for c in cps if 0xFE70 <= c <= 0xFEFF)
    lat = sum(1 for c in cps if c < 0x0250)
    cjk = sum(1 for c in cps if 0x3000 <= c <= 0x9FFF)
    han = sum(1 for c in cps if 0xAC00 <= c <= 0xD7AF)
    hdr = struct.unpack_from("<I2f5I", buf, g + 4)
    SUM[name] = dict(gfof=g, faces=[f["cnt"] for f in faces], glyphs=n, heb=heb)
    print("%-22s GFOF=0x%-6x hdrconst=%d  asc=%.4f desc=%.4f px=%d %d %.2f pad=%d,%d" %
          (name, g, hdr[0], hdr[1], hdr[2], hdr[3], hdr[4], struct.unpack_from("<f", buf, g + 0x18)[0], hdr[6], hdr[7]))
    print("      faces=%s total=%d breaks=%d blobEnd->EOF tail=%d | HEB=%d arab=%d presA=%d presB=%d lat=%d cjk=%d hangul=%d"
          % ([f["cnt"] for f in faces], n, bad, tail, heb, arab, presA, presB, lat, cjk, han))
    print("      face upem/one: %s  | terminator@0x%x = %s" %
          ([(f["upem"], round(f["one"], 3)) for f in faces],
           endp, struct.unpack_from("<8I", buf, endp) if endp + 32 <= len(buf) else "n/a"))

print()
print("=" * 100)
print("C) SDF vs COVERAGE  (70970 face0, glyph U+0645 + 16243 'A')")
print("=" * 100)


def dump(name, want_cp, render=True):
    buf = open(os.path.join(D, name), "rb").read()
    g, faces, endp, why = parse(buf, 36)
    for fi, f in enumerate(faces):
        for r in f["recs"]:
            if r[0] == want_cp:
                cp, adv, x0, y0, x1, y1, W, H, off = r
                W, H = int(W), int(H)
                bm = buf[g + off: g + off + W * H]
                hist = collections.Counter(bm)
                print("%s U+%04X face%d W=%d H=%d adv=%.3f bbox=(%.2f,%.2f,%.2f,%.2f) off=0x%x" %
                      (name, cp, fi, W, H, adv, x0, y0, x1, y1, off))
                print("   distinct=%d  zeros=%.1f%%  255s=%.1f%%  even=%.1f%%  min=%d max=%d" %
                      (len(hist), 100 * hist[0] / len(bm), 100 * hist[255] / len(bm),
                       100 * sum(v for k, v in hist.items() if k % 2 == 0) / len(bm),
                       min(bm), max(bm)))
                # corner value: SDF -> a constant low floor / 0; coverage -> 0
                print("   corners=%s  center=%d" % ([bm[0], bm[W - 1], bm[(H - 1) * W], bm[-1]],
                                                    bm[(H // 2) * W + W // 2]))
                mid = H // 2
                row = bm[mid * W:(mid + 1) * W]
                print("   mid row: %s" % list(row))
                if render:
                    ramp = " .:-=+*#%@"
                    for y in range(0, H, max(1, H // 28)):
                        print("      |" + "".join(ramp[min(9, bm[y * W + x] * 10 // 256)] for x in range(W)) + "|")
                return
    print("%s: U+%04X not found" % (name, want_cp))


dump("70970_88c902b3.bin", 0x0645)
print()
dump("16243_88c2952a.bin", 0x0041)

print()
print("=" * 100)
print("D) DONOR CANDIDATES in 70970 face0 (rare Arabic Presentation Forms, biggest boxes)")
print("=" * 100)
buf = open(os.path.join(D, "70970_88c902b3.bin"), "rb").read()
g, faces, endp, why = parse(buf, 36)
f0 = faces[0]
cands = [(int(r[6]) * int(r[7]), int(r[6]), int(r[7]), r[0]) for r in f0["recs"]
         if 0xFB50 <= r[0] <= 0xFDFF]
cands.sort(reverse=True)
print("face0 records=%d ; presA donors=%d ; top 40 by area:" % (f0["cnt"], len(cands)))
for a, W, H, cp in cands[:40]:
    print("   U+%04X  %3dx%-3d = %6d B" % (cp, W, H, a))
areas = [c[0] for c in cands]
print("median presA area=%d ; how many presA >= 40x40=1600B: %d" %
      (sorted(areas)[len(areas) // 2], sum(1 for a in areas if a >= 1600)))

# what do the REAL Arabic letters look like, size-wise (the target visual size)?
base = [(int(r[6]), int(r[7]), r[0], r[1]) for r in f0["recs"] if 0x0620 <= r[0] <= 0x064A]
base.sort(key=lambda t: -t[0] * t[1])
print("\nreference: base-Arabic letters W x H (top 12): %s" % [(hex(c), w, h) for w, h, c, a in base[:12]])
print("json dumped")
json.dump({k: v for k, v in SUM.items()}, open(os.path.join(os.path.dirname(D), "synth_summary.json"), "w"), indent=1)
