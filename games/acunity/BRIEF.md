# AC Unity Hebrew — Groundwork Research Brief (decisive)

**Date:** 2026-07-01. **Scope:** synthesize the 4-angle research sweep + the 2 adjudicated
verdicts into a single decisive Phase-1 brief. Seeds `FEASIBILITY.md` / `RECON.md`.

Game: **Assassin's Creed Unity** (2014, Ubisoft Montreal, **AnvilNext 2.0**), install
`E:\Games\Assassin's Creed Unity`, exe `ACU.exe`, DRM = **Uplay/Ubisoft Connect + VMProtect
(no Denuvo)**. Archives = `.forge`, magic `"scimitar\0"`, **version 27** (`u32@9`) — the
AC3/Black-Flag/Rogue/Unity/Syndicate AnvilNext generation (AC2 = v25, AC Shadows 2025 = v42).

> **Reading key.** `CONFIRMED` = independently verified (code/tool/peer-reviewed source, cited).
> `INFERRED` = strong reasoning from confirmed facts, not a direct citation → **verify before
> investing**. Ground-truth facts I proved directly on the real game files (container index,
> v27, the Arabic slot's existence, STORED loc) are treated as settled and built upon.

---

## TL;DR verdict — 🟢 **GO-WITH-CAVEATS** ("prove the repack, then run")

AC Unity is the **strongest-positioned** AC in this repo. **4 of the 5 pillars are CONFIRMED
solved or de-risked**; the whole project is gated on **one** thing:

> **#1 GATE — a v27 forge REPACK that both (a) the game loads and (b) survives Ubisoft
> Connect's file-integrity check.** The repack *capability* exists and is free (AnvilToolkit);
> the *deploy-integrity* wrinkle (Connect can demand an activation key after a forge swap) is the
> real operational risk. Everything else (container read, LZO codec, char-index loc class, Arabic
> slot present, no-Denuvo, huge modding scene) is CONFIRMED.

**Recommended next empirical step (one afternoon, decides the project):** a **Stage-0 identity
round-trip** — unpack `DataPC.forge`, repack it UNCHANGED with AnvilToolkit (or our own writer),
drop it in, launch. If it boots identically **and Ubisoft Connect does not demand a key**, the
gate is closed. Do this BEFORE the bidi/font work. Pair it with a **vanilla Arabic-slot
in-game check** (set text = Arabic on the untouched game, observe whether shipped Arabic renders
readable RTL) — that simultaneously answers the bidi question below.

---

## 1. Forge v27 codec + repack tool/format — the deploy gate

### Codec — **LZO** (CONFIRMED), Oodle absent
Compressed DataFile chunks inside v27 resources use **LZO**, with the per-block variant chosen by
a `compression_type`/mode byte:

| mode byte | LZO variant |
|---|---|
| `0` or `1` | `lzo1x` (the common path) |
| `2` | `lzo2a` |
| `5` | `lzo1c` |
| — | if `len(src)==dst_len` → block is **STORED** (returned verbatim, not compressed) |

- **Source of truth:** ACExplorer (`gentlegiantJGC/ACExplorer`) `pyUbiForge/misc/decompress_.py`
  calls a bundled `lzo32/lzo64.dll` with exactly this mode→variant switch. Independently,
  Blacksmith's CHANGELOG lists LZO `(1X, 1C, 2A)` for AC "III, Black Flag, **Unity, Syndicate**".
- **Oodle is NOT used** at the Unity generation (Oodle enters Anvil at Origins/Odyssey ~2017). So
  a repacker only needs `liblzo2` (`lzo1x_1_compress` for the write path). Runtime DLLs
  `lzo2_w64.dll` + `zstdlib.dll` ship with Delutto's Data Tool.
- **Deploy consequence:** our **loc packages are STORED** (I verified on-disk size ==
  uncompressed_size), so **translation READ is fully unblocked with no codec at all**. LZO is
  only needed to (a) read *compressed* resources (fonts/textures) and (b) re-compress if a repack
  ever needs to shrink a grown resource.

### Compressed chunk header (CONFIRMED — two `format_version` paths)
A compressed resource blob starts `33 AA FB 57 99 FA 04 10` (= `u32 0x57FBAA33`, then
`u32 0x1004FA99`, LE). Then (per ACExplorer `_read_compressed_data_section`):
- skip 2 · `u8 compression_type` (the LZO mode) · skip 3 · `u8 format_version`.
- **`format_version == 0`:** `u8 comp_block_count` (==1); size table of `u32` pairs
  `[compressed_size, uncompressed_size]`; per block skip a **4-byte hash** then read
  `compressed_size` bytes → LZO-decompress to `uncompressed_size`.
- **`format_version == 128 (0x80)`:** `u32 comp_block_count`; size table of `u16` pairs
  `[uncompressed_size, compressed_size]`; per block skip a 4-byte hash then read `compressed_size`.
- A large resource may hold a **second `0x57FBAA33` block** immediately after the first (reader
  concatenates). Non-compressed resources simply lack the `0x57FBAA33` magic.
- **A 010 Editor template exists** (`resources/010 Editor Templates/ACUDecompressedRawData.bt`)
  encoding the decompressed sub-file struct — a ready cross-check.

### Repack tool — **AnvilToolkit = YES, free, Unity-supported** (CONFIRMED)
- **`AnvilToolkit`** (by Kamzik123) — free on Nexus (`nexusmods.com/assassinscreedunity/mods/38`,
  hub at `site/mods/455`). Explicitly lists **Assassin's Creed: Unity** in supported games.
  Documented workflow (Kamzik123/AnvilToolkit-Resources wiki, Lesson 1): unpack `DataPC.forge` →
  open `xx_-_LocalizationPackage_<Lang>.data` → **Export to XML** → edit → **Import XML** →
  **Repack** the forge. Users on the Unity Nexus page report the repack succeeding
  ("all I needed was the file to repack and it worked"). GUI-only, closed-source .NET (requires
  .NET 5) → usable as an interactive tool, **NOT bundle-able into the launcher**.
- **End-to-end game-load proof (CONFIRMED it's possible, INFERRED which tool):** 2025 community
  English-localization mods for Unity ship a modified `DataPC.forge` + `DataPC_10_dlc.forge` that
  ACU.exe loads in-game (Steam guides `3075396573`, `3413126749`). They distribute the finished
  forges, not the toolchain → "AnvilToolkit built THOSE files" is inferred, but AnvilToolkit's own
  repack capability is separately confirmed.
- **Read reference (pure-Python):** `ACExplorer` fully supports v27 read (hard-checks
  `version==27`) — best open spec for container + chunk + LZO, but **READ-ONLY, no repack**. We
  already reproduce its container logic in `tools/acu_forge.py`.
- **Fallback chain (Delutto):** `Ubisoft_Forge_Tool` + `Ubisoft_DATA_Tool` + `aclocexport.exe`
  extract Unity loc; the DATA tool writes a `.NEW` to rename to `.data`. **Known friction:**
  "neither tool provides a way of putting .data files back INTO a .forge" and a documented
  "crashes while reading reimported DATA file" bug → test-grade, use only if AnvilToolkit fails.
  Do **not** conflate Delutto's re-injection friction with AnvilToolkit (a common mix-up in the
  prior research notes).
- **NOT viable for Unity v27 loc:** Turfster's forge extractor/replacer (old, not v27-loc-aware),
  QuickBMS Ubisoft-forge scripts (read-only; the `ac-valhalla` script is only for Valhalla's
  changed structure), Gibbed (different engine).

### Loc inner format — **char-INDEX serialization** (CONFIRMED), NOT UTF-16, NOT XML
There is **no plain string** anywhere in a LocalizationPackage: strings are reconstructed from a
per-package **sorted unique-char dictionary + per-string `u16` index arrays** (the AC2 v25 class:
`[u32 key_hash][u32 count][count × u16 index]` into the char table). ZenHAX/Delutto: *"Texts are
an index table for chars and/or char indexes, not XML, there's no a single one plain string on
localization resources."*
- **Hebrew consequence (critical):** you **cannot splice UTF-16 bytes**. You must **add the
  Hebrew codepoints `U+05D0–05EA` to the char/glyph dictionary and emit indices into it** — then
  the font must have those glyphs (§3). AnvilToolkit's XML export/import hides this (it round-trips
  the char-index for you), which is the single biggest reason to prefer AnvilToolkit over a
  hand-rolled encoder for v1.
- **Repack is size/offset/checksum-sensitive:** editing a package requires recomputing checksums
  and rewriting **DataSize (IndexTable / NameTable / DataTable) + Data Offsets (IndexTable)** at
  the `.forge` level, plus the per-compressed-block 4-byte hash. No in-place same-size shortcut
  unless the edited resource stays byte-length-identical (Hebrew rarely will). This is exactly
  what AnvilToolkit's Repack does for you; a home-rolled writer must reproduce it.

### Container index (CONFIRMED — matches what I cracked)
Header `"scimitar"`(8)+pad, `i32 version(27)` + `u64 file_data_header_offset`; at `offset+36`:
`i64 file_data_offset`; struct `i32 index_count(1620)` + pad + `q index_table_offset` +
`q file_data_offset2` + pad + `q name_table_offset` + `q raw_data_table_offset`. **Index record
= 20 bytes** (`u64 raw_data_offset, u64 file_id, u32 raw_data_size`). **Name record = 192 bytes**
(`u32 raw_data_size … u32 file_type … char[128] file_name` PLAINTEXT … timestamps). Invariant:
`index_table.raw_data_size == name_table.raw_data_size`; a repack must keep both in lockstep and
fix offsets.

---

## 2. Arabic-slot activation + bidi (LOGICAL vs VISUAL)

### Arabic TEXT locale is REAL and shipped (CONFIRMED)
Unity ships an **official Arabic text locale** (subtitles + docs, **text-only, no Arabic VO**),
added post-launch by Ubisoft's MENA distributor **"Red"** (SaudiGamer; a PS4 v2.00 patch + a
retail "AC Unity — Arabic Subtitles" SKU on noon.com/kanbkam). Matches my on-disk finding of
`TLocalizationPackage_Arabic` / `_Arabic_Subtitles` / `_Arabic_EManual` in `DataPC.forge`. So the
Arabic slot is genuine and dev-QA'd — **not** a WD2/GoWR-style "hijack a slot that has no shipped
Arabic". (My measured sizes: `Arabic_Subtitles` = 204,002 B real; `Arabic` (UI) = **139 B empty
stub** → Unity shipped **Arabic subtitles + English menus**, a common MENA config.)

### How the slot is selected (CONFIRMED — three levers)
1. **In-game Options → Sound/Subtitle → Arabic (العربية)** — voice and text set independently, so
   "Arabic text + English voice" is a supported in-game config (Steam app 289650 discussions;
   games300pc install guide).
2. **Root `localization.lang`** — a plaintext-editable **locale POINTER** (my 14-byte
   `"LANG" + u32 ver + 2×u32 hashes`). It is a *selector/region stamp*, **not** the text store.
   Getting it wrong triggers a **Uplay ownership/region re-check** (the "activation key" prompt on
   RU/CIS SKUs), **NOT a forge hash failure**. INFERRED: the two `u32` hashes reference/validate
   the selected locale's packages — leave them pointing at the Arabic set so the engine loads
   Hebrew-in-Arabic without a region mismatch (confirm at the byte level before relying on it).
3. **`HKCU\SOFTWARE\Ubisoft\Assassin's Creed Unity` → `Language` REG_SZ**.

The proven community deploy pattern is exactly the hijack: **swap the forge content + select that
slot in-game** (the 2025 English-loc guide replaces `DataPC.forge` + `DataPC_10_dlc.forge` then
picks that slot in settings).

### Bidi — **store Hebrew VISUAL (pre-reversed)** — CORRECTED, INFERRED, verify with a proof
> ⚠️ **This flips the earlier assumption.** An earlier note leaned "engine bidi's Arabic → store
> LOGICAL". The adjudicated verdict is **VISUAL**, and it is the safer default. Confidence:
> MODERATE — **build the proof, don't commit blind.**

- **Peer-reviewed evidence (Al-Batineh et al. 2024, John Benjamins; Al-Batineh 2021, T&I):** the
  AnvilNext-2.0-era AC titles **LACKED engine RTL/bidi support**; RTL (UI mirroring + right
  alignment + text orientation) was **added only in Valhalla (2020) and improved in Mirage
  (2023)** — a *later* Anvil generation. Odyssey (same family as Unity/Syndicate) is documented
  with "right-to-left alignment issues" precisely because RTL was absent. **AC Unity (2014) is
  even earlier**: its only Arabic surface is subtitles (no Arabic UI at all).
- **Practitioner corroboration (heshamlocalization.com):** engines lacking native support "perform
  no Arabic shaping and no bidirectional reordering, drawing glyphs in **raw byte order**"; the fix
  is an **offline RTL baker that shapes + reorders VISUALLY** — exactly this repo's `visual_line`
  pattern (AC2 / WD2-menu / GTA V / Anno).
- **Why Unity's shipped Arabic still looks right:** because Ubisoft's localizers **pre-baked the
  order into the DATA** (the normal way to ship a first-gen RTL locale on a non-bidi engine). The
  char-index format hides the raw order (no plain strings to eyeball), so this can't be read off
  disk — hence the proof.
- **Hebrew note:** Hebrew is strong-RTL and needs **no contextual joining/shaping** (unlike
  Arabic), so a `visual_line` pre-reversal (reverse Hebrew runs, keep Latin/digits/tokens forward,
  flip run order per line) is straightforward and matches AC2.
- **Decision rule (the proof):** store ONE line both ways. If **VISUAL renders correct and LOGICAL
  renders mirrored → VISUAL confirmed** (the expected result for this engine gen). AnvilToolkit's
  XML round-trip is **neutral** on order (it preserves whatever you store) → the *proof* decides,
  not the tool. Decide **per-surface** (subtitles vs UI) but expect both = VISUAL.

---

## 3. Font — Hebrew coverage + injection plan

> ⚠️ **CORRECTION vs the earlier recon.** Earlier notes said Unity UI = **Scaleform (GFx/FTX) +
> embedded TTF**. The research says AC Unity UI is **native AnvilNext 2.0** with a **per-script
> DDS bitmap glyph-atlas + `.ffd` (Fire_Font_Descriptor)** pipeline — **NOT Scaleform**. Treat the
> font path as the **AC2/SM2/WD2 DDS-atlas family**, not a `.gfx` swap. (This is INFERRED-high:
> no source names Unity's renderer literally "native", but the entire Anvil font toolchain is
> DDS-atlas+`.ffd` and there is zero Scaleform font artifact in it. **Confirm by dumping a Unity
> font resource** — a `.ffd`/`MapDesc` presence check settles it in minutes.)

### Facts (CONFIRMED)
- **Fonts are DDS bitmap atlases, NOT TTF** (AnvilToolkit wiki; ZenHAX: *"Fonts are DDS, not TTF"*).
- **Fonts live in the `extra` forge** (`DataPC_extra.forge` / for Unity a `DataPC_extra_*.forge`,
  e.g. `DataPC_extra_chr.forge`); **text lives in `DataPC.forge`** (LocalizationPackage). Edit =
  export the atlas TextureMap → DDS → edit → re-import.
- **Fonts are PER-SCRIPT atlases** — the resource name encodes the script, e.g. AC2
  `..._ProBold_Latin_1_MapDesc.data`. So **Latin, Arabic, CJK, etc. are separate atlases**; the
  Latin UI atlas does **not** contain Arabic/Hebrew.
- **The shipped default font does NOT cover Hebrew.** The AC Unity English-loc guide states
  directly that switching to Arabic "uses different font, so all symbols will be blank (same as
  Chinese)" — i.e. a script with no loaded atlas renders **blank**. Hebrew (`U+05D0–05EA`) has no
  shipped atlas → **blank unless injected**.
- **Injection technique = DDS atlas + `.ffd` descriptor, edited together.** `FFDConverter`
  (`eprilx/FFDConverter`) creates/edits AnvilNext bitmap fonts (`*.ffd`); its README: *"After
  replace `*.ffd`, you need to replace the image file in-game (e.g. `*.xbt`/DDS)."* The `.ffd`
  holds glyph metrics + codepoint→atlas mapping; the DDS holds the glyph bitmaps. **Both must be
  updated.**

### The one font caveat (CONFIRMED)
**FFDConverter does NOT list Unity/Syndicate (v27)** — its AC support stops at **AC Rogue**
(`FFDConverter` issue #2). The `.ffd` format may differ slightly at v27 → expect to **adapt/write
the `.ffd` reader** like our own AC2 work, using FFDConverter as the template.

### Plan (mirrors AC2/SM2/WD2/GoWR — this repo's proven font muscle)
1. **Locate + dump** the Unity font that renders the Arabic/subtitle slot from the `extra` forge
   (find by name: `*Font*MapDesc`, `FTX`/`FontManager`, `.ffd`). Confirm it is DDS-atlas+`.ffd`
   (kills the Scaleform ambiguity).
2. **Inject Hebrew** `U+05D0–05EA` into that atlas (draw glyphs from a Hebrew source font — Frank
   Ruehl/David, matching prior projects) **+** add the codepoint→glyph metrics to the `.ffd`.
   Redraw/append glyphs; **preserve the exact DDS PixelFormat the atlas already uses** (do NOT
   naïvely re-encode the DDS header — the WD2/GoWR lesson).
3. **Watch the classic traps:** off-by-one glyph-table indexing (GoWR/SM2 hit this — a stored
   record can encode the *next* codepoint's glyph), union-extent cell sizing (avoid clipping
   ascenders), baseline alignment via the signed y-offset. INFERRED-high (no Unity-specific
   citation, but the pattern is identical to prior injections).
4. **Prove one glyph** in-game before scaling (part of the single-Hebrew-string proof).

---

## 4. Deploy + anti-cheat + activation

### DRM & moddability (CONFIRMED)
- **DRM = Ubisoft Connect (Uplay) + VMProtect on `ACU.exe`; NO Denuvo** (Denuvo starts at Origins
  2017). VMProtect wraps the *code*, **not** the `.forge` asset archives.
- **Forge assets are NOT integrity-checked at load.** Mature modding scene: AnvilToolkit repacks;
  the runtime **Asset Overrides** loader (`NameTaken3125/AssetOverrides-ACUnity` via ACUFixes
  PluginLoader) swaps assets live, and its README states *"The game does not check for file
  errors … can freeze/crash even at startup if a `.data` is not a correct datapack"* — i.e. the
  loader parses your bytes with **zero content/hash validation**; a wrong datapack just **crashes**,
  it is not rejected as tampered. Whole texture/mesh mods load by forge replacement.

### Deploy mechanism (CONFIRMED)
Two paths:
- **(A) Whole-forge overwrite** (standard): back up `DataPC.forge` (+ `DataPC_10_dlc.forge` for
  DLC text / `DataPC_extra_*.forge` for the font), replace, select the slot in-game. This is what
  the 2025 English-loc mods do.
- **(B) Runtime override** via **ACUFixes PluginLoader + Asset Overrides** — no repack, the
  on-disk forge stays **vanilla**, the mod lives in a separate plugins folder. It hooks the
  datapack loader (ref-counted: an in-use object is overridden only once it stops being used).
  AnvilNext also uses numbered **patch forges** (`…_patch_01/02/03.forge`) that override the base
  (higher patch wins) — this override slot is CONFIRMED as the engine mechanism generally, and
  INFERRED-from-family for Unity (the community mostly overwrites the base or uses the runtime
  loader rather than authoring a new patch forge).

### ⚠️ The real deploy risk (CONFIRMED) — Ubisoft Connect integrity check
Newer **Ubisoft Connect builds run a strict file-integrity check on `DataPC.forge`**: a
modified/repacked forge can trigger an **"Activation Key" demand** and be blocked (region-
dependent, reported heavily on CIS/RU Steam builds; the strict check is a recent hardening).
- This is a **deploy** problem, **not** a repack-capability failure, and **not** the DRM hashing
  the code.
- **Mitigations to test (in the Stage-0 proof):** (a) the **runtime Asset-Overrides loader** — the
  cleanest, *verify-proof* path (on-disk forge stays vanilla → Connect sees no changed game file);
  (b) an offline/DRM-considered launch; (c) a build/region without the check; (d) if the Arabic
  subtitle slot is already selectable without swapping the forge, the `localization.lang` +
  in-game-select route. **Steam/Ubisoft "Verify Files" will always revert an overwritten forge**
  (re-downloads the diff) → keep the vanilla backup and re-apply, or use the runtime loader.

### Backup discipline (this repo's standard)
Back up every touched forge before writing → deploy to the neutral install (`E:\Games\…`), never
overwrite without a backup; `revert` = restore the backup forge (or, for the runtime loader, just
remove the plugin). VO packs `sounds_{eng,fre,…}.pck` (no Arabic) → text ↔ voice independent →
**English voice stays** with an Arabic-text hijack.

---

## 5. Verdict, #1 gate, next step

### 🟢 **GO-WITH-CAVEATS**
AC Unity is **feasible and the best-positioned AC in this repo.** Container read + LZO codec +
char-index loc class + real Arabic slot + no-Denuvo + a large modding scene are all **CONFIRMED**.
A free Unity-capable repacker (**AnvilToolkit**) exists and the community has shipped a
game-loadable modified Unity forge. The loc text is **STORED**, so translation READ needs no codec.

### #1 GATE
> **A v27 forge REPACK that the game loads AND that survives Ubisoft Connect's integrity check.**
> Repack *capability* is confirmed (AnvilToolkit); the *deploy-integrity* behavior (activation-key
> demand after a forge swap) is the concrete risk. The clean answer is likely the **runtime
> Asset-Overrides loader** (leaves the on-disk forge vanilla → verify-proof) rather than
> overwriting `DataPC.forge`.

### Residual caveats (rank-ordered)
1. **Deploy integrity** (Ubisoft Connect activation-key demand) — mitigate via the runtime loader.
2. **Bidi is INFERRED VISUAL** — must be proven with a one-line menu/subtitle test (do NOT assume
   LOGICAL).
3. **Font is DDS-atlas+`.ffd` (corrected from Scaleform), needs Hebrew injection, and FFDConverter
   stops at AC Rogue** → the v27 `.ffd` reader may need adapting.
4. **Char-index encode** is understood in class but unimplemented — AnvilToolkit's XML import
   bypasses it for v1; a launcher-bundled path needs our own encoder.
5. **AnvilToolkit is GUI-only, closed .NET** → fine for a one-off/manual mod, **not bundle-able**
   into the launcher (a launcher auto-install needs our own pure-Python forge/`.data` writer +
   `liblzo2`, reusing the ACExplorer read spec + the checksum/offset/DataSize fixups).

### ✅ Recommended NEXT empirical step (Stage 0 — one afternoon, no translation)
Run **two checks that together close the biggest unknowns**, in the neutral install with backups:
1. **Vanilla Arabic-slot render check** — set text = Arabic on the **untouched** game (in-game
   option / `localization.lang` / registry), observe: does shipped Arabic render **readable RTL**?
   (Confirms the Arabic slot is live on this SKU + gives the baseline for the bidi proof.)
2. **Identity repack round-trip** — unpack `DataPC.forge` → repack **UNCHANGED** (AnvilToolkit
   first; our writer later) → deploy (try BOTH: overwrite AND the runtime Asset-Overrides loader) →
   launch. Watch for: (a) boots identically, (b) **whether Ubisoft Connect demands an activation
   key**. This single test resolves the #1 gate.

**Only after both pass:** a single Hebrew test string (char-index encode + one injected glyph +
VISUAL vs LOGICAL) → proves the whole chain end-to-end → then scale to translation via the repo's
agent-handoff pattern (`universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`), then publish like
SM2/WD2/Anno.

---

## Source ledger (URLs)

**Codec / repack / container:**
- ACExplorer (v27 read spec + LZO switch): `https://github.com/gentlegiantJGC/ACExplorer` ·
  `.../blob/master/pyUbiForge/misc/decompress_.py` · `.../pyUbiForge/ACU/forge.py` ·
  `.../resources/010%20Editor%20Templates/ACUDecompressedRawData.bt`
- Blacksmith CHANGELOG (LZO 1X/1C/2A for Unity): `https://github.com/theawesomecoder61/Blacksmith/blob/master/CHANGELOG.md`
- AnvilToolkit (free repacker, Unity-supported): `https://www.nexusmods.com/assassinscreedunity/mods/38` ·
  `https://www.nexusmods.com/site/mods/455` · `https://github.com/Kamzik123/AnvilToolkit-Resources/wiki/Lesson-1`
- Delutto tool chain / friction: `http://www.zenhax.com/viewtopic.php@t=15369.html` ·
  `https://www.zenhax.com/viewtopic.php@t=9138.html` · `https://reshax.com/files/file/2678-ubisoft_forge_tool_by_delutto7z/`
- char-index loc format: `https://zenhax.com/viewtopic.php@t=7258.html`
- extract chain README: `https://github.com/MOIX-1192/assassin-s-creed-localization-texts`
- community game-loadable Unity loc mods: `https://steamcommunity.com/sharedfiles/filedetails/?id=3075396573` ·
  `https://steamcommunity.com/sharedfiles/filedetails/?id=3413126749`

**Arabic slot / bidi:**
- Al-Batineh et al. 2024 (AnvilNext lacked RTL; RTL added in Valhalla/Mirage; Unity Arabic = subtitles only):
  `https://www.jbe-platform.com/docserver/fulltext/dt.24013.alb.pdf`
- Al-Batineh 2021 (BiDi failure axis; 2014-era engines draw Arabic LTR/disconnected):
  `https://www.trans-int.org/index.php/transint/article/download/1380/388`
- Hesham (no engine bidi → offline visual baker): `https://heshamlocalization.com/`
- Official Arabic release: `https://www.saudigamer.com/assassins-creed-unity-will-officially-support-arabic-subtitles/` ·
  `https://www.noon.com/egypt-en/assassin-s-creed-unity-game-with-arabic-subtitles-...`
- Arabic activation (in-game / localization.lang / registry):
  `https://steamcommunity.com/app/289650/discussions/0/624075374615926273/` ·
  `https://games300pc.wordpress.com/2014/11/21/...` ·
  `https://www.ubisoft.com/en-us/help/.../000065269`

**Font:**
- AnvilToolkit wiki (DDS atlas, per-script, extra forge): `https://github.com/Kamzik123/AnvilToolkit-Resources/wiki/Lesson-1`
- ZenHAX ("Fonts are DDS, not TTF"): `https://zenhax.com/viewtopic.php@t=7258.html`
- Arabic "blank symbols / different font": `https://steamcommunity.com/sharedfiles/filedetails/?id=3075396573`
- FFDConverter (`.ffd`+DDS injection; stops at AC Rogue): `https://github.com/eprilx/FFDConverter` · `.../issues/2`

**Deploy / anti-cheat:**
- PCGamingWiki (Uplay+VMProtect, no Denuvo): `https://www.pcgamingwiki.com/wiki/Assassin%27s_Creed_Unity`
- Asset Overrides runtime loader (no integrity check): `https://github.com/NameTaken3125/AssetOverrides-ACUnity` ·
  `https://github.com/NameTaken3125/ACUFixes`
- Ubisoft Connect integrity / activation-key: `https://steamcommunity.com/sharedfiles/filedetails/?id=3075396573` (comments) ·
  `https://www.nexusmods.com/assassinscreedunity/mods/130`
- Steam Verify Files: `https://help.steampowered.com/en/faqs/view/0C48-FCBD-DA71-93EB`

## מסמכים קשורים
- באותה תיקייה: [[games/acunity/FEASIBILITY|FEASIBILITY]], [[games/acunity/PIPELINE|PIPELINE]], [[games/acunity/RECON|RECON]], [[games/acunity/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acunity|CLAUDE_INDEX_games]]
