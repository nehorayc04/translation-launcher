#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ght_sections.py — MAP the KCAP section/directory structure of ghost_title.xpps
(the Ghost of Tsushima DC multi-script UI/title/menu font inside gapack_misc_g.psarc),
so the FontVerts codec crack + Hebrew injection can place data correctly.

Read-only. Feed it the extracted /ghost_title.xpps (10,103,200 B) or the cached bin.
Emits: the full section table, identifies cmap vs vertex-store vs bitmap/keyframe
sections, and prints a REPACK FIXUP PLAN for growing the vertex store.

    python ght_sections.py [path/to/ghost_title.xpps]     # human table
    python ght_sections.py --json [path]                  # machine JSON
    python ght_sections.py --plan  <delta_bytes> [path]   # repack fixup plan for +delta

Findings verified against the real cached bin (see notes/ghost_title_sections.md).
"""
import os, sys, json, struct

DEFAULT = os.path.join(
    r"C:/Users/NEHORA~1/AppData/Local/Temp/claude",
    r"c--Users-Nehoray-Cohen-Projects-Game-translator",
    r"a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad/ghost_title.bin")


def load(path=None):
    p = path or DEFAULT
    with open(p, "rb") as f:
        d = f.read()
    if d[:4] != b"KCAP":
        raise ValueError(f"{p}: not KCAP (magic={d[:4]!r})")
    return d


def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]
def u64(d, p): return struct.unpack_from("<Q", d, p)[0]


# ---------------------------------------------------------------- header
def header(d):
    """KCAP header fields (verified constant-ish across the font asset)."""
    return {
        "magic":            d[:4].decode("latin1"),           # 'KCAP'
        "version@0x04":     u32(d, 0x04),                     # 0x0003001f
        "type@0x08":        u32(d, 0x08),                     # 0x0000041d
        "flags@0x0c":       u32(d, 0x0c),                     # 0x70010000
        "hdrsz@0x10":       u32(d, 0x10),                     # 0x30
        "node_tbl@0x18":    u32(d, 0x18),                     # -> 0xb8  MASTER NODE TABLE
        "sect_dir@0x1c":    u32(d, 0x1c),                     # -> 0x198 SECTION DIRECTORY
        "trailer_sz@0x28":  u32(d, 0x28),                     # 0x250 (== EOF - trailer_start)
        "trailer_off@0x2c": u32(d, 0x2c),                     # 0x9a2750 TRAILER START
        "asset_guid@0x98":  d[0x98:0xa8].hex(),               # 16-byte asset id
        "file_size":        len(d),
    }


# ---------------------------------------------------------------- @0x198 tail section directory
def section_dir(d):
    """13 x 12-byte [u16 flag=0x10][u16 kind][u32 size][u32 ABS_off].
    Covers ONLY the tail metadata sections 0x8eefa0..0x97c8d0."""
    p = u32(d, 0x1c)          # 0x198
    n = len(d)
    ents = []
    while p + 12 <= 0x8000:
        fl, k = u16(d, p), u16(d, p + 2)
        sz, of = u32(d, p + 4), u32(d, p + 8)
        if fl != 0x10 or of == 0 or of >= n or sz > n:
            break
        ents.append({"idx": len(ents), "kind": k, "off": of, "size": sz,
                     "end": of + sz, "flag": fl,
                     # the two 4-byte words that hold this entry's size/off (for fixups)
                     "size_at": p + 4, "off_at": p + 8})
        p += 12
    return ents, (u32(d, 0x1c), p)   # (dir_start, dir_end)


# ---------------------------------------------------------------- @0xb8 master node table offsets
def node_table_offsets(d):
    """Scan the master node table 0xb8..0x198 for the primary-region absolute
    offsets it embeds (bitmap/index/cmap-block/transforms/kind18/tail). Returns
    [(word_offset, value)] for every u32 in file-offset range — these are the
    fixup words for a growth that shifts a primary region."""
    n = len(d)
    out = []
    for p in range(0xb8, 0x198, 4):
        v = u32(d, p)
        if 0x800000 <= v < n:
            out.append({"at": p, "value": v})
    return out


# ---------------------------------------------------------------- kind18 hash index
def kind18_index(d, off, size):
    """Open-addressed hash table: 16-byte [u64 name-hash][u32 val][u32 0]. `val` is
    usually an ABSOLUTE file offset into the kind1/kind6 metadata (name resolution),
    but some used slots hold small sentinels (1) or the empty-marker 0xffffffff.
    Only REAL file-offset ptrs (0x800000<=val<file_size) need relocation on growth.
    Returns (slot_count, used, real_ptr_min, real_ptr_max, ptr_words[])."""
    n = len(d)
    cnt = size // 16
    used = 0
    pmin, pmax = 1 << 62, 0
    ptr_words = []
    for i in range(cnt):
        q = off + i * 16
        h = u64(d, q); a = u32(d, q + 8)
        if h == 0 and a == 0:
            continue
        used += 1
        if 0x800000 <= a < n:                # a real absolute file offset
            pmin = min(pmin, a); pmax = max(pmax, a)
            ptr_words.append(q + 8)          # word to fixup if <a> shifts
    return cnt, used, (pmin if ptr_words else 0), pmax, ptr_words


# ---------------------------------------------------------------- the full model
def build_model(d):
    n = len(d)
    ents, (dstart, dend) = section_dir(d)
    kind18 = next(e for e in ents if e["kind"] == 18)
    k18cnt, k18used, k18pmin, k18pmax, _ = kind18_index(d, kind18["off"], kind18["size"])
    tail_off, tail_end = kind18["end"], u32(d, 0x2c)   # 0x97c8d0 .. trailer
    # Primary (pre-tail-dir) data regions — bounds from @0xb8 offsets + cmap scan.
    sections = [
        {"name": "kcap_header",        "off": 0x0,       "end": 0xb8,
         "kind": "header", "role": "KCAP header (magic/version/ptrs/asset-guid)"},
        {"name": "master_node_table",  "off": 0xb8,      "end": 0x198,
         "kind": "nodes",  "role": "typed node/pointer table; embeds primary-region abs offsets+sizes"},
        {"name": "section_directory",  "off": dstart,    "end": dend,
         "kind": "dir",    "role": "13x12B [flag,kind,size,ABS_off] for the tail metadata sections"},
        {"name": "root_ptr",           "off": 0x250,     "end": 0x260,
         "kind": "rootptr","role": "root object pointer struct {1,0,->0x8f3d28}"},
        {"name": "title_bitmap",       "off": 0x2000,    "end": 0x850c00,
         "kind": "bitmap", "role": "pre-rendered title/logo atlas (bulk ~8.7MB)"},
        {"name": "sprite_index_table", "off": 0x850c00,  "end": 0x866952,
         "kind": "index",  "role": "8-byte {type,0}+abs-offset records into the bitmap/glyph sprites"},
        {"name": "cmap_glyph_records", "off": 0x866952,  "end": 0x8aec92,
         "kind": "cmap",   "role": "64-byte codepoint->(+14 page,+16 base,+18 idx) records; Latin/Cyrillic/HEBREW/Arabic/Indic/CJK"},
        {"name": "transforms_keyframes","off": 0x8aec92, "end": 0x8eefa0,
         "kind": "anim",   "role": "glyph-sprite transforms (pos/quat/scale) + ASCII keyframe() curves + hero/heroine styles"},
    ]
    # tail metadata sections from @0x198
    kindmap = {1: "curve/metric blob", 11: "kind11 blob", 6: "kind6 blob",
               26: "kind26 blob", 3: "glyph-id list + style-def ptrs + packed binary",
               18: "64-bit name-hash -> ABS-ptr index (name resolution)"}
    for e in ents:
        sections.append({
            "name": f"dir[{e['idx']}]_kind{e['kind']}",
            "off": e["off"], "end": e["end"], "kind": f"k{e['kind']}",
            "role": kindmap.get(e["kind"], f"kind{e['kind']}")})
    # tail geometry / vertex store (kind2 per @0xb8 @0x138) + trailer
    sections.append({"name": "vertex_store_tail_kind2", "off": tail_off, "end": tail_end,
        "kind": "k2", "role": "TAIL geometry: normalized f32 in [-1,1] — best FontVerts/outline-vertex candidate"})
    sections.append({"name": "trailer", "off": tail_end, "end": n, "kind": "trailer",
        "role": "KCAP relocation/patch directory; 8-byte type-hash-tagged records; ends FourCC ' DNE' (=END)"})
    return {
        "file_size": n, "header": header(d),
        "section_dir": {"start": dstart, "end": dend, "entries": ents},
        "kind18": {"off": kind18["off"], "size": kind18["size"],
                   "slots": k18cnt, "used": k18used,
                   "ptr_min": k18pmin, "ptr_max": k18pmax},
        "node_table_offsets": node_table_offsets(d),
        "vertex_store": {"off": tail_off, "end": tail_end, "size": tail_end - tail_off},
        "cmap": {"off": 0x866952, "end": 0x8aec92},
        "sections": sections,
    }


# ---------------------------------------------------------------- repack fixup plan
def repack_plan(d, delta):
    """Plan for GROWING the vertex store by `delta` bytes appended at the END of the
    tail kind2 region (i.e. just before the trailer @0x2c). This is the SAFEST growth:
    every absolute offset in the file is < the insertion point, so only the trailer
    moves. Returns the exact list of words to patch."""
    m = build_model(d)
    ins = m["vertex_store"]["end"]              # = trailer start = insertion point
    # tail kind2 SIZE word lives in the master node table @0x13c (0x25e80) and mirrored
    # in the dir? no — kind2 is NOT in @0x198. It's @0xb8 @0x13c. trailer_off @0x2c.
    fix = []
    fix.append(("trailer_off@0x2c", 0x2c, u32(d, 0x2c), u32(d, 0x2c) + delta))
    fix.append(("tail_kind2_size@0x13c", 0x13c, u32(d, 0x13c), u32(d, 0x13c) + delta))
    # sanity: NOTHING in @0x198 dir, kind18 ptrs, @0x250 root, or the other @0xb8
    # offsets should move (all < ins). Assert it.
    assert all(e["end"] <= ins for e in m["section_dir"]["entries"])
    assert m["kind18"]["ptr_max"] < ins
    return {"insertion_point": ins, "delta": delta, "words_to_patch": fix,
            "unchanged": ["@0x198 section dir (all offs < ins)",
                          "kind18 hash ptrs (all < ins)",
                          "@0x250 root ptr", "other @0xb8 offsets",
                          "cmap records (repoint in-place, same 64B each)"],
            "must_verify": "the trailer ' DNE'-terminated relocation records may encode the "
                           "tail extent/EOF — re-emit or copy+patch them, then boot-test."}


# ---------------------------------------------------------------- CLI
def print_table(m):
    print(f"ghost_title.xpps  {m['file_size']:,}B (0x{m['file_size']:x})  magic={m['header']['magic']}")
    h = m["header"]
    print(f"  version=0x{h['version@0x04']:08x} type=0x{h['type@0x08']:x} "
          f"node_tbl@0x18=0x{h['node_tbl@0x18']:x} sect_dir@0x1c=0x{h['sect_dir@0x1c']:x} "
          f"trailer@0x2c=0x{h['trailer_off@0x2c']:x} (sz 0x{h['trailer_sz@0x28']:x})")
    print(f"  asset_guid@0x98={h['asset_guid@0x98']}")
    print(f"\n  {'section':26} {'off':>10} {'end':>10} {'size':>10}  role")
    for s in m["sections"]:
        print(f"  {s['name']:26} 0x{s['off']:08x} 0x{s['end']:08x} 0x{s['end']-s['off']:08x}  {s['role']}")
    k = m["kind18"]
    print(f"\n  kind18 index @0x{k['off']:x} size 0x{k['size']:x}: {k['slots']} slots, "
          f"{k['used']} used, ptrs 0x{k['ptr_min']:x}..0x{k['ptr_max']:x} (ABSOLUTE, into metadata)")
    v = m["vertex_store"]
    print(f"  vertex_store (tail kind2) @0x{v['off']:x}..0x{v['end']:x} = 0x{v['size']:x} ({v['size']:,}B)")
    print(f"  node-table abs offsets (fixup words if a primary region shifts):")
    for o in m["node_table_offsets"]:
        print(f"     @0x{o['at']:03x} -> 0x{o['value']:08x}")


def main():
    args = [a for a in sys.argv[1:]]
    js = "--json" in args; args = [a for a in args if a != "--json"]
    if args and args[0] == "--plan":
        delta = int(args[1], 0); path = args[2] if len(args) > 2 else None
        print(json.dumps(repack_plan(load(path), delta), indent=2))
        return
    d = load(args[0] if args else None)
    m = build_model(d)
    if js:
        # strip the fixup-word helper fields for a clean dump
        print(json.dumps(m, indent=1))
    else:
        print_table(m)


if __name__ == "__main__":
    main()
