# -*- coding: utf-8 -*-
r"""ref_density.py — is the cmap 'ref' (+16) a DENSE CONSECUTIVE block-index or a SPARSE handle?

Decides the crux blocker (ref -> store offset):
  * dense/consecutive refs  => ref IS the sequential glyph index; offsets computable => MAJOR crack.
  * sparse refs             => ref is a hash/handle into a table => confirms the addressing dead-end.
Also cross-checks: sum of per-glyph vertex sizes (from +18 count) vs the store byte length.
"""
import struct, collections

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0


def u16(p): return struct.unpack_from("<H", F, p)[0]
def f32(p): return struct.unpack_from("<f", F, p)[0]


def is_rec(p):
    return p + 64 <= N and u16(p + 2) == 0 and F[p + 20] == 0xf8 and u16(p + 62) == 0xffff


# scan the whole cmap region [0x860000, store) for records
records = []
p = 0x860000
while p < STORE:
    if is_rec(p):
        records.append(p); p += 64
    else:
        p += 1
print(f"{len(records)} cmap records in [0x860000,0x{STORE:x})")

refs = collections.Counter()
ref_count = {}    # ref -> the +18 'count' (should be constant per ref)
ref_conflict = 0
for o in records:
    r = u16(o + 16)
    c = u16(o + 18)
    refs[r] += 1
    if r in ref_count and ref_count[r] != c:
        ref_conflict += 1
    ref_count.setdefault(r, c)

distinct = sorted(refs)
print(f"distinct refs: {len(distinct)}  range [{distinct[0]}..{distinct[-1]}]")
print(f"records sharing a ref (max): {refs.most_common(3)}")
print(f"ref->count conflicts (same ref, different +18): {ref_conflict}")

# density: how many of [min..max] are present?
span = distinct[-1] - distinct[0] + 1
print(f"\nDENSITY: {len(distinct)} present of {span} in span = {len(distinct)/span*100:.1f}%")
# gaps
gaps = [(distinct[i+1]-distinct[i]) for i in range(len(distinct)-1)]
gc = collections.Counter(gaps)
print(f"gap histogram (delta between consecutive present refs): {dict(sorted(gc.items())[:12])}")

# consecutiveness: longest run of +1 steps
run = best = 1
for i in range(1, len(distinct)):
    if distinct[i] == distinct[i-1] + 1:
        run += 1; best = max(best, run)
    else:
        run = 1
print(f"longest consecutive (+1) ref run: {best}")

# size check: if ref is a block index and +18 is a per-glyph vertex count,
# does sum(count) * bytes_per_vertex land near the store size for a few candidates?
tot_count = sum(ref_count[r] for r in distinct)
print(f"\nsum of per-ref +18 counts (distinct refs) = {tot_count}")
store_bytes = N - STORE
for bpv, name in [(8, "8B/vertex (s16x4 or f32x2)"), (4, "4B/vertex (s16x2)"),
                  (16, "16B/vertex")]:
    print(f"  store {store_bytes} / {bpv}B = {store_bytes//bpv} vertices; sum(count)={tot_count}"
          f"  ratio={store_bytes/(tot_count*bpv):.2f}  [{name}]")

# show a sample ladder of (ref,count) sorted by ref, to eyeball structure
print("\n== (ref,count) sorted by ref, first 40 ==")
for r in distinct[:40]:
    print(f"  ref {r:5}  count(+18)={ref_count[r]:3}  shared-by={refs[r]}")
