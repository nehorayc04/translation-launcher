# GoT DC "fOnk" font — Attempt #1 findings (2026-07-07)

**Headline: the recon premise is REFUTED. `fOnk` @ 0x156bff7 is NOT the font.** It is a
coincidental 4-byte match inside a **BCn texture** (`custom_ag_bowl_china_001.msac.n.0.sps`,
a china-bowl normal map). The real in-game font is a hash-referenced **`SFontData`** resource
(engine tag **`FONTK`**, sub-sections `FontGlyphs`/`FontVerts`) embedded in a **KCAP** package —
it is **not** in `game.sprig.texmeshman`, **not** a TTF, and **not** named "font" anywhere.

All claims below were verified by running the repo `.venv` python against the REAL files
(`work/fonk_a1_*.py` + `work/fonk_decode.py`). No game file was modified.

---

## 1. The fOnk chunk: offset / size / compression (task deliverable D1+D2)

- **Container:** `extract/game.sprig.texmeshman` = a **NAMS** ("SMAN" LE) manifest, 108,445,889 B.
  Header: `"NAMS"` + u32 version `0x00011d01` + 2×u64 pkg-hash + u32 0 + **u32 count=27562** +
  u32 653529 + u32 1364025, then a name table @0x28 (names framed `[0xff][≤8 bytes]`), then a
  resource directory of `{u32 dataOffset, u32 0, u32 nameLen, char name[]}` entries.
- **`game.sprig.packman` is NOT an offset index.** It is a flat, sorted **u64 asset-hash
  directory** (countA=3621 + countB=3614), grouped by a constant high-48-bit namespace
  (`0x80013e8a3870`, `0x80080b4d…`, …), with a trailing per-entry byte table (values `0x21,0x22,
  0x02,0x0c,0x0e,0x12…`). It contains **no** offset near 0x156bff7 (searched u32+u64). So the
  fOnk offset comes from the NAMS directory, not the packman.
- **The fOnk chunk (as a "font") does not exist.** `fOnk`(66 4f 6e 6b) occurs **exactly once**
  in the whole 108 MB file (random expectation ≈0.025). The NAMS directory entry that owns it:
  - resource **`custom_ag_bowl_china_001.msac.n.0.sps`**, dataOffset **0x156b6b0**, size **2744 B**
    (next resource `.s.0.sps` @0x156c168). fOnk sits **2375 B into it**. Verified:
    `fonk_decode.py locate … 0x156bff7` → owning resource + `inside=True`.
  - Sibling channels of the same material: `.d/.g/.m/.n/.s.0.sps` (diffuse/gloss/metal/normal/spec).
- **Compression = NONE (raw texture).** The region **zlib-recompresses to ratio 0.827** (would be
  ~1.0 if already compressed); **no** zlib / raw-deflate / lzma / bz2 / lz4-frame / lz4-block codec
  decodes it at any offset 0..20. Entropy 7.68 (compressed data is ~7.95+). Byte histogram is
  dominated by `0xff/0x00/0x01/0xfe/0x10/0x90` and **autocorrelation has a hard 16-byte period**
  (peaks at 16,32,48,64,112,784,5488 = 16×{1,2,3,4,7,49,343}) with 37% cross-block identity —
  the classic signature of **BCn 16-byte texture blocks**, not a compressed stream and not vector
  glyph data. So `fOnk`'s packman/offset question resolves to: **it's texture pixel bytes.**
- **The `b1 39 79 8e` and `rRxF` "markers"** are just recurring bytes inside the texture blob
  (unique to this ~46 KB neighbourhood of texture data); `MJwN`/`FwN?`/base64-looking tokens are
  random BC-block bytes. Not structural font markers.

## 2. Why it's not a font — corroborating negatives (all verified)

- **No codepoint ladder anywhere.** Whole-file scans for ascending u8 and u16 runs in
  [0x20..0x6ff] (Latin/Arabic ranges), all strides 1..32, found **zero** — there is no cmap here.
- **No embedded TTF/OTF.** Validated sfnt/OTTO/ttcf/wOFF magic hunt (checked real table tags
  `cmap/glyf/head/…`): **0** valid fonts in the file (confirms recon's own sfnt result).
- **No font strings.** `FONTK`/`SFontData`/`FontGlyphs`/`FontVerts`/`Font`/`glyph`/`cmap` =
  **0 occurrences** in `game.sprig.texmeshman`.
- **The whole file is textures+meshes.** Resource middle-extension histogram: **22,706 `.msac`**
  (materials) + `.sps` (texture pixel streams) + 10 `.xmesh` + 212 `.psd` + a few `.png/.dds/.bmp`.
  No font resource type. Every "font-ish" name is a texture (`debugfont.dds`, `ui_*`, decorative
  `*_kanji` prop textures, the `lang_*.msac.d.0.sps` localized UI rasters).

## 3. Where the REAL font is (lead for attempt #2)

From `GhostOfTsushima.exe` string/type tables:
- **`SFontData`** sits in the resource-**TYPE** table next to `SBitmap`, `SVldbData` → the font is
  a resource of type `SFontData`.
- **`FONTK`** sits in a package/section **TAG** list next to `PEWBK`, `PUBK`, `TravelMap`,
  `Compass` → the on-disk font tag is `FONTK` (5 bytes `46 4f 4e 54 4b`), **NOT** `fOnk`. The recon
  conflated the two.
- **`FontGlyphs`/`FontVerts`** are named sub-sections; **`FONT_KIND`/`FONT_SIZE`/`LARGE_FONT_SIZE_
  FACTOR`/`SET_TEXT_DIRECT`/`GENERATE_QUAD`/`H_JUST`/`V_JUST`/`EXTRA_CHARACTER_SPACING`/`TEXT_EFFECT`**
  are runtime text-draw params (the engine tessellates glyph outlines to quads on the GPU).
- **`CreateFontW`/`AddFontMemResourceEx`/`BitBlt`/`GetTextExtentPointW`/`RemoveFontMemResourceEx`**
  cluster with `GetUserNameW`/`RegOpenKeyExW` and `Launcher_Font` → this is the **Nixxes launcher's**
  GDI text path, a SEPARATE font from the in-game one. (So the `AddFontMemResourceEx`⇒"there's a
  hidden TTF" idea applies to the launcher, not the in-game font.)

**KCAP packages reference resource types by HASH, not name.** All `.xpps` are `KCAP` ("PACK" LE)
containers (used for text `lang_*_text.xpps`, characters `hero.xpps`/`adachi.xpps`/`khan.xpps`,
shaders `all_shaders.xpps`, locations, etc.). Grepping `core_common.sprig.xpps` (673 MB),
`core_tsu/iki`, `m_lm_menu.sprig.xpps`, `ghost_title.xpps`, `downloaded.sprig.xpps` for
`FONTK`/`SFontData`/`FontGlyphs` = **0 literal hits** → types are hash-referenced. So the font is
inside a KCAP package as a hash-typed `SFontData` blob.

**Attempt #2 plan to actually find + crack the font:**
1. Recover Sucker Punch's name-hash algorithm (the packman/manifest use 64-bit hashes; the KCAP
   directory keys types/resources by the same family). Candidates to test against the known
   packman keys: FNV-1a-64, CityHash, a CRC64, or a SP-custom mix — brute a few known
   (name→hash) pairs from the NAMS manifest (we have literal names AND their entries) to identify it.
2. Parse the **KCAP** directory (magic `KCAP`, u16 kind @6, then a resource table). Enumerate
   resources by type-hash; find the entry whose type-hash == hash("SFontData") (or the `FONTK`
   tag). Most likely host packages: `core_common.sprig.xpps`, `m_lm_menu.sprig.xpps`, or one of
   game.sprig's 2,202 xpps in `gapack_misc_g`.
3. Only THEN decode `FontGlyphs` (glyph records: codepoint→outline index/advance/bbox) +
   `FontVerts` (outline vertices — the earlier float16 read gave plausible coords 24.25/-44.5/-40.5
   but was measured on TEXTURE data, so ignore it; re-measure on the real SFontData blob).
4. Inject 27 Hebrew glyphs (U+05D0–05EA) into `FontGlyphs`+`FontVerts` (likely by repurposing 27
   Arabic glyph slots to keep counts constant, à la GoWR), repack the KCAP, re-wrap DSAR/PSARC.

## 4. Tools written (persist in `work/`)

- `fonk_decode.py` — **the deliverable decoder/verifier.** Parses the NAMS container manifest and
  maps any byte offset → owning resource. `info <texmeshman>` prints the fOnk verdict; `locate`/
  `dump <off>` prove containment. (It decodes the CONTAINER, which is what disproves the font claim;
  there is no fOnk glyph table to decode.)
- `fonk_a1_scan.py` / `_packman.py` / `_struct.py` / `_nams.py` / `_region.py` / `_deep.py` /
  `_desc.py` / `_manifest.py` / `_realfont.py` / `_verify.py` / `_findfont.py` / `_toc.py` /
  `_xpps.py` / `_locate.py` — the step-by-step analysis scripts (entropy, codec tests,
  autocorrelation, manifest harvest, exe string grep, archive-TOC grep, KCAP candidate search).

## 4b. THE REAL FONT — FOUND + FontGlyphs format cracked (2026-07-08)

Hunting a **codepoint ladder** (ascending Latin cp at a fixed record stride — which the
texture lacks but a real glyph table must have) LOCATED the real font tables inside the KCAP
packages. Verified with `work/fonk_a1_hunt_ladder.py` + `fonk_a1_glyphtable.py` +
`fonk_a1_corefont.py`.

- **FontGlyphs record = 64 bytes, fixed.** Layout (verified on `m_lm_menu.sprig.xpps` @0x4223e,
  104 records, and identical in `ghost_title.xpps` @0x867952 and core_common):
  - `+0  u16 codepoint` — **stored DIRECTLY, ascending, matches the glyph (A record cp=0x41).
    NO off-by-one** (unlike GoWR). Table terminated by a `cp=0xffff` sentinel record.
  - `+6  float16` — per-glyph metric (bearing/offset; A=-0.469, B=-0.484, C=-0.5, a=-1.875).
  - `+8  u16` (=4), `+14 u16` (=1), `+16 u32` (=0xffffffff), `+20 u16` (=0x00f8) — mostly constant.
  - `+22..+46` — ~24 B per-glyph **geometry** (outline/verts ref or packed coords; zero for
    simple glyphs like 'a').
  - `+46 f32≈0.998, +50/+54/+58 f32=1.0` — a 4-float **color (white)**; `+62 u16=0xffff` pad.
- **It is a VECTOR font, not an atlas.** core_common has **80** of these tables but **zero**
  `SBitmap`/`atlas`/`.sps` references → the glyph geometry is outline/vertex data (the exe's
  `FontVerts`), consistent with `GENERATE_QUAD` tessellating outlines at draw time. So Hebrew
  injection is glyph-OUTLINE synthesis (harder than the SM2/WD2/GoWR atlas-blit class).
- **Codepoint coverage of the tables found:** `m_lm_menu` = **Latin only** (0x20–0xff, 104
  glyphs). `core_common` = **80 Latin-family tables**, cp **0x1–0x1a6** (control-glyphs + ASCII +
  Latin-1 + Latin-Extended) — multiple sizes/weights. **NO Arabic/Hebrew/CJK table in
  core_common.** So the Arabic-slot font (our Hebrew target) is a **separate per-script font
  package** not yet located.

## 4c. Injection target for attempt #2

1. **Find the Arabic-covering 64-byte glyph table** (records with cp in 0x600–0x6ff). It is NOT
   in core_common; scan the remaining KCAP packages (game.sprig's 2,202 xpps in gapack_misc_g,
   the big gapack_misc_m/g/i/t, or a per-language/Arabic font package) for a 64-byte table whose
   cp reaches 0x600+. Reuse `fonk_a1_hunt_ladder.py` seeded on an Arabic cp instead of 'A'.
2. **Crack `+22..+46`** — the per-glyph geometry: determine if it references a `FontVerts`
   outline array (offset+count) elsewhere in the package, and the vertex coord type (float16
   likely) + winding, so a Hebrew outline can be synthesized.
3. **Inject 27 Hebrew glyphs (U+05D0–05EA):** either (a) **repurpose** 27 Arabic 64-byte records
   → Hebrew cp + Hebrew outline verts (GoWR-style, keeps counts constant; Hebrew 0x5d0–0x5ea sorts
   BEFORE Arabic 0x600 so re-sort or pick low Arabic slots), or (b) **insert** 27 records keeping
   the table ascending + fix the count field + append verts. Since KCAP grows freely (no downstream
   stream constraint proven yet — verify), insertion is likely OK.
4. Repack the KCAP package, re-wrap DSAR/PSARC (writers exist), deploy as the additive override.

## 5. Bottom line

- **decoded (fOnk as font): NO** — fOnk isn't a font; it's texture bytes. Proven.
- **compression: NONE** — raw BCn texture (zlib 0.827, no codec, 16-byte block period).
- **chunk: `custom_ag_bowl_china_001.msac.n.0.sps` @0x156b6b0, size 2744, fOnk +2375 into it.**
- **REAL font: FOUND** — 64-byte `FontGlyphs` records (`u16 cp @+0`, ascending, 0xffff sentinel,
  vector outlines) inside KCAP packages. Format cracked on `m_lm_menu`/`ghost_title`/core_common
  (Latin). **The Arabic-slot font (Hebrew target) + the +22 vertex-outline format are the two
  open items for attempt #2.**
