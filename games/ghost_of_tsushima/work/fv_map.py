#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_map.py — classify every 2KB block of the ghost_title tail (0x860000..EOF) to find
where the vertex/outline data lives and whether it is compressed. Also probe the
unaccounted gap 0x8aec92..0x8eefa0 (between glyph tables and section dir)."""
import os, struct, math, collections, zlib
import numpy as np
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
n = len(d)
def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]


def classify(off, w=2048):
    seg = d[off:off + w]
    if not seg:
        return "EOF", 0
    h = collections.Counter(seg)
    ent = -sum((c / len(seg)) * math.log2(c / len(seg)) for c in h.values())
    zeros = seg.count(0) / len(seg)
    if zeros > 0.85:
        return "ZERO", ent
    if ent > 7.3:
        return "HIENT", ent      # compressed/encrypted/texture
    # glyph records? stride-64 with +20==0xf8 & +62==0xffff
    lim = min(off + w, n - 64)
    gr = sum(1 for p in range(off, lim, 64)
             if u16(p + 20) == 0xf8 and u16(p + 62) == 0xffff and u16(p + 2) == 0)
    if gr >= w // 64 - 4:
        return "GLYPH", ent
    # vertex floats? fraction of f32 in glyph em-space
    a = np.frombuffer(seg[:(w // 4) * 4], dtype=np.float32)
    fin = np.isfinite(a)
    small = fin & (np.abs(a) < 4000)
    if small.mean() > 0.80:
        return "FLOAT", ent
    # i16 vertex coords?
    ai = np.frombuffer(seg[:(w // 2) * 2], dtype=np.int16)
    if (np.abs(ai) < 2048).mean() > 0.85 and (ai == 0).mean() < 0.5:
        return "I16", ent
    # pointer-ish: many u32 in file range
    pc = sum(1 for p in range(off, off + w - 4, 8) if 0x800000 <= u32(p) < n)
    if pc > (w // 8) * 0.5:
        return "PTR", ent
    return "MIXED", ent


print(f"file {n:#x}. mapping 0x860000..EOF in 2KB blocks:")
off = 0x860000
runs = []
while off < n:
    k, ent = classify(off)
    if runs and runs[-1][2] == k:
        runs[-1][1] = off + 2048
    else:
        runs.append([off, off + 2048, k, ent])
    off += 2048
for a, b, k, ent in runs:
    print(f"  0x{a:x}..0x{b:x} ({(b-a)//1024:>4}KB) {k:6} ent~{ent:.1f}")

# ---- probe the gap 0x8aec92..0x8eefa0 in detail
print("\n== gap 0x8aec92..0x8eefa0 head (past glyph tables, before section dir) ==")
for base in (0x8aec92, 0x8aed00, 0x8b0000, 0x8c0000, 0x8d0000, 0x8e0000, 0x8ee000):
    seg = d[base:base + 32]
    asc = "".join(chr(x) if 32 <= x < 127 else "." for x in seg)
    a = np.frombuffer(d[base:base + 32], dtype=np.int16)
    print(f"  @0x{base:x}: {seg.hex(' ')}  {asc}")
    print(f"          i16: {a.tolist()}")

# ---- try zlib-decompressing at HIENT starts (78 9c / 78 da / 78 01)
print("\n== zlib probe over the tail (look for 78 9c/da/01 stream starts) ==")
for i in range(0x860000, n - 2):
    if d[i] == 0x78 and d[i + 1] in (0x9c, 0xda, 0x01):
        try:
            dec = zlib.decompressobj()
            out = dec.decompress(d[i:i + 200000], 400000)
            if len(out) > 2000:
                print(f"  @0x{i:x}: zlib -> {len(out)} bytes  head={out[:24].hex(' ')}")
        except Exception:
            pass
