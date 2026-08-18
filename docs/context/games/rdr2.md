## Red Dead Redemption 2 Hebrew — PHASE 1 COMPLETE, every gate closed in-game, 🟢 GO (2026-07-20)

New game scaffolded at `games/rdr2/` (RECON/FEASIBILITY/PIPELINE + `work/`). Install
`C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2`. Engine = **RAGE**
(same company/family as GTA V) · archives = **RPF8** (`8FPR`, encrypted + Oodle
`oo2core_5_win64.dll`) — NOT RPF7, so GTA's `rpf7_reader.py` (magic `0x52504637`) does NOT parse
it. **Verdict 🟢 GO. Deploy needs NO RPF8 crack.** games.id (proposed) = **`rdr2`**. Memory
[[rdr2-groundwork-go]].

- **🔑 THE win — a complete open-source Arabic translation proves the whole chain in-game.**
  `github.com/Lore2x/RDR2-Arabic-Translation` (Ko Games) ships as **Lenny's Mod Loader (LML)
  loose files** (release `lml.zip`, dissected this session): `lml/mods.xml` + `KGF/asset_replace/
  font_lib_efigs.gfx` (Arabic-injected Scaleform, 3.28MB, `<FileReplacement>`) + `tranar/"Ko
  Games Studio.gxt2"` (25MB **plain-text** `KEY = value`, `<DataFile>`). So RDR2 = GTA-V/AC2/Anno
  class: **no Arabic locale → LML runtime string-override + VISUAL storage**, zero RPF write.
- **Text format** (the LML `<DataFile>`, misnamed `*.gxt2` but PLAIN UTF-8 TEXT): `KEY = value`
  per line, `#` comments. KEY = **label** (`LEGAL_SPLASH_1`) OR **joaat hex id** (`0x2B39B2B7`).
  Tokens = RAGE tilde controls (`~z~` dialogue [164k], `~s~ ~o~ ~d~ ~n~`, `~sl:a:b~` subtitle
  timing, `~1~/~2~`, `~COLOR_*~`, `~INPUT_*~`) — **identical to GTA V**. Codec
  `work/rdr2_text.py` (parse/serialise/`build_hebrew`, self-tested). ⚠️ **No value may contain
  `=`** — the LML `KEY = value` parser eats it (seen in-game); `build_legal.py` asserts on it.
  ⚠️ It started out reusing GTA's `visual_line`; proof #3 proved that WRONG for real sentences —
  the conversion now lives in `work/rdr2_rtl.py` (see the UBA bullet below).
- **Scope = 231,993 unique keys** (136,134 label + 95,834 hash), ~233k entries. `extract/
  key_universe.json`. Mostly subtitles + UI.
- **bidi = VISUAL** (definitive): the Arabic mod stores **85:1** presentation-form vs standard-
  block chars and **17,854** lines begin with the sentence-final `.` on the LEFT → the RAGE
  frontend does NO bidi + NO shaping. Store Hebrew **pre-reversed**; Hebrew has no shaping →
  simpler than Arabic. **CONFIRMED in-game 2026-07-19.**
- **🟢 FONT = BUILT (the hard gate, de-risked this session).** `font_lib_efigs.gfx` = Scaleform
  **GFX v8, 18 DefineCompactedFont faces** — **same family as GTA V's `font_lib_efigs_pc.gfx`**,
  loaded loose via LML `asset_replace` (game path `update:/x64/patch/data/cdimages/
  scaleform_frontend/font_lib_efigs.gfx`). Vanilla = 0 Hebrew. Downloaded **FFdec 26.2.1** →
  `swf2xml` (35s, ~350MB XML) → **`work/rdr2_font.py`** (reuses GTA's `font_add_hebrew.add_to_face`,
  auto-detects a 27-glyph donor; donor = `gtav/work/fontwork/gen_allheb.xml`) added **+27 Hebrew
  (U+05D0–05EA) to all 18 faces** → `xml2swf` (15s) → valid `font_lib_efigs_HE.gfx` (3,316,495B,
  +30KB). Ko Games' Arabic injection into this exact slot proves in-game render.
- **✅✅ MENU-PROOF PASSED IN-GAME (2026-07-19, user screenshots) — mount + font + RTL all
  CONFIRMED.** Shipped as a **one-extract drop-in** `RDR2_Hebrew_menu_proof_READY.zip`
  (`work/build_ready_dropin.py` = Ko Games' proven loader infra copied VERBATIM — `dinput8.dll` +
  `ScriptHookRDR2.dll` + `vfs.asi` + ModManager libs + `lml.ini`/`patterns.dat` — with ONLY the
  content swapped for our Hebrew font + text), so the user installs nothing else; guide in
  `games/rdr2/INSTALL.md`. Result: the boot splash rendered `ZZ-RDR2-OK-ZZ` + clean
  **right-to-left** Hebrew (**bidi = VISUAL confirmed** — a wrong mode would show it mirrored),
  the settings tiles showed **פקדים** (`PM_PANE_CON`) / **תצוגה** (`PM_SCR_DISPLAY`) in Hebrew
  beside the untouched English tiles, and **ZERO tofu** → the Hebrew-injected `font_lib_efigs.gfx`
  renders in the real frontend, i.e. **the font gate (the hard one) is CLOSED**. `~n~` breaks keep
  their line order. Revert = delete `dinput8.dll`. ⚠️ Two calibration notes (not defects):
  `TITLE_AUDIO` ("AUDIO") is NOT the Audio tile's key (tiles are `PM_PANE_*`/`PM_SCR_*`), and the
  marker line lives on the **second** splash screen (`LEGAL_SPLASH_1`) — the first shows
  `LEGAL_SPLASH_2`.
- **✅ PROOF #3 RAN (2026-07-19, user screenshots) — the user was right that a short-line menu
  proof clears nothing.** `work/build_proof3.py` → `RDR2_Hebrew_proof3_READY.zip`. Results:
  - **🔴 LONG PARAGRAPH + engine auto-wrap = BROKEN, exactly as predicted.** With the paragraph
    stored RAW the markers rendered `(5)(6)` on the FIRST line and `(1)(2)` on the LAST — the
    engine wraps in STORAGE order, so a VISUAL paragraph comes out **line-order inverted** (read
    bottom-up). **The SAME text PRE-WRAPPED with explicit `~n~` rendered CORRECTLY, `(1)→(6)`
    top-down** ⇒ pre-wrapping is the fix and it works. It needs the per-surface box width →
    proof #4 measures it.
  - **✅ The big distressed "ALERT"/death/mission-fail text is a FONT, not an image.** Predicted
    from the data (Ko Games translate `WARNING_EXIT_WINDOWS`/`ALERT_PLAYER_DEAD`/`MC_FAIL`/
    `CHAPTER_1` while shipping ONLY `font_lib_efigs.gfx`) and then CONFIRMED in-game: "אזהרה"
    rendered in the big title face with the `~n~` body correct. ⚠️ cosmetic — our injected glyphs
    are clean outlines, so the Hebrew title lacks the western **grunge texture** baked into that
    face's Latin glyphs (optional Phase-2 polish: distressed Hebrew glyphs for the title face).
  - **✅ Mixed EN+HE** — Latin runs and digits forward and correctly placed.
- **🔴🔴 THE BUG PROOF #3 FOUND — multi-character NEUTRAL runs were mis-placed, and it would have
  corrupted most of the corpus.** `gtav_gxt2.visual_line` reverses Hebrew runs, flips the run
  ORDER, and keeps every non-Hebrew run **FORWARD** — treating a punctuation run like a Latin
  island. But a neutral run belongs to the RTL flow and must be reversed (and brackets mirrored):
  `סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה. סוף!` rendered with the colon before the wrong
  word, `(סוגריים)` shown as `)סוגריים(`, and every comma/period on the wrong side; `ב-45.50 דולר`
  came out `ב- 45.50דולר`. **It is INVISIBLE on a one-clause menu label — a 1-char neutral run
  reverses to itself, which is exactly why `?` and `—` looked perfect in the menu proof — and
  wrong on essentially every real sentence.** **FIX = `work/rdr2_rtl.py` (NEW): run the real
  Unicode Bidi Algorithm** (`python-bidi`, already in the repo `.venv`) with an RTL base and store
  its visual output — the right tool *precisely because* the engine does no bidi (we do the
  engine's job offline), giving correct neutral resolution + L4 bracket mirroring for free.
  **Byte-identical to the old function on every case already confirmed working in-game (zero
  regression).** RAGE token handling matched to Ko Games' shipping Arabic: leading control tokens
  stay at the FRONT (**all 162,997 of their `~z~` lines start with it, 0 elsewhere**); `~n~` and
  `~sl:a:b~` are ORDER-PRESERVING segment separators so line order + subtitle timing stay bound to
  the right text; inline tokens become private-use placeholders so UBA treats each as one atomic
  LTR run. `rdr2_text.build_hebrew` now uses it and gained `wrap_width=`. Selftests 12/12 + 14/14.
  **⚠️ CROSS-GAME: GTA V ships the SAME `visual_line` → it very likely carries this identical
  mid-sentence punctuation defect; audit `games/gtav` before its next release.**
  **UNIVERSAL: for a store-VISUAL engine, do NOT hand-roll run-reversal — run the actual UBA with
  an RTL base and protect the engine's tokens; hand-rolled reversal is right only for 1-char
  neutrals, so a menu proof passes while the whole corpus is quietly wrong.**
- **✅✅ PROOF #4 PASSED (2026-07-19) — PHASE 1 IS COMPLETE, every gate closed.**
  `work/build_proof4.py` → `RDR2_Hebrew_proof4_READY.zip`, deployed straight into the live game
  folder (game closed; only the 2 content files swapped — the loader was already there).
  **Punctuation/brackets render exactly right** (`סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה.
  סוף!` and `מספרים: 1, 2 ו-3. שאלה? תשובה: כן.`), **mixed EN/HE spacing fixed**
  (`ב-45.50 דולר … 12/04/1899, ואז נסע 3 ק"מ.`), **the pre-wrapped paragraph reads (1)→(6)
  top-down**. **📏 WIDTH MEASURED on the boot/legal splash: 120 chars fit on ONE line, 130 wraps**
  → usable 120–129, recorded as `rdr2_rtl.WIDTH_SPLASH = 110` (margin for wide letters). The 130
  line also re-demonstrated the inversion — once it overflowed, its head marker jumped to the
  SECOND line, i.e. the ruler catches the failure by itself.
  **Corpus exposure to the wrap rule** (EN chars, tokens stripped): >60 **27,300 (12.5%)** · >80
  **14,076** · >100 **7,756** · >120 **4,952 (2.3%)**; longest value **1,487**. At the splash
  width only ~2% needs pre-wrapping, but the SUBTITLE box is far narrower → its own ruler run in
  Phase 2 will raise that a lot. **UNIVERSAL: measure a text box with a RULER string — lines of
  exactly N chars stamped `[N]` at BOTH ends; the largest N whose two markers stay on one line is
  the usable width. One screenshot, no guessing, and it transfers to every surface and game.**
- **✅ PROOFS #5–#6 — paragraph LAYOUT solved (the last real gap; user-driven).** Proof #4's
  paragraph decoded perfectly and still READ broken: it was wrapped at 70 chars inside a ~120-char
  box, and **the game's boxes are LEFT-aligned and JUSTIFY only the lines THEY wrap** — our
  explicit `~n~` lines are each treated as a final line, so nothing is justified and the RIGHT
  edge (where an RTL reader's eye starts) came out ragged. Proof #5 right-aligned by padding each
  visual line's LEFT with `width - len(line)` SPACES → in-game it landed **CENTRED, not right**.
  The user diagnosed it from the screenshot ("if it can reach the middle, it should be able to
  reach the right"): direction right, MEASURE wrong. **🔑 The font is PROPORTIONAL — a space
  advances 60 units, an average Hebrew letter 129, so ONE LETTER ≈ 2.2 SPACES** and one space per
  missing CHARACTER buys ~45% of the distance (exactly the observed half-way result).
  **FIX — `work/rdr2_metrics.py` (NEW): use the font's REAL advances.** Every
  `DefineCompactedFont` face in the FFdec XML ends with a `glyphInfo` array (`advanceX` per
  `glyphCode`, units of `nominalSize`=256) — it streams the 350 MB XML once and caches all **18
  faces** (`font_metrics.json`, 264 KB) with `text_width`/`wrap_px`/`pad_spaces`;
  `rdr2_rtl.wrap_visual_px` does BOTH the wrap and the padding in font units. Budget calibrated
  straight from the proof-#4 ruler (120-char line = 13,537 units FITS, 130 = 14,849 does not →
  **13,500 safe**). **✅ Proof #6 PASSED in-game:** all 4 lines measured 13,474–13,528 units
  (<0.4% spread) with a true flush right edge, short last line included; two candidate faces both
  rendered correctly (all candidates measure the same ruler within ~4%, so the face pick is not
  critical). Lines 1–3 needed 1–5 padding spaces, only the last needed 71.
  **UNIVERSAL: in a proportional font, NEVER wrap or pad by character count — pull the real glyph
  advances (they are already in the font you inject into) and measure in font units. A char count
  is off by ~2× for Hebrew-vs-space, which is exactly the difference between centred and
  right-aligned. And when an engine left-aligns + justifies only its OWN wrapped lines, explicit
  `~n~` lines must be right-aligned by padding or an RTL paragraph reads as broken even though
  every character is correct.**
- **✅ PROOF #7 — the residual killed; layout is now exact (0.2% spread).** Proof #6 still left the
  LAST line ~50px short while lines 1-3 were flush. Cause: a GREEDY wrap dumps the remainder on the
  final line (13224/13272/13414/**9268** units) so that line alone needed a **71-space** pad, and
  any error in the assumed space advance is multiplied by exactly that count. Two fixes:
  (1) **`rdr2_metrics.wrap_px_balanced`** binary-searches the smallest target width that still
  yields the same line count → widths even out (12810/12823/12646/12191), every pad falls to 12-23,
  and the same relative error becomes ~3px instead of ~50px.
  (2) **Stop guessing the space advance — make the GAME measure it.** We do not know which of the
  18 faces a surface renders with (they disagree 52-60 units = up to 15%). A LADDER of rows
  "N spaces + the number N" (N = 200…400) placed under the known-to-fit 120-char ruler answers it
  with NO face assumption: **N=200 fits and stops ~110px short; N≥240 OVERFLOWS and wraps** (the
  number drops alone onto the next row, and the doubled row-spacing gives it away) ⇒ **a full box
  ≈ 225 spaces**, so space ≈ 58 units vs the table's 60 — the model was right to within ~3% all
  along. Pinned as `rdr2_metrics.SPACE_UNITS_MEASURED = 58`, preferred by `space_width()`.
  Result: all 4 lines total 13,506–13,525 against a 13,500 budget and render flush right.
  **UNIVERSAL: (a) BALANCE the wrap — never let one line carry a huge pad, because the pad count
  multiplies every metric error; (b) to measure a font metric you cannot look up, build a LADDER
  that brackets it (N spaces + a visible marker) and read the answer off one screenshot — the row
  that overflows is as informative as the row that fits.**
- **🔴 Stray left indent from whitespace around `~n~` (user-spotted, fixed in the codec).** A header
  written as `"…~n~ מבחן 7… ~n~ …"` rendered its MIDDLE line indented by one space. Under an RTL
  base the logical-LEADING space moves to the visual END and the logical-TRAILING space moves to
  the visual START — i.e. into the LEFT margin, where it shows. The signature is diagnostic: only
  the line padded on BOTH sides was affected (the Latin-only line is never converted, and a line
  padded on one side only puts its space where it does not show). `rdr2_rtl._segment_to_visual`
  now `.strip()`s each segment first — a separator IS the line break, so whitespace around it is
  decorative, and stripping also keeps the `align_right` pad exact (the pad is prepended after).
  **UNIVERSAL: always strip a segment's edge whitespace before a logical→visual conversion;
  harmless-looking spaces around a line-break token become a visible margin indent.**
- **🔴 The real answer to "the first line starts with a space": FULL JUSTIFICATION, not
  right-alignment.** Right-aligning by padding each line's LEFT margin necessarily leaves the left
  edge ragged, so the paragraph's first line visibly starts indented — and **the game's own English
  paragraphs are JUSTIFIED (flush both edges)**, which is what the Hebrew was being compared to.
  `rdr2_metrics.justify` puts the slack in the word GAPS instead; `rdr2_rtl.justify_visual_px`
  justifies every line EXCEPT the last (typographic rule: a final line stays ragged, and in RTL
  "ragged" means flush RIGHT where reading starts). Result: lines 1..n-1 have ZERO leading spaces.
  **UNIVERSAL: match the surrounding text's alignment MODEL, not just its direction — an RTL block
  that is merely right-aligned still reads as misaligned beside justified LTR text.**
- **🔴 Rounding + metric inconsistency can silently re-break the layout.** Two bugs found by
  measuring the built file rather than trusting the builder: (a) `round()` in justify/pad could
  push a line OVER the budget, and an over-budget line gets wrapped by the engine — which
  reintroduces the inverted line order the whole pre-wrap exists to prevent → both now **floor**;
  (b) `justify` inserted spaces counted at the MEASURED advance (58) while `text_width` measured
  them back from the FACE TABLE (60), so every injected space added a hidden 2 units and a line
  with ~90 of them overshot by ~180 — **12 of 18 lines were over budget**. `text_width` now takes
  the space width from `space_width()` too. **UNIVERSAL: when a value is both COMPUTED WITH and
  MEASURED BY a metric, both sides must read it from the same source — internal consistency beats
  accuracy; and always verify the BUILT artifact's line widths, not the builder's intent.**
- **🔴 JUSTIFY ≠ BALANCE — combining them tore huge holes in the text.** The first justified build
  rendered with enormous word gaps. Cause: `justify_visual_px` wrapped with `wrap_px_balanced`
  (which SHRINKS lines so their widths match) and then stretched every line back to the FULL
  measure — a line balanced to ~6,800 units stretched to 13,500 is nearly double, and all of that
  slack goes into the gaps. **Justified text must be wrapped GREEDILY at the full measure** (each
  line then already sits near it, so the stretch is a few spaces); balancing belongs only to the
  RAGGED path, where its job is keeping the margin pads small. **UNIVERSAL: balancing and
  justification are alternatives, never a pipeline — balancing removes exactly the fullness that
  justification then has to re-create as white space.**
- **🔴 Never justify a line broken before a long unbreakable token.** `LEGAL_SPLASH_2` breaks right
  before `http://www.rockstargames.com/socialclub.` (~5,000 units), so that line was ~5,000 short
  and justification opened 7-space gaps — classic "rivers". `justify_visual_px` now leaves any line
  needing more than `MAX_GAP=2` extra spaces per gap RIGHT-ALIGNED instead (slack in one margin,
  which is what a typesetter does). Result: worst gap across all four strings is 2 spaces.
- **✅ REAL DELIVERABLE — the boot legal splash is genuinely translated** (`work/build_legal.py`):
  all four `LEGAL_SPLASH_*` strings (the game's own copyright / EULA / Social-Club / fiction
  disclaimer, 305-746 chars each) in Hebrew through the finished chain. 18 lines, every one
  13,443-13,500 units against a proven-fitting 13,537 → **0 over budget**. URLs stay Latin (UBA
  keeps them forward), `©`/`™` verified present in the font, `~n~~n~` paragraph breaks preserved by
  justifying each block separately. ⚠️ **No value may contain `=`** — the LML `KEY = value` parser
  eats it (seen in-game); `build_legal.py` asserts on it. Translation authorship here is the usual
  one-off user override of [[delegate-all-translation]]; the ~218k corpus still goes to the fleet.
- **✅ English corpus SOLVED (93.9%, fully automated, NO TFIT crack).** RPF8's TOC is **TFIT**-
  encrypted (rpf-rs "keys not held"; OpenIV/CodeX-gated) — but **we don't need it** (deploy = LML
  loose files; TFIT only gates WRITING inside RPF8). The English is a public dump
  `github.com/cedricalpatch/Red-Dead-Redemption-2-Text-Files` (2,204 txt, same `KEY = value`,
  **hash-keyed**, 233,262 entries). Join to our keys: hashes direct; **labels via `joaat(label)`→
  hash** (reused `gtav_gxt2.joaat`) → **217,758/231,968 (93.9%)** have English (labels 92.1%,
  hashes 96.3%) → `extract/en_corpus.json` (keyed by Ko Games key, drops into the LML text file).
  ~6% missing = RDR Online content (SP unaffected); 592 mojibake artifacts to clean in Phase 2.
  RPF8 format fully MAPPED (header Magic+EntryCount+NamesLen+DecryptTag+Platform → RSA sig 256B →
  entries×24; magic `0x52504638`) for reference. Ko Games `{key→Arabic}` (VISUAL) kept as gender oracle.
- **📊 LINE REPORT (Phase-2 scope, from `extract/en_corpus.json` = 217,758 keys with English).**
  By TYPE: **subtitles/dialogue (`~z~`) 158,720** (5,432,013 chars — 10,637 timed cutscene `~sl:`
  + 148,083 untimed ambient/interaction barks) · **UI/text content 59,038** (2,546,911 chars),
  broken down as items/gear/shop 10,386 (`CLOTHING_` 7,273 · `PROVISION_` 1,826 · `HORSE_` 726 ·
  `COMPONENT_` 662 · `CONSUMABLE_` 388) · menus/settings/HUD 803 · missions/objectives 137 ·
  help/tutorial 115 · other content + hash-only keys 47,597 (documents/letters/speakers/
  challenges). By MODE: **story mode 213,557** (holds ALL 158,720 dialogue lines) vs **RDR Online
  4,201** (`MP*`/`NET*`/`FME*`/`PXPT*`, zero dialogue → droppable for a SP-complete ship). By
  LENGTH: ≤25 chars 101,286 · 26–140 112,827 · >140 3,645 (only the 3,645 long ones are exposed to
  the paragraph-wrap question above).
### RDR2 — tool inventory + how to build/deploy (operational)

| File (`games/rdr2/work/`) | Role |
|---|---|
| `rdr2_text.py` | LML `KEY = value` codec — parse/serialise/`build_hebrew(wrap_width=)`. Selftest 14/14. |
| **`rdr2_rtl.py`** | logical→VISUAL via the real UBA + token protection; `wrap_logical`, `wrap_visual_px`, **`justify_visual_px`**, `WIDTH_SPLASH`. Selftest 12/12. |
| **`rdr2_metrics.py`** | real glyph advances from the font XML (18 faces cached in `font_metrics.json`); `text_width`/`wrap_px`/`wrap_px_balanced`/`justify`/`pad_spaces`; `SPACE_UNITS_MEASURED=58`. |
| `rdr2_font.py` | +27 Hebrew glyphs into all 18 Scaleform faces (reuses GTA's `font_add_hebrew`). |
| `build_ready_dropin.py` | one-extract drop-in (Ko Games loader infra verbatim + our font/text). |
| `build_proof3/4/5/6/7.py` | the in-game proofs, each isolating one gate (keep as regression templates). |
| **`build_legal.py`** | the real deliverable: the 4 `LEGAL_SPLASH_*` strings, `--deploy`. |
| **`build_ct_strings.py`** | the `/translate` upload — 6 Hebrew categories by visibility + the Arabic gender source per line. |

**Run everything with the repo `.venv` python** (`python-bidi` + `fontTools` live there; an IDE
analyser pointed at the base interpreter falsely reports `bidi.algorithm` missing).
**Deploy** = the loader is already installed in the game folder, so a build only swaps two files:
`lml/tranar/Ko Games Studio.gxt2` + `lml/KGF/asset_replace/font_lib_efigs.gfx`. **Close the game
first.** Revert everything = delete `dinput8.dll` from the game root. Guide: `games/rdr2/INSTALL.md`.

### ✅✅ `.yldb` CRACKED — the game's OWN text + ALL 13 professional translations (2026-08-07)

Unpacking the archives paid for itself immediately. RDR2's text is **not** GXT2: it is
`data/lang/<language>_rel/*.yldb` ("language database"), a RAGE resource whose payload is a
flat array of **64-byte nodes** with the strings inline in the same buffer:
`+0x00 u64 strPtr` (RSC virtual pointer, file offset = `ptr & 0x0FFFFFFF`) · `+0x08 u64 strLen`
(**including** the NUL) · `+0x10 u32 hash` — and that hash is **exactly the `0xHASH` key the LML
mod overrides**, so a decoded entry drops straight into the build. Reader:
`games/rdr2/work/yldb.py`; harvester `work/extract_game_text.py` →
`extract/game_text/<lang>.json`. **13 languages / 2,185,511 strings**, English 167,151.
- **🔑 SCAN + SELF-VALIDATE, don't trust a header.** The extractor strips each resource's
  16-byte header, so absolute header offsets are unreliable. Walking a 16-byte grid and
  keeping only nodes whose pointer lands in the file, whose length ends exactly on a NUL, and
  whose body decodes as UTF-8 with no embedded NUL, is self-proving and immune to that.
- **🔴🔴 THIS IS WHAT "MANY TEXTS ARE STILL ENGLISH" WAS.** The old corpus came from a public
  English dump covering **93.9 %** of the keys; the rest shipped in English. Diffing the game's
  real key set against the Hebrew spine: **31,632 keys missing, 28,101 with real text** —
  including the exact mission-board lines in the user's screenshots (`Jack has asked for a
  Penny Dreadful book.` = `0x4CFE94FA`, absent from the corpus entirely, while the *similar*
  `Find Jack a Penny Dreadful book.` was translated — which is why it looked random).
  **UNIVERSAL: a community text dump is a CONVENIENCE, never the key set. Diff it against the
  game's own container before believing a coverage number** — and the leftovers are not a
  random 6 %, they are whole SCREENS.
- **🔑 It also hands over a free New-Era panel.** Every missing line now ships with up to 7
  professional translations (ru/pl give speaker AND addressee gender, de register, fr/es/it/br
  referent) — 93.9 % of the 28,101 have one, averaging 5.2 languages. `rdr2_nim._payload` was
  widened from `{en, ar}` to the full panel and the prompt now ranks the languages by what each
  one settles.
- Fleet: `fleet/build_missing_corpus.py` (visibility-ordered: UI/missions 14,776 before dialogue
  13,325) → `split_missing.py` / `reslice_missing.py` → `deploy_all21.sh` → `pull_missing.sh`
  (validate-before-replace + name-canon at merge) → `hebrew_missing.json`, which `build_full.py`
  merges in automatically. Scheduled task `RdrMissingPull` every 5 min.

### 🔴🔴 The fleet ran at 1/8 speed because a TOKEN BUDGET was calibrated for the OLD payload (2026-08-07)

The 28,101-line run measured **~15 lines/min across 21 streams** — a 29-hour ETA against a
next-day deadline — and every instinct said "the free tiers are throttling". They were not.
The worker log said it in one line: **`pass: 1307 left, 920 batches`** — *1.4 lines per API
call*. `BUDGET = 150` had been sized when a line shipped as `{en, ar}` (median 30 tokens);
attaching the 7-language New-Era panel took the median to **107**, so the packer put almost
every line in a batch of its own and the fleet made 20× the calls it needed.
- **The fix is the PACKER, never the panel.** `BUDGET 150 → 1800` + a hard `MAXLINES = 24`
  (a token budget alone lets 90 two-word UI labels into one call, and past ~25 ids the model
  starts omitting — each omission costs a single-line re-ask and eats the gain). Measured over
  the real corpus: **1.4 → 10.5 lines/call, 7.5× fewer calls**, batch size median 8 / max 24.
  Do NOT trim the reference panel to chase speed — that was measured elsewhere and latency is
  queue variance, not prompt size ([[new-era-doctrine]]).
- **Re-derive `max_tokens` from the KEYS + ENGLISH, not from the batch's token estimate** —
  the estimate now counts the whole panel, but the model only writes Hebrew for the English
  while echoing every id verbatim, and a reasoning model spends its thinking against the same
  ceiling ([[reasoning-model-max-tokens-truncation]]).
- **UNIVERSAL: a batch token budget is a property of the PAYLOAD. The moment you widen what a
  line carries — a reference panel, context, a glossary — re-measure lines-per-call. Nothing
  fails, nothing errors; the fleet just quietly costs an order of magnitude more, and it looks
  exactly like provider throttling.** The diagnostic is one number in the worker's own log
  (`N left, M batches`); read it before touching a provider.

**Two other throughput leaks found in the same pass, both invisible from the dashboard:**
- **The DESKTOP workers had no relaunch task and had silently died** (3 of 21 streams, logs
  frozen 20 min, zero processes). CLAUDE.md's own note says a local `Start-Process` persists —
  it does not when the launching shell is a tool call. Fixed with a **user-level** scheduled
  task (`RdrMissingDesk`, 5 min) driving `hidden.vbs → run3.bat`; `/ru SYSTEM` needs elevation
  this shell does not have, and a user task is enough while the user is logged in.
- **Skyrim was still running on vm/vm2/vm3 and sharing the SAME provider keys.** Exactly the
  documented trap: a finished project keeps competing for the live fleet's quota and the only
  symptom is more 429s. Killed + `SkyrimMP`/`MPBoot`/`FleetPull` disabled on all six machines
  (re-enable after RDR2 ships).
- **⚠️ Stop fighting ssh quoting when you need a process list: a `CommandLine -match` filter
  sent through nested quotes returns 0 on EVERY machine and reads as a fleet-wide outage.**
  Cross-check with a filter-free `tasklist` first, then send the real query as
  `powershell -EncodedCommand <base64 UTF-16LE>` — that is what exposed the Skyrim processes.
  **The same broken filter then silently made my own KILL a no-op**, so a "push + restart"
  left every machine running the OLD code while the new launches sat blocked on the singleton
  lock — and the fleet looked mysteriously immune to a fix that had already shipped. If a kill
  reports success, VERIFY the count afterwards.

**🔴🔴 THE HEAL TASK WAS EATING THE FLEET — a relaunch must be a NO-OP when the thing is alive
(`fleet/relaunch.ps1`).** Workers were replaced at EXACTLY 04:16:02 and 04:21:02 — the 5-minute
task boundaries — so every stream got ~5 minutes, finished ~2 batches, threw away its in-flight
work and re-did the pass setup. Two independent faults in the documented `run3.bat` pattern:
1. **It relaunched unconditionally.** `acquire_singleton` only stops the NEW process; it cannot
   protect the old one, and `_alive()` resolving a pid's CommandLine is exactly the call that
   fails under a scheduled-task context. **The launcher itself must check per provider and
   start only what is missing** — then the heal is free to run every 5 minutes forever.
2. **🔴🔴 `start "" /B` LEAVES THE WORKER INSIDE THE SCHEDULED TASK'S JOB OBJECT, and Task
   Scheduler tears that job down on the NEXT trigger — so a 5-minute heal task does not
   relaunch the fleet, it KILLS THE WHOLE FLEET EVERY 5 MINUTES.** Proven, not inferred: a
   probe at 04:29 reported `live=` **EMPTY on all seven machines at once** (21 of 21 streams
   dead simultaneously — no per-machine failure is ever that tidy), and every worker's
   creation time was exactly a trigger instant (04:16:02, 04:21:02). Each stream therefore
   lived 5 minutes, finished ~2 batches, discarded its in-flight work, and the next process
   re-did the pass setup. **Fix: `Start-Process cmd /c "<py> … >> log 2>&1"`** — no `start`,
   no `/B`; an independent process whose lifetime IS the worker's, outside the task's job,
   and `>>` keeps the log history.
**🔴🔴 `max_tokens` IS A RATE-LIMIT COST ON GROQ — the "give a reasoning model more room" rule
has an opposite edge, and this run hit it.** groq's `openai/gpt-oss-120b` returns its thinking
in a separate `reasoning` field and leaves `content` **EMPTY** until the reasoning finishes, so
a too-small budget yields a perfectly valid response with **no answer at all** — measured live:
a 24-line batch came back `ok=True, answered=0`. The instinct
([[reasoning-model-max-tokens-truncation]]) is to raise `max_tokens`. **On groq that makes it
strictly worse: the value is RESERVED against the tokens-per-minute budget whether or not it is
used.** The same 6-line batch returned **HTTP 429 at mx=4000, at 12000 AND at 16000**, while a
200-token "Say OK" answered in **0.4 s** on the same key. ⇒ keep the reservation tight
(`min(3000, 900 + …)`) and let the single-line re-ask cover a genuine truncation.
- **Corollary — batch size is PER PROVIDER, because their limits differ in KIND:** nim has a
  generous quota and is slow per call, so a big batch is pure win (24/24 accepted live);
  groq is fast but TPM-capped, so a 24-line batch reserves enough to 429 the key instantly and
  **the fastest provider was contributing the least**. Shipped `MAXLINES = {groq: 8,
  sambanova: 16}.get(prov, 24)`.
- **✅ THE FIX THAT ACTUALLY UNBLOCKED GROQ: rotate MANY KEYS PER PROVIDER, and cool the KEY,
  not the provider.** `fleet_providers.load_keys` accepted one key per provider, so each
  machine hammered a single groq key into a 429 within a couple of batches — while the shared
  key file held **10 keys per provider and only 7 were ever used**. `keys.json` now accepts a
  LIST (a bare string still works), `Fleet` round-robins within a provider with a per-`(provider,
  key)` cooldown, and the whole provider is parked only once EVERY key is cooling. Each machine
  gets the same 10 keys ROTATED by a different offset so seven machines don't all start on
  key[0]. Measured immediately: the identical batch went from **60.6 s → 0.5 s to fail over**,
  and at `max_tokens=2500` groq answered **8/8 in 3.1 s**.
- **🔑 The sweep that settled it, and why it had to be a sweep:** `mx=1500 → 429 · 2500 → 8/8 in
  3.1 s · 4000 → 8/8 · 6000 → 8/8`. Too small and `content` comes back empty (all budget spent
  on reasoning); too large and the reservation 429s the key. **There is a WINDOW, not a floor** —
  and the two failure modes look identical from the outside (`answered=0`), so only varying the
  value across a range tells them apart.
- **🔴 And an EMPTY reply was being reported as a successful one.** `chat()` swallows the
  provider exception and returns a bare `{}`, so the 429 never reached `do_batch`'s except and
  the caller was told "the model replied and dropped every key" — which charges an omit to each
  line, and `MAX_OMITS` then PARKS good content. `do_batch` now treats an empty reply to a
  multi-line batch as **no-reply** (blameless, re-served). Same family as silent-failure #4:
  *"a strike must be driven by a RESPONSE ABOUT THAT ITEM"*.

**🔴🔴🔴 AND THE ACTUAL KILLER, found after all of the above: `SkyrimWatchdog` was EXECUTING
THE RDR2 FLEET.** `games/skyrim/fleet/skyrim_watchdog.ps1` carried
`$ZOMBIE = 'rdr2_nim|cc_nim|pt_nim|w3_nim|w3ut_nim|w3qa_nim|ac2_nim|cpqa_nim'` and force-killed
every python matching it, on every machine, on a recurring task. That list was CORRECT when it
was written — Skyrim was the live fleet and those games were retired. **Then the roles swapped**:
Skyrim finished, RDR2 became the live 21-stream run, and a retired project's janitor spent the
night murdering the active fleet every few minutes.
- **It is invisible by construction.** `Stop-Process` raises nothing, so the worker's log simply
  stops mid-pass, `e_*.log` stays empty, there is no exit code and no traceback — the exact
  signature of "the model is slow" or "the provider is throttling". The batch budget, the
  launcher form, the task job object and the provider quotas were each investigated and
  partially fixed FIRST, because all four produce the same silent stall.
- **The tell that finally isolated it:** a probe reported `live=` **EMPTY on all seven machines
  simultaneously**. Nothing organic kills 21 streams across 7 hosts at the same instant — that
  shape means something is sweeping them centrally. Then: audit every ENABLED scheduled task for
  one that kills processes, not just the tasks belonging to the game you are debugging.
- **RULE: a janitor may only ever kill ITS OWN workers.** Never hardcode another project's
  worker name into a recurring cleanup. A retired fleet gets swept ONCE, by hand — a recurring
  task outlives the project it belonged to, and the day the roles reverse it becomes a weapon
  pointed at whatever is live. (`$ZOMBIE` is now a never-matching placeholder, and the four
  Skyrim tasks are disabled on all seven machines.)

**UNIVERSAL — two rules, the second one being the expensive one:**
**(a) a self-heal that cannot tell "alive" from "absent" does not heal, it churns; verify one
by running it TWICE — the second run must start nothing.**
**(b) `start /B` from a scheduled task is NOT detached. If every machine's workers share the
same age and that age is a multiple of the task interval, the TASK is killing them.** This
hid behind every other symptom — no errors, no 429s, healthy-looking logs — and presented
purely as a throughput ceiling that reads exactly like provider throttling.

### 🔴🔴 …AND THE QUOTA WAS STILL HALVED: 21 ZOMBIE Skyrim workers, because "I stopped Skyrim" was never verified (2026-08-07)

Even after all of the above the rate stayed capped. A **filter-free** process dump found
**3 `skyrim_nim` workers alive on EVERY ONE of the 7 machines = 21 of them**, drawing on the
**identical API-key pool** as the 21 RDR2 streams. I had "stopped Skyrim" earlier and written
it down as done. Two independent reasons it was false, and both are silent:
1. **The kill went through an inline ssh `Get-CimInstance … | Where CommandLine -match`, and
   that filter matches NOTHING through nested ssh quoting** — `Stop-Process` was never called
   and the command still exited 0 with no output. **The same broken filter had separately
   produced a fleet-wide false `workers=0` alarm**, so one bug generated both a phantom outage
   and a phantom fix.
2. **Disabling the scheduled tasks does NOT end the instance already running.** All three
   Skyrim tasks read `Disabled` while their processes ran on — a worker only exits when its own
   slice drains, and Skyrim had ~36k lines left.
**Fix: `scp` a small `.ps1` to each host, run it with `powershell -File`, and have it PRINT
what it killed AND what survived** (`skyrim_killed=3 rdr2=groq,sambanova,nim`) — then re-count
**filter-free** (`tasklist /FI "IMAGENAME eq python.exe" /NH | grep -c`). Result: 21/21 RDR2
streams confirmed, 0 Skyrim.
**UNIVERSAL: a filtered count of 0 is worthless — it is the same value a broken filter returns.
Verify a kill by RE-COUNTING without the filter, and when a fleet is capped for no visible
reason, enumerate EVERY process on EVERY machine and read its command line before touching
batching, keys or providers. A retired project's workers competing for the same quota are
completely invisible in your own logs.** [[verify-a-kill-by-recounting]]

### 🔴 The `401 Unauthorized` in the worker log was the LEGACY FALLBACK, not a dead key (2026-08-07)

`w_groq.log` was full of `step1 fail (HTTP Error 401: Unauthorized) — skip batch`, which reads
as a revoked key. Probing every key through the real endpoint said otherwise: **all 10 groq
keys answered OK or 429, none 401.** Cause: `chat()` swallows a fleet failure and then falls
through to the ORIGINAL single-provider NVIDIA path, which posts whatever `_KEYS` holds to
`integrate.api.nvidia.com` — so a **groq-pinned** stream was sending a groq key to NVIDIA.
Every fleet failure therefore cost a second, guaranteed-doomed call AND logged a misleading
reason. Fix: on a PINNED worker (`_PIDX >= 0`) return `{}` instead of falling through — which
`do_batch` already treats as a blameless "nobody replied".
**UNIVERSAL: when a multi-provider adapter is bolted onto a single-provider worker, delete the
legacy fallback for pinned streams — otherwise every failure is reported with the WRONG
provider's error, and you will chase a key that was never broken.**

### 🔴🔴 THE REAL CEILING: A MODEL IS ITS OWN RATE BUCKET (2026-08-07) — 19 → far higher

With Skyrim gone, the keys rotated and the 401 noise removed, the fleet still crawled at
**19 lines/min**. Counting SUCCESS vs FAILURE per provider from the workers' own logs named it
instantly — and this ratio is the diagnostic, not "is it alive":
| provider | usable output | verdict |
|---|---|---|
| nim | **231 of 240 (96 %)** | healthy |
| sambanova | 218 of 326 (67 %) | recovering |
| **groq** | **16 of 244 (6.6 %)** | effectively dead |
And yet **the very same groq model answered 8/8 in 1.2 s when probed alone.** It was never
broken — 7 machines were sharing ONE model's quota. Same story on sambanova: **all 10 keys
returned `429 Rate limit exceeded` for `DeepSeek-V3.2` simultaneously** (which reads exactly
like a spent account) while those same keys answered **4/4** on `DeepSeek-V3.1`,
`Meta-Llama-3.3-70B-Instruct` and `gemma-4-31B-it`.
⇒ **the free-tier quota belongs to the (account, MODEL) pair.** `PROVIDERS` now takes a LIST of
models and `_model_for()` pins each machine to a different one — index from `FLEET_MODEL_IDX`,
else a `model_idx.txt` written by the deploy (7 machines → **3/2/2**), else a hostname hash
(**assign it explicitly; a hash piles machines onto one bucket**). Immediate effect on the
desktop's groq stream: `+0/8` every batch → **`+7/8`**, slice 328 → 500.
Second change on the same restart: a pinned worker now carries a **second, UNPINNED `Fleet`**
and BORROWS another provider when its own has every key cooling — which slice a worker owns is
independent of which endpoint answers it, so the slices stay disjoint and a 60 s cooldown stops
being dead time.
**UNIVERSAL: probe candidate models with a REAL batch of the actual corpus, never `"hi"` — a
trivial prompt succeeds on a model that returns an empty `content` for an 8-line JSON task, so
it cannot rank candidates. And only list a model you have verified returns complete, well-formed
output, not merely a 200.** [[a-model-is-its-own-rate-bucket]]

⚠️ **A worker count of 6 per machine was NOT duplicates** — the VMs have no
`…\Programs\Python\Python313\python.exe`, so the launcher fell back to the **WindowsApps store
stub**, which re-execs the real `pythoncore-3.14-64\python.exe` as a CHILD: 2 processes per
stream, 3 real workers. Acting on that miscount ("dedupe") killed the real workers and left the
machine at zero. **Read the parent/child pids before treating a doubled count as duplication.**
⚠️ And two overlapping launches **mutually killed each other**: both sets wrote the singleton
lock before either checked it, so each saw the other's pid and exited — a machine that had 6
processes went to 0 on its own. Relaunch SEQUENTIALLY (remove locks, one provider every few
seconds), never two sets at once.

### 🔴🔴 SPEED IS WORTHLESS IF THE OUTPUT ISN'T — the 1 % spot-check caught a model writing WORD-BY-WORD Hebrew

Minutes after the throughput fix, a sample of real lines from each NEW model showed
`openai/gpt-oss-20b` translating token-for-token: *"A pelt from the Legendary Onyx Wolf"* →
**`אחד עור מ ה מפורסם אוניקס זאב`**, *"Get a free Thank You Emote"* →
`קבל אחד חינם תודה לך אימוט`. **It passed every structural guard** — tokens intact, Hebrew
present, no niqqud, not a copy of the English — because those guards test SHAPE, not language.
Removed from the model list; `llama-3.3-70b-versatile` and `gpt-oss-120b` both render the same
lines correctly and stay.
**`work/../fleet/purge_wordbyword.py` turns the defect into a detector:** a single Hebrew
PREFIX letter (`מ ה ל ו ב ש כ`) standing as its OWN word before a Hebrew word — impossible in
real Hebrew, which always glues them. It found **100 damaged lines spread across ALL SEVEN
machines** (so the problem predated the model split), and they were deleted from the merged
bank AND from each worker's own `out_*.json` — **removing from only one of the two lets the
merge put them straight back**. It is now step 2a of `finalize.sh`, where a purged line falls
back to ENGLISH: readable English beats unreadable Hebrew.
⚠️ Tune the regex against the LEGITIMATE forms first — `ב~COLOR_MP_OBJECTIVE~`, `ל-RDO$`,
`ה-XP` are correct and a naive "standalone prefix" pattern flags 797 of them (8× the real
defect count).

### 🔴🔴 NEVER EMIT A CODEPOINT THE FONT WAS NOT GIVEN — sweep the whole corpus, not the sample

The font work injected **27 Hebrew LETTERS**. It did not inject Hebrew **punctuation**. A
character-coverage sweep of all 231k values found what would have been tofu boxes mid-word:
**geresh `׳` ×225** (`ג׳קסון` — the most common transliteration mark there is), gershayim ×30,
maqaf ×35, invisible bidi controls ×112, `U+FFFD` mojibake ×51, non-breaking hyphen ×19, and
one stray Devanagari letter. None of it is visible to a structural QA.
`build_full.font_safe()` maps each to its ASCII twin (`׳→'  ״→"  ־→-  ‑→-  „→"  ℅→c/o`), drops
the invisible controls and the mojibake, and drops any letter from a script the face never had.
After it, the BUILT artifact has **5** uncovered characters left (`†`×4, `™`×1 — both from the
game's own English, so the face has them). **Verify by re-scanning the built file, not the
source.** ⚠️ This is the one place the IRON RULE's maqaf exemption resolves the other way — the
exemption exists precisely so the FONT decides per game, and this font has no maqaf.
[[audit-corpus-against-font-coverage]]

### 🔴🔴 THE TAIL WAS A PROMPT PROBLEM, NOT A THROUGHPUT PROBLEM — mask the engine tokens (2026-08-07)

At 97.6 % the 21-stream fleet fell to **2 lines/min** and its logs read `+0/13` batch after batch.
That looks like provider throttling and is not: **428 of the 682 remaining lines carry 3+ engine
tokens** (`Take the ~COLOR_MP_OBJECTIVE_FRIENDLY~Saboteur~s~ ~1~` is five words and three tokens).
The worker sends the raw English, so the model must reproduce `~s~` byte-for-byte inside Hebrew —
and it keeps eating the `s`. The guard correctly rejects, the line is re-served, forever.

**THE FIX IS TO STOP SHOWING THE MODEL SOMETHING IT CAN BREAK.** `fleet/drain_tokenheavy.py`
replaces every token with an opaque `⟦0⟧ ⟦1⟧ …` before the call and restores it after — the same
atomic-placeholder trick `rdr2_rtl` uses against the bidi algorithm, applied one layer earlier.
Measured on the identical lines: **fleet `+0/13` → masked `40/40 accepted, 0 rejected`**, and
21 lines/min against the fleet's 2. **UNIVERSAL: when a fleet stalls on a subset, classify that
subset before touching providers, keys or stream counts — a structural property of the TEXT
(token density, length, markup) is a prompt fix, and no amount of parallelism repairs it.**

**🔴 THE REFERENCE PANEL MUST BE MASKED WITH THE SAME NUMBERING.** A sibling language carries the
same engine tokens, so showing the model a raw `~s~` in Polish teaches it the very spelling you
are hiding. `mask_with(txt, toks)` renumbers a ref against the ENGLISH token list; a token the
English does not have becomes `⟦?⟧`, which matches no engine token and is therefore **rejected by
the guard — fail-closed, never a silently mangled token.**

**🔴🔴 THREE CHAINED BUGS, EACH INDISTINGUISHABLE FROM "the model dropped every key":**
| symptom | real cause |
|---|---|
| `+0/8 ok=0 fail=0` | `max_tokens=325` — a REASONING model spends its thinking against the budget and returns an EMPTY `content` |
| `raw 321ch parsed 8` yet still `ok=0` | **the model MIRRORS THE INPUT SHAPE** — the payload became nested `{key:{en,pl,de}}` for the panel, so the replies came back nested too |
| a batch simply skipped | one pass never converges; only re-running (which recomputes `todo` from the bank) does |
The middle one is the sharpest: nothing errors, 8 keys parse, and every counter reads zero.
**Print the RAW length beside the PARSED count on any empty batch** (`[raw 321ch parsed 8]`) —
that one line separates "no reply", "unparseable reply" and "right shape, wrong nesting", which
`+0/8` alone cannot. And `--slice i/n` + `drain_loop.sh` (re-run until the remainder stops
shrinking twice) is what actually reaches 100 %.

### 🔴🔴 AND THE FINAL CEILING: 21 STREAMS ON ONE KEY POOL IS SLOWER THAN 9

After every fix above the fleet still hovered at ~24 lines/min, and a per-stream measurement
showed the desktop banking **1 line per minute** while its provider answered a direct probe in
1 s. The time was not spent working — it was spent **sleeping in cooldown**. Removing machines
proved the shape (same machine, same code, only the number of OTHER streams changed):
| fleet streams | that machine's rate |
|---|---|
| 6 | 18.0 /min |
| **9** | **24.0 /min** ← optimum |
| 15 | **0.0 /min** — every batch returned `step1 empty` |
| 21 | 3.4 /min |
⇒ **21 streams is not 21× the quota; it is 21 clients fighting over one pool, and the loser of
every race pays a full cooldown.** Settled at **9 streams (desktop + laptop + vm)** with the
remainder resliced onto exactly those, so no shard is stranded on a stopped machine.
⚠️ **A SHORTER cooldown is not a speed-up when the pool is the constraint** — 60 s → 20 s
quadrupled the request rate into a saturated pool and made it worse. The cooldown is what
PROTECTS the pool; cap the individual SLEEP (so a stream never freezes for minutes) but keep
the cooldown long. Final: `_COOLDOWN_S = 60`, `_MAX_WAIT_S = 10`.
⚠️ **Testing at 15 streams burned enough quota that the 9-stream config then measured 0 for a
while** — change one thing, wait, measure; do not blast a shared free tier while tuning.
[[fleet-size-is-capped-by-the-key-pool]]

### 🔴🔴 THE NAME-CANON AT MERGE WAS A SILENT NO-OP FOR THE WHOLE RUN (2026-08-07)

`pull_missing.sh` applied `name_fixes.json` as a flat `{wrong: right}` dict
(`for bad, good in fixes.items()`), but the file is `{"_doc": [...], "pairs": [[w, r], ...]}` —
so the only two "pairs" it ever tried were the literal strings `"_doc"` and `"pairs"`, and
**not one of the 49 corrections had ever been applied**, while this file documented
"name-canon at MERGE" as a working mechanism. Nothing errors when a dict simply has different
keys than you expect. It surfaced only because a spelling audit was re-run AFTER a merge and
every wrong form was still there. The reader now accepts BOTH shapes, sorts longest-first, and
**reports its own effect**: `name-canon applied to 305 lines (49 pairs)`.
**UNIVERSAL: make every corpus-wide transform print how many rows it changed, and check that
number — a reader that disagrees with its data file's SHAPE fails OPEN, and a silent transform
is indistinguishable from a broken one. Verify by COUNTING the effect on the data, never by
reading the code.** [[verify-a-transform-by-counting-its-effect]]

⚠️ Same family, hit twice more in one session: **a fix written straight into `hebrew_missing.
json` is reverted by the next merge** (the merge rebuilds it from `banks_missing/`), so an
english-guarded fixer has to be wired INTO `pull_missing.sh` rather than run by hand; and
**purging a key from the bank but not from the worker's own `out_*.json`** lets the merge put
it straight back (the 100 word-by-word lines reappeared exactly this way).

### 🔬 A 6-lens adversarial LQA over a 300-line stratified sample — 105 claims, 3 real

Ran review×6 lenses (gender vs the ar/ru/pl oracle · word-by-word · engine tokens · names ·
register · meaning) → an independent refute-by-default verifier per finding. **105 claims
raised, 3 survived** (the run hit the session limit before most verifiers finished, so the
3/21 ratio is the measured one). The verified class was **English idiom calqued literally**:
`I'll raise hell on you` → `אני אעלה את הגיהנום עליך` (not a Hebrew collocation),
`Aww, hell` → `אוי, גיהינום` (a place-noun used as an oath), `Holster weapons` → `לנדן`
(a *blade's* scabbard).
**The corpus itself settled the fix, not taste:** it already renders `hell` → `לעזאזל` in
**3,826 lines** against **10** with `גיהינום`, and uses `נרתיק` 106 times against 65 `נדן`
(some of which are genuine knife sheaths). So `Holster → נרתיק` became an ENGLISH-GUARDED
deterministic swap (11 lines) and the 5 calqued `hell` lines were re-queued for
re-translation — a word swap cannot fix a clause that is wrong end to end.
🔴 **And one proposed glossary rule was KILLED by reading its matches**: `Tonic → שיער:שיקוי`
looked like a divergent spelling, but `J. J. McCLURE FORTIFYING HAIR TONIC` → `טוניק לשיער` is
CORRECT — the game sells a health tonic AND a hair tonic. **A "divergence" between two senses
of one English word is not a defect; always read the matching lines before adding a pair**
([[glossary-measure-then-correct]]).
⚠️ The audit's divergence report is mostly NOISE by construction: Hebrew inflects, so
`חולצה`/`חולצת`, `מגפיים`/`מגפי`, `מסכה`/`מסכת` are the construct state and must never be
"fixed" — only proper names and outright wrong words are real.

### 🔴 Four in-game defects, all root-caused from the game's own data (2026-08-07)

- **The death-screen `מת` was clipped AND the pause menu drew giant overlapping letters — ONE
  cause: a bounding box computed over the "solid" contours only.** `rdr2_stencil_font.
  build_letter` took its bbox from `solids_d`, so any letter whose outer ring one role call put
  in the hole set got a box a QUARTER of its real size — measured **ב / נ / צ at h≈52 against a
  real ≈202**. Scaleform rasterizes a glyph into its cache using those bounds, so an undersized
  box both clips the glyph and makes it spill out at the wrong scale — exactly the two symptoms.
  Fixed by taking the union over **all** contours plus a 2 % pad; verified every one of the 27
  letters now covers its own ink. **UNIVERSAL: font metrics must never depend on a
  classification step — derive them from the geometry you are actually going to draw.**
- **🔴🔴 …AND THE DEATH SCREEN WAS STILL WRONG AFTERWARDS, FOR A SECOND, INDEPENDENT REASON:
  17 of the 18 faces carried Hebrew at a FLAT 134 units while their own Latin caps run
  179-274** (`work/scan_faces.py` measures every face: `M` cap · A-Z median · Hebrew median ·
  ratio). The original "+27 Hebrew into every face" pass injected the donor at ONE size for all
  of them, so **every Hebrew string on those surfaces renders at 55-75 % of the size the same
  string has in English** — which turns a huge `DEAD` headline into something the size of a
  menu row (the player's exact words: *"זה אותו גודל של התפריט"*). Only `RDR Lino` was right
  (214 vs 202 = **1.06**) because the stencil rebuild sized it from that face's own `M`.
  **FIX — `work/rescale_hebrew_faces.py`: scale each face's Hebrew to THAT FACE'S own cap**
  (459 glyphs, ×1.42-1.84), leaving RDR Lino untouched so the already-approved menu cannot
  regress. Verified by re-decompiling the file **out of the game folder**: 18/18 faces now at
  ratio 1.06-1.09.
  - **Scale the SHIPPED contours, don't re-inject a donor.** The letterFORMS were never the
    complaint — only the size. Scaling keeps the approved shapes byte-for-byte, so a
    regression can only ever be a size regression.
  - **🔑 The anchor is a FLAT-TOPPED Latin cap (E F H I L T), not `M` and not the A-Z median** —
    on a display/script face (`1871 Dreamer Script`) a swash or a round overshoot inflates
    those by 20 %+, and Hebrew has no ascender/descender to absorb it. **And on a NUMBERS-only
    face the letters are placeholders** (`RDR Catalogue Numbers`: flat-cap 61, digits 181) — a
    "flat cap unless tiny" rule silently HALVED that face. Digits and caps are the same height
    in any lining-figure font, so take **`max(flat-cap median, digit median)`**: the degenerate
    set is always the smaller one. A `k < 0.95 ⇒ refuse` guard catches the rest.
  - **Re-delta from ROUNDED ABSOLUTES.** Contours are delta-encoded and edge kind 3 is a quad
    curve carrying control+anchor deltas; rounding each *delta* independently accumulates error
    along the contour and visibly warps the letter. Reconstruct the absolute path, scale, round
    each absolute point, emit the delta between the ROUNDED absolutes.
  - **⚠️ Splice a multi-hundred-MB dump with ONE join.** `buf = buf[:s] + rep + buf[e:]` in a
    loop copies the whole 345 M-char document per edit (~460 edits ≈ 160 GB of copying).
  - **⚠️ A swf2xml dump holds TWO SHAPES AT ONCE** — the shipped faces are pretty-printed (a
    `<boundingBox>` spans five lines) while a face WE injected via `ET.tostring` is a single
    ~40 MB line. A line-oriented scanner silently reports **0** for one of the two and reads as
    "this face has no glyphs". Slurp the file and drive everything off offsets.
  - **⚠️ A text `--deploy` copies the whole template tree, which contains the font** — sync
    `work/legal/` **and** `work/full/`'s copy on every font change or the next text deploy
    silently reverts it.
  **UNIVERSAL: "the font has Hebrew" is not "the font has Hebrew at the RIGHT SIZE". Measure
  every face's Hebrew against ITS OWN Latin cap — a flat one-size injection is invisible on a
  body-text surface and screams on a headline surface, and it looks exactly like a bidi or a
  point-size bug.**

### 🔴 A FLEET'S THROUGHPUT CANNOT BE MEASURED FROM THE MERGED BANK (2026-08-07)

The merged bank is written by the **pull, every 5 minutes** — it is a periodic SAMPLE of the
workers' output, not the output itself. So any rate computed from it over a window shorter than
the merge cadence alternates between the true rate and **0**, and a single 3-minute sample
reading `0 lines/min` looks exactly like a dead fleet. It cost a wrong call here: the
21-stream config measured "0/min" and was about to be rolled back when the workers were in fact
producing normally.

**Measure at the WORKER**: each `w_<provider>.log` carries its own running `total N/M`, so two
samples of that counter are unconfounded. Desktop: 16 lines in 150 s = 6.4/min from 3 streams →
~45/min for 7 machines — and the bank-based monitor, once its window was widened past the merge
cadence, independently reported **44/min**. Two instruments converging is the proof; one
instrument sampled too fast is noise.

**UNIVERSAL: before believing a throughput number, ask what WRITES the thing you measured and
how often. Sample slower than the writer, or measure the writer.** Same family as
[[verify-a-transform-by-counting-its-effect]] — and the same reason a per-stream `ALL DONE`
must be read from the log rather than inferred from a flat counter.

⚠️ Corollary seen in the same hour: the documented **"21 streams is slower than 9"** did NOT
reproduce when the remainder was ~1,000 lines (≈45 per stream). That measurement was taken on a
long marathon where every stream hammered the pool continuously; a short burst is a different
regime. **A fleet-size rule is a curve, not a constant — re-measure it for the workload you
actually have.**

### 🔬 Turning the 15 LQA findings into fixes — 2 systematic passes, 1 targeted (2026-08-07)

The 6-lens adversarial LQA confirmed 15 defects. The right response was NOT 15 hand edits: the
first question is always **"is this a CLASS?"**, and the corpus itself answers it.

- **✅ `fleet/fix_imperative_number.py` — 414 lines.** The already-shipping 217k bank uses the
  masculine SINGULAR imperative **3,088 : 693 (82 %)**, so the fleet's 335 plural lines are the
  odd ones out and the LQA's "four imperatives flip number inside one tutorial paragraph" is
  the same defect seen from the other side. **🔴 A blind plural→singular swap corrupts correct
  Hebrew**: the 2nd-person plural imperative is spelled identically to the 3rd-person plural
  PAST (`הם פתחו את הכלוב` = "they opened the cage"), and a line whose English really addresses
  a group is correctly plural. Two English guards make it safe — the verb must appear in
  **imperative position** (first word of a clause once tokens and a leading `~z~` are stripped,
  which alone kills the past-tense trap because *"they opened up the cage"* does not start with
  "Open"), and the line must carry no plural-addressee cue (`you all`, `boys`, `everyone`).
  Result: 414 fixed, **271 correctly left alone**, re-run is a clean no-op.
- **✅ `fleet/fix_moonshine_term.py` — 151 lines.** RDR Online's Moonshiner role shipped in FIVE
  spellings (`מונשיין` 62 · `מון-שיין` 61 · a literal `ירח` calque 53 · `מון שיין` ·
  `משקה הירח`). The calque is the real defect and it is unambiguous: `מבשלי הירח` ("moon
  brewers"), `בקבוק הירח`, and the giveaway **`ייצור הירחון` = "MAGAZINE production"** for
  *"Moonshine production is complete."* Every `ירח` on a moonshine line was inspected — all 53
  are the calque, none mean the moon. English-guarded on `/moonshin/i`, longest phrase first so
  `הירחון` is never mangled by the bare `ירח` rule. **⚠️ The prefix group belongs on the PHRASE
  rules too** — `במשקה הירח` starts with an attached `ב`, so a lookbehind forbidding any Hebrew
  letter never fires and the bare rule produces a redundant `במשקה המונשיין`.
- **✅ `fleet/retranslate_lqa.py` — 11 lines back to the FLEET, not to Claude.** What is left
  after the two classes is not mechanical (a calqued idiom, an adjective disagreeing with its
  own noun), so it goes to the same providers **with the verified critique in the prompt** —
  that critique is information the first pass never had, and a plain re-ask would reproduce the
  calque. 10/11 came back correct and passed the structural guard (`דבר עלוב`→`מסכן`,
  `כדי לאפליקציה`→`כדי להחיל`, `בחוות ובחוות`→`בחוות בקר ובאחוזות חקלאיות`, `המבריקים`→
  `המייצרים מונשיין`). **The 11th failed the guard three times in the identical way** (the model
  ate the `s` out of `~s~`) — the documented "a re-queue does not converge" case — and its
  verified change was a ONE-WORD noun swap the sibling key already ships (`המטרות`→`היעד`), so
  it was done deterministically. **A guard rejection is the guard working; three identical
  rejections mean stop re-asking.**
- **🔴 THE WRITE RACE THAT THREW AWAY THE FIRST 11 GOOD TRANSLATIONS.** `os.replace` onto the
  bank lost to the 5-minute merge → `PermissionError WinError 5` **after** the provider calls
  had already succeeded, and the whole run was lost. Fixes: a **PID-unique** temp name (two
  writers must never share one), a backoff retry, a `--force`-less **skip-what-already-passed**
  so a re-run retries only the failures, and — the real one — **write the durable artifact
  FIRST**. `lqa_overrides.json` + `fleet/apply_lqa_overrides.py` now re-apply the verified lines
  after every merge, exactly like the other guarded fixers, because **`pull_missing.sh` rebuilds
  the bank from the per-worker banks and silently reverts anything written straight into it**
  ([[verify-a-transform-by-counting-its-effect]]). The merge tail now runs FOUR fixers in order:
  names → imperatives → moonshine → LQA overrides, each printing its own effect.
- **`אחה"צ` glued to the clock was in the TEMPLATE, not the label.** `TIME_AND_TEMP_C` ships as
  `~1~:~2~~3~ | ~4~°C` — time and AM/PM adjacent with no separator. "12:56PM" reads fine in
  English; a 5-character Hebrew label does not. Fixed in `fleet/ui_fixes.py` (`~1~:~2~ ~3~ |
  ~4~°C`). Same pass caught **`AM` still Latin while `PM` was translated** — a 2-letter token
  reads as a code, so the clock switched language at noon.
- **✅ BOTH BOOT SPLASHES STORE VISUAL — one answer for the whole game (CORRECTED 2026-08-09;
  the earlier claim here that the splash "RUNS BIDI" was WRONG).** All four `LEGAL_SPLASH_*`
  are VISUAL and never justified (justification pads a string the engine then draws in storage
  order). **🔴🔴 It went wrong THREE times because I judged the direction by READING the Hebrew
  in a screenshot** — the one instrument [[hebrew-screenshot-transcription-trap]] forbids, and
  **it fails in BOTH directions**: twice I read "correct" on a mirrored screen and shipped
  LOGICAL (the user answered "עברית ראי" both times), and once I read "mirrored" on a screen the
  user then confirmed was fine — flipping it would have BROKEN a working panel. **When the user
  has looked at the pixels, that IS the measurement; my transcription is not evidence at all.**
  What does read an image: punctuation attachment (`,גוריד` broken vs `אנשים, מקומות,` correct),
  digits/Latin islands, or glyph correlation against the atlas. ⚠️ A digit marker only helps if
  the user replies IN WORDS — a returned screenshot is just another image to misread.
- **⚠️ A text `--deploy` silently REVERTS the font.** `build_full.py` copies the whole `legal/`
  template, which contains `lml/KGF/asset_replace/font_lib_efigs.gfx` — so deploying text after
  a font build overwrote the new .gfx with the old one (caught by comparing sizes: 3,341,174 →
  3,316,495). The new font is now stored IN the template. **UNIVERSAL: when one build step
  copies a whole tree, every artifact produced by a DIFFERENT step must live in that tree, or
  the two will keep undoing each other.**

### 🔴🔴 RDR2 round 3 — the font fix never reached the menu, and the English source was broken (2026-08-09)

- **🔴 AN EXCLUSION THAT SPARES AN "ALREADY-APPROVED" SURFACE IS INVISIBLE WHEN IT IS WRONG.**
  `rescale_hebrew_faces.SKIP_FACES = {"RDR Lino"}` was justified as "the menu the user already
  approved must not regress" — but the user's FIRST report said that menu "renders huge
  letters". Lino therefore sat at 1.06 of its own cap through all three rescale builds while
  the other 17 moved to 0.85, and four rounds came back "still too big". **The failure mode is
  the trap: an excluded surface reports the identical defect after every build, which reads as
  "the fix doesn't work" rather than "the fix never got there".**
  [[recheck-exclusions-against-what-was-approved]] Also: the `k < 0.95 ⇒ refuse` shrink guard
  needed a corroboration escape — a shrink IS right when the flat-cap and digit medians agree,
  since two agreeing measurements cannot both be degenerate.
- **🔴 THE FONT SHIPPED TWO DIFFERENT HEBREW LETTERFORM SETS.** `RDR Lino` was rebuilt by
  `rdr2_stencil_font.build_letter` (western, condensed, lightly distressed, matching that
  face's own Latin); the other 17 carried the plain modern-sans donor. The prompt bar drew
  `צא מהמשחק` in the game's style and the pause menu drew the same words in a generic sans.
  Fix = **`work/transplant_lino_glyphs.py`**: copy Lino's 27 glyph bodies + advances into every
  other face, scaled by that face's OWN current Hebrew height — letterform changes, size does
  not. 🔑 It also sidesteps identification: all 18 faces draw the same outlines, so a screenshot
  cannot say which face a surface uses, and transplanting to ALL of them is true either way.

**🔴🔴 `.yldb` English is ~27 % MIS-PAIRED, and it shipped.** A label read `פקיד התחנה` where
SETTINGS belongs; `0xFBA3FBFE` — my extraction said *Station Clerk*, the game's own
fr/de/it/es/pl all say **Settings**. Every internal check passed: self-consistency is not
correctness. The measurement, the four disproved theories, and the scoping move that bounded
the damage to **2,363 renderable keys** (of 28,093): [[extraction-needs-an-external-oracle]].
The 217,491-line main corpus came from the public dump and is unaffected.

**✅ THE SAFE REPAIR SHAPE — review → adversarially verify → filter by CLASS.** 6,287 UI labels
reviewed (743 proposals, 13 %) → an independent judge shown only OLD vs NEW with OLD as the
default (394 confirmed) → **a deterministic filter for the bad class the judge kept passing: a
change that ADDS a Latin word or REMOVES a Hebrew word is a de-Hebraisation, never a fix**
(`מגפי הארדי` → `מגפי Hardie`), dropping 49. **345 applied.** Recovered: `Sip` was `שב`
(*sit*), `Corsets` `חצאיות`, `Florist` `פרחח`, `Mr. Gillis` `קום`, `Cracked` `מרוחק`.
⚠️ ARBITRATE ("follow the panel majority") was tried first and made things WORSE — on a
mis-paired key the panel is mis-paired too. [[review-then-adversarially-verify]]

**⚠️ Two environment traps, each costing a run:** putting `universal/` on `sys.path` ahead of
the fleet dir shadowed `fleet_providers` with a copy reading a different key file → **401 on
every call**, indistinguishable from a dead key pool; and a retired game's workers were still
live on this desktop (`SkyrimMP`/`SkyrimWatchdog` read **Ready**, not Disabled), burning the
same key pool — [[a-janitor-may-only-kill-its-own-workers]], [[verify-a-kill-by-recounting]].

### ✅✅ PUBLISHED — `1.0.0-beta.1`, all 4 surfaces verified through the CONSUMER (2026-08-09)

The user said **פרסם**. Live: GitHub `hebrew-translation-hub/rdr2-hebrew-mods` (repo created
this session, PUBLIC so the website can link the asset directly) tag **`v1.0.0-beta.1`**, a FULL
release so `releases/latest` resolves it — `rdr2_hebrew.zip` **9,043,492 B**, sha
`45af2e6b95defbe4f49ad637a18d412c78d1e28656807274671fa715a5705da4` (re-hashed from the
DOWNLOADED asset, not the build log) + `manifest.json`. Supabase `games` id=`rdr2` →
available/beta/`1.0.0-beta.1`/**₪53**/download_url + `mod_version_history` id=25 is_current.
Health check: `/api/games` (cache-busted MISS) returns the row, the linked download answers
**206** `bytes 0-0/9043492`, the public history returns 1 entry, `releases/latest` = the tag.
4 Hebrew `news_drafts` pushed for admin approval.
- **`show_on_launcher` = FALSE on purpose** — there is no RDR2 applier in the launcher yet, so a
  card with an install button would fail. Website download is the beta.1 channel. The Worker slug
  `rdr2-hebrew` is likewise NOT added (it only serves the launcher) — add both together when the
  applier exists.
- **`games/rdr2/pack_and_release.py` (NEW)** reads the bytes **out of the LIVE game folder**, not
  the build's staging dir, so the shipped package is byte-identical to what was play-tested
  (round-trip verified: 13/13 files identical, the zipped gxt2 re-parses to 245,437 entries, and
  the 6.6 MB of `*.prescale_backup`/`*.stencil_backup` in `asset_replace/` did NOT leak in — never
  glob that directory). It runs the QA gate first and REFUSES to pack on any failure.
- ⚠️ **`gh` cannot reach api.github.com from this environment** ("error connecting"), while plain
  `curl`/`urllib` can — do the whole release over the REST API. And the credential helper needs
  the **username**: `printf 'protocol=https\nhost=github.com\nusername=nehorayc04\n\n' | git
  credential fill` returns a `gho_` token with `repo` scope; the bare host-only form returns an
  EMPTY password and every call then 401s "Bad credentials".

**STATE:** deployed + PUBLISHED `18,531,270 B / 245,437 keys / 99.9 % Hebrew`, font `3,760,442 B`
(Lino letterforms in all 18 faces at 0.85 of each face's own cap), 0 niqqud · 0 markers · 0 `=` in
a value · 0 codepoints outside the font's own table · 0 duplicate keys · 0 empty values.

### 🔴🔴 A string the engine PARSES into buttons must ship ENGLISH — and it is a CLASS (2026-08-09)

With the mod on, **every** warning dialog lost its `Yes ⏎ No ⟵` row (quit included). Nothing
errored; the buttons were simply absent. The cause is not a bad translation — it is a category:
`~INPUT_FRONTEND_ACCEPT~ Yes ~INPUT_FRONTEND_CANCEL~ No` is a **widget the engine parses**
("glyph, label, glyph, label"), not prose it draws. Translate it and the parse fails → the whole
row vanishes. Store-VISUAL makes it certain: the transform moves the leading glyph to the visual
end. Fix = `build_full.OMIT_KEYS` (**7 of 245,431** — the row shipped English and returned).

**🔑 DETECT THE CLASS, NEVER THE INSTANCE.** After the user's screen was fixed, one corpus-wide
scan for the SHAPE (starts with a glyph token, then `[glyph] <short label>` pairs, no sentence
punctuation — a hint like *"Press ~X~ to open the menu."* is a SENTENCE and must not be flagged)
found **3 more already-broken rows on screens nobody had opened**, incl. the shop's Purchase row.
`work/parsed_rows.json`. Two of the three carried a **different glyph than the game's own
string** = `.yldb` mis-pairing surfacing as a functional break, not merely wrong words.

**Isolate by BISECTION, not inference.** I "knew" the key, fixed a real leading-token bug, shipped
— still gone; then a 36-marker ladder showed nothing. What actually worked: disable the mod (row
returns ⇒ it is us) → split by SOURCE (217k public dump vs 28k `.yldb`; row returns with the 28k
excluded) → omit the 4 prompt-shaped keys in that half. ⚠️ One ladder marker was itself
MALFORMED (tokens glued) — a broken probe reads exactly like a negative result and masked the
valid markers beside it. [[parsed-widget-strings-must-ship-english]]

### 🔴 The 4 boot splashes ship in VANILLA ENGLISH (user's call, deferred to the next version)

User, minutes before publishing: *"תשאיר את זה באנגלית כמו המקורי … ואז אחר כך נתקן את זה"*.
`build_full.SHIP_LEGAL_ENGLISH = True` **OMITS** the four `LEGAL_SPLASH_*` keys from the override.
🔑 **Omit the keys, do not write the English back in** — an LML override file only overrides the
keys it CONTAINS, so dropping them makes the game fall back to its own bytes exactly; writing the
English back would have shipped the public dump's mojibake'd copy (`?` where U+2211 belongs, a
stale `©2005-19`). The corrected Hebrew stays in the spine, so re-enabling starts from the better
text. Before the deferral these were fixed and are ready for the next version:
- **11 real Hebrew errors** (not layout): `להצעה`→`להינתן` (a noun where a verb belongs),
  `רישיונות משחק`→`נותני הרישיון` (*licensors* read as *licenses*), `ב http://`→`בכתובת http://`
  (a prefix floating detached before a Latin URL), `במסוימים מתכונות`→`בחלק מתכונות`,
  `הפשטת קוד`→`פירוק קוד`, `וזו מהווה`→`ואלה מהווים` (singular verb after a plural list),
  `תמיכת לקוחות וטכניים`→`לתמיכת לקוחות ולתמיכה טכנית`, `בכל הזמנים`→`בכל עת`.
- **U+2211 removed** — the splash face draws it as an EMPTY gap (the blank the user saw between
  two commas). It is a decorative logo mark; a font-coverage table that is a UNION across faces
  will happily say it is covered.
- **`Dead Eye` put back to Latin** inside the trademark list: a single Hebrew island in the middle
  of a Latin run is what makes such a line read as scrambled.

### ✅✅ RPF8 CRACKED — `games/rdr2/tools/rpf8/` extracts every RDR2 archive, no OpenIV (2026-08-06)

The long-standing "RPF8's TOC is TFIT-encrypted, keys not held, OpenIV/CodeX-gated" note is
**SUPERSEDED**. A standalone CLI now decrypts and unpacks all of it — **89/89 archives in the
game folder parse with a perfectly contiguous entry chain, 0 failures**, and a recursive run on
`levels_0.rpf` produced **20,143 files / 1.6 GB / 0 errors in 42 s** across 11 nested archives
with 11 different key tags. Docs: `games/rdr2/tools/rpf8/README.md`.

- **Format** (verified against all 24 shipping archives): `u32 'RPF8' · i32 entryCount · i32
  namesLength · u16 decryptionTag · u16 platformId('y'=PC)`, then a **256-byte RSA signature**,
  then `entryCount × 24-byte` entries at **0x110**, then file bodies laid out contiguously, and
  the NUL-separated **name table at the END of the file** (`EOF − namesLength`).
  **`decryptionTag == 0xFF` means the TOC is NOT encrypted** — `shaders_x64.rpf` is exactly that,
  which is the free plaintext control every step was validated against.
- **The cipher is TFIT, a white-box block cipher in CBC — NOT plain AES with an extractable key.**
  That is why a brute-force scan for a 32-byte AES key found nothing in RDR2.exe (89 MB, every byte
  offset) or OpenIV.exe: in a white-box the key exists only baked into per-round mask/lookup tables.
  Ciphers + tables come from the open-source `lazenes/RPF8_TOOL`; the container reader, name
  resolution and CLI are ours.
- **🔴 A REAL BUG in the published ciphers, fixed here:** `TfitCbcCipher.Decode` and
  `Tfit2CbcCipher.Decode` write the CBC result to `input[j]` instead of `input[i + j]` — correct
  for the first block, silent corruption for every block after it. Fixing that is what makes a
  multi-block TOC decrypt at all.
- **Only whole 16-byte blocks are transformed** (`len & ~15`), remainder left in the clear — which
  is why `pack/row` / `ifest_tu.xml` are readable in the raw name table of an encrypted archive.
  File bodies are only PARTIALLY encrypted (`StridedCipher`: a head, strided blocks, a 1 KB tail,
  selected by the entry's `encryptionConfig`), so decryption cost is tiny even on multi-GB files.
- **Names:** entries carry only a JOAAT hash, and an encrypted archive's own name table is NOT
  recoverable with the TOC key (proven by brute-forcing every key tag against it) — the same reason
  OpenIV ships an external name DB. `rpf8 namedb` harvests real archive paths out of the game's own
  **RPFC / `pfm.dat`** mount cache inside `appdata0_update.rpf`; anything unresolved is written as
  `0x<HASH>.<ext>`, which does not affect extraction.
- **🔴🔴 DISK COST: MEASURE IT, NEVER EXTRAPOLATE FROM ONE ARCHIVE — `rpf8 du` (2026-08-07).** The
  earlier "~4.6× ⇒ ~360 GB" figure was extrapolated from `levels_0` alone and was **~60 % too high**.
  Measured ratios span **×1.00 → ×5.44**: audio (`.awc`) and video are already compressed and do not
  grow at all, `textures_*` explode. **And a FIRST-LEVEL sum is worse than useless — it reports
  ×1.01**, because the big archives hold nested archives stored **uncompressed**, so every bit of the
  growth is one level down; a one-level measurement would have said "this is free". Only a recursive
  walk is honest. `du` reads TOCs only and writes nothing — validated by reproducing `levels_0`'s real
  extraction **to the byte and to the file (20,143)** in 2 s instead of 42 s. Full game:
  **119.14 GB (89 top-level / 4,960 incl. nested) → 225.73 GB / 488,721 files = ×1.89, net +106.6 GB
  with `--inplace`.** `unpack` now derives each archive's cost from its OWN TOC (a round extracts ONE
  level, so the cost *is* the sum of that archive's entry sizes) instead of a guessed ratio, and skips
  rather than fill the volume. ⚠️ `du` materialises nested archives in memory — it grew the Windows
  **pagefile to 75 GB** on this machine, which reads as "34 GB vanished"; that is the pagefile, not the
  unpack (verify with the folder's own size before blaming the tool).
- **🔴🔴 AN `--inplace` TOOL MUST NOT DELETE THE SOURCE ON A *PARTIAL* SUCCESS (real incident,
  2026-08-07).** `unpack` caught per-entry failures, counted them, and then deleted the archive
  anyway — so one `Oodle decompress failed` on a single `.ydr` **destroyed the only copy of that
  file** while the run reported `ok`. Three rules now, and they generalise to every destructive
  converter: **(a) delete the source only when EVERY item succeeded** (otherwise mark it `PARTIAL`,
  keep it, and list it at the end); **(b) SALVAGE what the codec refused** — the failed entry is
  written as `<name>.rpf8raw`, the decrypted-but-undecodable bytes, so no byte is lost even when the
  decode is; **(c) a kept source must be EXCLUDED from later rounds**, or a round-based loop that
  re-scans for work spins forever on it. Recovery here was free only because the pristine Steam
  install still existed — **check that a pristine source exists before running anything `--inplace`.**
- **🔴🔴 OODLE `fuzzSafe=NO` KILLS THE PROCESS, AND `try/catch` CANNOT SAVE YOU.** A malformed
  entry made the native `OodleLZ_Decompress` read past its buffer → `AccessViolationException` →
  the whole unpack died at archive 2,014 of 3,930 (exit 139). An AV is a **corrupted-state
  exception**: .NET will not deliver it to a `catch`, so no amount of wrapping the extractor
  helps. The only fix is to stop the native call running off the buffer — **`fuzzSafe=YES` + 64
  bytes of output slack**, verified byte-identical on a known-good archive (45 files /
  64,225,212 bytes), i.e. free. **UNIVERSAL: any P/Invoke'd codec with a "trust the caller's
  size" mode must be called in its SAFE mode inside a batch job — a single bad item otherwise
  takes down hours of work, and the exception type means you cannot defend against it in C#.**
- **🔴 THE 256-BYTE "SIGNATURE" IS NOT ALWAYS A LEADING HEADER.** All 461 entries of
  `data_0/data/ui/screens.rpf` set `IsSignatureProtected`; skipping 256 bytes at the FRONT makes
  **all 461 fail**, and not skipping decodes them **461/461 with 0 errors**. The reference
  implementation has the same bug. `GetFile` now tries the documented layout and RETRIES without
  the leading skip — **a fallback, never a replacement**, so nothing that already decoded can
  regress (re-verified: the known-good archive is byte-identical). **UNIVERSAL: when a flag's
  documented meaning makes an entire archive fail while ignoring it makes it pass 100 %, add the
  alternative as a fallback rather than switching interpretation — you rarely have the evidence
  to know which reading is right for the OTHER 490,000 entries.**
- **⚠️ 1 of ~490,000 entries is genuinely undecodable, and `probe` proves WHICH claims are false.**
  `levels_1 → 0x2A9BF706.rpf → 0xAEB90D10.ydr`: decryption is correct (undecrypted input fails at
  every size), **1,310,720 of 1,400,912 bytes decode = exactly 5 × 256 KB Oodle blocks**, the input
  is NOT truncated (those 5 blocks consume 479,856 of 524,752 bytes, leaving 44,896 for the last),
  the declared size is NOT wrong (a 16-aligned sweep of every possible final-block size decodes at
  none), and the tail is NOT still encrypted (decrypting it *breaks* the 5 blocks that work). The
  reference implementation fails identically. **UNIVERSAL: when one item in a huge batch fails,
  spend the probe on ELIMINATING hypotheses with the real bytes — "is the input truncated / is the
  size wrong / is the decrypt short" are each one measurement — instead of iterating fixes blind.**
  ⚠️ Probe with Oodle's **`fuzzSafe=YES`**: with `fuzzSafe=NO` a wrong size makes it **HANG** (seen),
  which is useless for asking "what size is this really?".
- **🔑 THE METHOD LESSON (cost most of the session):** three failed brute-force key scans all shared
  one root cause — **the oracle window was aimed at bytes that were not what I assumed** (the RSA
  signature at 0x10; the middle of file bodies; a "names table" I believed followed the entries but
  actually sits at EOF). **Before brute-forcing a key, prove the layout on an UNENCRYPTED sample of
  the same format** — `shaders_x64.rpf` would have shown all three mistakes in one minute. And
  checking whether the format is already solved in open source (`rpf-rs` named the cipher "TFIT";
  a GitHub search for `rpf8` found the full implementation) beats reverse-engineering a 32 MB
  Delphi binary. [[check-public-format-first]] [[engine-family-reuse-check-magic]]

**The proof workflow that worked (reusable):** one drop-in zip per question, each proof isolating a
single gate, with a **Latin marker** (`ZZ-RDR2-P7-ZZ`) so "the file didn't load" is distinguishable
from "the font has no glyphs", and A/B pairs on the two boot splash screens (they are FREE test
surfaces — visible every launch, no gameplay needed). Seven rounds closed: mount · font · bidi ·
punctuation · paragraph wrap · box width · justification.

- **✅ COMMUNITY `/translate` POOL LIVE — 217,491 rows in 6 Hebrew categories (2026-07-20).**
  `work/build_ct_strings.py` → `extract/ct_upload.json` → `universal/community_translate.py import
  rdr2`. `string_key` = the Ko Games LML key VERBATIM, so an approved line drops straight back into
  the override file at build time with no remapping. Ordered by VISIBILITY per
  [[community-pool-by-category]]: **ממשק ותפריטים 3,201 → פריטים וציוד 13,413 → כתוביות עלילה
  10,057 → מסמכים ותוכן נוסף 37,454 → דיבורי רקע 144,571 → תוכן מקוון (RDR Online) 8,795.**
  Only 267 dropped (no letters at all — pure numbers/symbols/token-only); a name/code passthrough
  is a TRANSLATOR decision, not the adapter's. Verified through the PUBLIC API (not the importer's
  success message): `/api/translate?action=games` → total 217,491 / open 217,491, all 6 categories
  render, and the `category` column is 0 `other` / 0 null (the trigger's Hebrew passthrough works).
- **🔑 GENDER SOURCE ATTACHED TO EVERY LINE — no gender debt** ([[gender-oracle-from-game-langs]]).
  English drops the gender Hebrew needs, so each row carries the game's OWN Arabic in `context`
  (**217,450 of 217,491**) as the source a translator reads, plus an auto-hint (`נמען=נקבה/רבים`)
  on the **1,031** lines where `gender_oracle.ar_addressee_strict` is unambiguous — a closed set of
  pronouns/suffixes only, because a WRONG hint creates exactly the debt it prevents
  ([[gender-hint-needs-closed-set]]).
  ⚠️ **The Arabic is stored VISUAL + presentation-form, so it must be NFKC-normalized AND reversed
  PER SEGMENT to be readable.** Stripping the `~sl:`/`~n~` tokens first and reversing the whole
  string concatenates the segments and **flips their order** — a two-part subtitle then shows its
  second half first (caught on `045_EXIT_DAY_1`). `to_logical_arabic()` splits on the separators,
  reverses each segment, and rejoins in order — the same rule as the build path, for the same reason.
- **⚠️ Supabase auth trap, the INVERSE of the Management-API one:** `SUPABASE_SERVICE_ROLE_KEY` is
  an `sb_secret_…` key, and **PostgREST 401s it when the request carries a browser User-Agent**
  ("Forbidden use of secret API key in browser") — while the Management API *requires* a browser UA
  to get past Cloudflare's 1010. So: **PostgREST → no browser UA; Management API → browser UA.**
- **Phase 2:** delegate the ~218k EN→Hebrew ([[delegate-all-translation]]; gender via the Arabic +
  a web-verified name registry [[name-registry-and-internet-check]]) → build through
  `rdr2_rtl.justify_visual_px` (VISUAL + pre-wrap + justify) → LML package → publish (GitHub
  `rdr2-hebrew-mods` + Supabase `games` id=`rdr2` + `mod_version_history`, price per
  [[mod-price-53-default]]). Same shape as SM2/GTA/Anno. **First Phase-2 step: run the ruler on the
  SUBTITLE box** — it is much narrower than the splash, and its budget decides how much of the
  158,720-line dialogue corpus needs pre-wrapping.

---


