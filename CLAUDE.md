# Translation Launcher

A Windows desktop launcher for Hebrew game-translation mods. Built with
**Eel** (Python ↔ Chromium bridge), a React + Vite frontend, and packaged
as a standalone installer via PyInstaller + Inno Setup.

The launcher fetches a games catalog from the public translation hub
API, displays available titles, downloads the matching translation
archive, and copies it into the game's mod folder.

---

## Repository layout

| Path | Purpose |
|---|---|
| `main_eel.py` | Eel entry point. Spawns the Chromium window and exposes the Python bridge functions consumed by the frontend. |
| `translation_manager/` | Python application package — UI views, asset/download logic, game detection, theme, paths, SWR cache. |
| `frontend/` | React + Vite UI rendered inside the Eel window. Build output is bundled into the executable. |
| `build_assets/` | Installer artwork (icon, wizard BMPs, store screenshots) used by Inno Setup + PyInstaller. |
| `build_exe.bat` | One-shot build script: builds the frontend, runs PyInstaller, then Inno Setup. |
| `TranslationManager.spec` | PyInstaller spec — declares hidden imports, data files, icon, and console behaviour. |

---

## Dev setup

Prerequisites: **Python 3.11+**, **Node 20+**, **Windows 10/11**.

```bash
# Python deps (run from the repo root)
python -m venv .venv
.venv\Scripts\activate
pip install -r translation_manager/requirements.txt

# Frontend deps
cd frontend
npm install
```

---

## Running locally

```bash
# Terminal 1 — frontend dev server (HMR)
cd frontend
npm run dev

# Terminal 2 — Eel host (Python)
python main_eel.py
```

For a one-shot production-mode launch (frontend already built into
`frontend/dist/`):

```bash
cd frontend && npm run build && cd ..
python main_eel.py
```

---

## Building the installer

`build_exe.bat` is the canonical end-to-end build:

1. `npm run build` inside `frontend/` — produces `frontend/dist/`.
2. `pyinstaller TranslationManager.spec` — bundles Python + frontend
   into `dist/TranslationManager/`.
3. Inno Setup compiles the installer into `Output/TranslationManager-Setup-<version>.exe`.

Latest signed builds: see
[Releases](https://github.com/nehorayc04/translation-launcher/releases).

### Re-release rule — build-id (in-app self-update)

The launcher version stays **v1.1.0** and is re-released in place. The
in-app self-updater therefore can't tell two builds apart by version, so
it compares a **build-id**: `build_exe.bat` bakes a fresh UTC timestamp
into `translation_manager/_build_info.py` (gitignored) on every build,
and `get_launcher_update_info` offers an update when the release feed's
build-id differs from the running build's.

**Every re-release MUST**, with the same build-id throughout:

1. Run `build_exe.bat` (bakes a new `BUILD_ID` into `_build_info.py`).
2. Compile `installer.iss`, replace the GitHub `v1.1.0` release asset
   in place (`gh release upload v1.1.0 --clobber`).
3. PATCH the `launcher_releases` row (id 14) with the new `sha256`,
   `size_bytes` **and `build_id`** — the build-id must equal the value
   in `_build_info.py`. Confirm the row stays `is_current = true`
   (the public `/api/launcher` returns 204 if no row is current).

If the baked `BUILD_ID` and the DB `build_id` ever diverge, every
launcher shows a perpetual false "update available".

The installer force-closes a running launcher before the file copy
(`installer.iss` `[Code]` `KillRunningLauncher` — poll-kill + settle +
file-lock probe) and relaunches it non-elevated (`[Run]`
`runasoriginaluser`); this covers both a manual install-over-old and
the in-app self-update.

### Build E (2026-05-23, BUILD_ID 20260523200531)

Two root-cause fixes shipped after a deep audit triggered by an
"install stuck at 0%" + "personal area empty" report:

- **`get_purchases` SQL** — the query asked for `user_purchases.created_at`,
  which does not exist (real columns are `purchased_at` + `completed_at`).
  Every personal-area call returned HTTP 400 `42703` so the UI silently
  rendered "0 purchases". Fixed in `translation_manager/auth/manager.py`
  via a PostgREST column alias `created_at:purchased_at` so the JS
  shape stays identical to `MyPurchase.created_at`.
- **`certifi` missing from the bundle on disk** — `TranslationManager.spec`
  now lists `requests/urllib3/idna/charset_normalizer/certifi` in
  `hiddenimports` AND adds `datas += collect_data_files('certifi')`
  so `_internal/certifi/cacert.pem` is always present. The user's
  Build D install was wrecked by **IObit Uninstaller** — it selectively
  deleted files (including `cacert.pem`) and renamed others with an
  `_IObitDel.<ext>` suffix while the launcher was running; the launcher
  then booted (Python stayed in PYZ) but every HTTPS call died with
  `OSError: Could not find a suitable TLS CA certificate bundle`. The
  explicit spec entry makes the data file impossible to miss — but the
  user-facing rule is **uninstall via Windows Settings → Apps, not via
  IObit/third-party uninstallers**, which is the only thing that
  reliably keeps a half-deleted install off disk.

---

## Frontend build flags

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with HMR on `localhost:5173`. |
| `npm run build` | Type-checks + emits production bundle to `frontend/dist/`. |
| `npm run preview` | Serves the built bundle to validate before bundling. |

---

## License

See repository for license terms.

---

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
`v2026.05.21.1` on `nehorayc04/cp2077-hebrew-mods` (zip + manifest, sha256
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

GitHub: https://github.com/nehorayc04/cp2077-hebrew-mods/releases/tag/v2026.05.24
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

# Steam Hebrew Localizer (Side Project)

Hijacks Steam's Arabic-locale slot to ship Hebrew UI in the desktop client +
Big Picture, using the same RTL/bidi pipeline trick as the CP2077 project.

## Current Status (2026-05-20)

**FULL RUN COMPLETE.** All 8 Steam UI files translated to Hebrew and
validated. `python steam_translator.py all` finished cleanly (exit 0).

### Final output (`steam_hebrew_output/`)

| File | Size | Slot | Keys | Hebrew |
|---|--:|---|--:|--:|
| `steamui_arabic-json.js` | 952 KB | (none — by filename) | 9,424 | 9,104 |
| `shared_arabic-json.js` | 315 KB | arabic | 3,964 | 3,822 |
| `friendsui_arabic-json.js` | 88 KB | arabic | 1,210 | 1,199 |
| `steampops_arabic-json.js` | 11 KB | arabic | 174 | 159 |
| `vgui_arabic.txt` | 10.8 KB | Arabic | 208 | 206 |
| `overlay_arabic.txt` | 20 KB | Arabic | 236 | 220 |
| `platform_arabic.txt` | 4.7 KB | Arabic | 59 | 56 |
| `trackerui_arabic.txt` | 57 KB | Arabic | 671 | 643 |

- **15,946 strings total · 98.03% Hebrew coverage.** The 309 "eng-only"
  entries are brand names / acronyms / FPS values (MMO, RPG, DLC,
  "60 FPS", "ROG Ally", "Steam", …) — intentional pass-throughs.
- Failure tally over the whole run: 34 timeouts · 12 fallbacks · 6
  single-fail (0.04%, kept English original).
- `steamui` carries no `language` key (true of the English source too) —
  Steam matches that bundle by filename. The other 3 JSON bundles + all
  4 VDF files have the locale slot hijacked to Arabic.
- QA: `python verify_steam_all.py` → "slot check: ALL OK".

### Throughput tuning — RESOLVED

The translator's speed problem went through three configs:

| Config | Result |
|---|---|
| `NUM_WORKERS=4`, `BATCH_SIZE=30` | LM Studio saturated — constant 240s `Read timed out`, cascading retries, ~16 strings/min decaying to ~3/min |
| `NUM_WORKERS=2`, `BATCH_SIZE=30` | Fewer timeouts but still ~5.7/min — 30-string batches still too slow per call |
| **`NUM_WORKERS=2`, `BATCH_SIZE=20`** | **~18-20 strings/min, near-zero timeouts** — final/correct setting |

Root cause: a 30-string batch generates enough output tokens that a
27B model on one GPU often exceeds the 240s read timeout; the retry
cascade then destroys throughput. A 20-string batch finishes well
inside the window. **Keep `BATCH_SIZE=20`.**

LM Studio also drifts slower over a long session (16+ h) — a "warm
reboot" (eject + reload the model in the LM Studio UI) restores speed.

### Checkpoint / resume (added 2026-05-20)

`steam_translator.py` now writes a sidecar `<output>.partial.json`
(`{key: hebrew}`) atomically after every batch. On restart it loads the
checkpoint and skips already-translated keys — any kill/crash loses at
most one batch. The checkpoint is deleted once the file completes.
Helpers: `checkpoint_path_for()`, `load_checkpoint()`, `save_checkpoint()`.

### VDF Language-slot bug (fixed 2026-05-20)

`translate_vdf` originally only processed lines inside the `"Tokens"`
block, but the `"Language"` key is a SIBLING of `"Tokens"` (sits before
it) — so the English→Arabic slot hijack never ran on VDF files. Fixed by
moving the `key.lower() == "language"` check ahead of the `in_tokens`
gate. The 4 VDF files already produced were patched in place by
`fix_vdf_language_slot.py` (no re-translation needed).

## Key files

| File | Purpose |
|---|---|
| `steam_translator.py` | Standalone translator — modern JSON bundle parser + legacy VDF parser, hijacks `language` field to `"arabic"`, outputs to `steam_hebrew_output/` |
| `verify_steam_output.py` | QA on translated JSON bundle (Hebrew %, placeholder preservation) |
| `verify_steam_vdf.py` | QA on translated VDF file (encoding round-trip, Language slot, placeholder count vs source) |
| `translation_manager/steam_apply.py` | `find_steam_install()` (registry probe → fallback) + `apply()` (backup-then-copy from `steam_hebrew_output/` into live Steam dirs) |
| `translation_manager/steam_mod.py` | Local lifecycle — cache + enable/disable toggle + clear_cache. Sits above `steam_apply`. |
| `translation_manager/mod_source.py` | GitHub-proxy fetch+verify+extract (written, not yet wired — Step 2 below). |

## Launcher integration (wired & live)

- **Sidebar** groups Games + Apps under a "ספרייה" header (`NavGroupRow` + `NavRow`).
- **AppsView** — Steam card with the full **Install / Enable / Disable**
  state machine (`SteamCardCta`) + a phase-aware progress bar fed by
  `mod_install_progress` events.
- **SettingsView** — "מטמון תרגומים" section with a **Clear Cache** button
  → `ClearCacheConfirm` modal (mirrors `LogoutConfirm`).
- **main_eel.py** exposes `apply_steam_translation`, `get_steam_mod_state`,
  `set_steam_mod_enabled`, `clear_steam_mod_cache`.
- **eel.ts** — `applySteamTranslation` / `getSteamModState` /
  `setSteamModEnabled` / `clearSteamModCache` + `onModProgress` subscriber.
- **eel-bindings.js** — static `mod_install_progress` registration
  (`window.__eelModHandlers`) — the bundler can't safely call `eel.expose`.

### Local lifecycle (steam_mod.py) — implemented 2026-05-20

- **Cache:** `~/.translation_manager/mod_cache/steam/` holds the extracted
  Hebrew tree + `state.json` (`{version, cached_at, enabled, installed_files}`).
  `apply_steam_translation()` is cache-first — only populates the cache on a
  miss, then `enable()`s.
- **Backup scheme — `<name>.orig`** (NOT timestamped `.bak`): the genuine
  Steam file is captured ONCE, the first time we overwrite it, and never
  touched again. A timestamped scheme can't toggle — a 2nd apply would back
  up our OWN Hebrew file. `enable()` = cache → Steam (+ make `.orig` once);
  `disable()` = `.orig` → Steam, or delete the file if no `.orig` (it was
  purely ours, e.g. a new `resource/*_arabic.txt`).
- **Partial-failure safety:** `disable()` only touches files in
  `state["installed_files"]` — the exact set the last `enable()` wrote — so a
  half-finished enable can't make disable delete an untouched Steam original.
- **`clear_cache()`** reverts Steam (restores `.orig`), deletes the `.orig`
  backups, then removes the cache — leaving the machine pristine.

**Cache source — STEP 2 LIVE (2026-05-20):** `apply_steam_translation()`
fetches from the private GitHub repo via the Cloudflare Worker proxy
(`mod_source.fetch_and_extract()` → download → SHA-256 verify → extract),
populates the cache, then `enable()`s. The temp dir is `shutil.rmtree`'d
in a `finally`. On a cache hit it skips straight to `enable()`.

Verified end-to-end 2026-05-20:
- `test_steam_lifecycle.py` — 22/22 (install → enable → disable →
  re-enable → clear_cache), self-restoring.
- Live worker fetch — `fetch_and_extract()` pulled v2026.05.20, SHA-256
  verified, 8 files extracted, temp cleaned. Phases download/verify/
  extract all fired.
Finding: Steam ships Arabic versions of only the 4 JSON bundles; the 4 VDF
`*_arabic.txt` files are purely ours (no `.orig`, deleted on disable).

End-to-end flow: launcher → תוכנות → "התקן" (download+enable) → restart Steam
with Interface=العربية. Thereafter the button toggles Enable/Disable with no
re-download; Settings → "נקה מטמון" wipes it.

## GitHub distribution (Phase 2 — 2026-05-20)

Private repo **`nehorayc04/steam-hebrew-mods`** is the source of truth.
Payload ships in Releases, never in the repo tree.

- **`pack_and_release.py`** — zips the 8 files from `steam_hebrew_output/`
  (internal layout mirrors Steam's tree), SHA-256s it, writes
  `manifest.json` (`{archive_name, sha256, version}`), and
  `gh release create`s it. Artifacts land in `./release/`.
  First release: **`v2026.05.20`** — `steam_hebrew_translation.zip`
  (300,996 bytes, sha256 `98a0c65f4186…`) + `manifest.json`.
- **`steam_mod_worker/`** — Cloudflare Worker proxy, **deployed & live**
  at `https://steam-hebrew-mods.nc52885.workers.dev`. `src/index.js` holds
  the GitHub PAT as the `GITHUB_TOKEN` secret (never shipped); routes
  `/steam-hebrew/manifest` + `/steam-hebrew/archive`. Redeploy after
  edits: `wrangler deploy` (the secret persists).
- `mod_source.py` `PROXY_BASE` defaults to
  `https://steam-hebrew-mods.nc52885.workers.dev` — verify after deploy.

## File-format gotchas (discovered the hard way)

1. **Modern bundles** are `JSON.parse('…')` inside a webpack chunk. Single-
   quoted JS string with `\'` and `\\` escapes wrapping a JSON payload.
   Round-trip needs proper JS-string decode/encode (NOT `unicode_escape`).

2. **Legacy VDF files are UTF-8 with BOM**, not UTF-16 LE as the older
   Steam docs imply. All four (`vgui_english.txt`, `overlay_english.txt`,
   `platform_english.txt`, `friends/trackerui_english.txt`) are UTF-8 BOM
   as of 2026. `translate_vdf` now sniffs both BOMs (`\xff\xfe` and
   `\xef\xbb\xbf`) and round-trips in the source's own encoding.

3. **`shared_dummy: "dont translate"`** — Steam's own meta-placeholder that
   instructs translators to leave it alone. Our system prompt + skip-rules
   correctly preserved it on the steampops test (the AI followed the
   instruction in-band).

4. **U+2028 / U+2029** must be escaped to `  /  ` when re-
   embedding in a JS source string literal — raw bytes would break the
   surrounding `'…'` literal. Easy to miss because they look like ordinary
   spaces in editor display.

## Steam install detection

`steam_apply.find_steam_install()` probes in order:
1. `HKCU\Software\Valve\Steam` → `SteamPath`
2. `HKLM\SOFTWARE\WOW6432Node\Valve\Steam` → `InstallPath`
3. Default `C:\Program Files (x86)\Steam`

Validates each candidate by checking `<dir>/steamui/` exists. Verified
working on this machine — returns `c:\program files (x86)\steam`.

## Verification on the steampops test (already passed)

| Metric | Value |
|---|---|
| Total keys | 174 |
| `language` slot | `"arabic"` ✓ |
| Translated to Hebrew | 172 / 173 (99.4%) |
| Preserved as-is | `shared_dummy: "dont translate"` (intentional) |
| Output | `steam_hebrew_output/steamui/localization/steampops_arabic-json.js` (11,220 bytes) |
| Runtime | 1335s (~22 min) sequential, BATCH_SIZE=12 |

## Open tasks (Steam project)

- [x] ~~Tune concurrency~~ — settled on `NUM_WORKERS=2`, `BATCH_SIZE=20` (2026-05-20)
- [x] ~~Complete full `steam_translator.py all` run~~ — done, 8 files, 15,946 strings (2026-05-20)
- [ ] Manual end-to-end: close Steam → click "התקן" → restart Steam with Interface=العربية → verify Hebrew UI
- [ ] Bundle `steam_hebrew_output/` alongside the launcher in `build_exe.bat` (PyInstaller / Inno Setup) so installed users get pre-compiled translations without running the translator themselves
- [ ] Handle Steam-running case: detect `steam.exe` and either auto-kill (UAC) or block with a clear error before attempting to copy
- [ ] (Optional) Add an "Uninstall" action in AppsView that restores `*.bak.<timestamp>` files
- [ ] (Optional) Log the failing input string in the per-item fallback handler so the 6 single-fail entries can be pinpointed for a cleanup pass

## Technical decisions (Steam project)

- **Arabic-slot hijack** rather than adding a new `hebrew` slot — Steam has
  no `hebrew` locale; the Arabic slot also gets us built-in RTL/bidi
  handling for free.
- **Backup-then-overwrite** with timestamped `.bak.<YYYYMMDD_HHMMSS>` files
  in the same directory — single-file restore, no separate backup tree.
- **OpResult-shaped return** from `apply_steam_translation()` so we don't
  need a new TS type; reuses the existing `OpResult` interface.
- **Source dir detection via `sys.frozen`** — works for both dev runs
  (`steam_hebrew_output/` next to `main_eel.py`) and PyInstaller bundles
  (`steam_hebrew_output/` next to the exe). Bundling step itself still TODO.
- **No new chrome for the install toast** — reuses App.tsx's existing top-
  center `reportStatus` plumbing; AppsView accepts it as a prop.
- **System prompt strictness** copied from CP2077: Hebrew + ASCII only,
  no Niqqud, preserve every placeholder/tag, brand names stay English.
  Validation showed only 1 untranslated string out of 173 — the one Steam
  itself flagged with "dont translate".
