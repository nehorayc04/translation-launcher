# -*- coding: utf-8 -*-
r"""align_walk.py — can a CLEAN rule close the sequential walk EXACTLY at the store end?

The 12B model overshoots by 3,864 B (322 verts). If a simple, principled rule (per-block
header, count-field semantics, or a sentinel exclusion) closes it to gap==0, block boundaries
are nailed => the notdef box becomes a Rosetta stone for the coord codec. If nothing clean
closes it, the on-disk layout is packed/transformed and static decode is genuinely dead.
"""
import struct, collections

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0
TARGET = N - STORE  # 155,856


def u16(p): return struct.unpack_from("<H", F, p)[0]
def is_rec(p):
    return p + 64 <= N and u16(p + 2) == 0 and F[p + 20] == 0xf8 and u16(p + 62) == 0xffff


recs = []
p = 0x860000
while p < STORE:
    if is_rec(p):
        recs.append(p); p += 64
    else:
        p += 1

counts = [u16(o + 18) for o in recs]
faces  = [u16(o + 14) for o in recs]
owners = [(c, fc) for c, fc in zip(counts, faces) if c not in (0xffff, 0)]
raw = sum(c for c, _ in owners)
print(f"owners={len(owners)}  sum(count)={raw}  TARGET/12={TARGET/12:.2f}  raw-TARGET/12={raw-TARGET/12:+.1f} verts\n")

# 1) per-block header of H bytes at various strides
print("== stride+header sweep: bytes = sum(count)*stride + nblocks*H ==")
best = []
for stride in (4, 6, 8, 10, 12, 16, 20, 24):
    for H in range(0, 33, 2):
        b = raw * stride + len(owners) * H
        best.append((abs(b - TARGET), stride, H, b))
for d, stride, H, b in sorted(best)[:8]:
    print(f"  stride={stride:2} header={H:2}B -> {b:,}  gap={b-TARGET:+,}")

# 2) count semantics: maybe count = CONTOURS and each contour has variable pts... can't test.
#    But maybe some count VALUES are sentinels (no block). Which single value, excluded, closes it?
print("\n== exclude one count-value (treat as sentinel) at stride 12 ==")
cc = collections.Counter(c for c, _ in owners)
overshoot_verts = raw - TARGET // 12  # verts to remove
for val, freq in cc.most_common(20):
    removed = val * freq
    newsum = raw - removed
    print(f"  drop count=={val:5} ({freq:4} recs, {removed*12:6}B): sum={newsum} -> bytes={newsum*12:,} gap={newsum*12-TARGET:+,}")

# 3) maybe count is off-by-one (count-1 real verts)
for delta in (-1, +1):
    b = sum(max(0, c + delta) for c, _ in owners) * 12
    print(f"\n  (count{delta:+}) *12 = {b:,}  gap={b-TARGET:+,}")

# 4) maybe only SOME faces own blocks. Sum per-face and see which face-set closes it.
print("\n== per-face vertex totals (top faces by count-sum) ==")
byface = collections.Counter()
for c, fc in owners:
    byface[fc] += c
tot = sum(byface.values())
for fc, s in byface.most_common(12):
    print(f"  face {fc:4}: {s:5} verts = {s*12:6}B  ({s/tot*100:4.1f}%)")
