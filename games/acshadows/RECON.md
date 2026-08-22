# Assassin's Creed Shadows — Hebrew translation RECON

Empirical facts gathered directly from the local install at
`C:\Games\Assassin's Creed Shadows` (2026-06-17). Everything here is
**verified on disk**, not assumed. Feasibility verdict + the full recipe are in
[FEASIBILITY.md](FEASIBILITY.md) / [PIPELINE.md](PIPELINE.md).

## The install
- **Engine:** Ubisoft **Anvil** (the AC Origins → Odyssey → Valhalla → Mirage →
  Shadows lineage). Released March 2025.
- **Size:** ~142 GB across **99 `.forge` archives** (`DataPC_*.forge`) + loose
  `resources/`, `videos/`, two exes (`ACShadows.exe`, `ACShadows_Plus.exe`).
- **Archive format — `scimitar` v42.** Every forge starts with the magic
  `b"scimitar\x00"` (9 bytes) then `uint32 LE version == 0x2A (42)` at offset 9.
  Confirmed identical across `DataPC_AnimusRoom`, `DataPC_shared_00`,
  `DataPC_boot_dx12`. **Version 42 is the AC Shadows generation** — older AC
  titles use lower scimitar version numbers, so a forge tool MUST support v42.
  (Probe: `tools/acs_forge_probe.py header "<forge>"`.)
- **Forge content is COMPRESSED.** A raw ASCII/UTF-16 scan of `DataPC_shared_00`
  returns only garbage fragments in the data region — the resource payloads are
  packed (Oodle/LZ4/Zstd — exact codec is in the tool research). Only an
  **uncompressed Anvil reflection type-name table** near the tail is plaintext
  (e.g. `DialogueGraph`, `LocationNode`, `VoiceAnimDataByOasisID`). ⇒ The
  localization text is **not** plaintext-scannable; it must be extracted +
  decompressed by a v42-capable forge tool.

## Localization system — "Oasis" string IDs (CONFIRMED)
The Anvil type table contains **`VoiceAnimDataByOasisID`** and a large family of
`Dialogue*` types. This confirms AC Shadows uses Ubisoft's **Oasis** localized
string system — strings keyed by an **Oasis ID** — the SAME localization family
as Watch Dogs 2 (`oasisstrings`). The proven WD2/universal-playbook oasis
approach is the right mental model: extract the Oasis string table, fill the
target-language slot, repack.
- The loc string table is **not** in `DataPC_shared_00`; it most likely lives in
  the 20 GB `DataPC_boot.forge` (+ its patch forges `DataPC_boot_patch_0{1,2}`).
  Pinning the exact container is the first extraction task.

## 🟢 Font — Hebrew renders natively, NO font work needed
The loose UI fonts in `resources/` are Monotype **AvenirNextWorld** (the global
superfamily) + CJK fonts (DFKai, HeiSei Gothic, KingGothic JP, NotoSans KR).
`fontTools` analysis of `AvenirNextWorld-Regular.ttf`:

| Script | Glyphs in cmap |
|---|---:|
| Latin A–z | 58 |
| **Hebrew U+0590–05FF** | **52 (full alphabet + finals + niqqud)** |
| Arabic U+0600–06FF | 104 |
| Arabic presentation forms (shaped/joined) | 133 |
| Cyrillic | 256 |

⇒ The shipped UI font **already contains the complete Hebrew alphabet**, and the
presence of Arabic **presentation forms** proves the engine does Arabic
**shaping/RTL**. This is the single biggest de-risk vs. every prior game:
- CP2077 needed the Arabic CR2W slot; SM2 needed Heebo glyph surgery; WD2 needed
  a hand-built Hebrew font atlas. **AC Shadows needs none of that** — Hebrew text
  routed through the Arabic RTL pipeline should render with the stock font.

## Language configuration — plain-text codes
`%USERPROFILE%\Documents\Assassin's Creed Shadows\ACShadows.ini`:
```ini
[Language]
Client=en-US
Text=en-US
Sound=en-US
Subtitles=en-US
```
Language is selected by **human-readable locale codes** (`en-US`, …) in the ini,
not a binary blob — so flipping `Text=`/`Subtitles=` to the Arabic code is a
trivial text edit. (The 23-byte root `localization.lang` `b"LANG..."` is a
separate small pointer/version stamp — not where strings live.)
- **Audio** ships for `bra, eng, fre, ger, ita, jap, spa` only (the
  `DataPC_*_sound_<lang>` forges). Audio is irrelevant to a TEXT translation —
  we keep English (or Japanese) voice and swap only on-screen text.
- **OPEN (tool research):** the exact Arabic text-locale code AC Shadows accepts
  (e.g. `ar-AE`) and whether the Arabic text slot is present in the loc data /
  selectable even if the menu hides it. AC **Mirage** (prior Anvil title, set in
  Baghdad) shipped Arabic text — the engine path almost certainly exists.

## Tooling present on this machine
- `fontTools 4.63.0` (font analysis ✓), Python 3.13.
- `tools/acs_forge_probe.py` — read-only forge inspector built this session
  (`header` / `strings` / `survey`). Confirms format; does NOT extract
  (compression) — a real v42 forge extractor/repacker is the next acquisition.

## Tooling progress — format partly cracked + Oodle in hand (2026-06-17)
Built + verified locally this session (the build-our-own repacker path, like
WD2/GoWR/AC2):
- **Oodle codec SOLVED** (`tools/acs_oodle.py`). Wrapped `oo2core_9_win64.dll`
  (borrowed from `C:\Games\Battlefield 6`; the game ships none) via ctypes —
  `OodleLZ_Compress` + `OodleLZ_Decompress`. Round-trip identical, and our Kraken
  output's **lead byte is `0x8C`, byte-identical to the forge data blocks**. So we
  can both decode AND re-encode forge payloads; the "Oodle is the wall" blocker is
  gone, and the encoder is format-compatible.
- **v42 forge TOC reader VERIFIED** (`tools/acs_forge.py list/raw/verify`). Index:
  `u64 index-ptr @ offset 13` → `u32 count @ idx+0x0C`, `u32 record-array-ptr @
  idx+0x28`; **24-byte records** `{u64 offset, u32 timestamp, u32 flags, u32 size,
  u32 nameHash}`. Proven by the cumulative-offset invariant `off[n+1]==off[n]+size[n]`
  holding **100%** on 4 forges: AnimusRoom (102/102), shared_00 **(35,076/35,076,
  2.2 GB)**, boot_dx12 (171/171). Enumerates every resource in any forge.
- **Resource sub-container CRACKED** (`tools/acs_forge.py extract / decode-stats`).
  Each resource blob = a sequence of chunks; chunk header is a fixed **0x1F bytes**:
  `u32 magic 0x57FBAA33 · u32 0x1004FA99 · … · u32 uncompressedSize @+0x13 · u32
  compressedSize @+0x17 · u32 checksum @+0x1B · payload @+0x1F` (payload Oodle-Kraken,
  or stored raw when comp==uncomp). Walk chunks → Oodle-decode → concatenate =
  the raw Anvil resource. **Verified: 98/103 AnimusRoom resources fully decode**
  (766,934 bytes). ⇒ **the full READ path is proven end-to-end** (TOC → resource →
  chunk → Oodle → bytes). The ~5% misses are chunk-header variants to refine.
- **✅ LOC PACKAGE FOUND + REAL STRINGS DECODED (2026-06-17).** `DataPC_boot.forge`
  resource **idx 36626** (nameHash **`0xa5b3bea0`**, ~34 MB on disk; appears twice =
  base+patch dup) is the localization package. It is a LARGE multi-block resource:
  after a small chunk0 (974 B) the big chunk holds a **block table** of 215 entries
  `{u32, u32 uncompressedSize}` (214×262144 + 194728 = **56,293,544 B total**), then
  the per-block Oodle streams, each preceded by an inline `{u32 compSize, u32 checksum}`
  header. **Block 0 decoded to 262,144 bytes of real content** incl. the quest string
  `Thepathofvengeance_Naoediscoversfluteismissing_0xAC4BDB1D26A8A81D` + `Script`. ⇒ the
  whole read chain (TOC → resource → block table → Oodle → AC Shadows loc text) is
  PROVEN on the real loc package.
- **✅ FULL MULTI-BLOCK DECODE + REAL DIALOGUE TEXT READ (2026-06-17).** A robust walk
  (binary-search each block's compressed length, forward-scan past the small variable
  inter-block headers) decoded **all 134 blocks of resource 36626 → 35,127,296 bytes**,
  consuming the entire resource. The translatable text is stored **UTF-16LE**, keyed by
  Oasis IDs (`0xAC4BDB1D…`). Real lines recovered verbatim: *"Don't be mad."*, *"I really
  did try my best."*, *"Can you play something, Naoe? Please?"*, *"It would seem Junjiro
  has a knack for mending things…"*. ⇒ **the READ path is COMPLETE end-to-end on actual
  translatable game text** — pure Python, home-built, no gated tool.
  (Header note: the per-resource `{count,blockSize}`/comp-table fields are NOT yet cleanly
  parsed — the walk is currently empirical, decode-until-end + binary-search-comp; fine
  for read, but the exact block-table layout must be nailed for clean WRITE.)
- **STILL TO DO (read polish):** parse the Oasis id↔UTF-16-string record layout to a clean
  `{oasisID: text}` table; confirm whether 36626 is the English package + locate the
  Arabic-slot package (the RTL skeleton to fill).
- **STILL TO DO (write — Part B):** nail the exact block-table + inter-block-header bytes,
  then repack (re-Oodle-encode blocks — encoder already in hand — rebuild the table, fix
  the forge TOC size/offset) and prove a repacked forge loads past Denuvo integrity.

## The one thing that decides GO/NO-GO
A **working forge REPACKER for scimitar v42** + the game **loading a modified
forge past Denuvo/file-integrity**. Extraction of older AC forges is solved;
*repacking the 2025 v42 generation and getting it to load* is the open risk the
research workflow is resolving. Font + locale-config + oasis-system are already
green.

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FEASIBILITY|FEASIBILITY]], [[games/acshadows/FORMAT|FORMAT]], [[games/acshadows/PIPELINE|PIPELINE]], [[games/acshadows/PLAN_HEBREW|PLAN_HEBREW]], [[games/acshadows/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
