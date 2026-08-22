# God of War: Ragnarök — FONT system (GATE 2)

The remaining blocker for visible Hebrew. Established 2026-06-17 by probing the
decompressed `r_lang_ar.wad` (read-only). **In-game proof:** Hebrew renders as
BLANK (zero-width), not tofu — the Arabic-slot font has no Hebrew glyphs and the
engine draws unknown codepoints as nothing.

## Font architecture (inside r_lang_ar.wad)

No embedded TTF/OTF (0 sfnt/`glyf`/`cmap`/`CFF ` tables). Fonts are **glyph-atlas
TEXTURES in Sony's `GNF ` format (PS4 GPU texture)** + separate metrics resources.

| Resource | Type | Stream size | Data offset (decompressed) | Role (likely) |
|---|---|---:|---|---|
| `sony_ar` | GNF tex | 12,288 B | 0x4fbfe1 | Sony logo/watermark |
| `iconspc` | GNF tex | 528,384 B | 0x581b20 | PC button/icon glyphs |
| `icons_ar` | GNF tex | 1,052,672 B | 0x691b20 | icon/glyph atlas (largest) |
| `copperplate_ar` | GNF tex | 528,384 B | 0x7338a3 | the copperplate text font atlas |
| `SMF_0`..`SMF_4` | metrics | — (no GNF) | 0x1888–0x1a38 (header region) | glyph metrics / font defs |

- GNF header parsed: magic `GNF `, contentsSize 0x0ff8, **version 4, numTextures 1,
  alignment 2^12 (4096)**, then a `Gnm::Texture` (Tsharp, 256-bit) descriptor, then a
  `USER` chunk, then the tiled texture data. Stream sizes (528 KB / 1 MB) ⇒ ~1024²
  atlases, almost certainly **BC-compressed single-channel (BC4 alpha)** coverage maps.
- `SMF_*` carry no GNF → they are the **glyph tables** (codepoint → atlas UV cell +
  advance/bearing). A plain u16/u32 codepoint-array scan found nothing ⇒ the metrics
  are packed/encoded (needs dedicated reversing).

## What Hebrew injection requires (two parts)

1. **Atlas (GNF):** decode the Tsharp (real width/height + surface format + PS4 tiling
   mode) → de-tile (PS4 Morton/standard swizzle) → BC-decode to a coverage bitmap →
   draw ~27 Hebrew letters (+ final forms + basic punctuation) into FREE atlas space →
   BC-encode → re-tile → rebuild the GNF. Hebrew is RTL but the atlas only stores glyph
   shapes; ordering is the engine's job (inherited free from the Arabic slot).
2. **Metrics (SMF):** reverse the SMF glyph-table format → add entries mapping Hebrew
   codepoints (U+05D0–U+05EA + finals) to the new atlas cells with correct advance/UV.

Then repack the WAD (gate-1 resizing packer or length-safe if metrics fit) and deploy.

## Deep-dive findings (2026-06-17) — the ATLAS half is SOLVED

- **The glyph atlases are stored LINEAR BC4 — NOT PS4-tiled.** Pure-Python BC4 decode of
  the raw stream renders a clean, upright, left-to-right glyph grid (verified by eye:
  Latin `BDEFHIKLMNPRTXYZ`, digits, symbols, **Arabic**, even CJK). So **no GOWTool, no
  de-tiling needed** — we can decode → draw → re-encode BC4 in pure Python (Pillow).
- **BC4 is fixed-size ⇒ replacing the atlas is LENGTH-PRESERVING** — splice the new atlas
  bytes into the decompressed WAD in place, re-LZ4, deploy (exact same mechanism that
  passed the gate-1 text test). No WTOC resize for the atlas.
- **Located the atlases (decompressed `r_lang_ar.wad.bin`):** the **text font** atlas at
  ~`0x690000` (1024²+, Latin+Arabic+CJK, **~half empty → room for ~27 Hebrew letters**),
  the **iconspc** button-glyph atlas at ~`0x580000`. (Carver + BC4 decoder + PNGs in
  `c:\tmp\gowr_bc4_decode.py` / `c:\tmp\atlas_*.png`.) GNF header + pixel stream are stored
  in SEPARATE WAD sections; the stream is the linear BC4 region above.
- **WTOC entry record** (~0x90 stride, names <0x2000): per-resource **size @ +0x2c**, an
  offset field @ +0xa0 (offset within the data section). Tooling can use this to locate
  any resource's bytes.

## The remaining blocker — SMF glyph-metrics / cmap (codepoint → atlas cell) NOT yet reversed

To make the engine map **Hebrew codepoints** (U+05D0–U+05EA) to the new glyph cells we draw,
we must edit the font's glyph table. Findings so far:
- It is **NOT a sorted codepoint array** (full-blob u16/u32 ascending-codepoint scan = 0 hits).
- `GLYPH` markers in the blob are **in-text `[Icons:*_GLYPH]` tokens**, not the metrics table.
- The format is opaque to quick scans (likely hashed/indexed). Reversing it is the deep,
  uncertain part — needs sustained RE (correlate the visible atlas grid ↔ records, or trace
  the renderer) or community/GOWTool knowledge of the GoWR font format.

## Paths to finish GATE 2 (decision)

- **A — reverse SMF ourselves** (pure Python, bundleable): deep multi-session RE of the
  glyph table, then add Hebrew entries pointing at cells we draw. Atlas half already done.
- **B — authorize GOWTool** (`kainotoa/GOWTool`, community GoWR-PC tool; needs the user's
  explicit OK to run a third-party binary — the safety classifier blocked it). May expose
  the font/metrics format and shortcut the SMF half.
- **C — atlas-edit in-game proof (cheap, do meanwhile):** overwrite a known existing glyph
  (e.g. a Latin letter visible in the menu logo) with a mark, deploy, confirm the atlas-write
  pipeline shows in-game — closing the last unproven atlas link without needing the cmap.

## BREAKTHROUGH (2026-06-17) — BOTH halves of GATE 2 fully cracked

**GOWTool (user-authorized) cleanly UNPACKS the WAD into per-resource files:**
`GOWTool settings -g "<GameLab root>"` then `GOWTool wad -p "<…>\r_lang_ar.wad" -u`
→ writes `…\pc_le\r_lang_ar\<name>---<idx>.bin` for every resource. Preserved in
`games/godofwar_ragnarok/extract/fonts/`. (`-t` exports nothing for the lang WAD; `-u`
is the one to use. GOWTool needs GameDir set to the install root.) Key outputs:
- `copperplate_ar---41.bin` = **524,288 B = raw 1024² BC4** = the body/text font atlas
  (Latin + Arabic + CJK + symbols, **lower half EMPTY** → room for Hebrew). `---42.bin`
  (0.2 KB) = its GNF/descriptor. icons_ar---38 = 1024×2048 BC4; iconspc_ar---35 = 1024² BC4.
- `SMF_1---43.bin` (40,520 B) = **"SMF4Copperplate"** glyph-metrics for that atlas.
  (SMF_0=Sony, SMF_2=IconsPC, SMF_3=Icons.)

**SMF4 glyph-record format (cracked, confirmed by atlas crop = crisp correct glyphs):**
- Header: `"SMF4" + fontName` null-padded; then header fields; **records start at 0x40c**.
- **928 records, 28 bytes each, SORTED by codepoint** (0x41,0x42,… then Arabic, CJK).
- Record fields (all atlas coords/sizes are **fixed-point ×8** → divide by 8 for pixels):
  `+0` u32 codepoint · `+12` u16 atlasX·8 · `+14` u16 atlasY·8 · `+16` u16 height·8 ·
  `+20` i16 x-bearing·8 · `+22` u16 width·8 · `+24` u32 advance·8 (·`+4/+6` index/page).
  (A small ~1-cell X calibration offset remains — nail it when WRITING by read-back.)

**Atlas pipeline proven in pure Python:** BC4 decode→PNG renders the real glyph grid
(`c:\tmp\gowr_bc4_decode.py`, `extract/fonts/font_copperplate_ar.png`). BC4 is fixed-size ⇒
atlas replacement is **length-preserving** (splice into the decompressed WAD + re-LZ4, the
gate-1 mechanism). No external binary needed for the atlas.

## Injector build plan (the remaining execution — `work/gowr_font.py`)

1. Decode `copperplate_ar---41.bin` BC4 → 1024² grayscale.
2. Render ~27 Hebrew letters (U+05D0–U+05EA) with a Hebrew TTF (Pillow) at ~37 px (height
   ·8≈294) into the EMPTY lower atlas region on a grid; record each cell's (x,y,w,h).
3. **BC4-encode** the modified atlas (write a BC4 encoder — min/max endpoints + 3-bit indices).
4. SMF: add 27 Hebrew records (codepoint + cell coords·8 + advance). Records are SORTED ⇒
   insert Hebrew (0x5D0–0x5EA, naturally between Cyrillic 0x4xx and Arabic 0x6xx) in order →
   SMF_1 GROWS by 27×28=756 B ⇒ needs the **gate-1 resizing repack** (update the resource's
   WTOC size field @+0x2c + any WAD totals, then re-LZ4). (If a linear/hash lookup is later
   confirmed instead of binary-search, overwriting spare records would be length-preserving.)
5. Splice modified atlas + SMF_1 back into the decompressed WAD (locate by byte-match) → re-LZ4
   → deploy to Game Lab → **iterative in-game calibration** (baseline/X offset) — needs the user.

## INJECTOR SHIPPED + DEPLOYED (2026-06-17) — `work/gowr_font.py`

Built, offline-verified, and deployed a Hebrew test WAD to Game Lab. The whole edit is
**LENGTH-PRESERVING — NO resize** (the gate-1 splice + re-LZ4 mechanism, which already
loaded in-game), so it sidesteps the WTOC offset surgery entirely.

**Two corrections to the earlier notes (verified by re-probing):**
- **Records start at 0x70, NOT 0x40c** (first cp = 0x20 space; 'A' is at index 33). 28-byte
  records, cp@+0 u16, sorted; a **0xfffc sentinel @~0x3480** ends the glyph array — after it is
  a 4-byte **kerning table** (`(u16 cp, i16 kern)` pairs). No separate glyph-count/offset field
  exists in the header → the sentinel + sorted order are the whole contract.
- **The resize is genuinely fiddly** (GOWTool test: growing SMF_1 +756 B and patching only the
  size field made SMF_3/2/0 unpack DIFF — section offsets are recomputed with a padding rule a
  naive end-insert disturbs). So we DON'T resize.

**The length-preserving trick (works for binary OR linear glyph lookup):** a Hebrew mod has
ZERO Arabic text, so the 51 Arabic glyph records (cp 0x600–0x6FF) are dead weight. Hebrew
(0x5D0–0x5EA = exactly 27 letters) sorts between the record just below (cp **0x308**) and the
first Arabic (**0x60c**). So we OVERWRITE the **27 lowest-cp Arabic records in place** (contiguous
array indices 123–149, cp 0x60c…0x638) with Hebrew 0x5D0…0x5EA ascending → the array STAYS SORTED,
SMF_1 stays exactly 40520 B, and SMF_3/2/0 + every other resource are byte-identical.

**Atlas:** decode BC4 → render the 27 Hebrew letters (David Bold, px≈56 → ~24–42 px ink, matches
the ~37 px Latin caps) into **empty 4-aligned blocks** (10k+ available; used a clear band at
y≈540) → re-encode **ONLY the touched 4×4 blocks** (1660 of them) and splice them back, so Latin /
digits / punctuation / Old-Norse runes stay byte-identical (respects the project's "only add
Hebrew" rule). BC4 round-trip fidelity: max err 5 / mean 0.33.

**Files / verification:**
- `work/gowr_font.py` — reusable injector (`inject_hebrew(dec_wad, font, px=…)`, BC4 codec,
  SMF helpers, empty-box finder). Edits the decompressed WAD in place.
- `c:\tmp\gowr_build_hebrew_test.py` — driver: inject font + 15 length-preserving Hebrew menu
  strings (full 27-letter alphabet in the longest) → re-LZ4 → self-verify → `out/r_lang_ar.wad`.
- Offline VERIFY = CLEAN: 27/27 Hebrew SMF records · atlas changed, size preserved · SMF_3/2/0 +
  icons byte-identical · 15/15 text strings Hebrew. **GOWTool re-unpacks the built WAD with every
  size unchanged** (structurally valid). Glyph contact sheet (`c:\tmp\gowr_hebrew_glyphs_check.png`)
  visually correct — all 27 letters crisp.
- Deployed to `Game Lab/…/exec/wad/pc_le/r_lang_ar.wad` (pristine `.he_backup` confirmed intact,
  md5 10963861…). C:\Games untouched.

## Status

GATE 1 PROVEN in-game. GATE 2 injector BUILT, offline-verified, DEPLOYED to Game Lab.
**Remaining = ONE in-game check by the user:** launch the Game Lab copy, set language = العربية
(Arabic), and look at the main menu / settings — the edited labels should show Hebrew (שלום /
עברית / the alphabet). If Hebrew shows → gate 2 is closed (then scale to full translation). If
blank → the engine binary-searches AND rejects our in-place remap for some reason → fall back to
the sorted-insert RESIZE (rebuild WTOC offsets with the correct padding rule). If glyphs render
but float/sink → tune the `+18` y-offset / bearing in `write_record` and rebuild.

## מסמכים קשורים
- באותה תיקייה: [[games/godofwar_ragnarok/FEASIBILITY|FEASIBILITY]], [[games/godofwar_ragnarok/GENDER_TASK|GENDER_TASK]], [[games/godofwar_ragnarok/PIPELINE|PIPELINE]], [[games/godofwar_ragnarok/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#godofwar_ragnarok|CLAUDE_INDEX_games]]
