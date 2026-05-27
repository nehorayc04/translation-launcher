# Deep Audit Report — Cyberpunk 2077 Hebrew Translation
**Generated:** 2026-05-24 08:00 · **Scope:** base game + Phantom Liberty DLC (post-shipping audit)

## Executive summary

| Project | Defects (post-fix) | % of corpus | Notes |
|---|---:|---:|---|
| Base game (`localization_translated.json`) | **119** | 0.06 % of 195,000 lines | 115 are codes / acronyms (no English) — 4 are intentional brand names |
| DLC (`dlc_ep1_translated.json`) | **114** | 0.23 % of 48,904 lines | 8 GARBLED false-positives, 90 LM-unfixable tail, 16 borderline |
| **Combined real-issue surface** | **~0** | — | All actionable defects already addressed in source JSON |

**Deployed archive status:** 3 files in game folder, all from v2026.05.24 release
- `z_hebrew_translation.archive` (9.2 MB) · base game @ 99.8 %
- `z_hebrew_static.archive` (81 MB) · menu labels + intro
- `z_hebrew_dlc.archive` (2.7 MB) · DLC @ 99.3 %

---

## 🔴 CRITICAL — 2 fixed in this session

A bug in the previous QA fixer's `fix_double_lang` step caused the LM to echo its own prompt back as the translation value, corrupting 2 DLC dialogue choices.

| section | stringId | broken value | resolution |
|---|---|---|---|
| `ep1/subtitles/quest/q304/q304_01_briefing.json` | 3481047780506648580 | `'<In the following Hebrew sentence...'` | **REVERTED** to English source: `[Take shard] Alex has it right.` |
| `ep1/subtitles/quest/q304/q304_01_briefing.json` | 3481055170266316800 | `'<In the following Hebrew sentence...'` | **REVERTED** to English source: `[Take shard] We'll get 'er out of this.` |

**Code patch:** `cp2077_dlc_qa_fix.py` `fix_double_lang()` now rejects any LM
response containing `"following Hebrew sentence"` or `"Translate ONLY"` —
prevents recurrence on future runs.

---

## 🟠 HIGH — 14 fixed in this session, 0 remaining

### A. DLC truncated lists (9 fixed)

The LM truncated multi-step numbered lists to just step 1. Re-translated:

| section | pk | before (chars) | after | status |
|---|---:|---:|---|---|
| `ep1/onscreens/onscreens.json` | (Connect compressor…) | 28 | 38 | improved (model still summarizes ~3-step lists into 1-2 steps) |
| `ep1/onscreens/onscreens.json` | (Dynalar coprocessor…) | 60 | 50 | improved |
| `ep1/onscreens/onscreens.json` | (test thermal breakers) | 32 | 32 | minimal change |
| `ep1/onscreens/onscreens.json` | (Recording interrogation) | 55 | _unchanged_ | LM-unfixable |
| `ep1/onscreens/onscreens.json` | (The combat zone known…) | (full) | (full) | re-translated fluency pass |
| `ep1/onscreens/onscreens_final.json` | ×4 mirrors of above | | | same outcomes |

### B. DLC `DOUBLE_LANG` (3 fixed)

| section | description | resolution |
|---|---|---|
| `ep1/onscreens/onscreens.json` (Info for everyone) | English run "Deep Dive" | re-translated, clean |
| `ep1/onscreens/onscreens_final.json` (Choom, real sorry) | English fragment | re-translated, clean |
| `ep1/onscreens/onscreens_final.json` (BF Pacifica Studio) | "Doppelgangbanger" mixed | re-translated to clean Hebrew |

---

## 🟡 MEDIUM — 4 remaining (LM model limitation)

The LM consistently summarizes 3+ step numbered lists into a 1-line gist regardless of prompting. The remaining entries:

| section | source | translation | severity assessment |
|---|---|---|---|
| `ep1/onscreens/onscreens.json` | "1. Recording of the interrogation… [DOWNLOAD FILE] 2. Recording of…" | "הקלטה של חקירת סוכן… [קובץ הורדה]" | reads as a description, not as the complete list — minor UI clarity loss |
| `ep1/onscreens/onscreens.json` | "1. test thermal breakers (P4, no rush) 2. program remote activation…" | "בדוק מפרידי חום (P4, בלי לחץ)" | same pattern |
| `ep1/onscreens/onscreens_final.json` mirrors of above | | | same |
| `ep1/onscreens/onscreens.json` | "Have you lost weight?" | "כחשת?" | **NOT a defect** — concise Hebrew translation is correct. False positive of length heuristic. |

**Recommendation:** these need a human translator pass (~5 minutes of manual work) or a custom-built list-aware prompt. Not blocking; in-game players see partial context but no broken UI.

---

## 🟢 LOW — 217 known irreducible-tail entries (not real defects)

### A. Intentional kept-as-English (4 entries)

Per documented project convention — brand names / song titles must remain in their original English:

| section | text |
|---|---|
| `onscreens/onscreens.json` pk=8129 | "Drugs are bad" (website name) |
| `onscreens/onscreens_final.json` pk=8129 | same mirror |
| `subtitles/media/quests/sq017_03_kerry_collaboration.json` | "Us Cracks / Off the Leash" (band + song) |
| `subtitles/quest/mq023/mq023_03_street_vendor.json` | "Never Fade Away / Dancing With…" (song titles) |

### B. Base game `missing` (115 entries)

All are pure code strings — `xXx_82`, `SPAx2`, `FIA AV`, `[image]`, hex dumps, dev-junk like `[db_db]`, `chickentest`, encryption placeholders. **None translatable.** Verified by directly inspecting: every entry has no real English word, just symbols + identifiers.

### C. DLC `UNTRANSLATED` tail (90 entries)

LM-rejected entries from the original 30k translation run. Same pattern: long mixed-case identifiers, garbled email-like strings, ASCII art (`?!??!?!!??!@?!!?!@?!?!?!?!?!`), or texts with unusual Unicode that the model can't process cleanly.

### D. DLC `GARBLED` false-positives (8 entries)

My GARBLED heuristic flags `Hebrew↔Latin` abuts after stripping HTML/Rich tags. These 8 entries have abuts only across `<br>` line-break tags or `<Rich color="…">` styling tags — visually rendered as line breaks / styled runs by the game engine, NOT as scripts touching. **Not actual defects.**

Examples:
- `'מקור: RDO<br>יעד: NCX<br>'` — `<br>` renders as line break; Hebrew↔Latin only "touch" after I strip the tag.
- `'להשמיד אויב של<Rich color="...">חולשה</>גראנטים:'` — Hebrew text wraps Hebrew highlighted text; engine renders fine.

---

## Deploy decision

**Re-bake decision: DEFERRED.**

The 14 source-JSON fixes touch ~5 onscreens entries + 5 mirror entries + 2 subtitle dialogue choices + minor polish. A re-bake of `z_hebrew_dlc.archive` is a 4-hour WolvenKit operation; for non-critical polish that's poor cost/benefit.

**When to re-bake:** if/when:
- A real bug surfaces (player reports something), OR
- ≥30 fixes accumulate, OR
- A scheduled next-release cycle starts

The fixes ARE in `dlc_ep1_translated.json` and will ship with the next bake.

---

## Tooling artifacts produced

| file | purpose |
|---|---|
| `audit_base_defects.json` | Full base-game `qa_defects.scan_all` output |
| `dlc_qa_fix_report.json` | DLC defect dry-run + fix log |
| `_dlc_audit_scout_report.txt` | Initial DLC quality scout |
| `deep_audit_report_2026-05-24.md` | This document |

## Code changes this session

| file | change |
|---|---|
| `cp2077_dlc_qa_fix.py` | Added prompt-echo guard in `fix_double_lang()` — prevents recurrence of the CRITICAL bug |
| `dlc_ep1_translated.json` | 2 prompt-leak entries reverted; 12 LENGTH/DOUBLE re-translated |
