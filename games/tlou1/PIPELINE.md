# The Last of Us Part I (PC) — PIPELINE

> **STATUS 2026-07-06 — Phase-1 COMPLETE, menu proof PASSED in-game; now in Phase 2.**
> Gates all closed: **bidi = VISUAL** (LOGICAL rendered reversed, VISUAL correct), **font = Heebo**
> (renders, no tofu), **deploy = PSARC REPACK** (⚠️ loose-file override does NOT work — the engine
> reads only `core.psarc`; built the surgical writer `tools/psarc_write.py`, identity+replace
> round-trips validated + proven in-game). Corpus extracted: **32,881 unique translatable strings**
> (`build_ct_strings.py`). Full build = `work/build_mod.py` (loc encode + `to_visual` + Heebo →
> `psarc_write` repack). Translation delegated via `agent_handoff/` (get_batch/merge_batch, anti-cheat).

End-to-end recipe. Phase 1 (groundwork) is DONE; the checklist below is what remains.

## Tooling (built, `games/tlou1/`)
```
tools/oodle.py       Oodle DLL wrapper (uses the game's oo2core_9_win64.dll)
tools/psarc.py       PSARC v1.4 reader:  info | list [--grep] | extract <path>
tools/tlou_loc.py    ND loc-v2 codec:    decode | dump | stats  (decode+encode, roundtrip-verified)
work/tlou_rtl.py     to_visual() RTL bake (VISUAL storage; markup logical, islands mirrored) — selftest
work/tlou_font.py    Hebrew font:  check <font> | make <heb_src> <out.otf> [--name-ref DINPro.otf]
work/build_menu_proof.py   stage | --deploy | --revert   (the Phase-1 menu proof)
```
Run everything with the repo `.venv` python (fontTools required for `tlou_font`).

## Phase 1 — groundwork (DONE) + the one remaining in-game gate
1. ✅ Container, text format, scope, fonts, Arabic-slot, bidi-mode, deploy, anti-cheat — mapped
   (RECON.md / FEASIBILITY.md).
2. ⏳ **MENU PROOF (user's in-game step):**
   ```
   python work/build_menu_proof.py --deploy      # patches 6 menu strings + swaps DINPro->Hebrew font
   # launch -> Options -> Language -> Text + Subtitles = English -> read the main menu
   python work/build_menu_proof.py --revert      # removes the loose files
   ```
   Reads: CONTINUE="ZZ-TLOU-OK-ZZ" (override loads?), NEW GAME/Options=LOGICAL vs
   LOAD GAME/SETTINGS/EXTRAS=VISUAL (which reads right → storage mode), tofu on all Hebrew → font.
   If loose-drop shows English unchanged, use `proof/DEPLOY.txt` option 2 (extract+rename core.psarc).

## Phase 2 — full translation + build + publish
3. **Extract the corpus.** `psarc.py extract core.psarc "text2/eng.common"` (+ `eng.subtitles`,
   `eng.subtitles-systemic`) → `tlou_loc.py decode` → per-file `{SID: english}` JSON.
   Build a normalized `ct_strings.json` (drop no-letter/number-only rows; keep the token grammar).
4. **Delegate translation** ([[delegate-all-translation]] — Claude never translates). Either the
   community `/translate` pool (import via `universal/community_translate.py import tlou1 <strings>`)
   or the parallel-agent handoff (`universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`). Translators work
   in **LOGICAL Hebrew**; preserve every `<font>`/`<br>`/`|token|`/`[TOKEN]` verbatim.
5. **Build.** For each of the 3 files: `tlou_loc.encode(orig, {SID: to_visual(hebrew_logical)})`
   (markup kept logical, LTR islands mirrored, per §tlou_rtl). Inject/replace the font
   (`tlou_font.make` with the user-chosen Hebrew face). Output the modified `text2/<slot>.*` +
   `fonts/DINPro-*.otf`.
6. **Deploy** to the hijacked LTR slot's files. Options:
   - **Loose override** (if the menu-proof confirmed loose files win): drop the modified files in
     `build\pc\main\` (`--deploy`), or extract core.psarc loose + rename it.
   - **Repack:** `ndarc` core.psarc with the swaps, OR build a **pure-Python surgical PSARC writer**
     (copy every unchanged compressed block verbatim from the original, Oodle-compress only the
     changed entries, rebuild the md5-ordered TOC + block table) — the self-contained path, worth
     building so the launcher can auto-install like SM2/WD2/GoWR. `tools/oodle.py` already does Oodle
     compress; `tools/psarc.py` already parses every field needed to re-emit.
7. **Publish** like SM2/WD2/GoWR: GitHub `tlou1-hebrew-mods` release (zip = modified files + a
   self-contained `install.py` doing the loose-drop/rename + `--revert` + a Hebrew readme) + Worker
   slug `tlou1-hebrew` (for a future launcher applier) + Supabase `games` (id `tlou1`) +
   `mod_version_history`. Activation for users = Options → Language → Text+Subtitles = the hijacked slot.

## Font choice (present to the user)
TLOU UI = FF DIN / Neue Helvetica (industrial grotesque). Hebrew pairings, cleanest first:
**Heebo** (a Hebrew Roboto — closest to DIN), **Assistant**, **Rubik**, then the classic **David** /
**Frank Ruehl**. `tlou_font.make <src.ttf> DINPro-Regular.otf --name-ref extract/fonts/DINPro-Regular.otf`
(masquerades the name so a family-name lookup still resolves). The proof uses Arial (Latin+Hebrew,
universal) just to prove render; swap to the chosen face for production.

## Gotchas / decisions carried forward
- **PSARC entries are md5(path)-ordered** — map by hash, never positional (RECON.md).
- **Deploy target:** `D:\Games\The Last of Us - Part I\build\pc\main\` (env `TLOU_MAIN` overrides). No
  `C:\Games` copy. Back up before any in-place write; loose-drop is non-destructive (adds files only).
- **LTR slot decision** (which language to replace) — pick in Phase 2 with the user (English vs an
  unused slot). Loc filename encodes the slot (`eng.*`, `nor.*`, …).
- **Bidi is VISUAL for all three surfaces** (expected) — but re-confirm subtitles specifically in the
  proof if a subtitle test string is added; the ND engine is uniform-non-bidi per the research.
- **loc can grow freely** (self-describing offsets; no downstream stream to shift) — no delta-0 padding
  needed, unlike GoWR/WAD. Font on the loose path has no byte-length constraint either.

## מסמכים קשורים
- באותה תיקייה: [[games/tlou1/FEASIBILITY|FEASIBILITY]], [[games/tlou1/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou1|CLAUDE_INDEX_games]]
