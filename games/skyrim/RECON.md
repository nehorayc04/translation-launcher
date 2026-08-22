# Skyrim SE / Anniversary Edition — RECON

**Install** `D:\Games\TES - Skyrim - Anniversary Edition` · exe `SkyrimSE.exe` (35.4 MB)
**Engine** Bethesda Creation Engine (32-bit Gamebryo lineage, 64-bit SSE rebuild)
**Steam appid** 489830 · CODEX crack (`steam_emu.ini`, `steam_api64.dll`) · **no Denuvo, no anti-cheat**
**Proposed `games.id`** `skyrim` · detector exe `SkyrimSE.exe`

## Layout

| | |
|---|---|
| `Data/*.bsa` | **91** archives (base + DLC + 64 Creation-Club) |
| `Data/*.esm` | 15 (Skyrim, Update, Dawnguard, HearthFires, Dragonborn + CC) |
| `Data/*.esl` | 64 Creation-Club plugins |
| `Data/` loose | only `Video/` — **no loose Strings/Interface**, so both are ours to add |
| user ini | `%REAL_HOME%\Documents\My Games\Skyrim Special Edition\{Skyrim.INI,SkyrimPrefs.ini}` |

⚠️ `Skyrim_Default.ini` lists `Skyrim - Patch.bsa` in `sResourceArchiveList2` but that
archive **does not exist** in this build — a missing entry is tolerated.

## Container — BSA v105

`games/skyrim/tools/bsa.py` (pure Python, read-only, verified on all 91 archives).

```
magic "BSA\0" | u32 version(105) | u32 folderRecordOffset(36)
u32 archiveFlags | u32 folderCount | u32 fileCount
u32 totalFolderNameLength | u32 totalFileNameLength | u32 fileFlags
folder record  v105 <QIIQ> (hash,count,pad,offset)   [offset INCLUDES totalFileNameLength]
file record    <QII>  (hash,size,offset); size bit30 TOGGLES compression vs the archive default
data           [u8 len + path if flag 0x100] [u32 origSize if compressed] payload
compression    v105 = LZ4 frame   (v104 = zlib)
```
`Skyrim - Interface.bsa` is `flags=0x3` = names only, **stored uncompressed** — the file we care
about most needs no codec at all.

## Where the text lives — TWO separate surfaces

| surface | file | format | scope |
|---|---|---|---|
| game content | `strings/<plugin>_english.{STRINGS,DLSTRINGS,ILSTRINGS}` inside `Skyrim - Interface.bsa` (base/DLC) and each `cc*.bsa` | Bethesda string table, **UTF-8** | 99,229 records |
| UI chrome | `interface/translate_english.txt` | UTF-16LE + BOM, CRLF, `$key<TAB>value` | 649 entries |

`.STRINGS` = short names · `.DLSTRINGS` = books/descriptions · `.ILSTRINGS` = dialogue/subtitles.
The main menu, settings, HUD labels are in `translate_english.txt`, **not** in the string tables.

## Languages shipped

`english french german italian spanish polish russian japanese` — **all LTR, no Arabic, no Hebrew.**
⇒ LTR-slot hijack (English), and the language is set by `Skyrim.INI` `[General] sLanguage=ENGLISH`.

## Fonts

Real **SWF** (not GFX/CFX) under `interface/`, routed by `interface/fontconfig.txt`:

| file | sig | faces |
|---|---|---|
| `fonts_en.swf` | CWS v15 | 16 DefineFont3 — Futura Condensed{Light,Medium,Bold}, Eurostile, SkyrimBooks_{Gaelic,Handwritten,Unreadable}, Dragon/Daedric/Dwemer/Falmer/Mage script, Controller Buttons |
| `fonts_console.swf` | CWS v15 | Arial |
| `gfxfontlib.swf` | CWS v10 | 12 shared faces |
| `fonts_ru.swf` / `fonts_pl.swf` | FWS/CWS | the Cyrillic / Central-European variants |

`fontconfig.txt` maps logical names (`$EverywhereFont`, `$SkyrimBooks`, `$DialogueFont` …) to
`face-name + style`, and carries a `validNameChars` whitelist (character-name entry only).
`fontconfig_ru.txt` / `_pl.txt` are the per-language variants.

## Read-only tooling built here

`tools/bsa.py` · `tools/strings.py` · `tools/translate_txt.py` · `tools/swf.py` ·
`tools/shape.py` (SWF glyph-shape reader — the ONLY way to measure these faces, see FEASIBILITY)

## מסמכים קשורים
- באותה תיקייה: [[games/skyrim/FEASIBILITY|FEASIBILITY]], [[games/skyrim/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#skyrim|CLAUDE_INDEX_games]]
