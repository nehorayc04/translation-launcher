# AC Unity — where do the rendered glyphs come from? (font research, 2026-07-27)

## VERDICT: **LIKELY** (solvable; needs one cheap step to become SOLVED — no exe unpack required)

Prior art proves the AC Unity font can be extended to a script the game does **not** ship
(Thai), via forge edits alone — so the VMProtect-packed exe is **not** the blocker. What is
missing is the exact runtime font wiring, which the prior-art mod hands over directly. The
earlier "inject the 7 TTFs" approach was structurally correct but failed because **AC Unity
does not do its render-time glyph lookup through the TTF `cmap`** — the reconciliation below.

---

## 1. The reconciliation — why injecting the 7 TTFs rendered boxes

Established this session (all read-only, pristine install untouched):

- **rec109 `TGame Bootstrap Settings` (DataPC.forge, class 3853006176) is the ONLY font-bearing
  resource in the ENTIRE game.** Verified: class-hash histogram of DataPC.forge (1475 TextureMap /
  66 LocalizationPackage / 0 font-atlas class), a decompressed-content scan of DataPC.forge, and a
  scan of `DataPC_extra.forge` (3501 recs) — **no `FireFontDescriptor`, no `TextureMap` glyph
  atlas, no second FontManager, no font data anywhere else.** There is no `DataPC_patch.forge`
  (only per-map LGS patch forges). So the earlier injection targeted the right (and only) resource.
- rec109 decompresses to **113 MB**. It holds a `FontManager_0X1A36B0959` object + **7 `Font`
  objects**, each `[u32 0x70a6a7ec ("Font")][u32 storedSize][raw sfnt TTF]` (storedSize == exact
  TTF length, verified on all 7). The other ~96 MB is a bootstrap entity/reference graph + a large
  BMP codepoint table (below) — **NOT glyph atlases** (no atlas class objects; short zero-runs =
  high-entropy, not a mostly-empty atlas; the "1024×1024 dim pairs" were 4-byte-alignment noise).
- The 7 fonts + their **only** script coverage (pristine cmaps):

  | font | glyphs | Latin | Cyrillic | **Arabic** | Hebrew | CJK |
  |---|--:|--:|--:|--:|--:|--:|
  | News Gothic ×3 | 748 | 58 | 64 | 0 | 0 | 0 |
  | DFHeiMedium-B5 | 15737 | 58 | 64 | 0 | 0 | ✓(Chinese) |
  | AbstergoSansJP | 8055 | 58 | 64 | 0 | 0 | ✓(Japanese) |
  | AbstergoSansKO | 3908 | 58 | 64 | 0 | 0 | ✓(Korean) |
  | **Shilia 330 Light** | 1101 | 58 | 64 | **122 (+140 pres-forms)** | 0 | 0 |

  ⇒ **Shilia is THE Arabic-subtitle font — the Hebrew target.** All 7 are Hebrew-0 in pristine.

- The repo's injection (`work/build_diag_allfonts.py`) was **structurally sound**: it subsets each
  font to Latin+punct, merges U+05D0–05EA, keeps it ≤ the `storedSize` slot (delta-0, storedSize
  preserved, zero-padded), and the rebuilt forge re-reads 27/27 Hebrew. So the FORGE WRITE is fine.

**Therefore the failure is in the RUNTIME FONT PATH, not the forge.** AC Unity renders text
through a glyph/codepoint routing structure (see §2), **not** a live `cmap` lookup of the TTF.
Adding a glyph to the TTF `cmap` is necessary but **not sufficient**: Hebrew is never wired into
the engine's glyph-set/routing, so its codepoints fall to `.notdef` → boxes, exactly as observed.
(The re-read verified the injected bytes are in the forge; it never proved the engine *uses* them
for a Hebrew codepoint.)

### The architectural key (why FFDConverter has no AC Unity profile)
- Older AC (AC2, Brotherhood, Rev, AC3, AC4, Rogue) and Watch Dogs ship a **FireFont `.ffd`
  descriptor + a baked bitmap atlas and NO source TTF** — that is FFDConverter's domain.
- **AC Unity (AnvilNext 2.0, 2014) ships full source TTFs** (incl. an 8.9 MB Chinese TTF with
  15,737 glyphs) inside a FontManager. A baked-atlas engine would never ship the source TTF.
  ⇒ AC Unity switched to an **embedded-TTF + runtime glyph-set** model, which is why FFDConverter
  (which stops at AC Rogue / WD Legion) has **no Unity/Syndicate profile**.
- rec109's tail (~0x626d8ac) holds a **large, near-dense u16 codepoint table** enumerating the BMP
  — Latin, Arabic, and **Hebrew 0x5D0–0x5EA are all present** in it (so it is *not* a charset that
  excludes Hebrew; the gate is more likely a codepoint→font/glyph-set routing the engine builds
  from this + per-font data). Pinning its exact semantics is reverse-engineering that the prior-art
  diff (§4) shortcuts.

---

## 2. Prior art — non-shipped scripts DO render on this engine (decisive)

AC Unity ships Latin / Cyrillic / CJK / Korean / **Arabic**. A script it does **not** ship, made
to render by a community mod, is the decisive proof — and it exists:

- **Thai AC Unity translation** — renders Thai (a non-shipped script) in-game. Installer at
  `thai-mod-game.net`; news writeup: https://www.sanook.com/game/1122241/ . By FB page
  "แปลเกมภาษาไทย V.1". **Known limitation: the game's font SIZE "cannot be fixed"** — i.e. glyphs
  were successfully ADDED and render, but at a wrong size/metrics. That "added-but-wrong-size"
  symptom is the classic TTF/atlas-injection metrics problem seen on this repo's other games, and
  it confirms the barrier is engineering, not impossibility.
- **Thai AC Syndicate localization** (same AnvilNext 2.0 engine):
  https://www.nexusmods.com/assassinscreedsyndicate/mods/65
- **Thai AC Odyssey font** (newer AnvilNext): https://www.nexusmods.com/assassinscreedodyssey/mods/223
- **FFDConverter** (the AnvilNext/Dunia/Disrupt `.ffd` font tool this repo already uses for WD2):
  https://github.com/eprilx/FFDConverter — supports AC2/Brotherhood/Rev/AC3/AC4/Rogue + WD1/2/Legion
  + FarCry, but **NOT AC Unity/Syndicate** (confirming the engine-generation split above). Support
  requests: https://github.com/eprilx/FFDConverter/issues/2
- Russian localizer note (playground.ru / gameguru.ru): *"different language localizations use
  different fonts, so some symbols may appear blank for certain languages like Chinese or Arabic"* —
  confirms per-language font selection + blank-on-missing-glyph behavior.

**All of these are FORGE patches (installer / `.forge` replacement) — none unpacks the exe.** So a
Hebrew solution does NOT require touching the VMProtect binary.

---

## 3. Ranked hypotheses (with evidence)

**H1 — Runtime glyph-set / codepoint→font routing gates rendering (HIGH).**
AC Unity rasterizes/selects glyphs via a routing structure (the big BMP codepoint table in rec109 +
per-font glyph data), not a live TTF `cmap` lookup. Hebrew is not wired into it, so its codepoints
→ `.notdef` even with the glyph in the TTF. *Evidence:* injection was structurally valid yet boxes;
full TTFs are shipped (rasterization/routing, not a static atlas); a dense codepoint table exists;
this matches the repo's own **Anno 1800 "cold-boot atlas breadth"** pattern (glyph in the font, not
in the engine's glyph-set → not drawn). *Fix:* wire Hebrew into that structure **and** the font
(Shilia for subtitles) — which is exactly what the Thai mod must do.

**H2 — The subsetting altered the cmap subtable/structure the engine reads (MEDIUM).**
The engine may read a specific cmap platform/encoding subtable (or a format) that fontTools
subsetting changed/normalized, so the engine's chosen lookup never sees the injected Hebrew even
though `getBestCmap()` shows it. *Fix:* minimal injection preserving the original cmap subtable
layout, mirroring the Thai mod's method.

**H3 — A baked atlas in a form not yet located (LOW).**
*Evidence against:* no `FireFontDescriptor`/`TextureMap` glyph-atlas class objects in any forge; the
non-font region is high-entropy (not a mostly-empty atlas); full TTFs are shipped (an atlas engine
ships no TTF). Not excludable only because a runtime-generated atlas cache could exist, but it is
the weakest.

**H4 — It's inside the VMProtect exe (RULED OUT as the blocker).**
The Thai/Syndicate/Odyssey mods all render non-shipped scripts via forge patches without unpacking
the exe. Whatever the wiring, it is reachable from the forge. (No import of DirectWrite/FreeType/
HarfBuzz/Uniscribe/ICU in ACU.exe or any of the 8 DLLs; ACU.exe is fully VMProtect-packed so its
own string/import scans are false-negative machines — but that only means "don't conclude from the
exe," not "the answer is in the exe.")

---

## 4. THE single cheapest decisive next test

**Download the Thai AC Unity mod (`thai-mod-game.net`) — or the Thai AC Syndicate mod
(Nexus #65) — extract it WITHOUT installing (unzip the installer / read its `.forge` patch),
and DIFF it against the pristine game to see exactly what it changes.**

That one diff answers everything and hands over a proven, copy-able recipe for a *non-shipped
script on this exact engine*:
- Which resource it edits (expected: rec109 `TGame Bootstrap Settings`).
- Whether it edits the TTF(s), and/or a **codepoint→font routing / glyph-set table** (this is the
  piece H1 says is missing) — and how it wires the new script in.
- How it addresses the "font size" issue (the metrics/scale fixup).

This is read-only, needs no game launch, and no writing to the pristine `E:\Games\...` install.
If it edits rec109 + a routing table, replicate it for Hebrew into **Shilia** (Arabic subtitle
slot) → likely elevates this to **SOLVED**.

**Secondary tests** (each needs a deploy → out of this research task's scope, for the build phase):
- Re-inject Hebrew into **Shilia only** with minimal subsetting (preserve its cmap subtable), and
  re-test in-game (isolates H2).
- After confirming the routing table's semantics, add Hebrew's codepoints to it (isolates H1).

---

## 5. Facts worth keeping (reusable)

- **Target = subtitles only.** `Menu Language` offers no Arabic (LTR only); `Subtitles language`
  offers Arabic. Menus are structurally unreachable; the Hebrew deliverable is the subtitle surface
  via the Arabic subtitle slot (`TLocalizationPackage_Arabic_Subtitles`, rec 1594).
- **The Hebrew font target is `Shilia 330 Light`** (font index 6 in rec109) — the only Arabic-
  capable face; it renders the Arabic subtitles.
- rec109 `Font` object layout: `[u32 0x70a6a7ec][u32 storedSize][raw sfnt TTF]`; storedSize = TTF
  byte length (must track the TTF if grown; the repo's delta-0 inject keeps it constant + pads).
- No glyph atlas / FireFontDescriptor / second font resource exists in any forge — rec109 is it.
- A near-dense BMP u16 codepoint table sits at ~0x626d8ac in rec109 (includes Hebrew) — candidate
  for the render-time codepoint→font routing (H1); its exact semantics are unconfirmed.
- Engine has NO DirectWrite/FreeType/HarfBuzz/Uniscribe/ICU imports (exe + 8 DLLs); ACU.exe is
  VMProtect-packed (all sections rawsz=0, RWX `.UBX1`).

### Tools written this session (read-only, in `c:/tmp/acu_res/`)
`pe_fonts.py` (PE import/string font scan) · `list_res.py` (forge resource+class listing) ·
`scan_ffd.py` (decompressed-content signature scan) · `dissect109.py`/`dissect109b.py` (rec109 map).
Reused: `tools/acu_forge.py`, `work/acu_loc.py`, `work/scan_fd2.py`, `work/tally_types.py`,
`work/classreg.json`. Run everything with the repo `.venv` python (base Python lacks LZO/fontTools
and the scanners swallow that → assert the decoder decodes a known-good resource first, done here:
`acu_loc.py extract/loc_english.bin` → 8999 strings).

## מסמכים קשורים
- באותה תיקייה: [[games/acunity/BRIEF|BRIEF]], [[games/acunity/FEASIBILITY|FEASIBILITY]], [[games/acunity/PIPELINE|PIPELINE]], [[games/acunity/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acunity|CLAUDE_INDEX_games]]
