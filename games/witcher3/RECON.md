# The Witcher 3: Wild Hunt — Hebrew translation — RECON (verified facts)

> Phase-1 groundwork recon. Every fact below is **verified by direct inspection** of the
> user's install and/or by a working pure-Python codec that round-trips the game's own files.
> Written 2026-07-01.

## Install

| | |
|---|---|
| Path | `D:\Games\The Witcher 3 - Complete Edition` (GOG, dual GOG/Steam launcher, next-gen 4.x, files patched 2026-06-30) |
| Engine | **REDengine 3** (NOT CR2W/REDengine 4 like Cyberpunk 2077 — different toolchain) |
| exe | `bin\x64\witcher3.exe` + `bin\x64_dx12\witcher3.exe` · launcher `gameId="witcher3"` |
| Anti-cheat | **NONE** (TW3 is fully mod-friendly; no EAC/Denuvo/Galaxy integrity on assets) |

## Where the text lives — `.w3strings`

All localized text = per-language `<lang>.w3strings` files, spread across:
- `content\content0..content12\<lang>.w3strings`  (base game + free DLC)
- `dlc\<name>\content\<lang>.w3strings`  (`ep1`=Hearts of Stone, `bob`=Blood and Wine, `dlc1..dlc20`)

**17 shipped languages:** `ar br cn cz de en es esmx fr hu it jp kr pl ru tr zh`.
✅ **`ar.w3strings` EXISTS = official Arabic (RTL) locale** (added by the next-gen 4.0 update).

There is **no separate UI-vs-subtitle file split** (unlike WD2). UI labels, menus, item text, quest
objectives, journal, **and dialogue subtitles** are all intermixed in the same keyed string tables,
referenced by numeric `str_id` from the scene/quest/UI resources. So "UI count" vs "subtitle count"
is not separable from the `.w3strings` alone (the human-readable key is not stored — see below).

## The `.w3strings` binary format (fully cracked + codec built)

Reproduced from `hhrhhr/Lua-utils-for-Witcher-3` (`mod_w3strings.lua` + `inspect_w3strings.lua`)
and **verified byte-for-byte** against the game's files. Codec: [`work/w3strings.py`](work/w3strings.py)
(pure Python, no deps, read+write).

```
Little-endian layout:
  char   magic[4]   = "RTSW"
  uint32 version    = 163 (0xA3) on this next-gen build   (rmemr's tool writes 162 for back-compat)
  uint16 key1       @ offset 8
  <count1 = bit6 varint @ offset 10>
  block1: count1 * { uint32 str_id ^ encKey ; uint32 offset (UTF-16 units into blob) ; uint32 strlen (UTF-16 chars) }
  <count2 = bit6 varint>
  block2: count2 * { uint32 key_hash (CDPR string-key HASH, SAME across languages) ; uint32 str_id ^ encKey }
  <count3 = bit6 varint>   (# of UTF-16 code units in the blob, incl. terminators)
  blob:   count3 * uint16  (UTF-16LE; each string 0x0000-terminated)
  uint16 key2       @ end-2
  keyID = (key1<<16) | key2  ->  language-key table  ->  encKey
```

- **`bit6`** = a custom 6/7-bit varint (first chunk 6 bits w/ 0x40="more", rest 7 bits w/ 0x80="more";
  `0` encodes as `0x80`). `emit_bit6` VERIFIED to reproduce the game's own count bytes
  (`35→23`, `76→4c01`, `27601→51af03`, `2174539→4bb98902`).
- **Per-string XOR cipher** keyed off `encKey`. **keyID 0 = CLEARTEXT (no encryption).**
- **🔑 The Arabic slot is CLEARTEXT** (`key1=key2=0` → keyID 0). Verified on every `ar.w3strings`.
  So **Hebrew goes in as plain UTF-16LE — no encryption key, no XOR**. This is the simplest possible case.
- English (and the 13 classic langs) ARE encrypted (en encKey `0x79321793`); the codec decrypts them
  so we can read the English **source**. (ar/esmx/cn/kr next-gen locales are all cleartext / keyID 0.)
- **`str_id` is SHARED across languages** after the `^encKey` un-mask. Proven:
  en raw `0x7923498e ^ 0x79321793 = 0x00115e1d` = exactly the Arabic slot's `str_id`. So EN→HE maps
  cleanly **by `str_id`** (decode `en`, translate the text, write it into the `ar` structure at the same id).
- **The human-readable string KEY is NOT stored** — only its `key_hash` (block2, shared across langs).
  Recovering the key NAME (for a UI/subtitle split or context) needs `wcc_lite dumpcharset`/uncooked
  key lists or a community key dump. Not required to translate (we key on `str_id`).

## Bidi / RTL storage mode — **VISUAL (pre-reversed)** — ✅ CONFIRMED in-game 2026-07-01

The shipped Arabic strings are stored **logical + a leading `U+202E` (RLO)** (e.g. `‮لعبة جديدة +`),
which is what makes the Arabic script render RTL. **But the engine only honors that bidi/RLO for the
ARABIC script, NOT for Hebrew** (CDPR only implemented RTL for the official Arabic locale; the font
happens to carry Hebrew glyphs, but the bidi engine doesn't treat Hebrew as RTL).

**Proven by two in-game menu builds:**
- v1 — Hebrew stored **logical + RLO** → rendered **REVERSED/mirror** (`אפשרויות`→`תוירשפא`). The RLO
  was a no-op for Hebrew; the menu drew the stored character order left-to-right.
- v2 — Hebrew stored **VISUAL (pre-reversed per line, no RLO)** → rendered **correct RTL** (user-confirmed:
  `המשך · משחק חדש · טעינת משחק · אפשרויות · התגמולים שלי · יציאה`, readable, no tofu, no mirror).

→ **Store Hebrew VISUAL** (WD2-menu/AC2/GTA/Anno class): the translator/agent writes LOGICAL Hebrew; a
`visual_line()` (reverse each Hebrew run, keep space/Latin/digit/symbol runs forward, flip run order, per
line) is applied only at BUILD time. No RLO needed. Implemented + verified in `work/build_menu_proof.py:visual_line`.

**✅ SUBTITLES confirmed VISUAL too (uniform across surfaces).** A second in-game proof translated the
opening bath-scene dialogue (Geralt/Yennefer, ids 1071628/1071629/1071630/1071435) → the subtitles + the
right-aligned dialogue options rendered **correct RTL** (user-confirmed). So **bidi = VISUAL everywhere**
(menu AND subtitles) — no per-surface difference, no logical-storage surface. Numbers/Latin inside a line
render fine (`visual_line` keeps them forward + flips run order).

### ⚠️ Per-file id placement — each str_id lives in ONE specific content file
An id belongs to a specific `content<N>`/`dlc` file, and **writing it into the wrong file is silently
ignored** (the opening dialogue ids are in **content1**, not content0 — dumping them into content0 did
nothing; only after writing them into content1 did they show). Higher content files take priority. **The
build MUST be per-file:** decode each `content*/dlc* ar.w3strings`, override only ITS own ids, re-encode
that file. `work/build_proof.py` does this correctly and is the Phase-2 build template. (`dump_corpus.py`'s
merged corpus is for translation only; `extract/index.json` tracks each id's file.)

## Scope (verified by decoding every file)

| Language | files | strings | chars |
|---|--:|--:|--:|
| **ar** (translation TARGET slot) | 34 | **97,458** | 5,823,443 |
| **en** (translation SOURCE) | 34 | **97,525** | 6,521,542 |

(ar has 67 fewer than en — a handful of strings are untranslated/absent in the shipped Arabic; we
translate from the EN source and fill the ar slot by `str_id`.)

Biggest chunks (en): `content0`=27,660 (base UI + White Orchard/Velen/Novigrad) · `content4`=23,779
(Skellige/main) · `dlc\bob`=18,905 (Blood and Wine) · `content5`=8,381 · `dlc\ep1`=7,100 (Hearts of
Stone) · rest small. **Total ≈ 97.5k strings / ~6.5M source chars** — a large but very tractable haul.

## Fonts — ✅ NO WORK NEEDED (Arabic-locale font already renders Hebrew) — confirmed 2026-07-01

The in-game menu proof rendered Hebrew glyphs cleanly (`המשך`, `אפשרויות`, …) with **zero tofu** — so
**the font used by the Arabic locale already covers Hebrew `U+05D0–U+05EA`**. **No font extraction, no
SWF editing, no glyph injection.** (This matches AC Shadows/WD2 — a pan-Unicode font that happens to
carry Hebrew.) For reference only: TW3 fonts = Scaleform SWF (`fonts_<lang>.redswf`, TTF embedded, in
`r4gui.bundle`); toolchain if ever needed = TW3 ModKit `wcc_lite` / WolvenKit 0.6.1 + JPEXS + FontForge
(NOT the CP2077 WolvenKit 8.x). The font gate is **CLOSED**.

## Deploy + activation

- **Deploy = a Mods folder mod**: `<game>\Mods\modHebrew\content\<content-folder-mirror>\ar.w3strings`
  (a `.w3strings` in a mod overrides the base one for that locale). Alternatively overwrite the base
  `content\*\ar.w3strings` + `dlc\*\content\ar.w3strings` directly (reversible via backup). No repack of
  bundles is needed for text — only if we also ship a font (which lives in the bundle/SWF).
- No `Mods\` folder exists yet; `Documents\The Witcher 3\mods.settings` is empty (no mods installed).
- **Activation:** in-game **Options → Text Language = Arabic (العربية)**, keep **Speech = English**.
  These are independent (`ListTextLanguages` / `ListSpeechLanguages`), and persisted in
  `Documents\The Witcher 3\user.settings` as `[Localization] TextLanguage=AR` (+ `SpeechLanguage=EN`).
  Verified the file currently reads `TextLanguage=EN` / `SpeechLanguage=EN`.
- **Precedent:** a next-gen "Community Patch — Menu Strings — Arabic Translation" mod (Nexus 11005)
  already ships RTL menu strings via the Arabic slot this exact way.

## Tools status

- `work/w3strings.py` — our pure-Python read/write codec (built + verified). ✅
- TW3 ModKit `wcc_lite.exe` / WolvenKit 0.6.1 — **NOT installed** (needed only for the font SWF, and
  optionally for uncooking the key-name list). The CP2077 `WolvenKit.CLI.exe` 8.x is present but is
  REDengine-4 only — it does **not** read TW3 bundles/fonts.
- `w3strings.exe` (rmemr) / `w3stringsx` — optional external encoders; our Python codec supersedes them.

## Sources

- rmemr w3strings encoder — https://www.nexusmods.com/witcher3/mods/1055
- hhrhhr Lua-utils (format source) — https://github.com/hhrhhr/Lua-utils-for-Witcher-3
- w3stringsx (newer encoder + guide) — https://www.nexusmods.com/witcher3/mods/8577 · guide 9792
- Better Arabic Font — https://www.nexusmods.com/witcher3/mods/5023
- Community Patch Menu Strings — Arabic (next-gen precedent) — https://www.nexusmods.com/witcher3/mods/11005
- TW3 ModKit / wcc_lite — https://www.nexusmods.com/witcher3/mods/3332 · rfuzzo Witcher-3-ModKit-UI

## מסמכים קשורים
- באותה תיקייה: [[games/witcher3/FEASIBILITY|FEASIBILITY]], [[games/witcher3/KNOWN_ISSUES|KNOWN_ISSUES]], [[games/witcher3/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#witcher3|CLAUDE_INDEX_games]]
