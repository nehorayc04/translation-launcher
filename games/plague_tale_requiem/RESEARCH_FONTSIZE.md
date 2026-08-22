# A Plague Tale: Requiem — Hebrew subtitle FONT-SIZE research

**Date:** 2026-07-27 · read-only recon (no game file modified, no launch, no DRM circumvention)
**Tooling:** repo `.venv` python · `capstone` disasm · streaming DPC TOC reader · `bff`/`APT_DPC_Tool`/`fmtk` sources.

---

## ⚠️ THE PREMISE IN CLAUDE.md IS STALE — READ THIS FIRST

The task brief (copied from an older CLAUDE.md snapshot) says *"on-screen size is NOT in the font
file, proven 6 ways; the LADDER is the one untested lever."* **The actual code disproves this and
the LADDER was already run.** `work/font/build_hebrew_font.py` lines 152-168:

> `✅ LADDER ANSWERED IN-GAME 2026-07-12: the three groups rendered at three clearly different sizes
> ... the ON-SCREEN SIZE FOLLOWS THE ATLAS INK, and the old "the engine normalises everything to a
> fixed cell" conclusion is WRONG — it came from the atlas-shrink test, which was confounded.`

So **size IS controllable from the font (the atlas-ink height), and it is already being controlled.**
The build currently ships `LADDER_INK = (9, 8, 7)`, `LADDER = False` → a uniform **9 px** ink, i.e.
Hebrew is *already small*. The genuine, still-open problem is **quality at small size**, not "can't
shrink".

---

## VERDICT

| Question | Verdict |
|---|---|
| Can Hebrew subtitles be made **small / normal-sized**? | **SOLVED** — atlas-ink lever, already shipping (9 px). |
| Can they be small **AND as sharp as the English subtitles**? | **RESEARCH-GRADE (leaning LIKELY, not IMPOSSIBLE).** The blur is the engine **up-scaling** the small atlas glyph by a per-font magnification `M>1` that is intrinsic to the `BIG_ARABIC` slot and is **not stored in the font**. Escaping it needs an *external* lever (exe patch or the compiled-UI subtitle widget), each needing ~1 more RE step + one game launch to confirm. It is not blocked by DRM (exe is unpacked) or by data (levers exist). |

**One-line answer to the brief's core question ("can Arabic-slot SUBTITLES use a SMALL font?"):**
Architecturally they currently use the **BIG** slot (→ `BIG_ARABIC`); there is **no `SMALL_ARABIC`**
and the engine's SMALL-font selector has **no Arabic branch** (hard-coded to Latin `SMALL_FONT`).
Making subtitles use a small font is possible but is **not a clean loose-file edit** — it requires
either an exe patch (redirect the Arabic font-name the selector hashes) or locating the subtitle
widget's font/size in the compiled UI (`All.psc`, tokenised — not yet cracked).

---

## THE MECHANISM (all verified this session)

### 1. Fonts are resolved by a **CRC-64 hash of the font NAME**, and the BIG slot is language-aware while the SMALL slot is NOT
Disassembled the font-registration routine at **`va 0x141342B90`** (`APlagueTaleRequiem_x64.exe`,
file 0x01341B90). It switches on the current language id (`ecx`) and hashes one `BIG_<lang>` name:

| lang id (dec) | branch | font name hashed |
|---|---|---|
| 0 | `test eax,eax` | `BIG_JAP` |
| 17 | `cmp ecx,0x11` | `BIG_RUS` |
| 9 | `cmp ecx,9` | `BIG_KOR` |
| 21 / 22 | `add eax,-0x15; cmp eax,1; jbe` | `BIG_CHI` |
| **23** | `cmp ecx,0x17` @`0x141342CE4` | **`BIG_ARABIC`** (`lea` @`0x141342CF4`, file `0x013420F4`) |
| else | default @`0x141342D89` | `BIG_FONT` |

Then **unconditionally** (no language switch) it hashes **`SMALL_FONT`** (`lea` @`0x141342DAA`,
file `0x013421AA`) and `DEBUG_FONT`, storing all three via `call 0x140d7de00` into globals.
The hash uses two tables at `.data 0x1b770f0` (256 B) + `0x1b771f0` (2048 B) — a standard reflected
CRC-64. **No point-size/scale float is passed anywhere in this routine.**

**Consequence:** every Arabic-slot line — menus AND subtitles — falls back to the **BIG** family →
`BIG_ARABIC`. The subtitle renders (it is *not* tofu, per the user), which proves it uses the BIG
slot (if it used the Latin `SMALL_FONT` it would be tofu). `LangDef.tsc` line 18
(`AddLangDefine 23 ... ARABIC`) confirms Arabic = language id **23**, matching the `cmp ecx,0x17` branch.

### 2. There is NO `SMALL_ARABIC` (or `SMALL_ARA`/`SMALL_AR`) anywhere
Byte-scanned the exe: `SMALL_JAP`, `SMALL_KOR`, `SMALL_CHI` **exist** in the `.data` property/enum
string table (`0x1B72980-0x1B729A0`) — so a per-language SMALL family is *conceived* in the engine —
**but they have ZERO code xrefs** (no `lea`/pointer references in `.text`) and are **not loaded by
`InitFont.tsc`** (which loads only `BIG_FONT · SMALL_FONT · SMALL_FONT_02 · BIG_RUS · BIG_JAP · BIG_KOR
· BIG_CHI · BIG_ARABIC`). `SMALL_ARABIC`/`SMALL_ARA`/`SMALL_AR` are **absent** from the exe and from
the FONT DPC. So the engine has no built-in small-Arabic path to activate.

### 3. `Fonts_Z` has **no size/scale/point-size field** — authoritatively
From `widberg/bff` (`bff/src/class/fonts/v1_381_67_09_pc.rs`), the `Fonts_Z` body is exactly:
```
characters:      map<CharacterID, { material_index: u32, descent: f32,
                                    top_left_corner: Vec2f, bottom_right_corner: Vec2f }>
material_names:  DynArray<Name>
```
(Requiem's 40-byte entry adds `advance`, `bearX/bearY` vs this v1.381 struct, but the object still
has **no font-level size/em/line-height/scale**.) The project's own `_diag_scale.py` confirms the
**footer is byte-identical across all 8 fonts** (`08 00 00 00 41 00 00 00`). ⇒ **You cannot change
on-screen size by editing the Fonts_Z object header/footer — the only size knob inside the font is
the per-glyph atlas box (the "ink"), which is exactly the LADDER lever.**

### 4. The render model, reconciled from all in-game evidence
- **LADDER (box tight, vary ink):** ink 40/26/16 → three different on-screen sizes (A>B>C). ⇒ screen ∝ inked box.
- **atlas-shrink (box fixed, shrink ink inside):** same on-screen size, blurrier. ⇒ the small glyph is **up-scaled** to fill the rendered size.
- **User reaction:** 26 px ink read as *too big*; every step down (21→17→9) still needed shrinking. ⇒ the BIG_ARABIC slot **magnifies** (`M > 1`): a 17 px ink already renders larger than desired, and the only way down is tinier ink, which the engine then up-scales → the "chunky/blurry, not like Word" the user reports.

So: **on-screen ≈ (atlas ink height) × M**, with **M > 1 and specific to the BIG_ARABIC slot**
(the English subtitle font renders normal-sized from a *bigger* atlas cap — `SMALL_FONT` cap 57 vs
`BIG_ARABIC` cap 79 — so its M is smaller). `M` is the quality limiter, and per §3 it is **not in
the font object**. It is set by the GUI layer (the widget's requested render size for the BIG slot).

> ⚠️ The absolute magnification numbers in the code comments (e.g. "26 px ink → 86 px screen,
> M≈3.3") are **self-flagged as unreliable** — `build_hebrew_font.py:226` warns they came from an
> autonomous capture taken while a **stale, elevated** instance of the game was running (wrong build
> photographed). Treat "M > 1, per-font" as proven; treat the exact value as unknown.

### 5. The subtitle widget (with `FontName`/`FontSize`) is NOT in a reachable loose/plain file
- `FontName`, `FontSize`, `FontLanguageOverride`, `FontColor`, `FontOutline*` are a contiguous block
  of **script-parser keyword strings** in the exe `.data` (`0x1B739A8-0x1B73B28`) → UI widgets are
  defined in `.tsc`/`.psc` scripts with these properties.
- `All.psc` (1.47 MB, the compiled `.tsc` bundle) contains `Dialog`/`Subtitle` **flow** but **0**
  occurrences of `FontName`/`FontSize`/`BIG_ARABIC`/`SMALL_FONT` → the property keywords are
  **tokenised/hashed** in the compiled `.psc`, so the FontSize *value* is a number after an opcode,
  not greppable.
- `COMMON.DPC` (31 GB) — parsed its map-only TOC (55,756 objects) and decoded samples: it holds only
  **4 low-level asset classes** (Texture + 3 unknown geometry/material/node hashes with binary
  float bodies, **no strings, no GUI/widget/font data**). The subtitle widget is **not** here.
- ⇒ The subtitle widget's `FontSize`/font-slot lives in the compiled `All.psc` opcode stream (format
  not yet reversed) or is a hard-coded default in the exe. **This is the missing piece for the clean
  fix.**

### 6. The exe is UNPACKED and DRM-free (a static patch is technically on the table)
`.text` entropy 6.51, entry point in `.text`, **no** VMProtect/Themida/Denuvo/UPX/Enigma signatures.
(A benign high-entropy `.bind` section is present — a loader stub, not a protector over the code we'd
touch.) A single font-name-pointer patch is **not** DRM circumvention. It is still an exe edit
(heavier, and reverted by any game update).

---

## RANKED EXPERIMENTS (do them in this order)

Each says exactly what to run, how many game launches it costs, and what each outcome proves.
"Build only" = `python work/font/build_hebrew_font.py` (offline Pillow verify, **no deploy**).
"Deploy"    = add `--deploy` (backs up `FONT/ENGLISH.DPC` → `.he_backup` once). Revert = `--revert`.
**Always confirm no stale/elevated game instance is running before judging a capture**
(`build_hebrew_font.py` already refuses to measure a process older than the deploy;
see `stale-elevated-instance-fakes-no-change`).

### ① EM-CLAMP × LARGE-INK — the decisive font-only test for "small AND sharp"  ·  1 launch
**Hypothesis:** the engine derives the render em/line-height for a font from its **tallest declared
glyph boxes**; `BIG_ARABIC` has ~100 *unused* Arabic glyphs declaring ~90 px boxes that inflate the
em, so all Arabic-slot text renders at the BIG em. If true, shrinking those boxes lowers the em, and
then a **large, sharp** Hebrew ink renders **small** = the whole problem solved font-side.
**Why it's untested-clean:** the current build already runs the clamp (`EM_CLAMP=48`, default) **but
with 9 px ink**, so a "still small+blurry" result can't distinguish "clamp did nothing" from "clamp
worked but 9 px is blurry regardless". Isolate it by pairing the clamp with LARGE ink.
**Steps:** in `build_hebrew_font.py` set `LADDER_INK = (40, 40, 40)` (large, sharp), keep
`--no-shrink` OFF (clamp on), also try a smaller `EM_CLAMP` (e.g. 30). Build → `--deploy` → launch →
read a subtitle.
- **Hebrew renders SMALL and SHARP** ⇒ **SOLVED font-side.** The em is metric-derived; ship large
  ink + a tuned `EM_CLAMP`. No exe patch, no widget hunt.
- **Hebrew renders LARGE (follows the 40 px ink)** ⇒ the em is **not** the lever; on-screen = ink×M
  purely, and there is **no font-only path to sharp small text.** Proceed to ②/③.

### ② Locate & reduce the subtitle widget's `FontSize` in `All.psc`  ·  0 launches to find, 1 to confirm
The clean, correct fix if ① fails: reduce the subtitle widget's requested `FontSize` so the engine
**down-scales** the full-resolution `BIG_ARABIC` glyph (down-scaling is sharp; only up-scaling blurs)
— keep the Hebrew atlas ink at `BIG_ARABIC`'s native ~79 px.
**Steps:** reverse the `All.psc` opcode/token format (magic `bd f5 67 00 ac 6b 16 00`, plaintext
`.tsc` chunk names like `CLONE.TSC`). Map the `FontSize` keyword (exe `.data 0x1B739B8`) to its
opcode; find the subtitle/`InfosText`/`Dialog` widget chunk; read its `FontSize` value; halve it;
repack (its own bundle, not a DPC). Confirm with one launch.
- Feasible (loose editable file, no exe patch) **but** needs the `.psc` format cracked first
  (RESEARCH-GRADE; ~a session). Highest-quality outcome if it lands.
- ⚠️ It may also shrink other widgets that share the subtitle FontSize — check scope in-game.

### ③ exe patch: route the Arabic font to a smaller, Hebrew-injected slot  ·  1-2 launches
The engine's Arabic branch hashes the literal string `BIG_ARABIC` at **`va 0x141342CF4`**
(`lea r8,[rip+0x834fbd]`, file `0x013420F4`). Repoint that `lea`'s disp32 at a **different font
name** whose slot has a smaller cap and Hebrew glyphs:
1. Inject Hebrew into `SMALL_FONT` (cap 57, ~28 % smaller than `BIG_ARABIC` 79) — or add a brand-new
   `SUB_ARABIC` object (cap ~30) to `FONT/ENGLISH.DPC` and `LoadFont FONTES\SUB_ARABIC` in the loose
   `InitFont.tsc`.
2. Patch the `lea` disp32 so the Arabic branch hashes that name instead of `BIG_ARABIC`
   (the target string must exist in the exe and be rip-reachable; `SMALL_FONT` already sits at
   `va 0x141B73B70`).
- ✅ Pure data levers for the font asset + `InitFont.tsc` (both loose/editable); the only exe edit is
  **one 4-byte `lea` displacement**. Not DRM circumvention.
- ⚠️ This changes the size of **all** Arabic-slot text (menus too), and only by the cap ratio
  (`SMALL_FONT` → ~28 % smaller; a custom `SUB_ARABIC` → whatever cap you author). Reverted by any
  game update. Confirm mount + no-tofu + size in-game.

### ④ SHIP the atlas-ink lever as-is, tuned  ·  already deployed, 1 launch per tweak
If ①-③ are deemed too costly, the shipping approach is legitimate: `LADDER_INK` controls the size;
pick the ink that best trades size vs sharpness (currently 9 px). This gives **small** subtitles that
are somewhat soft. It is the fallback, not a fix for "as sharp as English".

---

## RULED OUT (with evidence — do not repeat)

| Idea | Why it's dead |
|---|---|
| Edit a **size/scale field in the `Fonts_Z` object** | `bff` struct + `_diag_scale.py`: the object has **no** such field; footer byte-identical across all 8 fonts. |
| **`SMALL_ARABIC` already exists**, just enable it | Absent from exe and DPC. `SMALL_JAP/KOR/CHI` exist in the `.data` enum table but have **0 code xrefs** and aren't in `InitFont.tsc` — vestigial. |
| The subtitle widget's FontSize is in **`COMMON.DPC`** | COMMON's 55,756 objects are only 4 asset classes (Texture + 3 geometry/material/node); decoded samples have **no strings/GUI/font data**. |
| Grep **`All.psc`** for `FontName`/`FontSize` | 0 hits — keywords are tokenised/hashed in the compiled `.psc`; only `Dialog`/`Subtitle` *flow* strings survive. |
| A **config/ini** sets the Arabic font size | `InitFont.tsc` = `LoadFont` lines only; `LangDef.tsc` = language table (no font/size); no editable size anywhere. |
| **Shrink atlas ink further** for a sharp small result | The engine up-scales small ink by `M>1` → chunky/blurry (the current 9 px "not like Word"). Ink shrink trades quality for size; it cannot give sharp small text. |
| The size lives in a **per-font point-size passed at registration** | Disassembled the registration routine (`0x141342B90`): it passes only the name-hash to `0x140d7de00`; no float/size argument. |

---

## EXTERNAL TOOLS / PRIOR ART

- **`widberg/fmtk`** — Asobo/Zouna format toolkit + wiki (DPC spec, class list incl. `Fonts_Z`,
  `GameObj_Z`, `Node_Z`, `UserDefine_Z`): https://github.com/widberg/fmtk +
  https://github.com/widberg/fmtk/wiki/Asobo-DPC-File-Format-Specification
- **`widberg/bff`** — authoritative Rust structs; `Fonts_Z` layout used above:
  https://github.com/widberg/bff/blob/master/bff/src/class/fonts/v1_381_67_09_pc.rs
- **`amrshaheen61/APT_DPC_Tool`** — the Plague-Tale-specific DPC reader (`Core/DpcHelper.cs`); the
  `ReadFilesMapOnly` map-only path is what COMMON.DPC uses:
  https://github.com/amrshaheen61/APT_DPC_Tool
- **`widberg/ImZouna`** (ImHex hexpat) + **`ZounaModding/RatDecomp`** (engine decomp notes):
  https://github.com/widberg/ImZouna · https://github.com/ZounaModding/RatDecomp
- **PCGamingWiki — Engine:Zouna** (node-based engine background): https://www.pcgamingwiki.com/wiki/Engine:Zouna
- **Prior art on font SIZE:** none found. The only non-Latin Plague Tale fan translation is an
  **Indonesian text mod for *Innocence*** (`CAMKOHA_TL`, Nexus 37) — text only, same DPC approach,
  **no font-size work**. No community mod has changed Asobo/Zouna on-screen font size. So there is no
  shortcut to borrow; ①-③ are original work.

---

## PROJECT-STATE NOTES for whoever picks this up
- Current shipped font build: `LADDER_INK=(9,8,7)`, `LADDER=False` (uniform 9 px), `DEF_FONT` =
  Assistant-Regular, `EM_CLAMP=48` runs by default. Size is already small; the complaint is sharpness.
- The pristine font is `FONT/ENGLISH.DPC.he_backup`; `dpc_repack.py` rebuilds byte-identically; the
  builder re-parses every injected font before deploy and aborts on breakage.
- Scratch tooling written this session (in the sandbox scratchpad): `xref_font.py` (font-name xrefs),
  `disasm_fontsel.py` (the selector disasm), `common_toc.py` (streaming 31 GB TOC),
  `id_classes.py` (COMMON class identify), `DpcHelper.cs` (the map-only spec).

## מסמכים קשורים
- באותה תיקייה: [[games/plague_tale_requiem/FEASIBILITY|FEASIBILITY]], [[games/plague_tale_requiem/PIPELINE|PIPELINE]], [[games/plague_tale_requiem/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#plague_tale_requiem|CLAUDE_INDEX_games]]
