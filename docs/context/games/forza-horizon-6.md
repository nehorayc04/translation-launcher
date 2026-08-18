## Forza Horizon 6 Hebrew — ✅ Phase 1 COMPLETE, install repaired, proof DEPLOYED, 🟢 GO (2026-07-27)

**UPDATE (same day, after the section below was written): the install was repaired
and every gate that was blocked is now closed.**

- **✅ INSTALL REPAIRED to v403.798** via the 5-step ElAmigos delta chain
  (354.221→360.259→364.933→375.327→398.092→403.798). **All 27 critical files
  xxh128-MATCH** the game's own manifest — `forzahorizon6.exe` (183,603,672 B),
  `media\UI\Fonts.zip`, `media\ObjectModelGame.zip` and **all 24 language zips**.
  700 files remain missing and every one is per-language audio (a deliberate
  English-only install). `work/status.py` is the one-command health check; run it
  after ANY game update.
  ⇒ The "trust only the 8 hash-clean zips as oracles" caveat is **WITHDRAWN** —
  all 22 New-Era reference languages are now trustworthy.
- **✅ PROOF RE-DEPLOYED + verified 11/11** by reading back out of the live
  `media\Stripped\StringTables\GB.zip`. Scope re-measured identical (58,179
  records / 37,099 real prose), which confirms the pristine-snapshot measurement.
- **🔑 THE FONT GATE IS MAPPED — and it is far cheaper than feared** (`tools/fh6_font.py`).
  - **`.vfont` format solved exactly**, arithmetically from four files and then
    verified with **zero slack on all 21 shipped descriptors**:
    `len == 204 + 8*pageCount + 36*glyphCount + 12*kernCount`. Header =
    `char[128] name · u32 ver(2) · u32 4 · u16 glyphCount, u16 kernCount, u16 pageCount, u16 pageCount @0x80 · metrics floats`. Glyph record (36 B) = `f32` bearing ·
    `u16 w, u16 h` · **`u32` byte-offset into the `.vfontN` page** · `0xFFFFFFFF` ·
    **`u32` CODEPOINT @ +0x18** · 2 advance floats. The codepoint table is **sorted
    ascending and ends at U+FFFD**, then a short alias tail — so a naive
    "is it sorted" test says False; check the prefix.
  - **Coverage MEASURED: 0/27 Hebrew in all 20 families.** `Horizon_A/B/C/D` = 242
    glyphs (ASCII+Latin-1+punct), `_tf` = 21 (digits only), **`Horizon_RU_A/C/D` =
    440**, CJK 1,650–3,299.
  - **🔑🔑 INJECT INTO `Horizon_RU_A/C/D` ONLY — and `fontsettings.xml` needs NO
    edit.** That file declares an explicit **`fallback=` chain per language**, and
    the catch-all `lang="*"` block (what GB/EN/DE/FR… resolve to) already loads the
    RU family: `Horizon_A → Horizon_RU_A → Horizon_KO → Horizon_JP → Horizon_CHS →
    Horizon_CHT` (and `C → RU_C`, `D → RU_D`). A codepoint the Latin font lacks is
    looked up in the fallback automatically. **This is exactly how Playground
    shipped Cyrillic** — they extended the FALLBACK font to 440 glyphs rather than
    growing the primary, so the precedent for a new script lives inside the game.
    **UNIVERSAL: before planning to inject a script into every UI face, read the
    engine's font-ROUTING config for a fallback chain — extending one already-loaded
    fallback font can replace injecting eight, with zero configuration change.**
  - **The ONE open unknown = the `.vfontN` atlas pixel codec.** A page is a
    sequence of per-glyph blobs in glyph order: `{u32 idx, u32 w, u32 h}` + payload
    (a zero-size glyph is a bare 12-byte header). The payload runs
    **0.02–0.19 bytes/pixel** ⇒ compressed, almost certainly SDF or a custom RLE.
    Phase-1.5 sub-project. **It does not block the proof** — a tofu render still
    settles mount, bidi, punctuation placement and digit direction
    ([[tofu-still-answers-bidi]]).
- **✅ ROUND 1 CAME BACK (user screenshots): MOUNT ✅, FONT ✗ — exactly as measured.**
  `ZZ-FH6-OK-ZZ` rendered on the button prompt ⇒ the patched zip mounts. **The box
  COUNTS were exact** — 4 boxes for `שלום` on *Esc*, 5 for `עברית` on the language
  row ⇒ the text reaches the renderer and only the glyphs are missing (0/27, as
  measured). **bidi was NOT settled** — the two visible rows are pure Hebrew with no
  digit or punctuation, so they carry no ordering information.
- **🔴 SLOT MOVED GB → EN, at the user's request, for ZERO-ACTION activation.**
  English is the default, so a player who never touched the setting gets Hebrew on
  the next launch. **`GB.zip` ("English UK") is now the untouched escape hatch** and
  `IDS_LanguageSelect_GB` is deliberately left unpatched so the row stays findable
  while the UI is in Hebrew. GB was reverted first and re-verified **xxh128-MATCH**.
  **The measurement that makes this safe: GB differs from EN in only 7,346 of
  58,179 values (12.6 %), while every other language differs 77-90 %** — so
  whichever of the two English variants is sacrificed, the other one is a
  ~87 %-identical replacement, and no real language is ever destroyed.
  **UNIVERSAL: when a game ships two variants of the same language, measure the
  divergence between them before choosing a hijack slot — a near-duplicate pair
  lets you take the DEFAULT slot (zero-action activation) while still leaving a
  complete escape hatch. Without that pair, hijacking the default is destructive.**
- **⚠️ "System Language" is NOT a slot** — `IDS_LanguageSelect_Default` is a runtime
  resolver with no string table of its own (the game's own error string says
  "using system language instead"). Nothing to patch, and FH6 has no Hebrew locale
  so a Hebrew Windows resolves to English anyway.
- **⚠️ The language choice lives in a BINARY GDK profile blob**
  (`…\MicrosoftStore\RUNE\Forza Horizon 6 […]\SaveGames\…\C_ProfileData`) — the same
  class as GoWR's `userpreferences`. **Do not edit it**; there is no safe
  launcher-side language switch for this game (no `game_language.py` entry).
- **ROUND 2 DEPLOYED to `EN.zip` (15/15 verified).** Every bidi/layout probe moved
  onto the **language-select list** (reachable from the main menu; the pause menu
  needs a loaded save, which the user reported as hard). Rows are labelled with a
  **leading DIGIT — odd = stored LOGICAL, even = stored VISUAL** — because a digit
  renders through total tofu, so **the row whose digit sits on the RIGHT names the
  storage mode**. Pairs: `1/2` = `שלום`, `3/4` = the punctuation+parens+Latin
  sentence, `5..9` = repeats so any scroll window carries a full A/B pair.
  **UNIVERSAL: when a proof surface turns out to be hard for the user to reach,
  move the probes to a surface they have already demonstrated they can open —
  and label A/B rows with DIGITS, which survive a missing font.**
- **✅✅ ROUND 2 CAME BACK — bidi = VISUAL, settled by EIGHT rows agreeing unanimously.**
  Rows **1, 3, 5, 7, 9** (stored LOGICAL) rendered their label digit on the **LEFT**;
  rows **2, 4, 6, 8** (stored VISUAL) rendered it on the **RIGHT**. The decisive one
  is row 4 — the full sentence stored VISUAL rendered byte-for-byte as stored
  (`!▯▯▯ .Forza Horizon 6 ,▯"▯▯ 240 — (5 ▯▯▯▯ 3) "▯▯▯▯▯▯" :▯▯▯▯▯▯ 4`), which read
  right-to-left reconstructs the original sentence exactly — Latin island forward,
  `240` in place, the final `.` and `!` at the correct end — while row 3 (the same
  sentence stored LOGICAL) also rendered exactly as stored, i.e. unreadable.
  ⇒ **the engine draws in STORAGE ORDER and does NO bidi**, exactly as the XAML
  predicted. **`fh6_rtl.to_visual` is validated end-to-end in the live game.**
  The 27-letter row rendered as exactly **27 boxes** — a visual confirmation of the
  0/27 coverage measured offline.
  ⚠️ The `(` / `)` look "inverted" to a Hebrew reader and that is **CORRECT** — do
  not mirror them; it is what the shipped professional Arabic does on this class of
  engine (Playbook §8b rule 0).
  **UNIVERSAL — the digit-labelled A/B ladder is the cheapest bidi instrument there
  is:** put the SAME string on N rows of one screen, alternating storage mode, and
  label each row with a leading DIGIT. Digits are real glyphs, so the answer
  survives a completely missing font; N rows agreeing removes any reading
  judgement; and it costs one screenshot instead of one launch per hypothesis.
- **STATE: every Phase-1 gate is CLOSED except the font glyphs.** Container · text ·
  deploy · activation · scope · **bidi=VISUAL** · mount — all proven. The proof is
  left DEPLOYED on `EN.zip` (backup `EN.zip.he_backup` + sha sidecar) precisely
  because its 27-letter row is the ready-made test for the font injection: the
  moment glyphs land, one launch shows real Hebrew. Revert:
  `python games/forza_horizon6/work/build_menu_proof.py --revert`.
- **🔑🔑 PHASE 1.5 — `.vfontN` SOLVED, AND IT IS NOT A PIXEL ATLAS AT ALL.** The
  earlier "compressed atlas, almost certainly an SDF or a custom RLE" reading was
  **wrong**; the correction is the best news of the project. Each page stores, per
  glyph in glyph order: `u32 vertexCount · u32 indexCount · vertex[vc] (8 B) ·
  u32 codepoint` (a terminator; a record's `dataOffset` points at the PREVIOUS
  glyph's terminator, hence the +4 shift). **`payload == 8*vc + 2*ic`, verified on
  2,487 glyphs with ZERO exceptions** ⇒ the record's `+0x04`/`+0x06` u16 pair is
  **vertexCount / indexCount, NOT a width and height**. Vertex = **4 × fp16
  `(x, y, cu, cv)`**: `x,y` are normalised em coordinates, `cu,cv` are shader
  curve/AA params — **exactly 0 across all of `H`** (straight edges) and large on
  `O` (curves), in ± pairs straddling each edge. Indices are a u16 triangle list.
  **PROVEN BY RENDERING: rasterising the decoded triangles produces readable
  letterforms — `extract/mesh_render.png` shows H O A 1 Z W with correct counters.**
  ⇒ **no rasterisation, no SDF constants to fit, no atlas packing or page-size
  cap** — the whole expensive machinery of the GoWR / Plague Tale / 007 font jobs
  is moot here. Hebrew injection becomes *outline → flatten → triangulate → emit*,
  a solved problem with fontTools + ear clipping. Only `cu,cv` remain unknown, and
  they affect anti-aliasing, not geometry.
  **UNIVERSAL — when a "compressed atlas" resists, test whether the payload scales
  with the glyph's COMPLEXITY rather than its AREA.** Here `payload/(w+h)` was a
  near-constant ~4.15 while `payload/(w*h)` swung 8×, which is the signature of a
  vector representation; the two u16 then turned out to be vertex/index counts, and
  the last 60 bytes of the smallest glyph were visibly a `0,1,2, 1,3,2, …` triangle
  list. Then **render the decoded geometry — one image ends the argument.**
- **🔴 The codepoint field is OFF BY ONE RECORD** (record *i* holds the codepoint of
  the glyph whose mesh is in record *i+1*). Settled two independent ways, both
  refusing the naive reading: the only zero-vertex meshes then map to **U+0020,
  U+00A0, U+3000, U+FFFD** — exactly the outline-less characters — and digit vertex
  counts order by typographic complexity (`1`=49 < `7`=55 < `4`=84 < … < `8`=240),
  whereas the naive reading claims `!` has no outline and `0` has 20 vertices.
  Use `fh6_font.glyph_map()`, never `glyph.cp` directly, for geometry.
  ⚠️ `Horizon_CHS/CHT/KO` store f32 bit patterns at `+0x18`, so their cp tables are
  not authoritative — **every family this project touches is clean** (0 out-of-range).
- **✅✅ HEBREW GLYPHS INJECTED — 27/27 RENDER IN-GAME (2026-07-27).** The whole
  font gate is closed. `tools/fh6_glyphgen.py` turns a TTF outline into a
  `.vfontN` mesh: flatten → **exact trapezoid decomposition** (split the plane at
  every vertex y so no two edges can cross inside a band, pair the crossings by
  the **non-zero winding rule** — which handles counters/holes with no special
  casing at all — then merge adjacent bands bounded by the same edge pair, which
  collapses the long straight runs Hebrew is full of) → emit
  `(x + 0.5, y, cu=0, cv=1)` fp16 vertices + a u16 triangle list.
  **`cu=0, cv=1` is exactly what the game's OWN interior triangles carry**, so the
  result is guaranteed-opaque. Validated against an INDEPENDENT winding-number
  raster: identical, counters and diagonals included. **This first build was
  FLAT/opaque with no anti-aliasing at all — see the noise fix below.**
- **✅✅ "THE FONT HAS NOISE, LIKE AC2/GoWR/Plague-Tale-Requiem" — same COMPLAINT,
  a DIFFERENT root cause, because FH6's font is a VECTOR MESH not a bitmap atlas
  (2026-07-27, fix deployed).** Those three prior games all had a bitmap-atlas
  alpha-curve MISMATCH (wrong blur/threshold vs the native glyphs' measured
  ink/edge profile — see [[match-the-shipped-channel-profile]]). FH6 has no
  atlas to mismatch — but the flat opaque mesh above has no anti-aliasing
  vertices at all, so every edge rasterizes HARD, and a hard edge on a small
  vector glyph reads exactly like graininess: the same visual symptom the user
  had already seen three times, from an unrelated mechanism.
  **The fix is the analogous move for a mesh format: reproduce the game's OWN
  per-edge AA band instead of matching an alpha curve.** `fh6_font.py`'s own
  reverse-engineering already measured it: `cv = 1.0` on the solid interior,
  `cv = ±W/edgeLength` on a miter-inset AA-band quad straddling every outline
  edge, `W = 0.0283 em` (measured off the game's own 'H'). `fh6_glyphgen.mesh_for`
  now emits both parts: `fill_side()` picks ONE inset direction for the WHOLE
  glyph from its LARGEST contour (an earlier per-contour attempt inverted
  counters — ם/ס measured 18-20% off — because a hole's own winding disagrees
  with the glyph's overall fill direction), `inset_polygon()` miter-offsets
  every contour by `W` toward that side, and one AA quad per outline edge gets
  `cv = ±W/L` (its own edge length `L`) at both the inset and outset corners.
  **Validated by an INDEPENDENT ground truth**, not by eye: `work/test_aa_band.py`
  simulates the shader's own analytic-AA formula (`alpha = cv/fwidth(cv) + 0.5`)
  per triangle and compares the `cv>=0` region against a winding-number
  scanline rasterizer of the TRUE outline — worst case **0.09%** area error (ת),
  median **0.00%**, all 27 letters, confirmed visually in
  `extract/aa_band_check.png` (simulated engine AA vs ground truth, side by
  side). The AA band roughly **triples** vertex/index counts, so
  `HEB_BUDGET = 52_000` bytes caps the flattening tolerance search and the
  pages genuinely GROW now (`Horizon_RU_A` 516,340→547,362 · `RU_C`
  526,186→557,148 · `RU_D` 546,602→573,306 B) — safe only because the trailer
  bug above is fixed and every build now regenerates it from the real page
  length. **UNIVERSAL: "graininess" in a font fix is not always the same bug —
  for a bitmap atlas it's an alpha-curve mismatch, for a vector mesh it's a
  missing/wrong AA band; identify which representation the format actually
  uses before reaching for the fix that worked last time.**
- **Size and weight are MEASURED, never chosen by eye.** `x_em = x_mesh − 0.5`
  and `hgt` == the ink top were confirmed by symmetric bearings (H: lsb 0.0801 /
  rsb 0.0800). Body = the **cap/x-height midpoint** (0.7002 / 0.5000 → **0.60 em**
  — Hebrew is unicase, so matching the cap reads oversized and the x-height reads
  small). Weight: each face's own `H` stem drives a **binary search on Heebo's
  `wght` axis** — RU_A 0.1260→0.1258 @567 · RU_C 0.1577→0.1575 @736 ·
  RU_D 0.0820→0.0818 @345. One donor, three faces, three exact weights.
- **🔴🔴 THE `.vfont` DECLARES ITS OWN PAGE SIZE IN A TRAILER, AND THE ENGINE
  BELIEVES THAT OVER THE REAL FILE.** The last `4 + 8*pageCount` bytes are the
  REAL page table — `u32 slotCount` then `{u32 pageByteSize, u32 glyphsInPage}`
  per page — and every declared size matches the true `.vfontN` length on every
  font, CHS's 15 pages and JP's 10 included. Leaving it stale is what broke the
  injected letters: round 1 grew the page to 552,472 while the trailer still said
  516,340, so **exactly ש and ת — the only glyphs crossing the OLD declared size —
  came out wrong** (ר ended under it and was perfect, ש straddled it and drew half
  a letter, ת started past it and drew garbage); a later build with a stale SLOT
  count lost a letter in the middle of the range instead.
  **Recognise it by the pattern: letters breaking by POSITION in the injected run
  rather than by shape, on a file that parses perfectly.** Find the field rather
  than theorising — one line (`[i for i in range(len(f)-3) if u32(f,i) == pageSize]`)
  located it after an engine-side buffer cap, a u16 vertex-index limit (the page
  holds 46,864 of a possible 65,536) and a ZIP header mismatch had each been
  measured and cleared. `serialize(page_sizes)` now regenerates it and `validate()`
  refuses to deploy unless the trailer describes the page actually written.
- **🔴 TWO STRUCTURAL ERRORS RODE ALONG, AND BOTH CANCEL OUT ONLY AT
  `pageCount == 1`:** the 8-byte block after the 204-byte header looks like a
  per-page table and is not one (RU_C and RU_D have byte-identical records there
  while their pages differ by 20 KB), and the glyph region has **no 12-byte
  suffix** — those bytes were the trailer. Together they made every multi-page CJK
  font decode as garbage (Horizon_JP's max `dataOffset` came out as **3.1 billion**,
  its Latin coverage as 4 glyphs instead of 58) — and the selftest had **skipped**
  multi-page fonts, so nothing ever failed. Corrected model, exact on all 20:
  `204 + 8 + [24 + 36*N] + 12*kernCount + [4 + 8*pageCount]`, `slotCount == N+1`.
  **UNIVERSAL: make the identity round-trip REGENERATE derived fields from ground
  truth instead of copying them, and never let a selftest skip a subset — the
  skipped inputs are exactly where the model is wrong.** See
  [[vfont-trailer-is-the-page-table]].
- **The 7 math operators are STILL dropped for free headroom** (`∨∩∪∫∬∭∮`,
  19,370 B) — because **`Horizon_JP` carries all seven and sits in this font's
  own fallback chain (RU_A → KO → JP)** — and `inject_fitting()` picks the
  finest flattening tolerance within `HEB_BUDGET`. With the AA band the pages
  now GROW (~27-31 KB each, see above) rather than shrink; that growth is safe
  precisely because the trailer is regenerated from the real page length on
  every build (`validate()` checks it before deploy).
- **✅ REAL HEBREW MENU DEPLOYED** (`work/build_menu_he.py`, ~51 labels: main menu,
  options, screen titles, tiles, pause categories, the button-prompt bar). Every
  label decided against the game's OWN reference languages, which repeatedly beat
  the English: **"Video" is `Графика` / `Obraz`** = the DISPLAY category (→ תצוגה,
  so `וידאו` would have been wrong), "Hud & Gameplay" is
  `Interfaz y experiencia de juego` (→ ממשק ומשחקיות), and **Accept/Confirm stay
  DISTINCT in every language** (Принять/Подтвердить) → קבל / אשר. A QA gate
  (niqqud · foreign letter · still-English · token multiset · length vs the
  English) refuses to build on a defect. **One row is deliberately stored LOGICAL
  with a Latin tag (`ZZ-LOG`) so it MUST render mirrored** — a stale deploy can
  never be mistaken for a working one. Language names on the picker stay in their
  own scripts, which is what a picker is for.
- **`work/preview_ingame.py` renders the DEPLOYED text with the DEPLOYED font in
  storage order** — i.e. exactly what the engine does — so size, spacing and
  letterforms are judged in a chat message instead of a game launch
  ([[minimize-game-restarts]]). **Rewritten to composite the SAME analytic-AA
  formula as `test_aa_band.py`** (`raster_into()`: per-triangle barycentric
  coverage from `cv`, `alpha = cv/fwidth(cv) + 0.5`, max-blended into one
  canvas) instead of drawing flat `cv==1` polygons — the old version silently
  skipped every AA-band triangle, so it could never have shown the noise the
  user reported, nor would it show the fix. Now the preview is a real check
  for BOTH size/spacing AND edge quality.
- **⚠️ The user asked for NO automatic game launching** — hand builds over to run.
- **STATE: font (AA-band build) + Hebrew menu both DEPLOYED and verified by
  reading back out of the game's own files; `preview_ingame.py` confirms the
  AA-composited render looks smooth offline (`extract/ingame_preview_
  Horizon_RU_A.png`).** User-confirmed the mount/position/size are correct
  in-game, then reported the same font-noise defect seen on AC2/GoWR/Plague-Tale
  — traced to the missing AA band (see above) and fixed by reproducing it. The
  fix is offline-validated (`test_aa_band.py`: worst 0.09%, median 0.00% vs a
  winding-number reference) and DEPLOYED to the live `Fonts.zip`. Awaiting the
  user's NEXT in-game screenshot to confirm the noise is actually gone on
  screen — offline simulation is strong evidence, not proof. Revert:
  `build_menu_he.py --revert` + `build_hebrew_font.py --revert`.
- **✅ COMMUNITY `/translate` POOL LIVE — 56,179 rows in 2 Hebrew categories
  (2026-07-27).** `games.id` = **`forza-horizon6`** (row created this round —
  no prior row existed, `availability=planned/locked`, free, sort 10010).
  `work/build_ct_strings.py` keys **`string_key = "<table>:<IDS>"`** — EXACTLY
  `build_menu_he.py`'s `HE[(tbl, idn)]` key, so an approved export drops
  straight onto the build with no remapping. **NO dedup by English** (key by
  table+id, matching this game's own record-level scope, not the "37,099
  real-prose UNIQUE VALUES" recon estimate — those are different numbers by
  design, see [[dedup-safety-from-game-langs]]). Ordered by VISIBILITY
  ([[community-pool-by-category]]): **ממשק ותפריטים 39,270 → כתוביות ודיאלוג
  16,909**, split by the engine's own SUBT table-name keywords (same rule
  `scope.py` already used). Verified through the PUBLIC API, not the
  importer's message: `?action=games` → 56,179/56,179 open (cache-busted,
  confirmed MISS), `?action=list&game=forza-horizon6` → both Hebrew category
  chips with the exact counts, first served batch = UI rows.
  **NEXT: Phase 2** — delegate the 56,179 lines ([[delegate-all-translation]],
  the free 22-language panel, key by `(table, IDS)`) via the `/translate` pool
  now that it's seeded → build via `build_menu_he.py`'s pattern → publish only
  on an explicit "פרסם".
- **Cover/banner/logo uploaded (2026-07-27)** — the game had NO card on the site
  because the fresh row carried no artwork. `work/upload_images.py` (cover
  600×900 webp q86, banner ≤1600w webp q86, logo CONTAIN-fitted ≤360w
  transparent PNG) → `covers/forza-horizon6.webp` / `covers/banners/…` /
  `covers/logos/…`, PATCHed onto the `games` row. Verified: all 3 HEAD 200,
  `/api/games` (cache-busted MISS) returns the card with cover/bannerUrl/logoUrl.

### Original Phase-1 write-up (still accurate for the formats; the BLOCKED items above are resolved)

New game at `games/forza_horizon6/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` +
`extract/`). Install `C:\Games\Forza Horizon 6` (144 GB, Playground Games **ForzaTech**,
GDK/Microsoft-Store title `Microsoft.ForteBaseGame` v2.403.798.0 repacked for Steam appid
**2483190**, RUNE emu + "Online Fix" loader). Proposed `games.id` = **`forza-horizon6`**,
detector exe `forzahorizon6.exe`. Memory [[forza-horizon6-groundwork]].

- **🔴🔴 THE HEADLINE: THE INSTALL IS INCOMPLETE AND PARTLY CORRUPT — proven against the
  game's OWN manifest, not guessed.** The build ships `v403.798.xxh128` (plain text,
  `XXH128 *path`, 15,149 entries). `work/check_install.py` → **706 missing**; 700 of them are
  per-language audio banks (a deliberate English-only selective install, harmless) and **6 are
  real**: **`forzahorizon6.exe`** (⇒ **the game cannot launch at all**), `media\ObjectModelGame.zip`,
  `media\Audio\DialogueLength.xml`, `media\Stripped\StringTables\HU.zip`, `Fanatec.Devices.bin`,
  `hash.manifest`. `work/verify_hashes.py` then found **`media\UI\Fonts.zip` MISMATCH** and
  **15 of 23 language zips MISMATCH** (clean: CHS DK EN GB IT NL NO SV).
- **🔑 THE CORRUPTION MAP IS 1:1 WITH THE PARSE FAILURES — that correlation is what proved the
  codec right and the FILES wrong.** Every hash-clean zip reads **287/287** perfectly; every
  hash-failing zip has exactly the broken entries my reader reports. **UNIVERSAL: before
  reversing a "custom codec", hash the file against the game's own integrity list — a corrupt
  or half-installed file is indistinguishable from an unknown format, and no amount of RE can
  succeed against bytes that are not there** ([[verify-artifact-against-vendor-manifest]]).
  Everything below is built only on **EN.zip / GB.zip, both xxh128-VERIFIED pristine**.
- **🟢 CONTAINER SOLVED — `tools/fh6_zip.py`.** `media\**\*.zip` are ordinary deflate ZIPs plus
  ONE private convention, verified **288/288** on both pristine archives: every entry's data
  starts on a **4096-byte boundary**; the LOCAL header's extra is a padding record
  `{u16 0x1123}{u16 len}{zeros}` sized to reach it; and the **CENTRAL directory carries
  `{u16 0x1123}{u16 4}{u32 alignedDataOffset}` = the authoritative data start.** The writer
  reproduces it and **stream-copies untouched entries, so a no-op rebuild is BYTE-IDENTICAL**.
- **🔴 THE TRAP THAT COST THE MOST TIME: a stale `compress_size` must NOT bound the inflate.**
  Feeding exactly `cs` bytes makes a partially-updated entry raise
  `invalid distance too far back` — which reads *exactly* like "this uses a proprietary codec"
  and sent me chasing Oodle/zstd/encryption. Feeding generously and letting the deflate stream
  terminate itself took `Fonts.zip` from 26 "broken" entries to 8, and the manifest then proved
  those 8 are genuinely ABSENT. **Trust the stream's own end marker over a header field.**
- **🟢 TEXT SOLVED — `tools/fh6_str.py`.** `media\Stripped\StringTables\<LANG>.zip` → **287
  `.str` tables**. Layout: `u16 version(0x0800)` · `char[128] tableName` · `u16 sectionCount(2)`
  · `u32 sectionOffset[2]`; each section = `u32 total(=count*8+blobLen)` · `u32 blobLen` ·
  `u32 count` · `{u32 hash, u32 offset}*count` · NUL-terminated UTF-8 blob. **section[0] =
  VALUES, section[1] = ID NAMES (`IDS_Foo`), and BOTH share ONE hash array** — so the hash is a
  content hash of the id name, a translation only replaces VALUES for EXISTING ids, and **the
  hash function never has to be reimplemented** (copy the array verbatim). `edit()` is SURGICAL
  (original blob kept byte-for-byte, replacements appended) ⇒ **`edit(buf,{})==buf` on 287/287
  tables of both pristine zips**.
- **🔴 NO RTL LOCALE — 24 text languages, none Arabic/Hebrew** (BR CHS CHT CZ DE DK EL EN ES FI
  FR GB HU IT JP KO MX NL NO PL PT RU SV TR; HU not installed). ⇒ **LTR-slot hijack**, and
  **GB ("English UK") is the ideal sacrifice**: only **7,346 of 58,179** values differ from EN,
  so a user loses essentially nothing and `EN` ("English US") stays pristine.
- **🔑 ACTIVATION IS AN IN-GAME SELECTOR WHOSE LABEL IS ITSELF A STRING WE OWN.** `InGame.str`
  has a full `IDS_LanguageSelect_*` set (per-language names, `System Language`, a `DEV` slot,
  and a *"Applying this change will restart Forza Horizon 6"* confirm popup) ⇒
  **Settings → Language → "English UK" → restart**, and after the restart that entry reads
  **"עברית"** (the proof patches `IDS_LanguageSelect_GB`). No config file, no registry, no flag.
- **Scope = 58,179 records / 43,173 per-table unique / 37,488 GLOBAL unique / 37,099 real prose
  / 1.93 M chars.** Median 22 ch, p90 118, max 995 (`<=25` 20,703 · `26-140` 13,421 · `>140`
  2,975). Split by the engine's own table names: **UI/content 31,094 · dialogue-VO 11,474**
  (biggest: ChallengeData 4,487 · Dialogue 3,501 · Dialogue_Gameplay 1,697 · Dialogue_DJs 1,667).
  A single fleet pass, comparable to Uncharted LoT.
- **Tokens:** `{0}` ×1,405 (8 distinct) · `[TOKEN]` ×1,108 (486 distinct — `[PLAYERICON]`,
  `[GAMERTAG]`, `[Alt:…]`, `[SMALL:…]` and **`[HIGHLIGHT:{0}]`**) · `<tag>` ×583 · real newline
  ×825 · printf ×20 · **0** HTML entities. ⚠️ **`[HIGHLIGHT:{0}]` nests a brace inside a
  bracket — the token regex MUST be longest-first** or the guard splits it; `tools/fh6_rtl.py`
  already is (selftest 6/6).
- **🔑 THE ORACLE PANEL IS FREE AND UNUSUALLY RICH — 22 languages at 99.97-100 % id parity**
  (58,179 shared `(table,id)` pairs, same archive layout): **ru/pl/cz** give speaker AND
  addressee gender from the past tense, **es/fr/it/pt/br/mx** referent gender, **de** register.
  ⚠️ Only the 8 hash-clean zips are trustworthy as oracles until the install is repaired.
- **bidi = PREDICTED VISUAL, proof deployed.** The XAML UI (`media\UI.zip`, 455 files, Forza's
  "Anthem/AVUI" framework, 2,462 `IDS_` refs) sets `FlowDirection` 22× and **always
  `LeftToRight`**; every `RightToLeft` hit (29) is a `ControllerButtonPanel Layout=` or a
  slide-transition style NAME, `Bidi` (8) is an element name for a centre-out slider, and
  `Arabic`/`Hebrew`/`IsRtl`/`xml:lang` are **0 hits**. ⇒ no engine bidi expected. The proof
  decides; `fh6_rtl.to_visual` runs the real UBA (`python-bidi`, RTL base) with tokens stashed
  as atomic PUA placeholders, `\n` order-preserving, per-segment edge-strip.
- **🔴 FONT = the real gate, and it CANNOT BE ASSESSED until the install is repaired.** Fonts are
  proprietary `<name>.vfont` (descriptor: 128-byte name header + counts/floats) + `<name>.vfontN`
  atlas pages (not DDS), one family per script — `Horizon_A/B/C/D` (Latin), `Horizon_RU_A/C/D`
  (Cyrillic), `Horizon_CHS/CHT/JP/KO` (CJK) — routed by `fontsettings.xml` with an explicit
  per-language fallback chain that has **no Hebrew/Arabic entry anywhere**, so injection is
  certain to be needed (a GoWR/Plague-Tale-class sub-project, no public tool). **But
  `media\UI\Fonts.zip` fails its own xxh128 and the 7 descriptors that matter are not present in
  any recoverable form** — proved by a 4 KB-aligned scan of all 16 MB. Nothing about the format
  can be established from a damaged file.
- **✅ PROOF BUILT + DEPLOYED + VERIFIED (11/11 read back OUT of the live game file).**
  `work/build_menu_proof.py --deploy` patches `media\Stripped\StringTables\GB.zip` (backup
  `GB.zip.he_backup` + a sha sidecar recording BOTH `original_sha` and `deployed_sha`, so
  `--revert` **refuses** if a game update changed the file underneath —
  [[game-update-makes-backups-stale]]). One screenshot closes everything: a pure-Latin
  **`ZZ-FH6-OK-ZZ`** on the button prompts (mount, font-independent) · the SAME word `שלום`
  stored VISUAL on *Back* and LOGICAL on *Campaign* (bidi A/B) · `אבגד` (4 non-confusable
  letters) · **`1 שלום`** (the digit's side is unambiguous even if every letter is tofu —
  [[tofu-still-answers-bidi]]) · all 27 letters on *Creative Hub* (glyph coverage) · a
  quotes/parens/digits/Latin-island sentence in BOTH modes on *My Horizon* / *Online* (layout).
- **NEXT — the user must repair the install** (`forzahorizon6.exe`, `ObjectModelGame.zip`, a
  hash-valid `Fonts.zip`; `RapidCRC.exe` in the game root checks the shipped manifest, or run
  `work/check_install.py`), then **launch → Settings → Language → "English UK" → screenshot the
  pause menu**. Then: font sub-project → delegate the 37,099 lines
  ([[delegate-all-translation]], the free 22-language panel, key by `(table,IDS)`) → publish
  only on an explicit "פרסם". Revert:
  `python games/forza_horizon6/work/build_menu_proof.py --revert`.

---


