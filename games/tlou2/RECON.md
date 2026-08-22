# RECON — The Last of Us Part II Remastered (Hebrew) — Phase-1 groundwork

> **Status: Phase-1 groundwork DONE (2026-07-06), 🟢 GO — medium tier.** All OFFLINE gates
> closed (container read+write, loc codec, font, RTL, scope, deploy path); one in-game
> menu-proof pending the user. Verdict + full analysis in FEASIBILITY.md; recipe in PIPELINE.md.
> Everything below was read directly from the installed game (read-only, nothing modified).

## Install
- **Path:** `F:\Games\The Last of Us - Part II Remastered` (Steam AppId **2531310**, RUNE crack + Steam-emu, single-player).
- **Engine:** Naughty Dog engine (T3/"ND" lineage — same family as TLOU Part I PC + Uncharted 4/LoT PC). exe = `tlou-ii.exe` (+ `tlou-ii-l.exe` launcher variant).
- **Built-in mod loader:** `modloader.ini` → `[ModLoader] MountOrder= · ShowConsole=false · ModFolder=<...>\mods`. (The ini's ModFolder points at an `E:\...` path — stale; the game is on `F:\`. Note for deploy.)
- **games.id (Supabase) / detector key = `tlou2`** (already a coming-soon card on site+launcher since 2026-07-05). Detection exe pattern = `tlou-ii.exe`.

---

## ===== CONFIRMED LOCAL GROUND TRUTH (read from the install) =====

### Container format: DSAR → PSAR → .pak
- Data lives in `build\pc\main\*.psarc` (49 archives, ~81 GB). Outer magic = **`DSAR`** (`44 53 41 52`, version `03 00 01 00` = v3.1) — Naughty Dog's compressed container, **NOT** Sony's plain PSARC.
- DSAR header (16 B) + a bit-packed **block table** (recurring 24-byte-ish entries ending in the marker `03 54 55 55 55 55 55 55`) + `PADDING*` alignment.
- Inside DSAR blocks are **inner `PSAR` archives** (Sony PSARC, header `PSAR 00 01 00 04 "zlib"` = **v1.4, zlib compression**) whose entries are **`.pak`** files.
- `.pak` = Naughty Dog pak with sections `PAK_LOGIN_TABLE`, `RAW_DATA`, `TEXTURE_DICTIONARY`, `VRAM_DESC` (seen verbatim in `steam.psarc`).
- **Inner compression = zlib** (confirmed by the literal `zlib` tag) → far easier than Oodle/Kraken for a repack.
- `bin.psarc` (77 MB) holds scripts (`.bin`), `gui2`, `sfx`, `character` — NOT the localization text.

### Archive inventory (`build\pc\main\`)
- `common.psarc` (4.99 GB), `core.psarc` (2.78 GB), `sp-common.psarc` (21.3 GB), `bin.psarc` (77 MB), `shaders.psarc`, `steam.psarc` (475 B), + 30 `world-*.psarc` (per-level). `chunks.txt` maps chunk→index (common=0, epic=1, sp-common=2, steam=3, world-*=4+).
- Audio: `build\pc\main\speech1\english.psarc` (3.8 GB) + `english.xvag-index.json`. TTS accessibility: `tts1\{english,ukenglish,chinese,simpl-chinese}-{gameplay,menu}.psarc`.
- Movies: `movie1\*.bk2` (Bink2 — `bink2w64.dll` present).
- `remap.txt` (2.9 MB) = the **master hash→path table** (`<16-hex-hash> <virtual/path>`), the file registry the engine/mod-loader resolves against. This is the goldmine for the file layout.

### 🔑 Localization text — `text2/<lang>.<category>`
Virtual paths (from `remap.txt`): `text2/<lang>.common`, `text2/<lang>.subtitles`, `text2/<lang>.subtitles-systemic`, plus a shared `text2/sid-lookup` (string-id table). English source = `text2/eng.{common,subtitles,subtitles-systemic}`.
- **`.common`** ≈ UI/menus/system strings; **`.subtitles`** ≈ spoken dialogue; **`.subtitles-systemic`** ≈ systemic/bark/gameplay lines.
- On-disk format of these files = **NOT YET CRACKED** (a Naughty Dog localization binary; symbol `ss-localization-text-interact` seen). This is the core Phase-1 unknown → FEASIBILITY.

### ⚠️ NO Arabic locale — 26 LTR/CJK languages, ZERO RTL
Complete language set (`text2/` codes): **bra, chi, chs, cze, dan, dut, eng, fin, fre, ger, gre, hrv, hun, ita, jpn, kor, nor, pol, por, rus, sas, spa, swe, th, tur, uke.**
- `bra`=BR-Portuguese, `por`=PT-Portuguese, `spa`=ES-Spain, **`sas`=LATAM-Spanish** (title-card `sony-title_SAS.png`), `chi`=Trad-Chinese, `chs`=Simp-Chinese, `th`=Thai, `uke`=UK-English.
- **No `ara`/`ar`/Arabic. No Hebrew. No Farsi/Urdu. No RTL language of any kind.**
- ⇒ The project's usual **Arabic-slot hijack does NOT apply.** This is the **AC2 / Anno 1800 class**: hijack an **LTR slot** and handle RTL ourselves (**VISUAL** storage — pending menu-proof; the ND engine almost certainly has no bidi since it never shipped an RTL locale).
- **False positive avoided:** `*-rtl-only*.pak` entries are **level-lighting variants** (`-ingame`/`-phys` siblings), NOT right-to-left.

### Fonts — OTF/TTF in `fonts/`, none cover Hebrew
`remap.txt` `fonts/`: `seriffont-Regular.otf`, `seriffont-Medium.otf` (main UI/subtitle serif), `SIE-UtrilloPro-DB.otf`, `SIE-UtrilloPro_Everest-DB.otf` (Sony Utrillo Pro), `SSTThai-{Light,Medium}-PUA.otf`, `HelveticaNeueBold.ttf`, `asianfont-R.ttf` + `HeiSASC-Medium_0.ttf` (CJK), `firmware-V-SONY.ttf` (button glyphs), `debug.ttf`/`devonly.ttf`.
- All **OTF/TTF** (not atlas/CR2W) → Hebrew injection is the **easy** class (fontTools, like Anno 1800), IF injection is even needed.
- **None ship Hebrew glyphs** (Latin/CJK/Thai only) → injection almost certainly required into whichever font the hijacked slot renders with (likely `seriffont-*.otf`). To confirm which font + whether any covers U+05D0–05EA: cmap-check after extraction.
- Fonts are **packed inside a psarc** (virtual `fonts/` path), not loose on disk → deploy depends on the mod-loader override path.

### DRM / anti-cheat
- Single-player, RUNE-cracked + Steam-emu. No EAC/BattlEye. (Denuvo, if any, is on the exe — irrelevant to asset mods, and this copy is cracked anyway.) → No anti-tamper block for modded/mounted archives expected.

---

## Phase-1 gates — RESOLUTION (see FEASIBILITY.md)
1. **`text2/*` format** — ✅ **ND loc-v2**, identical to Part I; `tools/tlou_loc.py` decodes/encodes all
   `eng.*` with roundtrip=True. `sid-lookup` = the SID table (SID shared across languages).
2. **Extract + REPACK** — ✅ built pure-Python: `tools/dsar.py` (DSAR/LZ4→PSARC/zlib reader, validated on
   bin/common/core) + `tools/psarc_write.py` (plain-zlib override builder, round-trip byte-identical).
   External backups exist (ndarc, UnPSARC-open-source, NaughtyDogLocalizationTool).
3. **Deploy via mod loader** — ✅ **ndmodloader** mounts a small override `.psarc` from `mods\` above
   `core.psarc` — NO 2.8 GB repack. Plain PSARC (no DSAR) is accepted (source-confirmed). ⚠️ ndmodloader
   binary NOT yet installed here (only `modloader.ini`; user installs Nexus mod #32 + fixes the stale
   `E:\` ModFolder).
4. **bidi mode** — 🟡 VISUAL expected (same ND engine as Part I, which confirmed VISUAL) → menu-proof decides.
5. **Slot to hijack** — ✅ **English** (`text2/eng.*`) — simplest activation.
6. **Scope** — ✅ eng.common 12,781 + eng.subtitles 21,266 + eng.subtitles-systemic 9,739 ≈ **43,786 unique**.

## Tools present / built
- Python 3.13 + `zlib` + `lz4` + `fontTools` (verified). Vendored: `tools/dsar.py`, `tools/psarc_write.py`,
  `tools/tlou_loc.py`, `tools/oodle.py`; `work/tlou_rtl.py`, `work/tlou_font.py`, `work/build_menu_proof.py` + Heebo fonts.
- Extracted (read-only): `extract/{eng.common,eng.subtitles,eng.subtitles-systemic,sid-lookup}` + `extract/fonts/`.

## מסמכים קשורים
- באותה תיקייה: [[games/tlou2/FEASIBILITY|FEASIBILITY]], [[games/tlou2/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou2|CLAUDE_INDEX_games]]
