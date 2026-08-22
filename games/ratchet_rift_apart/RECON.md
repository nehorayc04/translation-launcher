# Ratchet & Clank: Rift Apart — RECON (Phase-1 groundwork)

**Date:** 2026-07-12 · **Verdict:** 🟢 GO (medium tier) · **games.id:** `ratchet-rift-apart`
**Install:** `F:\Game Lab\Ratchet & Clank - Rift Apart` (Steam appid **1895880**, Nixxes 2023 PC port)

## TL;DR
Insomniac engine — the **SAME container + text + font + applier stack as Marvel's Spider-Man 2**,
already fully cracked in this repo. The one real difference: **R&C ships NO Arabic text locale**
(0 Arabic/0 Hebrew codepoints across all 32 language variants) → this is the **LTR-slot hijack**
class (like TLOU2/AC2/GTA), not the Arabic-slot hijack. Container read + DAT1 repack + the native
toc-redirect applier are all **verified reusable from SM2 this session**. Remaining gates: Hebrew
**font injection** (Proxima Nova, injection required) and the **bidi mode** (LOGICAL vs VISUAL —
decided by an in-game menu-proof, not assumed).

## Engine / container — VERIFIED (dat1lib reads it)
- `toc` magic `35 90 E8 34` = **`0x34E89035` = TOC2 / I29**, then `1TAD` (DAT1). dat1lib parses it as
  class **TOC2, version 202300 == `VERSION_RCRA`** — the exact same branch Spider-Man 2 uses.
- **147 archives, 340,665 assets, 256 spans.** UI = **cohtml / Coherent GameFace**
  (`cohtml.WindowsDesktop.dll`, `RenoirCore.WindowsDesktop.dll`, `v8*.dll` present) — same UI stack as SM2.
- `d/` holds the data archives (`d\localization`, `d\conduit`, `d\userinterface`, `d\tex_ui`, `d\config`, …).
  dat1lib prints a benign `"Actual decompressed size … isn't equal"` warning on read — **harmless**, the toc
  parses fully with consistent 340,665-asset counts.

## Text — VERIFIED
- Asset path **`localization/localization_all.localization`**, aid **`0xBE55D94F171BF8DE`** (crc64 of the path),
  **32 variants** (one language per span; variant *N* → span *N*×8: spans 0, 8, 16 … 248). All 32 share the one aid.
- Inner layout **structurally IDENTICAL to SM2**: 36-byte asset header + DAT1 (`1TAD`), **9 sections**, same tags:
  `VALUES=0x70A382B8 · KEYS=0x4D73CEBD · TEXT_OFFSETS=0xF80DEEB4 · KEY_OFFSETS=0xA4EA55B2 · ENTRY_COUNT=0xD540A903`
  (+ 4 shared metadata/charset sections + a 4-byte flag). **entry_count = 24,575.**
- **Subtitle discriminator = the `<ts="a;b">` timing tag** (identical Insomniac marker to SM2): any value carrying
  it is a timed spoken VO/cutscene line. UI = zero-`ts` keyed labels.

### Scope (Playbook Stage 7 — UI vs subtitles counted separately)
| Bucket | Count | Notes |
|---|--:|---|
| **UI** | **7,521** | CREDITS(3,595→2,506 on-screen credit names, low priority) · CARD · MENU · STICKER · OBJ · WEAPON · COL · TUT · ARMOR · NAME · PHOTO · HELP |
| **Subtitles** | **10,033** | `<ts>`-tagged VO: RIVE=Rivet · RATC=Ratchet · CLANK · KIT · NEFT1-4=Nefarious troopers · PIR1-4=pirates · T4L1-4 · vendor/civilian VO |
| **Skip** | **7,021** | empty English (barks/animatics w/ no subtitle text — INV & PLAY prefixes 100% empty) + symbol/number/dev tokens |
| **Translatable total** | **17,554** | (matches the ~18,188 non-empty estimate; delta = symbol/number-only → skip) |

## Languages — the decisive difference: NO ARABIC
- **0 Arabic (U+0600–06FF) and 0 Hebrew (U+0590–05FF) codepoints in ALL 32 variants** (full decode, both UTF
  alignments — adversarially verified). Only one toc / one `d\localization` — no DLC/patch loc tree.
- An **Arabic AUDIO/dev-enum** slot exists in the framework (`wem.ar`/`soundbank.ar`, an ADR dub enum) but ships
  **no renderable text** (only `.us` audio on disk). Hebrew is entirely absent.
- ⇒ **LTR-slot hijack** (there is no Arabic text variant to reuse). Full variant→language map in FEASIBILITY.md.
- **English source = variant_00 (en-US).** English occupies 4 slots: v0≡v1 (en-US), v2≡v18 (en-GB).

## Font — injection REQUIRED (adversarially verified 0/27 Hebrew)
- UI **and** subtitle font = **Proxima Nova** Regular (aid `0xA2197874D2B7B1AC`) + Bold (`0xB5F411285669C55D`),
  both in **archive 109 = `d\userinterface`**, path `ui/loaded/authored/_common/fonts/proximanova_*_normal.ttf`.
- **CLEAN sfnt TTF at offset 0** (head `00 01 00 00`, `dsize==size`, **no wrapper** — even simpler than SM2's
  8-byte-prefix variant). All 10 shipped fonts (Proxima Nova + Sony PS font + CJK/JP/KR) = **0/27 Hebrew, 0 Arabic**.
- `configs/uiconfig/uifontmap.config` = per-language `FontsToReplace` map (proximanova→CJK/JP/KR; **no Hebrew slot**).
- Mechanism = same class SM2/GoWR/Anno/W3 solved: fontTools glyph-merge Hebrew into Proxima Nova, extend cmap
  (format 4/12), keep name/Latin intact. (Optional secondary lever: add a Hebrew `FontsToReplace` entry — but
  direct injection is the proven path.)

## Repack + deploy — VERIFIED reusable AS-IS
- **DAT1 identity round-trip = SEMANTIC-PASS** (0/24,575 key/value mismatch on re-parse; not byte-identical, same
  proven-in-game pattern as SM2/TLOU2), and a 1-string Hebrew patch reads back correctly.
- **`translation_manager/spiderman2_mod.py` applies to R&C AS-IS** (adversarially verified, NO applier changes):
  `get_spans_section()`=256 · `get_assets_section().ids`=340,665 · `get_sizes_section()` TAG `0x65BCF461`, 340,665
  RCRA 16-byte entries `<IIIi>` {value,archive_index,offset,header_offset} · `get_archives_section()` TAG `0x398ABFF0`,
  147 archives, 40-byte filename, 66-byte `<QQIHI>` tail. `_find_size_index(span=0, aid)` → index **87375**; live
  size-entry = `{archive_index=67 (d\localization), offset=0, value=2249335, header_offset=3123756}` (value == filesize−36).
- Deploy = write rebuilt DAT1 (header stripped) to `d\mods\tm_he_0` + append archive entry + redirect the hijacked
  variant's size-entry. Backup `toc.tm_he_backup`; revert restores. **No big archive repacked. No Overstrike.**

## DRM / anti-cheat / precedent — GREEN
- **No Denuvo** (Nixxes PC port shipped without it), **no EAC/BattlEye** (single-player). Steam build
  (steam_api64 + steamclient64; may be Goldberg-emu — asset mods load identically either way).
- **Overstrike** + **dat1lib/ALERT** + the **Insomniac Modding Tool** all support R&C Rift Apart.
- **Translation precedent:** R&C "Localization Tool" (Nexus RA mod 37), Dualsub (mod 50), akintos' SpidermanLocalizationTool.
- **RTL precedent on this engine:** an **Arabic localization mod for Spider-Man Remastered PC** (Nexus mod 361) —
  proves RTL text is achievable on the Insomniac DAT1/`.localization` engine.

## Probes (games/ratchet_rift_apart/work/, read-only)
`01_probe.py` (toc + variants) · `02_sections.py` (DAT1 sections) · `03_identify_langs.py` (language ID) ·
`04_roundtrip.py` (DAT1 identity round-trip + Hebrew patch) · `10_counts_ui_vs_subtitle.py` (+ `.json`) ·
`10_applier_probe.py` · `10_font_probe.py` / `11_extract_ui_scan_fonts.py` / `12_locate_fonts_coverage.py`.

## מסמכים קשורים
- באותה תיקייה: [[games/ratchet_rift_apart/FEASIBILITY|FEASIBILITY]], [[games/ratchet_rift_apart/PIPELINE|PIPELINE]], [[games/ratchet_rift_apart/PUBLISH|PUBLISH]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ratchet_rift_apart|CLAUDE_INDEX_games]]
