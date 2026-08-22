#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_trace.py — trace ONE real glyph to its vertices. Dump consecutive records from the
first table, find non-zero float contour spans, and test LZ4 on the high-entropy sections."""
import os, struct
import numpy as np
import lz4.block
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
n = len(d)
def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]
GREC = 64

print("== 24 consecutive 64B records from 0x866952 ==")
for i in range(24):
    p = 0x866952 + i * GREC
    cp = u16(p)
    ch = chr(cp) if 32 <= cp < 127 else ""
    ok = u16(p + 20) == 0xf8 and u16(p + 62) == 0xffff and u16(p + 2) == 0
    print(f"  [{i:2}] @0x{p:x} cp=0x{cp:04x}{ch:>2} +14={u16(p+14):4} +16={u16(p+16):5} +18={u16(p+18):4} "
          f"ok={ok} geom={[round(f32(p+22+4*j),1) for j in range(3)]}")

# find where 'A'..'Z' live: scan the whole file for records with cp 0x41 and +20==0xf8
print("\n== all records with cp in {0x41 'A', 0x4f 'O', 0x69 'i'} (real letters) ==")
for target in (0x41, 0x4f, 0x69):
    hits = []
    for p in range(0x860000, 0x8f0000):
        if u16(p) == target and u16(p + 2) == 0 and u16(p + 20) == 0xf8 and u16(p + 62) == 0xffff:
            hits.append(p)
    for p in hits[:4]:
        print(f"  '{chr(target)}' @0x{p:x} +14={u16(p+14)} +16={u16(p+16)} +18={u16(p+18)} "
              f"geom={[round(f32(p+22+4*j),1) for j in range(6)]}")

# non-zero float spans in 0x860000..0x8b0000 (the '320KB FLOAT' region)
print("\n== non-zero spans in 0x860000..0x8b0000 (candidate contour data) ==")
a = np.frombuffer(d[0x860000:0x8b0000], dtype=np.float32)
nz = np.nonzero((a != 0) & np.isfinite(a) & (np.abs(a) < 1e6))[0]
if len(nz):
    # group into runs
    runs = []
    st = nz[0]
    for k in range(1, len(nz)):
        if nz[k] != nz[k - 1] + 1:
            runs.append((st, nz[k - 1]))
            st = nz[k]
    runs.append((st, nz[-1]))
    big = [(a0, a1) for a0, a1 in runs if a1 - a0 >= 6]
    print(f"  {len(runs)} float runs, {len(big)} with >=7 consecutive nonzero floats")
    for a0, a1 in big[:12]:
        off = 0x860000 + a0 * 4
        vals = [round(float(a[j]), 1) for j in range(a0, min(a1 + 1, a0 + 14))]
        print(f"   @0x{off:x} ({a1-a0+1} floats): {vals}")

# LZ4 test on the compressed sections
print("\n== LZ4 block decompress test on dir[11]/dir[12]/HIENT regions ==")
for name, off, sz in (("dir11", 0x8f43b0, 0x40590), ("dir12", 0x934940, 0x47f90),
                       ("hient_8b0000", 0x8b0000, 0x7800), ("mixed_902000", 0x902000, 0x12800)):
    blk = d[off:off + sz]
    for us in (sz * 3, sz * 6, 2_000_000):
        try:
            out = lz4.block.decompress(blk, uncompressed_size=us)
            print(f"  {name}: LZ4 OK -> {len(out)} bytes  head={out[:20].hex(' ')}")
            break
        except Exception as ex:
            last = str(ex)[:50]
    else:
        print(f"  {name}: LZ4 fail ({last})")
