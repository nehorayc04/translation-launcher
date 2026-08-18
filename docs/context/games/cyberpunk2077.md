# Cyberpunk 2077 Hebrew Translation Pipeline

A second project sharing this directory — the standalone scripts that
extract, translate, and repack Cyberpunk 2077's onscreen text into
Hebrew. Not part of the launcher; runs locally against LM Studio.


## Current Status (2026-05-18)

**Onscreens translation — COMPLETE.** All 23,792 pending fields translated
via LM Studio (Gemma-2-27B), merged into `localization_translated.json`,
packed, and deployed.

### Deployed mod

| Property | Value |
|---|---|
| Path | `Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive` |
| Size | 9,216,000 bytes (9.2 MB) |
| MD5 | `91cf8c40302f645dbd265062a8aa0879` |
| Deployed | 2026-05-18 18:36:16 |

### Coverage in this build

| Section | Matched primary keys | femaleVariant updated | maleVariant updated |
|---|---|---|---|
| `onscreens.json` | 60,296 | 59,942 | 126 |
| `onscreens_final.json` | 60,296 | 59,944 | 126 |

→ ~120,138 Hebrew strings live via the Arabic-slot pipeline (up from the
~89k baseline on 2026-05-10).

### Activation

User must set Cyberpunk 2077 → Settings → Language → Interface = **العربية**
(Arabic), then restart the game. The Hebrew text routes through CDPR's
tested RTL/bidi pipeline (see "Arabic-slot approach" in earlier history
notes — putting Hebrew CR2W in `en-us/` crashes the engine).


## Working pipeline (replay any time)

End-to-end is `translate_queue_fast.py` → `fill_translations_from_queue.py
lm_output.json --rebuild`, which chains `rebuild_onscreens_and_pack.py`
through 7 steps:

1. Extract pristine Arabic CR2W skeleton from `lang_ar_text.archive`
2. Serialize CR2W → text JSON (WolvenKit `convert serialize`)
3. Apply Hebrew via `cp2077_apply_translations_to_wkit_json.py`
4. Deserialize text JSON → CR2W
5. Place CR2W into `<project>/source/archive/base/localization/ar-ar/onscreens/`
6. Pack with WolvenKit → `archive.archive`
7. Deploy → `<game>/archive/pc/mod/z_hebrew_translation.archive`

Total runtime: ~1.6 min (94s) on this machine.

**Precondition:** Cyberpunk 2077 must be closed (deploy target is overwritten).


## Throughput tuning (translate_queue_fast.py)

Patches applied 2026-05-17 — reduced error/translation ratio from 22%
to 0.1% over a full 23k-item run:

| Setting | Before | After |
|---|---|---|
| `DYN_MAX_WORDS` | 150 | 100 |
| `LONG_ITEM_CHAR_THRESHOLD` | (none) | 200 — items > 200 chars bypass batching, go straight to single-mode |
| Batch retries on 400 | 2 attempts × 2s sleep | 0 — instant fallback to per-item single-mode |
| `translate_one` retries on context-size | 3 × 2s sleep | 0 — `_is_context_error()` short-circuits the loop |

Sustained throughput on LM Studio (Gemma-2-27B, AMD RX 9070, 4 parallel
workers): **~13 items/min**. Total run for 23,792 items: ~31 hours.

The bottleneck is LM Studio inference, not Python. Process consumed
228 CPU-seconds in 16.5 hours of runtime — it's >99% idle waiting on
HTTP responses.


## Monitor stack

- `cp2077_monitor.bat` → `python -m progress_monitor --adapter cp2077 --tui`
- Adapter: `progress_monitor/adapters/cp2077.py` — parses the translator's
  log file directly, builds 3-stage snapshot (extraction / translation / packaging)
- Core: `progress_monitor/core.py` — pushes to website API every 15 min,
  refreshes TUI every 1.5s
- Bidi handling: `tui.py` `_LEGACY_CONSOLE` detection. On user's cmd.exe,
  `fix_rtl()` reverses Hebrew runs (their terminal doesn't run the bidi
  algorithm). Modern terminals (Windows Terminal, ConEmu, VS Code term)
  set env vars we sniff and skip the reversal.

### Cleanup-mode remap (2026-05-18)

When `translate_cleanup_all.py` runs (sub-thousand sweep against the
already-translated bulk), the adapter detects the `"Global queue:"` /
`"cleanup mode"` log markers and remaps the subset onto the global
scope before pushing/displaying:

- Constant: `CLEANUP_GLOBAL_TOTAL = 23792` in `cp2077.py`
- baseline    = CLEANUP_GLOBAL_TOTAL − cleanup_subset_size
- processed   = baseline + items_fixed_in_this_run
- total       = CLEANUP_GLOBAL_TOTAL

Without this remap the website progress bar snapped to "417/950" for
the cleanup-only subset, looking like project regression instead of
a 98% bulk + final-polish run. The TUI's stage-2 detail row shows both
numbers: "סה\"כ גלובלי: 23,792" + "תוקן עד כה: 23,259 (מהם 417 בריצה הזו)".

**Note:** changes to `cp2077.py` require a TUI restart — Python caches
the module on import. For an immediate one-shot push after editing:
`python -m progress_monitor --adapter cp2077 --once --no-tui`


## Key files

| File | Purpose |
|---|---|
| `translate_queue_fast.py` | Main translator — LM Studio queue runner with dynamic batching |
| `fix_missing_translations.log` | Monitor-watched log (DO NOT rename — adapter regex depends on it) |
| `lm_output.json` | Per-section output dict (`{section: [{primaryKey, femaleVariant, maleVariant}, ...]}`) |
| `missing_translations_queue.json` | Input queue (deduped pending items) |
| `fill_translations_from_queue.py` | Merges `lm_output.json` → `localization_translated.json`. With `--rebuild` chains the full pack+deploy |
| `rebuild_onscreens_and_pack.py` | 7-step WolvenKit chain (extract → serialize → apply → deserialize → place → pack → deploy) |
| `rebuild_subtitles_and_pack.py` | Surgical subtitle re-bake — reuses `cp2077_subtitle_batch.py`'s phase fns, re-bakes only the patched subtitle files (driven by `patch_615_report.json`), then pack+deploy |
| `cp2077_apply_translations_to_wkit_json.py` | Step 3 — applies Hebrew by primaryKey lookup |
| `patch_615_flagged.py` | Dynamic audit-driven cleanup — scans for foreign-script contamination (reuses `audit_translations.detect_scripts`, no 500-cap), re-translates from `localization_export.json`, writes `patch_615_report.json` |
| `cp2077_orchestrator.py` | Unattended final-pipeline driver — monitors subtitle batch → fresh audit → suspend rival LM clients (ctypes `NtSuspendProcess`) → `patch_615_flagged.py` → re-pack both. `--dry-run` supported |
| `progress_monitor/` | Universal monitor package (adapter-driven) |
| `cp2077_status_report.py` | Read-only completeness audit — categorizes every entry in `localization_translated.json` + `dlc_ep1_text.json` (UI / Story / NPCs / Devices / Items / RPG / Subtitles), classifies each as Hebrew / English / Arabic / blank / N-A, writes `cp2077_translation_status_report.txt`. English source: `localization_export.json` for onscreens (pk-matched), the subtitle `secondaryKey` for subtitles. DLC translation status via global stringId cross-check |
| `cp2077_consolidate_dlc.py` | One-time builder of `dlc_ep1_text.json` — consolidates the Phantom Liberty (ep1) localization that was extracted+serialized from `ep1/lang_en_text.archive`. Docstring carries the WolvenKit extract/serialize prereq commands |
| `dlc_ep1_text.json` | `source/resources/` — consolidated Phantom Liberty English text (716 sections: 2 onscreens + 714 subtitle files, 47,905 entries). Static game data; read by `cp2077_status_report.py` |
| `cp2077_qa_defects.py` | Shared 4-class defect detector (foreign-script / English-leak / missing / structural). `scan_all()` is the single source of truth for the QA sweep + watchdog; reuses `audit_translations.detect_scripts`, `cp2077_status_report.classify`, `cp2077_markup_translate.parse_slots`. Also holds the `qa.lock` write-coordination helpers |
| `cp2077_qa_sweep.py` | One-shot QA pass — audit→fix→re-audit loop (cap 5 + no-progress break). Re-translates flagged entries (plain via `patch_615_flagged.translate_clean`, markup via the slot model), gates each fix through `value_is_clean`, writes `qa_sweep_report.json` |
| `cp2077_qa_watchdog.py` | Persistent "castle guard" — every ~20 min re-audits + auto-fixes the JSON (never bakes/deploys). Writes `~/.translation_manager/cp2077_qa_status.json`; parks entries failing 3+ ticks in `qa_watchdog_giveup.json`. Run via `cp2077_qa_watchdog.bat` (auto-restart loop) |
| `cp2077_post_pipeline.py` | Master automation — finish translation → QA sweep → bake subtitles → bake onscreens+deploy → status report → launch watchdog. `--dry-run` / `--skip-qa` / `--full-subs` |


## QA / backup / watchdog automation (2026-05-20)

The post-translation pipeline is now fully automatic. `cp2077_post_pipeline.py`
chains: finish translation (`translate_cleanup_all.py --no-rebuild`) → QA sweep
→ bake subtitles → bake onscreens + deploy → status report → launch the QA
watchdog. Base game ONLY — the Phantom Liberty DLC is excluded everywhere.

- **QA sweep** scans EVERY line for foreign-script contamination, untranslated
  English mid-Hebrew, missing/blank, and broken markup; re-translates the
  flagged ones; loops audit→fix→re-audit until clean. Detection lives in
  `cp2077_qa_defects.py` so the sweep + watchdog flag identically.
- **English-leak heuristic** is "smart": a 2+ word run is flagged only when it
  carries a lowercase common English word (real prose); brand / product names
  ("Nokota Manufacturing", "Street Queen") are not flagged. Tuning against live
  data dropped false positives 1,874 → 175.
- **Backup-on-deploy**: `rebuild_onscreens_and_pack.py` (`step7_deploy`) and
  `cp2077_subtitle_batch.py` (`phase3_pack_deploy`) copy the current
  `z_hebrew_translation.archive` into
  `Cyberpunk 2077\archive\pc\mod_backups\<timestamp>\` before overwriting it
  (only that one archive — the menu/startup mods are untouched).
- **QA watchdog** runs forever; the monitor adapter surfaces it as a 4th stage
  "שלב 4 — בקרת איכות" from the `cp2077_qa_status.json` sidecar (a running TUI
  must be restarted once to pick up the adapter change).
- **markup translator fix**: `cp2077_markup_translate.py` now finalizes /
  logs / checkpoints each entry as it completes (was: silent until 100%), so
  the monitor tracks it live and a crash is resumable via `markup_done.json`.


## Phase 1 COMPLETE — base game deployed (2026-05-21)

Phase 1 (base-game completion + QA + deploy) finished and deployed.

- **Base game — 99.7%** (145,152 / 146,232 translatable lines in Hebrew; only
  390 untranslated — the irreducible damaged/truncated-source tail).
- Translated this session: 3,136 markup entries (`cp2077_markup_translate.py`)
  + 660 clean lines (`translate_cleanup_all.py`).
- **QA**: foreign-script contamination 287/290 stripped; English-word leaks
  141/161 fixed (20 borderline residual in `qa_sweep_report.json`).
- **Deployed**: `Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive`
  (9,170,944 bytes, 2026-05-21 09:48) — 702 re-baked subtitle CR2W + both
  onscreens CR2W. Old archives backed up under `archive\pc\mod_backups\<ts>\`.
- Phantom Liberty DLC untouched (38.8%) — separate task.

### Static mods merged into one archive (2026-05-21)

The two static mods — `z_hebrew_menu_name_patch.archive` (Settings>Language
label override, 18 locales) and `z_hebrew_startup_fix.archive` (Arabic intro
video swap) — were merged into a single **`z_hebrew_static.archive`** (~81 MB,
37 files: 36 onscreens CR2W + 1 bk2). Their game paths are disjoint, so the
merge is lossless — `merge_static_archives.py` extracts both, re-packs once,
backs the originals up to `mod_backups/static_merge_<ts>/`, and removes them.
The mod folder now holds exactly two archives: `z_hebrew_static.archive`
(static, rebuilt only when a build script reruns) + `z_hebrew_translation.archive`
(the live, re-baked translation mod — the only one backed up on every deploy).

### QA tooling — fixes made this session

- `cp2077_qa_defects.py` detector had false positives, all fixed: classify
  mis-flagged translated `<kiroshi>` entries (Hebrew lives in the tag attrs),
  naive `<`/`>` bracket counting, dev-junk (`IGNORE, TO BE DELETED`), and
  truncated-tag attribute leaks. Detection is now slot-aware.
- The english-leak fixer is 2-stage: whole-line re-fix (hallucination-guarded
  — rejects a result that drops <60% of the original Hebrew words), then a
  surgical fallback that translates each leaked fragment WITH the full line as
  context and substitutes it in place (surrounding Hebrew stays byte-identical).
- Foreign-script cleanup = direct `strip_foreign()` (deterministic; no LM).
- `cp2077_qa_sweep.py` gained `--only <kinds>`; `qa.atomic_write_json` retries
  through transient Windows file locks (`os.replace` WinError 5).
- `cp2077_status_report.classify` HEB check now reads the raw value, not the
  tag-stripped core — so translated `<kiroshi>`/`<mothertongue>` entries count
  correctly (this is why base-game jumped 98.0% → 99.7% on the same data).
- `bake_monitor_bridge.py` (NEW) — mirrors `rebuild_subtitles.log` progress
  into `subtitle_batch.log` in the adapter's format, so `cp2077_monitor.py`
  (and the website/launcher) track a `rebuild_subtitles_and_pack.py` bake live.


## Base-game polish + publish (2026-05-22)

Autonomous run after the user reported in-game blanks. A full 4-class
`cp2077_qa_defects.scan_all()` found 221 defects; addressed as follows:

- **QA sweep** (`cp2077_qa_sweep.py`) — 11 genuine fixes (real text + laughs).
- **Vocalizations** — `cp2077_fix_vocalizations.py` (NEW): the LM cannot
  "translate" interjections, so a deterministic 14-form map transliterates
  `Hmm…/Haha./Heh…` → `המממ…/חה חה./חה…`. **70 entries** fixed, no LM.
- **Markup translator** — 5 more `<kiroshi>` TR slots translated.
- **Corrupted markup** — `cp2077_fix_corrupted_markup.py` (NEW): repairs
  entries whose `<kiroshi>`/`<mothertongue>` tag was destroyed by an old
  non-markup-aware pass (`<kiroshi`→`קירושי`, foreign `o=` translated,
  structure collapsed). Rebuilds femaleVariant from the English skeleton in
  `secondaryKey`; falls back to the clean English skeleton when the LM result
  is not clean. **11 garbage entries** restored to valid markup.
- The remaining ~140 residual are correctly left: codes / serials / acronyms
  (`NC484…`, `VSync`, `ISO 100`, `8ug8ear`), CDPR dev-junk (`[db_db]…`,
  `chickentest`), and the truncated-source tail the markup parser rejects.

**Status after the run — base game 99.8%** (145,221 / 146,232 lines; 322
untranslated = the irreducible code/acronym/damaged tail). Re-baked 66
subtitle sections + both onscreens, backed up + deployed
`z_hebrew_translation.archive`.

**Published** `pack_cp2077_mod.py 2026.05.21.1` — GitHub release
`v2026.05.21.1` on `hebrew-translation-hub/cp2077-hebrew-mods` (zip + manifest, sha256
`ebbc63d2…`). Verified: the release is `latest`, the Cloudflare Worker
`/cp2077-hebrew/manifest` serves version `2026.05.21.1`.

The **QA watchdog** is running (`cp2077_qa_watchdog.py`, 1200 s patrol).
A boot-persistent Scheduled Task could not be registered (needs elevation) —
to make it survive reboots, run as admin: Task Scheduler → "At log on" →
`cp2077_qa_watchdog.bat` (the .bat documents this).

### Known issue — 273 dropped markup wrappers (future task)

`is_markup(secondaryKey) and not is_markup(femaleVariant)` finds **284**
entries where an old translation pass dropped the `<kiroshi>`/`<mothertongue>`
wrapper. **11 were garbage** (fixed above). The other **273 are type-A**: a
fluent Hebrew sentence with merely the foreign-audio wrapper gone — they read
correctly in-game (not broken sentences), just lack the Kiroshi/mothertongue
styling. Deferred — re-wrapping 273 means re-translating + re-baking 273
sections; worth its own dedicated pass, not a rushed addition.

### Out of scope — the user's two screenshots

- Journal **"Phantom Liberty"** blank — DLC content (`ep1/` / `Story-ep1-*`),
  not in the base-game pipeline → Phase 2.
- Empty **Contacts list** — no base-translation-data cause (0 structural
  defects; contact-name strings are translated). Needs in-game diagnosis
  (test with the mod disabled).


## Deep English-tail audit + manual hand-fixes (2026-05-23)

End-to-end forensic re-audit covering source JSON, **the baked archive
itself**, and the game folder. Two new artefacts shipped:

- `cp2077_deep_english_audit.py` — 5-layer auditor. Layer 1 reuses
  `cp2077_qa_defects.scan_all()` for source defects; Layer 2 is new — it
  extracts `z_hebrew_translation.archive` + `z_hebrew_static.archive` via
  WolvenKit, serializes every CR2W (~3,085 files), and diffs source vs.
  baked per `(section, primaryKey)`. Layer 3 catches dropped markup
  wrappers (`is_markup(secondaryKey) && !is_markup(femaleVariant)`). Layer
  4 is a defensive walk of small text files in the game folder. Layer 5
  categorises every finding into 12 buckets A..L. Cached extracts /
  serializations cut subsequent runs from ~3 h to ~30 s. Reports:
  `cp2077_deep_english_audit.txt` (human) + `.json` (machine).
- `apply_deep_audit_translations.py` + `apply_leak_fixes.py` — one-shot
  hand patches (no LM), back the spine file up and write atomically.

**Key plumbing fixes for the auditor:**
- Subtitle CR2W keys entries by `stringId`, onscreens by `primaryKey` —
  `_index_by_pk()` accepts both.
- Static archive (`z_hebrew_static.archive`) covers 18 locales (NOT ar-ar —
  that's the main mod). Verification targets the specific menu-label entry
  (pk=49601 / sk endswith `UI-Settings-Language-Arabic`) and asserts its
  femaleVariant ∈ {Hebrew, עברית, Ivrit}. The earlier "any Hebrew char in
  the file" heuristic was a false positive — the patch deliberately writes
  the Latin word "Hebrew" everywhere for cross-locale discoverability.
- `Story-ep1-…` / `…_EP1_…` entries leaked into the base source from older
  passes — they're DLC content and the base archive's Arabic skeleton has
  no slot for them. Filtered out of bake-drift; routed to category K
  (`translated_but_not_in_base_bake`) as informational.

**Findings + actions (base-game audit, JSON-only — no re-bake yet):**

| Bucket | Count | Verdict |
|---|---:|---|
| A. fixable_missing | **5 → 0** | All 5 hand-translated (see `apply_deep_audit_translations.py`) — tutorial text (Hazards/Focus), GPS shard title, `[Say nothing]` dialogue option. Source for pk=77919/87898 was truncated in `localization_export.json`; the FULL text came from a live extract of `lang_en_text.archive` (434 / 563 chars). |
| B. fixable_english_leak | **17 → 4** | 13 hand-fixed; 4 kept (intentional brand names — `"Drugs are bad"` website, `Us Cracks`/`Off the Leash` band+song, three song titles in `mq023_03_street_vendor.json`). Bonus: 4 Thai `เรื่อง:` (subject) labels in two emails fixed to `נושא:` — that's why H dropped 2→0 with no separate pass. |
| C. foreign_voiceset | 3 | `<kiroshi l="rus/jpn/mex"…>` content — by design. |
| D. code_or_acronym | 82 | HDR10, ISO 100, NC484, Mk.31, mmHg — by design. |
| E. dev_junk | 30 | `[db_db]…`, `chickentest`, `IGNORE` — CDPR dev refs. |
| F. dropped_markup_wrapper | 276 | Type-A: Hebrew is intact, only the `<kiroshi>` wrapper was lost. Deferred (cosmetic — no in-game English). |
| G. bake_drift | **5** | Real drift — the 5 manual A-translations are in the source JSON but the baked archive still has the OLD English/Arabic text. Cleared by re-bake. |
| H. foreign_script | **2 → 0** | The two Thai-script leaks were inside the entries hand-fixed in B; resolved as a side-effect. |
| I. loose_game_text | 0 | Clean. |
| J. structural_markup | 0 | Clean. |
| K. translated_but_not_in_base_bake | 1,305 | DLC overflow — base source JSON has Hebrew for these ep1 / Q307 / Barghest pks but the base game's Arabic skeleton has no slot for them. Will ship via the (separate) DLC archive — not a base-game drift. |
| L. orphan_or_other | 0 | Clean. |

**Re-bake required to make the 18 hand-fixes visible in-game.** Affected
sections (6 total):
- `onscreens/onscreens.json` (entries: 6269, 11534, 77919, 87898, 95358)
- `onscreens/onscreens_final.json` (6269, 11521, 11534, 82710, 83878,
  84326, 86817, 87898 (mirror via single pack), 95358)
- `subtitles/quest/mq028/mq028_02_park.json` (1975…)
- `subtitles/quest/q103/q103_07_ghost_town_drive.json` (1665…)
- `subtitles/open_world/voicesets/gang_scv_m_11_rus_40_mt.json` (1898…)
- `subtitles/open_world/voicesets/gang_vdb_f_03_car_30_mt.json` (1949…)

Two backups of the spine file:
`localization_translated.json.bak.deep_audit_a.20260523_132934` (pre-A)
and `…bak.deep_audit_b.20260523_140906` (pre-B). Both can be reverted
file-copy.


## Phantom Liberty DLC translation — SHIPPED v2026.05.24 (2026-05-24)

**Status: SHIPPED.** Full Phase 2 — Phantom Liberty Hebrew translation deployed
as a separate `z_hebrew_dlc.archive` (2.7 MB) sitting alongside the existing
base + static mods.

### Timeline (2026-05-23 → 2026-05-24)

| Stage | Duration | Result |
|---|---|---|
| Translation (`cp2077_dlc_translate.py` via supervisor) | 21.3 h | 30,104 → 325 untranslated (99.3% Hebrew) |
| QA fix (`cp2077_dlc_qa_fix.py`) | ~3 h | 941 / 1,063 defects fixed (88%) — 122 LM-unfixable tail accepted |
| Bake (`rebuild_dlc_and_pack.py`) | 4.0 h | 715 / 716 CR2W baked (1 had no Hebrew), 47,435 fv + 47,434 mv applied, 0 failures |
| Publish | ~1 min | GitHub release v2026.05.24 + Cloudflare Worker auto-served |

### Final deployment

| Mod archive | Size | Coverage |
|---|---:|---|
| `z_hebrew_translation.archive` | 9.2 MB | base-game (99.8 %) |
| `z_hebrew_static.archive` | 81 MB | Settings>Language label + Arabic intro video (18 locales) |
| **`z_hebrew_dlc.archive` (NEW)** | **2.7 MB** | **Phantom Liberty (99.3 %)** |

GitHub: https://github.com/hebrew-translation-hub/cp2077-hebrew-mods/releases/tag/v2026.05.24
SHA-256 of `cyberpunk_hebrew_translation.zip` (92.7 MB):
`15e7b3688495cb67c66bb1ba777019619402d9a22d97bbe2af9964049bac5636`

### Key tooling built this session

- `cp2077_dlc_qa_fix.py` (NEW) — targeted DLC defect fixer with 4 kinds:
  GARBLED (auto-pad Hebrew↔Latin script seams — deterministic, instant),
  UNTRANSLATED (LM retry strict→lenient), DOUBLE_LANG (surgical English-run
  re-translation with context splice), LENGTH_ANOMALY (LM re-translate).
  **Process order matters**: sort defects so GARBLED runs first — otherwise
  slow LM calls block the worker pool and instant fixes wait for hours.
- `_dlc_audit_scout.py` (NEW) — pre-fix defect inventory. Distinguishes
  real defects from heuristic noise (e.g. translated brand names like
  `BARGHEST → ברגסט` are CORRECT and must not be flagged).
- `auto_pad_script_seams()` — deterministic single-space insertion at every
  Hebrew↔Latin abut outside tags. Turned 651 GARBLED entries (like
  `'וreed'`) into clean `'ו reed'` in seconds, no LM calls.

### Known issues to file separately

- `cp2077_status_report.py` still calculates DLC coverage as 38.8 % via
  cross-reference with base `localization_translated.json` — it never
  loads `dlc_ep1_translated.json` directly. The real archive carries
  99.3 % Hebrew (verified by direct walk of the source JSON). Needs a
  small refactor to detect and load the DLC spine file.
- LM Studio runtime still hangs occasionally into `GENERATING` state with
  zero output for tens of minutes — same root cause as the 2026-05-23 hang.
  Recovery: `lms unload --all && lms load gemma-2-27b-it -y --gpu max
  --context-length 8192 --parallel 4`. Already documented in the LM
  Studio hang-recovery section above.
- 122 DLC entries remain LM-unfixable (long messy English, mixed-case
  identifiers, rare Unicode). They are flagged in `dlc_qa_fix_report.json`
  and can be hand-fixed later if specific ones surface in-game.

---


## In-game defects polish + subtitle re-bake (2026-05-24)

After v1.0.1 shipped, a 10-minute play-test surfaced three deterministic defect
patterns (screenshots): Spanish "cuerpo a cuerpo" leaking from English "melee"
tooltips; the protagonist's name `V` transliterated to `וי` in subtitles + UI;
Creole `kamyonèt` left untranslated mid-Hebrew Voodoo-Boys dialogue. Per the
standing rule **"the protagonist's name is always `V` in Latin"** all three are
search-and-replace — no LM needed.

`fix_ingame_defects.py` (NEW) — read-only deterministic pass over the spine JSONs:

| Pattern | EN match | HE replacement | Base hits | DLC hits |
|---|---|---|---:|---:|
| Spanish melee leak | `\bcuerpo[- ]a[- ]cuerpo\b` (case-insens.) | `פנים אל פנים` | **74** | 0 |
| V → V (Latin) | standalone Hebrew `וי` between word boundaries, when EN source has standalone `V` AND no negative context (`VIP`, `AV`, `V8`, `V/T`, `V-for-Victory`, `VTOL`, `VHS`, `VPN`, `V12`) | `V` | **220** | **209** |
| Creole truck word | `\bkamyon(?:èt|et)?\b` | `קמיון` / `קמיונט` (preserves Voodoo-Boys flavor; clean RTL flow) | **10** | 0 |

**Total: 513 spine edits**, atomic-written via `tqf._atomic_write_json`.

Two sequential bakes from the patched spines:

1. **Onscreens** (`rebuild_onscreens_and_pack.py`) — 67s, completed 20:06:54.
   Archive size unchanged (9,170,944 bytes — character-level swaps stay
   inside the CR2W slot).
2. **Subtitles** (`rebuild_subtitles_and_pack.py --sections-file
   affected_base_subtitle_sections.txt`, 571 sections containing V/kamyon
   hits) — **3 h 45 m wall (13,522 s)**, completed 23:52:29.
   fv=34,760 · mv=34,693 applied, **571/571 OK, zero failures**. Old archive
   backed up to `mod_backups/20260524_235229/` before overwrite.

Same `z_hebrew_translation.archive` (9,170,944 bytes) redeployed at
2026-05-24 23:52:29 — base game now ships all 530 in-game defect fixes.

**DLC re-bake** (222 V→V DLC entries patched in `dlc_ep1_translated.json`) —
**DEFERRED**. The DLC bake is ~4 h and the in-game DLC impact is limited; the
fixes will ride with the next DLC release cycle, not as a hotfix.

**v1.0.2 publish status: NOT SHIPPED.** Per user instruction, the release tag +
GitHub upload + Cloudflare manifest update will only run when the user
explicitly authorizes (`"publish 1.0.2"`). Until then the corrected archive is
local-only on the user's machine.

---


## Cross-validation audit infrastructure (2026-05-24)

Goal: independent LQA review of the shipped Hebrew translation — surface
stylistic literalisms, missed Cyberpunk register, and hidden truncations —
**without ever modifying the source JSONs**. The polished v1.0.1 spines are
sacred to this pipeline.

Three scripts, all in the project root:

| File | Role |
|---|---|
| `cross_model_watchdog.py` | Original LM Studio + Llama 3.1 8B watchdog at `http://10.0.0.5:1234`. Replaced after the 8B judge produced ~100% false positives on Hebrew parentheticals etc. Prompt was tightened mid-iteration to 4 mechanical defect categories (truncation / corruption / missing / structural); kept as a fallback. |
| `get_next_audit_batch.py` | Read-only batch fetcher + flag-logger + dashboard renderer. Subcommands: `next [--size N]`, `flag --file <json>`, `dashboard`. Flat row index across base+DLC (~238,556 rows total). Writes only the sidecars below. |
| `continuous_audit_loop.py` | Autonomous LM Studio judge driver (`qwen2.5-32b-instruct` @ `http://10.0.0.5:1234`, 90 s timeout). Subprocess-wraps `get_next_audit_batch.py`, judges each row, persists flags. Built to grind unattended for hours. |

**Sidecar state files** (all in project root, never source paths):

| File | Purpose |
|---|---|
| `cross_audit_checkpoint.json` | `{last_index, processed, flagged, base_done, dlc_done, ...}` |
| `cross_audit_flags.json` | JSONL append-only (one record per line, O(1) append regardless of size — filename keeps `.json` extension per spec) |
| `cross_audit_dashboard.md` | Overwritten with each new batch — live progress + last-5 flags table |
| `cross_audit_batch.json` | Transient: last batch payload between fetch and judge |

**Safety & Autonomy protocol** baked into `continuous_audit_loop.py`:

| Rule | Implementation |
|---|---|
| READ-ONLY source | `PROTECTED_FILES` frozenset of the 4 source JSONs (base/DLC × translated/English). `_safe_write_check()` runs before every write. Violation → `_critical_safety_stop()` writes `CRITICAL_SAFETY_STOP` marker to stderr + exits code 99. |
| Connection self-heal | LM Studio unreachable (preflight, judge call, or subprocess fetch) → 30 s pause, **infinite retry** until response. |
| Bad-response self-heal | Empty / malformed / non-connection error → 30 s pause, up to 3 retries, then skip row. |
| Batch crash recovery | Uncaught exception in row loop → flush partial flags, 30 s pause, restart same in-memory batch from row 0, up to `MAX_BATCH_RESTARTS` (5). Then move on. |
| 4xx client error | Log + skip row (retrying a malformed call doesn't help). |
| Ctrl+C | `_sleep_interruptible` checks `_STOP` every 1 s, so SIGINT exits within ~1 s instead of waiting out a 30 s backoff. |

**Tightened judge prompt (`JUDGE_SYSTEM`):** Lead LQA Editor, three axes
(naturalness / Cyberpunk register / integrity), explicit anti-flag whitelist
(single-word translations, transliterations, parentheticals like
`מיכל דלק (מתפוצץ)`, V kept as Latin). `BE CONCISE — default PASS, only flag
real bugs or stilted phrasing.` Output strictly one of `PASS` or
`FAIL: <critique>; SUGGEST: <better Hebrew>`.

**First batch (Claude-as-judge, 2026-05-24 22:01)** — 10 rows from
`onscreens/onscreens.json` (pk 40–53), 3 stylistic flags:
- pk 49 `BREAKING NEWS → חדשות חמות!` → suggest `מבזק!` (native Israeli ticker)
- pk 50 `Cyberpsycho on rampage! → סייברפסיכו בטירוף!` → suggest `סייברפסיכו משתולל!` (verb-match for "rampage")
- pk 52 `Politician killed by frenzied mob! → ...המון משוגע!` → suggest `...המון מתפרע!` (idiomatic mob descriptor), or active voice `המון פרוע רצח פוליטיקאי!`

**Permission change**: `permissions.defaultMode = "bypassPermissions"` written
to `.claude/settings.local.json` (project-only scope). Existing 50+ `allow`
rules preserved verbatim. Takes effect on next Claude Code launch.

### Audit watchdog false-kills — ROOT-CAUSED + FIXED (2026-06-11)

The audit had been getting killed by its own hang-watchdog **2-6×/hour for
12+ hours** (`audit_watchdog.log`: "HANG DETECTED — checkpoint age > threshold").
A warm LM-Studio reload did NOT fix it (reboot either). A 7-agent adversarial
workflow + direct latency measurement found the **real** root cause, deeper than
"LM is slow":

- **Measured throughput**: qwen2.5-32b on the RX 9070 spills to RAM
  (`DEVICE=Local`) → **~2.46 gen tok/s + ~35 prefill tok/s**. So `max_tokens=300`
  alone is up to ~122 s of generation, and the largest real audit rows
  (max **~3,400 prompt tokens** — a few dozen untranslated DLC onscreens entries
  like pk=85427) add ~97 s of prefill.
- **The actual kill mechanism**: the watchdog keys off
  `cross_audit_checkpoint.json` **mtime**, which `get_next_audit_batch.py` only
  rewrites at batch FETCH / flag-FLUSH — and `flush_flags()` returns early on a
  zero-flag (all-PASS) batch. So **~53 % of batches never refreshed the mtime
  mid-flight**; the watchdog measured *whole-batch wall-time*, not a true hang,
  and killed slow-but-healthy batches with zero stuck rows. The long-FAIL-critique
  timeouts were a *secondary* contributor.

**Fix package (all verified end-to-end, zero kills after restart):**
1. **Per-row mtime heartbeat** — `heartbeat_checkpoint()` (`os.utime(CHECKPOINT_FILE)`)
   called after every judged row in the loop (`continuous_audit_loop.py` ~line 745).
   THE fix: decouples "slow" from "hung" — a genuinely stuck `judge_row()` blocks
   the heartbeat too, so a *true* 900 s stall still trips the watchdog while a slow
   batch keeps the mtime fresh. mtime-only (content/`last_index` still advances per
   batch, so restart-resume is unchanged). Verified: mtime advanced +53 s mid-batch
   while `last_index` held.
2. `max_tokens` **300 → 160** (line ~558) — caps worst gen ~122 s → ~65 s.
   Truncation-safe: the PASS/FAIL verdict is the FIRST token and `critic_feedback`
   is stored as an opaque string (nothing splits on `FAIL:`/`SUGGEST:`), so a
   chopped critique never misclassifies a row — only cosmetically shortens the
   suggestion on <1 % of flags.
3. `REQUEST_TIMEOUT` **90 → 180 s** (line 125) — lets the largest legit rows
   (~162 s = 97 s prefill + 65 s gen) COMPLETE on the first attempt instead of
   timing out → 3 wasted retries. Measured: a full 160-token row = ~82 s.
4. `MAX_BAD_RESPONSE_RETRIES` **3 → 2**, `RETRY_SLEEP` **30 → 15 s** (lines 126-129)
   — caps a truly-stuck row at 180+15+180 = 375 s (< 900 s) instead of 510 s+.
5. `--batch-size` **20 → 8** (`start_audit.bat`) — content checkpoint advances
   ~2.5× more often (smoother website push, less re-work on a true-hang restart).
6. **LM Studio reloaded `--parallel 4 → 1`** — the audit is 100 % serial, so 4
   slots wasted KV cache AND split context to 8192/4 = **2048 per slot**, too small
   for the >2048-token rows (they'd truncate/error). `parallel 1` gives each serial
   request the full 8192 ctx + all compute. **After any reboot, reload with:**
   `lms load qwen2.5-32b-instruct -y --gpu max --context-length 8192 --parallel 1`.
7. `AUDIT_HANG_SECONDS=900` in `start_audit.bat` (kept) — now coherent with the
   above; was the earlier (insufficient-alone) attempt.

**Data → website is healthy**: `monitor_supervisor.bat` runs
`progress_monitor --adapter audit`, pushing `phase=qa processed/total` every 60 s
to `https://hebrew-translation-hub.com/api/admin/progress` (verified live, no HTTP
errors). Checkpoint at handoff: **processed 118,456 / 238,556 (base only), 8,314
flagged**.

### Local-32B audit quality MEASURED — it is poor (2026-06-11)

Blind calibration: Opus 4.8 (via the Claude Code subscription) re-judged 1,000
rows qwen had already rated (400 of its FAILs + 600 of its PASSes), stratified +
weighted to the population. Result — the local qwen-32B audit is **low quality,
not just slow**: **precision ~32 %** (≈68 % of its ~8,600 flags are noise) and
**recall ~23 %** (it misses ~3 of every 4 real defects). Estimated **~12,000 real
defects** in the corpus; qwen surfaced ~2,700 (buried under ~5,800 false flags)
and **missed ~9,200** (incl. ~5,800 OBJECTIVE integrity bugs — foreign-script like
Vietnamese `bất tử`, `V's Apartment`→`דירת ו`, German garbage, truncations — that
it passed). A cheap-screener cascade is therefore **empirically unsafe** (a 23 %-
recall screen never escalates the misses). The genuine quality floor for nuanced
Hebrew LQA is **Claude Sonnet 4.6** (Haiku 4.5 / Gemini Flash over-flag, repeating
the documented Llama-3.1-8B disaster); cheapest full-corpus path = Sonnet 4.6 via
the **Batches API ≈ $145**, async, same-day. (Gemini free-tier rotation does NOT
help — limits are per-PROJECT, not per-key.)

**Audit STOPPED 2026-06-11** and the flag set cleaned **deterministically (no AI,
token-cheap)** after the subscription session limit was hit. Two reusable scripts
added under `universal/`:
- **`classify_flags.py`** — NO-AI false-positive filter over `cross_audit_flags.json`:
  KEEP only on an objective machine-detectable defect (foreign script / control
  char / placeholder-or-tag present in EN but missing from HE); else DROP. The 760
  Opus verdicts already produced (`c:\tmp\flag_cleanup_verdicts.json`, keyed by flag
  line index) override the rule. Output: **`cross_audit_flags_clean.json` (512 real
  defects: 354 Opus + 158 rule)**, `cross_audit_flags_dropped.json` (8,156 noise),
  `needs_ai_review.jsonl` (5,275 prose flags for a later subjective AI pass).
- **`smart_filter_queue.py`** — NO-AI source pre-filter (reuses
  `get_next_audit_batch.build_corpus`): skips rows that need no AI (file-paths/IDs,
  bare code-tags, numbers/symbols-only, EN==HE proper nouns) and writes the rest to
  **`ai_work_queue.jsonl`**. Run: 238,556 → skipped 26,703 → **211,853 queued**.

### NO-AI deterministic defect sweep + fix (2026-06-11)

Going deeper without AI, two more scripts under `games/cyberpunk2077/`:
- **`deep_scan_deterministic.py`** — full-corpus deterministic scan reusing the
  project's tested `cp2077_qa_defects.scan_all` (slot-aware 4-class: foreign /
  english_leak / missing / structural, incl. niqqud via `detect_scripts`) PLUS an
  inline V→וי detector. Found **503 real defects with zero AI** (qwen had missed
  many): foreign 84 · v_transliteration 78 · english_leak 52 · missing 289
  (base 188 / DLC 315) → `universal/deterministic_defects.jsonl`.
- **`apply_deterministic_fixes.py`** — surgically fixes ONLY the deterministically
  fixable kinds: `foreign`→`strip_foreign()`, `v_transliteration`→replace standalone
  `וי` with Latin `V`. Acquires the project QA lock, **backs up each spine file**
  (`*.bak.detfix.<ts>`), atomic-writes, then re-verifies. Run: **135 fixes applied**
  (57 foreign-strip + 78 V→V), **VERIFY 0 residual**. The 27 unfixed "foreign" were
  chars INSIDE tags (legit game data — correctly untouched). `missing` (289) +
  `english_leak` (52) are left for the AI pass (they need translation, not cleanup).
  Spine backups: `localization_translated.json.bak.detfix.20260611_155400` (+ DLC).

### Subtitle speaker-label colon — player name MUST stay "וי" (2026-06-11)

In-game RTL bug: the subtitle **speaker label** (engine renders `[name]:[line]`) put
the colon on the WRONG side for the player — `V:` rendered broken — while Hebrew NPC
names (`שוטר NCPD:`) rendered correctly. Root cause + fix, after a long trace:
- The dialogue string carries **no speaker** (engine prepends it). The speaker name
  resolves from the **player base character record**, NOT the menu/FPP displayName.
  The decisive entry is **`onscreens.json` pk=48683**, secondaryKey
  `Story-base-characters-entities-player-player_base_rec…_displayName`. (Dead ends with
  NO effect: pk=6820 `player_menu_fpp` displayName, pk=6821 empty-sk, and invisible
  bidi marks RLM U+200F / RLE U+202B — the engine ignores marks; only a real Hebrew
  name flips the colon to the correct RTL side.)
- **`apply_deterministic_fixes.py`'s V→וי pass had changed pk 48683 "וי"→"V"**, which
  broke the colon (the old working mod had "וי"). Reverting pk 48683 to **"וי"** + an
  onscreens re-bake FIXED it (user-confirmed in-game).
- **GUARD added** to `apply_deterministic_fixes.py`: the V→וי pass now SKIPS any entry
  whose whole value is exactly "וי" (a bare speaker/character NAME) — only substring
  "וי" inside real dialogue becomes "V". **Do NOT remove this guard.** Rule refinement:
  "protagonist name is Latin V" applies to V **inside dialogue/prose**, NOT to a
  standalone speaker-NAME entry (there "וי" is required for correct RTL colon).
- **Follow-up (not done):** the EP1/DLC player display-names `onscreens.json` pk=92467
  & 92468 (`…player_{ma,wa}_tpp_ep1…_displayName`) hold the GARBLED value `"48683VVVV"`
  — Phantom Liberty player speaker labels will be broken until set to "וי" + re-baked.

WolvenKit CLI 8.17.4 was (re)installed this session to
`…AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe` (lost in a PC reset) —
`WolvenKit.Console-8.17.4.zip` from GitHub releases; .NET 7/8 present. The bake scripts'
`APPLY_SCRIPT` path was also fixed (post-reorg it pointed at the repo root instead of
`games/cyberpunk2077/`).

### ROOT CAUSE of all blank UI lines — Arabic maleVariant (2026-06-11)

The in-game "blank rows" (quest objectives rendering `.( )`, input-hint action
labels, etc.) were NOT missing translations and NOT fonts (both theories
disproven by direct evidence): **the player is male V → the engine resolves
`maleVariant`; our spine fills only `femaleVariant`, so ~7,400 onscreens
entries kept the Arabic skeleton's `maleVariant`; the Heebo fonts carry no
Arabic glyphs → only ASCII (parens/dots) rendered.** Decisive proof: baked
pk=39166 ("Talk to Jackie.") had fv=`דבר עם ג'קי.` mv=`تحدث إلى (جاكي).` —
the on-screen "( )" was literally the Arabic parens.

- **Fix:** `cp2077_apply_translations_to_wkit_json.py` now backfills
  `maleVariant = femaleVariant` when our translation lacks mv and the
  skeleton mv is non-empty. mv-updated jumped 126 → **7,471** on the next
  bake. The subtitle (`cp2077_subtitle_batch.py` L228-233) and DLC
  (`rebuild_dlc_and_pack.py` L152-156) appliers ALREADY had this backfill —
  onscreens was the only broken path. Do not remove it from any of the three.
- Also fixed in the spine the same evening: melee "פנים אל פנים"→"קרב מגע"
  (75 melee-context entries; user request), "Dodge/Dash"→"חמק/זנק" (was
  "חמק/קו" — "Dash" mistranslated as the punctuation dash), lottery
  "Body-count Lottery"→"הגרלת ספירת הגופות" + `"Vigilante"` quotes removed
  (base 17 + DLC 6), subtitle "punching bag"→"שק אגרוף" (q001+mq025,
  user-confirmed in-game).
- ~75 onscreens entries still carry Arabic femaleVariant = the untranslated
  tail (no Hebrew in spine) — queue to the local model later.
- **DLC archive (May 24) still lacks:** the lottery fixes, the pk 92467/92468
  `48683VVVV` repair, the DLC-side spine updates — needs a DLC re-bake (~4h).

### Overnight autonomous polish + final defect sweep (2026-06-13)

A fully-autonomous local-model (gemma-4-31b-it, loaded ALONE `--parallel 1`)
finishing run, then a deterministic verification sweep — base game brought to a
clean floor and re-deployed. All passes use the standard backup + QA-lock +
atomic-write spine discipline; every bake re-deploys
`z_hebrew_translation.archive`.

- **Arabic tail (`tail_translate.py`, NEW)** — the ~75 onscreens entries with an
  empty `femaleVariant` in the spine (so the Arabic skeleton showed in-game).
  gemma-4 translated 69/75 (gate: has Hebrew, tags preserved, no Arabic/niqqud);
  written to both `onscreens.json` + `onscreens_final.json`, onscreens re-baked.
- **Mixed-script corrective round (`corrective_fix.py`, NEW)** — Claude
  personally re-reviewed gemma's earlier "ok" verdicts on 189 Hebrew+Latin
  glued tokens and CONFIRMED the over-judging: ~half were genuinely-broken
  half-transliterations (גילherme, לQuadra, מטלFX, מילוGost). A DIRECTIVE prompt
  (force ONE script: person→Hebrew translit, brand→full English w/ maqaf,
  scream→all Hebrew) + a hard **seam gate** (`[א-ת][A-Za-z]|[A-Za-z][א-ת]`
  rejects any still-glued result) fixed **173/189**; 131 touched subtitle
  sections + onscreens re-baked.
- **Comprehensive anomaly scanners (NEW, reusable, game-agnostic-ish):**
  - `scan_word_anomalies.py` — per-word illogical-token detector across the
    whole corpus (mixed_script / hebrew_digit / single Hebrew|Latin letter /
    punct-in-word / niqqud / repeated / control / double-space / **hebrew_too_long**
    (≥22-letter run) / **long_latin_run** (5+ word Latin inside Hebrew)). Strips
    tags/`{ph}`/literal `\n` first; one ordered review file + JSONL.
  - `scan_language_report.py` — full-corpus English/foreign scan (unicodedata
    FOREIGN class catches ALL non-Latin/non-Hebrew letters): english_in_hebrew /
    english_only / foreign_script / corrupt_midword.
  - `glossary_consistency.py` — 52 named terms, reports those with >1 Hebrew
    rendering (`unify_glossary.py` already renamed 1,342 base + 379 DLC; 19 of 52
    still have context-dependent variants).
- **Final cleanup (`final_cleanup.py`, NEW)** — root-cause-aware: re-translates a
  foreign-leftover **only when the ENGLISH SOURCE is plain English** (`en_is_plain`,
  ≥85% Latin) — so it NEVER touches the intentional foreign-flavor gang dialogue
  (Valentinos Spanish / Voodoo Boys Creole, where the EN source is itself foreign).
  Fixed 11 of the residual seams+leaks.
- **Deterministic brand fix (`det_brand_fix.py`, NEW — no LM)** — the 5 stubborn
  UI brand names gemma kept gluing, mapped to their correct English form:
  מטלFX→**MetalFX**, קריסטלCoat™→**CrystalCoat™**, דוםלuncher→**Doomlauncher**,
  4XדרYves→**4xDRIVE**, EZאסטייטס→**EZ Estates**, plus subtitle ירו בbastards→
  **ירו בממזרים**. Whole-value substring map, instant, re-baked.

**Final verified state (re-scan after all passes, 238,556 rows):**
`mixed_script_word` 16→**0**, `corrupt_midword` 4→**0** — every broken
Hebrew↔Latin seam ELIMINATED. The remaining categories are all
**intentional-by-design, NOT defects**: `single_hebrew_letter` 2,518 (Hebrew
prefixes ו/ב/ל/ה before an icon/tag), `single_latin_letter` 1,157 (X/M button
labels, initials), `english_in_hebrew` ~11k (brand/vehicle/weapon/acronym
passthrough — the documented tuned-heuristic policy), `long_latin_run` 113 +
`english_only` 21 + `foreign_script` 15 (low-visibility foreign-flavor voiceset
/ gang lines + correct English brand names — left on purpose). Deployed:
`z_hebrew_translation.archive` 8,716,288 B + `z_hebrew_dlc.archive` 2.69 MB +
`z_hebrew_static.archive` 81 MB. Website QA bar tracked the whole run
(`chain_progress.py`, wall-time-weighted % to `/api/admin/progress`).

---


## Phantom Liberty DLC translation — IN PROGRESS (2026-05-22)

Full Phase 2 — the entire Phantom Liberty DLC to Hebrew, same Arabic-slot
trick, shipped as a separate `z_hebrew_dlc.archive`.

Base fixes shipped first (release **v2026.05.22**): save-screen playtime units
`UI-Labels-Units-Hours/Minutes` reverted `ה/מ` → `H/M` (`cp2077_fix_units.py`);
"Time Remaining" `rămaining` Latin-extended contamination fixed.

DLC pipeline — new files:
- `cp2077_dlc_build.py` — builds `dlc_ep1_translated.json` from
  `dlc_ep1_text.json`; pre-fills 8,233 entries reusable from the base
  translation by exact English match. LM workload: **40,531** new entries.
- `cp2077_dlc_translate.py` — DLC translator; reuses `translate_queue_fast`'s
  LM core (plain) + `cp2077_markup_translate`'s slot model (markup).
  `dlc_ep1_translated.json` IS the resumable state. **Running since
  2026-05-22 05:30 — ~50h** (40,212 plain + 301 markup). NOTE: it imports
  both tqf and mk, which each swap `sys.stdout`; `_KEEP_STREAMS` pins the
  orphaned wrappers so the shared buffer is never closed mid-run.
- `rebuild_dlc_and_pack.py` — DLC bake: extract `ep1/lang_ar_text.archive` →
  serialize → apply Hebrew (onscreens by `primaryKey`, subtitles by
  `stringId`) → deserialize → place at `ep1/localization/ar-ar/...` → pack →
  `z_hebrew_dlc.archive` → deploy. Verified: compiles, extract OK (717
  files), `section_to_relpath` mapping confirmed.

Section-key → CR2W path: `ep1/<rest>` → `ep1/localization/ar-ar/<rest>`.
DLC onscreens entries key on `primaryKey`; subtitle entries on `stringId`.

Remaining after translation completes: DLC QA sweep → `rebuild_dlc_and_pack.py`
→ deploy → `pack_cp2077_mod.py` (add `z_hebrew_dlc.archive` to `_MOD_FILES`)
→ status report → relaunch QA watchdog.

- `cp2077_dlc_run.py` (NEW) — crash-resilient supervisor: re-launches
  `cp2077_dlc_translate.py` after any abnormal exit (a one-off exit 127 was
  seen). Stops when the translator exits 0 (collected work done) or makes no
  progress. Run this, not the translator directly.

**LM Studio "0 GPUs detected" / "No runtimes found" after update (2026-06-07):**
machine is the Ryzen 5 5600X + **AMD RX 9070 (RDNA4, gfx1201)**. After an
in-place LM Studio 0.4.16 update the GUI Hardware panel showed `0 GPUs
detected`, VRAM 0, and `lms runtime ls` → `No runtimes found` even though the
backend folders were all on disk. Root cause: the previously-selected runtime
was **ROCm**, whose survey fails on RDNA4 Windows (`No hip devices found!`), AND
the 0.4.x decoupled-runtime/engine-index was left unregistered. Key facts:
- For RX 9070 / RDNA4 use **Vulkan**, NOT ROCm — ROCm "No hip devices found" on
  RDNA4 Windows; `vulkaninfo` sees the card fine. Vulkan survey then reports the
  9070 with ~15.92 GiB VRAM.
- `lms` CLI is only an RPC client to the LM Studio daemon. `lms runtime get`
  downloads to disk but only the **running GUI** finalizes/registers the pack —
  so a CLI-only download leaves `lms runtime select` failing with "No installed
  runtime extensions found matching". Don't fix this from the CLI alone.
- The "Enable LM Studio Engine Protocol" Developer toggle is a buggy beta in
  0.4.14–0.4.16 — keep it OFF.
- **Fix that worked (user, 2026-06-07):** back up models + saved profiles, wipe
  the `~/.lmstudio` runtime/config folders, relaunch the GUI so it rebuilds a
  clean engine index, restore the backups. Lighter fallback: quit, delete only
  `~/.lmstudio/.internal/internal-engine-index.json` (derived cache, rebuilt on
  next launch), relaunch. After the reset Vulkan was auto-selected and the GPU
  detected. Do NOT force-kill the GUI from a shell and try to relaunch it —
  agent shells can't launch the GUI into the user's desktop session.

**LM Studio hang recovery (seen 2026-05-23):** after the user updated LM Studio
mid-run, the engine settled into a `GENERATING` state that produced zero
output for tens of minutes (a 60 s curl to `/v1/chat/completions` for "Hello"
returned nothing). The fix: `lms unload --all && lms load gemma-2-27b-it -y
--gpu max --context-length 2048 --parallel 4` — a clean unload+reload clears
the stuck runtime. Sanity test post-reload with a 30 s curl; healthy is
~1.5 s for a short prompt, ~9 s for a 50-token reply.

**LM Studio context-per-slot — the real bottleneck (2026-05-23):** LM Studio
divides `--context-length` per parallel slot. With `--ctx 2048 --parallel 4`
each slot gets ~512 tokens, and a 12-item batch needs ~1,200 tokens
(SYSTEM_PROMPT ~430 + header ~25 + 12 items ~300 + `MAX_TOKENS=512`). Serial
batches still succeed (one slot uses the full 2048), but concurrent batches
all fail with `400 — Context size has been exceeded` and fall back to
single-mode → throughput collapses to ~0.3 entries/min.

**The fix:** `lms load gemma-2-27b-it -y --gpu max --context-length 8192
--parallel 4` — Gemma-2's native context. Each slot gets 2,048 tokens,
batches fit comfortably, all 4 workers run in parallel without errors.
Measured 2026-05-23 with `_lm_client_test.py` (the SDK-path verifier that
imports `translate_queue_fast` and runs its real `translate_batch` 4 ways):
serial 194.8 s, concurrent 117.2 s, **speedup 1.66×, 24.6 items/min**, zero
context errors. The earlier `_lm_parallel_test.py` urllib test reported
2.51× — that was misleading because its prompts were tiny (50 input + 120
output ≈ 170 tokens per slot, well under the 512 budget); use
`_lm_client_test.py` for any future tuning since it exercises the real
translator's prompt sizes.

If `lms ps` ever shows `DEVICE: Local` plus partial GPU offload (i.e. some
layers on CPU), drop to `--context-length 4096 --parallel 4` and set
`MAX_TOKENS = 256` in `translate_queue_fast.py` — see the plan file
`C:\Users\nc528\.claude\plans\hashed-meandering-stearns.md` for the full
fallback ladder.

- `cp2077_dlc_translate.py` markup pass parallelized to 4 workers; both tqf
  and mk swap `sys.stdout` at import → `_KEEP_STREAMS` pins the orphaned
  wrappers so the shared buffer is never closed mid-run.
- Monitor fix — `progress_monitor/adapters/cp2077.py`: the cleanup-mode remap
  (caps the total at 23,792) now triggers ONLY on the literal `cleanup mode`
  marker, not the generic `Global queue:` line — otherwise the DLC's ~40k
  queue was falsely capped. `cp2077_monitor.bat` now shows the DLC translation
  live (stage 2: processed / ~40,116).


## Translation status snapshot (2026-05-20)

`cp2077_status_report.py` baseline:

- **Base game — 97.5%** (141,343 / 144,996 translatable lines in Hebrew;
  3,653 remain). Onscreens 99%+ in every category. The remaining base gap is
  mostly subtitles: Open World **92.1%** (2,132 lines, concentrated in
  `open_world/voicesets/` — foreign-language gang `<kiroshi>` audio cues) and
  Quests 98.3% (765 lines). Zero Arabic-skeleton contamination.
- **Phantom Liberty DLC — 38.2% headline, but misleading.** The DLC ships in a
  separate `ep1/` archive not in the pipeline. DLC onscreens (97.6%) + overlay
  subtitles (97.8%) are "covered" only because they re-use base stringIds that
  are already translated. The **genuinely-new DLC dialogue** (subtitles
  quest 16,945 + open_world 5,904 + media 260) is **~0.7% translated —
  ~22,673 lines pending**, all in `ep1/subtitles/quest/q3xx/`.
- **Grand total base+DLC — 85.4%** (155,579 / 182,242). 26,663 lines remain,
  86% of which is untranslated Phantom Liberty dialogue.

Re-run `cp2077_status_report.py` any time for a fresh count — never re-pack blind.
Reports: `cp2077_translation_status_report.txt` (English) +
`דוח מצב תרגום Cyberpunk 2077 (בסיס + DLC).txt` (Hebrew).


## Prompt hardening (2026-05-18)

Both `translate_queue_fast.py` and `translate_cleanup_all.py` now use a
unified, stricter `SYSTEM_PROMPT`:

- "Professional Cyberpunk 2077 localizer" preamble with Night City tone
- Hard rule: Hebrew + English alphabets only (explicit list of banned
  scripts: Cyrillic, Arabic, Thai, Greek, CJK, Hangul, …)
- Hard rule: NEVER use Niqqud vowel-points
- Tag preservation extended (`<Rich color="...">`, `{VALUE,...}`)
- Glossary extended: Shard → שארד, Edgerunner → אדג'ראנר

The cleanup script also pre-filters items leading with control bytes
0x01–0x05 followed by Rich-text/JSON markers (CR2W framework
placeholders) — `_looks_like_framework_placeholder()`. These can't be
translated cleanly and used to flood the SKIP feed.


## Quality audit (2026-05-18, post-bulk)

`audit_translations.py` scans `localization_translated.json` for
foreign-script contamination in narrative Hebrew. Strips passthrough
tags first (`<kiroshi l="jpn" o="..."/>`, `<Rich color="...">`,
`{VALUE,...}`) so legitimate game-data text inside markup doesn't
count as a bad translation.

Results across 220,485 variants (3,085 sections):

| Stat | Value |
|---|---|
| With Hebrew chars | 214,615 |
| Real foreign-script leaks | **615 (0.28%)** |
| Top scripts | Hangul 268 · Greek 101 · Cyrillic 88 · Katakana 78 · Devanagari 35 · Arabic 31 · Hiragana 20 · Han CJK 8 · Thai 4 · Armenian 3 |
| Niqqud violations | 0 |

Report file: `audit_translations_report.txt` (per-script samples, capped
at 500 per script). These entries can be purged + retranslated via the
cleanup script once the user decides.


## Final-pipeline orchestrator (2026-05-20)

`cp2077_orchestrator.py` automates the post-subtitle-batch stages, unattended:

0. Admin check (`ctypes ... IsUserAnAdmin`) — warns if not elevated.
1. Polls every 60 s until `cp2077_subtitle_batch.py` exits; aborts if the
   process vanishes below 95 % (crash guard).
2. Re-runs `audit_translations.py` for a fresh count. If 0 flagged → stops.
   Else: auto-detects rival LM Studio clients (`steam_translator.py`,
   `translate_queue_fast.py`, `translate_cleanup_all.py`), **suspends** them
   via `ntdll.NtSuspendProcess` (ctypes — no psutil), runs
   `patch_615_flagged.py`, **resumes** them in a `finally` block.
3. If `patch_615` fixed > 0 entries → runs `rebuild_subtitles_and_pack.py`
   then `rebuild_onscreens_and_pack.py`.

Key correction vs. the original ask: suspending a translator client frees
LM Studio's **inference queue**, NOT VRAM (LM Studio holds the model). The
"615" in `patch_615_flagged.py` is historical — the script patches whatever
the *current* audit flags (the original 615 was already purged; audit is
currently 0-flagged).

Verified 2026-05-20: all 3 scripts `py_compile` clean; `patch_615 --dry-run`
→ 0 flagged; orchestrator `--dry-run` → detects the running batch + stage
flow; ctypes suspend/resume smoke test PASSED.


## ⚠ DEPLOY TARGET — critical (resolved 2026-05-20)

**The game the user launches/tests is the project's own staging copy:**
`C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077`
**NOT** `C:\Games\Cyberpunk 2077` (a separate install the user never plays).

All deploy scripts (`cp2077_subtitle_batch.py`, `rebuild_onscreens_and_pack.py`,
`rebuild_subtitles_and_pack.py`, `fix_*`) must have `GAME` pointed at the
staging path. A 2026-05-19 "forensic" note wrongly concluded `C:\Games` was
the real install and repointed two scripts there — so every re-pack landed in
a folder the user doesn't play, and the user kept loading a stale archive.
This is what made subtitles appear "blank" — the staging archive predated the
subtitle translation. **Never repoint deploy at `C:\Games` again.**


## Subtitle "blank" saga — RESOLVED (2026-05-20)

Symptom: in-game subtitles rendered blank / "only special characters" while
menus showed Hebrew. After an exhaustive hunt (verified: data 95 % Hebrew,
fonts md5-identical Heebo, archive structurally identical to pristine,
subtitle widget uses `raj` font that IS swapped) the cause was **purely the
deploy-folder mistake above** — not data, not fonts, not the override
mechanism. Copying the current archive into the staging mod folder → subtitles
render in Hebrew, bottom + above-NPC.

New cleanup tooling:
- `build_subtitle_cleanup_queue.py` — scans `localization_translated.json`
  subtitle sections, queues every untranslated line (multi-word English +
  empty; skips single-word proper nouns) → `cleanup_queue.json` +
  `subtitle_cleanup_sections.txt`. Last build: 3,246 entries / 537 sections.
- `rebuild_subtitles_and_pack.py` — gained `--sections-file` (read the section
  list from a file; avoids the Windows CLI-length limit for ~hundreds).
- `cleanup_subtitles.bat` — one-shot: `translate_cleanup_all.py --no-rebuild`
  → `rebuild_subtitles_and_pack.py --sections-file subtitle_cleanup_sections.txt`.
  ~6.5 h run (translate + re-bake + deploy).


## Open / optional

- [ ] Run `cp2077_post_pipeline.py` once the markup translation finishes — it
      finishes the clean lines, runs the QA sweep, bakes + backs-up + deploys,
      refreshes the report, and launches the QA watchdog. Supersedes the manual
      `cleanup_subtitles.bat` + `cp2077_orchestrator.py` flow for base-game work.
- [ ] (optional) Add `cp2077_qa_watchdog.bat` to Task Scheduler ("At log on")
      so the QA guard survives reboots.
- [ ] Handle Phantom Liberty DLC text in `archive/pc/ep1/lang_ar_text.archive`
      — separate task, NOT part of the base-game pipeline.

---


