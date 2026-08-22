#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_outline.py — locate + decode the external outline buffer in ghost_title.xpps.
Follows the 0x8f3xxx offset lead + tests whether (+16) indexes a fixed-stride descriptor
table that in turn points to vertex data. Read-only on the cached bin."""
import os, sys, struct
import numpy as np

CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
GT = os.path.join(CACHE, "ghost_title.bin")
GREC = 64
d = open(GT, "rb").read()
n = len(d)


def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]


def hexdump(base, nb=64):
    for i in range(0, nb, 16):
        c = d[base + i:base + i + 16]
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
        print(f"  {base+i:08x}  {c.hex(' ')}  {asc}")


print(f"file {n:#x}. trailer@0x2c -> 0x{u32(0x2c):x}")

# 1) Dump where the 0x8f3xxx offsets point
print("\n== region @0x8f3d00..0x8f3e80 (offset targets) ==")
hexdump(0x8f3d00, 0x180)

# 2) Trailer / directory @0x9a2750
print("\n== trailer @0x9a2750 (128 B) ==")
hexdump(0x9a2750, 128)

# 3) Section directory: header @0x18=0xb8, @0x1c=0x198, @0x28=0x250, @0x2c=0x9a2750
print("\n== header pointer fields ==")
for off in (0x08, 0x0c, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c):
    v = u32(off)
    print(f"  @0x{off:02x} = {v} (0x{v:x})")

# dump the little tables the header points at
for label, off in (("@0xb8", 0xb8), ("@0x198", 0x198), ("@0x250", 0x250)):
    print(f"\n== {label} (96 B) ==")
    hexdump(off, 96)

# 4) TEST: does +16 index a fixed-stride table? Find the record region span, then
#    look for a 24-byte-stride table whose entry count ~ max(+16)=4577.
#    First: collect (cp, +14, +16, +18) for a few known glyphs.
print("\n== hypothesis test: +16 -> descriptor table ==")
# Hebrew alef ref = (104,1522,11); Arabic 062a=(129,1680,3), 062c=(129,1690,0)
# If descriptors are 24B stride starting at T: entry k @ T + k*24.
# We saw offsets 0x8f3d18,0x8f3d30,0x8f3d48 (stride 0x18). Solve T for some k.
# Try: assume the pointer 0x8f3d18 corresponds to some index; find T by scanning.
# Simpler: scan 0x8ae000..0x9a2750 for a run of u32 that look like ascending file offsets.
print("\n== scan for ascending-u32 pointer tables in 0x8ae000..0x9a2740 ==")
lo, hi = 0x8ae000, 0x9a2740
best = []
p = lo
while p < hi - 4:
    v = u32(p)
    if lo - 0x100000 <= v < n:   # plausible in-file offset
        # try to extend a run where consecutive u32 (stride 4) are ascending & in-file
        run = [v]
        q = p + 4
        while q < hi - 4:
            w = u32(q)
            if run[-1] <= w < n and w - run[-1] < 0x8000:
                run.append(w); q += 4
            else:
                break
        if len(run) >= 32:
            best.append((p, q, len(run)))
            p = q
            continue
    p += 4
for a, b2, ln in best[:20]:
    print(f"  ptr-run @0x{a:x}..0x{b2:x} len={ln} first={u32(a):#x} last={u32(b2-4):#x} stride~{(u32(a+4)-u32(a))}")

# 5) The pre-table records (@0x8668xx) had u32 at +6 in 0x8f3xxx with stride 0x18.
#    Re-parse them as an ALT record layout to see structure.
print("\n== alt-record scan: 64B records whose u32@+6 is an in-file offset (stride hint 0x18) ==")
cnt = 0
firsts = []
for p in range(0x860000, 0x867000, 4):
    v = u32(p + 6)
    if 0x8ae000 <= v < 0x9a2750 and u16(p + 20) == 0xf8 and u16(p + 62) == 0xffff:
        firsts.append((p, v))
        cnt += 1
print(f"  found {cnt} such records in 0x860000..0x867000; first 8:")
for p, v in firsts[:8]:
    print(f"    @0x{p:x} cp=0x{u16(p):x} +6ptr=0x{v:x} +14={u16(p+14)} +16={u16(p+16)} +18={u16(p+18)}")
    print(f"       full: {d[p:p+32].hex(' ')}")
    print(f"             {d[p+32:p+64].hex(' ')}")
