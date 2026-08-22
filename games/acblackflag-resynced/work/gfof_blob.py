# -*- coding: utf-8 -*-
"""Find the base offset of the packed 8-bit glyph-bitmap blob."""
import os, sys, struct
ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
REC, FMT = 36, "<7f2I"

def load(sel):
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    n = struct.unpack_from("<I", data, g + 0x24)[0]
    tbl = g + 0x48
    recs = [struct.unpack_from(FMT, data, tbl + i * REC) for i in range(n)]
    return fn, data, g, n, tbl, tbl + n * REC, recs

def score_base(data, recs, B, sample):
    """Score candidate blob base B. Good base => glyph bitmaps look like AA coverage:
    lots of 0s, a decent number of high values, and blank glyphs are blank."""
    tot = 0.0
    for i in sample:
        adv, x0, y0, x1, y1, w, h, bo, cp = recs[i]
        w, h = int(w), int(h)
        if w == 0 or h == 0: continue
        s, e = B + bo, B + bo + w * h
        if e > len(data) or s < 0: return -1e9
        px = data[s:e]
        z = px.count(0) / len(px)
        hi = sum(1 for c in px if c > 200) / len(px)
        # AA glyph: 20-80% zeros, meaningful high-ink fraction
        tot += (1.0 if 0.05 < z < 0.85 else -1.0) + (1.0 if hi > 0.03 else -0.5)
        # border rows should be mostly empty-ish for a tight box? skip
    return tot

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else "70970"
    fn, data, g, n, tbl, tblEnd, recs = load(sel)
    print(f"{fn} n={n} tbl=0x{tbl:x} tblEnd=0x{tblEnd:x} size=0x{len(data):x}")
    print(f"first boff={recs[0][7]}  last reach={recs[-1][7]+int(recs[-1][5])*int(recs[-1][6])}")
    reach = max(r[7] + int(r[5]) * int(r[6]) for r in recs)
    print(f"max reach={reach}  => base if blob ends at EOF: {len(data)-reach} (0x{len(data)-reach:x})")
    print(f"   base if blob starts at tblEnd: {tblEnd} (0x{tblEnd:x}) -> end {tblEnd+reach} = 0x{tblEnd+reach:x}")

    # constraint: find blank (all-zero) glyph boxes -> they pin the base
    blanks = [(i, r) for i, r in enumerate(recs)
              if int(r[5]) * int(r[6]) >= 200 and r[8] in (32, 0xA0, 0x3000)]
    print(f"space-like recs: {[(i, hex(r[8]), int(r[5]), int(r[6]), r[7]) for i, r in blanks][:5]}")

    sample = list(range(0, n, max(1, n // 40)))[:40]
    cands = []
    # coarse scan over the whole plausible base range
    lo, hi = tblEnd, len(data) - reach
    print(f"scanning bases {lo}..{hi}")
    best = []
    step = 1
    for B in range(max(0, lo), hi + 1, step):
        s = score_base(data, recs, B, sample)
        best.append((s, B))
    best.sort(reverse=True)
    print("top candidate bases:")
    for s, B in best[:10]:
        print(f"   B={B} (0x{B:x})  score={s:.1f}   blobEnd={B+reach} (0x{B+reach:x}) tail={len(data)-B-reach}")

if __name__ == "__main__":
    main()
