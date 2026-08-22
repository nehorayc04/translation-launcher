# Marvel's Spider-Man Remastered — RECON

## Install

- `D:\Games\Spider-man Remastered` (FLT crack; exe `Spider-Man.exe`, 121,325,496 B,
  built 2022-08-12; `flt.ini` reports `AppId=1817070, BuildId=9304506`).
- Data lives in `asset_archive/` — `toc` (10,707,684 B, one index for the whole
  game) + 34 game archives `g00s000..g00s033` (~2 GB each) + 12 per-language voice
  archives `a00sXXX.<lang>` (only `.us` = English is installed on disk — a
  selective English-only install; the toc still declares all 12).
- Detector key + Supabase `games.id` = **`spiderman`** (already exists, already
  detected by all three detection paths, artwork already uploaded — see the
  Catalog section below). Not `spiderman2` (a different, already-shipping title).

## Engine

Insomniac "Luna" — same family already cracked in this repo for **Spider-Man 2**
(RCRA/TOC2) and **Ratchet & Clank Rift Apart**. MSMR predates both and is on the
**older MSMR container generation** (`dat1lib.VERSION_MSMR = 202200`), and its UI
is **Scaleform GFx** (SM2/R&C moved to cohtml — MSMR does not; confirmed by
scanning the exe: `cohtml`=0, `Coherent`=11 stray hits, `Scaleform`=167, `.gfx`=82,
`.swf`=10).

## Container — `toc`

```
[u32 magic 0x77AF12AF][u32 decompressed_len][zlib DAT1 '1TAD' ...]
```

Inner DAT1, 6 sections (all confirmed against the live file, `771,670` assets):

| tag | name | entry size | count |
|---|---|---|---|
| `0xEDE8ADA9` | Spans | 8 B `<II>` asset_index,count | 256 |
| `0x506D7B8A` | AssetIds | 8 B `<Q>` crc64(path) | 771,670 |
| `0x6D921D7B` | KeyAssets | 8 B | 12,163 |
| `0x65BCF461` | Sizes | 12 B `<III>` always1,value,index | 771,670 |
| `0xDCD720B5` | Offsets | 8 B `<II>` archive_index,offset | 771,670 |
| `0x398ABFF0` | Archives | 72 B `<II>`+char[64] bucket,chunkmap,filename | 46 |

An asset's location is split across TWO parallel sections (Sizes.value = size,
Offsets.{archive_index,offset} = where) — different from SM2/R&C's single 16-byte
`RcraSizeEntry`. `dat1lib` (vendored at `games/spiderman2/tools/ALERT`) reads and
writes MSMR natively with `RECALCULATE_ORIGINAL_ORDER` — no custom serializers
needed (unlike RCRA).

**The variant→span map is NOT arithmetic.** MSMR's 23 localization variants sit at
spans `0, 8, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 144, 152,
168, 184, 200, 208, 216` — R&C's "variant N -> span N×8" rule breaks here (16, 136,
160, 176, 192 are skipped). Resolve every span by scanning, never by formula.

## Text format — `localization/localization_all.localization`

One asset id (`crc64` = `0xBE55D94F171BF8DE`), **23 language VARIANTS** selected by
span. Each variant = `[36-byte asset header][DAT1]`, and the inner DAT1 is
**byte-for-byte the same 5-tag layout as Ratchet & Clank Rift Apart**:

| tag | role |
|---|---|
| `0xD540A903` | ENTRY_COUNT, u32 (57,368) |
| `0x4D73CEBD` | KEYS, NUL-separated UTF-8 (identical across every variant) |
| `0xA4EA55B2` | KEY_OFFSETS, u32 x N |
| `0x70A382B8` | VALUES, NUL-separated UTF-8 (per-language) |
| `0xF80DEEB4` | TEXT_OFFSETS, u32 x N |

Codec: `games/spiderman_remastered/tools/msmr_loc.py` — identity round-trip
**23/23 SEMANTIC-PASS, 0 mismatches** (byte size differs because MSMR's dedup
differs slightly from the shipped encoder's; every (key,value) pair matches
exactly on re-parse). Single-key patch test: 1 value changed, 0 others touched.

⚠️ A WHOLE-FILE Unicode script sniff of a variant LIES (all 23 report identical
`hebrew=2703 / arabic=6439 / cyrillic=6563` — that is shared binary-table noise
from the other 4 sections, not text). Classification must read the VALUES section
only.

## Language map (23 variants, classified from VALUES)

| variant | span | language | notes |
|---|---|---|---|
| 00 | 0 | English | `kLanguageNone` fallback slot — byte-identical dup of span 8 |
| 01 | 8 | **English** | `kLanguageEnglish` (=1) — the PRIMARY hijack target |
| 02 | 24 | Danish | |
| 03 | 32 | Dutch | |
| 04 | 40 | Finnish | |
| 05 | 48 | French | |
| 06 | 56 | German | |
| 07 | 64 | Italian | |
| 08 | 72 | Japanese | |
| 09 | 80 | Korean | |
| 10 | 88 | Norwegian | |
| 11 | 96 | Polish | |
| 12 | 104 | Portuguese | |
| 13 | 112 | Russian | |
| 14 | 120 | Spanish | |
| 15 | 128 | Swedish | |
| 16 | 144 | Portuguese (Brazil) | |
| 17 | 152 | **English** | `kLanguageArabic` (=19) slot — English TEXT paired with the Arabic VOICE track only (no real Arabic translation shipped) |
| 18 | 168 | Spanish (LatAm) | |
| 19 | 184 | Chinese | |
| 20 | 200 | Czech | |
| 21 | 208 | Hungarian | |
| 22 | 216 | Greek | |

**No Hebrew, no populated Arabic.** `LANGUAGE_ARABIC` is a menu-picker LABEL
(`'ARABIC'`) with no populated Arabic string content behind it anywhere in the
corpus (0 Arabic codepoints measured across all 23 variants). ⇒ MSMR is an
**LTR-slot hijack** game (AC2 / Anno / GTA / TLOU / R&C class), not an
Arabic-slot game.

## Language enum (exe, `Spider-Man.exe`, this build only — 32-slot name table)

```
0 kLanguageNone            8 kLanguageItalian        16 kLanguageSwedish        24 kLanguageCaFrench
1 kLanguageEnglish         9 kLanguageJapanese        17 kLanguageMxSpanish     25 kLanguageCzech
2 kLanguageUkEnglish       10 kLanguageKorean         18 kLanguageBrPortuguese  26 kLanguageHungarian
3 kLanguageDanish          11 kLanguageNorwegian       19 kLanguageArabic       27 kLanguageGreek
4 kLanguageDutch           12 kLanguagePolish          20 kLanguageTurkish      28 kLanguageRomanian
5 kLanguageFinnish         13 kLanguagePortuguese      21 kLanguageLaSpanish    29 kLanguageThai
6 kLanguageFrench          14 kLanguageRussian         22 kLanguageChineseS     30 kLanguageVietnamese
7 kLanguageGerman          15 kLanguageSpanish         23 kLanguageChineseT     31 kLanguageIndonesian
```

`kLanguageHebrew` = 0 occurrences (ASCII+UTF-16). **The enum is PER-TITLE** — a
sibling game's numbers do not transfer (R&C's Arabic is enum 18, not 19; MSMR
inserts `kLanguageMxSpanish` at 17, shifting everything after it by one).

Proven by cross-checking against which enum values ship a VOICE dub (12 archives:
`us fr de it jp pl pt ru es br ar la`) — every dubbed language must also have a
text slot; only `enum value == table position` (not `position - 1`) satisfies
that with zero orphans.

## Activation — one `REG_DWORD`, zero user actions

`HKCU\Software\Insomniac Games\Marvel's Spider-Man Remastered`
- `TextLanguage` (REG_DWORD): `1` = English, `19` = the Arabic/English-text slot.
- `AudioLanguage` is a SEPARATE value — never written by this project, so voice
  stays English regardless (this install only has the `.us` voice archive on
  disk anyway).
- No `englishVO` key exists on MSMR (unlike SM2) — do not copy that field.
- No pre-game launcher window (`ShowLauncher` = 0 occurrences, vs 1 in R&C).
- ⚠️ `FirstRun` seeding is unconfirmed (never observed a real first launch) —
  the language switch should be written just before each launch as a
  precaution, not assumed to stick permanently.
- This machine's `TextLanguage` was found set to `19` (leftover/auto-detected)
  and was reset to `1` (English) as part of this session's proof deploy.

## Font — Scaleform `DefineFont3` (SWF tag 75), the format already solved for
Witcher 3 / RDR2 / 007 / Corsair Cove

UI fonts are 5 standalone Scaleform `.gfx` libraries under `ui/export/fonts/`:
`Font_LatinAS3.gfx` (the Latin/fallback library — the one that matters for
Hebrew), `Font_Cyrillic.gfx`, `Font_Chinese.gfx`, `Font_Japanese.gfx`,
`Font_Korean.gfx`. Each `.gfx` is a **bare, uncompressed Scaleform container**
(magic `"GFX"` + version byte + u32 file length) — no CR2W/CFX wrapper at all,
the simplest container class encountered in this project.

`Font_LatinAS3.gfx` holds 5 `DefineFont3Tag` faces, **0/27 Hebrew, 0 Arabic, 0
bidi-control glyphs in all 5** (measured via cmap/code-table dump):

| face id | name | glyphs |
|---|---|---|
| 1 | Azbuka Pro Bold Italic | 430 |
| 2 | Azbuka Pro Bold | 430 |
| 3 | Courier New | 217 |
| 4 | Digital | 66 |
| 5 | Azbuka Pro Medium | 430 |

"Azbuka Pro" is the exact family name Spider-Man 2 also uses as its primary UI
face — the two titles share a font vendor even though the container generation
differs.

Injection: `games/spiderman_remastered/tools/msmr_font.py`, a direct port of
`games/witcher3/work/inject_gfxfontlib.py`'s `add_hebrew()` (ADD, not replace —
Hebrew's codepoint range sits below the faces' max existing code, so it must be
INSERTED at the sorted position) over the shared `gfx_inspect.py` / `swf_font.py`
/ `swf_glyphgen.py` / `build_font.py` codec (all reused unmodified). Donor:
Heebo-Regular.ttf. **135 Hebrew glyphs added across all 5 faces, self-verified
(re-parse hebrew=27 per face, delta ~+2-2.4 KB per face), and confirmed to still
open cleanly in FFdec after rebuild.**

## DRM / integrity — clean, no wall

`Spider-Man.exe`: Denuvo 0 · VMProtect 0 · `.vmp` 0 · BattlEye 0 · EasyAntiCheat 0
· `SHA256` x2 · `integrity` x4 · `tamper` 0 · `checksum` 0. Ordinary unpacked PE
(`.text` 58.3 MB matching raw size, `.reloc` 2.2 MB, no odd RWX section). No
anti-cheat DLL anywhere in the 81-file install. This is the cleanest DRM profile
measured in this project so far — nowhere near the AC Black Flag Resynced wall
(SHA256 x143 / integrity x5 / tamper x11).

## Deploy — index-redirect, proven end-to-end (offline AND live)

`games/spiderman_remastered/tools/msmr_deploy.py`, same mechanism as SM2's
`spiderman2_mod.py` ported to the older MSMR toc layout:

1. Write the rebuilt asset as a raw file under `asset_archive/mods/tm_he_N`.
2. Append a 72-byte `ArchiveFileEntry` naming it (cloned bucket/chunkmap from an
   existing real archive entry).
3. Redirect that asset's `Offsets` entry to `{archive_index=new, offset=0}` and
   its `Sizes.value` to the new length.

No archive is ever repacked; every OTHER asset in the 771,670-entry toc keeps its
exact offset (offline-validated: 771,669 untouched entries drifted = 0).
Pristine `toc` is backed up to `toc.tm_he_backup` (a name deliberately distinct
from Overstrike/ALERT's own `toc.BAK`, so this project never clobbers another
mod tool's baseline) before the first write; revert is byte-identical and
game-update-aware (a fresh toc that no longer references `tm_he_*` is treated as
already-clean, never silently downgraded).

**🔴 Each appended archive's `chunkmap` field MUST be a globally-unique value —
it is NOT a shared constant like `install_bucket`.** `dat1lib`'s own reader never
consults `chunkmap` (resolves purely by `archive_index → filename`), so cloning
it from an existing archive passes every offline check built on `dat1lib` while
silently colliding with the real engine's own archive/chunk-streaming resolution
(discovered live 2026-08-10, see PIPELINE.md). `append_archive()` now assigns
`max(existing chunkmap) + 1` per call.

## Community precedent + tooling

- **No live public evidence** that "Nexus mod 361 (Arabic)" proves engine-side
  RTL for Hebrew — the page is unreachable and has no Wayback snapshot. This
  claim, carried over from an earlier note, is **retracted**: there is no
  Arabic text slot to have proven anything with in the first place.
- **Overstrike** (`Tkachov/Overstrike`) supports MSMR first-class
  (`GameMSMR.cs`, internal code `MSMR`) — confirms modified `toc`s load in the
  live modding scene (suit/skin mods routinely edit this exact file).
- ALERT (`team-waldo`, vendored in this repo) is the read/write reference the
  above tooling is built on.
- At least one shipped, actively-updated full TEXT mod exists for MSMR
  (community language localizations) — further evidence modified localization
  assets load without issue.

## Catalog

`games.id = "spiderman"` already exists (created 2026-05-15): title
"Marvel's Spider-Man Remastered", `availability=planned`, `status=locked`,
`price_cents=0`, `show_on_website=true`, `show_on_launcher=true`,
`sort_order=23`. Cover/banner/logo are already uploaded and live in the public
`covers` bucket. `translation_manager/game_detector.py` already resolves this
install today via all three paths (folder pattern `spiderman`, exe pattern
`Spider-Man.exe`) — no code change needed for detection.
