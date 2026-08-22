# A Plague Tale: Requiem — RECON (engine / format map)

**Game:** A Plague Tale: Requiem · **Studio:** Asobo · **Engine:** **Zouna**
(same engine family as A Plague Tale: Innocence and Microsoft Flight Simulator).
**Install (staging/test copy):** `D:\Games\A Plague Tale - Requiem` (GOG+Steam
dual build; `steam_emu.ini` present). exe: `APlagueTaleRequiem_x64.exe`.
**No Denuvo / no anti-cheat.** Detector key / Supabase `games.id` = **`plague-tale-requiem`**
(already in `translation_manager/game_detector.py`).

## Where the text lives — the big win
All translatable text is in **LOOSE plain-text files** under `TRTEXT/`:

```
TRTEXT/tt01.pc  = English   (TSC_ID 01)  -> translation SOURCE
TRTEXT/tt23.pc  = Arabic    (TSC_ID 23)  -> our Hebrew TARGET SLOT
TRTEXT/tt02..22 = the other 13 languages (French/German/.../SChinese)
TRTEXT/ttNN.IGN = a second, divergent variant of each (see below)
```

`ttNN` maps to the **TSC_ID** in `LangDef.tsc` (`AddLangDefine 23 ... ARABIC`).
The files are read **loose at runtime** — NOT packed inside `COMMON.DPC`
(verified: the marker `ACHIEVEMENT__DESC_1` / `TRTEXT` / `BIG_ARABIC` are absent
from `COMMON.DPC`). So **deploy = overwrite `tt23.pc`. No repack, no compression.**

### File format (UTF-8, CRLF, NO BOM)
```
FreeLanguage
ResetEnumTT
TT <index> "<value>" <KEY>          <- 20,661 of these, index 0..20660
...
EndLoadTT
```
* `<value>` never contains a literal `"` (verified 0) → unambiguous parse.
* `<KEY>` = `[A-Za-z0-9_]+`, **shared across every language** → EN↔AR↔HE map 1:1
  by KEY (and by index; order matches). One quirk: `OBJECTIVE__CH14_PROTECTSOPHIAANDLUCAS`
  has a trailing space after its key — the codec preserves it byte-for-byte.
* In-value **line break = `|`** (there are NO literal `\n`). 3 rows use it.
* `{STR_...}` = a runtime button/key-bind token (31 distinct; kept verbatim).

## Scope (from tt01.pc, 20,661 strings)
| category | count | notes |
|---|---:|---|
| subtitles (`VO__…`) | 17,476 | spoken dialogue / bark / cutscene |
| UI (`MENU/HUD/OBJECTIVE/TUTO/ACHIEVEMENT/LOOT/GAME/...`) | 1,433 | menus, HUD, objectives, item text |
| credits (`CREDIT__…`) | 1,752 | end credits (low priority — names/legal) |

## Fonts
`InitFont.tsc` loads, from `FONT\ENGLISH.DPC`, the fonts:
`BIG_FONT, SMALL_FONT, SMALL_FONT_02, BIG_RUS, BIG_JAP, BIG_KOR, BIG_CHI, **BIG_ARABIC**`.
So the Arabic slot renders with **BIG_ARABIC**. Fonts in Zouna are **bitmap
texture ATLASES** (class `Fonts_Z` = `Map<CharacterID, Character>` → material_index
+ UV rect + descent, glyph pixels in a `Bitmap_Z` atlas; `CharacterID` = the
glyph's UTF-8 bytes reversed, null-padded). There is **no embedded TTF** to swap —
Hebrew glyphs (U+05D0–05EA) would be injected into the atlas + `Fonts_Z` metrics.
`MENU__ALLCHARACTERS` (tt01) lists the Latin font's charset (Hebrew/Arabic are in
the separate BIG_* font resources).

## DPC container (only needed IF font injection is required)
`.DPC` = Asobo "BigFile": 256-byte ASCII version banner
(`v2.128.52.19 - Asobo Studio - Internal Cross Technology`, NOT encryption) then a
block table; **A Plague Tale generation uses 64-bit name/class hashes + LZ4**
(`compressedSize==0` = stored raw). Community tools:
* **amrshaheen61/APT_DPC_Tool** (C#, Plague-Tale-specific; extract works, import
  buggy per author)
* **widberg/bff** ("BigFile Friend", Rust; Requiem = PARTIAL/WIP)
* **widberg/fmtk** wiki (format spec: `Fonts_Z`, `Bitmap_Z`), **widberg/ImZouna**
  (ImHex `.hexpat`), **widberg/dpc** (archived predecessor).

## DATAS / LEVELS (not translation-relevant)
`DATAS/*.DPC` = 3D/audio/texture asset packages (`COMMON.DPC` is 31 GB).
`LEVELS/<LEVEL>/*.DPC` per level (incl. `MENU/MENU.DPC`). These reference the
`TT` keys but do NOT hold the translatable strings.

## Activation
In-game **Options → Text language = العربية (Arabic)**. Voice/text are independent
(`LangDef` maps ARABIC's audio to English) so English VO is preserved for free.

## מסמכים קשורים
- באותה תיקייה: [[games/plague_tale_requiem/FEASIBILITY|FEASIBILITY]], [[games/plague_tale_requiem/PIPELINE|PIPELINE]], [[games/plague_tale_requiem/RESEARCH_FONTSIZE|RESEARCH_FONTSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#plague_tale_requiem|CLAUDE_INDEX_games]]
