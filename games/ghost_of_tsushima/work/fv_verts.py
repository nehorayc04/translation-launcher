#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_verts.py — find the record->vertex link. Dump full 64B records for real Latin
letters (first table @0x866952), examine EVERY field, and inspect the low-entropy FLOAT
regions (0x860000.., 0x8b7800..) as candidate outline vertices."""
import os, struct
import numpy as np
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
n = len(d)
def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]
GREC = 64


def full_rec(p, label):
    print(f"\n  {label} @0x{p:x} cp=0x{u16(p):x}")
    print(f"    bytes: {d[p:p+32].hex(' ')}")
    print(f"           {d[p+32:p+64].hex(' ')}")
    # every 2-byte and 4-byte field
    print(f"    u16@ +0={u16(p)} +2={u16(p+2)} +4={u16(p+4)} +6={u16(p+6)} +8={u16(p+8)} "
          f"+10={u16(p+10)} +12={u16(p+12)} +14={u16(p+14)} +16={u16(p+16)} +18={u16(p+18)}")
    print(f"    u32@ +4={u32(p+4)} +6={u32(p+6)} +8={u32(p+8)} +10={u32(p+10)}")
    print(f"    f32@ +4={f32(p+4):.4f}  geom+22: {[round(f32(p+22+4*j),2) for j in range(6)]}")


# ---- first table @0x866952: build cp->offset
s = 0x866952
cp2off = {}
q = s
while q + GREC <= n and u16(q + 2) == 0 and u16(q + 62) == 0xffff and u16(q + 20) == 0xf8:
    c = u16(q)
    if c == 0xffff:
        break
    if cp2off and c <= max(cp2off):
        break
    cp2off[c] = q
    q += GREC
print(f"first table @0x{s:x}: {len(cp2off)} records cp[0x{min(cp2off):x}..0x{max(cp2off):x}]")
for c in (0x20, 0x21, 0x2e, 0x41, 0x42, 0x4f, 0x69, 0x6c, 0x6d):
    if c in cp2off:
        full_rec(cp2off[c], f"'{chr(c)}' U+{c:04X}")

# ---- dump the FLOAT region 0x860000..0x866952 (before the table) as coordinate pairs
print("\n== float region 0x860000..0x866952 (before first table) as f32 pairs ==")
for base in (0x860000, 0x860040, 0x861000, 0x865000, 0x866900):
    fs = [round(f32(base + 4 * j), 2) for j in range(12)]
    print(f"  @0x{base:x}: {fs}")

# ---- dump 0x8b7800 float region
print("\n== float region 0x8b7800.. as f32 pairs ==")
for base in (0x8b7800, 0x8b8000, 0x8c0000):
    fs = [round(f32(base + 4 * j), 2) for j in range(12)]
    print(f"  @0x{base:x}: {fs}")

# ---- Is there a per-glyph vertex-span table? Look right AFTER the last glyph table,
#      and at the region 0x8ec800..0x8f1000 (FLOAT) which might be metrics/spans.
print("\n== 0x8ec800.. (FLOAT, candidate spans/metrics) as u32 quads ==")
for base in range(0x8ec800, 0x8ed000, 16):
    print(f"  @0x{base:x}: {u32(base)} {u32(base+4)} {u32(base+8)} {u32(base+12)}   "
          f"f: {[round(f32(base+4*j),2) for j in range(4)]}")

# ---- correlation attempt: Hebrew +16=1522. Interpret regions as arrays indexed by +16.
#      dir[4] kind1 @0x8f3080 size 0x7e0=2016 -> /? entries. Print as u16.
print("\n== dir[4] @0x8f3080 (size 0x7e0) as u16[:40] ==")
print("  ", [u16(0x8f3080 + 2 * j) for j in range(40)])
