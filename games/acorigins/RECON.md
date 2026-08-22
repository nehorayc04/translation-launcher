# AC Origins — RECON

**Install** `F:\Games\Assassin's Creed Origins` · Ubisoft Montreal 2017 · **AnvilNext 2.0**
exe `ACOrigins.exe` (241 MB) + `ACOrigins_plus.exe` · Uplay-emulated (`uplay_r1_loader64.dll`)
Proposed **`games.id` = `acorigins`** — ⚠️ CHECK the live catalog before proposing an id; the
detector key must equal the existing `games.id` (the Odyssey trap: I proposed `ac-odyssey`
and the real row was `acodyssey`).
detector exe `ACOrigins.exe`, marker `DataPC_ACE_Egypt.forge`

## Container — pure reuse

**scimitar `.forge` version 28, header_size 1050 — BYTE-IDENTICAL in layout to AC Odyssey.**
Checking the magic first ([[engine-family-reuse-check-magic]]) collapsed the entire
container + codec + loc + font + deploy workstream into a copy of `games/acodyssey/tools/`
with the paths retargeted. `DataPC.forge` parses **707/707 entries, 0 validation errors**.

```
0x00  "scimitar\0"      0x09  u32 version = 28      0x0d  i64 header_size = 1050
1050  i64 total_count · i64 0 · i32 -1 · i64 -1 · i32 count+6 · i32 fileset_count
      i64 first_fileset (= 1094)
Entry (20 B): i64 offset · u64 id · i32 length_on_disk
```
No name table → resources are located by the u32 ScimitarClass hash at `content[0]`.
**62 forges in the root + 18 `dlc_*` dirs.**

## Codec

**CFD** — magic `0x1004FA9957FBAA33`, 7-byte CompressionInfo, `i32 blockCount`,
`{i32 uncomp, i32 comp}` table, per block `{u32 adler32(comp,0), bytes}`.
The game **ships its own `oo2core_4_win64.dll`** — no borrowing. Codec is sniffed per
resource off `byte1 & 0x7F` ([[oodle-codec-is-byte1-not-byte0]]).

## Text — 34 LocalizationPackages, and the shape differs from Odyssey

`LocalizationPackage` = `crc32 1849465967`. Object names are **PLAINTEXT** (never encrypted),
so a package is addressed by name.

| source | packages | note |
|---|---|---|
| `DataPC.forge` | 34 | the base game — 16 UI + 16 Subtitles + an empty Spanish(Mexico) pair |
| `DataPC_22_dlc_patch_01.forge` | 6 | `DLC22-30_*` (Hidden Ones / Curse of the Pharaohs) |
| `dlc_32/DataPC_32_dlc.forge` | 4 | `DLC32_Upsell_*` — store promo, 1,597 B, ignorable |

**🔴 There is NO `DataPC_patch_01.forge`** — unlike Odyssey, nothing shadows the base loc
(§8e does not fire for the base text). The two DLC sources are additive, not shadows.

```
[u32 class][i32 obj_size][i32 name_len][name][… base …]
[i32 Type][u32 Language][12 pad][u32 marker 0xD28389B5][i32 count][BE payload]
```
Payload = the char-index / fragment-tree store shared with AC2 v25 / Unity v27 / Odyssey v28 /
Mirage v29 — `acu_loc.decode_payload` works verbatim. `Type` 0 = UI, 1 = Subtitles.

## 🔴🔴 THE DEFINING FACT — Arabic ships for SUBTITLES ONLY

| package | payload | records |
|---|---:|---:|
| `LocalizationPackage_Arabic` (**UI**) | **457 B** | **20 — a STUB** |
| `LocalizationPackage_Arabic_Subtitles` | **372,940 B** | **12,844 — full** |
| `LocalizationPackage_English` (UI) | 285,764 B | 8,223 |
| `LocalizationPackage_English_Subtitles` | 404,676 B | 14,782 |

Exactly the **AC Unity** pattern. The 20 stub rows are nevertheless REAL translations
(`خيارات`=OPTIONS, `العربية`, `تجهيز`=EQUIP …), so the package is a live object, just empty —
which is why filling it is worth laddering rather than assuming it is dead.

## 🔑 Activation — TWO INDEPENDENT surfaces, and the code is `ar-AR`

`%USERPROFILE%\Documents\Assassin's Creed Origins\ACO.ini` (plain text):
```
[Language]
Text=en-US        <- the UI
Sound=en-US       <- English VO, preserved for free
Subtitles=ar-AR   <- the subtitle language, fully independent
Client=en-US
```
`uplay_install.state` registers 15 language packs ending `ar-AA`, and
`HKCU\SOFTWARE\Ubisoft\Assassins Creed Origins\Language` = `ar-AA`.
**`ar-AA` is Ubisoft's language-PACK id; `ar-AR` is what the GAME reads** — the game's own
config is the tie-breaker, exactly as on Odyssey. No Arabic `Support/Readme` ships ⇒ Arabic
is a **text-only MENA locale**.

⇒ **UI Hebrew in the English slot costs the user ZERO actions** (en-US is the default);
subtitles cost ONE in-game setting.

## Scope (`work/scope_report.py` → `extract/scope.txt`)

| count | value |
|---|---:|
| records, all English packages | 23,005 |
| sum of per-package uniques (**wrong to quote**) | 21,947 |
| **GLOBAL unique English strings** | **21,924** |
| characters | 1,322,501 |

UI 8,223 records / 7,678 unique · median 25 ch · max 2,699
Subs 14,782 records / 14,269 unique · median 46 ch · max 961
**UI and subtitle id spaces are disjoint (overlap 0).** A single-pass job — no fleet needed.

## Oracle panel — free and wide

**12 languages at 100.0 % key parity with English on the UI** (fr de it es ru pl cs nl br ja
ko + zt/zs) and 86.9 % on subtitles. ru+pl give speaker AND addressee gender, fr/it/es the
referent, de the register, and the shipped **Arabic subtitles** are the Semitic near-match.
Arabic UI parity is 0.2 % — the stub, as expected.

## 🔴 DEDUP BY THE ENGLISH STRING IS UNSAFE — measured, not assumed

| surface | duplicate-EN groups | divergence in the game's OWN locales |
|---|---:|---|
| UI | 368 (913 ids) | pl 15.5 % · ru 12.8 % · fr/de 9.2 % · it 6.5 % · es 6.2 % |
| subtitles | 288 (801 ids) | **ru 44.7 % · fr 38.8 % · de 36.5 % · pl 32.2 % · ar 28.6 %** |

Seven independent professional locales agree that a third of the duplicate subtitle groups are
context-dependent ⇒ **key the pool by id, never by the English string**
([[dedup-safety-from-game-langs]]).

## Tokens (measured on Origins' own corpus)

`[...]` 676 occ · `<...>` 253 · `{...}` 188 (only 6 distinct: `{0} {1} {2} {DD} {HH}`) ·
`\n` 2,143 · `%d`/`%l` 16 · `&entity;` **0**.

**🔴 Brackets are OVERLOADED** — 366 engine-token occurrences vs **310 prose**, and the game's
own professional Arabic **translates 239 of the prose ones and keeps 1 verbatim**
(`[sigh]`, `[Save Icon]`, `[Locate Zone Icon]`, `[Hem Netcher]`). A verbatim `[...]` guard
would silently strike out ~240 real lines (the AC2 failure class).
⚠️ **ORIGINS DELTA:** this game also uses `[KB_LeftShift]` and `[RightStick]`-style tokens that
are NOT ALL-CAPS, so Odyssey's `_ENGINE_BR` classified them as prose. Widened in `aor_rtl.py`.
A small tail (`[A]`, `[Bm]`, `[Dpad]`, `[0x00100100]`) still misclassifies — Phase 2 should use
the pro-Arabic itself as the per-bracket oracle, which beats any regex.

## Fonts — 9, all `glyf`, all injectable

`FontFile` = `crc32 3295364632`, **9 resources, all in `DataPC.forge`**, all **0/27 Hebrew**:

| face | outlines | glyphs | Arabic | note |
|---|---|---:|---:|---|
| DINPro (576 KB) | glyf | 1,936 | **37/42 + 141 pres** | the Arabic-bearing UI face |
| DINPro ×3 (~173 KB) | glyf | 1,668 | 0 | Latin/Cyrillic UI |
| MDChamGothicL_NC | glyf | 3,886 | 0 | Korean |
| ACE-TrajanBold | glyf | 1,937 | **37/42** | display / titles |
| ACE-SimplifiedChinese-Noto | glyf | 30,493 | **37/42** | CJK fallback |
| DFPHeiMedium-B5 · DFHSGothic-W5 | glyf | 15,077 · 8,010 | 0 | CJK fallbacks |

**🟢 Better than Odyssey: NOT ONE face is CFF/OTTO**, so a glyf merge works on every one —
Odyssey had to leave 2 `DINCond` faces un-injected. All 9 injected to **27/27** from **Heebo**.

## DRM / integrity

Denuvo + VMProtect on the exe (`.vmp0`/`.vmp1`, a 140 MB `.xtls`), but **0 EasyAntiCheat,
0 BattlEye, 0 `tamper` strings, 3 `integrity`, 41 `SHA256`** — the AC-Shadows profile
(asset mods load), not the AC-Black-Flag-Resynced profile (SHA-256 content wall, ×143/×5/×11).
Denuvo protects the executable, not the asset forges. This copy is Uplay-emulated anyway.
Corroborated by AC Origins' large, mature forge-mod scene.

## Deploy

**Append-relocate** (`aor_deploy.apply`): append the new blob at EOF, patch only that record's
`offset` (+0) and `length` (+16). Header, FileSet table and every other resource stay
byte-identical. Required because the rebuilt payload is **~2× the shipped size** (the game uses
a multi-char fragment dictionary, our encoder is single-char), so nothing fits in place.
Pristine `DataPC.forge.he_backup` + `DataPC.forge.he_journal.json`.

## מסמכים קשורים
- באותה תיקייה: [[games/acorigins/FEASIBILITY|FEASIBILITY]], [[games/acorigins/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acorigins|CLAUDE_INDEX_games]]
