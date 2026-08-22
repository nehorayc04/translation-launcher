# AC Odyssey — PIPELINE

Run **everything** with the repo venv: `../../.venv/Scripts/python.exe`
(`fontTools` + `python-bidi` live there; base Python 3.13 has neither, and a missing codec
turns every scan into a silent false "0 hits").
Set `ACO_OODLE_DLL="F:/Games/Assassin's Creed Odyssey/oo2core_4_win64.dll"` (the game ships
its own Oodle). Override the install with `ACO_GAME`.

## Tools

| file | role |
|---|---|
| `tools/aco_forge.py` | scimitar **v28** reader (`info` / `list` / `extract`) + `validate()` |
| `tools/aco_cfd.py` | CFD decode/encode; **per-resource codec sniffing** (`roundtrip`, `codec`) |
| `tools/aco_loc.py` | LocalizationPackage codec — `list` / `dump` / `stats`, `Package.rebuild()` |
| `tools/aco_scan.py` | locate resources by ScimitarClass hash (`hist` / `find` / `sweep`) |
| `tools/aco_font.py` | Hebrew injection into `FontFile` (`list` / `inject`) |
| `tools/aco_rtl.py` | **`to_visual` (SHIPPING)** · `to_logical` (A/B only) · **`is_engine_token`** |
| `work/build_ct_strings.py` | the `/translate` upload — 2 Hebrew categories by visibility + the ar/ru gender source |
| `tools/aco_deploy.py` | append-relocate write-back + `verify` + byte-identical `revert` |
| `work/build_menu_proof.py` | the Phase-1 proof — `--plan` / `--deploy` / `--verify` / `--revert` |
| `work/validate_offline.py` | run the whole deploy against a COPY, then revert |
| `work/scope_report.py` | the honest 3-number scope + dedup safety + bidi evidence |

## Phase 1 — DONE and DEPLOYED

```bash
cd "games/acodyssey"
PY=../../.venv/Scripts/python.exe
export ACO_OODLE_DLL="F:/Games/Assassin's Creed Odyssey/oo2core_4_win64.dll"

$PY work/validate_offline.py --forge DataPC_patch_01.forge   # offline, on a copy
$PY work/build_menu_proof.py --deploy
$PY work/build_menu_proof.py --verify
$PY work/build_menu_proof.py --revert                        # undo everything
```

**Deployed right now:** 11 resources in `DataPC_patch_01.forge` + 11 in `DataPC.forge`
(2 Arabic LocalizationPackages + 9 Hebrew-injected fonts each), and
`ACOdyssey.ini [Language] Text/Subtitles/Client = ar-AR` with `Sound = en-US`.
Backups: `<forge>.he_backup` + `<forge>.he_journal.json` beside each forge.

### What the user does

1. Launch the game — the **title screen** is the first proof surface.
2. Press **Esc** in-game for the **pause menu** (Character / Store / Options / Quit / Credits
   are all on one screen), and open **Options**.
3. Screenshot both.

### How to read the screenshot (current build — everything VISUAL)

| row | what it is | verdict |
|---|---|---|
| `משחק חדש` / `המשך משחק` / `אפשרויות` / `חנות` / `קרדיטים` … | a REAL Hebrew menu, stored VISUAL | every label must read **correctly** — that is the whole test |
| the 27-letter row (Credits, Options page) | glyph coverage | any tofu box = a face missed the injection |
| the sentence with `(סוגריים) "מרכאות" — מקף, 12.5 ו-Odyssey` | layout | punctuation, parens, digits and the Latin island in a real sentence |
| `ZZ-A22-LOGICAL שלום` (Sound row) | the ONE control, stored LOGICAL | it **must look mirrored** while everything else reads right — and the Latin tag makes a stale deploy impossible to mistake for a fix |

⚠️ **Do not transcribe the Hebrew to judge it** — a transcription returns *reading* order, not
pixel order, so a mirrored line and a correct line come out identical
([[hebrew-screenshot-transcription-trap]]). A native reader looking at the screen is the
authority; that is exactly how the first LOGICAL build was caught.

## Phase 2 — translation (delegated; the pool is LIVE)

Claude never translates the corpus ([[delegate-all-translation]]).

1. ✅ **Community pool LIVE — 59,430 rows** (`work/build_ct_strings.py` →
   `universal/community_translate.py import acodyssey`): **ממשק ותפריטים 25,658 → כתוביות
   עלילה 33,772**, `string_key` = `ui:<id>` / `subs:<id>`, 123 dropped (no real letter after
   token removal), round-trip verified 0 unresolvable. **55,273 rows carry the game's own
   Arabic AND Russian in `context`** as the gender source; no auto-derived hint (Odyssey's
   Arabic is largely unvocalized → an open-class guess manufactures confident garbage,
   [[gender-hint-needs-closed-set]]).
2. **Key by id, never by the English string** — 7 of the game's own locales diverge on
   10–37 % of duplicate-English groups.
3. **Guards.** Preserve `<tag>`, `{NAMED}` and numeric placeholders, `%spec`, `\n`. Treat a
   bracket as a token **only** via `aco_rtl.is_engine_token` — `[sigh]`/`[&gasp]`/`[Save Icon]`
   are prose and must be translated.
4. **Fleet.** ar/ru/pl/fr/it/es/de are all at 100 % id parity, so the New-Era panel is free.
5. **Build.** `aco_rtl.to_visual` (SHIPPING) → `acu_loc.encode_payload` → `Package.rebuild` →
   `aco_cfd.encode_resource` (sniffed codec) → `aco_deploy.apply` into **both** forges. Only
   the **lang-22** pair is strictly needed (the ladder proved it live); patching lang 24 too
   is cheap insurance.
6. **Font.** If the proof shows tofu on a DINCond surface, add a whole-font REPLACE path for
   the 2 CFF faces.
7. **Publish** only on an explicit "פרסם" — GitHub release + Worker slug + Supabase `games`
   row + `mod_version_history`, price per [[mod-price-53-default]].

## Reverting

```bash
$PY work/build_menu_proof.py --revert     # forges + ini + registry
```
Restores from `<forge>.he_backup` when present, else replays `<forge>.he_journal.json`
(records + truncate) — both proven byte-identical.

## מסמכים קשורים
- באותה תיקייה: [[games/acodyssey/FEASIBILITY|FEASIBILITY]], [[games/acodyssey/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acodyssey|CLAUDE_INDEX_games]]
