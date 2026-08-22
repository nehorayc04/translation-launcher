# GTA V (Legacy) — recon (on-disk facts)

Install: `F:\Games\Grand Theft Auto V Legacy` · GTA V **Legacy** v1.0.231.0 / build **3788**.
Verified live (workflow `wf_dbd4b5bc-79c`, 10 agents). `games.id = gtav`.

## Engine / container
- **RAGE** engine; archives = **RPF7** (`magic 0x52504637`/`7FPR`). Legacy edition (RPF8 = Enhanced, not here).
- **TOC** = AES-128-ECB, 16 rounds, public 32-byte GTA5 PC key (`B3 89 73 AF...`). **Files** = NG-encrypted (`flag 0x0fefffff`) or open. The NG key is one of 101 candidates chosen by `joaat(name)+length`; needs the bundled NG key tables (gtautil ships them; GenerateV2(GTA5.exe) only recovers the AES key — the NG LUT must come from a cache).

## Text = GXT2
- File magic `0x47585432` ("GXT2" LE; on disk reads as `2TXG`). Layout: `magic | u32 count | count×(u32 hash, u32 offset) | magic | u32 endPos(=filelen) | UTF-8 strings, NUL-terminated`. Offsets **absolute**. Entries **sorted ascending by hash**. **UTF-8** (not UTF-16).
- Key hash = **joaat (Jenkins one-at-a-time), seed 0, over the LOWERCASED label** (7/7 verified; uppercase fails). CodeWalker's raw `GenHash` does NOT lowercase — ours does.
- Codec `work/gtav_gxt2.py`: read/write **byte-identical** round-trip, 21/21 tests, `joaat('test')=0x3f75ccc1` ✓.

## Where the text lives (canonical set)
| File (inside RPFs) | Role | Count |
|---|---|---:|
| `x64b.rpf/data/lang/american_rel.rpf/global.gxt2` | **UI/HUD/menu spine** | **23,136** |
| `update/update.rpf/x64/data/lang/american_rel.rpf/global.gxt2` | update override (the live one) | — |
| `x64b.rpf/data/lang/american_rel.rpf/MISSION.gxt2` | story subtitles/dialogue | ~255k |
| `…/dlcpacks/<PACK>/dlc.rpf/x64/data/lang/americandlc.rpf/global.gxt2` | per-DLC (53 MP) | ~193k |
| `mods/update/update.rpf/…/american_rel.rpf/global.gxt2` | **deploy target** | — |
- 13 locales (`american/french/german/italian/spanish/portuguese/polish/russian/korean/japanese/mexican/chinese/chinesesimp`_rel.rpf), **all LTR**, no Arabic/Hebrew.

## bidi
- **VISUAL** (confirmed 0.9). No bidi in RAGE/Scaleform. Proven on disk: `menyooStuff/Language/Hebrew.json` is stored visual (`visual==reverse(logical)`, word-order reversed, Latin forward).

## Font (Scaleform GFx)
- `Menyoo_Hebrew_Font.oiv` (a prior agent's package) installs **Hebrew** `font_lib_efigs.gfx` + `font_lib_efigs_pc.gfx` (GFX8, 711,440 B, **27/27** Hebrew letters, atlas-based tag 1005) into `mods/update/update.rpf` → `x64/data/cdimages/scaleform_generic.rpf` + `scaleform_platform_pc.rpf`. **Already applied** (live mods/update/update.rpf, 2026-06-23 03:15).
- Covers HUD/subtitles/pause-menu/phone/map/general text. **Not yet Hebraized:** `gfxfontlib.gfx`, `font_lib_sc.gfx` (Social Club), `font_lib_heists/slots/taxi/typewriter/web.gfx` (niche surfaces).

## Deploy / activation / safety
- **OpenIV `mods/` override** — verified `{M}` in `OpenIV.log`. Edit `mods/update/update.rpf` only; real files pristine.
- ASI loader = `dinput8.dll` (Alexander Blade) → loads `OpenIV.asi`. Launch `GTA5.exe`.
- **No language change needed** (hijack American slot; text-lang lives in launcher's encrypted `%LOCALAPPDATA%\Rockstar Games\Launcher\`, not settings.xml).
- **BattlEye OFF** (`args.txt -nobattleye -noBE`), SP only; mods/ immune to Rockstar "Verify".

## Tooling on disk
- CodeWalker dev46 (GUI; `CodeWalker.Core.dll` reflectable headless but needs key-cache bootstrap), OpenIV.asi, ScriptHookV, Menyoo. **gtautil NOT installed** (needs download for headless repack).

## מסמכים קשורים
- באותה תיקייה: [[games/gtav/FEASIBILITY|FEASIBILITY]], [[games/gtav/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#gtav|CLAUDE_INDEX_games]]
