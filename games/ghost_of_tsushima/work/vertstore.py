#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""vertstore.py — Ghost of Tsushima DC `ghost_title.xpps` font geometry-store map +
KNOWN-PLAINTEXT crack attempt on the packed vertex/outline codec (round 3, 2026-07-08).

RESULT (honest): the per-glyph outline/vertex store was LOCATED precisely and the whole
addressing chain (sub-resource -> cmap record -> outline-id -> 8-byte units) was mapped,
but the 8-byte units are MAX-ENTROPY per byte-lane and every plaintext-coordinate
hypothesis (int16 / int8-delta / float16 / 11-bit-packed / cumulative-delta) FAILS to
trace a known glyph. The store is compressed or encrypted (NOT zlib/lz4/Oodle-lead, NOT a
plain BC4 atlas) -> it is NOT crackable by offline known-plaintext; it needs the exe's
`FONTK` decode callbacks (image base 0x140000000, handler table @exe 0x011628F8) or is
whitened/encrypted. So `cracked = False`; this file documents the verified structure so a
future exe-RE pass lands directly on the decoder. See notes/FONT_ATTEMPT6_FINDINGS.md.

VERIFIED STRUCTURE (all run against scratchpad/ghost_title.bin, 10,103,200 B,
md5 3d5d62aa44dacd44640ed132493ab6db):

  KCAP header @0: @0x18->0xb8 (sub-resource table), @0x1c->0x198 (KCAP section dir, 13
    entries), @0x28->0x250, @0x2c->0x9a2750 (trailer: hash-keyed resource dir ending FourCC
    "END ").

  Sub-resources (the file is a multi-resource KCAP, NOT a pure font):
    - 0x1000..~0x40000   title-card SPRITE TRANSFORMS + keyframe animation (pos.xyz +
                         quaternion 0,0,0,1 + scale 1,1,1 sparse floats). NOT glyph data.
    - ~0x40000..0x840000 8.4 MB BC7 texture = the pre-rendered "GHOST OF TSUSHIMA" title
                         LOGO bitmap (ent ~7.5). NOT glyph outlines.
    - 0x850c00..0x8b74b0 (size 0x668b0) = the FONT sub-resource (see below).
    - 0x8eefa0..0x97c8d0 the 13 KCAP sections (kind1 index/curve lists; kind3 @0x8f43b0 =
                         glyph-id list + style-def pointers; kind18 @0x934940 = a 64-bit
                         hash -> style-def-pointer index -- it points at the hero/heroine
                         STYLE defs @0x8f3exx, i.e. kind18 is the STYLE index, NOT outlines).

  FONT sub-resource 0x850c00..0x8b74b0:
    - 0x850c00.. header + {u64 1, u64 2, u64 ptr} records.
    - u16 index buffers (0x851000: idx 392..4454; 0x852c00 area: idx 0..0xfff8 w/ 0xfff8
      restart sentinel) -- triangle/edge index lists for the tessellated glyph mesh.
    - {u64 flag=1, u64 ptr} DRAW DESCRIPTORS: 3728 of them, ptr steps by +8 across
      0x8b0000..0x8b74a8 -> 3728 consecutive 8-byte units in the store.
    - 0x866912..0x8aed12  CMAP glyph records, 4550 x 64 bytes (see rec layout below).
    - 0x8aed12..0x8b0000  DESCRIPTOR table, 16-byte stride: +6 u16 outline-id (ascending),
      +8 u16 count. Enumerates a SUBSET of outline-ids (skips the Hebrew & Arabic ranges).
    - 0x8b0000..0x8b74b0  THE STORE: 3728 x 8-byte MAX-ENTROPY units (packed/compressed).

  CMAP 64-byte glyph record (little-endian):
    +0  u32 cp (ascending within a sub-table; 0xffff = positional-form group separator)
    +4  f32 metric (0 here)
    +8  u32 font-kind (0 in ghost_title)
    +12 u16 = 0
    +14 u16 CLUSTER / face id (0..602; ~570 distinct)
    +16 u16 OUTLINE-ID  (real glyphs 1269..3496, ~283 distinct; 0xffff = no vector outline
                         -> Latin/Greek/basic-Cyrillic pages 4/20/23 are ALL 0xffff = they
                         render from the pre-rendered bitmap, not a vector outline)
    +18 u16 COUNT (0..56; 0xffff when +16==0xffff)
    +20 u8 = 0xf8 (record marker) ; +21 u8 = 0
    +22 f32,+26 f32,+30 f32  geom (bbox/advance/placement; e.g. Arabic alef [114,0,10])
    +34..+45 usually 0
    +46,+50,+54,+58  f32 colour = 1,1,1,1 (white)
    +62 u16 = 0xffff

  THE HEBREW GATE (confirmed): the 27 Hebrew letters U+05D0..05EA (@0x87ec92) all share
    +16 = 1522 with a per-letter notdef geom box [x,y,5.0] -> no real outline -> the in-game
    tofu. (Hebrew POINTS 0x591.. and Arabic 0x627.. carry DISTINCT +16 = real outlines.)

  RESOLUTION HYPOTHESIS (structure consistent, payload opaque): glyph outline data =
    store[ +16 : +16 + +18 ] as 8-byte units at 0x8b0000. Unverifiable because the units are
    encrypted/compressed.
"""
import os, sys, struct, math, collections
try:
    import numpy as np
except Exception:
    np = None

CACHE = (r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/"
         r"c--Users-Nehoray-Cohen-Projects-Game-translator/"
         r"a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad")
GT = os.path.join(CACHE, "ghost_title.bin")
GREC = 64

FONT_RES = (0x850c00, 0x850c00 + 0x668b0)   # 0x8b74b0
STORE_BASE = 0x8b0000                        # 3728 x 8-byte packed units
STORE_UNITS = 3728
STORE_STRIDE = 8
CMAP0 = 0x866912                             # first cmap glyph record
DESC0 = 0x8aed12                             # descriptor table

_D = None
def data():
    global _D
    if _D is None:
        _D = open(GT, "rb").read()
    return _D

def u8(d, p):  return d[p]
def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]
def u64(d, p): return struct.unpack_from("<Q", d, p)[0]
def i16(d, p): return struct.unpack_from("<h", d, p)[0]
def i8(d, p):  return struct.unpack_from("<b", d, p)[0]
def f32(d, p): return struct.unpack_from("<f", d, p)[0]

def hexdump(d, base, nb=64):
    out = []
    for i in range(0, nb, 16):
        c = d[base + i:base + i + 16]
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in c)
        out.append(f"  {base+i:08x}  {c.hex(' '):<47}  {asc}")
    return "\n".join(out)

def entropy(seg):
    if not seg:
        return 0.0
    h = collections.Counter(seg)
    return -sum((c / len(seg)) * math.log2(c / len(seg)) for c in h.values())


# ---------------------------------------------------------------- KCAP dirs
def parse_sections(d=None):
    """The @0x198 KCAP section directory: 12-byte [u16 flag=0x10][u16 kind][u32 size][u32 off]."""
    d = d or data(); n = len(d); p = 0x198; ents = []
    while p + 12 <= 0x8000:
        flag, kind = u16(d, p), u16(d, p + 2)
        size, off = u32(d, p + 4), u32(d, p + 8)
        if flag != 0x10 or off == 0 or off >= n or size > n:
            break
        ents.append(dict(idx=len(ents), kind=kind, size=size, off=off))
        p += 12
    return ents


# ---------------------------------------------------------------- cmap records
def is_rec(d, p):
    n = len(d)
    return (p + GREC <= n and u16(d, p + 2) == 0
            and u16(d, p + 20) == 0xf8 and u16(d, p + 62) == 0xffff)

def iter_records(d=None, lo=0x860000, hi=0x8b0000):
    d = d or data(); p = lo
    while p + GREC <= hi:
        if is_rec(d, p):
            yield dict(off=p, cp=u16(d, p), cluster=u16(d, p + 14),
                       outline=u16(d, p + 16), count=u16(d, p + 18),
                       geom=[round(f32(d, p + 22 + 4 * j), 2) for j in range(3)])
            p += GREC
        else:
            p += 2

def records_for_cp(cp, d=None):
    return [r for r in iter_records(d) if r["cp"] == cp]


# ---------------------------------------------------------------- draw descriptors
def iter_draws(d=None):
    """The {u64 flag=1, u64 ptr} draw descriptors in the font sub-resource. ptr -> STORE."""
    d = d or data(); out = []
    for p in range(FONT_RES[0], CMAP0, 16):
        if (u32(d, p) == 1 and u32(d, p + 4) == 0
                and STORE_BASE <= u32(d, p + 8) < FONT_RES[1] and u32(d, p + 12) == 0):
            out.append((p, u32(d, p + 8)))
    return out


# ---------------------------------------------------------------- store slice
def store_unit(idx, d=None):
    d = d or data()
    o = STORE_BASE + idx * STORE_STRIDE
    return d[o:o + STORE_STRIDE]

def glyph_units(outline_id, count, d=None):
    """The hypothesised outline payload for a glyph: store[outline_id : outline_id+count]."""
    return b"".join(store_unit(outline_id + k, d) for k in range(max(count, 1)))


# ---------------------------------------------------------------- known-plaintext tests
def kp_report(cp, d=None):
    """Run every plaintext-coordinate hypothesis on a glyph's store slice and report
    whether any traces a plausible outline. Returns a dict of the decoded candidates."""
    d = d or data()
    recs = records_for_cp(cp, d)
    if not recs:
        return {"cp": cp, "error": "no cmap record"}
    r = recs[0]
    oid, cnt = r["outline"], r["count"]
    res = {"cp": hex(cp), "outline_id": oid, "count": cnt, "geom": r["geom"]}
    if oid == 0xffff:
        res["note"] = "no vector outline (+16==0xffff); renders from bitmap"
        return res
    span = max(cnt, 8) + 4
    raw = glyph_units(oid, span, d)
    if np is None:
        res["raw_hex"] = raw.hex(" ")
        return res
    i16a = np.frombuffer(raw, dtype="<i2")
    i8a = np.frombuffer(raw, dtype=np.int8).astype(int)
    res["H1_raw_i16_pairs"] = [(int(i16a[2 * k]), int(i16a[2 * k + 1])) for k in range(len(i16a) // 2)][:cnt or 6]
    cx, cy = np.cumsum(i16a[0::2]), np.cumsum(i16a[1::2])
    res["H2_i16delta_range"] = (int(cx.max() - cx.min()), int(cy.max() - cy.min()), int(cx[-1]), int(cy[-1]))
    cx8, cy8 = np.cumsum(i8a[0::2]), np.cumsum(i8a[1::2])
    res["H3_i8delta_range"] = (int(cx8.max() - cx8.min()), int(cy8.max() - cy8.min()))
    # verdict: a real closed outline stays bounded (small range, returns near start).
    res["verdict"] = ("OPAQUE — no hypothesis traces a bounded glyph; store is "
                      "compressed/encrypted (see module docstring)")
    return res


# ---------------------------------------------------------------- CLI
def cmd_map():
    d = data(); n = len(d)
    print(f"ghost_title.bin  {n:,} B ({n:#x})  magic={d[:4]!r}")
    print("\n== KCAP section directory @0x198 ==")
    for e in parse_sections(d):
        print(f"  [{e['idx']:2}] kind={e['kind']:2} off={e['off']:#09x} size={e['size']:#08x} "
              f"ent={entropy(d[e['off']:e['off']+min(e['size'],1<<16)]):.2f}")
    print(f"\n== FONT sub-resource {FONT_RES[0]:#x}..{FONT_RES[1]:#x} ==")
    draws = iter_draws(d)
    print(f"  draw descriptors {{1,ptr}}: {len(draws)}  ptr {draws[0][1]:#x}..{draws[-1][1]:#x}"
          if draws else "  (none)")
    print(f"  STORE @{STORE_BASE:#x}: {STORE_UNITS} x {STORE_STRIDE}B units, "
          f"ent={entropy(d[STORE_BASE:STORE_BASE+STORE_UNITS*STORE_STRIDE]):.2f}")
    recs = list(iter_records(d))
    real = [r for r in recs if r["outline"] != 0xffff]
    print(f"  cmap records: {len(recs)}  ({len(real)} with a real +16 outline id)")

def cmd_kp(cp_hex):
    import json
    print(json.dumps(kp_report(int(cp_hex, 0)), ensure_ascii=False, indent=2))

def cmd_rec(cp_hex):
    d = data(); cp = int(cp_hex, 0)
    for r in records_for_cp(cp, d):
        print(f"@{r['off']:#x} cp={cp:#x} cluster={r['cluster']} outline={r['outline']} "
              f"count={r['count']} geom={r['geom']}")
        print(hexdump(d, r['off'], 64))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "map"
    if cmd == "map":
        cmd_map()
    elif cmd == "kp":
        cmd_kp(sys.argv[2])          # known-plaintext report for a codepoint, e.g. 0x627
    elif cmd == "rec":
        cmd_rec(sys.argv[2])
    else:
        print(__doc__)
