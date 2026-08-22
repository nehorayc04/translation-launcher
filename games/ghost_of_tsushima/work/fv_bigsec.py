#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_bigsec.py — dump/classify the two big sections (dir[11] kind3 @0x8f43b0, dir[12]
kind18 @0x934940) + follow header tables @0xb8/@0x250, hunting the FontVerts vertex buffer
and the per-glyph descriptor table that (+14,+16,+18) indexes."""
import os, struct
import numpy as np
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
n = len(d)
def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]
def hexdump(base, nb=96):
    for i in range(0, nb, 16):
        c = d[base + i:base + i + 16]
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
        print(f"    {base+i:08x}  {c.hex(' ')}  {asc}")

for label, off, sz in (("dir11 kind3", 0x8f43b0, 0x40590), ("dir12 kind18", 0x934940, 0x47f90)):
    print(f"\n===== {label} @0x{off:x} size=0x{sz:x} ({sz}B) =====")
    hexdump(off, 128)
    # entropy
    import math, collections
    win = d[off:off + min(sz, 65536)]
    h = collections.Counter(win)
    ent = -sum((c / len(win)) * math.log2(c / len(win)) for c in h.values())
    print(f"    entropy={ent:.2f} bit/byte")
    # as i16 stats
    arr = np.frombuffer(d[off:off + (sz // 2) * 2], dtype=np.int16)
    print(f"    i16: min={arr.min()} max={arr.max()} mean={arr.mean():.1f} "
          f"frac|x|<1024={(np.abs(arr) < 1024).mean():.2f} zeros={(arr==0).mean():.2f}")
    a32 = np.frombuffer(d[off:off + (sz // 4) * 4], dtype=np.float32)
    fin = a32[np.isfinite(a32)]
    small = np.abs(fin) < 4000
    print(f"    f32: frac finite&|x|<4000={small.mean():.2f}  sample={[round(float(x),2) for x in a32[:8]]}")

# ---- @0xb8: parse as u32 array to find pointers/sizes
print("\n===== @0xb8 as u32[0..40] =====")
for i in range(0, 40, 4):
    p = 0xb8 + i * 4
    print(f"  @0x{p:x}: {u32(p)} {u32(p+4)} {u32(p+8)} {u32(p+12)}")

# ---- @0x250: [count][.. ][0x8f3d28]  -> follow 0x8f3d28
print("\n===== follow @0x250 -> 0x8f3d28 (64B) =====")
hexdump(0x8f3d28, 64)

# ---- The glyph records' +14 indexes SOMETHING with up to 602 entries.
#      Search for a table of >=602 fixed-stride entries near the glyph tables / sections.
#      Candidate strides 4,6,8,12,16. Look for a region of ascending or structured u16.
print("\n===== hunt: a table with >=550 entries that +14 (0..602) could index =====")
# dir[0]@0x8eefa0 looked like [0,cp] pairs (u16). Let's dump more of dir[0..4] as u16 pairs.
for di, (of, sz) in enumerate([(0x8eefa0,0x14b0),(0x8f0450,0x14a0),(0x8f18f0,0xeb0)]):
    print(f"\n  dir[{di}] @0x{of:x}: first 24 u16-pairs:")
    pairs = [(u16(of+4*j), u16(of+4*j+2)) for j in range(24)]
    print("   ", pairs)

# ---- KEY: correlate. Hebrew glyphs use +16=1522. Arabic 1680/1690/1693.
#      If +16 indexes dir[11] (kind3) as 24B stride: entry@ off+1522*24
print("\n===== test +16 as index into dir[11]/dir[12] (various strides) =====")
for base_off, base_name in ((0x8f43b0, "dir11"), (0x934940, "dir12")):
    for stride in (4, 8, 12, 16, 24, 32):
        for idx, nm in ((1522, "HEB"), (1680, "AR062a")):
            tp = base_off + idx * stride
            if tp + 16 <= n:
                pass
    # just dump dir11 @ +1522*stride for a couple strides
print("  dir11 @ +1522*24 =", hex(0x8f43b0 + 1522*24), "(would be", hex(0x8f43b0+1522*24), "vs sec end", hex(0x8f43b0+0x40590), ")")
