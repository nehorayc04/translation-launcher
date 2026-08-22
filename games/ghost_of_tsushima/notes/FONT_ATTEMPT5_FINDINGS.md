# GoT DC font — round-2 injection attempt (#5): the "Arabic table" is a CMAP, not outlines (2026-07-08)

**HEADLINE (honest): FontVerts is STILL not cracked, and the round-2 `arabic_font_table.md`
model is REFUTED. The 64-byte "glyph records" in `ghost_title.xpps` are a CODEPOINT MAP, not a
glyph-shape table, so there is NOTHING in them to repoint at a Hebrew outline. `ghost_title.xpps`
is an animated TITLE-CARD asset (a pre-rendered bitmap logo + glyph-sprite transforms + `keyframe()`
animation curves + `hero/young_hero/heroine` style defs), not the vector-outline font store. The
real glyph outlines are a hash-keyed, packed/opaque resource that a raw signature scan cannot
decode.** No real Hebrew glyph was produced. No file under `F:/Games/...` was modified. Every claim
was run with the repo `.venv` python against the cached real `ghost_title.xpps` (10,103,200 B).
Tools (all in `work/`): `fv_analyze.py`, `fv_struct.py`, `fv_outline.py`, `fv_sections.py`,
`fv_bigsec.py`, `fv_map.py`, `fv_verts.py`, `fv_trace.py`, `fv_diff.py`, `build_hebrew_font.py`.

## 1. The DECISIVE proof: the 64-byte records are a CMAP (codepoint enumeration)
`work/fv_diff.py` dumped the FULL 64 bytes of three real letters from the first `ghost_title` table
(@0x866952) that unquestionably render distinct shapes in-game:
```
A    @0x867952: 41 00 00 00 ... 04 00 27 00 ff ff f8 00 ...(all zero)... 80 3f×4 ff ff
O    @0x867cd2: 4f 00 00 00 ... 04 00 27 00 ff ff f8 00 ...(all zero)... 80 3f×4 ff ff
i    @0x868352: 69 00 00 00 ... 04 00 27 00 ff ff f8 00 ...(all zero)... 80 3f×4 ff ff
```
**A vs O and A vs i differ in EXACTLY ONE byte: +0, the codepoint.** Everything else is byte-identical.
The whole printable-ASCII range shares `+14=4, +16=0x27(39), +18=0xffff`, zero geometry, white colour.
A structure where A/O/i are identical except the codepoint **cannot** carry per-glyph outlines — it is
a codepoint→class map. `+14` is a coarse class/page that increments in big blocks (cp 0x01–0x10 → 0,
0x11–0x13 → 1, … printables → 4; Hebrew block → 104; Arabic → 129/130), `+16` is a shared per-block
attribute (39 for all Latin), NOT a per-glyph shape id.

⇒ **The round-2 claim "the 27 Hebrew letters share only 3 (+16,+18) refs ⇒ that is the tofu" is a
red herring.** Latin A/O/i ALSO share one ref (4,39,0xffff) and render perfectly. Sharing a ref in
this table does not cause tofu, and editing `+16/+18` adds no shape. The Hebrew records DO exist in
the cmap (0x5d0–0x5ea present) — the cmap is not the gate.

Why Hebrew tofus while Arabic renders (from THIS asset's data): Latin/Arabic cmap entries carry
`geom=0` (their sprite/shape comes from the asset's real glyph set), whereas the 27 Hebrew entries
carry a NON-zero fallback marker `geom=[x, y, 5.0]` (e.g. alef `[262,-348,5]`) — a "draw a 5-unit
box at (x,y)" notdef → scattered boxes = the tofu. The fix is a real outline, which is not here.

## 2. What `ghost_title.xpps` actually is (structure, from `fv_struct/sections/map/verts/trace`)
- KCAP header: `@0x18→0xb8`, `@0x1c→0x198` (section dir), `@0x28→0x250`, `@0x2c→0x9a2750` (trailer).
- **`@0x198` = a 13-entry section directory**, 12-byte entries `[u16 flag=0x10][u16 kind][u32 size][u32 off]`:
  kind1 metric/curve blobs, **kind3 @0x8f43b0 (0x40590 B)** = a glyph-id list + pointers to style defs
  + packed binary, **kind18 @0x934940 (0x47f90 B)** = a **64-bit-hash → offset index** (`[8-byte hash]
  [u32 ptr][u32 0]`, the packman-style index), plus small kinds 6/11/26.
- The 8.4 MB bulk (0x0–0x866952) is the pre-rendered **title bitmap**; the 0x89xxxx region is arrays
  of glyph-sprite **transforms** `[pos.xyz, quaternion.xyzw, scale 1,1,1]`; the 0x8ec000–0x8f4000 region
  is ASCII **`keyframe(TIME_OF_DAY,…)` / `keyframe(dist(water_pos…))`** animation-curve expressions;
  `hero`/`young_hero`/`heroine` style names sit at 0x8f3e20. This is a title-card composition asset.
- The remaining tail (0x8f4000–0x9a0000) is packed high-entropy binary (byte-entropy ~7.2; **not raw
  LZ4 and not zlib** — `lz4.block.decompress` fails on kind3/kind18/every HIENT block).

## 3. Why the outline is not recoverable here
- The only per-glyph-varying field in a record is the 24-byte `geom` (6 f32). **6 floats cannot encode
  a full Arabic/CJK/Devanagari outline** (dozens of points) — so `geom` is bbox/advance/marker metadata,
  never the contour. The game ships 34 languages incl. Devanagari/Bengali/Tamil/Thai/CJK, all of which
  DO render, so their outlines exist — but in the packed/hash-keyed store, not in any signature-scannable
  64-byte-record table.
- The real vector font (`SFontData`=`FontGlyphs`+`FontVerts`, tessellated by the exe's `GENERATE_QUAD`
  at the string cluster 0x1107f10) is a **hash-keyed resource** (kind18 is literally a 64-bit-name-hash
  index) whose vertex payload is packed/quantized (entropy ~7). It is not addressable by a raw scan.

## 4. THE BLOCKER (exact) + the only viable next steps
**Blocker: the FontVerts vertex encoding + the record→vertex resolution are unknown, and the vertex
payload is a hash-keyed, packed/quantized blob (not raw LZ4/zlib, not plain f32/i16 arrays).** Cracking
it requires ONE of:
1. **Disassemble `GhostOfTsushima.exe`'s SFontData loader** — read the `FontGlyphs`/`FontVerts` struct
   + the `GENERATE_QUAD` tessellator (@ the string cluster near 0x1107f10) to get the vertex struct,
   winding, coord scale, and the record→vertex reference authoritatively. (Highest confidence; it is an
   exe-RE sub-project, outside offline KCAP analysis.)
2. **Resolve the packman 64-bit-name-hash index (kind18)** to the real font resource + reverse the
   section codec that packs the vertex payload. (Also large; the codec is unknown.)
3. **Prove which package the UI text font actually is** (ghost_title is the title card). Re-scan
   `gapack_misc_g` (2202 .xpps) + the core packages for a package whose records carry a *decodable*
   per-glyph outline (a content signature — dense low-entropy contour floats + a per-glyph index —
   NOT the cmap signature `+20==0xf8/+62==0xffff` used so far, which only finds codepoint maps).

Until one of those lands, **a real Hebrew vector glyph cannot be synthesized or injected**, so the
font gate stays closed. Do NOT spend more effort on: editing the cmap `+16/+18` (adds no shape),
`m_lm_menu` (placeholder/icon), or treating `geom` as an outline (only 6 floats).

## 5. Deploy recipe — VALID and ready FOR WHEN the outline format is cracked (not before)
The container + deploy path is proven (the Latin text-marker rendered in the menu-proof). Once real
Hebrew outlines can be written into the font package `P.xpps` (ghost_title, or the true UI-font .xpps
found via §4.3):
1. Edit `P.xpps` in place: append the 27 Hebrew outlines to the vertex store, add/repoint the 27
   `U+05D0–05EA` glyph entries, and — if the package grows — fix the KCAP section-dir sizes/offsets
   (`@0x198` entries) + trailer `@0x2c`.
2. Wrap back into a DSAR/PSARC override: if same-size, `work/got_dsar.py patch_inner` (surgical, only
   the changed chunks re-LZ4'd, header unchanged). If grown, rebuild the inner PSARC then
   `got_dsar.wrap(inner, boundaries)` (LZ4 compType 3, `55*7` filler, 16-byte-aligned `PADDING*` gaps).
3. Name the override to sort AFTER the shipping `gapack_misc_g.psarc` (e.g. `zzz_hebrew_font.psarc`)
   and drop it in `F:/Games/Ghost of Tsushima DC/cache_pc/psarc/`; the engine mounts `*.psarc`
   alphabetically, later overrides earlier. Revert = delete the one file.
4. Activation: in-game Settings → Options → General → Text Language = **العربية** (Arabic slot).
