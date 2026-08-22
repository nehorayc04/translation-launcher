# VirtualDJ 2026 Hebrew — PIPELINE

## Tools
- `tools/vdj_lang.py` — carve embedded `languages.zip` · parse/build the language XML ·
  `build_hebrew(arabic_bytes, {"Section/Key": he})` · CLI `carve|dump|stats|roundtrip`.
- `work/build_menu_proof.py` — `--deploy` / `--revert` the Phase-1 proof.
- Corpus: `extract/langs_orig/*.xml` (12 originals), `extract/english.json`, `extract/arabic.json`.

## Refresh the corpus from a new build
```
PY=../../.venv/Scripts/python
$PY tools/vdj_lang.py carve "C:/Program Files/VirtualDJ/virtualdj.exe" extract/langs_orig
$PY tools/vdj_lang.py dump extract/langs_orig/English.xml extract/english.json
$PY tools/vdj_lang.py dump extract/langs_orig/Arabic.xml  extract/arabic.json
```

## Deploy target (hard-coded)
`%LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml` (per-user, no admin). Overrides the embedded Arabic.
Backup = `Arabic.xml.he_backup` (auto). Revert = restore backup / delete the file.
**Activation:** VirtualDJ → Settings → Options → **language = Arabic**; (re)start the app.

## Phase 2 — full translation (after the menu proof passes)
1. **Delegate the translation** (per `[[delegate-all-translation]]` — Claude never translates game/app
   text; a fleet/second-agent does). Build a handoff over `extract/english.json` (source) with
   `extract/arabic.json` as the professional cross-reference. Register a name/term glossary
   (`[[name-registry-and-internet-check]]`): keep brand/product names Latin (VirtualDJ, ASIO, CDJ, iTunes,
   Serato, RekordBox, Traktor, Deezer, TIDAL, SoundCloud, Beatport, Spotify, Ableton Link, BPM, Stems…),
   preserve `%i/%s/%d/%%` placeholders.
2. **Scope order by visibility:** `Config`+`Settings`+`Columns`+`ContextMenu`+`RootElements`+`Messages`+
   `Errors`+`tooltips` first (the 3,081 UI strings), then the 813 `Actions` VDJScript docs last
   (technical; optional).
3. **bidi:** the menu proof determines LOGICAL vs VISUAL. If VISUAL, add a `visual_line` transform to a
   `build_full.py` (reuse `games/anno1800/work` or `games/watchdogs2/work` `visual()` as template) applied
   at BUILD time only; the translator/fleet always writes LOGICAL Hebrew.
4. **Build:** `vdj_lang.build_hebrew(arabic_bytes, hebrew_map)` → `Languages\Arabic.xml` (keeps
   `lang="Arabic" iso="ar"`; untranslated keys fall back to Arabic so nothing is ever blank).
5. **QA:** placeholder-multiset preserved · no niqqud · no leftover foreign script · Hebrew present where
   English has words · brand/code passthrough allowed. (Reuse the universal structural QA.)
6. **Publish (only on explicit "פרסם"):** this is a free per-user config drop. If we ship it like other
   games — GitHub release repo `hebrew-translation-hub/virtualdj-hebrew-mods` + a tiny installer that copies
   `Arabic.xml` into `%LOCALAPPDATA%\VirtualDJ\Languages\` (+ `--revert`) + Supabase `games` row
   `id=virtualdj` + `mod_version_history`. Optional launcher native applier
   `translation_manager/virtualdj_mod.py` (drop/delete one file — trivial). Community `/translate` pool
   import if desired (`universal/community_translate.py import virtualdj`).

## Notes / traps
- Dropdown has no "Hebrew" → **always the Arabic slot** (or plan-B `Hebrew.xml`+settings name).
- No gender variants, no subtitles, no repack, no anti-cheat → none of the usual traps apply.
- Auto-update re-embeds languages.zip; folder override persists, but re-verify after a major build bump.

## מסמכים קשורים
- באותה תיקייה: [[games/virtualdj/FEASIBILITY|FEASIBILITY]], [[games/virtualdj/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#virtualdj|CLAUDE_INDEX_games]]
