# The Last of Us Part I (PC) — RECON

**Install:** `D:\Games\The Last of Us - Part I` (FitGirl repack, cracked — `steam_api64.rne`
+ `steam_emu.ini`, Denuvo removed). exe `tlou-i.exe` (`tlou-i-l.exe` = launcher-less). Engine =
**Naughty Dog proprietary engine** (the TLOU2 / Uncharted-LoT PC lineage). Ships
`oo2core_9_win64.dll` (Oodle 2.9) + `bink2w64.dll`. Steam app-id **1888930** (do NOT confuse with
`2531310` = TLOU Part II Remastered, a different game that later got Arabic).

Detector key + Supabase `games.id` = **`tlou1`** (already a `coming-soon`/`locked` catalog row).

## Container — PSARC v1.4, Oodle (CRACKED, pure-Python reader built)

Game data: `build\pc\main\*.psarc` (24 archives, ~63 GB) + `speech1/` (English audio only in this
repack) + `tts1/` + `movie1/` (Bink) + loose manifests (`paks.txt`, `chunks.txt`, …).

Header (big-endian), verified on every archive:
```
0x00 "PSAR"  0x04 u16 verMajor=1 u16 verMinor=4  0x08 "oodl"  (Oodle Kraken)
0x0C u32 totalTOCSize   0x10 u32 tocEntrySize=30   0x14 u32 numFiles
0x18 u32 blockSize=0x10000   0x1C u32 archiveFlags
TOC entry (30 B): 16 md5(path) + u32 blockListStart + u40 origSize + u40 startOffset
block table: u16 BE per block (0 => a full raw blockSize block); nb bytes = smallest with 256**nb>=blockSize
entry 0 = the manifest: NUL-separated (\x00) UTF-8 path list
```
- **⚠️ THE bug that cost the most:** TOC entries are ordered by **md5(path) ascending**, NOT by
  manifest order. A naive positional `manifest[i]→entry[i+1]` map mislabels almost every file (a
  `text2/*` path resolves to a random `sfx1` audio entry → looks like "XVAG audio", the red herring
  that nearly derailed recon). Correct: `entry.name_hash == md5(path).digest()`. Fixed in
  `tools/psarc.py` (`by_path`).
- No `DSAR` outer wrapper on these archives (some ND PC archives have one; these start with `PSAR`).
- Oodle DLL ships in the game folder → no borrowing (unlike AC Shadows). `tools/oodle.py` wraps it;
  round-trip verified.

## Where the text lives — `core.psarc` (CRACKED, codec built)

`core.psarc` (6.3 GB, 14,062 files) → **`text2/`** (79 files):
| Path | What |
|---|---|
| `text2/<lang>.common` | UI / menus / HUD / options / accessibility labels |
| `text2/<lang>.subtitles` | scripted story/cinematic dialogue subtitles |
| `text2/<lang>.subtitles-systemic` | systemic gameplay barks / ambient NPC callouts |
| `text2/sid-lookup` | SID→key lookup table (169,588 entries) |

**26 language codes present, NO `ara`/Arabic, NO Hebrew** (see FEASIBILITY §Arabic).

Format = Naughty Dog **loc "version 2"** (little-endian), reimplemented in `tools/tlou_loc.py`
(decode + encode, roundtrip-verified):
```
uint32 count
count × { uint64 stringId(SID) ; uint64 blobOffset }   # 16 B/record
UTF-8 NUL-terminated string blob;  string = blob[blob_start+offset : NUL],  blob_start = 4 + count*16
```
- **SID is identical across every language file** → map EN→HE by SID (never invent IDs; edit in place).
- Encoding **UTF-8** → Hebrew stores directly. Duplicate values share one blob offset (dedup).
- **No gender split** in the ND loc (one string per SID) → no femaleVariant/maleVariant backfill needed
  (unlike CP2077).

### Scope (English source, measured)
| File | records | unique | non-empty |
|---|--:|--:|--:|
| `eng.common` (UI) | 16,933 | 13,049 | 15,550 |
| `eng.subtitles` (story) | 13,672 | 10,970 | 13,333 |
| `eng.subtitles-systemic` (barks) | 32,875 | 9,814 | 32,861 |
| **translatable ≈ (unique)** | | **~33,800** | |

### Token grammar (preserve verbatim through the visual bake)
- MARKUP: `<font face="default" color="t2-white-medium">…</font>`, `<br>`, `<break/>`, `<hang></hang>`
- ISLAND glyph/var tokens: `|gen:interact|` `|menu:select|` `|move|` `|l3|` `|T|` `|@01|`
  `|arrow-menu-path|`, `[A]` `[B]` `[TEXT]` `[TEXT2]`
- `\n` (literal two chars) + real newlines; occasional `%`/`{}`.
Counts (top): `</font>`×1592, `<br>`×1336, `<break/>`×644, `[A]`×254, `|gen:interact|`×102 …

## Fonts — `core.psarc/fonts/` (16 faces, 89 MB)
Standard **TTF/OTF** (loose, not atlas/CR2W): `DINPro-Regular.otf` + `DINPro-Medium.otf` (the main UI
grotesque), `HelveticaNeueBold.ttf`, CJK faces (`DFHEI5-V-SONY.ttf`, `HeiSASC-Medium_0.ttf`,
`SCE-RyuminH-KL.ttf`, `AsiaKGD14-R.ttf`), `SSTThai-*`, `KaushanScript`, `SIE-UtrilloPro*`,
`debug.ttf`, `svg.ttf`, `devonly.ttf`.
- **Hebrew coverage = ZERO in every face** (cmap-verified: 0 glyphs in U+05D0–05EA). `DFHEI5-V-SONY`
  covers Arabic (208/256) + CJK but no Hebrew. → **Hebrew must be injected/replaced** (§FEASIBILITY).
- DINPro is **CFF/PostScript** (no `glyf`) → Anno-style glyph-copy injection is a no-op → REPLACE with a
  Latin+Hebrew face (`tools`/`work/tlou_font.py`).

## Not the text (recorded so nobody re-chases it)
- `bin.psarc` (4,821 `dc1/*.bin`) = ND **`00CD` DC** compiled data/state-scripts (`ss-*`, `part-*`),
  incl. `dc1/subtitles.bin` (5 KB = subtitle *system config*), `dc1/text2-fonts.bin`,
  `dc1/text2-styles.bin` — NOT the strings.
- The XVAG/`LIPS`/`RIFF-WAVE` files that looked like "text2/*.subtitles" were the **md5-mismap red
  herring** — they are `sfx1/*.xvag` audio, never the loc text.

## Tools built (all self-tested)
`tools/oodle.py` (Oodle DLL wrapper) · `tools/psarc.py` (`info`/`list`/`extract`) · `tools/tlou_loc.py`
(`decode`/`dump`/`stats`) · `work/tlou_rtl.py` (`to_visual` bake, 9/9 selftest) · `work/tlou_font.py`
(`check`/`make`) · `work/build_menu_proof.py` (stage/`--deploy`/`--revert`).

## מסמכים קשורים
- באותה תיקייה: [[games/tlou1/FEASIBILITY|FEASIBILITY]], [[games/tlou1/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou1|CLAUDE_INDEX_games]]
