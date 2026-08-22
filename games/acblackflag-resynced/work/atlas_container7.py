# -*- coding: utf-8 -*-
"""Phase 7: walk the secondary block chain; locate the true base of the glyph-data offsets."""
import sys, os, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = [("16243",0x88c2952a),("16245",0x88c2952b),("16248",0x88c2952c),
         ("19498",0x88cf5a5b),("19499",0x8b21454b),("19500",0x88cf5a5c),
         ("70970",0x88c902b3),("70971",0x88c902b5),("70972",0x88c902b1),
         ("70973",0x88cab006),("70974",0x88c902b0)]
data = {}
for n, f in FILES:
    data[n] = open(os.path.join(D, f"{n}_{f:08x}.bin"), "rb").read()
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def f32(b,o): return struct.unpack_from("<f",b,o)[0]
def hx(b): return " ".join(f"{x:02x}" for x in b)

print("=" * 108)
print("A) WALK the block chain: [u32 count][28B hdr][count x 36B records], starting at GFOF+32")
print("=" * 108)
BASE = {}
for n, _ in FILES:
    b = data[n]; g = b.find(b"GFOF"); size = len(b)
    print(f"\n  {n} (size 0x{size:x}) GFOF@0x{g:x}")
    p = g + 0x24              # the count field of block 0
    blocks = []
    for bi in range(24):
        if p + 32 > size: break
        cnt = u32(b, p)
        mark1000 = u32(b, p + 20)
        onef = u32(b, p + 28)
        rec0 = p + 32
        if mark1000 != 1000 or onef != 0x3f800000:
            print(f"    block{bi}: HDR MISMATCH at 0x{p:x} (u32@+20={mark1000} u32@+28=0x{onef:08x}) -> stop")
            break
        end = rec0 + 36 * cnt
        cps = [u16(b, rec0 + 36*i) for i in range(min(cnt, 4))]
        offs = [u32(b, rec0 + 36*i + 32) for i in range(cnt)] if cnt else []
        print(f"    block{bi}: hdr@0x{p:06x} count={cnt:<6d} recs@0x{rec0:06x}..0x{end:06x} "
              f"firstCPs={[f'U+{c:04X}' for c in cps]} "
              f"offRange={(min(offs),max(offs)) if offs else '-'}")
        blocks.append((p, cnt, rec0, end, offs))
        p = end
    if p < size:
        print(f"    -> chain ends at 0x{p:06x}; remaining to EOF = {size-p} bytes "
              f"({(size-p)/size*100:.1f}% of file)")
        print(f"       first 32B there: {hx(b[p:p+32])}")
    allo = [o for _,_,_,_,offs in blocks for o in offs]
    BASE[n] = (p, max(allo) if allo else 0, blocks)

print()
print("=" * 108)
print("B) BASE TEST — does blobStart(end of chain) + maxOffset land near EOF-24?")
print("=" * 108)
for n, _ in FILES:
    b = data[n]; size = len(b)
    p, mx, blocks = BASE[n]
    blobLen = size - 24 - p
    print(f"  {n}: chainEnd=0x{p:06x} blobLen={blobLen:<9d} maxOff={mx:<9d} "
          f"maxOff/blobLen={mx/blobLen:.4f}  slack={blobLen-mx}")

print()
print("=" * 108)
print("C) IMPLIED GLYPH DATA LENGTH vs bounding-box size (70970, Arabic) — sanity of the offsets")
print("=" * 108)
n = "70970"; b = data[n]
p, mx, blocks = BASE[n]
hdr, cnt, rec0, end, offs = blocks[0]
rows = []
for i in range(cnt):
    k = rec0 + 36*i
    cp = u16(b, k); off = u32(b, k+32)
    fl = [f32(b, k+4+4*j) for j in range(7)]
    rows.append((off, cp, fl, i))
rows.sort()
print(f"  base(chainEnd)=0x{p:x}  blobLen={len(b)-24-p}")
for j in range(8):
    off, cp, fl, i = rows[j]
    nxt = rows[j+1][0] if j+1 < len(rows) else len(b)-24-p
    w, h = fl[5], fl[6]
    print(f"    U+{cp:04X} off={off:<9d} implLen={nxt-off:<7d} boxW={w:<6.1f} boxH={h:<6.1f} "
          f"W*H={w*h:<9.0f} ratio={(nxt-off)/(w*h) if w*h else 0:.3f}")
print("  ... last few:")
for j in range(max(0, len(rows)-4), len(rows)):
    off, cp, fl, i = rows[j]
    nxt = rows[j+1][0] if j+1 < len(rows) else len(b)-24-p
    w, h = fl[5], fl[6]
    print(f"    U+{cp:04X} off={off:<9d} implLen={nxt-off:<7d} boxW={w:<6.1f} boxH={h:<6.1f} "
          f"W*H={w*h:<9.0f} ratio={(nxt-off)/(w*h) if w*h else 0:.3f}")

print()
print("=" * 108)
print("D) Is the glyph payload an 8-bit COVERAGE BITMAP? test W*H == implied length")
print("=" * 108)
for n, _ in FILES:
    b = data[n]; p, mx, blocks = BASE[n]
    hdr, cnt, rec0, end, offs = blocks[0]
    rows = []
    for i in range(cnt):
        k = rec0 + 36*i
        rows.append((u32(b,k+32), u16(b,k), f32(b,k+28), f32(b,k+32-4)))
    rows.sort()
    hits = tot = 0
    for j in range(len(rows)-1):
        off, cp, w, h = rows[j]
        implied = rows[j+1][0] - off
        if implied == 0: continue
        tot += 1
        if abs(implied - round(w)*round(h)) <= max(2, 0.02*implied):
            hits += 1
    print(f"  {n}: W*H matches implied length for {hits}/{tot} glyphs ({hits/tot*100 if tot else 0:.1f}%)")
