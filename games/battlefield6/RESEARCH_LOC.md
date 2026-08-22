# Battlefield 6 — Localization-format research (loc CAS)

**Session goal:** crack/find BF6's dedicated localization format (the wall the recon hit — text
is NOT in the bundle/`.toc` asset system), decide whether the single-player build is an easier
target, and scope the rest. Read-only: all analysis ran on a scratchpad **copy** of the game
files; nothing in the install was written, no build was launched, no anti-cheat touched.

---

## VERDICT: 🟡 PARTIALLY CRACKED — format family + decode algorithm + section map are solved; one focused RE task (rebuild the Huffman tree from the symbol table) remains before strings decode

This is a **major downgrade of the risk** from the recon's "research-grade, zero reference code,
no community precedent". The loc format is now positively identified as a member of the
**well-documented Frostbite Huffman localized-string family**, the exact decode algorithm is in
hand (FrostyToolsuite source), the file's internal sections are mapped by byte offset, and — the
key practical win — **the whole English corpus can be extracted by SEQUENTIALLY decoding the
bitstream (strings are NUL-terminated in the Huffman stream), without needing the id→offset
table at all.** What is NOT yet done is reconstructing BF6's *specific compact tree encoding*
(it stores a symbol/alphabet table + code lengths, not the older uint32 `~char` node array), and
the write/repack path.

Confidence: **high** on the format family and section map (multiple independent confirmations);
**medium** on exactly how the tree/code-lengths are packed in the ~0x20–0x310 header (needs one
more focused pass).

---

## 1. Where the loc data actually lives (install layout)

Main install: `Game Lab/Battlefield 6/`. The **only** text language pack on disk is English:

```
Data/Win32/installation/commonbase/
    cas_01.cas … cas_10.cas   (~9.8 GB, the base-game payload; chunk-header + RIFF/EBX)
    en/
        cas.digest            (1028 B)
        cas_01.cas            1,155,072 B  ← THE LOCALIZATION FILE (this whole document)
        loc/en.toc            620 B  empty stub (0 bundles / 0 chunks)
        SP/loc/en.toc         620 B  empty stub — BYTE-IDENTICAL to en/loc/en.toc (md5 2db545fa…)
    voen/                     English voice-over (irrelevant)
```

- **`ar` is NOT present locally** — only `en` + `voen` exist under `commonbase/`. A structural
  `en`-vs-`ar` diff-crack is therefore **not possible on this repack**; it needs the ArabicSA
  language pack downloaded first (recon Phase-2 prerequisite, still open).
- Both loc `.toc` files (`en/loc/en.toc` and `en/SP/loc/en.toc`) are the same 620-byte empty
  stub, confirming the recon: the text is **not** indexed through the `.toc`/bundle system. It is
  the raw `en/cas_01.cas` that the engine's dedicated loc subsystem reads directly.

---

## 2. The single-player build IS the easier deploy target (but shares the same loc file)

```
Game Lab/Battlefield 6/SP/
    bf6.exe            176,898,408 B  (main build's bf6.exe = 188,775,272 B — different binary)
    oo2core_9_win64.dll, oo2ext_9_win64.dll   ← ships Oodle directly
    steam_api64.rne, steam_emu.ini            (RUNE crack)
    x64/               (crack payload)
    NO Data/ folder at all
    NO EAAntiCheat.* files   ← the main build root HAS EAAntiCheat.GameServiceLauncher.{exe,dll}
```

- **The SP build has its own `bf6.exe` and ships ZERO EA AntiCheat binaries** (the main build
  ships them in its root). ⇒ a **single-player-only Hebrew mod dodges the anti-cheat question
  entirely** — the acceptable, lower-risk outcome the brief allows for.
- **BUT the SP build has no `Data/` directory** — it shares the main `Data/` tree. The SP-specific
  loc stub (`commonbase/en/SP/loc/en.toc`) is an empty 620-byte stub identical to the MP one, and
  there is no separate SP loc CAS. So **SP and MP read the same `commonbase/en/cas_01.cas`.**
- **Implication:** SP does **not** reduce the cracking effort (same 1.15 MB Huffman file), and it
  is **not** smaller/simpler/uncompressed. Its only advantage is **deployment**: patch the shared
  loc file, launch the SP `bf6.exe`, no anti-cheat in the loop. That is a real advantage and makes
  SP the target to aim at once the format is cracked.

---

## 3. `en/cas_01.cas` — concrete byte-level structure (the core finding)

File size **1,155,072 B (0x11A000)**. Content ends at **0x119CCF**; 0x119CD0→EOF is zero padding.
Entropy is ~7.9 across the whole body **except** the small header region — i.e. the bulk is a
near-random Huffman bitstream.

### Section map (offsets confirmed by hex inspection)

| Region | Offset | What it is | Evidence |
|---|---|---|---|
| Header | `0x00`–`0x1F` | 8× uint32 fields (counts/offsets) | `0x00` LE = **256**; `0x1C` LE = **1057**; other fields not yet field-mapped |
| **Symbol/alphabet table** | `~0x24`–`~0xA6` | The Huffman **symbol set**, ~130 symbols | BE u16 codepoints for ≥0x100: `2018`(’) `2013`(–) `2022`(•) `2026`(…) `201D`(”) `201C`(“) `2114`(№) `0141`(Ł) `0142`(ł) `011E`(Ğ) `2204`(∄) `0105`(ą) `0106`(Ć) `0143`(Ń) `015A`(Ś) `0179`(Ź) `010C`(Č) **`300D`(」) `3000`(　)** …; then Latin-1 (0xA0–0xFF: © ® ° · À…ü) packed as single bytes |
| Tree / code-lengths + histogram residue | `~0xA6`–`~0x30C` | The Huffman tree encoding (compact) + a shipped **histogram-builder debug dump** | Recurring 16-byte signature `00 01 00 00 11 70 .. 8C 06 .. FF FF` at file start and repeating at 0x290–0x310; plaintext debug string at **0x2CF**: `"   Entry = 0x300d   Char = '_'  Frequency =     1 ( 0.00%)\n"` |
| **Huffman bitstream** | `~0x310`–`0x119CCF` | The compressed strings (the bulk, ~1.153 MB) | One contiguous 7.9-entropy blob, no internal structure |
| Padding | `0x119CD0`–`0x11A000` | zeros | — |

### Why this is the Frostbite Huffman loc family, not a novel format

1. **The symbol table contains `0x300D` (」)** — exactly the `Char` in the recon's debug string
   `"Entry = 0x300d Char = '_' Frequency = 1"`. That string is a **Huffman frequency-histogram
   dump** ("Entry = <codepoint> Char = <symbol> Frequency = <count> (<pct>)"), the canonical
   build-time artifact of a Frostbite localization "histogram chunk". The recon's guess ("the text
   is Huffman-coded") is **confirmed**.
2. The symbol set (European accented Latin + typographic punctuation `’–•…""` + a little CJK
   punctuation `」　`) is exactly the alphabet a Frostbite multi-language loc corpus builds its
   Huffman tree over.
3. The structure (symbol/histogram table → tree → NUL-terminated Huffman-coded strings) matches
   the documented Frostbite loc resource family (see §4).

### The one difference from the documented variants (the remaining RE task)

BF6 does **not** store the tree as the older BioWare/standard "uint32 array where each value =
`~char`" node list — a scan for a contiguous run of `0xFFFF????`/small uint32 values found
**none**. Instead BF6 stores a **compact symbol table** (the codepoint list at 0x24) plus (almost
certainly) a **code-length table** — i.e. a **canonical-Huffman** representation. Rebuilding the
decoder therefore needs: parse the symbol list → parse the per-symbol code lengths → assign
canonical codes → decode. That header parse (the ~0xA6–0x30C region) is the single unsolved piece.

### The practical shortcut for reading the corpus (no id table needed)

Individual strings terminate at the Huffman **letter 0x00** (the end-delimiter node — see §4). So
once the tree is rebuilt, the **entire English corpus can be dumped by sequentially decoding the
bitstream from its start bit-offset, string after string, until 0x119CCF** — the string-id→offset
table is only needed to *key* strings for targeted replacement, not to *read* them. No trailing
id→offset table with recognizable `{id, monotonic-offset}` structure was found in the tail
(0x118000–0x119CCF is pure bitstream), so the id map is either compact in the header or a separate
resource — a Phase-2 concern, not a blocker for corpus extraction.

---

## 4. Prior art — the exact decode algorithm and the tool family (URLs)

The authoritative implementation is **FrostyToolsuite** (`FrostySdk/Utils/HuffmanDecoder.cs`).
Confirmed algorithm (identical in spirit to the bundle-name `read_huffman_string` already ported
in `tools/bf6_toc.py`):

- **Tree table** = array of `uint32` nodes, read in pairs; a leaf's letter = `~value` (bitwise
  NOT); internal nodes get sequential values `0,1,2,…`; nodes are de-duplicated by value; the
  **last-built internal node is the root**. Special leaves: `0xFFFFFFFF` → letter `0x00`
  (**string terminator**), `0xFFFFFFF5` → newline `0x0A`.
- **Bitstream** = array of `int32`; bit `i` = `(data[i/32] >> (i%32)) & 1`, i.e. **LSB-first per
  32-bit word**. Walk root→leaf: bit 0 = Left, bit 1 = Right. Append `~value`; stop at `0x00`.
- **Endianness varies** between the tree and the data (Frosty tests read data little-endian, tree
  big-endian for one sample) — must be brute-checked per file.

The **container layout** is documented verbatim in FrostyToolsuite's BioWare plugin file
**`BW LocaliziationResourceBits.txt`** — header (`uint magic`, `uint nodeCount`, `uint nodeOffset`,
`uint stringsCount`, `uint stringsOffset`) → HuffmanCoding (`nodeCount × uint = ~char`) → StringData
(`stringsCount × {uint stringId, int bitOffset}`) → Strings (the bitstream). BF6's header magic
differs (BF6 starts `00 01 00 00`, BioWare uses `0xd78b40eb`) and BF6 uses the compact
symbol+code-length form, but **the string/tree/id-table triad is the same family**.

**Sources / tools that handle this format family:**
- **FrostyToolsuite/FrostyToolsuite** — `FrostySdk/Utils/HuffmanDecoder.cs`, `HuffmanEncoder.cs`,
  `FrostySdkTest/Utils/HuffmanCodingTests.cs` (the decisive files; give the exact algorithm + a
  worked encode/decode round-trip): <https://github.com/FrostyToolsuite/FrostyToolsuite>
- **CadeEvs/FrostyToolsuite** (branch `1.0.6.3`) — `Plugins/BiowareLocalizationPlugin/` incl.
  **`BW LocaliziationResourceBits.txt`** (byte-layout doc) and
  `LocalizedResources/LocalizedStringResource.cs`; also `Plugins/Fifa/LegacyDatabasePlugin/HuffmanTree.cs`
  (FIFA histogram-tree variant): <https://github.com/CadeEvs/FrostyToolsuite/tree/1.0.6.3/Plugins/BiowareLocalizationPlugin>
- **VNNCC/FbLocalization** — editor for a *simpler, uncompressed* Frostbite loc variant
  (magic `0x39000`, hash-pair list + C-strings; README explicitly notes it lacks histogram/Huffman
  support, so **not** BF6's variant but useful for the id/hash-pair concept):
  <https://github.com/VNNCC/FbLocalization>
- **NFSToolHB** (search result "decompile/compile localization binary + histogram chunk files;
  handles character encoding") — the histogram-aware variant; the exact owner/repo could not be
  resolved via the API this session (GitHub code-search needs auth) — worth locating next session.
- **majomix/frostbite-localization-tools** — a Frostbite **filesystem** tool (bundles/chunks/
  LZ4/Zstd), *no* loc-Huffman handling — not relevant to the string format:
  <https://github.com/majomix/frostbite-localization-tools>

**No BF6-specific text/translation mod or thread was found** (English search). BF6 is Nov-2025 and
FMT's BF6 profile is "EARLY WIP / CanLaunchMods:false", so no community loc mod exists yet.
Russian (zoneofgames.ru) / Chinese / Arabic searches were not exhausted this session (budget);
the ArabicSA community angle remains the most promising un-searched lead.

---

## 5. Scope of the rest (honest)

- **Corpus size estimate:** bitstream ≈ `0x119CCF − 0x310` ≈ **1,153,471 B ≈ 9.23 M bits**. With a
  ~130-symbol English alphabet, average Huffman code ≈ 4.3–4.8 bits/char ⇒ **~1.9–2.1 M decoded
  characters**. At a UI+subtitle average of ~40 chars/string that is **roughly 45,000–55,000
  strings** — a **FLEET-scale corpus** comparable to Witcher 3 / Skyrim. (This one file serves
  both MP and SP, since they share `Data/`.)
- **`ToCSig` write gate:** unexplored, and note it is **not even the relevant gate here** — the
  loc file is `en/cas_01.cas`, a raw CAS blob, **not** a `.toc`, so it carries no `ToCSig` at all.
  The real open questions are (a) whether `cas.digest` (1028 B, sits beside the loc CAS) is a
  content hash the game verifies at load, and (b) whether editing a CAS blob in place is accepted.
  Both are single-player-testable and untested.
- **`BFText-Regular-AR` font:** it is **not** a standalone TTF on disk. Per the recon it is a
  Frostbite font **resource** (`resType 104436933`, referenced by path
  `Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR` inside the
  `fontconfiguration_languageformat_arabicsa` bundle in `ui.toc`), whose pixel/glyph data is a
  larger compressed entry in the big `commonbase` CAS. Reading it needs Oodle (ships:
  `oo2core_9_win64.dll`) + cracking that resType's internal atlas/glyph format — a separate
  proprietary-font sub-project (unstarted), and Hebrew (U+05D0–05EA) coverage is unknown until
  then. There is a real Arabic face, so the Arabic-slot hijack has a font to ride; whether it
  contains Hebrew glyphs is the open font question.

---

## 6. Ranked next-step plan (with effort estimates)

1. **Crack BF6's compact tree/code-length header (0x24–0x30C)** — parse the symbol table, find the
   per-symbol code-length table, assign canonical Huffman codes, and decode. Validate by
   sequentially decoding the bitstream from its start bit-offset and checking for readable English.
   **This is the single gate between "partial" and "corpus in hand".** Effort: **1 focused session**
   (medium RE; the algorithm and validation oracle — readable English — are both known). Fastest
   path: also try locating **NFSToolHB**'s histogram+binary source, which handles exactly this
   histogram variant and may hand over the tree encoding directly.
2. **Sequential corpus dump** — once #1 decodes one string, dump all ~50k strings in order. No id
   table needed. Effort: **hours** after #1. Produces the translatable corpus for the fleet.
3. **String-id keying** — locate the `{stringId, bitOffset}` map (compact in the header, or a
   companion resource) so each Hebrew line can be written back to the right entry. Effort:
   **0.5–1 session**. Only needed for the write path, not for reading/estimating.
4. **Write/repack + `cas.digest` gate** — build a modified `en/cas_01.cas` (re-Huffman-encode with
   the same tree, or extend the tree for Hebrew symbols U+05D0–05EA + RTL controls), determine
   whether `cas.digest` or a load-time hash rejects it. Test on the **SP build** (no anti-cheat).
   Effort: **1–2 sessions** (includes the encoder, which FrostyToolsuite's `HuffmanEncoder.cs`
   already implements as a reference).
5. **Font** — crack the `BFText-Regular-AR` resType `104436933` atlas format, check Hebrew glyph
   coverage, inject if missing. Effort: **its own sub-project** (comparable to the dedicated font
   work other games in this repo needed); gated behind Oodle wiring (trivial — DLL ships).
6. **Deploy to SP + in-game verify** — patch the shared loc file, launch the standalone `bf6.exe`
   (no EA AntiCheat), screenshot. Effort: **user-driven** (project rule: no autonomous launch).

**Bottom line:** the recon's "genuinely harder, open-ended, no reference code" wall is now a
**bounded, well-referenced RE task** — one session to a decodable corpus, and the single-player
build gives a clean anti-cheat-free deployment path once the format is cracked.

## מסמכים קשורים
- באותה תיקייה: [[games/battlefield6/FEASIBILITY|FEASIBILITY]], [[games/battlefield6/PIPELINE|PIPELINE]], [[games/battlefield6/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#battlefield6|CLAUDE_INDEX_games]]
