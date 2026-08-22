#!/usr/bin/env python3
"""Map the regions of a PHXFD atlas that the GFOF record table does NOT explain:
the gap between the record table and the first raster, and the tail after the last raster."""
import os, sys, struct, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES, blockname


def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())


def regions():
    for n in FILES:
        d = load(n)
        hdr, recs = parse(d)
        srt = sorted(recs, key=lambda r: r["tex"])
        first = srt[0]["tex"]
        last = max(r["tex"] + int(round(r["w"]))*int(round(r["h"])) for r in recs)
        gap = d[hdr["rec_end"]:first]
        tail = d[last:]
        # more GFOF / PHXFD occurrences?
        gfofs, i = [], -1
        while True:
            i = d.find(b"GFOF", i+1)
            if i < 0: break
            gfofs.append(i)
        phx, i = [], -1
        while True:
            i = d.find(b"PHXFD", i+1)
            if i < 0: break
            phx.append(i)
        print(f"\n=== {n} ({len(d):,}) ===")
        print(f"  GFOF magics @ {[hex(x) for x in gfofs]}   PHXFD magics @ {[hex(x) for x in phx]}")
        print(f"  REGION A header+recs 0x0..0x{hdr['rec_end']:x}")
        print(f"  REGION B gap  0x{hdr['rec_end']:x}..0x{first:x}  ({len(gap):,} B)  "
              f"entropy={ent(gap):.3f}  /count={len(gap)/hdr['count']:.3f} B/glyph  zero%={100*gap.count(0)/max(1,len(gap)):.1f}")
        print(f"     head: {gap[:48].hex()}")
        print(f"  REGION C rasters 0x{first:x}..0x{last:x} ({last-first:,} B) entropy={ent(d[first:last][:2_000_000]):.3f}")
        print(f"  REGION D tail 0x{last:x}..0x{len(d):x} ({len(tail):,} B) entropy={ent(tail[:2_000_000]):.3f} "
              f"zero%={100*tail.count(0)/max(1,len(tail)):.1f}")
        print(f"     head: {tail[:64].hex()}")
        print(f"     tail-of-tail: {tail[-48:].hex()}")
        # is the tail a second raster blob of the same total size?
        print(f"     tail/sum(W*H) = {len(tail)/max(1,sum(int(round(r['w']))*int(round(r['h'])) for r in recs)):.4f}")


def gap_struct(name="70970_88c902b3.bin"):
    """Try to read region B as a table."""
    d = load(name); hdr, recs = parse(d)
    srt = sorted(recs, key=lambda r: r["tex"])
    g0, g1 = hdr["rec_end"], srt[0]["tex"]
    gap = d[g0:g1]
    cnt = hdr["count"]
    print(f"{name}: gap {len(gap)} B, glyphCount={cnt}")
    for w in (2, 4, 8, 12, 16):
        q, r = divmod(len(gap), w)
        print(f"   as {w}-byte units: {q} units rem {r}   ({q/cnt:.4f} per glyph)")
    print("   first 8 u32:", [hex(x) for x in struct.unpack_from("<8I", gap, 0)])
    print("   first 16 u16:", [hex(x) for x in struct.unpack_from("<16H", gap, 0)])
    # are u16s sorted codepoints?
    u16 = struct.unpack_from(f"<{len(gap)//2}H", gap, 0)
    inc = sum(1 for a, b in zip(u16, u16[1:]) if b >= a)
    print(f"   u16 monotonic-nondecreasing fraction: {inc/(len(u16)-1):.3f}")
    u32 = struct.unpack_from(f"<{len(gap)//4}I", gap, 0)
    inc32 = sum(1 for a, b in zip(u32, u32[1:]) if b >= a)
    print(f"   u32 monotonic-nondecreasing fraction: {inc32/(len(u32)-1):.3f}")
    print(f"   u32 max={max(u32):#x}  values < glyphCount: {sum(1 for x in u32 if x < cnt)}/{len(u32)}")
    # kerning-pair guess: pairs of (u16 cp, u16 cp, f32)
    cps = set(r["cp"] for r in recs)
    hit = sum(1 for i in range(0, len(gap)-8, 8)
              if struct.unpack_from("<H", gap, i)[0] in cps and struct.unpack_from("<H", gap, i+2)[0] in cps)
    print(f"   8-byte stride, both u16 are known codepoints: {hit}/{len(gap)//8}")
    hit4 = sum(1 for i in range(0, len(gap)-4, 4)
               if struct.unpack_from("<H", gap, i)[0] in cps and struct.unpack_from("<H", gap, i+2)[0] in cps)
    print(f"   4-byte stride, both u16 are known codepoints: {hit4}/{len(gap)//4}")
    print("   hexdump first 160 B:")
    for o in range(0, 160, 16):
        print(f"     +{o:04x}: {gap[o:o+16].hex()}")


def tail_struct(name="70970_88c902b3.bin"):
    d = load(name); hdr, recs = parse(d)
    last = max(r["tex"] + int(round(r["w"]))*int(round(r["h"])) for r in recs)
    tail = d[last:]
    print(f"{name}: tail {len(tail):,} B @0x{last:x}")
    for o in range(0, 256, 16):
        print(f"   +{o:04x}: {tail[o:o+16].hex()}  {''.join(chr(b) if 32<=b<127 else '.' for b in tail[o:o+16])}")
    # entropy profile across the tail
    W = 4096
    prof = [ent(tail[i:i+W]) for i in range(0, min(len(tail), 400*W), W)]
    print(f"   tail entropy windows: min={min(prof):.3f} med={sorted(prof)[len(prof)//2]:.3f} max={max(prof):.3f}")
    # does the tail look like a half-res copy? compare to sum(w*h)/4
    s = sum(int(round(r['w']))*int(round(r['h'])) for r in recs)
    print(f"   sum(W*H)={s:,}  /4={s//4:,}  /2={s//2:,}  tail={len(tail):,}")
    # is the tail actually a SECOND GFOF-like record set? search for float patterns
    print(f"   u32 at tail+0..8: {struct.unpack_from('<2I', tail, 0)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = sys.argv[1] if len(sys.argv) > 1 else "regions"
    {"regions": regions, "gap": gap_struct, "tail": tail_struct}[c](*sys.argv[2:])
