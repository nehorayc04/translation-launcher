# -*- coding: utf-8 -*-
r"""store_parse.py — crack the FontVerts store addressing STATICALLY.

Hypothesis under test: the tail-kind2 store @0x97c8d0 is a SEQUENTIAL stream of
per-glyph blocks; a cmap record's ref (+16) is (a base offset +) the block index,
so the store needs NO separate offset table. If block[k] for the notdef ref (1522)
is degenerate/repeated and block[k'] for the Arabic-alef ref (1680) is a real curve,
the sequential-index model is confirmed and the addressing is cracked.

Prints the store's structural map: alternating CLEAN(f32 pairs in [-1,1]) vs
PACK(0x74XX pattern) runs, plus any obvious record/header delimiter.
"""
import struct, collections

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0
print(f"file {N:,} B  store @0x{STORE:x}  tail bytes={N-STORE:,}")


def f32(p): return struct.unpack_from("<f", F, p)[0]
def u16(p): return struct.unpack_from("<H", F, p)[0]
def u32(p): return struct.unpack_from("<I", F, p)[0]


def clean_pair(p):
    """True if the 8 bytes at p look like a normalized (x,y) coord pair in [-1.05,1.05]."""
    try:
        x, y = f32(p), f32(p + 4)
    except struct.error:
        return False
    return (-1.05 <= x <= 1.05) and (-1.05 <= y <= 1.05) and not (x == 0.0 and y == 0.0)


def is_pack(p):
    """0x74XX 0x74XX little-endian pattern: bytes [p+1]==0x74 and [p+3]==0x74 style."""
    if p + 4 > N: return False
    # observed as '74 XX 74 XX' in the notes; check both byte-1 and byte-3 == 0x74
    return F[p + 1] == 0x74 and F[p + 3] == 0x74


# ---- 1. Coarse run map over the whole tail: CLEAN vs PACK vs OTHER, step 4 ----
print("\n== coarse run map (first 60 runs) ==")
runs = []
p = STORE
kind = None
start = STORE
step = 4
while p + 8 <= N:
    if clean_pair(p):
        k = "CLEAN"; adv = 8
    elif is_pack(p):
        k = "PACK"; adv = 4
    else:
        k = "OTHER"; adv = 4
    if k != kind:
        if kind is not None:
            runs.append((kind, start, p))
        kind, start = k, p
    p += adv
runs.append((kind, start, p))
for k, a, b in runs[:60]:
    n = b - a
    extra = ""
    if k == "CLEAN":
        extra = f"  first=({f32(a):+.4f},{f32(a+4):+.4f}) pairs={n//8}"
    print(f"  {k:5} @0x{a:07x} len={n:5}{extra}")
tot = collections.Counter()
for k, a, b in runs:
    tot[k] += b - a
print(f"  ... {len(runs)} runs total; bytes: {dict(tot)}")


# ---- 2. Look for a block/record delimiter: scan for repeated small headers ----
# A common vector-font layout: each glyph = [u16 nContours][u16 nPts]... or a marker.
# Check the bytes IMMEDIATELY before each CLEAN run start (candidate per-glyph header).
print("\n== bytes preceding each CLEAN run (candidate glyph headers) ==")
clean_starts = [a for (k, a, b) in runs if k == "CLEAN"]
print(f"  {len(clean_starts)} CLEAN runs")
hdrcount = collections.Counter()
for a in clean_starts[:40]:
    pre = F[max(STORE, a - 8):a]
    hdrcount[pre.hex()] += 1
    print(f"  @0x{a:07x} pre8={pre.hex()}  u16s={[u16(a-8+i*2) for i in range(4)]}")

# ---- 3. Notdef signature: the box is 'A B C B C…' repeated ~111x per the notes ----
# Find the most-repeated 8-byte unit in the tail (should be the notdef box vertex).
print("\n== most-repeated 8-byte-aligned units in the tail ==")
units = collections.Counter()
p = STORE
while p + 8 <= N:
    units[F[p:p + 8]] += 1
    p += 8
for u, c in units.most_common(8):
    xs = struct.unpack("<ff", u) if len(u) == 8 else (0, 0)
    print(f"  {u.hex()}  x{c}   asf32={xs[0]:+.5g},{xs[1]:+.5g}")
