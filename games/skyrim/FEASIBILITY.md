# Skyrim SE / AE Hebrew — FEASIBILITY: 🟢🟢 GO, and one of the EASIEST targets in the project

**Every Phase-1 gate is CLOSED, in-game, in one screenshot** (`work/_menu.png`,
zoom `work/_menu_zoom.png`, captured autonomously by `work/autocheck.py`).

| gate | verdict | evidence |
|---|---|---|
| container | 🟢 no repack needed | loose files override the BSA — nothing inside an archive is touched |
| text codec | 🟢 **BYTE-IDENTICAL** identity round-trip | 5/5 tables, incl. the 34,427-entry `skyrim_english.ilstrings` |
| encoding | 🟢 **UTF-8** | ru/ja/pl values are UTF-8 multi-byte → Hebrew stores directly, no codepage |
| RTL slot | 🟡 no Arabic → English-slot hijack | zero user action: `sLanguage` already `ENGLISH` |
| bidi | 🟢 **VISUAL** (pre-reversed) | A/B pair on the live main menu, see below |
| font | 🟢 injected, 27/27, **zero tofu** | 13 faces across 3 SWFs, verified re-read from the deployed files |
| DRM / integrity | 🟢 none | no Denuvo, no anti-cheat, no content hashing; a huge live mod scene |

## The decisive screenshot

Both a LOGICAL and a VISUAL copy of the same word were placed on adjacent main-menu rows.
Exactly one can read as the real word — that is the whole bidi question, settled in one launch:

```
שלום                              <- $NEW,           stored VISUAL   -> READS CORRECTLY
םולש                              <- $LOAD,          stored LOGICAL  -> reads reversed
אבגד                              <- $CREATION CLUB, stored VISUAL   -> READS CORRECTLY
אבגדהוזחטיכךלמםנןסעפףצץקרשת       <- $MOD MANAGER,   all 27 letters  -> ZERO TOFU
דגבא                              <- $CREDITS,       stored LOGICAL  -> reads reversed
יציאה לשולחן העבודה                <- $QUIT,          real label      -> perfect
```

⇒ **Skyrim's Scaleform GFx does NO bidi. Store VISUAL.** This matches the community's own
Arabic tooling (xTranslator ships an explicit "Arabic RTL → LTR conversion"), and it is the
same class as GTA V / AC2 / Anno / RDR2 / TLOU — so `tools/skyrim_rtl.py` runs the REAL UBA
(python-bidi, RTL base) with engine tokens stashed as atomic PUA placeholders.

Bonus observations from the same frame: the main menu is **already right-aligned**, and a
string too long for its box is **auto-scaled down, not clipped** (the 27-letter line).

## Encoding — the finding that removes the biggest risk

Original Skyrim (LE) stored each language in its own ANSI codepage (en=1252, ru=1251,
pl=1250 …), which would have made Hebrew impossible without a cp1255 hack. **Skyrim SE
switched to UTF-8**, proven directly from the shipped bytes:

```
skyrim_russian.strings  id=1  b'\xd0\x9a\xd1\x80\xd1\x8b...'   <- UTF-8 Cyrillic, not cp1251
skyrim_japanese.strings id=1  b'\xe3\x83\xa9\xe3\x83\x83...'   <- UTF-8, not Shift-JIS
skyrim_polish.strings   id=1  b'Sk\xc5\x82adowisko'            <- UTF-8 ł, not cp1250
```
The same is true of `translate_english.txt` (UTF-16LE). So Hebrew is written verbatim.

## Scope — the three honest numbers

| | records | unique | chars |
|---|---:|---:|---:|
| `.STRINGS` (names, UI-ish) | 48,994 | 32,226 | 863,825 |
| `.ILSTRINGS` (dialogue / subtitles) | 44,570 | 41,166 | 2,846,101 |
| `.DLSTRINGS` (books, descriptions) | 5,665 | 4,960 | 3,461,725 |
| **total** | **99,229** | **78,042 GLOBAL unique** | **7,164,642** |

\+ 649 UI entries in `translate_english.txt`. 79 plugins carry English strings
(skyrim 67,414 · dragonborn 11,070 · dawnguard 8,182 · hearthfires 2,273 · update 1,393 ·
then the 64 Creation-Club plugins). Length: median 40, p90 118, **max 40,131** (a long book).
23,382 are ≤25 chars; 3,674 are >140.

⇒ workload comparable to Witcher 3 (94k) — a **fleet** job, not a single pass.

## Tokens that must survive verbatim

| token | count | examples |
|---|---:|---|
| `\r\n` | 34,073 | order-bearing → convert each segment, rejoin |
| `<...>` | 8,801 | `<Alias=City>` `<mag>` `<dur>` `<br>` `</p>` `<font face='$HandwrittenFont'>` `<p align="center">` `<font size='40'>` |
| `[...]` | 1,946 | `[Activate]` `[Sneak]` `[Mouse Move]` — control-name substitutions |
| `%d %s %i` | 42 | |

## 🔑 The New-Era / gender oracle is FREE and unusually rich

All 7 other shipped languages sit at **the same plugin|id|kind key**:

| language | rows | key parity vs English | what it settles |
|---|---:|---:|---|
| french, german, italian, spanish, polish | 99,305 | **100.0%** | referent gender (fr/es/it), register (de) |
| russian | 99,304 | **100.0%** | **speaker AND addressee gender** (past tense -л/-ла) |
| japanese | 89,870 | 90.6% | politeness level |

Polish + Russian together give the addressee/speaker gender that English drops — attach them
per line in the Phase-2 handoff and the Hebrew is gendered correctly from line 1
(`universal/GENDER_ORACLE_ROLLOUT.md`, scenario "no Arabic → use the game's own gendered locales").
Dumped to `extract/langs/<lang>.json`.

## Font — measured, not guessed

Skyrim's own faces carry **all-zero bounds RECTs**, so the only way to measure them is to walk
the glyph SHAPE records (`tools/shape.py`, which parses **2,041/2,041** shipped glyphs):

| id | face | cap | H aspect | role |
|---|---|---:|---:|---|
| 5 | Futura CondensedLight | 15,440 | **0.415** | `$DialogueFont` `$EverywhereFont` |
| 7 | Futura Condensed Medium | 15,440 | 0.466 | `$StartMenuFont` `$EverywhereMediumFont` |
| 9 | Futura Condensed Bold | 15,440 | 0.595 | `$EverywhereBoldFont` |
| 3/4 | Eurostile (LT) Cyr Std | 15,360 | 0.85/0.81 | `$CClub_Font{,_Bold}` |
| 13 | SkyrimBooks_Gaelic | 14,260 | 0.823 | `$SkyrimBooks` |
| 15 | SkyrimBooks_Handwritten_Bold | 15,660 | 0.993 | `$HandwrittenFont` |

The UI faces are **extremely condensed** (0.415!) while every Hebrew font is ~0.7–0.9, so
`skyrim_font.plan_face()` derives, per face: `body = 0.86 × that face's own cap height`, and a
horizontal condensation pulled toward that face's own H aspect but floored at 0.72 so the
letterforms never collapse. Donors: **Heebo** (Light/Regular/Medium) for the geometric UI,
**Frank Ruhl Libre** for the book face, **David Libre** for the handwritten face.

Structural facts that make the injection safe:
* `DefineFontAlignZones` (tag 73) carries exactly **10 bytes per glyph** (verified 206→2060) and
  is padded in lockstep, or the font desyncs.
* codes must stay ASCENDING — Hebrew (U+05D0) lands mid-table, above Latin and below U+2122.
* u16 offsets overflow if the extended shape data passes 0xFFFF → the injector **promotes the
  font to wide offsets** (flag 0x08) instead of corrupting it (fired on ids 3/4/15).
* new glyphs get **empty bounds**, matching all 2,041 shipped glyphs.

## Deploy — the cleanest mechanism in the project

Five **loose files**. No BSA is opened for writing, no repack, no archive invalidation,
no admin rights, and Steam file-verification cannot fight it (the BSAs are byte-untouched):

```
Data\Interface\fonts_en.swf
Data\Interface\fonts_console.swf
Data\Interface\gfxfontlib.swf
Data\Interface\translate_english.txt
Data\Strings\skyrim_english.STRINGS      (+ the other plugins in Phase 2)
```
Revert = delete them (`python work/build_proof.py --revert`).

## The launcher is a THIRD surface — also closed

`SkyrimSELauncher.exe` keeps 100% of its text in resources: 576 RT_STRINGs in nine 1000-wide
ID blocks (10xxx EN · 11 FR · 12 IT · 13 DE · 14 ES · 15 PL · 16 RU · 17 zh-TW · 18 JA) plus 72
pre-rendered 275x50 menu bitmaps (4 items x 9 languages x 2 states). Hijacking the ENGLISH block
again costs zero user actions. Patched via `Begin/Update/EndUpdateResource` (no-op round-trip
verified byte-identical), pristine exe backed up.

**🔴 Its dialogs need the OPPOSITE bidi mode from the game.** Proven the same way, on the Options
dialog: `שלום` stored LOGICAL read CORRECTLY while the VISUAL copy on the adjacent checkbox read
reversed — Win32/Uniscribe *does* run the bidi algorithm, Scaleform does not. The Latin marker
`ZZ-SKYL-OK-ZZ` rendered, all 27 letters rendered with zero tofu in Windows' own dialog font, and
the main menu came up fully Hebrew (שחק / אפשרויות / תמיכה / יציאה).

⚠️ The launcher's manifest demands admin, so it must be started with `__COMPAT_LAYER=RUNASINVOKER`
for an unattended capture. It is also NOT required to play — `SkyrimSE.exe` runs the game directly.

## Risks / open items

* **`.DLSTRINGS` books hold `<p align>` / `<font size>` markup and run to 40k chars** — the
  paragraph wrap + justification questions from RDR2 §8b apply there and need their own ruler
  pass; the menu proof only cleared short strings.
* The 64 Creation-Club plugins each ship their own strings — Phase 2 must emit one loose
  `Strings/<plugin>_english.*` per plugin (79 files), not just `skyrim_*`.
* Long strings are auto-shrunk to fit, so overflow shows as *smaller text*, not clipping.

## מסמכים קשורים
- באותה תיקייה: [[games/skyrim/PIPELINE|PIPELINE]], [[games/skyrim/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#skyrim|CLAUDE_INDEX_games]]
