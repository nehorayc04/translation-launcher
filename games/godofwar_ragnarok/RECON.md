# God of War: Ragnarök — RECON (format reverse-engineering)

On-disk facts established 2026-06-17 by direct probing of the live install. All
numbers are reproducible via `work/gowr_wad.py` against the reference WADs in
`extract/`. **Read-only so far — nothing in the game folder was modified.**

## Install + engine

- **Game root (project staging copy, the one the user plays/tests):**
  `Game Lab/God of War - Ragnarok/` (a FitGirl repack — `_Redist/fitgirl.md5`).
  A second copy exists at `C:\Games\God of War - Ragnarok` — ignore it.
- **Engine:** Sony Santa Monica proprietary ("WAD" archives, `GoWR.exe`).
- **Build:** app-version 01.01, build-id 96749 (`exec/boot-options.json`).
- **Localization lives in:** `exec/wad/pc_le/r_lang_<locale>.wad` — one WAD per
  language, ~3 MB each. 23 locale WADs present (en, ar, fr, de, es, ru, ja, …).
- **Language manifest:** `exec/languages/LANGS_GOWR09000.txt` →
  `21 ar ARABIC 21` (Arabic is locale id 21). `boot-options.json` playgo-chunks
  list `"ar"` as a shipped chunk. Arabic is an **official, full** locale
  (voice + text) → its RTL/bidi pipeline is tested by the developer.

## Container chain (the important part)

```
r_lang_XX.wad
  └─ LZ4 frame              magic 04 22 4D 18  (lz4.frame, round-trips in Python)
     └─ inner WAD           'WTOC' table-of-contents @ offset 0
        ├─ resource entries TXRX/WPTX/DLGX/BTRX/XCXT/… each '<TAG>_R_Lang'
        ├─ font resources   SMF_0..4, copperplate_<loc>, godofwar_<loc>, iconspc_<loc>
        └─ 'MSGS_TXT'        the localization STRING TABLE  ← what we translate
```

- **LZ4:** standard frame, content-size + content-checksum flags set. ar:
  3,219,902 → 7,551,235 B (2.35×); en: 3,754,502 → 8,574,877 B (2.28×).
- **Inner WAD** starts with `WTOC` (WAD Table Of Contents): `"WTOC"` + u32 ver(2)
  + u32 count + … then fixed-size entry records (name padded to a fixed field,
  `aa aa aa ba aa …` filler / hash placeholders). Each `<TAG>_R_Lang` resource is
  one entry. **Full WTOC offset/size parsing is still TODO** (needed only for
  re-packing, not for reading the text — see below).

## MSGS_TXT — the string table (fully decoded)

Inside `MSGS_TXT` the strings are a flat, newline-delimited list of records:

```
*<numeric_id>*\n<string value, may span lines / carry markup>\n
```

Example (en):  `*372*\nVanir Summon\n*373*\nWeapon\n*374*\nAxe Attachment\n…`
Same ids in ar: `*372*\nاستدعاء فانير\n*373*\nسلاح\n*374*\nملحقات الفأس\n…`

- **Keying:** the `*N*` numeric id is the engine's string id and is **identical
  across locales** → EN and AR align 1:1 by id (a perfect parallel corpus).
- **Encoding: UTF-8.** Arabic stores as UTF-8 (`d8/d9` lead bytes, 255k runs).
  **Hebrew is also UTF-8 → it stores byte-for-byte the same way the slot already
  expects** (this is why the Arabic-slot hijack is clean here).
- `*2*` = `Design#Text Status#Needs Review` is the dev spreadsheet header
  (`#`-separated columns) — skip it. Some values are `OBSOLETE` / `CUT`.

## The numbers (translation scope)

| Metric | EN (`r_lang_en.wad`) | AR (`r_lang_ar.wad`) |
|---|--:|--:|
| strings extracted | 53,199 | 49,199 |
| total chars | 4,398,114 | 3,572,076 |
| id range | 2 – 138,479 | 372 – 137,887 |

- **Shared ids (EN ∩ AR) = 48,886** ← the real translatable scope: take the
  **English** value as the source, translate → Hebrew, write into the **Arabic**
  slot id.
- EN-only ids = 4,313 (dev/cut strings not shipped in any locale → skip).
- AR-only ids = 313 (Arabic present without an EN source).
- AR slot is 49,086/49,199 actual-Arabic, 90 Latin-only (brand/code passthrough),
  0 blank → the slot is a fully-populated RTL target, ideal to overwrite.

## In-text markup that MUST be preserved verbatim (top tokens in EN)

| Token | ~count | Meaning |
|---|--:|---|
| `[[S:CHAR:vo_…]]` | ~40k+ | speaker/voice-cue reference (e.g. `[[S:ATREUS:vo_int1_cbt_…]]`) |
| `\n` | 6,353 | literal line break |
| `[style=Highlight]` … `[/style]` | 1,823 / 2,154 | rich-text highlight span |
| `[i]` … `[/i]` | 1,078 / 1,075 | italic span |
| `%d` | 965 | printf integer |
| `[Icons:LUCK]`, `[SquareButton]`, button glyphs | many | UI glyph refs |

String lengths: min 1 / **median 83** / max 2,279 chars (long lore letters) →
the translator needs **token-budget batching** (short UI lines batched; a 2k-char
letter goes solo), exactly like the SM2 subtitle path.

## What is NOT yet established (the open gates)

1. **Re-pack round-trip** — writing a modified MSGS_TXT back requires rebuilding
   the inner-WAD `WTOC` offsets/sizes (Hebrew ≠ Arabic byte length) and re-wrapping
   the LZ4 frame. The WTOC binary layout is only partially mapped. **Fallback:**
   the community **"God of War Localization Tool" by Delutto** (handles
   `r_lang_*.wad`) — fetch + evaluate before writing our own packer.
2. **Hebrew font glyphs.** The locale WAD carries font resources (`copperplate_*`,
   `godofwar_*`). The **Arabic** font almost certainly has **no Hebrew glyphs** →
   risk of tofu boxes. Same problem solved on SM2 (font injection) and WD2 (Hebrew
   atlas). Must verify which font the subtitle/UI widgets use and whether Hebrew
   renders, then inject glyphs if needed.
3. **In-game load confirmation** — deploy a test `r_lang_ar.wad` with a known
   marker string, set interface=Arabic, confirm it shows (and renders RTL).

## מסמכים קשורים
- באותה תיקייה: [[games/godofwar_ragnarok/FEASIBILITY|FEASIBILITY]], [[games/godofwar_ragnarok/FONT|FONT]], [[games/godofwar_ragnarok/GENDER_TASK|GENDER_TASK]], [[games/godofwar_ragnarok/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#godofwar_ragnarok|CLAUDE_INDEX_games]]
