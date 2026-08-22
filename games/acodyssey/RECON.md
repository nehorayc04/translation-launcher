# AC Odyssey — RECON

**Install** `F:\Games\Assassin's Creed Odyssey` · Ubisoft Quebec 2018 · **AnvilNext 2.0**
exe `ACOdyssey.exe` (285 MB) + `ACOdyssey_plus.exe` · Uplay-emulated (`uplay_r1_loader64.dll`)
**`games.id` = `acodyssey`** (the catalog row already existed — check before proposing an id)
detector exe `ACOdyssey.exe`, marker `DataPC_ACD_Greece.forge`

## Container

**scimitar `.forge` version 28** — the gap between AC Unity (v27) and AC Mirage (v29).
🔑 **The Mirage v29 reader parsed every Odyssey forge UNCHANGED** (`total_count == entries
read`, 0 contiguity violations on all 33 readable forges) — container work was reuse, not
re-derivation ([[engine-family-reuse-check-magic]]).

```
0x00  "scimitar\0"      0x09  u32 version = 28      0x0d  i64 header_size = 1050
1050  i64 total_count · i64 0 · i32 -1 · i64 -1 · i32 count+6 · i32 fileset_count
      i64 first_fileset (= 1094)
FileSet: +0x00 u32 count · +0x10 i64 next (-1 = last) · +0x30 entries
Entry (20 B): i64 offset · u64 id · i32 length_on_disk
```

No name table (like v29/v42) → resources are located by **content** (the u32 ScimitarClass
hash at `content[0]`), never by name. 33 forges, **443,356 entries**.
⚠️ `DataPC_ACD_greece_ext.forge` (21 GB) returned *Permission denied* — a lock, not a format
problem; it holds world geometry and no localization.

## Codec

Resource blobs are **CFD** — magic `0x1004FA9957FBAA33`, identical to AC Shadows v42 and
Mirage v29: 7-byte CompressionInfo, `i32 blockCount`, `{i32 uncomp, i32 comp}` table, then
per block `{u32 adler32(comp, 0), bytes}`. 399/399 resources decoded with 0 failures.

- The game **ships its own `oo2core_4_win64.dll`** — no borrowing.
- **Odyssey MIXES codecs per resource**: entry #1 is **Mermaid**, entry #60 is **Kraken**.
  Read it from `byte1 & 0x7F` of a real block, never assume
  ([[oodle-codec-is-byte1-not-byte0]]). `aco_cfd.sniff_codec` does this per resource, and a
  re-encode with the sniffed codec is **BYTE-IDENTICAL to disk** on both.

## Text

**66 `LocalizationPackage` resources** (class `crc32("LocalizationPackage") = 1849465967`),
one contiguous block, `DataPC.forge` **and** `DataPC_patch_01.forge`. None in extra /
SharedGroup / Greece / PresentDay / TitleScreen.

🔑 Unlike Mirage, **object names are PLAINTEXT and never encrypted** — a package is addressed
by name (`LocalizationPackage_Arabic`).

```
[u32 class][i32 obj_size][i32 name_len][name][… base …]
[i32 Type][u32 Language][12 pad][u32 marker 0xD28389B5][i32 count][BE payload]
```
Payload = the char-index / fragment-tree store shared with AC2 v25 / Unity v27 / Mirage v29 —
`acu_loc.decode_payload` works verbatim. `Type` 0 = UI, 1 = Subtitles.

**🔴 The language-id enum is NOT a standard one.** A plausible guess was wrong by an offset on
the European block; the map was DERIVED by reconciling each id against its own package name:
`1 English · 2 French · 3 Italian · 4 German · 5 Spanish(Spain) · 6 Spanish(Mexico) ·
8 Portuguese(Brazil) · 9 Czech · 11 Dutch · 16 Polish · 17 Russian · 18 Japanese · 19 Korean ·
20 Chinese(Trad) · 21 Chinese(Simp) · 22 Arabic · 23 Auditioning(Male) · 24–39 the parallel
"_MTM" family · 39 LocTest`.

**🔴 §8e — the PATCH forge shadows the base.** The same 62 package ids exist in
`DataPC_patch_01.forge` with **different, larger payloads** (English UI 639,263 vs 612,481 B;
25,763 strings vs 24,590). Both are patched; the patch is the authoritative one.

## RTL slot

🟢 **Arabic is a first-class shipped locale** — `uplay_install.state` registers 15 languages
ending in `ar-AA`, and **two full Arabic packages ship populated**:
`LocalizationPackage_Arabic` (lang 22) and `LocalizationPackage_Arabe_MTM` (lang 24), each
with UI + Subtitles. No Arabic *readme* ships → Arabic is a **text-only MENA locale**, so
English VO is preserved.

**Activation = a plain-text INI, settled by reading the game's own config**
`%USERPROFILE%\Documents\Assassin's Creed Odyssey\ACOdyssey.ini`:
```
[Language]
Text=ar-AR   Subtitles=ar-AR   Client=ar-AR   Sound=en-US
```
🔴 The code is **`ar-AR`**, NOT `ar-AA`. `uplay_install.state` pairs them
(`…\Language` + `ar-AA` + `ar-AR`): `ar-AA` is Ubisoft's language-PACK id, `ar-AR` is the value
the game reads. Every *other* locale has that pair identical (`en-US`/`en-US`), which is
exactly why the difference is easy to miss. `Sound` is independent → **English VO for free**.
The mirror registry value is `HKCU\SOFTWARE\Ubisoft\Assassins Creed Odyssey\Language`.

## Fonts

**15 `FontFile` resources** (class 3295364632) in `DataPC.forge`, and **15 more in
`DataPC_patch_01.forge` under different ids with byte-identical TTFs** — both sets exist, so
both are injected. Object layout is delta-13, byte-for-byte the same as Mirage:
`… i32 ttf_len @26 · sfnt @30`.

| face | ttf | glyphs | Hebrew | Arabic |
|---|---:|---:|---:|---:|
| DINPro ×7 (Latin/Cyrillic) | 173–392 KB | 1,668–1,836 | 0/27 | 0/43 |
| **DINPro (Arabic UI face)** | 511 KB | 1,936 | **0/27** | **37/43** |
| DINCond-Medium / -Bold | 30/31 KB | 230 | 0/27 | 0/43 | ← **CFF/OTTO** |
| Friz Quadrata TT (display) | 62 KB | 252 | 0/27 | 0/43 |
| DFPHeiW5-A / DFPHeiMedium-B5 / DFHSGothic-W5 / MDChamGothicL_NC | 0.8–19.5 MB | 3.9–29 K | 0/27 | 0/43 |

⇒ Hebrew injection required. Donor = **Heebo** (the Hebrew companion to Roboto, the closest
geometric-sans match to DIN — the same pairing that worked for Mirage's DINPro).

## DRM / integrity

No Denuvo strings, no EAC/BattlEye (single-player). A Uplay emulator is already in place.
The append-relocate deploy was validated on a copy of the real 3.26 GB patch forge with
301 untouched resources byte-identical — see FEASIBILITY.md.

## מסמכים קשורים
- באותה תיקייה: [[games/acodyssey/FEASIBILITY|FEASIBILITY]], [[games/acodyssey/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acodyssey|CLAUDE_INDEX_games]]
