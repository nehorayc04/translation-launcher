# Assassin's Creed II — Hebrew translation RECON

Concrete, locally-verified findings (2026-06-18). Game install:
`D:\Games\Assassin's Creed II` (Ubisoft Montreal, 2009/2010 PC, **Scimitar engine**).

---

## 1. Engine / archive format — `scimitar` v25

All game data lives in `.forge` archives. Header: `b"scimitar"` + `\x00` + `u32
version = 25` (AC Shadows = v42; this is the OLD generation). Verified on every
forge in the folder.

`tools/ac2_forge.py` is a working, pure-Python **read-side** parser (no deps):

```
Header @0x00: "scimitar"\0 + u32 ver + i64 index_offset
Index hdr @index_offset: u32 N (resource count) + ... + i64 record_ptr @+0x30
Record table @record_ptr: N × 16 bytes = [i64 data_offset][u32 hash/misc][u32 SIZE]
  - data_offset is 0x800-aligned (padded on disk); the u32 SIZE field is the
    true byte length (do NOT derive size from next offset).
Each resource starts with: "FILEDATA"(8) + char[128] name + payload.
  - Names are read authoritatively from these FILEDATA headers (clean), not from
    the 188-byte descriptor table (which carries a hash prefix on some entries).
```

CLI: `python tools/ac2_forge.py <forge> list|grep <s>|extract <name> <out>`.
Verified: extracts `LocalizationPackage_English` (145,887 B) and every font
atlas correctly; the FILEDATA name inside each blob matches.

## 2. Where the text is — `DataPC.forge`

`DataPC.forge` (171 MB, 81 resources) holds the localization as per-language
sub-resources:

- `LocalizationPackage_<Lang>`          — UI / menu / item / document text
- `LocalizationPackage_<Lang>_Subtitles` — dialogue subtitles

**14 languages present**: English, French, Spanish, Spanish(Spain), Italian,
German, Dutch, Polish, Danish, Norwegian, Swedish, Korean, Chinese(Tra),
Chinese(Chs). **NO Arabic, NO Hebrew, NO Persian** (0 hits) — confirmed by scan.
→ The CP2077/SM2/WD2/GoWR "Arabic-slot hijack" does NOT apply here. We must
**hijack an existing LTR slot** (e.g. English, or a language the user won't use)
AND solve RTL ourselves (§5).

### LocalizationPackage payload format (decoded read-side, NOT yet repacked)

After the `FILEDATA`+name(128) header: a Scimitar-serialized object. Observed:
- Scimitar class-IDs (e.g. `0x1004FA99`) and the resource hash (`0x176CE0F5`,
  equal to the record's hash field) embedded near the top.
- The strings are a **char-INDEX serialization**: each line is `[u32 key_hash]
  [u32 char_count][char_count × u16 index]` where each u16 is an index into a
  character table (NOT raw UTF). High-byte clustering (0xF1–0xF7) = the index
  space. There are checksums on the data file.
- This char-index + checksum machinery is exactly the part community tools call
  the "hard" / "unsolved-in-public" repacker. **We do NOT hand-roll the write
  side** — AnvilToolkit exports/imports it as XML (§4). A from-scratch Python
  repacker is a documented future option (the read decode is well under way).

## 3. Where the font is — `DataPC_extra.forge`

`DataPC_extra.forge` (107 MB, 1213 resources) holds the fonts as **per-script
texture atlases** named `*_<Script>CharacterSet_1_MapDesc` (a `FILEDATA` texture
resource, editable as DDS via AnvilToolkit + the bundled `texconv.exe`):

- `AC2Aaux_ProBold_Latin_1_MapDesc`, `..._ProMedium_Latin_1_MapDesc`, `..._ProLight_Latin_1`
- `AC2Aaux_ProBold_Numbers_1_MapDesc`
- `AC2Aaux_ProBold_RussianCharacterSet_1_MapDesc`   ← **Cyrillic = a non-Latin script the engine already renders**
- `..._KoreanCharacterSet_1`, `..._JapaneseCharacterSet_1`, `..._TraChineseCharacterSet_1`, `..._SimChineseCharacterSet_1`
- Plus full-glyph CJK/Cyrillic atlases (`MDChamGothic_PS3_Korean…`, `DFPSoGei-W5_Japanese…`, `UbiGame_Text_TMP3_Russian…`).

**Key de-risk:** the engine has a working *CharacterSet* mechanism for non-Latin
scripts. Hebrew has no atlas, so we either (a) draw Hebrew glyphs over unused
Latin slots in `..._Latin_1_MapDesc` (the Persian-patch method), or (b) replace a
CharacterSet atlas we don't need (e.g. Korean/Japanese) with Hebrew glyphs and
map the loc indices to it. Either way: **no shaping needed** (Hebrew doesn't join).

## 4. Toolchain — AnvilToolkit (already on this machine)

`C:\Users\Nehoray_Cohen\Downloads\AnvilToolkit_Release_v1.2.10…\AnvilToolkit.exe`
(2 copies, v1.2.10). The proven, free, AC2-capable round-trip tool. From the
README/changelog:
- Unpacks/repacks `.forge` and `.data` (Ezio-trilogy repack restrictions removed
  in 1.2.5; AC1–Rogue supported).
- **Export `LocalizationPackage` → XML, edit, import new XML** (since 1.1.0) —
  this hides the char-index/LZO/checksum machinery.
- **Texture viewer** → export/replace DDS (uses bundled `Utils/texconv.exe`).
- `Lists/AC2.gfl` = AC2 name→hash file list.
- **GUI only** — no documented CLI. So the container/loc/texture round-trip is a
  user-assisted GUI step; our Python does the content transforms around it.

## 5. RTL — the engine has NO bidi; bake direction into the data

Proven by the existing **Persian (Farsi)** AND **Arabic** fan-translations of AC2
(both translate menus/UI). Their documented method: reshape (Arabic only) + **pre-
reverse the line visually** at build time, so the LTR engine paints correct RTL.
Hebrew needs **only the visual reversal** (no joining).

`work/ac2_rtl.py` `to_visual(logical_he)` implements this (zero deps, unit-tested):
protect tags/placeholders → reverse → un-reverse LTR runs (numbers/Latin/tokens
stay forward) → mirror brackets → restore tokens. Self-test PASS (7/7).

## 6. No prior art to inherit, but a clear precedent

No Hebrew AC translation has ever existed (PCGamingWiki Hebrew list = 0 AC games).
Persian + Arabic AC2 patches prove the full chain works on this exact engine.
This would be the first Hebrew one.

## מסמכים קשורים
- באותה תיקייה: [[games/assassinscreed2/FEASIBILITY|FEASIBILITY]], [[games/assassinscreed2/FORMAT|FORMAT]], [[games/assassinscreed2/PIPELINE|PIPELINE]], [[games/assassinscreed2/RESEARCH_SMALLSIZE|RESEARCH_SMALLSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#assassinscreed2|CLAUDE_INDEX_games]]
