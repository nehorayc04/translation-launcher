# GTA V Enhanced — PIPELINE

Run everything with the repo venv: `../../.venv/Scripts/python.exe`.

```
games/gtav_enhanced/
  tools/rpf_lazy.py     lazy read-only RPF7 walker (AES-aware, bit-63 aware)
  tools/rpf7.py         RPF7 writer — serialize_inplace + the resource-flag fix
  tools/gxt2.py         GXT2 codec + visual_line() (logical Hebrew -> VISUAL)
  work/extract_vanilla.py   OPEN mods\ -> extract/vanilla + extract/fonts + layout.json
  work/build_hebrew.py      extract/vanilla + EN->HE corpus -> build/ + coverage.json
  work/build_oiv.py         build/ + layout.json -> release/*.oiv
```

The translation corpus is **shared with Legacy** and read straight from
`games/gtav/agent_handoff_full/` (`reuse_he.json` + `hebrew*.json`, 141,001 EN→HE). There
is no second corpus to maintain.

---

## Step 0 — One-time bootstrap (the user does this once) 🔴

Enhanced ships every archive NG-encrypted and the keys are OpenIV-only, so the OPEN
`mods\` copies have to be created once. Nothing downstream can run before this.

1. Install **OpenIV**, plus **ZEnhanced** so OpenIV recognises an Enhanced install.
2. Install **OpenRPF.asi** (with its `dsound.dll`) into the game root — this is what makes
   the game load from `mods\` at all. It replaces Legacy's `OpenIV.asi` + `dinput8.dll`.
3. In OpenIV, use *Tools → ASI Manager / “copy to mods folder”* so that
   `E:\Games\Grand Theft Auto V Enhanced\mods\update\update.rpf`,
   `…\mods\update\update2.rpf` and `…\mods\update\x64\` exist as **OPEN** archives.

Verify — this must print `OPEN`, not `NG`:

```bash
../../.venv/Scripts/python.exe tools/rpf_lazy.py \
  "E:\Games\Grand Theft Auto V Enhanced\mods\update\update2.rpf" 5
```

## Step 1 — Extract Enhanced's vanilla text + fonts

```bash
../../.venv/Scripts/python.exe work/extract_vanilla.py
```

Discovers the language archives and Scaleform font libraries, writes
`extract/vanilla/**.gxt2`, `extract/fonts/*.gfx` and `extract/layout.json`.
Archives that are still encrypted are reported and skipped, never fatal.

Exit 2 means the bootstrap has not been done.

## Step 2 — Build the Hebrew layer

```bash
../../.venv/Scripts/python.exe work/build_hebrew.py
```

For every vanilla entry: if its English source has a translation → `visual_line(strip_gloss(...))`;
otherwise the English is kept verbatim. Each output is round-trip-asserted
(`read_gxt2(write_gxt2(x)) == x`) before it is written.

Read `build/coverage.json` afterwards:
- `pct` — overall Hebrew coverage
- `missing_english` — every untranslated English string with its occurrence count. On
  Enhanced this is the **Enhanced-only** corpus, i.e. the exact remaining work item.

## Step 3 — Package

```bash
../../.venv/Scripts/python.exe work/build_oiv.py
```

Writes `release/gtav_enhanced_hebrew.oiv` and `release/gtav_enhanced_restore.oiv`, with
the archive paths taken from `layout.json` — never hard-coded. Both use
`<archive type="RPF7"><replace>`, so other mods sharing those archives are untouched.

## Step 4 — Install + verify in-game

Install the `.oiv` with OpenIV (ZEnhanced active), launch, and check the pause menu / map
/ mission text.

**Hebrew is stored VISUAL (pre-reversed)** — GTA V's Scaleform UI runs no bidi. Correct
Hebrew therefore looks reversed in a hex/JSON dump and correct on screen; if it reads
correctly in the dump and reversed on screen, the `visual_line()` step was skipped.

## Deploy without OpenIV (later, optional)

Once `mods\` exists, `tools/rpf7.py` can do the RPF surgery directly, exactly like the
Legacy launcher applier: **`serialize_inplace`**, never a full re-pack.

> A full re-pack drops the original inter-file padding and makes the game fail Story Mode
> with `ERR_GEN_ZLIB_2`. In-place = append changed files at EOF, patch only their TOC
> entries. Always compare the output size to the original: a large shrink is the tell.

## Notes carried over from Legacy

- **Fonts** — GTA V's native text draws from the Scaleform font libraries. Hebrew-injected
  `font_lib_efigs.gfx` / `font_lib_efigs_pc.gfx` already exist under
  `games/gtav/_BACKUP_20260623/` and `games/gtav/_originals/`; whether Enhanced needs them
  is decided by `extract/fonts/` + the first in-game screenshot.
- **Bit 63 of a file entry is the RESOURCE flag**, and the data offset is only 23 bits.
  Reading it as a 24-bit offset corrupts every resource file. Both `rpf_lazy.py` and
  `rpf7.py` handle it.
- **`FileSize == 0` means stored raw**, with the real length in `FileUncompressedSize`.
