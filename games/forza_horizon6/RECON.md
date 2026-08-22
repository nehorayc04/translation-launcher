# Forza Horizon 6 — Phase-1 RECON

**Install** `C:\Games\Forza Horizon 6` · 144 GB · Playground Games / **ForzaTech**
· GDK / Microsoft Store title (`MicrosoftGame.config`, `Microsoft.ForteBaseGame`,
StoreId `9NR1R1XWLCNB`, version `2.403.798.0`) repacked for Steam
(`steam_appid.txt` = **2483190**, RUNE `steam_emu.ini`, `NoDVD\Online Fix\`).
Proposed `games.id` = **`forza-horizon6`**, detector exe `forzahorizon6.exe`.

## 🔴🔴 THE INSTALL IS INCOMPLETE AND PARTLY CORRUPT — verified against the game's OWN manifest

The build ships its own hash list, `v403.798.xxh128` (plain text, `XXH128 *path`,
15,149 entries). `work/check_install.py` + `work/verify_hashes.py` measured it:

| | |
|---|---|
| listed | 15,149 |
| present | 14,443 |
| **MISSING** | **706** |

Of the 706 missing, **700 are per-language audio banks** (`R*_Stingers_{BR,DE,ES,IT,JP,MX}`,
VO/music) — a deliberate English-only selective install, harmless. The other **6 are real**:

```
forzahorizon6.exe                      <-- THE GAME EXECUTABLE. Nothing can launch.
media\ObjectModelGame.zip
media\Audio\DialogueLength.xml
media\Stripped\StringTables\HU.zip     (Hungarian — so the game ships 24 text langs, 23 installed)
Fanatec.Devices.bin
hash.manifest
```

And of the files that ARE present, several fail their XXH128:

| file | xxh128 | consequence |
|---|---|---|
| `media\UI\Fonts.zip` | **MISMATCH** | 7 of the 8 primary font descriptors are unrecoverable |
| `StringTables\{BR,CHT,CZ,DE,EL,ES,FI,FR,JP,KO,MX,PL,PT,RU,TR}.zip` | **MISMATCH** (15) | 1-2 tables per file unreadable |
| `StringTables\{CHS,DK,EN,GB,IT,NL,NO,SV}.zip` | **MATCH** (8) | pristine |
| `media\UI.zip`, `media\zipmanifest.xml`, `MicrosoftGame.config` | MATCH | pristine |

**The corruption map is 1:1 with the parse failures**, which is what proves the
codec below is correct rather than the files: every zip that fails its hash has
exactly the broken entries my reader reports, and every zip that passes reads
287/287 clean. All work below is therefore built on **EN.zip / GB.zip, both
xxh128-verified pristine**.

## Container — plain ZIP with a 4 KB alignment convention (`tools/fh6_zip.py`)

`media\**\*.zip` are ordinary `PK\x03\x04` deflate archives plus one private rule,
verified **288/288** on EN and GB:

* every entry's compressed data starts on a **4096-byte boundary**;
* the LOCAL header's extra field is one padding record `{u16 0x1123}{u16 len}{zeros}`
  sized so `header_offset + 30 + len(name) + len(extra)` lands on that boundary;
* the CENTRAL directory carries `{u16 0x1123}{u16 4}{u32 alignedDataOffset}` — the
  authoritative data start.

**A stale `compress_size` must not bound the inflate.** Feeding exactly `cs` bytes
makes a partially-updated entry raise `invalid distance too far back`, which reads
exactly like "unknown codec" and cost the most time this session. Feed generously
and let the deflate stream terminate itself — that alone took Fonts.zip from
26 "broken" entries to 8, and the manifest then proved those 8 are genuinely absent.

`fh6_zip.write()` reproduces the convention; untouched entries are **stream-copied**,
so a **no-op rebuild is byte-identical** on both pristine archives.

## Text — `media\Stripped\StringTables\<LANG>.zip` → 287 `.str` tables (`tools/fh6_str.py`)

```
+0x00  u16   version (0x0800)
+0x02  char[128] table name, NUL-padded
+0x82  u16   sectionCount (2)
+0x84  u32   sectionOffset[2]

section: u32 total(=count*8+blobLen)  u32 blobLen  u32 count
         {u32 hash, u32 offset} * count            offset = index into blob
         blob: NUL-terminated UTF-8

section[0] = VALUES (what the player reads)
section[1] = ID NAMES (IDS_Foo) — the SAME hash array keys both
```

The hash is a content hash of the id name, and a translation only ever replaces
VALUES for EXISTING ids, so the hash array is copied verbatim and **the hash
function never has to be reimplemented**. `edit()` is surgical (original blob kept,
replacements appended) →
**`edit(buf, {}) == buf` byte-for-byte on 287/287 tables of both pristine zips.**

## Languages — 24 shipped, **ZERO RTL**

`BR CHS CHT CZ DE DK EL EN ES FI FR GB HU IT JP KO MX NL NO PL PT RU SV TR`
(HU not installed). No Arabic, no Hebrew, anywhere — not in the string tables, not
in `MicrosoftGame.config`'s 19 UI locales, not in `fontsettings.xml`.
⇒ **LTR-slot hijack**, not the Arabic-slot trick.

**Id parity is 99.97–100 % across all 22 other languages** (58,179 shared
`(table,id)` pairs) → the richest New-Era oracle panel available so far:
ru/pl/cz for speaker+addressee gender, es/fr/it/pt/br/mx for referent gender,
de for register.

**GB ("English UK") is the ideal sacrifice slot**: only **7,346 of 58,179** values
differ from EN, so hijacking it costs a user essentially nothing while
`EN` ("English US") stays pristine.

## Activation — an in-game selector, and its label is itself a string we own

`InGame.str` holds a complete `IDS_LanguageSelect_*` set (per-language display
names, `System Language`, a `DEV` slot, and a *"Applying this change will restart
Forza Horizon 6"* confirm popup). So:

> **Settings → Language → "English UK" → restart.**

After the restart that entry reads **"עברית"** (the proof already patches
`IDS_LanguageSelect_GB`). No config file, no registry, no launch argument.

## UI layer — XAML, and no evidence of text bidi

`media\UI.zip` = 455 files (386 `.xaml` + 69 `.xml`), Forza's "Anthem/AVUI"
XAML framework, 11.6 M chars, 2,462 `IDS_` references. Fonts are bound by name
(`FontFamily="Horizon_A|B|C|D|A_tf|RU_A"`).

* `FlowDirection` appears 22× and is **always `LeftToRight`**.
* Every `RightToLeft` hit (29) is a `ControllerButtonPanel Layout=` or a slide-
  transition style name; `Bidi` (8) is an element name for a centre-out slider.
* `Arabic` / `Hebrew` / `IsRtl` / `xml:lang`: **0 hits**.

⇒ **Prediction: the renderer does NO bidi → store VISUAL.** The proof decides.

## Font — the real gate, and it is currently unreachable

`media\UI\Fonts.zip` = 83 entries: `<name>.vfont` (a descriptor: 128-byte name
header, then counts + floats) + `<name>.vfontN` atlas pages (proprietary, not DDS).
Families are per script — `Horizon_A/B/C/D` (Latin), `Horizon_RU_A/C/D` (Cyrillic),
`Horizon_CHS/CHT/JP/KO` (CJK) — and `fontsettings.xml` gives each language an
include list with a fallback chain. **There is no Hebrew or Arabic entry anywhere**,
so Hebrew coverage is ~certainly zero and injection will be required.

**But the 7 descriptors that matter (`Horizon_A/B/C/D`, `Horizon_RU_A/C/D`) cannot
be read at all — `Fonts.zip` fails its xxh128.** A 4 KB-aligned scan of the whole
16 MB file finds no deflate stream producing them. This is a damaged file, not an
unknown format, so **the font work cannot start until the install is repaired.**

## DRM / integrity

No Denuvo, no EAC/BattlEye. The title is GDK/Store; this copy is a Steam repack
with a RUNE Steam emulator + an "Online Fix" loader. The game ships a content
hash list (`*.xxh128`) and `RapidCRC.exe` to check it, but that is an *installer*
integrity aid — there is no evidence of a runtime content check. **Unverifiable
until the exe exists**, so treat "do modified archives load" as OPEN.

## מסמכים קשורים
- באותה תיקייה: [[games/forza_horizon6/FEASIBILITY|FEASIBILITY]], [[games/forza_horizon6/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#forza_horizon6|CLAUDE_INDEX_games]]
