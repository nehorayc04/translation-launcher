# RDR2 — RECON (read-only facts)

## Install (Steam)
`C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2`
- Root RPF8 archives: `common_0.rpf`, `data_0.rpf`, `anim_0.rpf`, `levels_0..7.rpf`,
  `textures_0/1.rpf`, `movies_0.rpf`, `packs_0/1.rpf`, `shaders_x64.rpf`,
  `update_1..4.rpf`, `appdata0_update.rpf`; `x64/audio/**`, `x64/dlcpacks/**`.
- `oo2core_5_win64.dll` (Oodle), `bink2w64.dll`, `RDR2.exe`, `PlayRDR2.exe`.

## RPF8 (container) — confirmed by magic
Magic bytes `38 46 50 52` = **"8FPR"** (RPF v8, little-endian `0x52504638`). NOT RPF7 —
GTA V's `rpf7_reader.py` (magic `0x52504637`, `[u32 magic][u32 entryCount][u32 nameLen][u32
encType]` TOC) does **not** parse it. RPF8 TOC is encrypted (AES) + entries are Oodle-packed;
entries in newer RPF8 have **hashes, not names** (OpenIV note). Reference reader that DOES
handle RPF0–RPF8: `VIRUXE/rpf-rs` (Rust). We do not need RPF8 for deploy (see FEASIBILITY).

## Text (localization)
- Base game text = **`.yldb`** databases inside `update_3.rpf` → `x64/data/lang/`.
- Export: OpenIV → "Save raw content" → `.full` files → **ModActivator** → `.txt`.
- Keyed by **label** (e.g. `LEGAL_SPLASH_1`, `RCTXD_UC_PLC`) or **joaat id** (`0x2B39B2B7`).
- Public label DB: `github.com/OpenIV-Team/RAGE-StringsDatabase` (GTA IV/V + RDR2 known labels).

## Override mechanism (the deploy path — no RPF write)
- **Lenny's Mod Loader (LML)** loads loose mods from `<RDR2>\lml\`. Prereqs: RDR2 **ASI
  Loader** + **ScriptHookRDR2** (+ `dinput8`-style loader). Story mode only, no anti-cheat.
- `lml/mods.xml` registers mods + load order. Each mod dir has `install.xml` (EasyInstall) with:
  - `<DataFile>Name.gxt2</DataFile>` — a plain-text `KEY = value` string override (runtime).
  - `<FileReplacement><GamePath>…</GamePath><FilePath>…</FilePath></FileReplacement>` — loose
    asset (e.g. the font).
- **String Translator** (Nexus #364) = an alternative ASI+XML runtime override (`id`/`label`).

## Font
- Menu/subtitle font = Scaleform **`font_lib_efigs.gfx`** (GFX v8, uncompressed), game path
  `update:/x64/patch/data/cdimages/scaleform_frontend/font_lib_efigs.gfx`. Replaced loose via
  LML `asset_replace` (same slot the Arabic mod replaces).
- **18 DefineCompactedFont faces**: RDR Chalk Hand / Turri / Catalogue Bold / Catalogue Numbers
  / Gothica / RockstarTAG / Arial / Droid Serif Pro / Rockstar Gamertag Cond / RDR Lino Numbers
  / Hapna Slab Serif DemiBold / 1871 Dreamer Script / Cabrito Norm Demi / RDR Ledger Hand /
  HelveticaNeue LT 47 LightCn / RDR Lino / Redemption / Arial DEBUG. Each ~58 Latin. Vanilla = 0
  Hebrew (the Arabic mod injected ~608 Arabic per face). Injection is the GTA V FFdec technique.

## Reference — Ko Games Arabic mod (open source, dissected)
`github.com/Lore2x/RDR2-Arabic-Translation` release `lml` (`lml.zip`, 8 MB):
```
lml/mods.xml · lml/patterns.dat
lml/KGF/install.xml + KGF/asset_replace/font_lib_efigs.gfx   (Arabic-injected Scaleform, 3.28 MB)
lml/tranar/install.xml + tranar/"Ko Games Studio.gxt2"       (25 MB plain-text KEY=value, VISUAL)
```
Analysis: 231,993 unique keys; storage VISUAL (85:1 presentation-form; 17,854 lines start with
`.` on the left). This one mod proves text-override + font-inject + RTL all work in-game.

## Reference copy (this session, scratchpad — not committed)
`…/scratchpad/rdr2_ref/` : the extracted `lml/` (Arabic), `rdr2_font.xml` (decompiled),
`rdr2_font_he.xml` (Hebrew-injected), `font_lib_efigs_HE.gfx` (recompiled Hebrew font).
FFdec 26.2.1 at `…/scratchpad/ffdec/ffdec.jar` (Java = Adoptium JDK 25, on PATH).

## מסמכים קשורים
- באותה תיקייה: [[games/rdr2/FEASIBILITY|FEASIBILITY]], [[games/rdr2/INSTALL|INSTALL]], [[games/rdr2/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#rdr2|CLAUDE_INDEX_games]]
