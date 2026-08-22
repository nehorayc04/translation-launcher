# Ghost of Tsushima Director's Cut — RECON (Phase 1)

**Install:** `F:\Games\Ghost of Tsushima DC` · exe `GhostOfTsushima.exe` (29 MB) · Steam appid **2215430**.
**Engine:** Sucker Punch proprietary (Ghost of Tsushima / inFamous lineage) · **PC port by Nixxes**.
**Crack:** RUNE (`steam_api64.rne` + `steam_emu.ini`, Goldberg-style Steam emu) → **DRM-free**. DirectStorage
(`dstorage.dll`/`dstoragecore.dll`) + FSR3/DLSS/XeSS present. **Detection key + Supabase `games.id` = `tsushima`**
(already wired in `translation_manager/game_detector.py`, `config.py`, `games.json`, `games_catalog.py` — the
launcher already detects the install).

## Container — DSAR → PSARC (IDENTICAL to TLOU Part II)
Every `cache_pc/psarc/*.psarc` has magic **`DSAR`** (not `PSAR`): outer **DSAR** = Nixxes "DirectStorage Archive"
(LZ4-block chunks, entry flags low-byte `0x03`) → inner **Sony PSARC v1.4** (comp field literal `zlib`, block
size `0x10000`, 30-byte TOC entries keyed by `md5(path)`, entry-0 = NUL-separated manifest). This is the **same
container stack as `games/tlou2`** → its reader/writer work on GoT with **zero code change**:
- reader `games/tlou2/tools/dsar.py` (`class Psarc2`) — validated on GoT (`list`/`extract`).
- writers `games/tlou2/tools/{psarc_write,dsar_write}.py` — round-trip PASS on GoT (see FEASIBILITY §repack).
- `music_*.psarc` are plain `PSAR` (audio) — ignore.
- ⚠️ Reader gap: `gapack_misc_b` has a DSAR padding-sentinel entry (`compType=254, cs=0`, literal `PADDING*`)
  that crashes `dsar.py` (lz4 on empty input). Guard before extracting such archives. `gapack_misc_l` (target)
  and `gapack_misc_p` are clean.

54 gapacks total (~51 GB): `gapack_bitmaps_*` (textures/fonts), `gapack_meshes`, `gapack_misc_*`, `lang_*_audio`,
`music_*`. Internal resource types: `.sps` (Sucker Punch textures, `XTBS` wrapper), `.xpps` (KCAP packages),
`.xmesh`, `.texmeshman`/`.packman`/`.sprig` (manifests/db), `.wem` (audio).

## Text — `gapack_misc_l.psarc` → `lang_<lang>_text.xpps` (KCAP)
The localization text is per-language files inside `gapack_misc_l.psarc` (1.43 GB, 495 inner files):
- **Source** = `/lang_english_text.xpps` (16,583,124 B).
- **Hebrew target (Arabic slot)** = `/lang_arabic_text.xpps` (17,064,240 B) — **official Arabic locale EXISTS**.
- ~34 text languages total (`lang_<x>_text.xpps`), + separate `lang_<x>_audio.xpps` (audio, out of scope).
- The internal path has a **leading slash** (`/lang_arabic_text.xpps`) — critical for the deploy override key.

### KCAP format (`.xpps`) — cracked, reader = `tools/xpps.py`
Magic `KCAP` (= "PACK" reversed), all integers little-endian, strings UTF-8 NUL-terminated.
```
0x00 "KCAP" | 0x04 u16 0x1f,u16 0x07 (ver) | 0x08 u32 0x41d | 0x0c 0x00010000 | 0x10 0x00070000
0x14 u32 29 | 0x18 u32 184 | 0x1c u32 var | 0x20 0 | 0x24 0
0x28 u32 BASE (string-blob start: 484 EN / 472 AR)
0x2c u32 TRAILER_START (= filesize − trailer_size)      0x30..BASE = zero padding
[BASE ..]  STRING BLOB: UTF-8, NUL-terminated, duplicates NOT deduped.
INDEX TABLES (16-byte records, ascending KEY): u64 KEY, u64 OFFSET (file_pos = BASE + OFFSET).
   two KEY kinds: (a) LARGE 64-bit content-hash — GLOBAL, cross-language-stable → EN↔AR map by exact key;
                  (b) SMALL structured dialogue ids {u16 f1,u16 f2,u32 0,u64 off}, key=(f2<<16)|f1 — PER-LANGUAGE,
                      COLLIDE globally (join dialogue by block/position, NOT by key).
[.. EOF] TRAILER: 16-byte {u64 tag,u64 value} directory, ends with value FourCC "END ".
```
Identity round-trip is **byte-identical** (`xpps.patch(data, {}) == data`); a value override is **surgical**
(append the new NUL-terminated string before the trailer + repoint the key's u64 OFFSET + bump `@0x2c`) — **free
growth, no delta-0 constraint** (offsets are u64, strings self-describing). Same-length in-place overwrite is the
lowest-risk zero-growth option.

### Scope (measured on the real blob)
- **~36,000 distinct translatable strings** (EN ~41,399 instances / 36,259 distinct; AR ~36,295 distinct).
  Length split (distinct EN): **~17,500 short (≤25 ch)** UI/labels · **~17,400 medium (26–80)** tutorials/item
  desc/objectives/short dialogue · **~1,400 long (>80)** lore/tales/subtitle paragraphs.
- **Reliably key-joinable UI/content (large-hash): ~13,000 EN↔AR pairs** (of which ~11,900 are genuine Arabic
  translations, ~800 identical passthroughs = single letters/codes/`HDR`). Up to ~18,280 EN large-hash records.
- **Dialogue/subtitle (small-id): ~28,000 EN records** — join by **block+position** (keys collide: e.g.
  "Watch out!" and "Nobu!" both key `0x300000`). Exact count + the block-position join is a Phase-2 task.
- ⚠️ The reader `tools/xpps.py` (strictly-ascending contiguous tables only) reports ~15,058 — an UNDERCOUNT;
  the true corpus is the ~36k blob count above. Phase 2 must widen the table scanner (walk the trailer directory
  to enumerate ALL index sections) to capture the dialogue tables.

### Tokens to preserve verbatim
PUA button/format glyphs `U+E000–U+F8FF` (184 distinct — controller buttons `U+F340`/`U+F30E`…, emphasis/wrap
markers `U+F003/U+F004/U+F005` used in matched PAIRS) · named vars `{SAVE_FOLDER}`/`{GPU_NAME}`/`{ERROR_MSG}`/… ·
printf `%d`/`%f` · literal newline `\n` (real 0x0A, in ~441 multi-paragraph strings) · literal `(\/)`. No HTML/XML.

## Font — proprietary `fOnk` vector glyphs (THE gate)
The menu+subtitle font is a Sucker Punch proprietary **`fOnk`** resource (chunk tag `fOnk`, engine structs
`SFontData`/`FontGlyphs`/`FontVerts` — vector outlines tessellated to GPU verts, **compressed**, ~7.47 bits/byte)
inside `game.sprig.texmeshman` (in `gapack_misc_g.psarc`, chunk @ ~0x156BFF7). **NOT a TTF/OTF and NOT a DDS atlas**
(0 sfnt anywhere in the exe or archives; only a dev-only `debugfont.dds` exists). Arabic IS covered (Arabic is
shipped); **Hebrew is almost certainly ABSENT** (Hebrew is not a shipped language; disjoint Unicode block). The 34
`lang_<lang>.msac.d.0.sps` (~87 KB DDS, `gapack_bitmaps_l`) are **localized UI button-legend images, NOT glyph
atlases** (all ~87 KB regardless of language — a CJK atlas can't fit). → font injection needs the `fOnk` format
cracked first (a sub-project). The menu-proof (see PIPELINE) tests font coverage definitively in-game.

## Precedent / tools
- **Existing mods prove text edits load, incl. non-shipped languages:** Nexus #807 Austronesian Lang Pack (edits
  `lang_greek_text.xpps`, ships `gapack_misc_z*.psarc` dropped into `cache_pc/psarc/`); commercial **Persian (RTL)**
  localization (farsisaz/gamesub/elaymedia) — proves RTL rendering + slot-hijack load. Nexus #809 "GoT Translation
  Tool" (a `.xpps` editor). Caveat: Persian rides the Arabic script → does not independently prove Hebrew bidi.
- **Tools:** GoTExtractor (Glumboi, C#/MIT, github.com/Glumboi/GoTExtractor), UnPSARC (rm-NoobInCoding v2.3+),
  DKDave DSAR decompressor + QuickBMS, MO2 plugin #329. In-repo `games/tlou2/tools/*` is the validated path.
- **Sibling ports:** the DSAR→PSARC container is shared across Nixxes/Sony PC ports (TLOU2, Horizon, Spider-Man,
  Ratchet). The **KCAP `lang_<x>_text.xpps` text format is Sucker-Punch-specific** (Insomniac uses DAT1/.localization,
  ND uses loc-v2 `text2/*`+`sid-lookup`). `games/ratchet_rift_apart` in the repo has art only (different text format).

## מסמכים קשורים
- באותה תיקייה: [[games/ghost_of_tsushima/FEASIBILITY|FEASIBILITY]], [[games/ghost_of_tsushima/PIPELINE|PIPELINE]], [[games/ghost_of_tsushima/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ghost_of_tsushima|CLAUDE_INDEX_games]]
