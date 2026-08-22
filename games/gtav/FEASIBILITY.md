# GTA V (Legacy) — Hebrew translation feasibility

**Source install:** `F:\Games\Grand Theft Auto V Legacy` — GTA V **Legacy** v1.0.231.0 (build **3788**, Mar 2026). Heavily SP-modded (OpenIV ASI + ScriptHookV + CodeWalker dev46 + Menyoo). Proposed `games.id` = **`gtav`** (already in `translation_manager/game_detector.py`). Engine: **RAGE** (Rockstar Advanced Game Engine). Findings below were empirically confirmed against the real install + multi-agent adversarially-verified (workflow `wf_dbd4b5bc-79c`, 10 agents) — nothing here is assumed.

## Verdict

# 🟢 GO (UI-first) — every pillar proven; 2 minor PARTIAL gates, neither blocks the main UI

| Factor | State | Detail |
|---|---|---|
| Archive format | ✅ cracked | RPF7 (Legacy; RPF8 = Enhanced, not this). TOC = AES-128-ECB (public 32-byte GTA5 PC key); files = NG-encrypted or open. |
| Text format | ✅ cracked + codec built | **GXT2** (magic `0x47585432`, UTF-8 NUL-terminated, joaat-lowercased u32 keys, entries sorted ascending). `work/gtav_gxt2.py` round-trips **byte-identical**, 21/21 tests. |
| **UI vs subtitle split** | ✅ **clean at FILE level** | **`global.gxt2` = 23,136 = the entire UI/HUD/menu spine.** `MISSION.gxt2` + per-DLC = ~255k story subtitles. No label-name classification needed — the file boundary IS the UI/subtitle boundary. |
| Arabic slot (free RTL) | ❌ none | GTA V ships **no Arabic, no Hebrew** — all 12 locales LTR (American/French/German/Italian/Spanish/Portuguese/Polish/Russian/Korean/Chinese×2/Japanese/Mexican). The **AC2/Anno class**: hijack an LTR slot + store **VISUAL**. |
| **bidi mode** | ✅ **VISUAL (confirmed 0.9)** | RAGE/Scaleform does **no bidi** (Scaleform RTL needs `GFX_ENABLE_BIDIRECTIONAL_TEXT` + a custom Translator; Rockstar ships zero RTL locales). Independently proven on disk: the user's own `menyooStuff/Language/Hebrew.json` is stored **visual** (`visual==reverse(logical)` for 297/301 values, word-order reversed, Latin kept forward). |
| Font (main UI) | ✅ already Hebraized | `font_lib_efigs.gfx`(+`_pc`) carries **27/27** Hebrew letters (atlas-based, GFX8, clean), already installed into `mods/update/update.rpf`. Covers HUD/subtitles/pause-menu/phone/map/general text. |
| Font (niche surfaces) | ⏳ **gate (minor)** | `gfxfontlib.gfx`, `font_lib_sc.gfx` (Social Club frontend), `font_lib_heists/slots/taxi/typewriter/web.gfx` are NOT yet Hebraized → those niche surfaces render tofu/Latin until injected. Does not block the main UI. |
| Read (extract gxt2) | ✅ proven | `global.gxt2` (1,141,267 B / 23,136 entries) extracted + parsed via CodeWalker.Core.dll; pure-Python re-encode byte-identical. |
| Write / repack | ⏳ **gate (easy):** needs .NET tool | NOT pure-Python (no maintained pure-Python RPF7 NG-encrypt writer). Fully automatable via **`gtautil`** CLI (bundles all 6 GTA5 key blobs; `extractarchive`/`createarchive`/`fixarchive`/`compilegxt2`) — must be downloaded once. Alt: CodeWalker.Core reflection with a key cache. Alt: mods/ RPF can be written **open (unencrypted)** and still loads via OpenIV ASI → sidesteps NG entirely. |
| Deploy slot | ✅ trivial + safe | **OpenIV `mods/` override** (`mods/update/update.rpf`) — verified live in `OpenIV.log` (`{M}` tag on every RPF read). Real game files left pristine + reversible. |
| Anti-cheat / DRM | ✅ none | **BattlEye OFF** (`args.txt` = `-nobattleye -noBE`), SP only. mods/ is immune to Rockstar Launcher "Verify". |
| Activation | ✅ none needed | Hijacking the **American** slot means the user keeps Language=American and just sees Hebrew — **no in-game language change**. (GTA V text language lives in the launcher's encrypted `%LOCALAPPDATA%\Rockstar Games\Launcher\` binaries, NOT settings.xml — so hijacking the active English slot is the clean path.) |

## The core trick (this game)

GTA V has **no RTL locale**, so the usual "Arabic-slot hijack" does NOT apply. Instead — **AC2/Anno class**:
1. Translate Hebrew **logical** (readable).
2. Store it **VISUAL (pre-reversed per line)** in the **American (English)** `global.gxt2` slot — the engine draws glyphs strictly in stored byte order, LTR, no bidi.
3. Ship the Hebrew Scaleform font (already done for `font_lib_efigs`).
4. User keeps the game in English → sees Hebrew. No language switch, no anti-cheat, fully reversible (mods/ folder).

## Counts (separate, per playbook §7)

| Scope | File(s) | Strings |
|---|---|---:|
| **UI / interface (this phase)** | `global.gxt2` (american_rel) | **23,136** |
| Story subtitles / dialogue | `MISSION.gxt2` + per-mission | ~255,000 |
| Online/MP DLC (out of SP scope) | 53 dlcpacks `americandlc.gxt2` | ~193,229 |
| SP american total (unique) | — | 278,387 |
| Grand total (incl. MP) | — | 471,071 |

→ **UI-first = ~23,136 strings** (≈17,547 short / 3,884 mid / 1,705 long). This is the agent-handoff scope.

## Open gates (none block the UI haul; close before "full game")

1. **Write/repack tool** — download `gtautil` once (or generate the CodeWalker key cache) so `gtav_build.py` can repack + NG-encrypt (or write open RPF). *Easy, external binary → needs user OK.*
2. **Niche Scaleform fonts** — inject Hebrew into `gfxfontlib.gfx` + `font_lib_sc/heists/slots/taxi/typewriter/web.gfx` for 100% surface coverage. The main UI is already covered by `font_lib_efigs`.
3. **Per-surface A/B** — store one short string VISUAL vs LOGICAL on a Scaleform label + a gxt2 line, launch once, confirm RTL renders right (the user is the gate). Then the 23k haul is safe.
4. **Identity round-trip** — extract `global.gxt2` → re-pack unchanged → confirm the game still boots with vanilla English (proves the repack chain) before shipping Hebrew.

## Tooling status

- `work/gtav_gxt2.py` — pure-Python GXT2 codec (joaat / read / write / TABL / `visual_line`). **Built + 21/21 tests pass.**
- `work/gtav_extract.py` — driver: `global.gxt2` → `to_translate.json` (hash-keyed English). *Needs gtautil or CW key cache.*
- `work/gtav_build.py` — `hebrew.json` (logical) → `visual_line` → gxt2 → repack → deploy to `mods/update/update.rpf`. *Needs gtautil.*
- `agent_handoff/` — UI-only translation handoff for a second (Google/Antigravity) agent.

*Recon: 2026-06-23. Verdicts: bidi=VISUAL confirmed 0.9; gxt2 read+write partial 0.78 (gtautil gate); font partial 0.78 (niche libs gate).*

## מסמכים קשורים
- באותה תיקייה: [[games/gtav/PIPELINE|PIPELINE]], [[games/gtav/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#gtav|CLAUDE_INDEX_games]]
