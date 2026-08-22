#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_diff.py — decisive: byte-diff real letters A vs O vs Hebrew alef to find the TRUE
per-glyph discriminator. If A and O differ only in cp -> this table is a cmap and the
real vector font is elsewhere. Also map +14's meaning across the first table."""
import os, struct
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
d = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
def u16(p): return struct.unpack_from("<H", d, p)[0]
def f32(p): return struct.unpack_from("<f", d, p)[0]
GREC = 64

A = 0x867952   # 'A'
O = 0x867cd2   # 'O'
I = 0x868352   # 'i'
ALEF = 0x87ec92

def show(p, name):
    print(f"  {name} @0x{p:x}: {d[p:p+32].hex(' ')}")
    print(f"  {'':>{len(name)}}  {d[p+32:p+64].hex(' ')}")

print("== full 64B: A, O, i, alef ==")
show(A, "A   ")
show(O, "O   ")
show(I, "i   ")
show(ALEF, "alef")

print("\n== byte-diff A vs O ==")
diffs = [(k, d[A+k], d[O+k]) for k in range(GREC) if d[A+k] != d[O+k]]
for k, a, b in diffs:
    print(f"  +{k}: A={a:#04x} O={b:#04x}")
print(f"  total differing bytes A vs O: {len(diffs)}")

print("\n== byte-diff A vs i ==")
diffs2 = [(k, d[A+k], d[I+k]) for k in range(GREC) if d[A+k] != d[I+k]]
for k, a, b in diffs2:
    print(f"  +{k}: A={a:#04x} i={b:#04x}")
print(f"  total differing bytes A vs i: {len(diffs2)}")

# map +14 across first table (0x866952) for the first 120 records
print("\n== +14 / +16 / cp across first-table records [0..120] ==")
p = 0x866952
prev = None
row = []
for i in range(120):
    q = p + i * GREC
    if u16(q + 20) != 0xf8:
        continue
    cp, v14, v16 = u16(q), u16(q + 14), u16(q + 16)
    ch = chr(cp) if 32 <= cp < 127 else "."
    row.append(f"{ch}:{v14}/{v16 if v16!=0xffff else '-'}")
print("  " + "  ".join(row))
