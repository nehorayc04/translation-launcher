# Ghost of Tsushima DC (PC / Nixxes) — DEPLOY mechanism (Phase 1)

Verdict: **LIGHT OVERRIDE PATH EXISTS — no 1.4 GB `gapack_misc_l` rebuild required.**
Ship a small custom `.psarc` containing only the modded `/lang_arabic_text.xpps`, drop it into
`cache_pc/psarc/` with an alphabetically-later name; the engine's own folder scan loads it and
overrides the packed copy. No mod loader, no proxy DLL, no anti-cheat obstacle.

## How the modified xpps reaches the game
The GoT engine, at boot, **scans `<game>/cache_pc/psarc/` and mounts every `*.psarc` in
ALPHABETICAL order**; a file present in a later-loaded archive **overrides** the same internal
path from an earlier one. Confirmed by the modding scene:
- ResHax #746: *"the game loads modified originals and custom psarcs in alphabet order just fine."*
- Nexus MO2 plugin #329 + community: mods are packaged as `.psarc` and placed in `cache_pc/psarc`;
  *"files are loaded in alphabetical order, making it possible to create a 'load order'"*, and
  *"the game seems to load any custom psarc you put in, replacing data on the fly."*
- **Hard cap: max ~16 mod psarcs** in the folder (community-reported). We need exactly 1.

So the deploy = build `zzz_hebrew.psarc` (or `gapack_misc_zz_hebrew.psarc` — any name sorting
AFTER `gapack_misc_l.psarc`) holding a single entry `/lang_arabic_text.xpps` (Hebrew), copy it
into `cache_pc/psarc/`. Revert = delete that one file. The original 55 archives are never touched.

### Override KEY (critical)
The internal path inside `gapack_misc_l.psarc` is **`/lang_arabic_text.xpps` (LEADING SLASH)** —
verified via `dsar.py` TOC read (494 entries; siblings `/lang_italian_text.xpps`, etc.). The mod
psarc MUST store the file at exactly `/lang_arabic_text.xpps` so its `md5(path)` TOC hash matches
and the engine's lookup resolves to our copy. (PSARC resolves files by md5 of the manifest path.)

## needs_repack
**FALSE.** No need to rebuild `gapack_misc_l` (1.43 GB). A separate small override psarc is the
proven path. (Editing the original in place also works — "modified originals … load fine" — but
that means rewriting 1.4 GB; the additive override is far lighter and trivially reversible.)

## loose_override
Loose files (an extracted `cache_pc/psarc/lang_arabic_text.xpps` sitting NOT inside a psarc) are
**NOT a confirmed path** — every documented GoT mod ships as a `.psarc` in `cache_pc/psarc`, and
the sibling ND projects showed loose-file override is unreliable (tlou1 loose = did NOT work).
Do not rely on loose; use the override psarc.

## mod_loader / tools (community)
- **No dedicated runtime mod loader and no proxy DLL** (checked game root: no dinput8/winmm/
  version/xinput/dxgi/bink proxy). The engine's native `cache_pc/psarc` scan IS the loader.
- **Mod Organizer 2 plugin** (Nexus #329) — virtualizes mods into `cache_pc/psarc` (organizational
  only; not required — a manual file copy is equivalent).
- **UnPSARC** (rm-NoobInCoding, v2.3+) — community unpack/**pack** for GoT DSAR/PSARC.
- **GoTExtractor** (Nexus #65), DKDave python decompressor, QuickBMS (<2 GB only).

## repack_tools — can tlou2 dsar_write.py + psarc_write.py rebuild a GoT gapack?
**YES — validated end-to-end against the REAL file.** Round-tripped the real 17,064,240 B
`lang_arabic_text.xpps` through `psarc_write.build({"/lang_arabic_text.xpps": blob},
compress=False)` → `dsar_write.wrap(...)` → read back via `dsar.py` (the SAME reader that reads
GoT's shipping gapacks) → **byte-identical, md5 match**. GoT uses the same DSAR→inner-PSARC-v1.4
(md5-path TOC, NUL manifest) container the tlou2 tools target.

Gotchas:
- Internal path must be **`/lang_arabic_text.xpps`** with the leading slash (see above).
- Inner PSARC blocks: use `compress=False` (STORED) to mirror how the shipping gapack holds files
  (the DSAR/LZ4 outer does the compression). A zlib inner block can be misread — same lesson as
  tlou2. `dsar_write.wrap` LZ4-compresses the outer blocks (matches shipping `flags` low-byte 0x03).
- DSAR vs plain PSAR: the game natively reads BOTH (gapacks = DSAR, `music_*.psarc` = plain PSAR),
  so either format loads. **Recommend DSAR** to match the gapack it overrides. If a plain-PSAR mod
  is ever preferred, `psarc_write.build(..., compress=True)` alone (no DSAR wrap) is also a
  candidate — but DSAR is the format-matching, safest choice and is proven to round-trip here.
- `.xpps` (KCAP) internal format is a separate Phase-1 codec problem — NOT a deploy concern; deploy
  only moves whatever bytes we produce.

## anti-cheat / DRM
- **Copy = RUNE crack**: `steam_api64.rne` + `steam_emu.ini` (Goldberg-style Steam emu, AppId
  2215430) + `NoDVD/RUNE`. Saves at `Users\Public\Documents\Steam\RUNE\2215430`.
- **NO Denuvo** (Nixxes/Sony PC ports of GoT ship Denuvo-free), **no EAC/BattlEye** (single-player).
- **No asset-integrity gate**: PSARC has no whole-archive checksum; entries are keyed by md5(path)
  + a block table → content edits load. The entire GoT Nexus mod scene (texture/mesh/audio) proves
  asset psarc mods load with zero enforcement. The RUNE crack only replaces Steam DRM.
- Deploy is safe: additive override psarc, single-player, reversible by deleting one file.

## Activation (how the user shows the hijacked Arabic slot)
In-game **Settings → Options → General → Text Language (שפת טקסט) = Arabic / العربية** (subtitle +
UI text language). Voice can stay English or Japanese (audio language is independent). The Hebrew,
shipped inside the Arabic slot, then renders through the engine's tested RTL pipeline.

## Concrete deploy recipe (Phase 2)
1. Build modded Hebrew `lang_arabic_text.xpps` (KCAP codec — separate task).
2. `inner = psarc_write.build({"/lang_arabic_text.xpps": HEBREW_BYTES}, compress=False)`
3. `mod = dsar_write.wrap(inner)`  → write `cache_pc/psarc/zzz_hebrew.psarc`
4. (Optional applier) back up nothing (original untouched); revert = delete `zzz_hebrew.psarc`.
5. Activate: in-game Text Language = Arabic.
