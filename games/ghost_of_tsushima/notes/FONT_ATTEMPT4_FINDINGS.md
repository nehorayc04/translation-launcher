# GoT DC font — FontVerts crack, independent attempt #2 / round-2 (2026-07-08)

Goal: crack the external **FontVerts** glyph-outline format so Hebrew glyphs can be
synthesized. **Outcome: the round-1 model of the 64-byte glyph record is REFUTED, the
reference-field candidates (+4/+12/+16) are DISPROVEN, and no decodable FontVerts buffer
exists in any accessible package. The real text-font `SFontData` is a hash-keyed resource
not present in the 64-byte-record form anywhere scanned.** Every claim below was produced by
running the repo `.venv` python against the REAL files. No file under `F:/Games/...` was
modified. Tools: `work/fontverts_alt.py` (deliverable) + `work/fv_probe{1..7}.py` +
`work/fv_core_scan.py` / `fv_locate_font.py` / `fv_extract.py` / `fv_title.py`.

## 1. Corrected 64-byte RICH glyph-record model (m_lm_menu.sprig.xpps @0x41abe, cp 0x02..0x91)
| off | field | note |
|---|---|---|
| +0 | u16 cp (+2 u16=0) | ascending, 0xffff sentinel |
| +4 | f32 "metric" | **LINEAR RAMP** −0.156..−6.5 (Δ=−0.0078) over cp 0x27..0x7c => placeholders |
| +8 | u32 == 4 | const |
| +12 | u32 (= +14 u8 << 16) | **GROUP index**, only ~4 values {0,1,2,3} |
| +16 | u16 | **0xffff for ~90%**; sparse {0x0c..0x10, 0x75} for ~15 records |
| +18 | u16 == 0xffff | |
| +20 | u16 == 0x00f8 | const marker |
| +22..+45 | **24 B = 6× f32** | the ONLY per-real-glyph-varying field |
| +46 | f32 colour R (~0.7..1.0) | |
| +50/+54/+58 | f32 == 1.0 | colour G,B,A (white) |
| +62 | u16 == 0xffff | terminator/pad |

## 2. Round-1 reference candidates (+4/+12/+16) — ALL DISPROVEN as an outline pointer
- **+4** = the placeholder metric-ramp (constant Δ; not a per-glyph ref).
- **+12/+14** = a 4-value group index (cannot address ~40 distinct outlines).
- **+16** = 0xffff for the vast majority; a small sparse special-resource index for ~15
  records. Not a per-glyph outline pointer.
- The ONLY field that varies per real glyph is the **24-byte block +22..+45** (attempt #3 was
  right that this is the varying field; it was WRONG that a fixed 24-B block is shared across
  all shape-different glyphs — that sharing is only among the notdef/placeholder set).

## 3. The 24-byte block does NOT reference a co-located FontVerts (4 disproofs)
- decoded as **3 "big" f32** (glyph slots ≈ +28000, −710000, +1300; icon slots ≈ +1000..2700)
  **+ 3 "small" f32** (~0, ~0.7, ~0).
- **float0-as-byte-offset is DEAD**: round(float0) for A/B/I/O → 0x699c/0x6b57/0x6de9/0x6f1e,
  which are **all-zero** bytes. Not a vertex buffer.
- float1 is huge-negative (can't be an offset); no (offset,count) parse; the "big" floats have
  **fixed exponents** (0x46xx.. / 0xc92d.. ) => quantized/opaque, not geometry.
- **No glyph-outline buffer exists in m_lm_menu**: every low-entropy / small-float region is
  zeros, UI transforms, or bbox rects (e.g. [-800,950], [-651,285], [-420,224]) — never a
  dense outline. Region map = ~99% SPARSE + tiny (<8 KB) scattered float blocks; no texture.

## 4. m_lm_menu is a BUTTON-PROMPT / ICON menu, NOT the text font
- 55/149 records = the EXACT notdef block `6a3cde46c4552dc9d9ba99440000000000000000d3f67e3f`;
  ALL of cp 0x27..0x7c (every Latin A..Z / a..z) sit on the synthetic metric ramp = unused.
- Only ~36 real slots (cp 0x02..0x1e = controller/button-prompt icons) carry distinct data;
  the icon glyphs at cp 0x19..0x1e reference resource `+16=0x0c` with small-coord floats
  (position/scale-like), i.e. placed ICON quads, not letter outlines.
- **Consequence: m_lm_menu cannot provide a Latin O/L/i decode-proof** (it has no real letter
  outlines) — a critical correction to the round-1 plan that told attempt #4 to decode from it.

## 5. The 64-byte record format is UNIQUE to m_lm_menu (real font is hash-keyed elsewhere)
- `core_common.sprig.xpps` (673 MB): **0** glyph records despite 640,627 `04 00 00 00` hits.
- `core_tsu`, `core_iki`, `game.sprig`, `ghost_title`, `m_lm_training`: **0** rich glyph tables.
  (ghost_title's big "runs" are index arrays; its title text is a pre-rendered BITMAP —
  `bitmaps/sprobe_ghost_title_*`, `ghost_title_lut.psd` — not vector glyphs.)
- The generic record tail `0000803f 0000803f 0000803f ffff` appears in 2077 files but is just
  a white-RGBA+0xffff triple (colors/quaternions), NOT a glyph-record signature.
- => the real menu/subtitle **`SFontData` (FontGlyphs+FontVerts)** is a HASH-KEYED resource
  NOT stored in this uncompressed 64-byte-record form in any locatable package.

## 6. CONCLUSION + the only viable next steps
FontVerts CANNOT be cracked from the accessible KCAP data alone (this converges with attempts
#1–#3). To proceed, the next attempt must FIRST locate the real `SFontData` blob, which is
hash-keyed — two large sub-projects:
1. **Crack the `game.sprig.packman` 64-bit name-hash index** (attempt #1's open item) to
   resolve hash("SFontData"/the font resource) → its byte location, possibly inside a
   COMPRESSED KCAP sub-resource (so a raw signature scan will keep failing).
2. **Disassemble `GhostOfTsushima.exe`'s SFontData loader** (the `FontGlyphs`/`FontVerts`
   struct read + the `GENERATE_QUAD` tessellator @ the string cluster 0x1107f10) to get the
   record→verts reference field and the vertex struct authoritatively.

Do NOT spend further effort trying to decode m_lm_menu's 64-byte records as a vector font —
they are a menu-baked icon/placeholder structure with no co-located outline data.
