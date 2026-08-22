#!/usr/bin/env python3
"""Close out: (a) what the repeating 4-char ASCII runs really are, (b) BC7 plausibility."""
import os, sys, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES, ATLAS

AR = "70970_88c902b3.bin"


def runs():
    d = load(AR)
    hdr, recs = parse(d)
    first = min(r["tex"] for r in recs)
    # Take ONE known glyph's raster and show that the "runs" are inside it.
    r = max((x for x in recs if x["cp"] == 0x645), key=lambda x: x["w"] * x["h"], default=None) \
        or sorted(recs, key=lambda x: -x["w"] * x["h"])[0]
    w, h = int(round(r["w"])), int(round(r["h"]))
    buf = d[r["tex"]:r["tex"] + w * h]
    print(f"glyph U+{r['cp']:04X} W={w} H={h} @0x{r['tex']:x}")
    print("  byte-value histogram of THIS glyph (top 12):",
          collections.Counter(buf).most_common(12))
    # find the printable-ASCII runs inside this single glyph
    found = []
    i = 0
    while i < len(buf):
        j = i
        while j + 1 < len(buf) and buf[j + 1] == buf[i]:
            j += 1
        L = j - i + 1
        if L >= 4 and 32 <= buf[i] < 127:
            found.append((i, chr(buf[i]), L, i % w, i // w))
        i = j + 1
    print(f"  printable-ASCII runs >=4 INSIDE this one glyph: {len(found)}")
    for f in found[:10]:
        print(f"    off {f[0]:6d} byte '{f[1]}' x{f[2]:<4d}  -> pixel (x={f[3]}, y={f[4]})")
    print("  => the runs are flat SPANS OF PIXELS inside a glyph, not text.\n")

    # global: which byte values form long runs, and are they on an even/16 lattice?
    reg = d[first:first + 3_000_000]
    hist = collections.Counter()
    i = 0
    while i < len(reg):
        j = i
        while j + 1 < len(reg) and reg[j + 1] == reg[i]:
            j += 1
        if j - i + 1 >= 4:
            hist[reg[i]] += 1
        i = j + 1
    print("  run-forming byte values across the raster region (top 20):")
    for b, c in hist.most_common(20):
        ch = chr(b) if 32 <= b < 127 else "."
        print(f"    0x{b:02x} '{ch}'  runs={c:6d}   even={b%2==0}  mult16={b%16==0}")
    even = sum(c for b, c in hist.items() if b % 2 == 0)
    print(f"  runs on EVEN byte values: {even}/{sum(hist.values())} "
          f"({100*even/sum(hist.values()):.1f}%)")

    # overall byte histogram of the raster region -> SDF quantization
    bh = collections.Counter(reg)
    ev = sum(v for k, v in bh.items() if k % 2 == 0)
    print(f"\n  raster-region byte histogram: EVEN values = {100*ev/len(reg):.2f}% of bytes "
          f"(random would be 50%)")
    print(f"  distinct values used: {len(bh)}/256; top 10: {bh.most_common(10)}")
    lattice = collections.Counter(k % 16 for k in reg)
    print(f"  value mod 16 distribution: {sorted(lattice.items())[:16]}")


def bc7():
    print("\n\n=== BC7 / block-compressed-texture plausibility ===")
    print("BC7 & BC3 = 16 B per 4x4 block = 1.00 B/px; BC1/BC4 = 0.50 B/px.")
    print("A BCn surface must be a whole number of 4x4 blocks and a power-of-two-ish surface.\n")
    for n in FILES:
        d = load(n)
        hdr, recs = parse(d)
        first = min(r["tex"] for r in recs)
        payload = len(d) - first
        print(f"{n}: payload after tables = {payload:,} B")
        for w in (512, 1024, 2048, 4096, 8192):
            for bpp, kind in ((1.0, "BC7"), (0.5, "BC1")):
                nomip = w * w * bpp
                mip = 0
                s = w
                while s >= 1:
                    mip += s * s * bpp
                    s //= 2
                for need, tag in ((nomip, "no-mip"), (mip, "+mips")):
                    if need and abs(payload - need) / need < 0.02:
                        print(f"    !! MATCH {kind} {w}x{w} {tag} = {int(need):,}")
        # decisive: the parsed model already explains it exactly
        px = sum(int(round(r["w"])) * int(round(r["h"])) for r in recs)
        print(f"    parsed stream-A model: sum(W*H) = {px:,} B, "
              f"and raster span = {max(r['tex']+int(round(r['w']))*int(round(r['h'])) for r in recs)-first:,} B "
              f"-> ratio {px/max(1,(max(r['tex']+int(round(r['w']))*int(round(r['h'])) for r in recs)-first)):.6f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs()
    bc7()
