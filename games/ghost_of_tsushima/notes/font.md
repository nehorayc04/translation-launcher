# Ghost of Tsushima DC — FONT investigation (Phase 1)

Date: 2026-07-07. Reader used: `games/tlou2/tools/dsar.py` (DSAR→PSARC). Game install
`F:/Games/Ghost of Tsushima DC`. All findings verified by running Python against the real files.

## TL;DR
- **Menu + subtitle font = a single proprietary Sucker Punch `fOnk` resource baked inside
  `game.sprig.texmeshman`** (which lives in `cache_pc/psarc/gapack_misc_g.psarc`).
- It is **NOT** a stored TrueType/OpenType file and **NOT** a DDS glyph atlas. Its payload is
  high-entropy (compressed / packed vector-glyph data — matches the engine's
  `SFontData` / `FontGlyphs` / `FontVerts` structures).
- **No shipped font can be cmap-checked** because there is no sfnt anywhere (exe, loose, archives).
- **Hebrew (U+05D0–05EA) is NOT a shipped language → its glyphs are almost certainly absent.**
  Arabic IS an official shipped language (the Hebrew target slot) so the `fOnk` DOES carry Arabic
  glyphs + RTL. ⇒ **Font injection into `fOnk` is required.**

## Evidence

### 1. No loose fonts, no embedded TTF/OTF
- `find` over the whole install: **0** `.ttf/.otf/.ttc/.fnt/.woff`.
- Scanned `GhostOfTsushima.exe` for sfnt/OTTO/ttcf headers validated by real table tags
  (`cmap/glyf/head/…`): **0 valid fonts** (24 raw magic hits, all false positives — first table
  tags were junk like `5nx5`, `POSI`).
- Scanned `game.sprig.texmeshman` (108 MB) the same way: **0 valid sfnt**.

### 2. The exe uses a font-from-memory + vector-glyph pipeline
`GhostOfTsushima.exe` ASCII strings include:
`CreateFontW`, `AddFontMemResourceEx`, `RemoveFontMemResourceEx`, `Launcher_Font`,
`Launcher_Font_Version`, `FontGlyphs`, `FontVerts`, `SFontData`, `FONTK`, `FONT_KIND`,
`FONT_SIZE`, `LARGE_FONT_SIZE_FACTOR`.
→ the engine holds a font in memory and bakes glyph **outlines to vertices** (vector text on GPU),
not a bitmap atlas. `FONTK` == the `fOnk` chunk tag below.

### 3. The actual font resource: `fOnk`
- `game.sprig.texmeshman` container magic = `NAMS` ("SMAN" LE). Extracted full (108,445,889 B).
- Exactly **one** `fOnk` tag, at offset 22,462,455 (0x156BFF7). None in `all_shaders.texmeshman`,
  `pulse.sprig.texmeshman`, or `gapack_meshes.psarc`.
- 8 KB immediately after `fOnk` has entropy **7.47 bits/byte** ⇒ compressed / densely packed
  (Sucker Punch codec), not plaintext outlines and not sfnt. Cracking this `fOnk` format is the gate.
- `game.sprig.packman` (68 KB, gapack_misc_g) is a binary hash index for the package (no strings).

### 4. `debugfont.dds` is a debug-only bitmap font (ignore)
- `gapack_bitmaps_d.psarc` → `/bitmaps/debugfont.dds.0.sps` (65,626 B). Only "font"-named asset in
  ALL bitmap+misc archives.
- `.sps` wrapper magic = **`XTBS`** (Sucker Punch texture; "sBTX"). Inner is a `.dds` bitmap.
  This is a developer debug font, not the shipping UI/subtitle face.

### 5. The `lang_<lang>.msac.d.0.sps` textures are NOT per-language font atlases
- 34 of them in `gapack_bitmaps_l.psarc`, one per shipped language (arabic, japanese,
  chinesesimplified, korean, greek, turkish, british, french, …).
- **Every one is ~87,667 bytes regardless of language**, incl. `lang_chinesesimplified` (87,676 B).
  A CJK glyph atlas cannot fit in 87 KB → these are **localized UI raster images**
  (a fixed-resolution `XTBS`/DDS texture per language — e.g. a button-legend / control-prompt or a
  localized title/marketing strip), NOT font glyph atlases. Same `XTBS` magic as the debug font.

### 6. Shipped language list (from `gapack_misc_l.psarc`, `lang_*_text.xpps`)
arabic, brazilian, british, chinese, chinese_s, croatian, czech, danish, dutch, english, finnish,
french, german, greek, hungarian, italian, japanese, korean, latino, norwegian, polish, portuguese,
russian, spanish, swedish, thai, turkish, (+ `pgc_lang_*` incl. vietnamese, indonesian, romanian,
quebecois). **No Hebrew.** Arabic present ⇒ the RTL/Arabic glyph coverage + shaping already ships.

## Verdict for the pipeline
- Store Hebrew in the **Arabic text slot** (`lang_arabic_text.xpps`) as already planned.
- **Font injection IS needed**: Hebrew glyph outlines/vertices must be added to (or replace part of)
  the proprietary `fOnk` font inside `game.sprig.texmeshman`, then repack the container and re-wrap
  it as DSAR/PSARC (writers exist: `games/tlou2/tools/dsar_write.py` + `psarc_write.py`).
- **Gate**: the `fOnk` internal format (SFontData / FontGlyphs / FontVerts; compressed) is not yet
  cracked. That reverse-engineering is the font sub-project. (A pure "replace-the-TTF" shortcut is
  NOT available — no TTF is shipped; the runtime `AddFontMemResourceEx` path feeds an internally
  reconstructed font, and vector `GetGlyphOutline`-style extraction does not get OS font-linking
  fallback, so Windows will not silently supply Hebrew.)
