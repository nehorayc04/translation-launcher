# UNCHARTED: Legacy of Thieves Collection — RECON

**Target:** `F:\Game Lab\UNCHARTED - Legacy of Thieves Collection`
**Date:** 2026-07-24 · read-only recon, **no game file modified**
**`games.id` = `uncharted`** (the catalog row `/games/uncharted` = "Uncharted: Legacy of Thieves"
ALREADY EXISTED — do NOT create `uncharted-lot`; the `/translate` pool + all Phase-2 tooling attach
to `uncharted`. ⚠️ always check the live catalog before minting a games.id.)

---

## 1. Identity

| | |
|---|---|
| Studio / port | Naughty Dog (2016/2017) · PC port by **Nixxes**, 2022 |
| Engine | Naughty Dog proprietary — **same family as TLOU Part I / Part II** |
| Contents | **TWO games in one install**: Uncharted 4 (`u4.exe`) + The Lost Legacy (`tll.exe`) |
| Launcher | `Launcher.exe` + `Launcher.ini` picks which exe to run |
| Steam appid | **1659420** (depots 1659421 / 1659422) |
| Copy on disk | Cracked — Goldberg emu (`steam_settings/`), no Steam client needed |
| DRM | **None.** 0 hits for Denuvo / VMProtect / `.vmp` / EAC / BattlEye in both exes |
| Packing | Plain PE. `.reloc` 314 KB against a 38 MB `.text` ⇒ **not packed**, statically analyzable |
| Oodle | Ships its own **`oo2core_9_win64.dll`** (Oodle 2.9) in the game root — no borrowing |
| UI runtime | **Iggy** (`iggy_w64_final.dll`, RAD's Flash player) + a native bitmap-font renderer |
| Video | `bink2w64.dll` |

Detector candidates: folder `UNCHARTED - Legacy of Thieves Collection`, exes **`u4.exe`** +
**`tll.exe`**, marker dir `Uncharted4_data`.

---

## 2. Archive layout

```
Uncharted4_data/
  data/                 fonts.psarc  post.psarc  wind.psarc
  build/pc/
    main/               flash1.psarc  iggy1.psarc  sound1.psarc  text2.psarc(241 KB)
    uncharted4/         text2.psarc  sid1.psarc  boot1  dc1  pak54  texturedict2 ... (17)
    thelostlegacy/      text2.psarc  sid1.psarc  boot1  dc1  pak54  texturedict2 ... (17)
  screeninfo.cfg        graphics settings only — no language key
```

**🔑 `uncharted4/text2.psarc` and `thelostlegacy/text2.psarc` are BYTE-IDENTICAL**
(md5 `5002993429da7fe3b2abccad7b39ff2e`, 24,919,578 B) — and so are the two `sid1.psarc`.
The archive holds **both games' text** (verified: Chloe/Nadine/Asav from Lost Legacy sit
alongside Sully/Elena/Rafe/Sam from Uncharted 4).
⇒ **ONE text deploy covers BOTH games**, written to both paths.

`main/text2.psarc` holds only `trophy-definitions.json` — not translatable UI.

---

## 3. Container — PSARC v1.4 / Oodle · **already cracked, zero new work**

Header of every archive: `PSAR` + `00 01 00 04` + `oodl`.
This is **exactly** TLOU Part I's container (**not** TLOU2's DSAR wrapper), so
`games/tlou1/tools/{oodle,psarc,psarc_write}.py` read AND write it **unchanged**:

```
TLOU_OODLE_DLL="F:/Game Lab/UNCHARTED .../oo2core_9_win64.dll" \
  python games/tlou1/tools/psarc.py list <archive>
```

**Repack proven (this session, on the real 24 MB `text2.psarc`):**

| test | result |
|---|---|
| identity repack | **24,919,578 B — same size as source**, all 48 entries content-identical, **0.1 s** |
| Hebrew edit repack | value reads back correctly; **all 47 other entries byte-identical** |

`psarc_write.repack()` stream-copies unchanged entries verbatim and only Oodle-compresses
what changed — so a full text rebuild is a fraction of a second, not minutes.

---

## 4. Text format

`text2.psarc` → **48 entries**: `<lang>.common` + `<lang>.subtitles` × 23 languages,
plus `eng.subtitles-systemic` (English only) and `sid-lookup` (3.8 MB).

Naughty Dog string table, little-endian:

```
uint32 count
count * { sid, blobOffset }          <- RECORD WIDTH IS NOT FIXED
blob:  UTF-8, NUL-terminated at blob_start + blobOffset
       blob_start = 4 + count * REC
```

**🔴 The record width differs per file type — this is why `games/tlou1/tools/tlou_loc.py`
returns empty strings on `.common` / `.subtitles`:**

| file | REC | struct |
|---|---|---|
| `<lang>.common`, `<lang>.subtitles` | **8 B** | `<II>` — u32 sid, u32 offset |
| `eng.subtitles-systemic` | **16 B** | `<QQ>` — u64 sid, u64 offset |

Codec written: **`tools/unc_loc.py`** (`detect_rec` validates the width instead of guessing;
never assume 8 or 16). **Self-test PASS on all three files** — identity re-encode is
**byte-identical**, an override round-trips, every other record stays intact.
`encode()` is **surgical** (original blob kept verbatim, new values appended to the tail) —
the same discipline that a full rebuild broke in-game on TLOU2R.

---

## 5. Languages — 23 slots, **all LTR**, plus a dormant Arabic ID

Shipped: `bra chi chs cze dan dut eng fin fre ger gre ita jpn kor nor pol por rus sas spa swe tur uke`

* `sas` = LatAm Spanish · `chi` = Traditional Chinese · `chs` = Simplified
* **`uke` = `LANGUAGE_UKENGLISH` (en-GB), NOT Ukrainian** — its text is essentially the English
  text. It is therefore the cheapest sacrifice slot if an LTR hijack is ever needed.
* **No Arabic, no Hebrew file ships.**

**🔴🔴 But `LANGUAGE_ARABIC` exists in the engine.** The exe carries a language table of
triplets — *3-letter loc code · `*hud-flash-keys-XX-XX-array*` · asset/font name*:

```
'tur' *hud-flash-keys-tr-tr-array* 'turkish'
'ara' *hud-flash-keys-ar-ae-array*            <-- Arabic entry, ar-AE
'nor' *hud-flash-keys-no-no-array* 'norwegian'
'chi' *hud-flash-keys-zh-hant-array* 'chinese'
'rus' *hud-flash-keys-ru-ru-array* 'russian'
'pol' *hud-flash-keys-pl-pl-array* 'polish'
...  LANGUAGE_ARABIC ... 'ar' ... 'arabic'
```

**The third field is exactly the `.fnt` name in `fonts.psarc`** (`russian.fnt`, `chinese.fnt`,
`korean.fnt`, `japanese.fnt` all exist) — so the table is the language→font mapping, and the
Arabic row points at an **`arabic.fnt` that simply was not shipped on PC**. Uncharted 4 did ship
Arabic subtitles on PS4 in MENA, so the engine's Arabic path is real code, not a stub.
See FEASIBILITY §"the decisive question".

Also present: `LanguageManager::FindPlayGoAvailableLanguage`,
`m_languages[preferredTextAndSubtitleLanguage].IsTextSupported()` — availability is
**data-driven**, i.e. a language becomes selectable when its files exist.

---

## 6. Activation — a one-line text file

`steam_settings/force_language.txt` → `english`
`steam_settings/supported_languages.txt` → 22 Steam language names.

Steam name → loc code: english→eng · french→fre · italian→ita · german→ger · spanish→spa ·
czech→cze · danish→dan · dutch→dut · finnish→fin · greek→gre · japanese→jpn · koreana→kor ·
norwegian→nor · polish→pol · portuguese→por · brazilian→bra · russian→rus · schinese→chs ·
latam→sas · swedish→swe · tchinese→chi · turkish→tur. (`arabic` is the Steam name for `ara`.)

⇒ **The simplest activation lever in the project** — on this (Goldberg) copy the language is one
word in one text file; on a legitimate Steam copy it follows the Steam client language / the
in-game option. A launcher language switch would be a new `kind:"textfile"` in `game_language.py`.

---

## 7. Fonts — two independent surfaces, **neither has Hebrew**

### (a) Native bitmap atlases — `data/fonts.psarc` (18 files)

**Plain-text AngelCode BMFont descriptors + uncompressed TGA.** The easiest font format met so
far in this project: no DXT/BC, no binary glyph records, no SWF surgery.

```
info face="Adelon-Serial DB" size=42 bold=1 ... unicode=1 ...
common lineHeight=42 base=34 scaleW=256 scaleH=128 pages=1 packed=1
page id=0 file="main_00.tga"
char id=32 x=.. y=.. width=.. height=.. xoffset=.. yoffset=.. xadvance=.. page=0 chnl=..
```

| .fnt | face | size | glyphs | latin | cyr | **HEB** | atlas |
|---|---|---:|---:|---:|---:|---:|---|
| **main** | Adelon-Serial DB | 42 | 204 | 95 | 0 | **0** | 256×128 |
| classic | Adelon-Serial DB | 42 | 210 | 95 | 0 | **0** | 256×256 |
| game3 | Adelon-Serial DB | 42 | 201 | 95 | 0 | **0** | 256×128 |
| game | Albertus Medium | 30 | 95 | 95 | 0 | **0** | 256×256 |
| **russian** | Myriad Pro Light | 38 | 258 | 95 | 63 | **0** | 256×128 |
| korean | Arial Unicode MS | 36 | 1,010 | 0 | 6 | **0** | 512×512 |
| japanese | FOT-Seurat Pro M | 38 | 1,399 | 0 | 0 | **0** | 1024×512 |
| chinese | Arial Unicode MS | 38 | 2,172 | 0 | 6 | **0** | 1024×512 |
| symbol3 / test2 | — | | 18 / 95 | | | **0** | |

TGA = **32-bit RGBA, uncompressed, type 2, top-down (`desc=0x20`)**, 18-byte header + 26-byte
footer. `packed=1` ⇒ glyphs are **channel-packed** (`chnl` 1/2/4/8 = B/G/R/A), so the 256×128
`main_00.tga` really holds 4×32,768 px of glyph space.

**Free space in `main_00.tga` (measured from the box list):**
chnl 1 = 97.7 % used · chnl 2 = 96.0 % · chnl 4 = 95.3 % · **chnl 8 (alpha) = 47.9 % used,
maxY = 69** ⇒ **rows 69→128 of the alpha channel are entirely free (≈15 k px)**, plus gaps.
Whole atlas is 84.2 % used across 4 channels.

### (b) Iggy / Flash UI — `main/iggy1.psarc` (+ `flash1.psarc` sources)

`fontlib.iggy` (1.45 MB) and `fmenu.iggy` (3.7 MB) are the compiled Flash the game loads;
`flash1.psarc` keeps the `.swf` sources. Parsed the SWF `DefineFont3` tags:

| lib | fonts | notable |
|---|---:|---|
| `fontlib.swf` | 10 | Cast-Bold, Cast-Regular, Arial Unicode MS, Albertus Medium, Comic Sans, 宋体, 굴림 |
| `fontlib-universal.swf` | 7 | Arial Unicode MS **5,176 glyphs**, DFHeiW5-A-V-SONY 4,164, HeiT ASC 3,178 |

**Every one of the 17 fonts: `HEB = 0/27`.** Cyrillic is present (65 glyphs) in the big faces,
CJK up to 4,775 — but **no Hebrew and no Arabic anywhere**.
One curiosity: `fontlib.swf` id=13 is a 1-glyph "Arial" whose only codepoint is **U+200E (LRM)**
— the UI does at least carry a bidi control glyph.

⇒ **Hebrew glyphs must be injected.** Which surface matters for which text (subtitles vs menus)
is the #1 thing the menu proof has to settle — see PIPELINE.

---

## 8. Scope (measured from `eng.*`, unique non-empty)

| file | sids | non-empty | **unique** | chars | median | p90 | max | ≤25 ch | >140 ch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `eng.common` (UI) | 5,710 | 5,707 | **5,261** | 199,621 | 20 | 56 | 2,526 | 3,314 | 119 |
| `eng.subtitles` (story) | 60,882 | 58,353 | **30,415** | 908,831 | 25 | 55 | 166 | 15,731 | 14 |
| `eng.subtitles-systemic` (barks) | 32,809 | 32,432 | **11,687** | 340,253 | 23 | 56 | 202 | 6,645 | 7 |

**GLOBAL unique = 36,610 strings / 1,148,831 chars.** (Records total 99,401; subtitles and
systemic overlap by 10,737 identical strings, common vs subtitles by only 16.)

### Token inventory over all 36,610 unique strings — **remarkably clean**

| token | occurrences | distinct |
|---|---:|---:|
| `{...}` braces | **0** | 0 |
| `<...>` tags | **0** | 0 |
| `&entity;` | **0** | 0 |
| `[TOKEN]` | 252 | 62 (`[A]`, `[B]`, `[TEXT]`, `[TEXT2]`, `[GAME]`, `[crossed out]`, …) |
| printf `%` | 8 | 7 (`%d`, `%m`, `%Y`, `%I`, `%M`, `%p`) |
| newline `\n` | 175 | 1 |
| `$H` | 1 | 1 |

Long UI blocks (patch notes / privacy policy, up to 2,526 chars) use a literal `\` as their line
separator — preserve it.

---

## 9. SID parity — 100 %, and a free 22-language reference panel

Every one of the 23 languages has **exactly the same sid set** as English in **both**
`.common` (5,710) and `.subtitles` (60,882) — **100.0 % match, all 23**.

⇒ EN→Hebrew maps by sid with zero ambiguity, **and** the New-Era panel
([[new-era-doctrine]]) is free: every line already exists in 22 other languages.

**Gender oracle is unusually rich** (no Arabic here, so use the game's own gendered locales,
per `universal/GENDER_ORACLE_ROLLOUT.md`): **rus** + **pol** + **cze** give speaker *and*
addressee gender from the past tense; **fre / ita / spa / sas / por / bra / gre** give referent
gender from adjective/participle agreement. ~10 gendered languages joined by sid.

---

## 10. Tools / artifacts produced

```
games/uncharted_lot/
  tools/unc_loc.py          NEW  — ND string-table codec, auto-detects 8 vs 16 B records
  extract/lang/             48 files — every language's .common/.subtitles + sid-lookup
  extract/fonts/            18 files — all .fnt descriptors + .tga atlases
  extract/ui/               fontlib.swf, fontlib-universal.swf, fmenu.swf, sp-hud.swf, *.iggy
  RECON.md  FEASIBILITY.md  PIPELINE.md
```

Reused **unchanged** from `games/tlou1/tools/`: `oodle.py`, `psarc.py`, `psarc_write.py`.
Run everything with the repo `.venv` python and
`TLOU_OODLE_DLL="F:/Game Lab/UNCHARTED - Legacy of Thieves Collection/oo2core_9_win64.dll"`.

## מסמכים קשורים
- באותה תיקייה: [[games/uncharted_lot/FEASIBILITY|FEASIBILITY]], [[games/uncharted_lot/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#uncharted_lot|CLAUDE_INDEX_games]]
