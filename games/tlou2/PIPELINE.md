# PIPELINE — The Last of Us Part II Remastered (Hebrew)

Reproducible build/deploy/publish recipe. Same shape as [Part I](../tlou1/PIPELINE.md);
run everything with the repo `.venv` python (needs `fontTools`, `lz4`).

## Tooling (`games/tlou2/`)
| file | role | status |
|---|---|---|
| `tools/dsar.py` | DSAR→PSARC→pak **reader** (`info`/`list`/`extract`) | ✅ validated on bin/common/core |
| `tools/psarc_write.py` | plain-PSARC v1.4 (zlib) **override builder** (`build`/`verify`/`selftest`) | ✅ round-trip byte-identical |
| `tools/tlou_loc.py` | ND loc-v2 codec (`decode`/`dump`/`stats`) — Part I's, unchanged | ✅ roundtrip=True on eng.* |
| `tools/oodle.py` | Oodle wrapper (only if an inner PSARC uses `oodl` — TLOU2R core is `zlib`) | present, unused for core |
| `work/tlou_rtl.py` | `to_visual` VISUAL baker — Part I's, unchanged | ✅ self-test 9/9 |
| `work/tlou_font.py` | Heebo REPLACE (`check`/`make`) — Part I's, unchanged | ✅ Latin 58 + Hebrew 27 |
| `work/build_menu_proof.py` | Phase-1 menu proof (`--deploy`/`--revert`) | ✅ builds 539 KB override |

Deploy target env overrides: `TLOU2_GAME` (root), `TLOU2_MODS` (mods dir, default `<game>\mods`).

## Phase 1 — groundwork (DONE except the in-game proof)
```
# extract the English source + fonts (already in extract/)
python tools/dsar.py extract <core.psarc> "text2/eng.common"   --out extract/eng.common
# ... eng.subtitles, eng.subtitles-systemic, sid-lookup, fonts/seriffont-*.otf
python tools/tlou_loc.py stats extract/eng.subtitles           # scope + roundtrip check
python work/build_menu_proof.py --deploy                        # user installs ndmodloader, launches, confirms
python work/build_menu_proof.py --revert
```
Menu-proof activation: Options → Language → Text + Subtitles = **English**; read the main menu
(CONTINUE = `ZZ-TLOU2-OK-ZZ`; LOGICAL vs VISUAL Hebrew groups decide bidi storage).

## Phase 2 — full translation (after the proof passes + user approval)
Translation is DELEGATED (never Claude — [[delegate-all-translation]]); Claude builds the tooling +
handoff, merges, QAs, builds, deploys, publishes.

1. **Corpus build** (`work/build_ct_strings.py`, to write) — decode `eng.{common,subtitles,
   subtitles-systemic}` via `tlou_loc`, drop non-translatable (pure tokens / numbers / codes / names),
   emit `extract/ct_strings.json` (community-pool format) keyed by `SID` + section. Import to the
   community `/translate` pool: `python universal/community_translate.py import tlou2 extract/ct_strings.json`.
   Supabase `games` row id=`tlou2` already exists (coming-soon since 2026-07-05).
2. **Gender-aware handoff** (per universal/GENDER_ORACLE_ROLLOUT.md — build NO gender debt):
   alongside each English line, attach the game's own **`text2/rus.subtitles`** (addressee/speaker) +
   **`text2/spa`/`fre`.subtitles** (referent) for the SAME SID (extract them with `dsar`+`tlou_loc`,
   join on SID). Agents translate LOGICAL Hebrew with correct gender from line 1.
3. **Translate** via the agent handoff (copy Part I's `agent_handoff/` template — `get_batch`/
   `merge_batch`/`qa_scan`/`_tokens`) — parallel disjoint md5 slots, anti-cheat gate (reject
   English-on-prose), token-multiset preserved.
4. **Build** the full mod:
   ```
   # apply approved Hebrew (LOGICAL) -> tlou_loc.encode with to_visual per value -> Heebo fonts
   #   overrides[SID] = to_visual(hebrew_logical)      (VISUAL, per the menu-proof outcome)
   #   files = { text2/eng.common, text2/eng.subtitles, text2/eng.subtitles-systemic,
   #             fonts/seriffont-Regular.otf, fonts/seriffont-Medium.otf }
   python tools/psarc_write.py build proof/tlou2-hebrew.psarc \
       text2/eng.common=build/eng.common ... fonts/seriffont-Regular.otf=work/_he_reg.otf ...
   ```
   (A `work/build_mod.py` will wrap this, like Part I. Because a plain PSARC override can grow freely
   and each string is self-describing by offset, there is **no delta-0 padding** constraint — unlike
   GoWR/Anno/Part-I-repack.)
5. **Deploy** — copy `tlou2-hebrew.psarc` into `<game>\mods\` (ndmodloader mounts it). Non-destructive.
6. **Publish** like SM2/WD2/GoWR/Part-I:
   - GitHub `hebrew-translation-hub/tlou2-hebrew-mods` FULL release (so `releases/latest` resolves) — the mod psarc
     + a self-contained `install.py` (finds the game, drops into `mods\`, `--revert`) + Hebrew readme + `manifest.json`.
   - Worker slug `tlou2-hebrew` in `games/steam/steam_mod_worker/src/index.js` (+ `npx wrangler deploy`).
   - Supabase `games` (version/stage/download_url) + `mod_version_history` via
     `universal/publish_version.py tlou2 <ver> --stage beta --sha … --size … --archive-url … --apply`.
   - Optional launcher native applier `translation_manager/tlou2_mod.py` (bundle `dsar.py`+`psarc_write.py`,
     detect key `tlou2`, deploy to `mods\`, back up + revert) like `gowr_mod.py` — SHOW_ON_LAUNCHER once shipped.

## Format quick-reference
- **DSAR** (LE): `"DSAR"` v3.1 | `u32 numEntries@8` | `u32 dataStart@0xC` | `u64 innerSize@0x10` | pad to 0x20;
  entries 32 B `<qqiiB7s` (decompOff, compOff, uSize, cSize, compType, reserved); compType 0=stored else LZ4 block; cSize==0 = zero-fill.
- **Inner PSARC v1.4** (BE): `"PSAR" 1 4 "zlib"` | tocSize | entSize=30 | numFiles | blockSize=0x10000 | flags=0xC;
  TOC 30 B (16 md5(ASCII path) + u32 blockStart + u40 origSize + u40 offset); u16-BE block table (0=full raw block);
  entry 0 = manifest (zero md5), paths **NUL-separated**; entries sorted by md5 ascending.
- **loc v2** (LE): `u32 count` | `count×{u64 SID, u64 offset}` | UTF-8 NUL-terminated blob (blobStart=4+count*16).
  SID shared across languages → map/edit by SID; dup values share one offset; grows freely.
- **Font:** `seriffont-*.otf` = DINPro (CFF, no Hebrew) → REPLACE with Heebo (masquerade the `name` table).

## Notes / gotchas
- Deploy target ≠ the play copy trap: this install is `F:\Games\The Last of Us - Part II Remastered`;
  its `modloader.ini` ModFolder points at a stale `E:\…` path — fix or blank it.
- `oodle.py` is present but core.psarc's inner PSARC is `zlib` — no Oodle DLL needed for TLOU2R (unlike Part I).
- Never touch `core.psarc` — always override via `mods\` (immune to Steam "verify integrity").
- UTF-8 stdout on every script; game must be CLOSED to overwrite a deployed mod file.

## מסמכים קשורים
- באותה תיקייה: [[games/tlou2/FEASIBILITY|FEASIBILITY]], [[games/tlou2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou2|CLAUDE_INDEX_games]]
