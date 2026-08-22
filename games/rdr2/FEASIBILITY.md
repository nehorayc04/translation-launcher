# Red Dead Redemption 2 — Hebrew — Phase-1 groundwork, 🟢 GO (easy-tier deploy)

Install: `C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2` · engine =
**RAGE** (same family as GTA V) · archives = **RPF8** (encrypted, Oodle `oo2core_5_win64.dll`).
games.id (proposed) = **`rdr2`** · exes `RDR2.exe` / `PlayRDR2.exe`.

**Verdict: 🟢 GO. Deploy needs NO RPF8 crack** — the whole Hebrew chain rides Lenny's Mod
Loader (LML) loose files, exactly like the shipping **Ko Games RDR2 Arabic mod** (open source:
GitHub `Lore2x/RDR2-Arabic-Translation`, releases `lml`/`ready-mod`). We dissected that mod; it
proves every gate in-game. RDR2 is the GTA-V / AC2 / Anno class: no Arabic locale slot → hijack
via LML's runtime string-override, store Hebrew **VISUAL** (the RAGE frontend does no bidi).

## The pipeline (proven from the Ko Games Arabic mod)

| Gate | Finding | Status |
|---|---|---|
| **Container** | RPF8 (`8FPR`), encrypted + Oodle. Base text = `.yldb` in `update_3/x64/data/lang/`. | **Not needed for deploy** (LML overrides at runtime). Needed only to read the EN corpus. |
| **Text format** | LML `<DataFile>` = a **plain UTF-8 text** file (misnamed `*.gxt2`): `KEY = value` per line, `#` comments. KEY = **label** (`LEGAL_SPLASH_1`) OR **joaat hex id** (`0x2B39B2B7`). Tokens = RAGE tilde controls (`~z~ ~s~ ~o~ ~n~ ~sl:a:b~ ~1~ ~COLOR_*~ ~INPUT_*~`) — identical to GTA V. | ✅ codec `work/rdr2_text.py` (parse/serialise/build_hebrew, self-tested). |
| **Scope** | Ko Games file = **231,993 unique keys** (136,134 label + 95,834 hash), ~233k entries. Dominant token `~z~` (164k, dialogue). Mostly subtitles + UI. | ✅ `extract/key_universe.json`. |
| **bidi** | **VISUAL.** The Arabic mod stores 85:1 presentation-form vs standard-block chars and 17,854 lines start with the sentence-final `.` on the LEFT → the engine does NO bidi + NO shaping. Hebrew = store **pre-reversed** via `visual_line` (reuses GTA V's, token/tag-safe). Hebrew needs no shaping → simpler than Arabic. | ✅ **CONFIRMED IN-GAME 2026-07-19.** |
| **Font** | Scaleform **`font_lib_efigs.gfx`** (GFX v8, uncompressed, **18 DefineCompactedFont faces** — same family as GTA V's `font_lib_efigs_pc.gfx`). Vanilla has 0 Hebrew. Loaded loose via LML `asset_replace` → `update:/x64/patch/data/cdimages/scaleform_frontend/font_lib_efigs.gfx`. | ✅ **BUILT**: FFdec `swf2xml` → GTA V's Hebrew injection (`work/rdr2_font.py`, +27 glyphs U+05D0–05EA into all 18 faces from donor `gtav/.../gen_allheb.xml`) → FFdec `xml2swf` → valid `font_lib_efigs_HE.gfx` (3,316,495 B). |
| **Deploy** | **Lenny's Mod Loader** (`lml/mods.xml` + per-mod `install.xml` with `<DataFile>` for text + `<FileReplacement>` for the font). No RPF write, no repack, no admin. | ✅ menu-proof assembled (`RDR2_Hebrew_menu_proof_lml.zip`). |
| **DRM / anti-cheat** | Story mode = none. (RDR Online uses BattlEye — irrelevant to SP.) | ✅ safe. |
| **Activation** | Install LML + ASI Loader + ScriptHookRDR2, drop the `lml` mod. No in-game language switch needed (the override replaces the ACTIVE language's strings; keep the game in English). | Documented. |

## The English corpus — ✅ SOLVED (93.9%, fully automated, NO TFIT crack)
The Hebrew haul needs `{key → English}`. RPF8's TOC is encrypted with the **TFIT** cipher
(rpf-rs: "keys not held"; RDR2's new cipher, OpenIV/CodeX-gated) — a hard RE gate. **We do NOT
need it:** deploy is LML loose files, so TFIT only matters for WRITING inside RPF8, which we
never do. The English text is available as a **public complete dump**:
- **`github.com/cedricalpatch/Red-Dead-Redemption-2-Text-Files`** — 2,204 `.txt`, same
  `KEY = value` format, **hash-keyed** (`0x...`), 233,262 entries of the real English text.
- Our Ko Games keys are 136,134 **labels** + 95,834 **hashes**. Join: hash keys → direct;
  label keys → **`joaat(label)` → hash** (RAGE Jenkins-one-at-a-time, lowercased — reused from
  `gtav_gxt2.joaat`). Result: **217,758 / 231,968 keys (93.9%) have English** (labels 92.1%,
  hashes 96.3%) → `extract/en_corpus.json` (keyed by the Ko Games key → drops straight into the
  LML text file). The ~6% missing = mostly **RDR Online** (Moonshiner/Voucher/Coupon/Clothing) —
  story mode unaffected. 592 entries carry a `U+FFFD` mojibake artifact from the dump → a light
  clean pass in Phase 2. Report: `extract/corpus_report.txt`; full dump also in `extract/en_all.json`.
- Backups for the gap if ever wanted: OpenIV export "Save raw content" → ModActivator → txt; or
  `rollschuh2282/RDR2-Unhashed-Strings` (label recovery). Not needed for a SP-complete ship.
We ALSO hold the Ko Games `{key → Arabic}` (231,993) as a gender/meaning oracle (Arabic ≈ Hebrew;
it is VISUAL/presentation-form → de-shape or use for gender only).

## ✅✅ MENU-PROOF PASSED IN-GAME (2026-07-19, user screenshots) — ALL GATES CLOSED

`RDR2_Hebrew_menu_proof_READY.zip` (`work/build_ready_dropin.py` — a complete one-extract
drop-in: Ko Games' proven loader infra verbatim + OUR Hebrew font + OUR Hebrew text) was
installed into the game root and booted. Two screenshots closed every remaining gate at once:

1. **Boot legal splash** rendered our `LEGAL_SPLASH_2` in **clean Hebrew, correct right-to-left**
   ("אם אתה קורא עברית תקינה מימין לשמאל — הכל עובד") → the LML `<DataFile>` override MOUNTS and
   **bidi = VISUAL is CORRECT** (a wrong mode would have shown it mirrored).
2. **Settings menu** rendered the tiles **פקדים** (`PM_PANE_CON`) and **תצוגה** (`PM_SCR_DISPLAY`)
   in Hebrew, sitting beside the untouched English tiles (Audio/Graphics/Camera/General) →
   the override is per-key and the rest of the game is unaffected.
3. **ZERO tofu** anywhere → the Hebrew-injected `font_lib_efigs.gfx` (27 glyphs × 18 faces)
   renders in the real frontend. **The font gate — the hard one — is closed.**

⚠️ Two calibration notes for Phase 2 (not defects):
- The `ZZ-RDR2-OK-ZZ` marker line was NOT visible: the REAL `LEGAL_SPLASH_1` is the Rockstar
  copyright line, drawn on a different screen/pass. It didn't matter — the Hebrew itself proved
  the mount (a Latin marker is only needed to separate "file didn't load" from "font has no
  glyphs", and the glyphs demonstrably rendered).
- `TITLE_AUDIO` ("AUDIO") is NOT the Audio tile's key, so that tile stayed English. The settings
  tiles are `PM_PANE_*` / `PM_SCR_*` (`PM_PANE_AUD`, `PM_PANE_GFX`, `PM_PANE_CAM`,
  `PM_SCR_GENERAL`). Irrelevant to the ship — the full corpus covers every key.

Revert = delete `dinput8.dll` from the game root.

### ✅ Proof #3 RAN (2026-07-19) — one PASS, one CONFIRMED-BROKEN, one NEW BUG found
The user correctly identified that the menu-proof only exercised SHORT single lines. Results:

| Case | Result |
|---|---|
| **Long paragraph, RAW** (`LEGAL_SPLASH_2B`) | ❌ **LINE ORDER INVERTED, exactly as predicted** — markers rendered `(5)(6)` on the FIRST line and `(1)(2)` on the LAST. The engine wraps in STORAGE order. |
| **Long paragraph, PRE-WRAPPED with `~n~`** (`LEGAL_SPLASH_1B`) | ✅ **CORRECT** — `(1)→(6)` top-down. **So pre-wrapping IS the fix, and it works.** |
| **Big distressed title** (`WARNING_EXIT_WINDOWS`) | ✅ **"אזהרה" rendered** in the big title face + the `~n~` body correct with `?` on the left ⇒ **font, not an image**, confirmed in-game. ⚠️ cosmetic: our injected glyphs are clean outlines, so the Hebrew title lacks the western *grunge texture* baked into that face's Latin glyphs. |
| **Mixed EN+HE** | ✅ Latin/digits forward and correctly placed. |
| **Punctuation / brackets** | ❌ **NEW BUG (see below).** |

#### 🔴 THE BUG proof #3 found: multi-character neutral runs were mis-placed
`gtav_gxt2.visual_line` reverses Hebrew runs, flips the run ORDER, and keeps every
non-Hebrew run **FORWARD** — treating a punctuation run like a Latin island. But a neutral
run belongs to the RTL flow and must be reversed (and brackets mirrored). In-game:

```
logical   סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה. סוף!
rendered  !ףוס. הדוקנ, ףקמ" — תואכרמ) "םיירגוס: (קוסיפ ינמיס   <- ": (" and ") "" kept forward
correct   !ףוס .הדוקנ ,ףקמ — "תואכרמ" (םיירגוס) :קוסיפ ינמיס
```
→ the colon landed before the wrong word, `(סוגריים)` displayed as `)סוגריים(`, and every
comma/period attached to the wrong side. It is **invisible on a one-clause menu label** (a
1-char neutral run reverses to itself — which is exactly why `?` and `—` looked perfect in
the menu proof) and **wrong on essentially every real sentence**, i.e. most of the corpus.
Also visible in the mixed line: `ב-45.50 דולר` rendered as `ב- 45.50דולר` (space on the
wrong side).

**FIX — `work/rdr2_rtl.py` (NEW): run the real Unicode Bidi Algorithm** (`python-bidi`,
already in the repo `.venv`) with an RTL base and store its visual output. That is the right
tool here *precisely because* the engine does no bidi — we do the engine's job offline, and
we get correct neutral resolution + L4 bracket mirroring for free. **Verified byte-identical
to the old function on every case already confirmed working in-game (zero regression)** and
correct on all the cases it got wrong. RAGE token handling, matched to Ko Games' shipping
Arabic: leading control tokens stay at the FRONT (all 162,997 of their `~z~` lines start with
it, 0 elsewhere); `~n~` and `~sl:a:b~` act as ORDER-PRESERVING segment separators so line
order and subtitle timing stay bound to the right text; inline tokens are swapped for
private-use placeholders so UBA treats each as one atomic LTR run. `rdr2_text.build_hebrew`
now uses it and gained `wrap_width=` (pre-wrap before conversion). Selftests: 12/12 + 14/14.

⚠️ **Cross-game: GTA V ships the SAME `visual_line`, so it very likely carries this same
mid-sentence punctuation defect** — worth an audit of `games/gtav` before its next release.

#### ✅✅ Proof #4 PASSED (2026-07-19) — the UBA fix verified in-game + box width MEASURED
`work/build_proof4.py` → `RDR2_Hebrew_proof4_READY.zip`, deployed into the live game folder.

- **Punctuation / brackets — FIXED, exactly right:** `סימני פיסוק: (סוגריים) "מרכאות" — מקף,
  נקודה. סוף!` and `מספרים: 1, 2 ו-3. שאלה? תשובה: כן.` both render perfectly — colon after the
  right word, `(סוגריים)` correctly enclosing, every comma/period on the correct side.
- **Mixed EN/HE — spacing FIXED:** `…ב-45.50 דולר בחנות של VALENTINE בתאריך 12/04/1899, ואז נסע
  3 ק"מ.` (the old `ב- 45.50דולר` defect is gone).
- **Long paragraph, pre-wrapped — CORRECT:** `(1)→(6)` top-down with correct punctuation.
- **📏 WIDTH MEASURED (boot/legal splash): 120 chars fit on one line, 130 wraps** → usable
  **120–129**. Recorded as `rdr2_rtl.WIDTH_SPLASH = 110` (safety margin for wide letters).
  The 130 line ALSO re-demonstrated the inversion: once it overflowed, its head marker landed
  on the SECOND line — the same auto-wrap failure, caught by the ruler itself.

**Corpus exposure to the wrap rule** (EN chars, tokens stripped — Hebrew usually runs ~10-15%
shorter): >60 chars **27,300 (12.5%)** · >80 **14,076** · >100 **7,756** · >120 **4,952 (2.3%)**;
longest value **1,487** chars. So at the splash width only ~2% needs pre-wrapping — but the
SUBTITLE box is far narrower, so its own ruler run will move that number up a lot.

#### ✅ Proofs #5–#6 — paragraph LAYOUT solved (the last real gap)
Proof #4's paragraph decoded perfectly and still *read* broken. Cause: it was wrapped at 70
chars inside a ~120-char box, and the game's boxes are LEFT-aligned while JUSTIFYING only the
lines THEY wrap — our explicit `~n~` lines are each treated as a final line, so nothing is
justified and the RIGHT edge (where an RTL reader's eye starts) came out ragged.

- **Proof #5** wrapped at 115 and right-aligned by padding each visual line's LEFT with
  `width - len(line)` SPACES. In-game the padded paragraph landed **CENTRED, not right**.
  The user read the result correctly: *"if it can reach the middle, it should be able to
  reach the right"* — the direction was right, the MEASURE was wrong.
- **🔑 Why: the font is PROPORTIONAL.** A space advances **60** units, an average Hebrew
  letter **129** — **one letter ≈ 2.2 spaces**, so one space per missing CHARACTER buys ~45%
  of the distance. Exactly the observed half-way result.
- **FIX — `work/rdr2_metrics.py` (NEW): use the font's real advances.** Each
  `DefineCompactedFont` face in the FFdec XML ends with a `glyphInfo` array
  (`advanceX` per `glyphCode`, units of `nominalSize`=256). It streams the 350 MB XML once
  and caches all **18 faces** (`font_metrics.json`, 264 KB), exposing `text_width` /
  `wrap_px` / `pad_spaces`. `rdr2_rtl.wrap_visual_px` then does BOTH the wrap and the padding
  in font units. Budget calibrated straight from the proof-#4 ruler: the splash FITS the
  120-char line = **13,537 units** and rejects the 130-char one = 14,849 → **13,500 is safe**.
- **✅ Proof #6 PASSED in-game.** All four lines measured 13,474–13,528 units (<0.4% spread)
  and rendered with a true flush right edge, the short last line included. Tested with two
  candidate faces (Hapna Slab Serif DemiBold / Cabrito Norm Demi) — **both look correct**, so
  the face choice is not critical here (all candidates measure the same ruler within ~4%).
  Lines 1–3 need only 1–5 spaces of padding; only the final line needs real padding (71).

- **Proof #6 left a residual: the LAST line still landed ~50px short** while lines 1-3 were
  flush. Cause: a GREEDY wrap dumps the remainder on the final line
  (13224/13272/13414/**9268** units), so that line alone needed a **71-space** pad — and any
  error in the assumed space advance is multiplied by exactly that count.
- **Proof #7 = two fixes, both verified in-game.**
  1. **`wrap_px_balanced`** binary-searches the smallest target width that still yields the
     same line count, evening the widths out (12810/12823/12646/12191) so every pad falls in
     the 12-23 range. Same relative error, ~3px instead of ~50px.
  2. **Stop guessing the space advance — let the game measure it.** We do not know which of
     the 18 faces a surface renders with (they disagree 52-60 units, up to 15%). A LADDER of
     rows "N spaces + the number N" (N = 200…400) under the known-to-fit 120-char ruler
     answers it with no face assumption: **N=200 fits and stops ~110px short; N≥240 OVERFLOWS
     and wraps** (the number drops alone onto the next row) ⇒ **a full box ≈ 225 spaces**, i.e.
     space ≈ 58 units vs the table's 60 — **the model was right to within ~3% all along**.
     Pinned as `rdr2_metrics.SPACE_UNITS_MEASURED = 58`, which `space_width()` now prefers.
  Result: all four lines total 13,506–13,525 against a 13,500 budget (**0.2% spread**) and
  render with a true flush right edge.

⚠️ Per-surface: the subtitle and item-description boxes are narrower — run the same ruler in
Phase 2 to get their budgets. The metrics/wrap/pad code is surface-agnostic.

---

The original three questions, for reference:

- **Q1 — long paragraph + the engine's own word-wrap. THE open risk.** We store VISUAL and the
  engine wraps in STORAGE order, so a long un-broken Hebrew paragraph should wrap into lines
  whose ORDER is inverted (the sentence END lands on the FIRST line → you must read bottom-up).
  `gtav_gxt2.visual_line` already splits on `~n~` and preserves line order — but that only covers
  **explicit** breaks; auto-wrap was never tested on RAGE. `work/build_proof3.py` runs an A/B on
  the two consecutive boot splash screens, which are both long auto-wrapping paragraphs:
  `LEGAL_SPLASH_2B` = the paragraph RAW (expect BROKEN) vs `LEGAL_SPLASH_1B` = the SAME text
  PRE-WRAPPED with `~n~` (expect CORRECT). Sentence markers `(1)…(6)` make an inverted line order
  obvious. If confirmed, the Phase-2 builder must **pre-wrap every long value** (measure the real
  box width per surface) — this affects long item/document descriptions, not the ~40-char average
  dialogue line.
- **Q2 — mixed English+Hebrew in one sentence.** Already PASSED for the simple case: the splash
  line `בדיקת כיוון RTL: 12 דולרים` rendered with the Latin run and digits forward and in the
  right place. Proof #3 stresses it further (Latin brand names, a decimal `45.50`, a date
  `12/04/1899`, a `ק"מ` gershayim).
- **Q3 — the big distressed "ALERT" title: font or image? → FONT, answered from the data.** Ko
  Games' Arabic mod translates `WARNING_EXIT_WINDOWS` / `WARNING_EXIT_WINDOWS2` ('ALERT' → 'يحذر'),
  and also `ALERT_PLAYER_DEAD` ('DEAD' → 'ميت'), `MC_FAIL` ('MISSION FAILED'), `CHAPTER_1` — while
  shipping **only** `font_lib_efigs.gfx`. So every big display string is a FACE inside the exact
  file we injected (all 18 faces got the 27 Hebrew glyphs), not a texture. Proof #3 confirms it in
  3 seconds (ESC → Quit to desktop) via `WARNING_EXIT_WINDOWS` → "אזהרה" + `EXIT_SURE_2`.
- **Bonus — bracket/quote mirroring, also never tested.** `visual_line` deliberately does NOT
  pre-mirror brackets (GTA V's proven choice), and a no-bidi engine performs no L4 mirroring
  either → `(סוגריים)` may display as `)סוגריים(`. Proof #3 carries a dedicated punctuation line.

Artifact: `RDR2_Hebrew_proof3_READY.zip` (same one-extract drop-in shape).

## Next (Phase 2 — everything GREEN, corpus in hand)
Delegate the translation ([[delegate-all-translation]]; gender via the Ko Games Arabic +
[[name-registry-and-internet-check]]) → `rdr2_text.build_hebrew` (VISUAL) into the LML text file
→ ship font + text as an LML package → publish like SM2/GTA/Anno (GitHub `rdr2-hebrew-mods` +
Supabase `games` id=`rdr2` + `mod_version_history`). Scope: see the line report below.

## Line report (Phase-2 scope, from `extract/en_corpus.json` = 217,758 keys with English)

| Type | Lines | Chars (tokens stripped) |
|---|---:|---:|
| **Subtitles / dialogue** (`~z~`) | **158,720** | 5,432,013 |
| ⮡ timed cutscene (`~sl:a:b~`) | 10,637 | |
| ⮡ untimed (ambient barks / interactions) | 148,083 | |
| **UI / text content** | **59,038** | 2,546,911 |
| ⮡ items / gear / shop (`CLOTHING_`, `PROVISION_`, `HORSE_`, `COMPONENT_`, `CONSUMABLE_`…) | 10,386 | |
| ⮡ menus / settings / HUD (`PM_`, `UI_`, `PMHELP_`, `TITLE_`…) | 803 | |
| ⮡ missions / objectives | 137 | |
| ⮡ help / tutorial | 115 | |
| ⮡ other content (documents/letters/speakers/challenges) + hash-only keys | 47,597 | |

Split by mode: **story mode 213,557** (all 158,720 dialogue lines) vs **RDR Online 4,201**
(`MP*`/`NET*`/`FME*`/`PXPT*`, zero dialogue) — Online can be dropped for a SP-complete ship.
Length: ≤25 chars **101,286** · 26–140 **112,827** · >140 **3,645**.

## מסמכים קשורים
- באותה תיקייה: [[games/rdr2/INSTALL|INSTALL]], [[games/rdr2/PIPELINE|PIPELINE]], [[games/rdr2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#rdr2|CLAUDE_INDEX_games]]
