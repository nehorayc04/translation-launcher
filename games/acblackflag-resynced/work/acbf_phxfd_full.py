#!/usr/bin/env python3
"""Full PHXFD layout: main GFOF table (stream A) + the grouped secondary tables (stream B),
and proof that stream B's records tile the tail exactly.

Stream B group:
    u32[4] zeros
    u32 unitsPerEm (1000)
    u32 ?          (0)
    f32 scale      (1.0)
    u32 arrayBytes           <-- record array length in bytes (= 36 * K)
    K x 36-byte record       <-- same record shape as GFOF: 7 f32 + u32 tex + u32 codepoint
"""
import os, sys, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES, blockname

REC = 36
HDR = 32


def parse_groups(d, start, end):
    groups = []
    o = start
    while o + HDR <= end:
        z = struct.unpack_from("<4I", d, o)
        upem, u1, scale, nbytes = struct.unpack_from("<IIfI", d, o + 16)
        if nbytes % REC or nbytes == 0 or o + HDR + nbytes > end:
            return groups, o, f"bad group @0x{o:x}: zeros={z} upem={upem} nbytes={nbytes}"
        recs = []
        for k in range(nbytes // REC):
            ro = o + HDR + REC * k
            m = struct.unpack_from("<7f", d, ro)
            tex, cp = struct.unpack_from("<II", d, ro + 28)
            recs.append(dict(adv=m[0], xmin=m[1], ymin=m[2], xmax=m[3], ymax=m[4],
                             w=m[5], h=m[6], tex=tex, cp=cp, o=ro))
        groups.append(dict(o=o, upem=upem, u1=u1, scale=scale, n=nbytes // REC,
                           zeros=z, recs=recs))
        o += HDR + nbytes
    return groups, o, None


def main():
    for n in FILES:
        d = load(n)
        hdrA, recsA = parse(d)
        firstA = min(r["tex"] for r in recsA)
        lastA = max(r["tex"] + int(round(r["w"])) * int(round(r["h"])) for r in recsA)
        groups, endo, err = parse_groups(d, hdrA["rec_end"], firstA)
        allB = [r for g in groups for r in g["recs"]]
        print(f"\n=== {n} ({len(d):,} B) ===")
        print(f"  stream A: {hdrA['count']} glyphs, table 0x{hdrA['rec_start']:x}..0x{hdrA['rec_end']:x}, "
              f"raster 0x{firstA:x}..0x{lastA:x}")
        print(f"  stream B: {len(groups)} groups / {len(allB)} glyphs, table 0x{hdrA['rec_end']:x}..0x{endo:x} "
              f"(target 0x{firstA:x}, leftover {firstA-endo} B){'  ERR=' + err if err else ''}")
        if not allB:
            continue
        sizes = collections.Counter(g["n"] for g in groups)
        print(f"  group sizes (glyphs per group): {sizes.most_common(8)}")
        upems = collections.Counter(g["upem"] for g in groups)
        scales = collections.Counter(round(g["scale"], 4) for g in groups)
        print(f"  upem values: {dict(upems)}   scale values: {dict(scales)}")
        srt = sorted(allB, key=lambda r: r["tex"])
        gaps = collections.Counter()
        for a, b in zip(srt, srt[1:]):
            gaps[b["tex"] - (a["tex"] + int(round(a["w"])) * int(round(a["h"])))] += 1
        firstB = srt[0]["tex"]
        lastB = max(r["tex"] + int(round(r["w"])) * int(round(r["h"])) for r in allB)
        print(f"  stream B raster 0x{firstB:x}..0x{lastB:x}   "
              f"(A ends 0x{lastA:x}; B starts exactly there: {firstB == lastA})")
        print(f"  B tiling gap histogram: {gaps.most_common(5)}")
        print(f"  file end 0x{len(d):x}  bytes after B raster: {len(d)-lastB}")
        blocks = collections.Counter(blockname(r["cp"]) for r in allB)
        print(f"  B codepoint blocks: " + ", ".join(f"{k}={v}" for k, v in blocks.most_common(6)))
        hebA = [r for r in recsA if 0x590 <= r["cp"] <= 0x5FF]
        hebB = [r for r in allB if 0x590 <= r["cp"] <= 0x5FF]
        print(f"  HEBREW: streamA={len(hebA)}  streamB={len(hebB)}")
        # total accounting
        pxA = sum(int(round(r["w"])) * int(round(r["h"])) for r in recsA)
        pxB = sum(int(round(r["w"])) * int(round(r["h"])) for r in allB)
        acc = firstA + pxA + pxB
        print(f"  ACCOUNTING: header+tables 0x{firstA:x}({firstA}) + rasterA {pxA:,} + rasterB {pxB:,} "
              f"= {acc:,}   filelen {len(d):,}   unexplained {len(d)-acc}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
