#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_sections.py — parse the @0x198 section directory + test whether the glyph
reference fields (+14 section, +16 offset, +18 count) resolve into a vertex/outline
section. Read-only on cached bin."""
import os, sys, struct
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
n = len(d)


def u16(p): return struct.unpack_from("<H", d, p)[0]
def u32(p): return struct.unpack_from("<I", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]
def i16(p): return struct.unpack_from("<h", d, p)[0]


def hexdump(base, nb=48):
    for i in range(0, nb, 16):
        c = d[base + i:base + i + 16]
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
        print(f"    {base+i:08x}  {c.hex(' ')}  {asc}")


# ---- parse @0x198 as 12-byte entries while offset in-file & size sane
print("== @0x198 section directory (12-byte entries [u16 flag][u16 kind][u32 size][u32 off]) ==")
p = 0x198
entries = []
while p + 12 <= 0x8000:
    flag, kind = u16(p), u16(p + 2)
    size, off = u32(p + 4), u32(p + 8)
    if flag != 0x10 or off == 0 or off >= n or size > n:
        break
    entries.append((flag, kind, size, off))
    p += 12
print(f"  {len(entries)} entries, dir 0x198..0x{p:x}")
for i, (fl, k, sz, of) in enumerate(entries):
    tag = ""
    if i in (104, 129, 130, 143, 0, 1, 2):
        tag = " <--"
    print(f"  [{i:3}] kind={k:2} size=0x{sz:<6x} off=0x{of:x}{tag}")
    if i > 40 and i not in (104, 129, 130, 143):
        pass

# how many entries total? try extending the loop bound
print(f"\n  (entry count = {len(entries)}; max +14 seen among glyphs was 602)")

# ---- if +14 indexes this dir, entry 104 = Hebrew's section
print("\n== resolve Hebrew (+14=104) & Arabic (+14=129,130) sections ==")
for idx in (104, 129, 130, 143):
    if idx < len(entries):
        fl, k, sz, of = entries[idx]
        print(f"\n  dir[{idx}] kind={k} size=0x{sz:x} off=0x{of:x}:")
        hexdump(of, 96)
    else:
        print(f"  dir[{idx}] OUT OF RANGE (dir has {len(entries)} entries)")

# ---- @0xb8 table (u64 pairs) + @0x250
print("\n== @0xb8 region (parse as records) ==")
hexdump(0xb8, 96)
print("\n== @0x250 region ==")
hexdump(0x250, 48)

# ---- The @0x198 offsets (0x8exxxx) - dump the FIRST section (dir[0]) as floats/ints
if entries:
    fl, k, sz, of = entries[0]
    print(f"\n== dir[0] kind={k} @0x{of:x} size=0x{sz:x} — as u16/f32 ==")
    hexdump(of, 64)
    print("   as i16[:16]:", [i16(of + 2 * j) for j in range(16)])
    print("   as f32[:8] :", [round(f32(of + 4 * j), 3) for j in range(8)])
