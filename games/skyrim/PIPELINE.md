# Skyrim SE / AE Hebrew — PIPELINE

Run **everything** with the repo venv:
`c:\Users\Nehoray_Cohen\Projects\Game translator\.venv\Scripts\python.exe`
(base Python has no `lz4` / `fontTools` / `python-bidi`, and a missing codec turns every
scan into a silent false negative).

Game path override: `SKYRIM_GAME=...` (default `D:\Games\TES - Skyrim - Anniversary Edition`).

## Tools

| file | role |
|---|---|
| `tools/bsa.py` | BSA v103/104/105 reader — `list` / `extract` / `get` |
| `tools/strings.py` | `.STRINGS`/`.DLSTRINGS`/`.ILSTRINGS` codec — `info` / `dump` / `rt` (identity check) |
| `tools/translate_txt.py` | `interface/translate_<lang>.txt` codec (UTF-16LE + BOM, CRLF) |
| `tools/swf.py` | SWF container (FWS raw / CWS zlib) + tag walk |
| `tools/shape.py` | SWF glyph-SHAPE reader → bbox; the ONLY way to measure these faces |
| `tools/skyrim_font.py` | Hebrew injection into DefineFont3 + align-zone lockstep + wide-offset promotion |
| `tools/skyrim_rtl.py` | logical → VISUAL via the real UBA, engine tokens protected. `selftest` |
| `work/build_corpus.py` | full English corpus + the 7 oracle languages + `extract/scope.json` |
| `work/build_proof.py` | the Phase-1 menu proof — `--deploy` / `--revert` / `--verify` / `--body` |
| `work/preview.py` | render injected glyphs OFFLINE to a PNG (judge size/weight without a launch) |
| `work/autocheck.py` | launch → capture the main menu → close, unattended (`shot` / `windowed` / `kill`) |

## Phase 1 — DONE

```bash
PY=".venv/Scripts/python.exe"
$PY games/skyrim/tools/strings.py rt <a .strings file>     # byte-identical round-trip
$PY games/skyrim/tools/skyrim_rtl.py                       # selftest
$PY games/skyrim/work/build_corpus.py                      # scope + oracle languages
$PY games/skyrim/work/build_proof.py --deploy               # build + 5 loose files + verify
$PY games/skyrim/work/autocheck.py shot games/skyrim/work/_menu.png
$PY games/skyrim/work/build_proof.py --revert               # back to pristine
```

`autocheck` writes `[General] sIntroSequence=` into `Skyrim.INI` (skips the Bethesda logo — the
bright intro frame otherwise passes every "is it rendering yet" heuristic and yields a useless
screenshot) and forces windowed 1280x720 in `SkyrimPrefs.ini`. Both are ordinary game settings.

## Phase 2 — translation (delegated; Claude never translates the corpus)

**New-Era 2 corpus PREPARED (2026-08-04) — infrastructure only, NO fleet dispatched.**
`games/skyrim/fleet/build_multilang.py` is the thin Skyrim adapter for
`universal/multilang_review.py` ([[new-era-doctrine]], `universal/MULTILANG_REVIEW.md`).
Run it any time: `.venv/Scripts/python.exe games/skyrim/fleet/build_multilang.py` →
`games/skyrim/fleet/review_corpus/{strings,dlstrings,ilstrings,ui}.final.jsonl`.

- **ONE string per (id, language)** — unlike CP2077's femaleVariant/maleVariant pairs, Bethesda's
  format has no gendered-variant split; `panel[id][lang] = [text, text]` (both slots identical)
  is the honest representation, so the engine's automatic `gendered`/`split_langs` partition
  never fires for Skyrim (same as every other single-string game). What DOES fire: the full
  `refs` panel (up to 6 other languages for `ui`, `de/es/fr/it/pl/ru` — Japanese only covers
  strings/ilstrings/dlstrings, not the UI table which ships in 6 langs, no `translate_japanese.txt`)
  plus the deterministic per-row `gender_hint` this adapter attaches from the Russian reference
  via `universal/gender_oracle.py` (`ru_addressee`/`ru_speaker`, past-tense morphology) — exactly
  the mechanism `build_ct_strings.py` already uses for the `/translate` pool's `context` field.
- **🔴 Bug found + fixed while building this**: `gender_oracle.ru_addressee`/`ru_speaker` return
  `"pl"` for plural (not `"p"`); both the new adapter and the already-published
  `build_ct_strings.py.gender_bits()` mapped `{"p": "רבים"}`, so the fallback silently emitted the
  literal `"נמען=pl"` instead of `"נמען=רבים"`. Fixed in both files; **5,379 already-live
  `/translate` pool rows** carried this in their `context` field — rebuilt + re-imported
  (idempotent upsert-by-string_key, verified live via the public API: 0 remaining `=pl` literals,
  correct `=רבים` on spot-checked rows).
- **`games/skyrim/fleet/brain_glossary.json`** seeded with the 6 already-VERIFIED-in-game terms
  from the Phase-1 proof (`build_proof.py STRINGS_PROOF`: Whiterun→וייטראן, Dragonborn→בן דרקון,
  Iron Sword→חרב ברזל, Lockpick→מפתח פריצה, Gold→זהב, Health Potion→שיקוי בריאות) + 3 game-scope
  rules (engine-token passthrough, no-fv/mv-in-data, store-VISUAL). `brain.Brain.for_game(...)`
  loads it merged with the universal layer (`brain_universal.json`) — verified `terms_in`/
  `inject_fragment`/`canon`/`rules_text` all work end-to-end.
- **Scope, exactly as extracted** (matches `records` in `extract/scope.json`, not the smaller
  cross-plugin-deduped "unique" figure — each row is one distinct string-ID position and needs
  its own line): **strings 48,994 · ilstrings 44,570 · dlstrings 5,665 · ui 647 = 99,876 rows.**
  🔴 **Real bug this exposed and fixed**: an early version of the adapter flattened
  `{plugin: {sid: ...}}` into a flat dict keyed by the BARE `sid` — Bethesda string ids are small
  per-plugin sequential integers, so this silently collapsed 48,994 → 34,855 "strings" rows via
  cross-plugin id collisions. Fixed by keying the flat panel/spine dicts `"<plugin>|<sid>"` while
  `section` still carries the bare plugin name for grouping.
- The launcher (already 100% done, a separate resource surface) is deliberately **excluded** from
  this corpus.
- **✅✅ FLEET RAN + FULL BUILD DEPLOYED LOCALLY (2026-08-11).** A 21-stream fleet (7 machines ×
  groq/sambanova/nim, `fleet/skyrim_nim.py` + `fleet/machines.json` + `fleet/skyrim_watchdog.ps1`)
  translated `fleet/corpus.json` (99,875 rows, built from this adapter's `review_corpus/*.final.jsonl`)
  into `fleet/hebrew.json` — **99,472/99,875 (99.6%)**. The 403 unfilled rows are legitimately
  content-free (`<p align='center'>\r\n</p>`, empty markup-only book-page fragments) — no real text
  to translate. QA sweep on the fleet output: **0 niqqud, 0 foreign-script leaks, 0 leftover
  long-dashes**; the 1,329 rows with no Hebrew letters are all legitimate name/asset-code
  passthroughs (`MaleHeadRedguardVampire`, `AudioTemplateFalmer`, `V1z`, `;`). Random samples read
  as fluent, correct Hebrew.
  **`work/build_full.py`** (NEW) merges it: loads the COMPLETE English base
  (`extract/langs/english.json`, 99,229 entries / 79 plugins / 174 (plugin,kind) groups — the
  authoritative id universe, so every plugin's `.STRINGS`/`.DLSTRINGS`/`.ILSTRINGS` is written in
  FULL, never a partial/blank table), overrides each id with `skyrim_rtl.to_visual(hebrew)` where
  translated else keeps the original English, and rebuilds the UI table + all 3 font SWFs (same
  donors/body_ratio=0.86 as the Phase-1 proof, superseding it). **Deployed to the live game as 178
  loose files** (174 per-plugin STRINGS-family + `translate_english.txt` + 3 SWFs) under
  `D:\Games\TES - Skyrim - Anniversary Edition\Data\` — nothing inside a `.bsa` touched, so Steam
  file-verification cannot revert it. Verified by reading BACK off disk (never trust the builder):
  178/178 present, sample plugin files 100% Hebrew, `$CONTINUE`/`$NEW`/`$LOAD` correctly
  VISUAL-stored, all 13 font faces 27/27 Hebrew glyphs. Manifest `work/_full_deployed.json` drives
  `--revert` (deletes exactly those 178 files, nothing else). **LOCAL ONLY — NOT published**
  (no GitHub release, no Worker manifest, no Supabase `games` row flip); publish only on an
  explicit "פרסם".
- **Ruler pass for books.** `.DLSTRINGS` run to 40k chars with `<p align>` markup — measure
  the book page width with a ruler string and pre-wrap per RDR2 §8b before shipping them.
- **Community pool.** `string_key` = `"<plugin>|<id>|<kind>"` for the string tables and
  `"ui:<$key>"` for the UI table (already live, see above), so an approved export drops straight
  onto the build.

## Publish (only on an explicit "פרסם")

`games.id = skyrim`, detector exe `SkyrimSE.exe`. The mod is a plain folder of loose files:
zip `Data\Interface\*` + `Data\Strings\*` + a self-contained `install.py` (copy in, `--revert`
deletes) — the same shape as the Borderless Gaming / GoWR packages. Price per
`[[mod-price-53-default]]`.

## The LAUNCHER (SkyrimSELauncher.exe) — a THIRD surface, gates closed separately

`tools/launcher_res.py` (resource codec, self-test PASS on 576 strings + 75 bitmaps) ·
`work/build_launcher_he.py` (`--preview` / `--deploy` [`--proof`] / `--verify` / `--revert` /
`--measure`) · `work/launcher_check.py` (launch → screenshot menu + Options dialog → close).

```bash
$PY games/skyrim/tools/launcher_res.py                 # no-op patch must be byte-identical
$PY games/skyrim/work/build_launcher_he.py --preview   # offline PNG of the menu bitmaps
$PY games/skyrim/work/build_launcher_he.py --deploy    # backup + patch (real strings only)
$PY games/skyrim/work/launcher_check.py                # screenshots
$PY games/skyrim/work/build_launcher_he.py --revert    # restore the pristine exe
```

**Two surfaces inside the launcher, needing OPPOSITE handling:**

| surface | storage | why |
|---|---|---|
| 4 main-menu buttons | pre-rendered **275x50 RT_BITMAP** (4 items x 9 languages x 2 states) | we rasterise them ourselves → no bidi question at all |
| everything else | **RT_STRING, stored LOGICAL** | Win32/Uniscribe runs the bidi algorithm for dialog controls |

⚠️ **LOGICAL here is the OPPOSITE of the game engine (VISUAL).** Never route a launcher string
through `to_visual()`.

Writing goes through `Begin/Update/EndUpdateResource`, so replacements may be longer or shorter
than the original. The exe is backed up to `SkyrimSELauncher.exe.he_backup` and every build is
made FROM that pristine copy.

Menu-bitmap rules (all MEASURED off the shipped English, `--measure`): right-aligned with a
**29 px right margin**, cap height 23-26, ink peak **85 dim / 168 bright**, near-black background
erased per column. Size the Hebrew from a FLAT letter (`ה`) — measuring the whole alphabet
inflates the reference by lamed's ascender and the final letters' descenders and under-sizes the
word by ~40% — and align the **baseline**, not the glyph-run bottom, or any word containing
`ק ך ן ף ץ` floats upward.

Remaining: 54 of the 64 English launcher strings (`extract/launcher_en.json`) go through the same
delegated pass as the game corpus.

## מסמכים קשורים
- באותה תיקייה: [[games/skyrim/FEASIBILITY|FEASIBILITY]], [[games/skyrim/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#skyrim|CLAUDE_INDEX_games]]
