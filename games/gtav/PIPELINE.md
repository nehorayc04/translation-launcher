# GTA V (Legacy) — Hebrew pipeline

`games.id = gtav` · deploy slot `mods/update/update.rpf` · bidi = **VISUAL** · slot = **American (English)**.

## Tooling
| File | Role |
|---|---|
| `work/gtav_gxt2.py` | GXT2 codec — `joaat` / `read_gxt2` / `write_gxt2` / `visual_line`. Built, 21/21 tests. |
| `work/gtav_extract.py` | `global.gxt2` → `agent_handoff/to_translate.json` {joaat_hex: english} + `work/global_en.json`. |
| `work/gtav_build.py` | `agent_handoff/hebrew.json` (logical) → `visual_line` → gxt2 → repack → deploy to mods/. |
| `agent_handoff/` | UI-only translation handoff (INSTRUCTIONS + get_batch/loop_merge/qa_scan + _tokens). Loop proven end-to-end. |

**Prereq for extract+build:** a .NET repack tool. **gtautil** (indilo53/gizzdev) is the recommended one (bundles all 6 GTA5 key blobs; `extractarchive`/`replace`/`createarchive`/`fixarchive`). Put `gtautil.exe` on PATH or in `games/gtav/tools/`, or set `GTAUTIL=<path>`. Alt: CodeWalker.Core reflection with a key cache; or write the mods/ RPF **open** (OpenIV ASI still loads it) to skip NG-encrypt.

## Phase 1 — groundwork (DONE)
Format cracked · codec built+tested · bidi=VISUAL confirmed · font (main UI) already installed · deploy slot proven · counts done. See `FEASIBILITY.md`.

## Phase 2 — UI translation (CURRENT)
1. **Get gtautil** (download once) → `py -3 work/gtav_extract.py` → fills `agent_handoff/to_translate.json` (~23,136 UI strings) + `work/global_en.json`.
   *(or OpenIV-export `global.gxt2` to `work/_rpf/global.gxt2` and re-run extract — it reads that file.)*
2. **Hand off** `agent_handoff/` to the second (Google/Antigravity) agent — see `agent_handoff/INSTRUCTIONS.md`. It loops `get_batch → translate (LOGICAL) → loop_merge` to "All done!". `qa_scan.py` must read CLEAN.
3. **Identity round-trip FIRST** (before shipping Hebrew): `py -3 work/gtav_build.py --build-only` on an UNCHANGED `hebrew.json` (all-English) → repack → confirm the game boots vanilla English. Proves the repack chain.
4. **Build + deploy:** `py -3 work/gtav_build.py` → visual-reverse + write gxt2 + repack into `mods/update/update.rpf` (backs up first). Game CLOSED.
5. **In-game proof (user gate):** launch `GTA5.exe`; confirm menu/HUD Hebrew renders RTL, readable, tokens intact, no tofu/mirror/crash. (font already installed.)

## Phase 3 — full game (LATER)
- Subtitles/dialogue: `MISSION.gxt2` (+ per-mission) — same pipeline, separate `to_translate`. Huge (~255k).
- Niche Scaleform fonts: inject Hebrew into `gfxfontlib.gfx` + `font_lib_sc/heists/slots/taxi/typewriter/web.gfx`.

## Publish (like SM2/CP2077, when ready)
GitHub `hebrew-translation-hub/gtav-hebrew-mods` + Worker slug `gtav-hebrew` + Supabase `games` row (`gtav`) + `mod_version_history`. Mod payload = the edited `mods/update/update.rpf` deltas (the Hebrew `global.gxt2` + the font OIV), packaged as an OpenIV `.oiv` or a mods/ overlay zip.

## Activation (document for users)
Install into `mods/` (OpenIV), keep Language=American, launch `GTA5.exe`. No language switch. Reversible (delete the mods/ edits). BattlEye off / SP only.

## מסמכים קשורים
- באותה תיקייה: [[games/gtav/FEASIBILITY|FEASIBILITY]], [[games/gtav/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#gtav|CLAUDE_INDEX_games]]
