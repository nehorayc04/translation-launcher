# -*- coding: utf-8 -*-
r"""rec_offset_hunt.py — is the glyph's STORE OFFSET a field INSIDE the 64-byte cmap record?

Prior work assumed "ref -> offset needs a separate table (absent from file) => dead end".
But only ~30 of the 64 record bytes are mapped. The store offset/length could be one of the
UNEXAMINED fields (+4..+13, +34..+45, +50..+61). If any 4-byte window, read across all
records, yields values that (a) mostly land in [0, store_size], and (b) are monotonic in
record order with deltas that look like block sizes — THAT is the offset field, and the whole
addressing unlocks (no external table needed).

Tests every u32 AND u16 position 0..60 and scores it. Also cross-checks against a SEQUENTIAL
walk (Nth record -> Nth block) using +18 as a vertex count.
"""
import struct, collections

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0
STORE_BYTES = N - STORE


def u16(p): return struct.unpack_from("<H", F, p)[0]
def u32(p): return struct.unpack_from("<I", F, p)[0]


def is_rec(p):
    return p + 64 <= N and u16(p + 2) == 0 and F[p + 20] == 0xf8 and u16(p + 62) == 0xffff


# ---- gather records in file (record) order ----
recs = []
p = 0x860000
while p < STORE:
    if is_rec(p):
        recs.append(p); p += 64
    else:
        p += 1
print(f"{len(recs)} records; store=[0x{STORE:x}..0x{N:x}) = {STORE_BYTES:,} B\n")


def score_u32(x):
    vals = [u32(o + x) for o in recs]
    inrange = sum(1 for v in vals if 0 <= v < STORE_BYTES)
    # monotonic non-decreasing fraction, ignoring records whose val is out of store range
    mono = 1
    prev = None
    good = [v for v in vals if 0 <= v < STORE_BYTES]
    for v in good:
        if prev is None or v >= prev:
            mono += 1
        prev = v
    mono_frac = mono / max(1, len(good))
    distinct = len(set(good))
    return inrange / len(vals), mono_frac, distinct, len(good), vals


def score_u16(x, scale):
    vals = [u16(o + x) * scale for o in recs]
    inrange = sum(1 for v in vals if 0 <= v < STORE_BYTES)
    good = [v for v in vals if 0 <= v < STORE_BYTES]
    mono = 1; prev = None
    for v in good:
        if prev is None or v >= prev:
            mono += 1
        prev = v
    return inrange / len(vals), mono / max(1, len(good)), len(set(good)), len(good)


print("== u32 fields: fraction landing in store, monotonic-frac, distinct ==")
u32res = []
for x in range(0, 61):
    inr, mono, dist, ngood, vals = score_u32(x)
    u32res.append((inr, mono, dist, x, vals))
    if inr > 0.5:
        print(f"  +{x:2}  in-store={inr*100:5.1f}%  mono={mono*100:5.1f}%  distinct={dist}")

print("\n== best u32 candidates by (in-store * mono), top 6 ==")
for inr, mono, dist, x, vals in sorted(u32res, key=lambda r: -(r[0] * r[1]))[:6]:
    sample = [hex(v) for v in vals[:10]]
    print(f"  +{x:2}  in-store={inr*100:5.1f}%  mono={mono*100:5.1f}%  distinct={dist}  first10={sample}")

print("\n== u16 fields (offset possibly scaled x4/x8/x16), best by in-store*mono ==")
u16res = []
for x in range(0, 63):
    for sc in (1, 2, 4, 8, 16):
        inr, mono, dist, ngood = score_u16(x, sc)
        u16res.append((inr, mono, dist, x, sc))
for inr, mono, dist, x, sc in sorted(u16res, key=lambda r: -(r[0] * r[1]))[:8]:
    print(f"  +{x:2} x{sc:2}  in-store={inr*100:5.1f}%  mono={mono*100:5.1f}%  distinct={dist}")

# ---- SEQUENTIAL walk cross-check: does sum of per-record +18 vertex counts * bpv ~= store? ----
print("\n== sequential model: sum(+18 as count, excluding 0xffff sentinel) ==")
counts = [u16(o + 18) for o in recs]
real = [c for c in counts if c != 0xffff and c != 0]
print(f"  records: {len(recs)}  with real +18 (not 0xffff/0): {len(real)}  sum={sum(real)}")
cc = collections.Counter(counts)
print(f"  +18 value histogram top: {cc.most_common(8)}")
for bpv in (4, 8, 12, 16):
    tot = sum(real) * bpv
    print(f"    sum(count)*{bpv:2}B = {tot:,}  vs store {STORE_BYTES:,}  ratio={STORE_BYTES/max(1,tot):.3f}")
