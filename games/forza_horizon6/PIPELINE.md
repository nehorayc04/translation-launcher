# Forza Horizon 6 — PIPELINE

Run everything with the repo venv: `.venv/Scripts/python.exe`.
Override the install path with `FH6_GAME=<dir>`.

## Tools

| file | role |
|---|---|
| `tools/fh6_zip.py` | ForzaTech ZIP reader/writer — preserves the 4 KB alignment + the `0x1123` extra; untouched entries stream-copied so a no-op rebuild is byte-identical. Self-test: `python tools/fh6_zip.py <zip>` |
| `tools/fh6_str.py` | `.str` string-table codec; `parse` / `edit` (surgical) / `to_bytes`. Self-test: `python tools/fh6_str.py <lang.zip>` → `byte-identical 287/287` |
| `tools/fh6_font.py` | `.vfont` descriptor reader (`204 + 8*pages + 36*glyphs + 12*kerns`, exact on all 21 families). Self-test: `python tools/fh6_font.py` → the full coverage table |
| `tools/fh6_rtl.py` | logical → VISUAL via the real UBA (`python-bidi`, RTL base) with engine tokens stashed as atomic PUA placeholders; `\n` order-preserving; per-segment edge-strip. Self-test 6/6 |
| `work/check_install.py` | which manifest-listed files are missing |
| `work/verify_hashes.py` | XXH128 selected files vs the shipped `*.xxh128` |
| `work/survey.py` | per-language table/id counts + parity vs EN |
| `work/scope.py` | the 3 scope numbers + token inventory + surface split → `extract/en.json` |
| `work/probe_zip.py` | re-verify the ZIP alignment invariant |
| `work/probe_ui.py` | XAML fonts / FlowDirection / RTL / hardcoded literals |
| `work/build_menu_proof.py` | the Phase-1 proof: `--deploy` / `--verify` / `--revert` |

## Deploy

**Slot = `media\Stripped\StringTables\EN.zip`** ("English US") — the user's call
(2026-07-27), for **ZERO-ACTION activation**: English is the default, so a player
who never touched the language setting gets Hebrew on the next launch.

**`GB.zip` ("English UK") is the escape hatch and stays PRISTINE.** Measured: GB
differs from EN in only **7,346 of 58,179 values (12.6 %)** while every other
language differs **77-90 %**, so "Settings → Language → English UK" returns an
87.4 %-identical English. `IDS_LanguageSelect_GB` is deliberately NOT patched, so
that row stays findable while the UI is in Hebrew.

⚠️ The language choice lives in a **binary GDK profile blob**
(`…\MicrosoftStore\RUNE\Forza Horizon 6 […]\SaveGames\…\C_ProfileData`) — the same
class as GoWR's `userpreferences`. **Do not edit it**; there is no safe launcher-side
language switch for this game.

```
python work/build_menu_proof.py            # dry run
python work/build_menu_proof.py --deploy   # backs up EN.zip -> EN.zip.he_backup (+ .json sidecar)
python work/build_menu_proof.py --verify   # re-reads the patch OUT of the game file
python work/build_menu_proof.py --revert
```

The sidecar records `original_sha` **and `deployed_sha`**; `--revert` refuses if the
live file is not what we deployed, so a game update can never be silently
downgraded by the backup.

**Activation: none.** English is the default, so the mod is live on the next
launch. A player already on another language picks **Settings → Language →
"English US"** once; after the restart that row reads **"עברית"**.

All bidi/layout probes sit on the **language-select list** (reachable from the main
menu — the pause menu needs a loaded save), labelled by a leading DIGIT because a
digit renders through total tofu: **odd = stored LOGICAL, even = stored VISUAL**.

## Phase-2 build (once the proof settles bidi and the font is solved)

```python
import fh6_zip as Z, fh6_str as S, fh6_rtl as R
entries, payload = Z.read(PRISTINE_EN)           # ALWAYS from the backup, never from the deployed file
replace = {}
for table, edits in hebrew_by_table.items():     # {IDS: logical hebrew}
    txt = {k: R.to_visual(v) for k, v in edits.items()}   # or v, if the proof says LOGICAL
    replace[table + ".str"] = S.edit(payload[table + ".str"], txt)
Z.rebuild(PRISTINE_EN, OUT, replace)
```

Rules that already hold in the code and must not regress:

* build **from the pristine backup**, never from what is deployed;
* `S.edit` keeps the original blob verbatim and appends — untouched strings never move;
* the hash arrays are copied, never recomputed;
* `R.to_visual` stashes tokens longest-first, so `[HIGHLIGHT:{0}]` stays atomic;
* verify by reading the patch back **out of the game file**, not out of the builder.

## Translation (Phase 2 — delegated, Claude never translates the corpus)

* **37,099 real lines / 1.93 M chars.** Single fleet pass.
* **New-Era panel is free and unusually rich**: 22 languages at ~100 % id parity in
  the same archive layout — `ru/pl/cz` (speaker **and** addressee gender from the past
  tense), `es/fr/it/pt/br/mx` (referent gender), `de` (register). Load any of them
  with `work/survey.load(<LANG>)`.
  ✅ After the v403.798 repair **all 24 language zips xxh128-MATCH**, so every one of
  the 22 oracle languages is trustworthy (the earlier "only 8 are clean" caveat is
  withdrawn).
* **Do NOT dedup by the English string before measuring it** — run the standard
  divergence check against the game's own professional locales first. Measured
  divergence from EN: GB 12.6 %, every other language **77-90 %**.
* Community `/translate` pool ordered by visibility: UI/menus → challenges/objectives
  → dialogue/DJ radio.

## Font injection (Phase 1.5)

Target = **`Horizon_RU_A`, `Horizon_RU_C`, `Horizon_RU_D` only.** They already sit
in the `lang="*"` fallback chain that EN/GB resolve to (`Horizon_A → Horizon_RU_A`,
`C → RU_C`, `D → RU_D`), so a Hebrew codepoint the Latin font lacks is looked up
there automatically and **`fontsettings.xml` needs no edit**. Extending the
fallback font is exactly how Playground shipped Cyrillic (440 glyphs vs 242).

Per file: append 27 glyph records (36 B each, codepoint at `+0x18`, kept in
ascending order before the U+FFFD entry), bump `glyphCount` at `0x80`, append the
rasterised blobs to the `.vfontN` page and point each record's `data_off` at them.
**The `.vfontN` payload codec is the one open unknown** — see FEASIBILITY.

## Open

1. **Launch the proof** → settles bidi + confirms the tofu/coverage story.
2. **Font sub-project** — crack the `.vfontN` pixel codec, then inject into the 3 RU files.
3. Publish only on an explicit "פרסם".

## מסמכים קשורים
- באותה תיקייה: [[games/forza_horizon6/FEASIBILITY|FEASIBILITY]], [[games/forza_horizon6/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#forza_horizon6|CLAUDE_INDEX_games]]
