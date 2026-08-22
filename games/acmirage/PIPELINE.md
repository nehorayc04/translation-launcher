# AC Mirage — PIPELINE

Run everything with the repo `.venv` python (needs the Oodle wrapper + `lzallright` is NOT used here).

## Read (works today)

```bash
P=.venv/Scripts/python.exe
G="F:/Game Lab/Assassin's Creed Mirage"

# container
$P games/acmirage/tools/mirage_forge.py "$G/DataPC.forge" info
$P games/acmirage/tools/mirage_forge.py "$G/DataPC.forge" list --limit 20

# what classes / which resources
$P games/acmirage/tools/mirage_scan.py  "$G/DataPC.forge" classes
$P games/acmirage/tools/mirage_scan.py  "$G/DataPC.forge" find 1849465967     # LocalizationPackage
$P games/acmirage/tools/mirage_scan.py  "$G/DataPC.forge" names --grep Font

# text
$P games/acmirage/tools/mirage_loc.py   "$G/DataPC.forge" 2132259441960 out_en.json   # English(US) UI
$P games/acmirage/tools/mirage_loc.py   "$G/DataPC.forge" 2130870776974 out_ar.json   # Arabic UI

# every forge, loc + encryption state
$P games/acmirage/tools/sweep_loc.py    "$G" --out games/acmirage/extract/loc_sweep.txt
```

### Resource IDs (identical in `DataPC.forge` and `DataPC_patch_01.forge`)

| language | UI | Subtitles |
|---|---|---|
| **Arabic** (the Hebrew slot) | `2130870776974` | `2130870776975` |
| English (US) — source | `2132259441960` | `2132259441961` |
| French | 2130870776950 | 2130870776951 |
| Italian | 2130870776952 | 2130870776953 |
| German | 2130870776954 | 2130870776955 |
| Spanish (Spain) | 2130870776956 | 2130870776957 |
| Spanish (Mexico) | 2130870776958 | 2130870776959 |
| Portuguese (BR) | 2130870776960 | 2130870776961 |
| Polish | 2130870776962 | 2130870776963 |
| Russian | 2130870776964 | 2130870776965 |
| Japanese | 2130870776966 | 2130870776967 |
| Korean | 2130870776968 | 2130870776969 |
| Chinese (Trad) | 2130870776970 | 2130870776971 |
| Chinese (Simp) | 2130870776972 | 2130870776973 |

## Write — BUILT + VALIDATED OFFLINE (2026-07-22)

```bash
# 1) identity round-trip of the whole resource (build -> re-read)
$P games/acmirage/tools/mirage_build.py "$G" selftest 2130870776974

# 2) build the menu-proof blob (ids resolved from the ENGLISH package, written into ARABIC)
$P games/acmirage/tools/mirage_build.py "$G" proof 2130870776974 games/acmirage/work/proof_ar_ui.bin

# 3) deploy — append-relocate (makes DataPC.forge.he_backup on the first run)
$P games/acmirage/tools/mirage_deploy.py "$G" apply 2130870776974 games/acmirage/work/proof_ar_ui.bin
$P games/acmirage/tools/mirage_deploy.py "$G" revert          # byte-identical restore
```

**Object layout (mapped byte-for-byte; both length fields are re-derived on every build):**
```
+0   u32 class_hash = 1849465967
+4   i32 size        <-- LENGTH #1 = len(content) - (12 + name_len + 1)
+8   i32 name_len
+12  name[name_len] + u8 0x00 + u8 0x01
     u64 ClassID (== the forge resource id) + u32 Hash
     i32 Type (0=UI, 1=Subtitles) + u32 Language (1=English(US), 22=Arabic)
     12 unused bytes + u32 0xD28389B5 (constant, read-and-discarded)
+mk+4 i32 count      <-- LENGTH #2 = len(payload)
+mk+8 payload        BE char-index store; runs to the END of the object (tail = 0 bytes)
```

**Offline validation on a COPY of the real forge — all green:**

| check | result |
|---|---|
| patched resource re-reads | 7,612 strings + the 5 edits, header/Type/Language intact |
| every other resource | **38,109 / 38,109 byte-identical** |
| header + FileSet table | byte-identical (first 2 KB) |
| sibling loc packages | **27 / 27 still decode** |
| file growth | exactly the appended blob (194,729 B) |
| contiguity violations | 1 — the relocated resource, by design |

Payload grows ~1.68× (single-char fragment dict) but the resource blob is *smaller* than vanilla
(194,729 B vs 214,689 B) because Mermaid compresses the simpler stream better.

## Menu proof — what gets patched

`mirage_build.py proof` writes into the **Arabic** package of `DataPC.forge`
(ids resolved from the English package, since ids are shared):

| id | English | new value |
|---|---|---|
| 456215 | Options Page | `ZZ-MIRAGE-OK-ZZ` (pure-Latin mount marker) |
| 456219 | Controls | `הגדרות` |
| 456233 | Interface Language | `בחר שפה` |
| 456221 | Credits | `יציאה` |
| 456223 | Sound | `המשך` |

Then: **close the game**, deploy, launch, **Options → Language → العربية**, screenshot.

## Write (older notes / remaining)

1. **`mirage_build.py`** — `{id: hebrew}` → payload (`acu_loc.encode_payload`, **LOGICAL**) →
   splice into the object content, patching **both** size fields (the object's `size` at +4 **and**
   the payload `count` after the `0xD28389B5` marker — the AC Unity lesson: a stale length field is
   an out-of-bounds read → "warning window + crash").
2. **CFD re-encode** — `acs_cfd.encode_resource`, **Oodle Mermaid (compressor 9) at level 7**, not
   Kraken (byte1 of an Oodle chunk is the real codec — CLAUDE.md `oodle-codec-is-byte1-not-byte0`).
   Blocks whose `comp == uncomp` stay STORED.
3. **`mirage_deploy.py`** — **append-relocate** (the proven AC Unity / 007 pattern): append the new
   blob at forge EOF, then repoint only that entry's `offset` + `length_on_disk` in its 20-byte
   record. Header, FileSet, every other resource stay byte-identical, so the engine still parses
   the file as the base it already loads, and any size works. Back up `<forge>.he_backup` first;
   `--revert` restores.
   *Fallback:* AnvilToolkit v1.3.4 `Serialize29` is a full v29 repacker (GUI).
4. **Menu proof** — patch the **Arabic** UI package in `DataPC.forge`:
   a pure-Latin marker `ZZ-MIRAGE-OK-ZZ` on one visible key + several Hebrew menu strings, stored
   LOGICAL. Set `HKCU\SOFTWARE\Ubisoft\Assassins Creed Mirage\Language = ar-AA`, launch, screenshot.
   Decides mount · patch-shadowing · font · bidi in one shot (see FEASIBILITY §"The one gate").

## Deploy target + revert

- Edit `DataPC.forge` (plaintext). Backup `DataPC.forge.he_backup`; revert = restore the copy.
- Game must be CLOSED (the forge is locked while running).
- Activation: in-game **Options → Language = العربية**, or the registry value above.
  Audio language is independent → English (or the shipped Arabic) VO is preserved.

## Phase 2 (after the proof passes)

- Delegate the **13,085** lines ([[delegate-all-translation]]) — single pass, no fleet.
- **New-Era panel is free**: all 14 languages sit at the same ids in the same forge, so every line
  ships with ar + fr + ru + es + it + pl + de + pt parallels for meaning/gender/register
  (`extract/*.json` already holds en/ar/fr/ru/es/it/pl).
- Name registry + web-verified spellings (Basim, Roshan, Nehal, Baghdad, Anbar, Alamut,
  Hidden Ones, Order of the Ancients) before translating.
- Community `/translate` pool ordered by visibility: `ממשק ותפריטים` (7,612) → `כתוביות עלילה` (5,473);
  `string_key` = the raw numeric id prefixed with its package (`ui:<id>` / `subs:<id>`) so an
  approved line maps straight back onto the right package.
- Publish like the other games (GitHub `acmirage-hebrew-mods` + Worker slug + Supabase `games`
  `ac-mirage` + `mod_version_history`), price per the ₪53 default — **only on an explicit "פרסם"**.

## מסמכים קשורים
- באותה תיקייה: [[games/acmirage/FEASIBILITY|FEASIBILITY]], [[games/acmirage/RECON|RECON]], [[games/acmirage/REPORT_HE|REPORT_HE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acmirage|CLAUDE_INDEX_games]]
