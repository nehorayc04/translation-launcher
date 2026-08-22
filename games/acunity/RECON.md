# Assassin's Creed Unity — Hebrew translation RECON

Concrete, **locally-verified** findings (2026-07-01). Game install:
`E:\Games\Assassin's Creed Unity` (Ubisoft Montreal, 2014 PC, **AnvilNext 2.0**, Uplay/Ubisoft
Connect). Everything below was proven by directly reading the real game files with
`tools/acu_forge.py` — no game file has been modified (read-only recon).

> **Research update (2026-07-01, see `BRIEF.md`).** Three items were resolved/corrected since the
> original recon: **(1) codec = LZO CONFIRMED** (mode byte 0/1→lzo1x, 2→lzo2a, 5→lzo1c; no Oodle).
> **(2) Font = native AnvilNext DDS-atlas + `.ffd`, NOT Scaleform** (§3 corrected below).
> **(3) Bidi default → VISUAL, not logical** (Unity-era Anvil had no engine RTL; §2 flag below).
> Repacker = **AnvilToolkit** (free, Unity-supported).

> AC Unity sits **between** the two Ubisoft Anvil titles already in this repo:
> **AC2** (2009, scimitar **v25**, no Arabic, char-index loc, DDS atlas fonts) and
> **AC Shadows** (2025, scimitar **v42**, Oodle, real Arabic, TTF-with-Hebrew).
> Unity = scimitar **v27**, **HAS an Arabic locale**, char-index loc, `.ffd`+DDS-atlas fonts (WD2 model), no engine bidi → VISUAL.

---

## 1. Engine / archive format — `scimitar` v27

Header of every `.forge`: `b"scimitar"` + `\x00` + `u32 version = 27` (AC2=25, ACS=42).
`DataPC.forge` = 312 MB, **1620 resources**. There are ~70 forges: a shared `DataPC.forge`
+ `DataPC_extra.forge` + region bundles (`Paris`, `Versailles`, `Prologue`, `LGS_*` (Helix
missions: Medieval/BelleEpoque/WorldWar2), `RebirthRitual`, `TitleScreenFPP`, `SharedGroup_*`)
each with `_gi`/`_assets`/`_patch_0N` siblings, plus `dlc_10`/`dlc_11`.

### Container layout (cracked + reader built — `tools/acu_forge.py`)
```
Header @0x00:  "scimitar"\0 · u32 version(27) · i64 index_offset (@ file offset 13)
Index @index_offset (0x41a in DataPC.forge):
    u32 file_count (@+0)           = 1620
    ... small linked-chunk preamble (0x70 bytes) ...
Record array @ index_offset + 0x70, file_count × 20 bytes:
    u64 data_offset  ·  u32 file_id  ·  u32 flags  ·  u32 uncompressed_size
    (records are contiguous → on-disk size = next_offset - this_offset; last = terminator off=0)
Descriptor table @ record_array_end, FIXED 0xC0 (192) byte entries:
    +0x20 u32 record_index   ·   +0x2b char name[] ('T'-prefixed, null-terminated)
    descriptor[0] = "TGlobalMetaFile" (index field 0xFFFFFFFF, a header, not a data record)
```
`tools/acu_forge.py list|names|extract <Name> <out>` — **verified: extracts any resource by
name** (records carry PLAINTEXT names, unlike ACS's pure-hash TOC → we find loc/fonts by name).

### Resource sub-container — Anvil "DataFile" chunks
Every resource blob is a chain of chunks each starting with `u32 0x57FBAA33` + `u32 0x1004FA99`
(the SAME chunk magic as AC2 v25 and AC Shadows v42 — one Anvil family). A chunk header carries
compressed/uncompressed sizes; payload is stored **or** compressed. **The loc packages are STORED
(on-disk size == uncompressed_size)** → the char-index text is directly readable with no codec.
**Codec for *compressed* chunks (fonts/textures) = LZO — CONFIRMED (research 2026-07-01):** a
compressed blob starts `0x57FBAA33`/`0x1004FA99`, then `…u8 compression_type…u8 format_version`;
`compression_type` selects the LZO variant (0/1→`lzo1x`, 2→`lzo2a`, 5→`lzo1c`), Oodle NOT used at
the Unity generation. `format_version` 0 (u32 size pairs) vs 128 (u16 pairs, u32 block count),
each block prefixed by a 4-byte hash. Source: ACExplorer `pyUbiForge/misc/decompress_.py` +
Blacksmith CHANGELOG. Re-compress via `liblzo2 lzo1x_1_compress`. (See `BRIEF.md` §1.)

## 2. Where the text is — `DataPC.forge` `TLocalizationPackage_<Lang>`

Same family as AC2. Per-language resources (record index in brackets, verified):
- `TLocalizationPackage_<Lang>`            — UI / menu / item / document text
- `TLocalizationPackage_<Lang>_Subtitles`  — dialogue subtitles
- `TLocalizationPackage_<Lang>_EManual`    — electronic manual

**24 shipped text languages** (from the descriptor table + `Support/Readme/<Lang>/`):
English(US), French(France), Spanish(Spain), Spanish(Mexican), Italian, German, Dutch, Polish,
Czech, Hungarian, Danish, Norwegian, Swedish, Finnish, Portuguese, Portuguese(Brazil)/Brazil,
Russian, Korean, Japanese, Chinese(PRC), Chinese(Trad), **Arabic**, LocTest.

### 🟢 DECISIVE — AC Unity ships an **Arabic** text locale
`TLocalizationPackage_Arabic` [1593], `TLocalizationPackage_Arabic_Subtitles` [1594],
`TLocalizationPackage_Arabic_EManual` [1599] all exist, and `Support/Readme/Arabic/Readme.txt`
is shipped. So the project's **Arabic-slot hijack applies** (unlike AC2, which had zero Arabic
and forced an LTR-slot + visual hack). Arabic is an official MENA text locale on this SKU.

### ⚠️ Wrinkle — Arabic is **subtitle-populated, UI-stub**
Real sizes (all STORED / uncompressed):
| resource | record | bytes |
|---|---|---|
| `Arabic_Subtitles` | 1594 | **204,002** (real) |
| `Arabic` (UI) | 1593 | **139** (empty stub) |
| `English` (UI) | 1527 | 345,123 |
| `English_Subtitles` | 1519 | 466,415 |

→ Ubisoft shipped Arabic as **Arabic subtitles + English menus** (a common MENA config). The
Arabic locale is **official** (added by Ubisoft's MENA distributor "Red"; a real retail
"Arabic Subtitles" SKU) → the slot is genuine and selectable (in-game Options / `localization.lang`
/ `HKCU\…\Language`).

> ⚠️ **BIDI — store Hebrew VISUAL, not logical (CORRECTED, research 2026-07-01).** The earlier
> "subtitles inherit RTL for free, store LOGICAL" assumption is overturned: peer-reviewed studies
> (Al-Batineh 2024/2021) document that the **Unity-era AnvilNext engine had NO native RTL/bidi**
> (RTL was added only in Valhalla 2020 / Mirage 2023). Unity's shipped Arabic renders correctly
> because the **order was pre-baked into the DATA** — so Hebrew must likewise be stored **VISUAL
> (pre-reversed via `visual_line`)**, the AC2/WD2 method, for BOTH surfaces. Confidence MODERATE →
> **prove with a one-line menu/subtitle test** (VISUAL correct + LOGICAL mirrored ⇒ VISUAL). The
> UI/menu path still needs the populate-Arabic-UI-stub vs hijack-English-slot decision, but in
> either case store VISUAL. (See `BRIEF.md` §2.) Repacker for the write = **AnvilToolkit** (free,
> XML export/import of the LocalizationPackage — hides the char-index encode for v1).

### Loc text format = **char-INDEX** (AC2-class, not flat UTF-16)
Extracted `TLocalizationPackage_English` (345 KB) and `_Arabic` (139 B). After the DataFile chunk
header the payload is a **u16 char-index serialization**: a per-package sorted unique-char
dictionary + strings encoded as index sequences (control code `0x8000` seen; the Arabic package's
dictionary is the sorted Arabic block `U+0600–06FF`). This is the exact machinery AC2's `FORMAT.md`
describes ("byte/word codes indexing a sorted unique-char dict"). To put Hebrew in, rebuild the
dictionary with Hebrew codepoints `U+05D0–05EA` + re-encode strings → the **loc encode gate**.

`extract/loc_english.bin` + `extract/loc_arabic.bin` are the working read-side artifacts.

## 3. Where the font is — native AnvilNext **DDS-atlas + `.ffd`** (CORRECTED — NOT Scaleform)

> ⚠️ **CORRECTED (research 2026-07-01).** The earlier "Unity UI = Scaleform (GFx/FTX) + embedded
> TTF" read is overturned. AC Unity UI is **native AnvilNext 2.0** with the same **per-script DDS
> bitmap glyph-atlas + `.ffd` (Fire_Font_Descriptor)** font pipeline as AC2/SM2/WD2 — **not**
> Scaleform, **not** a `.gfx`/TTF swap. CONFIRMED facts: "Fonts are DDS, not TTF" (ZenHAX +
> AnvilToolkit wiki); fonts are **per-script atlases** named `..._<Script>_1_MapDesc.data`;
> they live in the **`extra` forge** (`DataPC_extra_*.forge`, e.g. `DataPC_extra_chr.forge`),
> while text lives in `DataPC.forge`. The shipped default font does **NOT** cover Hebrew — the
> Unity English-loc guide states Arabic "uses a different font, so all symbols will be blank (same
> as Chinese)"; Hebrew (`U+05D0–05EA`) with no atlas renders **blank** → **must inject**.
> (The `FTX`/`FontManager`/embedded-TTF strings observed in `DataPC_patch_01.forge` are the
> font-resource contents, not a Scaleform renderer.)

**Injection plan = DDS atlas + `.ffd` descriptor, edited together** (`FFDConverter` template —
`*.ffd` holds glyph metrics + codepoint→atlas mapping, the DDS holds the bitmaps; both updated).
Draw Hebrew glyphs from Frank Ruehl/David into the Arabic/subtitle atlas + add the `.ffd` entries;
**preserve the atlas's exact DDS PixelFormat** (don't naïvely re-encode the header — WD2/GoWR
lesson); watch the **off-by-one glyph-table** trap (GoWR/SM2). ⚠️ **FFDConverter's AC support stops
at AC Rogue** (issue #2) → the v27 `.ffd` reader may need adapting (like our AC2 work). First
step: dump a Unity font resource from the `extra` forge and confirm the `.ffd`/`MapDesc` presence
(settles the last Scaleform-vs-DDS ambiguity in minutes). (See `BRIEF.md` §3.)

## 4. Language selection + activation

- `ACU.ini` (`Documents\Assassin's Creed Unity\`) has **no `[Language]` key** → text language is
  set by the **Uplay/Ubisoft Connect account language** and/or the 14-byte root **`localization.lang`**
  stamp (`b"LANG"` + `u32 1` + two u32 hashes) — not by an obvious in-game field. Confirming the
  exact "force Arabic text, keep English voice" path is a research/in-game item.
- VO packs present: `sounds_{eng,fre,ger,ita,spa,jap,mex,bra,rus}.pck` (no Arabic VO) → Arabic is a
  **text-only** locale, so text ↔ voice are independent (English voice stays).

## 5. Protection / deploy surface

- DRM = **Uplay/Ubisoft Connect + VMProtect** on `ACU.exe`; **no Denuvo** (Unity predates it).
  VMProtect wraps the **code**, not the `.forge` assets. Asset forges are **NOT integrity-checked
  at load** (CONFIRMED): the runtime **Asset-Overrides** loader (`NameTaken3125/AssetOverrides-ACUnity`
  via ACUFixes) parses replacement bytes with **zero content/hash validation** — a wrong datapack
  just crashes, it isn't rejected as tampered. Large texture/mesh/tweak modding scene ⇒ modded
  forges load.
- ⚠️ **DEPLOY RISK — Ubisoft Connect file-integrity check (CONFIRMED).** Newer Connect builds run a
  **strict integrity check on `DataPC.forge`** and can **demand an "Activation Key" after a forge
  overwrite** (region-dependent, heavy on CIS/RU). This is a *deploy* issue, not a repack failure.
  **Mitigations:** (a) the **runtime Asset-Overrides loader** — on-disk forge stays vanilla →
  Connect/Verify-Files see no changed game file (the clean, verify-proof path); (b) offline launch;
  (c) a build/region without the check; (d) `localization.lang`+in-game-select if the slot is
  selectable without a forge swap. **Steam/Ubisoft "Verify Files" ALWAYS reverts an overwritten
  forge** (re-downloads the diff) → keep the backup + re-apply, or use the runtime loader.
- Two deploy paths: **(A) whole-forge overwrite** (back up `DataPC.forge` + `DataPC_10_dlc.forge`
  for DLC text + `DataPC_extra_*.forge` for the font, replace, select the slot) — the community
  English-loc pattern; **(B) runtime override** via ACUFixes PluginLoader (no repack, vanilla forge
  on disk). AnvilNext also uses numbered patch forges (`…_patch_0N.forge`, higher wins). Backup any
  forge before writing; deploy to the neutral install (`E:\Games\...`), never overwrite without a
  backup. `revert` = restore the backup forge (or remove the plugin).

## 6. No prior Hebrew AC; Arabic slot is the precedent

No Hebrew AC translation has ever existed. Unlike AC2 (which leaned on Persian/Arabic fan patches
for LTR precedent), Unity ships a **real Arabic locale** — the RTL pipeline is Ubisoft-tested. This
is the strongest starting position of any AC in this repo.

## מסמכים קשורים
- באותה תיקייה: [[games/acunity/BRIEF|BRIEF]], [[games/acunity/FEASIBILITY|FEASIBILITY]], [[games/acunity/PIPELINE|PIPELINE]], [[games/acunity/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acunity|CLAUDE_INDEX_games]]
