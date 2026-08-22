# AC Black Flag Resynced — mod-path re-research (2026-07-24, read-only)

## VERDICT: 🟢 **A LEGITIMATE PATH EXISTS — the target REOPENS.**

The 2026-07-17 "FINAL VERDICT: blocked by a SHA-256 content-integrity check" is
**contradicted by the live modding scene** and was almost certainly a
technique-specific misdiagnosis, not a game-side wall. As of today there is a
mature Nexus modding community for this exact title whose mods **modify the
`.forge` archives and load in-game** — including translation mods that inject a
**non-shipped script** (Thai), which is the precise proof the sibling AnvilNext
research relied on. The path forward for Hebrew is the community's own proven
mechanism, applied to the already-extracted Arabic loc slot.

**This is NOT a DRM/anti-tamper defeat.** No game-side integrity check blocks
forge content — proven empirically by hundreds of texture-mod and translation-mod
downloads that load. The path uses the standard Anvil override/inject mechanism
the whole community uses; the exe's VMProtect and its `SHA256`/`integrity`/`tamper`
strings protect the *code*, not the data archives.

---

## 1. The modding scene — modified forges demonstrably load TODAY

A full Nexus category tree now exists for the game
(`nexusmods.com/assassinscreedblackflagresynced`): **Gameplay 14 · Miscellaneous
16 · User Interface 4 · Utilities 4**. The decisive ones:

### Translation mods (the "non-shipped script renders" proof — analogous to Thai on AC Shadows)
| Mod | URL | What it ships / how it installs |
|---|---|---|
| **Thai localization** (NooneTranslation / custom LLM, v1.9, updated **2026-07-24**) | [mods/10](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/10) | **Copy a whole `DataPC_boot_patch_02.forge` + a `resources` folder into the game root.** Thai is NOT a shipped script → its rendering proves added forge content loads. Also on [simscolony](https://simscolony.com/) (Thai community). |
| **Ukrainian AI-translation** (uploaded 07-09, updated 07-17) | [mods/8](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/8) | Copy mod files into the game folder (next to `ACBlackFlag.exe`), then **run a bundled Python script (~5–10 min on SSD)** that patches the forge in place. |
| **Turkish (TÜRKÇE YAMA)** | [mods/31](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/31) | Menus + in-game text in Turkish. |
| **Bahasa Indonesia** | [mods/37](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/37) | Full loc. |

Ukrainian is not a shipped locale either. **Four independent translation mods,
adding two non-shipped scripts, all load.** That single fact retires the
integrity-wall conclusion.

### The tool that makes it a supported channel
| Tool | URL | Capability |
|---|---|---|
| **Forge Injector V1 BETA** | [mods/108](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/108) | A standalone **FORGE v50** resource injector for this exact title. Inspects/extracts/**replaces**/verifies/restores resources inside `DataPC_boot.forge`; ships **729 named Resource IDs**; detects raw-vs-LZO1X chunks, decompresses, checks decoded size, and **verifies each chunk against its per-chunk (adler32 "BMS") checksum**. Uses SHA-256 only to **fingerprint the game build** (pick the right offsets) — not to forge a game-side check. |
| "Encrypteds Resynced Ultimate Rewrite" | [mods/64](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/64) | Additional forge tooling. |

### Content (texture) mods editing `DataPC_boot.forge` in-place
Sail/flag/character skins — all installed by **running a bundled executable
injector**: "run the .exe, it auto-detects the game (or drag `DataPC_boot.forge`
onto it), wait for **SUCCESS (verification passed)**, launch." They "touch only
`DataPC_boot.forge` and only the specific texture," keep a backup record, and
"if a game update reverts the mod, just run the exe again":
[mods/96](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/96) ·
[97](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/97) ·
[98](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/98) ·
[106](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/106) ·
[109](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/109) ·
[124 National Flags](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/124) ·
[127 Black Beard Playable](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/127).

### Runtime/overlay mods (outside the data path — not evidence either way)
`ACBlackFlagFix` DLL/ASI FPS+FOV fixes
([mods/7](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/7)),
ReShade presets (Natural Colors
[mods/17](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/17),
Simple Realistic
[mods/22](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/22)),
a starter savefile
([mods/63](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/63)),
and Cheat-Engine trainers.

**⇒ Two proven deploy patterns, both loading in-game:**
1. **In-place surgical resource replace** in `DataPC_boot.forge` (Forge Injector /
   the texture mods' bundled exes) — every other resource stays byte-identical at
   its original offset; only the target resource's bytes are rewritten to its slot,
   with the per-chunk adler32 recomputed.
2. **Drop a higher-priority override forge** `DataPC_boot_patch_02.forge` (Thai) —
   the standard Anvil patch-forge override by fileID (a `patch_02` overrides
   `patch_01` and the base).

**Why the project's own attempt black-screened (best reconstruction):** the
2026-07 attempts used **append-relocate / full-repack into `DataPC_boot_patch_01`
(resource 1244)**. The community's working methods do the opposite — a *same-slot*
in-place replace in the **base** forge, or a *fresh* `patch_02` override. The
failure was in the write technique, not a content hash. (The project's own "Anvil
Deploy Law" already hinted at this: keep the forge contiguous, buffer==object.)

---

## 2. Official / supported mod path — **NONE**

- **No official mod support.** Steam:
  ["Ubisoft; Give us Mod Support for this"](https://steamcommunity.com/app/3751950/discussions/0/570414689743456370/)
  — users requesting it, reply "Not going to happen." No SDK, no in-game mod browser.
- **No `mods/` folder convention** — the live game root has `D3D12/`,
  `InstallerResources/`, `NVStreamline/`, `benchmark/`, `resources/`,
  `uplay_download/`, `videos/` and **no `mods/`** (verified read-only).
- **No RDR2-LML-style loose-file override loader** and **no ASI loader** — the
  root DLLs are all legitimate engine components (`dstorage`, `amd_fidelityfx_*`,
  `libxess*`, `GFSDK_Aftermath`, `upc_r2_loader64`, …); there is no
  `dinput8.dll`/`winmm.dll` proxy. `ACBlackFlagFix` is the only DLL/ASI mod and it
  hooks the exe at runtime, it does not load loose game assets.
- The community substitutes for this with **per-mod bundled injector exes** and
  **drop-in override forges** (§1).

---

## 3. Content OUTSIDE the integrity boundary

- **`resources/` at the game root is a LOOSE-file tree, read directly off disk**
  (not inside any forge). It holds **all 20 `AvenirNextWorld-*.ttf` UI fonts**
  (incl. the Hebrew-capable `-Regular.ttf`), the CJK fallback fonts, and the
  startup `.webm` videos. These are freely replaceable and load — proven by the
  "Akula Quick Launch" mod that swaps the `.webm`s for 0-byte placeholders, and by
  the Thai mod copying "a `resources` folder" in. **Any font work needs no forge
  edit at all** — and the shipped Regular font already contains all 27 Hebrew
  glyphs, so even that is unnecessary.
- **The Arabic text pack (`ara=65582`) lands INSIDE the forges**, not as a loose
  file. It is the char-index `LocalizationPackage` (nameHash `0x6e3c9c6f`, marker
  `0xD28389B5`) already extracted this project to
  `extract/arabic_ui.json` (idx 27724, ~11k strings) + `extract/arabic_subs.json`
  (idx 27725, ~5.3k). The Connect language pack downloads that loc into the forge
  layer; it is the same v50 format the community edits.
- **Post-install / patch forges are the SAME moddable format.** A game update
  landed **2026-07-22** (patch forges + both exes re-dated), and the Thai mod
  targets a `patch_02` override — confirming patched/DLC forges are covered by the
  identical (mod-friendly) mechanism, not a stricter check.

---

## 4. Integrity prior — re-measured today (report only)

`ACBlackFlag.exe` — **471,110,648 B, mtime 2026-07-22** (updated by the Jul-22
patch). Read-only string counts vs the 2026-07-11 baseline:

| token | 2026-07-11 | 2026-07-24 |
|---|---|---|
| `SHA256` | ~143 | **164** |
| `SHA-256` | — | 4 |
| `integrity` | 5 | **7** |
| `tamper` | 11 | **11** |
| `.vmp0`–`.vmp3` | present | **present (all 4)** |
| `denuvo` literal | (inferred) | 0 in-exe |
| `VMProtect` | present | 1 |

**No structural change** — VMProtect and the same integrity/tamper string profile
persist; the small count movement is ordinary build churn. Crucially, **these are
code-protection strings that demonstrably do NOT gate forge content** (texture +
translation mods that edit forges load with these strings present). The earlier
"SHA-256 on forge content" reading is not supported by the live evidence.
*(This is a passive measurement — no unpacking, no attempt to understand or defeat
any check.)*

---

## 5. Format-level prior art for forge v50

- **The Forge Injector V1 BETA ([mods/108](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/108)) is a working, public v50 reader+writer** with 729 named resource IDs and restore support — independent confirmation of this project's own from-scratch v50 crack, and proof the write side is solved by the community too.
- Multiple bundled per-mod v50 injectors ship inside the texture/translation mods.
- GitHub has BFR trainers/save-editors (e.g. `BiliaBjJA8/...Trainer`), memory-side only; the forge tooling lives on Nexus, not (yet) as an open GitHub library.
- **AnvilToolkit** still has no published BFR/v50 profile — but it is no longer needed; the project already reads AND writes v50 (`tools/acbf_forge.py`, `acbf_cfd.py`, `acbf_locpkg.py` with a byte-identical round-trip), and the community tool corroborates it.

---

## What changed between 2026-07-11 and today
1. **A full modding scene appeared** (game was 2 days old then; ~40+ mods now across 4 categories) — texture, gameplay, UI, and **four translation mods**.
2. **Modified forges are proven to load** (texture mods edit `DataPC_boot.forge`; Thai ships a `patch_02` override) — directly contradicting the black-screen conclusion.
3. **Non-shipped scripts render** (Thai, Ukrainian) — the exact bar the sibling AnvilNext research used.
4. **A public v50 Forge Injector exists** ([mods/108](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/108)) — a supported community write channel.
5. **A 2026-07-22 game patch** updated the exes/forges; **protection profile is unchanged** and still does not block forge mods.

## The Hebrew path this reopens
Reuse the community's proven mechanism with this project's already-built v50
codecs (all read+write side complete: `acbf_forge`/`acbf_cfd`/`acbf_locpkg`,
byte-identical round-trip):
1. Patch the **Arabic-slot** char-index LocalizationPackage (idx 27724 UI +
   27725 subs, already extracted) with Hebrew.
2. Deploy by **the working pattern** — either an **in-place same-slot resource
   replace in `DataPC_boot.forge`** (mirroring the texture-mod injectors and the
   Forge Injector, keeping every other resource byte-identical + per-chunk adler32
   correct), **or** ship a fresh **`DataPC_boot_patch_02.forge` override** (the Thai
   pattern) — instead of the append-relocate-into-patch_01 that black-screened.
3. Font: already free (shipped `resources/AvenirNextWorld-Regular.ttf` has all 27
   Hebrew glyphs; loose, no forge edit).
4. Activate via `HKCU\SOFTWARE\Ubisoft\Assassins Creed Black Flag Resynced\Language
   = ar-AA` and in-game Text = ar-SA.
5. Menu-proof in-game (legit key owned).

**What would RENEW a block:** only a future patch that (a) adds a genuine
game-side content hash over the forges *and* (b) breaks the in-place/override
mechanism the whole Nexus scene relies on. No sign of that — the Jul-22 patch did
not, and the scene keeps shipping.

---

### Constraints honoured
Read-only on `C:\Games\...` (listing + read-only `grep` only; nothing written,
game left clean). No launch, no deploy, no registry writes. No DRM/anti-tamper
circumvention, no exe unpacking, no research into defeating any check — this is a
**supported-channel** finding built entirely on public community mods + passive
measurement. `build_menu_proof.py --revert` NOT run.

**Sources:**
[Nexus BFR mods/top](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/top) ·
[categories](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/categories) ·
[Forge Injector #108](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/108) ·
[Thai #10](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/10) ·
[Ukrainian #8](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/8) ·
[Turkish #31](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/31) ·
[Indonesian #37](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/37) ·
[texture mods #96–#127](https://www.nexusmods.com/assassinscreedblackflagresynced/mods/96) ·
[Steam: "give us mod support"](https://steamcommunity.com/app/3751950/discussions/0/570414689743456370/) ·
[install guide (sportskeeda)](https://tech.sportskeeda.com/gaming-news/how-install-use-mods-assassin-s-creed-black-flag-resynced)

## מסמכים קשורים
- באותה תיקייה: [[games/acblackflag-resynced/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acblackflag|CLAUDE_INDEX_games]]

---

## 5. ⭐ CRACKED patch_02 RECIPE (2026-08-20, from real Thai #10 + Ukrainian #8 samples)

Downloaded + dissected both mods (`work/refmods/th`, `work/refmods/ua`). Both ship a
`DataPC_boot_patch_02.forge` with the **IDENTICAL 10-record structure** (only the loc
content differs), fully v50 (our `acbf_forge.parse` reads it, contiguity 9/9):

| rec | fileID | hash(type) | role |
|---|---|---|---|
| [0] | `0x46537fd8` | `0x6e3c9c6f` loc | **UI package** (Thai/UA differ → the one that carries text). base boot **idx 27730** = ENGLISH UI |
| [1] | `0x46537fd9` | `0x6e3c9c6f` loc | **Subtitles package**. base boot **idx 27731** = ENGLISH subs |
| [2,3,4] | `0x88c2952a/b/c` | `0xcbd4939a` | loc char-dictionary/atlas — **byte-identical Thai==UA**, also in base+patch_01. Copy verbatim |
| [5..9] | `0xc1,0xffa,0xff8,0x91,0x10` | `0x00000000` | patch-forge scaffold/manifest — **same set patch_01 ends with** (5591-5595). Copy verbatim |

- **UA[0] decodes to 11,033 UI strings, UA[1] to 5,388 subtitle strings** (Ukrainian) —
  matches our extracted Arabic scope (~11k UI + ~5.3k subs). Confirms build_payload target sizes.
- **Install (UA `Встановлення.txt`):** drop `DataPC_boot_patch_02.forge` next to
  `ACBlackFlag.exe`; **in-game select interface language = "English"**; uninstall = delete file.
  ⇒ the community hijacks the **English** slot (fileID 0x46537fd8/d9), NOT Arabic. No registry.
- **Thai also ships a loose `resources/` with all 20 `AvenirNextWorld-*.ttf`** (Thai glyphs
  injected); **UA ships NO fonts** (Cyrillic already in the shipped font) — **exactly Hebrew's
  case** ⇒ UA is our clean template, zero font work.

**⇒ Minimal Hebrew patch_02 build:** clone UA forge, rebuild ONLY records [0]+[1] with Hebrew
loc (our `acbf_locpkg.build_payload`+`acbf_cfd.build_cfd`), copy [2..9] verbatim, re-pack TOC
(`repack_patch.py` logic; trivial at 10 recs), drop in game root.

**OPEN DECISION — RTL slot:** English slot (27730/31, community path, select "English", but Hebrew
may render LTR) vs Arabic slot (27724/25, needs `Language=ar-AA`, RTL native). Resolve with ONE
multi-mode menu-proof that injects Hebrew into BOTH slots; user toggles menu language to decide.

---

## 6. 🎯 ARABIC-NATIVE PATH — font atlas map (2026-08-20)

**Why Arabic:** English slot works (Hebrew renders) but has NO bidi -> needs pre-reversed
visual order and stays LEFT-aligned. The Arabic slot gives native engine bidi (right-aligned,
correct order) but Hebrew = TOFU.

**PROVEN (in-game, by elimination):** the Arabic text path does NOT use the loose
`resources/AvenirNextWorld-*.ttf`:
1. cmap-hijack (Arabic carrier codepoints -> existing Hebrew glyphs, font verified valid) = ZERO effect.
2. **Outline overwrite** of ALL 487 Arabic-region glyphs (every isol/init/medi/fina form +
   ligatures, GSUB-expanded) with the shin outline, all 20 fonts = **ZERO effect** ("ערבית מלאה").
⇒ Arabic glyphs come from a **baked glyph atlas inside the forge**, not a runtime TTF.
Also: full scan of DataPC_boot.forge (40,575 resources 40KB-30MB) = **0 embedded sfnt fonts**.

**FOUND — the atlases are resource class `0xcbd4939a`** (Anvil "MapDesc"-style font resource;
per AnvilToolkit wiki, Anvil fonts = texture atlas + MapDesc metrics, edited as DDS textures,
split per script/language e.g. Latin/Russian/Asian). In `DataPC_boot.forge`, 11 records:

| idx | fileID | on-disk | decoded | note |
|---|---|---|---|---|
| 16243 | 0x88c2952a | 593,963 | 2,080,447 | **shipped in every patch_02** (Latin/shared) |
| 16245 | 0x88c2952b | 189,322 | 847,577 | **shipped in patch_02** |
| 16248 | 0x88c2952c | 578,006 | 2,030,243 | **shipped in patch_02** |
| 19498 | 0x88cf5a5b | 4,089,685 | 12,375,614 | **contains `BC7`** — script atlas candidate |
| 19499 | 0x8b21454b | 2,995,726 | 10,601,705 | **contains `BC7`** — script atlas candidate |
| 19500 | 0x88cf5a5c | 3,983,466 | 13,486,283 | |
| 70970-70974 | 0x88c902b3/b5/b1, 0x88cab006, 0x88c902b0 | 0.7-1.4 MB | 3.7-6.3 MB | |

**KEY: these are overridable through `patch_02` exactly like the loc records** (the 3 above are
literally shipped in the Thai/UA mods' patch_02) ⇒ **deploy is already solved**; no new mechanism.

**Remaining gates for Arabic-native Hebrew:**
1. Identify WHICH atlas serves the Arabic UI (8 candidates; BC7 ones first).
2. Crack the MapDesc metrics (char/glyph -> atlas rect + advance/bearing) — compiled Anvil
   resource, no schema; the Forge Injector's guide confirms these are BMS/texture entries.
3. Draw Hebrew glyphs into the atlas (BC7 encode) + add their metrics.
4. Store Hebrew as Arabic CARRIER codepoints (`work/hebrew_arabic_hijack.py`) so the engine's
   Arabic RTL path picks them up -> native right-aligned Hebrew.

⚠️ Decoding these is slow (12MB / 48 Oodle blocks) — cache decoded atlases to disk, never
decode inline in a short-timeout shell.
