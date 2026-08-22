# -*- coding: utf-8 -*-
r"""walk_store.py — CONFIRM the sequential store model + decode notdef vs Arabic blocks.

Model (from rec_offset_hunt): records with +18 != 0xffff/0 own a block; blocks are laid
SEQUENTIALLY in file(record) order; block size = count * 12 bytes. No ref->offset table.

Walk it and check the cursor closes near the store end. Then decode the notdef block and a
real Arabic block under 3 candidate 12B-vertex codecs to see which gives a sane glyph.
"""
import struct, collections

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0


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

# ---- walk: assign each block a store offset ----
cur = STORE
blocks = {}    # rec_addr -> (off, count)
for o in recs:
    c = u16(o + 18)
    cp = struct.unpack_from("<I", F, o)[0]
    ref = u16(o + 16)
    if c in (0xffff, 0):
        continue
    blocks[o] = (cur, c)
    cur += c * 12

print(f"records={len(recs)}  blocks={len(blocks)}")
print(f"walk ended at 0x{cur:x}; store ends at 0x{N:x}; gap = {N - cur:+,} bytes "
      f"({(cur-STORE)/(N-STORE)*100:.1f}% of store consumed)\n")

# try a few stride variants to see which closes EXACTLY
for stride in (12, ):
    cur = STORE
    for o in recs:
        c = u16(o + 18)
        if c in (0xffff, 0):
            continue
        cur += c * stride
    print(f"  stride {stride}: end=0x{cur:x} gap={N-cur:+,}")


def codecs(block):
    """decode a block 3 ways, return short strings."""
    nv = len(block) // 12
    out = {}
    # A: 3 x f32
    a = []
    for i in range(min(nv, 6)):
        x, y, z = struct.unpack_from("<3f", block, i * 12)
        a.append(f"({x:+.3f},{y:+.3f},{z:+.3g})")
    out["3xf32"] = " ".join(a)
    # B: 2 x f32 + u32
    b = []
    for i in range(min(nv, 6)):
        x, y = struct.unpack_from("<2f", block, i * 12)
        fl = struct.unpack_from("<I", block, i * 12 + 8)[0]
        b.append(f"({x:+.3f},{y:+.3f})|{fl:08x}")
    out["2xf32+u32"] = " ".join(b)
    # C: 6 x s16 /32768
    c6 = []
    for i in range(min(nv, 4)):
        s = struct.unpack_from("<6h", block, i * 12)
        c6.append("(" + ",".join(f"{v/32768:+.2f}" for v in s) + ")")
    out["6xs16"] = " ".join(c6)
    return nv, out


# ---- pick sample records: notdef (ref 1522), Arabic (ref 1680), a big-count one ----
def find_ref(ref, want=1):
    got = []
    for o in recs:
        if u16(o + 16) == ref and o in blocks:
            got.append(o)
            if len(got) >= want:
                break
    return got


for label, ref in [("notdef/Hebrew page", 1522), ("Arabic 1680", 1680)]:
    hits = find_ref(ref, 1)
    if not hits:
        print(f"\n[{label}] ref={ref}: no block-owning record"); continue
    o = hits[0]
    off, c = blocks[o]
    cp = struct.unpack_from("<I", F, o)[0]
    block = F[off:off + c * 12]
    nv, dec = codecs(block)
    print(f"\n[{label}] rec@0x{o:x} cp=U+{cp:04X} count={c} block@0x{off:x} ({c*12}B, {nv} verts)")
    for k, v in dec.items():
        print(f"    {k}: {v}")

# ---- is the notdef block IDENTICAL across its 114 records? (dedup vs per-copy) ----
nd = [o for o in recs if u16(o + 16) == 1522 and o in blocks]
print(f"\nnotdef-page block-owning records: {len(nd)}")
if len(nd) >= 2:
    b0 = F[blocks[nd[0]][0]:blocks[nd[0]][0] + blocks[nd[0]][1] * 12]
    same = sum(1 for o in nd if F[blocks[o][0]:blocks[o][0] + blocks[o][1] * 12] == b0)
    print(f"  identical-to-first blocks: {same}/{len(nd)}  (all same => notdef box repeated per copy)")
    # count distinct block CONTENTS among notdef records
    cont = collections.Counter(F[blocks[o][0]:blocks[o][0] + blocks[o][1] * 12] for o in nd)
    print(f"  distinct notdef block contents: {len(cont)}  top={[(h[:8].hex(),n) for h,n in cont.most_common(3)]}")
