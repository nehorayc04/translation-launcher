# 007 First Light — RECON (Phase-1 groundwork, 2026-07-10)

## The game
- **Title:** 007 First Light (IO Interactive, Oct 2025 — origin-story James Bond).
- **Engine:** **Glacier** (the Hitman engine). One of the most heavily-modded engines that exists.
- **Install (staging/play copy):** `F:\Game Lab\007 First Light\`
  - `Retail\007FirstLight.exe` (342 MB) + graphics/audio DLLs (D3D12, DLSS, PhysX, dstorage…).
  - `Runtime\chunk0.rpkg` (20.7 GB), `Runtime\chunk1.rpkg` (35.8 GB), `packagedefinition.txt`, `Retail\thumbs.dat`.
- **Steam appid:** `3768760`. Detector/`games.id` candidate: **`007-first-light`** (kept hyphenated,
  matching the `ac-shadows` convention so the launcher install-finder resolves it).
- **DRM:** cracked build — `Retail\voices38.dll` (Denuvo bypass, user-mode) + Goldberg
  (`steam_api64.dll` + `steam_settings\`). **DRM-free for our purposes**; Denuvo (if present) protects the
  exe only, never the asset RPKGs (proven by the active Nexus asset-mod scene). No EAC/BattlEye (SP game).
- **DLCs:** all cosmetic (skins/outfits/gadget skins) — no language packs. Languages ship inside the RPKGs.

## Container — RPKG v2 ("2KPR") — FULLY CRACKED, pure-Python reader validated
`games/007_first_light/tools/gl_rpkg.py` parses **both** chunks with **exact** metadata consumption
(consumed == table_size, 0 error) — chunk0 = 284,971 files, chunk1 = 464,014 files.

Header (25 bytes, base package — no patch):
```
0x00 char[4] "2KPR" | 0x04 byte[9] unknown | 0x0d u32 file_count
0x11 u32 hash_header_table_size (= file_count*20) | 0x15 u32 hash_resource_table_size
```
File table 1 (hash table) at 0x19, `file_count × 20`: `{u64 hash; u64 data_offset; u32 data_size}`.
- `data_size`: **bit 0x80000000 SET ⇒ XORed**; low 30 bits = compressed size (0 ⇒ stored/not LZ4).

File table 2 (metadata) right after table 1, `file_count` entries — **007-specific: 20-byte base**
(the Hitman `reference_table_dummy` u32 was REMOVED on the first-light branch):
```
+0 char[4] resource_type (stored REVERSED) | +4 u32 reference_table_size
+8 u32 size_final (decompressed) | +12 u32 size_in_memory | +16 u32 size_in_video_memory
if reference_table_size>0: u32 depends_count(low30=count); count×u8 flag; count×u64 hash  => 4+9*count bytes
```
Resource read: seek `data_offset`, read on-disk bytes; **if XORed → `xor_data` (key
`DC 45 A6 9C D3 72 4C AB`, byte%8)**; if LZ4'd → raw-block decompress to `size_final`; else raw.

## Resource inventory (both chunks)
| type | chunk0 | chunk1 | meaning |
|---|---:|---:|---|
| **DLGE** | 18,769 | 23,387 | dialogue/subtitle containers (per-language subtitle + WAV/switch refs) — **the bulk** |
| **LOCR** | 164 | 37 | UI/menu/HUD/item text (per-language string tables) |
| **TEXT** | 8,248 | 23,523 | shader/other text (NOT localization) |
| **GFXF** | 14 | — | **Scaleform GFx FONTS** (the UI font resources) |
| GFXV / GFXI / GFXA | 144 / 2,673 / 18 | 73 | Scaleform GFx movies / images / atlases (the UI is Scaleform) |
| RTLV | 2 | — | localized video (subtitle-in-video) |
| CLNG | 1 | — | language-slot list |
| UICB / UICT | 70 / 69 | — | UI control blueprint/template |

## Localization format — cracked + validated (read AND write)
- **Crypto** (from RPKG-Tool `first-light` branch `crypto.cpp` + TonyTools `Languages.cpp`):
  - Resource XOR key `DC 45 A6 9C D3 72 4C AB` (same as Hitman).
  - **LOCR/DLGE string XTEA — 007-SPECIFIC key** `{0x68AC3361, 0x562B4AA0, 0xB9F2771F, 0x28EB3CE7}`,
    delta `0x9E3779B9`, 32 rounds (Hitman used `{0x53527737,…}` — 007 changed it, commit
    "[RushPKG] Update thumbs + l10n XTEA keys").
  - `packagedefinition.txt`/`thumbs.dat` XTEA key `{0x71482CF0,…}`, delta `0x61C88647` (not needed yet).
- **LOCR** (`tools/gl_locr.py`, `decode_locr`/`decode_clng`/`xtea_encrypt/decrypt` — all validated):
  `u8 version` + `numLangs×u32 offset` table (numLangs=(offset0-1)/4; 0xFFFFFFFF=empty) → per-language
  block `u32 numStrings` + `numStrings × {u32 lineHash; u32 encLen; encLen XTEA bytes; u8 0x00}`.
  Strings = **UTF-8**. `lineHash` is the shared key across all languages → map EN→HE by hash.
  - **164/164 chunk0 LOCRs decoded clean.** Ciphertext round-trip **119/119 byte-identical**;
    Hebrew UTF-8 encrypt→decrypt clean → **write path proven**.
- **CLNG** = one `bool` byte per language slot. Ours = **15 bytes → 15 slots**.

## Language map (identified from real LOCR content — 15 slots, NO Arabic/Hebrew)
```
0 xx(EN src)  1 en  2 fr  3 it  4 de  5 es(Spain)  6 ru  7 mx(LatAm-Spanish)
8 br(Portuguese)  9 pl  10 cn(Chinese-Simpl)  11 jp  12 tc(Chinese-Trad)  13 kr(Korean)  14 tr(Turkish)
```
= the Hitman-H2 langmap (`xx en fr it de es ru mx br pl cn jp tc`) + **kr + tr** appended. All LTR/CJK.
CLNG bools: slots 0,1 = false (xx/en base), 2–14 = true.

## Scope (measured)
- **UI (LOCR) ≈ 7,306 unique strings** (chunk0; avg 51 chars) + chunk1's 37 LOCRs (some overlap).
- **Dialogue/subtitles (DLGE) ≈ 42,156 containers** (18,769 + 23,387) — decode format TODO (located).
- **Total ≈ 49k** — matches the community Arabic mod's stated "~48,000 entries".

## Tools built this session (`games/007_first_light/tools/`)
- `gl_rpkg.py` — RPKG v2 read-only reader (`info`/`types`/`find`/`dump`), exact-parse validated.
- `gl_locr.py` — LOCR/CLNG decode + XTEA (007 key) encode/decode, round-trip proven.

## Sources
- Container: Picoseconds/GlacierFormats `hitman3_rpkg2.ksy`; glacier-modding/RPKG-Tool `first-light`
  branch (`import_rpkg.cpp`, `hash.h`, `crypto.cpp`, `extract_locr_to_json_from.cpp`).
- LOCR/DLGE/CLNG format + langmaps: AnthonyFuller/TonyTools HMLanguages `Languages.cpp`.
- Precedent: Nexus `007firstlight` mod #11 (Arabic, ~48k, injected Arabic font + full RTL) +
  #55 (Greek) + Turkish community effort → **active text-mod scene, RTL proven on this exact game**.

## מסמכים קשורים
- באותה תיקייה: [[games/007_first_light/FEASIBILITY|FEASIBILITY]], [[games/007_first_light/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#007_first_light|CLAUDE_INDEX_games]]
