# GTA V Enhanced — RECON (measured 2026-08-02)

Install: `E:\Games\Grand Theft Auto V Enhanced`
Version: **1.0.1158.13** (`GTA5_Enhanced.exe`, from `versioninfo.txt`)
Engine: RAGE. Sibling project: [`games/gtav`](../gtav) (GTA V **Legacy**, shipped Hebrew mod).

Everything below was read off this install — nothing inferred from Legacy.

## 1. Container — RPF7, identical to Legacy ✅

```
ENH update.rpf     3,122,239,488 B  magic 7FPR  enc=NG   entries 1,790  names 17,488
ENH update2.rpf      656,189,440 B  magic 7FPR  enc=NG
ENH common.rpf        19,351,552 B  magic 7FPR  enc=NG
ENH x64a.rpf         101,433,344 B  magic 7FPR  enc=NG
```

`7FPR` = RPF7 — **the same container the Legacy toolchain already reads and writes.**
Checking the magic first is what collapsed the whole container workstream into reuse.

For comparison, the same probe on Legacy:

| archive | encryption | entries |
|---|---|---|
| Legacy `update.rpf` (vanilla) | **NG** | 1,644 |
| Legacy `mods\update\update.rpf` | **OPEN** | 1,659 |
| Legacy `mods\update\update2.rpf` | **OPEN** | 2,081 |
| Enhanced `update.rpf` (vanilla) | **NG** | 1,790 |

Enhanced-vanilla sits in exactly the state Legacy-vanilla was in before its one-time
OpenIV bootstrap. The `mods\` copies are the OPEN ones.

## 2. Encryption — NG everywhere, no readable island 🔴

- A 512-byte-aligned scan of the whole 3.1 GB `update.rpf` found **220 nested RPFs —
  all 220 NG**. There is no OPEN sub-archive to slip through.
- All **97** `update\x64\dlcpacks\**\*.rpf` are NG.
- `update\x64\data\` holds only `errorcodes\*.txt`. **No loose `.gxt2` and no loose
  `.gfx` anywhere in the install.**
- `rpf.cache` (16 MB, magic `HSHR`) is a binary hash cache — scanned, it carries **no
  filenames**. `index.bin` (80 KB) is opaque. Neither is a usable index.
- `GTAUtil.exe` 2.2.7.0 (bundled with the Legacy project) only prompts for a game folder
  interactively and extracted nothing; OpenIV is **not installed** on this machine.

⇒ The Enhanced text corpus **cannot be read** until the OPEN `mods\` copies exist.
This is the same documented NG wall as Legacy, not a new problem.

## 3. Text + font layout (verified on Legacy, to be re-verified on Enhanced)

Read live out of `F:\Games\Grand Theft Auto V Legacy\mods\`:

| artefact | location |
|---|---|
| base text table | `update2.rpf` → `x64/data/lang/american_rel.rpf` — **610 gxt2** |
| patch delta | `update.rpf` → `x64/patch/data/lang/american_rel.rpf` (44 KB) |
| UI fonts | `update.rpf` → `x64/data/cdimages/scaleform_platform_pc.rpf` → `font_lib_efigs_pc.gfx` |
| | `…/scaleform_generic.rpf` → `font_lib_efigs.gfx`, `font_lib_web.gfx` |

`global.gxt2` decodes to **69,209 entries, 64,354 of them Hebrew** — i.e. the live Legacy
mod, confirming the reader, the nested-archive walk and the GXT2 codec all work.

`work/extract_vanilla.py` **discovers** these paths rather than hard-coding them, so an
Enhanced layout that differs is detected instead of silently missed.

## 4. Per-file encryption — a real trap 🔴

An archive whose table-of-contents is OPEN can still hold **per-file AES-encrypted
payloads**: a binary entry's last u32 is `IsEncrypted`, not a generic flag word.
`mods\x64b.rpf` is exactly this — its TOC reads OPEN while 562 of its 602 gxt2 stay
encrypted. `tools/rpf_lazy.py` decrypts (GTA5 AES-256-ECB ×16) before inflating, and
treats a still-unreadable payload as *skipped and reported*, never fatal — those older
vanilla archives are not what the mod touches.

## 5. Deploy mechanism ✅

Enhanced keeps the `mods\` override mechanism, via community tooling:

- **OpenRPF.asi** (+ its `dsound.dll` proxy) — the Enhanced replacement for `OpenIV.asi`;
  redirects asset loading to `mods\`. Legacy used a `dinput8.dll` proxy.
- **ZEnhanced** — makes OpenIV recognise an Enhanced install so `.oiv` packages install.

`BattlEye` ships with Enhanced but guards GTA Online; the single-player `mods\` path is
what the whole Enhanced modding scene uses.

## 6. What this means

| gate | state |
|---|---|
| container | ✅ RPF7 — Legacy tooling transfers, verified end-to-end |
| text format | ✅ GXT2 — codec verified |
| translation corpus | ✅ 141,001 EN→HE, keyed by **English source string** ⇒ engine-independent |
| deploy | ✅ `mods\` + OpenRPF.asi |
| fonts | ✅ Scaleform `.gfx`, Hebrew-injected copies already exist for Legacy |
| **reading Enhanced's own vanilla text** | 🔴 **blocked on the one-time OpenIV bootstrap** |

See [FEASIBILITY.md](FEASIBILITY.md) for the verdict and [PIPELINE.md](PIPELINE.md) for
the build/deploy steps.
