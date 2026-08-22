# GoT DC font — `ghost_title.xpps` KCAP SECTION/DIRECTORY MAP (2026-07-08)

**Goal of this pass (support): fully map the section/directory structure of
`ghost_title.xpps` so the FontVerts codec crack + Hebrew injection can place data
correctly.** This does NOT crack the vertex encoding (still open — see §7); it maps
WHERE every region lives, WHICH one is the cmap vs the vertex store, and EXACTLY what
must be fixed up if the vertex store grows.

All facts run with the repo `.venv` python against the cached real
`ghost_title.xpps` (10,103,200 B = 0x9a29a0, magic `KCAP`). Tool: `work/ght_sections.py`
(`--json`, `--plan <delta>`). No file under `F:/Games/...` was modified.

## 1. Master container layout (KCAP = "PACK")
KCAP is Sucker Punch's serialized-object container. `ghost_title.xpps` has THREE
top-level structures + a tail, all reachable from the header:

```
header  0x00..0xb8   magic 'KCAP', version 0x0003001f, type 0x41d, flags 0x70010000
  @0x18 -> 0xb8      MASTER NODE TABLE
  @0x1c -> 0x198     SECTION DIRECTORY (the 13 tail metadata sections)
  @0x28  = 0x250     trailer SIZE (== EOF - trailer_off)
  @0x2c  = 0x9a2750  TRAILER start  (abs)
  @0x98  16-byte asset GUID = 10fa795e95c3841de88dd7124238b51d
  @0x250 root object pointer struct {1,0, -> 0x8f3d28}
```

- **`@0xb8` MASTER NODE TABLE (0xb8..0x198):** typed nodes describing the *primary*
  data regions (bitmap / sprite-index / cmap-block / transforms / kind18 / tail) with
  their **absolute offsets + sizes**. The offset words it embeds (fixup targets):
  `@0x0ec/@0x118 = 0x934940` (kind18), `@0x140 = 0x97c8d0` (tail), `@0x160/@0x170 =
  0x850c00`, `@0x17c = 0x8b74b0`, `@0x188 = 0x8e9bc0`, `@0x194 = 0x8ed180`; and the
  tail size at `@0x13c = 0x25e80`, kind18 size at `@0x114 = 0x47f90`.
- **`@0x198` SECTION DIRECTORY (0x198..0x234):** 13 × 12-byte entries
  `[u16 flag=0x10][u16 kind][u32 size][u32 ABS_off]`. **Covers ONLY the tail metadata
  sections 0x8eefa0..0x97c8d0** — NOT the 9.36 MB before it. (Round-2's "13-entry
  section dir" is this; it is a sub-directory, not the master TOC.)

## 2. Full section table (verified)
| section | off | end | size | role |
|---|---|---|---|---|
| kcap_header | 0x0 | 0xb8 | 0xb8 | header (ptrs + asset GUID) |
| master_node_table | 0xb8 | 0x198 | 0xe0 | typed nodes; embeds primary-region abs offsets+sizes |
| section_directory | 0x198 | 0x234 | 0x9c | 13×12B [flag,kind,size,ABS_off] for the tail metadata |
| root_ptr | 0x250 | 0x260 | 0x10 | root object ptr {1,0,→0x8f3d28} |
| **title_bitmap** | 0x2000 | 0x850c00 | ~0x84e c00 | pre-rendered title/logo atlas (bulk ~8.7 MB) |
| sprite_index_table | 0x850c00 | 0x866952 | 0x15d52 | 8-byte {type,0}+abs-offset records into the bitmap/sprites |
| **cmap_glyph_records** | 0x866952 | 0x8aec92 | 0x48340 | 64-byte codepoint→(+14 page,+16 base,+18 idx) records; Latin/Cyrillic/**Hebrew**/Arabic/Indic/CJK |
| transforms_keyframes | 0x8aec92 | 0x8eefa0 | 0x4030e | glyph-sprite transforms (pos/quat/scale) + ASCII `keyframe()` curves (34, @0x8eca04..0x8f1acc) + hero/heroine styles (@0x8f3e24) |
| dir[0..4] kind1 | 0x8eefa0 | 0x8f3860 | — | curve/metric blobs |
| dir[5] kind11 | 0x8f3860 | 0x8f3c00 | 0x3a0 | blob |
| dir[6] kind1 | 0x8f3c00 | 0x8f3ee0 | 0x2e0 | curve/metric (holds style names + kind18 ptr targets @0x8f3e28+) |
| dir[7] kind6 | 0x8f3ee0 | 0x8f4190 | 0x2b0 | blob |
| dir[8] kind26 | 0x8f4190 | 0x8f42d0 | 0x140 | blob |
| dir[9,10] kind1 | 0x8f42d0 | 0x8f43b0 | — | blobs |
| **dir[11] kind3** | 0x8f43b0 | 0x934940 | 0x40590 | glyph-id list + style-def ptrs + packed binary |
| **dir[12] kind18** | 0x934940 | 0x97c8d0 | 0x47f90 | 64-bit name-hash → ABS-ptr index (name resolution) |
| **vertex_store (tail kind2)** | 0x97c8d0 | 0x9a2750 | 0x25e80 (155,264 B) | TAIL geometry: normalized f32 in [-1,1] — best FontVerts/outline candidate |
| trailer | 0x9a2750 | 0x9a29a0 | 0x250 | KCAP relocation/patch directory; ends FourCC ' DNE' (=END) |

Note the tail kind2 region is described by `@0xb8` (offset `@0x140`, size `@0x13c`),
and it runs EXACTLY to the trailer (`0x97c8d0 + 0x25e80 = 0x9a2750`).

## 3. cmap section (where the 64-byte records are)
`cmap_glyph_records` = **0x866952..0x8aec92** (~4553 records / 76 cp-ascending
sub-tables; Latin/Cyrillic/**Hebrew 0x5d0–0x5ea**/Arabic/Indic/CJK). It is part of the
*primary* data blob (pre-0x8eefa0), described by the `@0xb8` node table, NOT by the
`@0x198` directory. Record fields: `+0 cp, +14 page, +16 base, +18 index, +20=0xf8,
+62=0xffff` (per `arabic_font_table.md`). Global stats: 4327 detected records; `+14`
0..602, `+16` 39..4577 (389 distinct), `+18` 0..0xffff (47 distinct).

## 4. kind18 hash index (name → object resolution)
`dir[12]` @0x934940, size 0x47f90 = **18,425 slots**, **17,125 used**. Each slot =
`[u64 name-hash][u32 val][u32 0]`. `val` is usually an **ABSOLUTE** file offset; real
ptrs range **0x80015d..0x9931f1**. **KEY: the max (0x9931f1) is INSIDE the tail vertex
store (0x97c8d0..0x9a2750)** → the hash index resolves names to objects in BOTH the
metadata sections AND the tail store. (Some used slots hold sentinels: `1` or
`0xffffffff` = empty-marker — not offsets.) Implication for repack: appending must go
at the tail's **very end** (before the trailer), never mid-tail, or these ptrs break.

## 5. Which section is the vertex/outline store
**`vertex_store_section` = the tail kind2 region `0x97c8d0..0x9a2750` (155,264 B).**
Evidence: it decodes as normalized f32 in [-1,1] (64 % of floats |x|≤1.5, 84 % nonzero;
sample `[-0.6128, 0.7584, 0.2221, 0.6355, -0.7652, 0.5844, …]` = coordinate/normal-like
triples), it is the largest opaque geometry region, it is bounded as one `kind2` node by
`@0xb8`, and named objects (kind18 ptrs up to 0x9931f1) live inside it. This is the
best-supported FontVerts (glyph-outline vertex) candidate. `dir[11] kind3` (264 KB) is
the companion **glyph-id list / per-glyph descriptor** that the cmap `(+14,+16,+18)`
reference most likely indexes into to reach these vertices. **Caveat (honest):** the
record→vertex *resolution* is still uncracked (§7), so this is identification by
content+structure, not a proven decode — confidence **medium**.

## 6. REPACK RECIPE — growing the vertex store (`work/ght_sections.py --plan <delta>`)
The SAFEST growth: **append the new outline vertices at the END of the tail kind2
region (i.e. at 0x9a2750, immediately before the trailer).** Because EVERY absolute
offset in the file is `< 0x9a2750`, nothing before the trailer moves. Fixups:

1. **`@0x2c` trailer_off** `0x9a2750 → +delta`.
2. **`@0x13c` tail_kind2 size** `0x25e80 → +delta` (the master-node size word).
3. **Trailer relocation records** (`@0x9a2750`, 0x250 B, `' DNE'`-terminated, 8-byte
   type-hash-tagged): may encode the tail extent / EOF — re-emit or copy+patch, then
   **boot-test** (this is the one residual uncertainty).
4. **cmap records:** DO NOT grow them. Repoint the 27 existing Hebrew records
   (0x5d0–0x5ea) `(+14,+16,+18)` to the appended outlines **in place** (same 64 B each)
   → no cmap shift.

Guaranteed UNCHANGED by this strategy (all `< insertion`): the `@0x198` section
directory offsets, the 17k kind18 hash ptrs, the `@0x250` root ptr, and the other
`@0xb8` offsets (0x850c00 / 0x8b74b0 / 0x8e9bc0 / 0x8ed180 / 0x934940 / 0x97c8d0).
Keep `delta` 16-byte-aligned (the file uses 16-byte chunk alignment).

**Alternative (RISKIER) — if outlines must live in `kind3`/metadata (before the tail):**
then every downstream absolute offset shifts and you must relocation-sweep ALL of:
`@0xb8` offsets ≥ insertion, every `@0x198` dir off (and grow the changed section's
size), every kind18 ptr ≥ insertion, `@0x250` root ptr, `@0x2c` trailer, and the trailer
relocation records. Avoid unless forced.

**Then wrap back to a PSARC/DSAR override** (per `notes/FONT_ATTEMPT5_FINDINGS.md` §5):
if the edit ends up same-size (overwrite an equal-size unused slot), use
`work/got_dsar.py patch_inner` (surgical). If it grew, rebuild the inner PSARC then
`got_dsar.wrap(inner, boundaries)`. Ship as `zzz_hebrew_font.psarc` sorting after
`gapack_misc_g.psarc` in `cache_pc/psarc/`.

## 7. Still open (NOT this pass — the actual codec gate)
The section MAP is done; the **vertex ENCODING + the cmap→vertex resolution are still
uncracked** (`FONT_ATTEMPT5_FINDINGS.md` §4). This map tells you WHERE to write
(append to the tail kind2 store, repoint cmap `+14/+16/+18`, fix trailer + 2 size/offset
words) but not yet HOW the tail floats are structured per glyph (winding, coord scale,
how `dir[11] kind3` + `(+14,+16,+18)` select a glyph's vertex run). Cracking that needs
either the exe's SFontData/GENERATE_QUAD loader (RE) or a full decode of the kind3
descriptor + tail float layout.

## 8. Tool
`work/ght_sections.py` — `python ght_sections.py [xpps]` (table), `--json` (machine),
`--plan <delta_bytes>` (exact fixup words for a tail-append growth). Reads the extracted
`/ghost_title.xpps` or the cached `ghost_title.bin`.
