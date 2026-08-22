# Hogwarts Legacy — Hebrew translation — RECON (verified facts)

> Phase-1 groundwork recon. Every fact below is **verified by direct inspection** of the
> user's install (byte-level pak parsing + real extraction via `repak`) and/or a working
> pure-Python codec that round-trips the game's own files. Written 2026-07-04.

## Install

| | |
|---|---|
| Path | `E:\SteamLibrary\steamapps\common\Hogwarts Legacy` (Steam) |
| Engine | **Unreal Engine 4** (heavily modified; internal project codename **"Phoenix"** — the project folder itself is named `Phoenix/`), likely UE 4.27 |
| Main exe | `Phoenix\Binaries\Win64\HogwartsLegacy.exe` (450 MB) — the root `HogwartsLegacy.exe` (289 KB) is a small EOS-bootstrap launcher stub |
| Uses | Epic Online Services (`EOSSDK-Win64-Shipping.dll`), Wwise audio, no bundled `oo2core_*.dll` (Oodle is statically linked into the exe) |
| Anti-cheat | **None** (no EAC/BattlEye). **Denuvo Anti-Tamper** is present but protects the **executable only** — it does not checksum pak/asset content (confirmed: community texture/gameplay mods on Nexus load fine; Denuvo's fingerprint-token mechanism operates at the exe/runtime level, per public cracking write-ups). Single-player only, no online/competitive mode → zero ban/enforcement risk from asset mods. |

## Archive format — hybrid legacy-pak + IoStore

`Phoenix\Content\Paks\` holds both:
- **Legacy `.pak` files** (classic UE4 container, full self-contained data+index) — e.g.
  `pakchunk0-WindowsNoEditor.pak` (5.6 GB).
- **IoStore `.ucas`/`.utoc` pairs** (magic `-==--==--==--==-`) for the bulk of large streaming
  assets (textures/meshes) — e.g. `pakchunk0-WindowsNoEditor.ucas` (13.7 GB).

**Our target — the localization text — lives entirely inside the LEGACY `.pak`** (confirmed:
`Phoenix/Content/Localization/...` paths were found by grepping the plaintext directory index of
`pakchunk0-WindowsNoEditor.pak`, and `repak list`/`repak get` extracted the files directly with no
IoStore involvement). So the whole translation pipeline never has to touch IoStore at all.

### Legacy pak footer (`FPakInfo`, verified via direct byte parse + `repak info`)

```
magic:            0x5A6F12E1 (PakFile_Magic)
version:          11  ("Fnv64BugFix" — the newest legacy pak index format, PathHashIndex)
mount point:      ../../../
encrypted index:  false
encryption guid:  00000000-0000-0000-0000-000000000000  (all-zero = NOT AES-encrypted)
compression:      Zlib, Oodle
path hash seed:   0xAAB884E7
file entries:     26,546  (in pakchunk0-WindowsNoEditor.pak alone)
```

**No AES key needed anywhere** — confirmed both by our own byte inspection (zero encryption
GUID / `bEncryptedIndex=0`) and independently by the community (`FModel/Unreal-Game-Keys` GitHub
repo, which only lists games that DO need a key, has no entry for Hogwarts Legacy).

## Where the text actually lives — NOT `.locres`

The game ships the standard-looking UE4 `Content/Localization/Game/<culture>/Game.locres` tree
(14 locales incl. `ar`/`ar-AE`), but **these files are boilerplate/near-empty** — extracted and
decoded directly: `Game.locres` (en) is 146 bytes and holds exactly ONE default engine string
(`UniversalLocalizationKey` → `"Universal Localization Text"`); the `ar` one is 37 bytes (empty
StringTable). **This is a dead end — do not build the pipeline around `.locres`.**

**The real, actually-read-at-runtime text lives in a custom Avalanche Software format:**
`Phoenix/Content/Localization/WIN64/{MAIN,SUB}-<locale>.bin` — one flat pair of files per locale
(NOT per-culture subfolders), confirmed both by direct extraction and by the community modding
wiki (modding.wiki's localisation page describes only this workflow, never `.locres`):

- **`MAIN-<locale>.bin`** = UI/menus/settings/item names/etc.
- **`SUB-<locale>.bin`** = subtitles/dialogue (speaker-tagged keys, e.g. `DarkWizardMaleA_10950`)

14 locale pairs shipped: `enUS deDE esES esMX frFR itIT jaJP koKR plPL ptBR ruRU zhCN zhTW **arAE**`.
**`arAE` = the official Arabic locale** (MENA release) — confirmed real, fully-translated Arabic
content (not a stub), for both MAIN and SUB.

### The `.bin` format — "AVAFDICT 2.0" — fully cracked, pure-Python codec built

Reverse-engineered from the open-source community tool **`insomnious/parseltongue`** (C#, MIT-ish,
GitHub) and reimplemented + verified in pure Python: [`work/hl_bin.py`](work/hl_bin.py)
(`decode`/`encode`, self-tests on every real file). Trivially simple — no compression, no
encryption, no size-matching tricks needed (unlike every delta=0 game elsewhere in this repo):

```
Little-endian layout:
  bytes[32]  magic       = UTF-16LE "AVAFDICT 2.0   \0"
  int64      entryCount
  int64      headerSize  = 72 (always)
  int64      entriesSize = entryCount * 24
  int64      dataStart   = headerSize + entriesSize
  int64      dataSize    = total bytes of the data section

  entryCount x 24-byte entry records:
      int64  keyOffset    (relative to dataStart)
      int32  keySize      (UTF-8 byte length)
      int64  valueOffset  (relative to dataStart)
      int32  valueSize    (UTF-8 byte length)

  data section: UTF-8 key bytes immediately followed by UTF-8 value bytes, per entry,
  all entries concatenated into ONE flat blob (offsets are a running cumulative total).
```

A community GUI decoder also exists (`avafdict-codec`, Nexus #439) confirming the same format
name/structure independently.

## Real extracted scope (verified via `repak` + `hl_bin.py`, 2026-07-04)

Extracted directly from the user's own `pakchunk0-WindowsNoEditor.pak` with `repak` (no AES key):

| File | Entries |
|---|---:|
| `MAIN-enUS.bin` (English UI) | 18,889 |
| `MAIN-arAE.bin` (Arabic UI) | 18,889 |
| **MAIN, EN ∩ AR** | **18,889** (perfect 1:1 key match) |
| `SUB-enUS.bin` (English subtitles/dialogue) | 34,955 |
| `SUB-arAE.bin` (Arabic subtitles/dialogue) | 39,684 |
| **SUB, EN ∩ AR** | **34,955** (every EN key has an AR counterpart; **4,729 AR-only** extra keys — out of scope, likely dev-cut lines) |
| **Total translatable (EN∩AR, both files)** | **53,844** |

Sample content (proves real, natural-language Arabic, not placeholder junk):
```
Hint_HasRewardsToCollect: EN "You have uncollected rewards available in the Challenges Menu."
                          AR "توجد مكافآت لم يتم تحصيلها في قائمة التحديات."
DarkWizardMaleA_10950:    EN "Not that!"           AR "ليس هذا!"
playerfemale_27052:       EN "I don't think I can take much more of this."
                          AR "لا أظن أنه يمكنني تحمل المزيد من هذا."
```

### Tokens/markup to preserve verbatim (scanned across all EN values)

| Pattern | Count | Example |
|---|---:|---|
| `{0}` / `{1}` style brace tokens | 835 | `"Destroy the Egg Sacs ({0}/{1})"` |
| `<img src="..."/>` inline icon tags | 1,312 | `'...Beast Dens <img src="BeastDen"/> throughout...'` |
| `[LT icon]` / `[conjuration icon]` bracket tokens | 2,429 | `"Hold [LT icon] to aim..."` |
| Real embedded newlines (multi-paragraph notes/journals) | 381 | full in-game letters, up to 1,735 chars |
| `{[error:%d]}` (a base-game quirk, not ours) | 2 | `"Find {[error:%d]} pieces of lore"` — preserve as-is |

No HTML entities (`&...;`) found. `SUB` value length: min 3, median 48, p90 110, max 1,735 chars.

## Font & RTL — the differentiating finding of this game

**Unreal Engine has NATIVE Unicode bidi (ICU) + Arabic shaping (HarfBuzz), unlike every other
engine in this repo (CR2W/cohtml, Disrupt, Anvil, RAGE-ish, Zouna, REDengine).** Per Epic's own
docs, Slate's "Text Shaping Method" (`Auto`) applies full ICU bidi reordering automatically for a
RTL culture, and Full Shaping (HarfBuzz) only kicks in for scripts that need letter-joining
(Arabic) — **Hebrew needs bidi-reordering only, no joining**, so it rides the simpler half of the
same pipeline. Community forum reports (UE4/UE5, not Hogwarts-Legacy-specific) describe Hebrew
"working out of the box" once a Hebrew-covering font is present — the historical failure mode in
every UE Hebrew report found was **missing glyphs (tofu/identical-boxes)**, never wrong reordering.
**This means Hogwarts Legacy may be the FIRST game in this project where Hebrew can be stored
LOGICAL (natural reading order) with zero bidi code of our own** — to be confirmed by the menu
proof below.

Font mechanism: UE4/5 **Composite Font** assets (a base typeface + per-Unicode-range fallback
sub-typefaces) are the standard way multi-script UI text is handled; Epic's docs + community
write-ups confirm Arabic fallback ranges are commonly added this way. If Hogwarts Legacy's Arabic
Composite Font lacks Hebrew (near-certain — no game ships Hebrew), adding a `U+0590–05FF` fallback
sub-family should be far simpler than the DXT5-atlas/off-by-one glyph-table hacks needed for every
custom-engine game here — but the actual font asset has not yet been extracted/inspected; that is
the next concrete step after the menu proof.

## Deploy mechanism — non-destructive, community-standard, PROVEN today

Hogwarts Legacy uses UE4's `~mods` auto-mount convention (confirmed by `modding.wiki`'s official
packaging guide + community GitHub guides): a new **override pakchunk** (any unused chunk ID, e.g.
`111`) dropped into `Phoenix\Content\Paks\~mods\pakchunk111-WindowsNoEditor_P.pak` is mounted at
**higher priority** than the shipped `pakchunk0`, for any file path it contains — **the original
pak is never touched**, so Steam/Epic/GOG "Verify Integrity" does not revert it. This is exactly
the mechanism used by every published Nexus mod for this game.

**Verified working end-to-end today** using `repak` (Rust CLI, MIT/Apache, `trumank/repak`
v0.2.3 — downloaded, SHA-256-verified, confirmed to fully support pak version 11 read+write):
- `repak list`/`repak get` extracted `MAIN-enUS.bin`, `SUB-enUS.bin`, `MAIN-arAE.bin`,
  `SUB-arAE.bin` directly from the live `pakchunk0-WindowsNoEditor.pak`, no AES key.
- `repak pack --version V11` built a fresh override pak containing an unmodified copy of
  `MAIN-arAE.bin`; extracting it back was **byte-identical** to the original — the write path
  round-trips cleanly.
- A **menu-proof pak was built and deployed** (see FEASIBILITY.md) — awaiting the user's in-game
  check.

## Activation (to be confirmed by the user in the proof)

In-game: **Settings → Select Language** (`Menu_LanguageSelect`) → choose **Arabic (العربية)**.
A separate **Select Audio Language** (`Menu_VOLanguageSelect`) setting exists — confirmed
independent of text language (a "Language and Subtitle Options — Any Audio Any Text" community
mod exists specifically to decouple these), so English voice-over can be kept.

## מסמכים קשורים
- באותה תיקייה: [[games/hogwarts_legacy/FEASIBILITY|FEASIBILITY]], [[games/hogwarts_legacy/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#hogwarts_legacy|CLAUDE_INDEX_games]]
