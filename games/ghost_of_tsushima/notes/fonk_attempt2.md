# GoT DC font — independent attempt #2 (2026-07-08)

Goal: crack the "fOnk" font. **Outcome: the container + LZSS are fully cracked; the "fOnk@0x156bff7"
premise is DEBUNKED (red herring); the real font is a hash-keyed `SFontData` vector resource that was
NOT yet located.** Everything below is verified by running Python against the real files
(`work/fonk_decode_alt.py`).

## 1. `fOnk@0x156bff7` is COINCIDENTAL — not the font (high confidence)
- `b"fOnk"` occurs **exactly once** in 108 MB (≈ chance for a 4-byte string: 108M/2³² ≈ 0.025 → a lone
  hit is unremarkable). It sits in a **RAW high-entropy MESH region** (bytes
  `…39 79 8e 29 8f fe f5 01 | 66 4f 6e 6b | 0b 8d 90 b1 39 79 8e…`): no zero/count fields, no header.
- The game's actual font tag is **`FONTK`** (exe @0x11628f8, in a list of render-resource kinds:
  Minimap/StampMap/TravelMap/Compass/**FONTK**…). `fOnk` ≠ `FONTK`, and `fOnk` is **not in the exe at all**.
- `font`/`Font`/`FONT`/`glyph`/`SFontData`/`FONTK` = **0 occurrences** in the raw texmeshman.
- Sucker Punch resources are keyed by **64-bit hashes**, not 4-char ASCII tags (see the directory
  entry `id` + 3 trailer hashes) → a stray ASCII "fOnk" is not a resource tag.
- Verify: `python work/fonk_decode_alt.py fonkcheck extract/game.sprig.texmeshman`.

## 2. Container = "NAMS" package — CRACKED + verified
`game.sprig.texmeshman` (from `gapack_misc_g.psarc`) layout:
```
0x00  "NAMS"  | 0x04 u32 ver=0x00011d01 | 0x08 u64 hashA
0x1c  u32 entryCount = 27562
0x20  u32 = 653529
0x24  u32 dirOffset  = 1364025 (0x14d039)      # RAW resource directory starts here
0x28 .. 0x14d039   LZSS-compressed hashed-name/metadata pool  (-> 4,581,806 bytes)
0x14d039 .. 0x369cbf   RAW texture directory: 19819 SBitmap (.sps) entries
0x369cbf .. 0x16cd6b8   "gap" = MESH data (vertex/index buffers) + more dir records + probe floats
0x16cd6b8 .. 0x5c23798  RAW texture blobs (BC7 pixel data, NO XTBS wrapper; format in dir params)
0x5c23798 .. EOF        further raw data / dir records
```

### 2a. LZSS codec (Okumura, N=4096) — verified byte-clean on the asset-name table
- flag byte, **LSB-first**; bit==1 → literal (1 byte); bit==0 → match (2 bytes) `b0,b1`:
  `pos = b0 | ((b1 & 0xF0) << 4)` (absolute ring index), `len = (b1 & 0x0F) + 3`.
- ring 4096 bytes, write pointer **r starts at 0**.
- Proof: `hero_arc`+ring[64..]("her")+ring[68..]("_ar")+lit"mor_th"+lit"ighcover" =
  `hero_archer_armor_thighcover`; whole table decodes to clean names
  (`eagle_costume_pants_mtl`, `reiko_shirt`, `samurai_elite_helmet_10`, `ronin`, `kamakura`…).
- The metadata pool then becomes a **hashed-name string pool** (still printable; NOT a decode bug).

### 2b. Resource-directory entry (SBitmap textures) — verified (19819 parse cleanly)
```
u64 id                 # e.g. 0x00000076badbad13
u32 zero
u32 dataOffset         # byte offset of raw blob (0x16cd6b8..0x5c23798)
u32 zero
u32 nameLen
char name[nameLen]     # "custom_cv_straw_coaster_001.msac.d.0.sps"
u64 hash1, hash2, hash3
u8  params[12]         # texture format/dim (e.g. 00 06 01 0f 00 01 00 01 01 00 09 00)
```
Entries chain at `24 + nameLen + 36`. The parser stops at the first mesh-interlude record
(the ~7743 remaining entries of the 27562 use a different, not-yet-cracked shape).

## 3. The REAL font (per GhostOfTsushima.exe)
- Type **`SFontData`** — sibling of `SBitmap`/`SLoadable`/`SVldbData`/`STbdbData` (resource-type list @0x1157db8).
- **Vector**: allocation categories **`FontGlyphs` + `FontVerts`** (@0x1107f10), i.e. glyph OUTLINES
  tessellated to 2D vertex meshes — NOT a TTF, NOT a DDS atlas.
- Text system: `FONT_KIND`,`FONT_SIZE`,`SET_TEXT_DIRECT`,`H_JUST`,`V_JUST`,
  `EXTRA_CHARACTER_SPACING`,`LARGE_FONT_SIZE_FACTOR` (@0x12784f0).
- Loaded as a hash-keyed resource. `AddFontMemResourceEx`/`CreateFontW`/`Launcher_Font` are the
  **launcher** GDI path (irrelevant to in-game UI/subtitles).

## 4. Where is the glyph data? (open — ruled out the obvious)
- **Not a named file**: across all ~50 psarcs the only "font" is `/bitmaps/debugfont.dds` (debug bitmap).
- **Only 4 container files exist**: game.sprig.{packman,texmeshman}, pulse.sprig.texmeshman (UI
  textures), all_shaders.texmeshman (shader luts + debugfont ref). pulse/all_shaders have **no cmap**.
- **No sorted cmap** (strided ascending codepoints over ASCII+Arabic+Latin) anywhere in the raw
  texmeshman, nor in the first ~4.6 MB of correctly-decompressed metadata.
- The exe has `{u32 codepoint}` ascending tables @0x110c000–0x1112000 (ASCII/Latin/Greek/Cyrillic up
  to 0x531, val2 = small category enums) — these are **Unicode script/category property tables** used
  by the text system, **not** the font's glyph store (no vertex/outline data there).
- **Directory is textures-ONLY**: a resync-scan of the whole directory+gap region found 21,901
  named records — **100% `.sps` textures** (msac.d/s/n/m/g/ao/…, spabmp, spnbmp, psd), **0 non-texture
  names**. So meshes AND the font are stored as **UNNAMED, hash-keyed** blobs (only textures carry
  names) → the font cannot be found by string/name at all; it needs the type-hash/index system.
- **Most likely location**: inside `game.sprig.texmeshman`'s **mesh region** (the 3.6–24 MB "gap",
  incl. the fOnk neighborhood @22.4 MB) — glyph outlines are 2D meshes, so the font is stored/keyed
  like a mesh (`FontVerts` = vertex buffer, `FontGlyphs` = per-glyph metadata table). Finding it
  requires cracking the **mesh-directory** format (the interleaved float+record structure the texture
  parser stops on) or the **packman** master index (its 2nd section is an ascending u16 index table).

## 5. Injection plan (revised — the fOnk lead is dead)
1. **Do NOT edit 0x156bff7.** It is mesh bytes; patching it corrupts a mesh, not the font.
2. **Menu-proof first (already built by recon):** deploy Hebrew in the Arabic `.xpps` slot and screenshot.
   If Hebrew renders → the Arabic-slot font already covers U+05D0–05EA → **zero font work** (done).
3. **If tofu (expected):** locate the `SFontData` resource:
   - crack the mesh-region directory (parse past 0x369cbf handling float/record interludes) and/or the
     packman 2nd section; find the entry whose data is glyph metrics + FontVerts (a small metrics/cmap
     table followed by a 2D-vertex buffer), not a 3D mesh.
   - decode its cmap (codepoint→glyph) + per-glyph vertex outline format (2D points; likely float32 or
     int16 pairs with a winding/contour list — verify against a known Latin glyph 'A').
   - synthesize 27 Hebrew glyphs (U+05D0–05EA) as 2D outlines from a Hebrew TTF (fontTools
     `DecomposingRecordingPen` → flatten curves → triangulate/point-list to match the format), add
     glyph records + cmap entries.
4. **Repack**: the resource lives in the texmeshman; a growing edit needs a texmeshman rebuild (fix the
   directory dataOffsets that shift), then re-wrap DSAR/PSARC (`work/got_dsar.py` + tlou2 psarc_write).
   A constant-size glyph-repurpose (overwrite spare Arabic-slot glyph records, like GoWR) avoids the
   rebuild — preferred once the format is known.
5. **Deploy**: additive override `.psarc` into `cache_pc/psarc/` (proven), Text Language = العربية.

## 6. Tools
- `work/fonk_decode_alt.py` — LZSS decoder + NAMS directory parser + `fonkcheck` (verified):
  `info` / `dump [N]` / `lzss [K]` / `fonkcheck`.
- Decompressed metadata blob (scratch): `…/scratchpad/texmeshman_decomp.bin` (371 MB whole-file
  one-stream decode — VALID only for the first 4.58 MB = the real LZSS metadata; the rest is a
  desynced decode of raw blobs, kept only as a scratch artifact).
