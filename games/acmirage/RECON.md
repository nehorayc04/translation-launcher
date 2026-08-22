# AC Mirage — RECON (Phase 1, 2026-07-22)

Install: `F:\Game Lab\Assassin's Creed Mirage` · exe `ACMirage.exe` (520 MB) + `ACMirage_plus.exe`
Engine: **AnvilNext / Anvil (Valhalla lineage)** · Ubisoft Bordeaux, 2023.
Proposed `games.id` = **`ac-mirage`** · detector exe `ACMirage.exe`.

---

## 0. Container — `.forge`, **scimitar v29** — CRACKED + VALIDATED

| Game | scimitar ver | Name table | Status in this repo |
|---|---:|---|---|
| AC2 / Brotherhood / Revelations | 25 | plaintext descriptors | solved |
| Black Flag … Unity … Odyssey | 27/28 | plaintext descriptors | solved |
| **Valhalla / Mirage** | **29** | **NONE (hash→name DB)** | **solved here** |
| AC Shadows | 42 | hash only | read solved |
| AC Black Flag Resynced | 50 | hash only | read solved, deploy blocked |

Header (validated on every Mirage forge):

```
0x00  "scimitar" + 0x00
0x09  u32  version                 == 29
0x0d  i64  header_size             == 1050 (0x41a)
1050  i64  total_entry_count
      i64  0
      i32  -1
      i64  -1
      i32  entry_count + 6
      i32  fileset_count
      i64  first_fileset_offset    == 1094
1094  FileSet:
      +0x00 u32 count      +0x10 i64 next_fileset (-1 = last)
      +0x20 i64 info_table_offset  (UNUSED on v29)
      +0x30 entries[count] : { i64 offset ; u64 id ; i32 length_on_disk }   (20 B)
```

**🔴 v29 has NO name table.** AnvilToolkit resolves `Entry.Name = ID.GetOriginalFileName()`
from an external hash→name database. Resources are addressed by the **u64 ID** only.
Locate anything by **CONTENT** (its ScimitarClass hash), never by name — `tools/mirage_scan.py`.

Reader: **`tools/mirage_forge.py`** — `validate() == 0` (contiguous, in-bounds, monotonic) and
exact entry counts on all 35 root forges + 15 DLC forges.

## 1. Resource blob = CFD chain (identical to AC Shadows v42)

Every resource is one or more `CompressedFileData`:
`u64 magic 0x1004FA9957FBAA33 · CompressionInfo[7] (ver=3, algo=8=Oodle) · i32 blockCount ·
{i32 uncomp, i32 comp}×N · {u32 adler32(comp,0), bytes}×N`, 262144-byte blocks, **stored when
`comp == uncomp`**. `games/acshadows/tools/acs_cfd.py` decodes it **unchanged**.

Layout is always `CFD0` (16-byte meta) + `CFD1` (the object). The game ships **no `oo2core` DLL** —
borrow `C:\Games\Battlefield 6\oo2core_9_win64.dll` (`acs_oodle.py`, already wired).

Decompressed object header:
```
u32 class_hash   (= zlib.crc32(ClassName))
i32 size
i32 name_len     (bit 0x40000000 = ENCRYPTED, see §3)
char[name_len] name
```
Confirmed class hashes: `Animation 262342271` · `Skeleton 615435132` · `Material 2244483011` ·
`TextureMap 2729961751` · `Entity 159662430` · `EntityBuilder 2535097390` ·
**`LocalizationPackage 1849465967`**.

## 2. Text — `LocalizationPackage`, 14 languages, **official Arabic**

`tools/mirage_loc.py` decodes forge → CFD → object → `[i32 Type][u32 Language][12][u32 marker
0xD28389B5][i32 count][BE payload]` → the AC2/Unity **char-index fragment-tree** store
(decoder reused verbatim from `games/acunity/work/acu_loc.py`).

A **full sweep of all 50 forges** found LocalizationPackages in exactly three places:

| Forge | packages | state |
|---|---:|---|
| `DataPC.forge` | 28 (14 langs × UI + Subtitles) | ✅ **PLAINTEXT** |
| `DataPC_patch_01.forge` | 28, same resource IDs, ~+22 % bytes | 🔴 encrypted |
| `dlc_2\DataPC_2_dlc.forge` | 28 (Valley of Memory DLC) | 🔴 encrypted |

Decoded from the base forge (`extract/*.json`):

| package | strings | EN chars |
|---|---:|---:|
| UI (`LocalizationPackage_<lang>_Rift_MG_…`) | **7,612** | 524,155 |
| Subtitles (`…_<lang>_Subtitles_Rift_MG_…`) | **5,473** | 278,445 |
| **total translatable** | **13,085** | **802,600** |

Key sets are **identical across all 14 languages** (7,612 / 5,473 shared) → map EN→HE by id.
UI median 22 chars (4,160 ≤ 25 chars) with codex entries up to 2,167; subtitles median 43, max 155.
Tokens to preserve verbatim: `\n` (2,414), `<img src='…'/>`, `<style name='…'>…</style>`,
`{0}`/`{1}`, `[CT_*]` button tokens, `[sigh]`/`[laugh]`/`[beat]` stage directions.

Languages: Arabic · Chinese(Simp/Trad) · English(US) · French · German · Italian · Japanese ·
Korean · Polish · Portuguese(Brazil) · Russian · Spanish(Spain/Mexico).

## 3. 🔴 The patch/DLC forges are ENCRYPTED

`name_len` carries a flag: `nlen & 0x40000000` ⇒ everything from the name onward is ciphertext.
Measured: `DataPC.forge` **0 %** encrypted · `DataPC_patch_01.forge` **≈87 %** · DLC loc **100 %**.

Known-plaintext attack (XOR the patch ciphertext with the base's plaintext name) shows the
recovered "keystream" is **identical for exactly the first 16 bytes** between two resources whose
names share a 16-byte prefix, then diverges at the first differing plaintext block ⇒
**a 16-byte BLOCK cipher (AES-class), not an XOR keystream**. The key lives in the
VMProtect-packed `ACMirage.exe` (`.vmp0`/`.vmp1` sections + `denuvo` strings).

**We do not attack it.** The bypass to test is that the flag is **per resource** and the base
forge proves the engine reads flag-0 objects natively → write a **plaintext** (flag cleared)
package into the slot the engine wins with.

## 4. Activation — a plain registry string

`uplay_install.state` maps every locale to
`HKEY_CURRENT_USER\SOFTWARE\Ubisoft\Assassins Creed Mirage\Language`, with **`ar-AA`** among them
(alongside en-US, fr-FR, it-IT, de-DE, es-ES, es-MX, ru-RU, pt-BR, ja-JP, pl-PL, ko-KR, zh-TW, zh-CN).
The key is **absent** until the game runs once. Same one-value lever as AC Black Flag Resynced →
an in-launcher Hebrew/English switch is a `kind:"registry"` `game_language.py` entry.

**All 14 languages ship inside the forge** — no separate language pack download. And Mirage ships
**Arabic VO** (`sounddata\PC\sounds_ara.pck`, `ara=15` in `streaminginstall.ini`); text and audio
language are independent, so English voice is preserved.

## 5. Font — NOT located yet

- No `.ttf` / `.otf` / `.ffd` strings and **no embedded sfnt** in `ACMirage.exe` (VMProtect-packed,
  so static strings are unreliable — only `Noto` ×3, `ICU` ×2 survive).
- No font-named resource in any forge: the only hits are `DebugFontTexture` and
  `SDR_UI_WorldMap_FogFont`. `DataPC_extra.forge` holds 5,578 `TextureMap`s (the UI art pack).
- ⚠️ This is the same shape that ended AC Unity — but with a decisive difference: **Mirage's
  Arabic is a full UI locale that renders RTL in the real menus**, so an Arabic-capable font is
  definitely loaded. The open question is only Hebrew coverage, and the menu proof answers it.

## 6. bidi — **LOGICAL** (engine does its own shaping + reordering)

Measured over the shipped Arabic (497,101 Arabic chars): **0 presentation forms**, **2** explicit
bidi controls in the whole corpus, 3,437 lines end with `.` vs 1 that starts with one.
⇒ store natural Hebrew, **no VISUAL bake, no `&rlm;` injection**. (Confirm in the proof.)

## 7. Repack — identity round-trip

`acu_loc.encode_payload` → `decode_payload` reproduces **7,612/7,612** (UI) and **5,473/5,473**
(subtitles) strings, **semantic PASS**. Not byte-identical: the game uses a multi-char (BPE-like)
fragment dictionary while our encoder emits single chars, so a rebuilt payload is ~1.7–2× larger
(273,907 → 460,795 B). Same as AC Unity — fine for a growing deploy, and `acu_minbuild.py`'s
minimal-rebuild trick (reuse the original codes, re-encode only edited strings) is the size fix.

## 8. Tooling

| file | role |
|---|---|
| `tools/mirage_forge.py` | v29 container reader (`info`/`list`/`extract`) |
| `tools/mirage_scan.py` | content scan → class histogram / find-by-class / grep names |
| `tools/mirage_loc.py` | LocalizationPackage → `{id: string}` |
| `tools/sweep_loc.py` | sweep every forge for loc packages + encryption state |
| `extract/*.json` | decoded en/ar/fr/ru/es/it/pl × UI+subs |
| `extract/loc_sweep.txt` | the full-forge sweep report |

Run everything with the repo `.venv` python.

## מסמכים קשורים
- באותה תיקייה: [[games/acmirage/FEASIBILITY|FEASIBILITY]], [[games/acmirage/PIPELINE|PIPELINE]], [[games/acmirage/REPORT_HE|REPORT_HE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acmirage|CLAUDE_INDEX_games]]
