# GoT DC font — Arabic-slot glyph table LOCATED (round 2, 2026-07-08)

**HEADLINE: the Arabic-slot font (the true Hebrew-injection target) is `ghost_title.xpps`
inside `gapack_misc_g.psarc` — a single MULTI-SCRIPT UI/title/menu font.** It covers Latin,
Cyrillic, **Hebrew (0x5d0–0x5ea)**, **Arabic (0x600–0x6ff + more)**, Indic and CJK. Round 1
missed it because its detector keyed on `+8 u32 == 4` (the m_lm_menu Latin variant); ghost_title's
Arabic/Hebrew records use **`+8 == 0`**, so `find_rich_tables` never saw them. All facts below were
run against the real files with the repo `.venv` python via `work/find_arabic_font.py`. No game file
was modified.

## 1. Where it is
- Package: **`/ghost_title.xpps`** (10,103,200 B) in **`gapack_misc_g.psarc`**. This is the
  boot/title package; the menu-proof (CONTINUE / New Game / Load Game / Options / Subtitles) was on
  the title screen, which renders from THIS font.
- It is the ONLY package in the game with Hebrew/Arabic glyph records. Verified by a lean
  glyph-signature scan (record sig `+20==0xf8 & +62==0xffff & cp-hi==0`):
  - `core_common.sprig.xpps` (673 MB): 6872 glyph records, **0 Hebrew-letter, 2 stray Arabic**
    (150 MB apart = coincidental, not a table). Latin/Cyrillic/Indic/CJK only.
  - `core_tsu` (99 recs) / `core_iki` (63) / `game.sprig` (244) / `ghost_title_0_0_0` (0): **0 Heb, 0 Ar.**
  - `m_lm_menu`: Latin only (the one "Arabic" RELAXED hit is a no-marker index/mesh false positive).
- So round 1's "core_common = Latin only" was right for core_common — but the Arabic font simply
  lives in ghost_title, not the shared core.

## 2. Record format (this font, kind `+8 == 0`) — 64 bytes, fixed
Reconstructed from real records (Latin/Cyrillic/Hebrew/Arabic sub-tables of ghost_title):
```
+0   u32  cp                       (ascending within a sub-table; cp==0xffff = positional-form group separator)
+4   f32  metric (often 0.0)
+8   u32  font-kind = 0            (Latin-in-ghost_title also 0; a few sub-tables 143; m_lm_menu Latin = 4)
+12  u16  = 0
+14  u16  FontVerts "page"/base group   (104 Hebrew block, 129/130 Arabic block, 143 elsewhere)
+16  u16  FontVerts region base pointer  ┐  (+16,+18) together = the per-glyph OUTLINE reference
+18  u16  outline index within region    ┘  into the external FontVerts buffer
+20  u8   = 0xf8   (constant record marker)
+22  f32  geometry X   (bbox / advance-ish)
+26  f32  geometry Y
+30  f32  geometry Z / size (5.0 Hebrew, 10/50 Arabic)
+34..+44  more geometry (usually 0 here)
+46,+50,+54,+58  4× f32 colour = 1,1,1,1 (white)
+62  u16  = 0xffff  (constant per-record marker — NOT a table terminator)
```
NOTE: this differs from the m_lm_menu Latin RICH layout (`+8==4`, `+16==0xffffffff`, inline geometry).
The invariants that DO hold across both fonts and drive the detector: **`+2==0`, `+20==0xf8`,
`+62==0xffff`, cp ascending.**

## 3. Full script coverage in ghost_title (76 sub-tables, 4553 glyph records)
cp 0x0→0x1125+, split into per-script sub-tables (many overlapping Arabic sub-tables = positional
forms). Highlights (offset / cp-range / distinct (+16,+18) refs):
- Latin+punct: `@0x867292` 0x26–0x108, `@0x86ab92`/`@0x86b452` Latin-1.
- Latin-ext + **Cyrillic**: `@0x86c1d2` 0x163–0x51f (Lat1=413, Cyr=256).
- **Hebrew + Hebrew-points + early Arabic:** `@0x87d7d2` cp **0x584–0x6db**, 149 records.
- **Arabic letters (real, per-glyph outlines):** `@0x880dd2` (0x627–0x6e1), `@0x881512` (0x642–0x670),
  `@0x8821d2` (0x673–0x6c0, refs=37), `@0x883652`, `@0x883f92` … through ~0x884000.
- Indic/other: 0x900–0xd0c, 0xd2e–0x1125 (Devanagari/Bengali/Tamil/… — the game ships 34 languages).

## 4. THE HEBREW GATE — why the menu tofu'd (the key finding)
Hebrew codepoints ARE declared, but as **degenerate placeholders with no real outlines**:
- The 27 Hebrew letters (0x5d0–0x5ea) live in the `@0x87d7d2` sub-table. First record (ALEF 0x5d0)
  is at **`@0x87ec92`**; they are 27 contiguous ascending records (→ 0x5ea @ ~`0x87f312`).
- **All 27 share `+8=0, +14=104, +16=1522`; only `+18` varies across just 3 values (11×1, 12×16, 13×10).**
  → 27 distinct letters map to only **3** `(+16,+18)` outline references. Real per-glyph outlines are
  impossible with 3 refs → the letters render as garbage/notdef = **the tofu observed in-game.**
- Contrast, same package:
  - Hebrew POINTS 0x591–0x5c7: 55 records, **35** distinct refs (near per-glyph — real).
  - Arabic letters (e.g. `@0x880dd2`): distinct `(+16,+18)` per glyph (1680/6, 1690/0, 1691/0 …) — real
    outlines → Arabic renders fine in-game.
- So Sucker Punch's Arabic-slot font declares the Hebrew block for completeness but never authored
  Hebrew letter outlines. **Injection target = give the 27 existing 0x5d0–0x5ea records real
  per-glyph outlines** (add Hebrew outlines to the external FontVerts buffer + repoint `+16/+18`, or
  repurpose 27 real Arabic-letter records → Hebrew cp + Hebrew outlines, GoWR-style).

## 5. How the menu loads (reconciles "Latin marker + Arabic both rendered, Hebrew tofu")
When Text = Arabic, the title/menu renders from ghost_title's per-script sub-tables IN THE SAME
PACKAGE: the Latin marker `ZZ-GOT-OK-ZZ` from the Latin sub-tables (0x26–0x51f), the game's own Arabic
from the real Arabic sub-tables (`@0x880dd2`+), and our Hebrew from `@0x87d7d2` — which has no real
Hebrew outlines → tofu. So the active font covers BOTH Latin and Arabic, and MULTIPLE per-script
sub-tables of the one package are consulted per run.

## 6. Open item for the injection round (attempt #4)
The 64-byte glyph RECORD is now cracked (fields above). The remaining blocker is the **external
FontVerts outline buffer** referenced by `(+14,+16,+18)`: its location in the KCAP package, the vertex
struct + winding + coordinate scale, so 27 real Hebrew outlines can be synthesised from a TTF, appended,
and the 27 existing 0x5d0–0x5ea records repointed. The geometry floats at `+22/+26/+30` (bbox/advance)
also need confirming against a known Arabic glyph.

## 7. Tools (persist in `work/`)
- **`find_arabic_font.py`** — the locator. `pkg <arc> <name>` scans one package (STRUCT + CMAP +
  RELAXED detectors, reports Arabic-reaching tables + field signature); `arc <arc> [minrun] [maxsize]`
  scans every file in an archive; `dump <arc> <name> <off> [n]` dumps records. The RELAXED detector
  (only `+2==0` + ascending) is what caught ghost_title's `+8==0` Arabic that round 1's `+8==4`
  detector missed.
