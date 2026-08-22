# AC2 Hebrew — the 19px `ה` box: small-size render research (read-only, 2026-07-27)

Research + experiment design only. **Nothing was written to `D:\Games\Assassin's Creed II`**
(all measurements read the pristine `_HE_BACKUP/*.forge` and the two exes; no game launch).
Repo venv used for every measurement.

---

## TL;DR VERDICT on the 19px `ה`

**NOT fixable by enlarging the glyph in the ProMedium atlas** (confirmed — the cell UV rects are
engine-fixed and match the *original Latin* shapes, so a bigger Hebrew glyph is clipped, not scaled).
**A bespoke small `ה` FORM in the atlas is a LOW-probability last resort** (the recorded in-game
attempts already bracket the failure: attached leg → clean box; 34%-detached top → floating segment).

**The correct, precedent-backed fix is to make the Options/Controls screen render with a LARGER font
family (ProLight or ProBold) instead of the tiny ProMedium** — because on-screen size ≈ 0.65 ×
atlas-cell-height, and that surface is small *only* because it uses the smallest-celled Latin atlas.
This is exactly what Ubisoft itself does for every non-Latin script (see Prior Art). Two ways to do
it, in cost order:

1. **DATA edit** — add a ProLight font reference to the `Animus_OptionsProcedural` UI resource
   (the same mechanism the working screens use). Preferred; unproven FCB edit + a real layout-overflow
   risk.
2. **EXE repoint of the engine default font** — `AssassinsCreedIIGame.exe` is a **plain, unprotected,
   fully-relocatable x86 PE** (no Denuvo/VMProtect/SecuROM/Themida; the lone `tages` string is a dead
   leftover), so an exe patch is *legitimate*, but locating the default-font/size binding is a
   runtime-trace task (several launches).

So, in the coordinator's own terms: **the 19px `ה` "needs a different atlas/family for that screen"**,
achievable via data (best) or a clean exe patch, with a bespoke-atlas glyph as a low-odds fallback.

---

## 1. Premise verification — which surfaces render at which px

I cannot launch the game, so the on-screen numbers below combine (a) atlas cell heights I measured
now from the pristine forge, and (b) the in-game measurements already recorded in memory
[[ac2-controls-font-atlas-ceiling]]. The relationship is consistent and gives a clean model.

Measured **atlas cell heights** (median over the A–Z carrier cells, pristine `DataPC_extra.forge`):

| Font family | atlas cell h (median) | `ה`-carrier cell (`Q`) | recorded on-screen h | ratio |
|---|---|---|---|---|
| **ProLight**  (main menu, inventory, popups) | **43 px** | 23×43 | **~28 px** | 0.65 |
| **ProMedium** (Options/Controls body — the problem) | **28 px** (`ה` cell 23) | 29×23 | **~19 px** | 0.68 (median) / 0.83 (`ה` cell) |
| **ProBold**   (headers / HUD) | **43 px** | 32×43 | **~27 px** | 0.63 |

- **The ratio is ~0.63–0.68 across all three families → on-screen size ≈ 0.65 × atlas-cell-height,
  a single global UI scale.** ProMedium renders small *only* because its atlas cells are ~1.5× shorter
  than ProLight's. This is the key mechanism and it reframes the whole problem: the fix is cell-height
  (i.e. font family), not glyph artistry.
- The "~19 px" figure is the on-screen height of the `ה` glyph on the Controls screen (its cell is
  23 px, the shortest; 23 × 0.83 ≈ 19). Premise **confirmed** to the precision available offline.
- The main menu (ProLight, 28 px) already renders `ה` cleanly — proving 28 px is above the legibility
  floor and 19 px is below it.

**SOLID-BLOCK PROBE (designed, not run)** — to re-measure the true on-screen px per surface in ONE
launch. It is the technique already in `work/probe_cell_metrics.py` (proven on ProLight); extend it:
- For each of ProLight / ProMedium / ProBold, paint each carrier cell's FULL bbox **solid white** in
  its atlas (`A[y0:y1+1, x0:x1+1] = 255`), texconv→BC3, deploy to a scratch copy of
  `DataPC_extra.forge`, and patch a KNOWN string on each target surface with the carriers (main menu,
  Options page body, a section header).
- One screenshot → measure each solid block's on-screen pixel height with a ruler. This yields the
  exact per-family scale and confirms the 19 px figure and the 0.65 constant. (It also re-confirms the
  UV rect ≤ bbox, i.e. no leftover ink — already true for ProLight.)
- ⚠️ The Options body font must be confirmed to be ProMedium on that exact screen (the recorded
  hex-probe says so). Put the block string on the actual Controls list rows, not a header.

---

## 2. Is the atlas route genuinely exhausted?

### 2a. Full font-atlas inventory (`DataPC_extra.forge`, pristine)

Every real font atlas (the codex/`ADB_Glyph*` illustration blobs are excluded):

| Resource | dims | fmt | tex bytes | used for |
|---|---|---|---|---|
| `AC2Aaux_ProLight_Latin_1_MapDesc`   | **512×512**  | DXT5 | 262,144 | main menu / inventory / popups (Hebrew already injected, 28 px, good) |
| `AC2Aaux_ProMedium_Latin_1_MapDesc`  | **256×512**  | DXT5 | 131,072 | **Options/Controls body — the 19 px surface** |
| `AC2Aaux_ProBold_Latin_1_MapDesc`    | **512×1024** | DXT5 | 524,288 | headers / HUD |
| `AC2Aaux_ProBold_Numbers_1_MapDesc`  | 256×256 | DXT1 | 32,768 | numerals |
| `AC2Aaux_ProBold_RussianCharacterSet_1_MapDesc` | 512×1024 | DXT5 | 524,288 | Russian |
| `UbiGame_Text_TMP3_RussianCharacterSet_1_MapDesc` | 512×1024 | DXT5 | 524,288 | Russian (2nd) |
| `AC2Aaux_ProBold_KoreanCharacterSet_1_MapDesc` | 1024×2048 | DXT5 | 2,097,152 | Korean |
| `MDChamGothic_PS3_KoreanCharacterSet_1_MapDesc` | 2048×2048 | DXT5 | 4,194,304 | Korean (2nd) |
| `AC2Aaux_ProBold_JapaneseCharacterSet_1_MapDesc` | 2048×2048 | DXT5 | 4,194,304 | Japanese |
| `AC2Aaux_ProBold_{Sim,Tra}ChineseCharacterSet_1_MapDesc` | 2048×2048 | DXT5 | 4,194,304 | Chinese |
| `DFHeiW5-GB / DFPHeiMedium-B5 / DFPSoGei-W5 …CharacterSet` | (huge, alt CFD layout) | – | 1.3–1.7 MB | CJK (2nd) |

(Identical set duplicated in `DataPC_extra_dlc.forge`.) All three Latin atlases are **mips=1** (no mip
chain), so mip-sampling is *not* the cause of the gap closing. There are only three Latin atlases; the
smallest (ProMedium 256×512) is the Options surface.

**🔑 The single most important inventory fact: every NON-Latin CharacterSet ships ONLY at ProBold-tier
or larger. There is no ProMedium or ProLight variant of any non-Latin script.** Ubisoft never authored
a *small* non-Latin bitmap font — for Russian/Korean/Japanese/Chinese the engine renders everything
(including the Options screen) in the bigger ProBold/CharacterSet face. **This is proof-by-construction
that legible small non-Latin text was a wall Ubisoft's own team sidestepped by upsizing the font, not
by drawing a tiny glyph.** It is the strongest evidence in this whole report, and it points straight at
the font-reselection fix.

### 2b. Can ProMedium's on-screen text simply be made bigger via the atlas? NO.

The recorded ceiling finding [[ac2-controls-font-atlas-ceiling]] is corroborated by the mechanism
above: on-screen size = 0.65 × **cell** height, and the cell (UV) rect is **fixed** — the empirically
derived cells *still match the original Latin glyph shapes* even after Hebrew injection, which proves
the rects are a baked table (from the original Latin atlas), not auto-detected from current ink. So a
larger Hebrew glyph drawn into ProMedium's cell is clipped to the small rect, not enlarged. The rect
table was searched for in the exe (as int32/float/UV) and in the `_MapDesc` payload → 0 hits, i.e. it
is engine-internal/computed. **Enlarging via the atlas is dead.**

- **Decisive re-confirmation (ladder, designed not run):** deploy ProMedium `ה` variants where the
  glyph INK progressively fills more of the cell and then *overflows* it, each on a different Options-
  screen string, one screenshot. If on-screen `ה` grows → cells are ink-detected → atlas route lives.
  If it stays 19 px and clips → cells are fixed → dead. Expect the latter (the "cells match original
  Latin" evidence already implies it).

### 2c. Repoint the small surface at a bigger atlas — collapses into "font reselection"

Swapping ProMedium's *texture bytes* for ProLight's does nothing: the engine still uses ProMedium's
small cell rects → clipped. The only way to get bigger cells on the Options screen is to make that
screen USE a different font family. I investigated whether that selection is data-editable:

- Font resources are referenced by a **forge-local 32-bit id** (the record's middle `u32`):
  ProLight `0xbaf200c7`, ProMedium `0xbaf20127`, ProBold `0xbb2e807d`.
- Searching all UI-screen resources: screens that render at 28 px **reference the ProLight id** —
  `Animus_PopupBase`, `Animus_PausePresent`, `VillaMenu`, `Animus_InventoryNavigation`. ✅ matches the
  "these look good" reality.
- **`Animus_OptionsProcedural` (the Options screen, 329 KB) and `Animus_VirtualKeyboard` reference NO
  font id at all.** → they use the **engine DEFAULT font = ProMedium.** That is *why* the Controls
  screen is the one problem surface.
- The ProMedium id has **zero UI-screen references** (its only matches are inside its own `_MapDesc`
  self-linkage at +391/+471/+587), and the font ids appear **nowhere in the exe** (forge-local, not the
  global 64-bit GUID the engine binds the default with). So the default-font choice is set deeper (font-
  manager, keyed by GUID), not as a flip-able id or a 4-byte exe constant.

⇒ **Font reselection is a real, precedent-backed mechanism**, but the Options screen's specific
selection is *the default*, so making it use ProLight means either (a) editing `Animus_OptionsProcedural`
to ADD a ProLight reference (data, unproven FCB structure, layout-overflow risk since ProLight cells are
1.5× taller than the tightly-packed Controls rows), or (b) an exe change to the default font.

### 2d. Can `ה` alone get a bespoke pixel form that survives 19px? — low odds, one ladder left

`full_deploy.py`/`font_inject.py` already render `ה` with a special case (`if ch == "ה"`: detach the
top ~34% of the left leg). Memory records the in-game outcome: **attached leg → clean box (reads as
`ם`); 34%-detached → a broken floating segment.** Those two results bracket the failure — at 19 px
after BC3-alpha quantization + the ~0.83× bilinear downscale, the window between "the counter closes"
and "the leg detaches into a floating bar" is razor-thin. Offline downscale sims are *optimistic*
(recorded) and must not be trusted here.

Untested treatments worth ONE consolidated ladder (design; expect it to confirm the wall):
- **Hand-authored pixels at the target size**, block-aligned: draw `ה` directly as a crisp ~23-px
  bitmap with the counter forced to a full 4×4 DXT block and the roof/leg strokes kept to 2 px so
  bilinear can't bleed them into the counter (instead of LANCZOS-downscaling a TTF).
- **Alternative letterforms** in the same cell: an open-counter `ה`, a heavier-stroke `ה`, and a
  clearly-detached-leg `ה` with generous whitespace — three variants side by side.
- Ship all ~5 variants on adjacent Options-screen strings in ONE build; one screenshot decides.
- Circumstantial prior probability against success: Ubisoft's own designers never authored a small
  non-Latin bitmap (§2a) — they always upsized. That is a strong hint 19 px non-Latin is impractical
  on this engine's DXT-atlas path.

---

## 3. The exe patch — protection status + how to find the constant

### 3a. Measured protection (`AssassinsCreedIIGame.exe`, 34.7 MB, md5 `aa546ce8b00da9ec3575b939ef9b65b9`)

| Check | Result |
|---|---|
| Machine / ImageBase | **x86 (0x14c)** / 0x400000 |
| Entry point section | **`.text`** (VA 0x1000) — the normal code section, NOT a packer stub |
| `.text` entropy | **6.45** — normal x86 code (packed/encrypted code is > 7.0) |
| `.rdata` / `.data` entropy | 6.26 / 3.74 — normal |
| `.rsrc` entropy | 7.93 — normal (compressed icons/manifest, expected) |
| `.reloc` | **present, 1.45 MB = 4.1 % of image** — a fully-relocatable PE (packers strip/shrink this) |
| Denuvo / VMProtect / `.vmp` / SecuROM / Themida / SafeDisc / SolidShield | **NONE** |
| `tages` string | **×1 — a dead leftover** (AC2's original Tagès DRM). Not active: entry in `.text`, normal entropy, full `.reloc`, game runs offline. Active Tagès adds a driver + a high-entropy section + an abnormal entry point — none present. |
| font strings | `firefont` ×1, `fontdescriptor` ×1 (reflection metadata, 0 push-immediate xrefs per prior recon); `prolight/promedium/probold/aaux` = **0** (hash-addressed) |

**Conclusion: a clean, unprotected, statically-analyzable x86 PE. An exe patch is technically
legitimate — no DRM circumvention involved.** (`AssassinsCreedII.exe` is a 13 KB launcher stub; ignore
it. `UPlayBrowser.exe` is unrelated.)

### 3b. How to locate the font-size / default-font binding (roadmap — DO NOT patch)

The font ids are forge-local and absent from the exe, and there is no plain size/box table in the exe
(prior recon: searched as int32/float/UV → 0 hits). So this is a **runtime-tracing** task, not a
string-anchored static patch. Two possible targets, pick the cheaper once tracing starts:

- **Target A — the default-font binding (preferred).** The Options screen uses the default font. Trace
  where the font-manager resolves the default and repoint it from ProMedium's GUID to ProLight's. Method
  (all doable non-elevated, same-user): launch under `__COMPAT_LAYER=RUNASINVOKER`; with a ctypes
  `PAGE_GUARD` debugger (see [[autonomous-ingame-verification]]) set a read-watchpoint on the ProMedium
  `_MapDesc` **texture bytes in the running process** (find the VA by scanning committed RW pages for the
  deployed DXT5 signature) — the RIP that first samples it while the Options screen renders is the glyph
  sampler; walk the call stack up to the point that *selected* ProMedium and see what constant/GUID drives
  it. ⚠️ the atlas loads once and is cached → arm the watchpoint BEFORE the Options screen first renders.
- **Target B — the per-family draw scale.** on-screen = 0.65 × cell. If the 0.65 (or the per-family point
  size) is a float constant read in the draw path, bumping ProMedium's factor to ProLight's enlarges only
  that family. Same watchpoint entry, then disassemble backward from the sampler for the size/scale mul.

Risks to verify after any exe change: (a) enlarging the Options font can overflow/overlap the tightly-
packed Controls list rows → check layout; (b) don't touch a *global* UI scale (would balloon the already-
good main menu). Cost: **3–6 launches** (arm/trace/verify), harder than any data route.

---

## 4. Prior art (non-Latin AC2 / the AnvilNext-family small-size wall)

- **Ubisoft's own solution = upsize, never shrink (strongest evidence, §2a):** the game ships *no* small
  non-Latin bitmap. Russian/Korean/Japanese/Chinese render in ProBold-tier atlases on *every* screen. The
  official answer to "small options text in a non-Latin script" was to use a bigger font — precisely the
  font-reselection fix recommended here.
- **Turkish AC2 patch** (community, 2025): distributes a modified **`DataPC_extra.forge`** "to fix many
  font errors" — confirming the standard AC2 approach is editing the DDS atlas in that forge (what this
  project does). Turkish uses accented Latin (İ Ş Ğ Ç Ö Ü) that already fits the Latin atlas, so it does
  not hit the new-script/small-size wall as hard as Hebrew.
- **Persian (Fansub.ir / PersianLingo / GameNub)** and Russian patches exist and translate menus +
  subtitles, but none publishes its font/size technique; search results only hint at "different font-size
  options" in the subtitle variants (i.e. they offer size *presets*, not a small-size fix).
- **AnvilNext/Dunia/Disrupt family (Odyssey/Syndicate/Watch Dogs) — the same wall, one engine newer:**
  the community tool **FFDConverter** (`eprilx/FFDConverter`) edits `.ffd` bitmap fonts for those engines,
  and the recurring known limitation there is exactly "font size cannot be increased" — the same symptom
  class the sibling research flagged (the Thai Odyssey precedent). FFDConverter targets `.ffd`, **not**
  AC2's Scimitar DDS `_MapDesc` atlases, so it does not apply to AC2 directly; but it confirms the pattern:
  across this engine lineage, glyph SIZE is engine-side and the community fix is upsizing the source face,
  never rescuing a tiny glyph.
- **Tools:** the AC2 community font/forge tool is Turfster's `.forge extractor/replacer` (ModDB) + `texconv`
  for the DDS — this project already reimplements both in pure Python (`tools/ac2_forge.py` +
  `work/ac2_font.py`), so no external dependency is needed.

**Takeaway:** there is no known community trick that makes a tiny DXT-atlas non-Latin glyph legible on
this engine. The universal workaround is to render the surface with a bigger font — the font-reselection
route.

---

## 5. The two parked follow-ups — current state + cost

### (a) Carriers on base Latin A–Z break untranslated English — **ALREADY SOLVED for ProLight**

`work/full_deploy.py` (2026-07-22) is a complete builder that injects the 27 Hebrew glyphs into
**accented carrier cells** (`ac2_carriers27.json`, the À/Á/É/… cells) instead of base A–Z, AND clears
each accented cell's separate diacritic blob (the exact concern in the follow-up: it wipes both the base
cell and the accent-mark blob in a 26–30 px band above it — 82 lines of that script). So base A–Z stays
Latin and untranslated English/Italian/brand names render normally, no gibberish. **State: solved and
built for ProLight; verified logic present.**

- **Remaining cost:** `full_deploy.py` only injects **ProLight**. `font_inject.py` (which injects
  ProMedium/ProBold) still uses **base A–Z carriers** (`azmap_<fam>.json`), inconsistent with ProLight's
  accented carriers. To ship a complete mod the two carrier maps must be UNIFIED — inject the SAME
  accented carriers into ProMedium + ProBold. **~1–2 h of tooling + 1 verification launch.**

### (b) How much beyond the main menu is translated — **translation is 100% done; the mod build is partial**

- **Translation: COMPLETE.** `fleet/hebrew.json` holds all **10,003 lines** (4,403 UI + 5,600 subtitles),
  100 % non-empty; all fleet streams report `drained (complete)`. The `/translate` community pool (10,062
  rows) is live.
- **Build/deploy path: EXISTS and is near-complete.** `full_deploy.py` encodes ALL 10,003 lines into both
  loc packages (`LocalizationPackage_English` + `_Subtitles`) via `ac2_rtl.to_visual` + the accented
  carrier map, with a pre-deploy round-trip assert, and builds the ProLight atlas. So every ProLight
  surface (main menu, inventory, popups, pause) would show full Hebrew.

**What a complete, shippable AC2 Hebrew mod still requires:**

1. **Inject Hebrew into ProMedium + ProBold with the SAME accented carriers** (else the Options/Controls
   screen and headers show accented-Latin gibberish instead of Hebrew). ~1–2 h + 1 launch.
2. **Decide the 19 px `ה` (this report):** ship the font-reselection fix for the Options screen (best), OR
   accept a single-letter cosmetic box on that one screen, OR spend the exe-trace. The mod is otherwise
   fully legible everywhere ProLight/ProBold is used.
3. **QA pass on wording** — the recorded examples (`DISMISS` → "פטור" is context-wrong; the `[Laughs]`/
   bracket handling) need a review sweep over the 10,003 lines.
4. **Character/name consistency** — a `name_registry.json` exists in `fleet/`; confirm it's applied.
5. **Publish** (project standard, gated on an explicit "פרסם"): GitHub `assassinscreed2-hebrew-mods`
   release (the two edited forges or a loose-file installer) + Supabase `games` row (id `ac2`) +
   Worker slug + a launcher applier. Deploy is a forge overwrite; REVERT = copy `_HE_BACKUP/*.forge` back.

---

## 6. Ranked plan (cost + launches)

| # | Step | What it buys | Cost | Launches |
|---|---|---|---|---|
| 1 | **Unify ProMedium+ProBold injection to accented carriers** | Hebrew (not gibberish) on Options/headers | 1–2 h | 1 |
| 2 | **Re-run the SOLID-BLOCK probe on all 3 families** | exact per-surface px; confirms 19 px + the 0.65 scale | 0.5 h | 1 |
| 3a | **DATA font-reselection: add a ProLight ref to `Animus_OptionsProcedural`** (preferred fix) | legible 28 px `ה` on the Controls screen, no exe patch | 3–6 h (FCB RE) | 1–3 (+layout-overflow risk) |
| 3b | *(if 3a fails)* **`ה`-form ladder in ProMedium** (hand-pixels + alt letterforms) | maybe rescues 19 px `ה` | 2–3 h | 1 |
| 3c | *(if 3a/3b fail)* **EXE default-font/scale repoint** (clean PE, runtime trace) | legible Options screen | 1–2 days | 3–6 |
| 4 | **Wording/name QA sweep over 10,003 lines** | quality | delegate | 0 |
| 5 | **Publish** (on "פרסם") | shipped mod | 1–2 h | 0 |

**Recommended path:** 1 → 2 → 3a. If 3a's FCB edit proves intractable or overflows the layout, fall back
to 3b (one cheap ladder), and only then 3c. Steps 1–2 are independent of the `ה` decision and should ship
regardless — they make the whole game Hebrew, leaving the Options `ה` as the single open cosmetic item.

---

## 7. Tools / artifacts touched (all read-only on the game)

- `tools/ac2_forge.py` (forge reader), `work/ac2_font.py` (atlas Atlas/decode), `work/full_deploy.py`
  (the full-mod builder — carriers already accented, all 10,003 lines), `work/font_inject.py`
  (ProMedium/ProBold injector — still base-A–Z carriers, needs unifying).
- New scratchpad probes written to the session scratchpad (`enum_atlases.py`, `font_atlases.json`,
  `atlas_inventory.json`) — not in the repo.
- Font ids: ProLight `0xbaf200c7`, ProMedium `0xbaf20127`, ProBold `0xbb2e807d`.
- Exe: `AssassinsCreedIIGame.exe` md5 `aa546ce8b00da9ec3575b939ef9b65b9` — clean unprotected x86 PE.

**Sources (prior art):**
[Turkish AC2 patch (DataPC_extra.forge font fix)](https://steamcommunity.com/app/33230/discussions/0/1368380934245887874/) ·
[Persian AC2 patch — Fansub.ir](https://fansub.ir/ac-ii-patch/) ·
[FFDConverter (AnvilNext/Dunia/Disrupt .ffd fonts)](https://github.com/eprilx/FFDConverter) ·
[Turfster .forge extractor/replacer](https://www.moddb.com/games/assassins-creed-ii/downloads/forge-extractorreplacer-by-turfster) ·
[Game-localization typography / bitmap-atlas downsides](https://www.sidebearings.com/game-localization-typography-challenges/)

## מסמכים קשורים
- באותה תיקייה: [[games/assassinscreed2/FEASIBILITY|FEASIBILITY]], [[games/assassinscreed2/FORMAT|FORMAT]], [[games/assassinscreed2/PIPELINE|PIPELINE]], [[games/assassinscreed2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#assassinscreed2|CLAUDE_INDEX_games]]
