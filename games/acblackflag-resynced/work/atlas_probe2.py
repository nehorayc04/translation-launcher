# -*- coding: utf-8 -*-
"""Phase 2: locate GFOF magic in every atlas resource, parse the header
that follows it, and dump candidate glyph records."""
import os, sys, struct

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin"))

def f32(b, o): return struct.unpack_from("<f", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def i32(b, o): return struct.unpack_from("<i", b, o)[0]

def show_words(b, start, end, label=""):
    print(f"  -- dwords {label} 0x{start:x}..0x{end:x} --")
    for o in range(start, end, 4):
        v = u32(b, o)
        fv = f32(b, o)
        iv = i32(b, o)
        fs = f"{fv:.6g}" if (abs(fv) > 1e-6 and abs(fv) < 1e9) or fv == 0 else "~"
        print(f"    +0x{o-start:04x} @0x{o:06x}  u32={v:<12} i32={iv:<12} f32={fs:<14} hex={v:08x}")

def main():
    for fn in FILES:
        p = os.path.join(ATLAS, fn)
        data = open(p, "rb").read()
        hits = []
        off = 0
        while True:
            i = data.find(b"GFOF", off)
            if i < 0: break
            hits.append(i); off = i + 1
            if len(hits) > 20: break
        print(f"{fn:26s} size={len(data):>9}  GFOF@{[hex(h) for h in hits]}")
        # also other 4-letter magics near head
        for mg in (b"HXFD", b"FOFG", b"DFXH"):
            j = data.find(mg, 0, 4096)
            if j >= 0: print(f"    {mg.decode()} @0x{j:x}")

    print()
    print("="*100)
    target = sys.argv[1] if len(sys.argv) > 1 else "70970"
    fn = [f for f in FILES if target in f][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    print(f"TARGET {fn}  GFOF@0x{g:x}")
    show_words(data, g, g + 0x90, "post-GFOF header")

if __name__ == "__main__":
    main()
