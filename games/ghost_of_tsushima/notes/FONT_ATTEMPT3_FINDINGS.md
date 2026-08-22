# GoT DC "fOnk" font — Attempt #3 findings (2026-07-08)

Goal this round: inject 27 Hebrew glyphs (U+05D0–05EA) into the "fOnk" font and build a
modified `game.sprig.texmeshman`. **Outcome: the premise is void and full glyph-SHAPE
injection is blocked; I delivered a verified glyph-table CODEC, a lossless round-trip, and
a byte-safe codepoint-map injection DEMO, plus the exact blockers for attempt #4.** Every
claim was run against the real files with the repo `.venv` python. No file under
`F:/Games/Ghost of Tsushima DC` was modified.

## 1. `fOnk@0x156bff7` is NOT the font — RE-CONFIRMED (3rd independent check)
- Bytes at the tag: `…39 79 8e 29 8f fe f5 01 | 66 4f 6e 6b | 0b 8d 90 b1…`.
- Entropy of the 8 KB window = **7.44 bit/byte** (texture/compressed range).
- **Zero** 64-byte-strided ascending-codepoint runs anywhere in ±4 KB (a real glyph table
  has one). → fOnk is BCn texture bytes inside `custom_ag_bowl_china_001.msac.n.0.sps`.
- **Editing `game.sprig.texmeshman` cannot add a Hebrew glyph.** The whole
  "build a modified texmeshman/fOnk" task is targeting the wrong resource.

## 2. The REAL font = 64-byte glyph records in KCAP `.xpps` packages — codec built + verified
- `work/got_fonk.py` reads/writes the tables losslessly. **Identity round-trip PASS**:
  `write_table(read_table(m_lm_menu@0x4243e)) == on-disk bytes`.
- **Two record layouts** (both verified on real files):
  - **RICH** (m_lm_menu / per-menu UI fonts): `+0 u32 cp` · `+4 f32 metric` · `+8 u32==4`
    · `+12 u32 flag` · `+16 u32` · `+20 u16==0xf8` · **`+20..+45` a FIXED 24-byte
    descriptor** · `+46/+50/+54/+58 f32` (≈colour, ~1,1,1,1) · `+62 u16==0xffff`.
    Table ends at a `cp==0xffff` sentinel record; cp strictly ascending.
  - **CMAP** (core_common): near-all-zero 64-byte records, `+0 u32 cp`, `+62 u16==cp`
    (codepoint echoed), a small u16 pair near +50 — a codepoint→id MAP only, no metrics.
- **THE GLYPH OUTLINES ARE EXTERNAL (decisive, new this round).** In m_lm_menu's table,
  the glyphs share only a handful of distinct `+20..+45` blocks and **~36–55
  shape-different glyphs (space, M, W, l, i, m, N–Z…) carry the byte-identical 24-byte
  block.** A fixed 24-byte field that is identical across shape-different glyphs cannot be
  a per-glyph outline → the real outlines live in a separate `FontVerts` vertex buffer
  (the exe's `FontGlyphs`/`FontVerts` split). This is the crux blocker.

## 3. The Arabic-slot font table (the true Hebrew target) is NOT cleanly located
Scanned with a validated detector (format signature, not cp-seeded) so pure-Arabic tables
would be found:
- `core_common` (673 MB) = **968 Latin/Latin-Ext tables, cp ≤ 0x1a6; ZERO Arabic, ZERO CJK.**
- `core_tsu`/`core_iki`: the small (6–34-rec) "Arabic/Hebrew" hits fail the record-signature
  check → **mesh / vertex-buffer false positives**, not glyph tables.
- `ghost_title`: the big ascending runs are **consecutive-integer arrays** (cp
  0xbd0..0x1128 etc.) — index tables, not sparse font cmaps.
- CMAP hits "reaching CJK/Arabic" in core_common are **off-by-one misreads** of the Latin
  tables (detector locked at odd offset 0x…089 vs the real even 0x…08a → shifted cp reads).
- GoT is a Japanese game yet **no CJK glyph table is in the core packages either** → the
  Arabic AND CJK fonts are hash-keyed `SFontData` resources in a package not yet scanned
  (candidates: `game.sprig` in `gapack_misc_g`, `gapack_misc_m` 3.9 GB, `gapack_misc_t`), or
  resolvable only via the packman type-hash index.

## 4. What was BUILT + VALIDATED offline this round (`work/build_hebrew_fonk.py`)
- Re-verified fOnk-is-texture.
- Read the real m_lm_menu glyph table; **identity round-trip = byte-identical**.
- **SAME-SIZE codepoint-map injection demo**: remapped the 27 highest Latin slots
  (cp 0x55..0x6f) → **U+05D0..U+05EA**, keeping the table ascending (all Latin cp < 0x5D0),
  file size **unchanged** (no KCAP directory surgery). Scratch out:
  `work/_proof_out/m_lm_menu_hebrew_demo.sprig.xpps`.
- **Offline validation PASS**: re-decode → 27/27 Hebrew codepoints present, table ascending,
  **27/27 resolve to REAL (non-notdef) glyph records**, size == original.
- ⚠️ The injected records carry the **cloned Latin outline** of the slot they replaced (the
  descriptor is external), so in-game they would render as those Latin shapes, NOT Hebrew
  letters — and this is the Latin MENU font, not the Arabic slot. It proves the map
  mechanism + codec, **not** Hebrew rendering.

## 5. Exact blockers for attempt #4 (in order)
1. **Locate the Arabic-slot glyph table** — scan `game.sprig`/`misc_m`/`misc_t` with
   `work/got_fonk.find_rich_tables` (RICH) + `work/fonk_cmaphunt.py` (CMAP) for a clean
   Arabic-covering table, or crack the `game.sprig.packman` type-hash index to resolve the
   `SFontData` resource directly.
2. **Crack the external `FontVerts` buffer** — its location, the per-record REFERENCE field
   (a field that VARIES among the same-descriptor glyphs: candidates `+4`/`+12`/`+16`), the
   vertex struct + winding + coordinate scale (tessellated quads per `GENERATE_QUAD`).
3. **Synthesise 27 Hebrew outlines** from a TTF (fontTools `DecomposingRecordingPen` →
   flatten/tessellate to the FontVerts vertex format), append them, point 27 new records at
   them, mind the coord scale + winding (GoWR off-by-one lesson: verify the cp→glyph anchor).
4. **Grow + re-serialise the KCAP package** (fix its internal directory offsets), re-wrap
   DSAR/PSARC (`work/got_dsar.py`), deploy as the proven additive-override `.psarc` in
   `cache_pc/psarc`; activate with Text Language = العربية.

## 6. Tools (persist in `work/`)
- `got_fonk.py` — glyph-table codec (find_rich_tables / read_table / write_table /
  repurpose_same_size / is_rich_rec / is_notdef). Identity round-trip verified.
- `build_hebrew_fonk.py` — the deliverable: refute fOnk → round-trip → same-size 27-cp
  injection demo → offline validation → blocker report. Writes the scratch package.
- `fonk_reclayout.py` / `fonk_reclayout2.py` — record field analysis (proved outlines external).
- `fonk_hunt_script.py` / `fonk_hunt_strict.py` / `fonk_find_arabic.py` / `fonk_richhunt.py`
  / `fonk_cmaphunt.py` — table hunters (multi-cp, signature-strict, RICH, CMAP).
