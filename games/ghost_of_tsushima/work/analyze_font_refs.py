#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""analyze_font_refs.py — RESOLVE the +14/+16/+18 contradiction empirically.

Round-2 note (arabic_font_table.md): (+14,+16,+18) is the per-glyph OUTLINE reference;
  real Arabic letters have DISTINCT refs, the 27 Hebrew records share near-identical refs.
Attempt-#5 note (FONT_ATTEMPT5_FINDINGS.md): the records are a pure CMAP; Latin A/O/i are
  byte-identical except cp, so nothing in the record points at an outline.

This scans the REAL cached ghost_title.xpps, independently locates the glyph-record
sub-tables (NO trust in hardcoded offsets — found by the record signature + cp ladder),
and tabulates (cp, +14, +16, +18, geom[+22/+26/+30]) for the Latin, Hebrew and Arabic
letter blocks. It then reports whether Arabic refs are per-glyph-distinct and whether the
27 Hebrew refs are degenerate.
"""
import os, struct, collections

CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
D = open(os.path.join(CACHE, "ghost_title.bin"), "rb").read()
GREC = 64
print(f"ghost_title.xpps: {len(D):,} B")


def u16(p): return struct.unpack_from("<H", D, p)[0]
def u32(p): return struct.unpack_from("<I", D, p)[0]
def f32(p): return struct.unpack_from("<f", D, p)[0]


def is_rec(p):
    """Record invariants that hold across BOTH layouts (per notes): +2==0 (cp hi half),
    +20 byte==0xf8, +62==0xffff."""
    if p < 0 or p + GREC > len(D):
        return False
    return u16(p + 2) == 0 and D[p + 20] == 0xf8 and u16(p + 62) == 0xffff


def rec_fields(p):
    return dict(off=p, cp=u16(p), v14=u16(p + 14), v16=u16(p + 16), v18=u16(p + 18),
                gx=f32(p + 22), gy=f32(p + 26), gz=f32(p + 30),
                kind=u32(p + 8), metric=f32(p + 4))


# --- 1. find every record + group into strictly-ascending 64-byte sub-tables -----------
# Scan the font-table region. The bulk 0x0..0x866000 is the title bitmap; tables live after.
records = []
p = 0x860000
END = 0x8a0000
while p < END:
    if is_rec(p):
        records.append(p)
        p += GREC
    else:
        p += 1
print(f"found {len(records)} records in [0x{0x860000:x},0x{END:x})")

# group into runs where consecutive records are 64 apart AND cp ascends (allow 0xffff sep)
subtables = []
cur = []
for i, off in enumerate(records):
    if not cur:
        cur = [off]; continue
    prev = cur[-1]
    if off == prev + GREC:
        cur.append(off)
    else:
        subtables.append(cur); cur = [off]
if cur:
    subtables.append(cur)
print(f"{len(subtables)} contiguous 64B runs")


def cp_of(off): return u16(off)


def find_block(lo, hi):
    """Return the list of record offsets whose cp is in [lo,hi], in file order."""
    return [off for off in records if lo <= cp_of(off) <= hi]


def tab(offs, title):
    print(f"\n== {title}  ({len(offs)} records) ==")
    print(f"  {'cp':>6} {'off':>10} {'+14':>5} {'+16':>6} {'+18':>5}  {'geom (x,y,z)':>22}  kind")
    for off in offs:
        r = rec_fields(off)
        ch = chr(r['cp']) if 32 <= r['cp'] < 127 else ''
        print(f"  0x{r['cp']:04x} 0x{off:08x} {r['v14']:>5} {r['v16']:>6} {r['v18']:>5}"
              f"  ({r['gx']:>7.1f},{r['gy']:>7.1f},{r['gz']:>6.1f})  {r['kind']:>3} {ch}")
    refs = [(rec_fields(o)['v14'], rec_fields(o)['v16'], rec_fields(o)['v18']) for o in offs]
    dist = collections.Counter(refs)
    print(f"  DISTINCT (+14,+16,+18): {len(dist)} of {len(offs)}  -> {dict(list(dist.items())[:8])}"
          + (" ..." if len(dist) > 8 else ""))
    geoms = [(round(rec_fields(o)['gx'], 1), round(rec_fields(o)['gy'], 1), round(rec_fields(o)['gz'], 1)) for o in offs]
    nonzero_geom = sum(1 for g in geoms if g != (0.0, 0.0, 0.0))
    print(f"  geom nonzero: {nonzero_geom}/{len(offs)}  (sample {geoms[:5]})")
    return offs, dist


# --- 2. Latin (control), Hebrew (target), Arabic (source of refs) -----------------------
latin = find_block(0x41, 0x5a)          # A..Z
heb = find_block(0x5d0, 0x5ea)          # alef..tav (27 letters)
# Arabic letters: isolated basic block 0x627..0x64a; but many positional-form sub-tables.
arab_all = find_block(0x600, 0x6ff)

tab(latin[:12], "LATIN A..(sample) — attempt#5's 'cmap' evidence")
heb_offs, heb_dist = tab(heb, "HEBREW 0x5d0..0x5ea (the 27 target records)")

# Arabic: group by which sub-table (contiguity) so we pick clean isolated letters
print(f"\n== ARABIC 0x600..0x6ff: {len(arab_all)} records across sub-tables ==")
# split arabic into contiguous runs
aruns = []
cur = []
for off in arab_all:
    if cur and off != cur[-1] + GREC:
        aruns.append(cur); cur = []
    cur.append(off)
if cur:
    aruns.append(cur)
for run in aruns:
    cps = [cp_of(o) for o in run]
    refs = [(rec_fields(o)['v14'], rec_fields(o)['v16'], rec_fields(o)['v18']) for o in run]
    ndist = len(set(refs))
    geoms = [(round(rec_fields(o)['gz'], 1)) for o in run]
    nz = sum(1 for o in run if (round(rec_fields(o)['gx'],1), round(rec_fields(o)['gy'],1), round(rec_fields(o)['gz'],1)) != (0.,0.,0.))
    print(f"  run @0x{run[0]:08x} n={len(run)} cp[0x{min(cps):x}..0x{max(cps):x}] "
          f"distinct-refs={ndist}/{len(run)} geom-nonzero={nz}")

# detail: the primary Arabic letters block (the one @~0x880dd2 per notes)
prim = max(aruns, key=len)
tab(prim[:30], f"ARABIC primary block @0x{prim[0]:x} (first 30) — do refs differ per glyph?")
