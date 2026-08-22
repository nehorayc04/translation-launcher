# Far Cry 5 — RECON

**Install:** `F:\SteamLibrary\steamapps\common\FarCry5` (Steam appid **552521**)
**Engine:** Ubisoft **Dunia / "Fire"** (2018) — `bin\FC_m64.dll` (250 MB), exe `bin\FarCry5.exe`
**Proposed `games.id`:** `farcry5` · detector exe `FarCry5.exe`, marker dir `data_final\pc`
**Sibling already cracked in this repo:** Far Cry 6 (`games/farcry6/`) — same container family.

---

## 1. Container — Dunia **FAT2 version 10**

`data_final\pc\*.fat` + sibling `.dat`. Magic `2TAF` (= "FAT2"), **version 10** (FC6 = 11).

Header is **byte-identical in shape to FC6's v11**:

| off | field |
|---|---|
| 0 | u32 magic `0x46415432` |
| 4 | u32 version = **10** |
| 8 | u32 platform (1 = PC) |
| 12,16 | u32 0, u32 0 |
| 20 | u32 entryCount |
| 24 | entries × 20 B |
| tail | u32, u32 subfat counts |

**Entry = 20 B (5 × u32).** The only real delta vs FC6 is the offset/size packing:

```
a  = NameHash high 32          (hash halves stored HIGH word first)
b  = NameHash low 32
c  = (UncompressedSize << 2) | CompressionScheme(2 bits)
dd, e:
    v10 (FC5):  off  = (e >> 29) | (dd << 3)      # BYTE-granular, spans 35 bits
                comp = e & 0x1FFFFFFF             # 29 bits
    v11 (FC6):  off  = ((e >> 29) | (dd << 3)) << 4   # 16-byte aligned
```

**Proof the v10 packing is right** — `max(off + comp)` equals the `.dat` size **exactly, to the
byte**, with **0 overflows**, on three independent archives:

| archive | entries | .dat size | max(off+comp) |
|---|---:|---:|---:|
| `common.fat` | 3,401 | 182,265,474 | **182,265,474** |
| `patch_english.fat` | 53,574 | 404,322,380 | **404,322,380** |
| `worlds/farcry5_english.fat` | 184,281 | 2,217,809,078 | **2,217,809,078** |

The v11 packing overflows by 16× and the v9 packing misses — no ambiguity.
The 35-bit offset field is also *why* an 8.9 GB `patch.dat` is addressable at all.

**Schemes:** 0 = stored, 1 = LZO1x, 2 = LZ4 (one standard block over the whole entry).
Observed in FC5: only **0 and 2**. `games/farcry6/tools/fc6_fat.py` already carried a correct
`ver == 10` branch, so the FC6 reader runs on FC5 **unchanged**.

**Archive inventory:** 42 `.fat`, of which the ones that matter:
`common.fat` (3,401) · `patch.fat` (63,547, **overrides common**) · `worlds/farcry5.fat`
(292,148) · `worlds/installpkg.fat` (172,047) · per-language audio packs
`patch_<lang>.fat`, `worlds/farcry5_<lang>.fat`, plus `*_feminine` variants, 2 story DLCs
(`dlc_mars`, `dlc_vietnam`) and the Arcade editor (`ige.fat`, `igepatch.fat`).

### 🔴 The name hash — and a real bug this exposed
Name hash = **CRC64 (reflected, init 0) over the path lowercased with BACKSLASH separators**.

`games/farcry6/tools/fc6_crc64.py:name_hash()` does `path.lower().replace("\\", "/")` — the
**opposite** normalization, so it never reproduced a real hash. It was latent-only (FC6's deploy
uses a hardcoded constant and nothing else called it). Validated against FC6's own documented
oasis hash: only `lower + backslash` yields `0x14f790b7fb9610c2`. Fixed in
`games/farcry5/tools/fc5_crc64.py`.

---

## 2. Text — OASIS, and there are **two** oases per language

Found by name-hash probe (both live in `common.fat` **and** `patch.fat`):

```
languages/<lang>/oasisstrings.oasis.bin            <- UI / menus / system
languages/<lang>/oasisstrings_subtitles.oasis.bin  <- dialogue subtitles
```

**9 shipped text languages:** english, **arabic**, french, german, italian, spanish, russian,
brazilian, japanese.

### Format — identical to FC6 except ONE field
```
u32 version = 1
u32 sectionCount
Section:
    u32 NameCRC
    u32 StringCount
    [StringCount x { u32 Id, u32 SectionCRC, u32 EnumCRC }]     <-- 12 B   (FC6: 16 B, +u32 Extra)
    u32 CompressedValuesSectionsCount
    [ { u32 LastSortedCRC, s32 CompressedSize, s32 DecompressedSize, bytes } ]
inner (standard LZ4 block), values ordered by EnumCRC:
    s32 StringCount, [u32 SortedEnums], [s32 StringOffsets],
    [ { u32 id, utf-16le value, u16 0 } ]
```

`tools/fc5_oasis.py` implements it and **identity-rebuilds BYTE-IDENTICALLY for all 9 languages**,
with a hard "0 leftover bytes" assert on parse:

```
english   ver=1 sections=759 strings=17,815  identity=BYTE-IDENTICAL
arabic    ver=1 sections=759 strings=17,815  identity=BYTE-IDENTICAL
... (all 9)
```

---

## 3. Scope (measured, three honest numbers)

`patch` overrides `common`, so the effective corpus is their union with patch winning:

| oasis | common | patch | **effective** |
|---|---:|---:|---:|
| UI | 17,815 | 17,786 | **18,889** |
| Subtitles | 12,654 | 12,083 | **12,775** |

* key overlap between the two oases: **0**
* **records: 31,664** · **GLOBAL unique English strings: 25,095** · **chars: 2,320,899**
* UI: median 22 ch, p90 104, max 1,339 — 10,224 ≤25 ch, 1,092 >140
* Subtitles: median **106** ch, p90 199, max 1,973 — real dialogue
* corpus dumped to `extract/en_corpus.json`

**🔑 100 % key parity across all 9 languages** (12,775/12,775 on subtitles) ⇒ EN→HE maps 1:1 by
`(sectionCRC, id)`, and **8 oracle languages come free** for the New-Era method
(ar / fr / de / it / es / ru / br / ja).

### Tokens to preserve verbatim
| token | occurrences | distinct |
|---|---:|---:|
| `[TOKEN]` (`[STYLE_END]`, `[STYLE_ZETA_*]`, `[Quest_Generic]`) | 9,004 | 1,191 |
| `{n}` / `{TX_PCButton_*}` | 1,545 | 29 |
| literal `\n` | 2,338 | 1 |
| `%spec` (`%i %d %l %u`) | 120 | 17 |
| `<tag>` (`<br>`, `<GLITCH>`, `<img …>`) | 109 | 19 |
| `&#xA;` | 28 | 1 |

### More oases exist (scan still running)
A content scan for the oasis signature reports **52 blobs in `common.fat`, 172 in `patch.fat`,
40 each in the two story DLCs** — i.e. more than the 18 named above. Those extra blobs are the
per-DLC / per-mode oases and must be folded into the Phase-2 corpus before it is called complete.

---

## 4. Language / RTL slot — 🟢 Arabic is first-class

* The engine's language enum (extracted from `FC_m64.dll`) has **22 languages** ending
  `… russian, spanish, mexican, swedish, turkish, arabic, invalid_language`.
* `FC_m64.dll` exports a dedicated **`IsArabicUILanguage`** check — the engine has a real
  Arabic UI path (very likely RTL layout/mirroring), not just a font swap.
* The UI oasis itself contains the selector label `'Arabic'` (`sec=82c1dced id=874045`) plus
  `'Game language'`, `'Audio Language'`, `'Change the subtitle language'` ⇒ **the user can pick
  Arabic in-game, and text/audio are independent, so English VO is preserved for free.**
* Arabic **text** ships in `common.fat`/`patch.fat` (always installed). Arabic **audio** does
  not — irrelevant, we only need the text slot.

### How the game's own Arabic is stored (predicts the bidi class)
```
arabic standard-block chars : 463,531
arabic PRESENTATION forms   : 0
bidi control chars          : NONE
lines ENDING with . ! ?     : 4,198     (logical tell)
lines STARTING with . ! ?   : 10
```
⇒ the engine **shapes and reorders Arabic itself** — it has a full RTL pipeline, and its own
Arabic is stored **LOGICAL**. That is the AC-Mirage / Witcher-3-4.00 signature, where the RTL
pipeline turned out to be gated to the **Arabic script**, leaving Hebrew in storage order (which
is exactly why Far Cry 6 ended up VISUAL). **Prediction: VISUAL. The proof decides — not assumed.**

---

## 5. Font — 🟡 NOT a raw TTF; container not yet identified

A content scan for the sfnt magic (`\x00\x01\x00\x00` / `OTTO` / `true` / `ttcf`) anywhere in the
first 4 KB of every entry, with a table-directory sanity check + a real fontTools load, over
**~360,000 entries across `patch` · `common` · `ige` · `igepatch` · `worlds/installpkg` ·
`worlds/farcry5`** returned **0 fonts**. `FC_m64.dll` embeds **0** fonts either, and contains no
`.ttf` / `.otf` / `.ffd` / `.fnt` string.

What the DLL *does* contain:
```
..\..\..\..\fire\private\common\src\FontDescriptor.cpp
..\..\..\..\fire\private\common\src\DynamicFontContent.cpp
CFont   CFontBank   fontSize
.xbt  x41   (the Dunia texture container)
```
⇒ FC5 uses a proprietary `FontDescriptor` + `DynamicFontContent` font system, most likely a
glyph **atlas** (`.xbt` = TBX + DDS) plus binary metrics — the same shape as **Watch Dogs 2**
(also Ubisoft Dunia lineage), whose `.ffd` + `.xbt` SDF-atlas font is a **solved class in this
repo** (`games/watchdogs2/work/wd2_font.py`).

Since Arabic is a shipped, rendering locale, an Arabic-capable font certainly exists. Whether it
also covers Hebrew is what the deployed proof answers.

---

## 6. DRM / integrity — 🟢 clear

* No Denuvo on this build; Steam + Ubisoft Connect wrapper (`uplay_r1_loader64.dll`).
* No EAC / BattlEye (single-player + Arcade).
* Asset archives are edited, never the exe.
* The FAT has no whole-archive checksum, and appended data + a repointed entry re-read correctly
  (verified end-to-end offline).

---

## 7. Tooling built

| file | role |
|---|---|
| `tools/fc5_fat.py` | FAT2 v10 reader (fork of the FC6 reader) |
| `tools/fc5_crc64.py` | CRC64 name hash — **with the normalization bug fixed** |
| `tools/fc5_lzo.py` | LZO1x (scheme 1; unused so far) |
| `tools/fc5_oasis.py` | OASIS codec, 12-byte record; `parse` / `edit` / `flat`; identity BYTE-IDENTICAL ×9 |
| `tools/fc5_deploy.py` | append-relocate deploy, scheme-0; `pack_entry_v10` self-tested on 4,000 real entries |
| `work/scope.py`, `work/scope_full.py` | scope reports |
| `work/bidi_probe.py` | measures how the game's own Arabic is stored |
| `work/find_more_oasis.py` | name probe + content scan for extra oases |
| `work/find_fonts2.py` | sfnt hunt (unbuffered, progress-reporting) |
| `work/build_proof.py` | the Phase-1 menu proof — `--deploy` / `--revert` |

Run everything with the repo **`.venv`** python (`lz4`, `fontTools`, `python-bidi` live there).

## מסמכים קשורים
- באותה תיקייה: [[games/farcry5/FEASIBILITY|FEASIBILITY]], [[games/farcry5/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry5|CLAUDE_INDEX_games]]
