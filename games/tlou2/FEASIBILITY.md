# FEASIBILITY — The Last of Us Part II Remastered (Hebrew)

## Verdict: 🟢 GO — medium tier (deploy EASIER than Part I). ALL OFFLINE GATES CLOSED; one in-game menu-proof pending user.

TLOU2R is the **same Naughty Dog engine + same class as [TLOU Part I](../tlou1/)** — no Arabic
locale → LTR-slot hijack + VISUAL bake + font replace. The Part I toolkit ported with near-zero
change; the one genuinely new piece (the **DSAR** outer container) was cracked and validated
end-to-end, and deploy is **simpler** than Part I (a small override psarc via the built-in mod
loader — no 2.8 GB `core.psarc` repack). Confidence is very high because Part I (identical engine,
identical `seriffont`/DINPro font, identical loc format) **already passed its in-game proof**
(VISUAL + font-works + repack-loads). See [[tlou1-groundwork-go]].

---

## Gate-by-gate (playbook order)

### 0. Format map — ✅ CRACKED + VALIDATED
- Container: **DSAR** (LZ4-block, 256 KB chunks) → **inner PSARC v1.4** (zlib, 64 KB blocks) → `.pak`.
  Pure-Python reader `tools/dsar.py` (interface mirrors Part I's `psarc.py`). Validated: reconstructed
  `bin.psarc`'s inner PSARC (8005 files) + parsed `common.psarc` (2461 files) + `core.psarc` (13,967 files).
- DSAR entry (32 B, LE): `s64 decompOffset · s64 compOffset · s32 uncompSize · s32 compSize · u8 compType(0=stored,else LZ4) · 7 reserved`. Header: magic/ver + `u32 numEntries@0x08` + `u32 dataStart@0x0C` + `u64 totalUncompSize@0x10`, entries at 0x20. (Cross-checked against UnPSARC's `Decompressor.cs`.)
- **UI text vs subtitles vs fonts all live in `core.psarc`.** English source: `text2/eng.common`,
  `text2/eng.subtitles`, `text2/eng.subtitles-systemic`, shared `text2/sid-lookup`. Fonts in `fonts/`.

### 1. Arabic slot — ❌ NONE → LTR-slot hijack (AC2/Anno/Part-I class)
26 languages, **all LTR/CJK, zero RTL** (bra chi chs cze dan dut eng fin fre ger gre hrv hun ita jpn
kor nor pol por rus sas spa swe th tur uke). No `ara`/Hebrew. → **hijack the English slot**
(`text2/eng.*`) — simplest activation (user sets Text = English). `sas` = LATAM-Spanish (not Arabic).

### 2. Arabic skeleton — N/A (no Arabic). Source of truth = `text2/eng.*`
Not a skeleton fill; we OVERRIDE the English slot's values in place, keyed by **SID** (same SID
across every language → future gender oracle joins on it, see §Gender).

### 3. bidi mode — 🟡 VISUAL expected (store pre-reversed), decided by the menu-proof
Same ND engine as Part I → no bidi/no shaping (never shipped an RTL locale) → **store VISUAL**.
`work/tlou_rtl.py` `to_visual` (Part I's, self-test 9/9): reverses Hebrew runs, keeps Latin/digit/token
islands forward, mirrors brackets, keeps markup pairs LOGICAL, splits on `\n`. Part I **confirmed
VISUAL in-game** — TLOU2R is the same engine, so VISUAL is the strong default. The proof's LOGICAL vs
VISUAL menu items settle it definitively.

### 4. Font — ✅ REPLACE with Heebo (built)
`seriffont-Regular.otf`/`-Medium.otf` are literally **DINPro** (CFF/PostScript, 751 glyphs, **no Hebrew,
no Arabic**) — identical to Part I. CFF ⇒ glyf-injection is a no-op ⇒ **REPLACE** with a Latin+Hebrew
face. Built `extract/_he_seriffont-*.otf` from **Heebo** (Latin 58/58 + Hebrew 27/27), masquerading as
the DINPro `name` table (`work/tlou_font.py`). Part I proved the replace renders in-game (no tofu).
Fonts are all loose OTF/TTF — the easy class.

### 5. Repack (identity round-trip) — ✅ PROVEN offline (mod = DSAR, the game's native format)
`tools/psarc_write.py` builds the inner **plain PSARC v1.4 (zlib)**; `tools/dsar_write.py` wraps it in the
game's native **DSAR (DirectStorage/LZ4)** container. Both self-test + real round-trip: a 540 KB DSAR
override with patched `eng.common` + Heebo fonts **reads back byte-identical** through `tools/dsar.py`.
Loc codec `tools/tlou_loc.py` (Part I's, unchanged) decodes all three `eng.*` with **roundtrip=True**.
**⚠️ Ship DSAR, NOT plain PSARC:** two research passes conflicted — one (UnPSARC source) said plain zlib
PSARC loads; the other (the TLOU2R scene, ndarc default = DirectStorage) said mods must be DSAR/LZ4 and
plain PSAR/zlib is "not a confirmed runtime path." DSAR matches the shipping archives + ndarc's default →
the safe choice; the plain-PSARC path stays as a fallback the in-game proof can also test.

### 6. Menu proof — 🟡 BUILT, awaiting user in-game confirm
`work/build_menu_proof.py` (`--deploy`/`--revert`) patches 6 main-menu SIDs (CONTINUE→Latin marker
`ZZ-TLOU2-OK-ZZ`; NEW GAME/options→LOGICAL; LOAD GAME/Settings/Extras→VISUAL) + swaps DINPro→Heebo,
into a 539 KB override psarc dropped in `mods\`. Closes bidi + font + mount-loads in one screenshot.

### 7. Scope (measured, unique) — ~43,800 strings
| file | records | unique | role |
|---|---:|---:|---|
| `text2/eng.common` | 17,095 | **12,781** | UI / menus / accessibility / system |
| `text2/eng.subtitles` | 36,189 | **21,266** | story dialogue |
| `text2/eng.subtitles-systemic` | 104,311 | **9,739** | barks / systemic (heavily deduped) |
| **total unique translatable** | | **~43,786** | |
Tokens to preserve verbatim (Part I grammar): markup `<font …>…</font>`/`<br>`/`<break/>`/`<hang>`;
island `|gen:interact|`/`|menu:select|`/`[A]`/`[TEXT]`/`%d`/`{value}`; literal `\n`.

---

## Deploy + activation
- **Deploy = a single small DSAR archive in `<game>\mods\`**, auto-mounted by **ndmodloader** above `core.psarc`
  (empty `MountOrder` auto-loads all `.psarc` in `ModFolder` → overrides `text2/eng.*` + `fonts/seriffont-*`
  WITHOUT touching `core.psarc`). Non-destructive, reversible (delete the file). Community text mods
  (Better Arabic Localisation #279 hijacks the subtitle slots, Indonesian #49) prove this exact path.
- **⚠️ THE current blocker — ndmodloader is NOT installed in this copy.** Only `modloader.ini` is present:
  no `winmm.dll` (the Ultimate-ASI-Loader proxy) and no `modloader.asi` (the closed-source loader). Without
  them nothing mounts `mods\` → the game stays vanilla English (this is exactly what "עדיין אנגלית" was —
  NOT a problem with our files). The user installs ndmodloader once (743 KB, Nexus TLOU2 mod #32 or the
  VGTimes mirror — `modloader.asi` has no clean HTTP source, it's Nexus/Telegram-gated). **I already fixed
  `modloader.ini`** (`ModFolder`→`F:\…\mods`, `ShowConsole=true`; backup `modloader.ini.bak-claude`) and
  verified there's no pre-existing `winmm.dll` for the RUNE crack to conflict with.
- **Version gotcha:** ndml must match the game build (`EnableSafetyChecks` rejects outdated mods — mainly the
  `characters.bin` auto-merge path; a text-only mod is lower-risk but grab the ndml build for this game version).
- **Plan B (loader-independent) if ndml can't be installed:** a direct `core.psarc` DSAR repack (like Part I) —
  `dsar_write` + a surgical inner rebuild that stream-copies the ~14k unchanged entries and re-zlib's only ours.
  Heavier (2.8 GB rewrite) + a boot risk (recoverable via `core.psarc.he_backup`), but needs no third-party loader.
- **Activation:** in-game Options → Language → Text + Subtitles = **English** (the hijacked slot),
  Speech = English (audio is independent).
- **DRM:** single-player, **no Denuvo / no EAC** (Sony shipped it DRM-free; RUNE-cracked here). No
  anti-tamper blocks a mounted mod archive.

## Gender strategy (Phase-2, per universal/GENDER_ORACLE_ROLLOUT.md — no gender debt)
No Arabic oracle here. Derive gender from the game's OWN gendered localizations, joined on **SID**
(shared across languages, read via the same `dsar`+`tlou_loc`): **`text2/rus.subtitles`** = addressee/
speaker (past-tense -л/-ла, unambiguous) + **`text2/spa`/`fre`.subtitles** = referent/adjective (-o/-a,
-é/-ée). In the Phase-2 agent handoff, attach the Russian/Spanish line beside the English per SID so the
translator genders correctly from line 1; run `gender_oracle scan` as the closing QA. English = meaning
only, never the gender source.

## Reused from Part I (near-zero change)
`tlou_loc.py` (unchanged — same ND loc-v2), `tlou_rtl.py` (unchanged — VISUAL), `tlou_font.py`
(unchanged — Heebo replace), Heebo fonts. **New for Part II:** `tools/dsar.py` (DSAR outer layer),
`tools/psarc_write.py` (plain-zlib override builder — simpler than Part I's surgical repack).

## Open gates / risks
1. **In-game menu-proof** (the only real gate) — user installs ndmodloader + deploys + confirms VISUAL
   + font + mount. Very high confidence (Part I passed on the same engine/font/format).
2. `text2/eng.subtitles` `secondaryKey`/context: subtitles may key story-line context — verify during
   the Phase-2 corpus build (Part I did this).
3. External-tool independence: the launcher applier can bundle the pure-Python `dsar.py`+`psarc_write.py`
   (no dependency on the closed-source ndarc binary); ndmodloader itself is the only third-party runtime
   piece the END USER installs.

## מסמכים קשורים
- באותה תיקייה: [[games/tlou2/PIPELINE|PIPELINE]], [[games/tlou2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#tlou2|CLAUDE_INDEX_games]]
