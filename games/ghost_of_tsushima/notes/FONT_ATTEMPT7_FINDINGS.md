# GoT DC font — round 7: store theories reconciled, codec confirmed exe-gated (2026-07-08)

**HEADLINE (honest): the FONT gate is STILL closed. No real Hebrew outline was injected. This round
RECONCILED the two competing outline-store theories from prior rounds and REFINED the blocker from
"encrypted (hopeless)" to "proprietary bit-packed quantization (needs the exe's decoder)". The
deployable STAGE-2 mechanism-proof (`gapack_misc_g_mechproof.psarc`) is re-validated and remains the
deliverable. The SOURCE half of the pipeline (david.ttf -> 27 Hebrew outlines) is now implemented and
proven offline.** All facts run with the repo `.venv` python against the cached real `ghost_title.xpps`
(10,103,200 B, md5 `3d5d62aa44dacd44640ed132493ab6db`). No file under `F:/Games/...` was modified.
Tool: `work/build_hebrew_glyphs.py` (`--contours`/`--mechproof`/`--real`).

## 1. The two prior store theories — RECONCILED
- **`vertstore.py` (round 3):** outline store = "store8" @0x8b0000..0x8b74b0 (29,872 B, 3733 x 8-byte
  units), declared max-entropy/opaque. **CORRECT location.**
- **`ght_sections.py` (round 6):** vertex store = the tail kind2 @0x97c8d0..0x9a2750 (155 KB),
  "normalized f32 in [-1,1]". **REFUTED this round:** only 48% of its floats are in [-1,1], 32% are huge
  (~5e31), 16% exact-zero, and it contains a repeated UNIT QUATERNION `[-0.8133,-0.3398,0.4724,0.1522]`
  x3. That is title-card sprite TRANSFORM data (pos/quat/scale), NOT glyph vertices. The "normalized
  floats" claim was cherry-picked from the head of the region.
- **Whole-file window sweep (0x850000..EOF):** exactly THREE dense regions exist — store8 (ent 7.96),
  `kind3` @0x8f43b0 (264 KB, ent 7.25), `kind18`/tail (ent 7.1-7.2). Everything else is low-entropy
  (ent 1.5-5) cmap + sprite-transform + keyframe data. ghost_title.xpps simply does not hold enough
  dense data for thousands of full-fidelity multi-script outlines unless they are heavily quantized
  (=> store8) — corroborating that store8 is the packed vertex store.

## 2. store8 is PACKED, not encrypted (new, decisive)
Byte analysis of 0x8b0000..0x8b74b0:
- **Repeats:** one 8-byte unit appears **111x**, another 111x, another 110x; a 16-byte pair appears
  **56x**; a doubled unit `af4f663e9270bd11 x2` appears 28x. 2450 distinct of 3733 units.
- **Periodicity:** dominant byte-match lag = **8**, then 16, 24, 32, 48 (all multiples of 8) — a clean
  8-byte record stride. (Encryption/whitening would show ~zero repeats and a flat lag profile.)
- **Not standard-compressed:** lead byte `0x1f`; `zlib` (wbits 15/-15/31/47), `lz4.block`, and
  oodle-lead all fail. **Not plain coordinates:** as f16/i16/f32 the units span +-65440, ~50% out of
  [-2,2], and a known glyph's slice traces to unbounded garbage. Every plaintext-coordinate hypothesis
  (i16, i8-delta, f16, f32, 11-bit, cumulative-delta) fails to trace a bounded closed contour
  (this round + `vertstore.py`).
=> store8 is a **proprietary bit-packed/quantized** vertex format. Structured and addressable, but its
per-unit bit layout is only defined in the exe's decode path.

## 3. Resolution chain (shape now known)
`cmap record +16` = outline-id (real glyphs **1269..3496**, 283 distinct; +18 = 0..56 count/sub-index)
-> **descriptor table @0x8aed12** (16-byte stride: ascending outline-id at +6, small vertex/index COUNT
at +8 = 23,28,36,42..) -> the store8 units + the plaintext **u16 index buffers @0x851000** (ascending
vertex indices) / @0x852c00 (triangle indices). So *which* bytes belong to a glyph is derivable; *how*
those 8-byte units encode the vertices is the single missing piece.

## 4. THE BLOCKER (exact) — unchanged in kind, sharper in detail
The **store8 8-byte-unit bit layout** (quantization scheme + how a glyph's vertex run + its u16 index
list reconstruct the contours). It is not offline-recoverable by known-plaintext (exhausted rounds 3+7).
Crack it by **RE of `GhostOfTsushima.exe`'s SFontData / FontVerts / GENERATE_QUAD loader** (image base
`0x140000000`; the FONTK handler cluster near exe `0x011628F8`; the string cluster near `0x1107f10`).
That is an exe-disassembly sub-project, outside offline KCAP analysis.

## 5. What IS done / ready
- **STAGE 1 (SOURCE) implemented + proven:** `build_hebrew_glyphs.py --contours` extracts the 27 Hebrew
  outlines U+05D0..05EA from `C:/Windows/Fonts/david.ttf` (fontTools; quadratics flattened; em-normalized)
  and ascii-rasters them to recognizable letters (alef/bet/shin verified). The moment the store codec is
  known, only the ENCODE + repoint + KCAP-growth remain (all mechanically specced in rounds 5/6/7).
- **STAGE 2 (MECHANISM) deployable:** `gapack_misc_g_mechproof.psarc` (built by
  `work/build_font_mechproof.py`, gold-validated) re-verified: 2205 files, /ghost_title.xpps 10,103,200 B,
  27 Hebrew cps intact, refs now **27/27 distinct** (shipping 3/27 degenerate), other files byte-identical.
  Deploy in-place (back up `gapack_misc_g.psarc` first) with Text=Arabic and look at the menu Hebrew:
  **Arabic letters appear** => the cmap ref addresses the shape (repoint works; only the store codec
  remains). **Still tofu** => the shape is keyed by codepoint in an external store (record-editing dead;
  the exe-RE must target that store). Either outcome pins the exe-RE target precisely.

## 6. Do NOT re-attempt (dead ends, verified)
- Decoding store8 / kind3 as floats/int16 or via zlib/lz4/oodle (all fail).
- Treating the tail kind2 as the vertex store (it is sprite transforms).
- Editing the cmap `+16/+18` to ADD a shape (adds no geometry; only repoints to an existing outline).
- Treating the 6-float record `geom` as an outline (bbox/advance only).
