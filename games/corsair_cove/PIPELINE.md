# Corsair Cove — PIPELINE

Run everything with the repo venv: `.venv/Scripts/python.exe`
(`fontTools` + `python-bidi` live there; the base Python has neither and a missing
codec turns every scan into a silent false negative).

## One-time extraction (already done, output in `extract/`)

```bash
R=games/hogwarts_legacy/tools/repak.exe
G="E:/Games/Corsair Cove/CorsairCove/Content/Paks"

# loose files: locres + StringTable CSVs + Config + Engine Slate fonts
$R unpack -o games/corsair_cove/extract/pak0 \
  -i "CorsairCove/Content/Localization" -i "CorsairCove/Content/StringTables" \
  -i "CorsairCove/Config" -i "Engine/Content/Slate/Fonts" "$G/pakchunk0-WinGDK.pak"

# the game's UI fonts
$R unpack -o games/corsair_cove/extract/fonts "$G/pakchunk0_s25-WinGDK.pak"
```

## Tools

| file | role |
|---|---|
| `tools/cc_locres.py` | UE LocRes v3 codec. `load` / `save` / `roundtrip`. **Byte-identical on all 12 shipped cultures.** |
| `tools/cc_ufont.py`  | `.ufont` container = `[u32 sfntSize][sfnt][4×00]`. `selftest` = **18/18 byte-identical**. |
| `tools/cc_font.py`   | Hebrew glyf-merge into the 4 Alegreya faces (reuses `anno1800/work/anno_font._add_hebrew`). |
| `tools/cc_rtl.py`    | `to_logical` = the SHIPPING transform: natural order **+ a leading RLM** to pin the paragraph base. `to_visual` is the A/B counterpart only. Selftest 10/10. |
| `tools/donors/`      | vendored SIL-OFL Hebrew donors so a build is reproducible off-machine. |
| `work/scope_report.py` | scope + surface split + developer kit + dedup-safety + `extract/context_source.json`. |
| `work/build_menu_proof.py` | builds, self-verifies and deploys the Phase-1 proof pak. |

### 🔴 Two codec facts that cost time — do not re-derive

1. **An EMPTY LocRes string is length `0` with NO payload**, not a lone NUL. Writing
   `\x00` with length 1 round-trips *semantically* but is never byte-identical. Fixing
   that (plus writing the REAL refcount, which equals the number of entries pointing at
   the string) is what turned the round-trip byte-exact.
2. **`.ufont` here is NOT a bare TTF.** Until Dawn's `.ufont` starts with the sfnt magic
   at offset 0; Corsair Cove's has a `u32` length prefix and a 4-byte zero tail. Dump the
   first bytes before assuming a sibling game's layout.

## Font

Donors (both SIL OFL → redistributable), chosen for atmosphere, not convenience:

| target | donor | why |
|---|---|---|
| `Alegreya-Regular` / `-SemiBold` | **Frank Ruhl Libre** Regular / Medium | Alegreya is a calligraphic humanist serif; Frank Ruhl is the Hebrew equivalent |
| `AlegreyaSans-{Regular,Bold}-FixedNumbers` | **Assistant** Regular / Bold | both humanist sans |

```bash
.venv/Scripts/python.exe games/corsair_cove/tools/cc_font.py inject \
    games/corsair_cove/extract/fonts games/corsair_cove/work/fonts_he
# -> 4 faces, each 27/27 Hebrew and 26/26 Latin preserved, original font NAMES kept
```

The 14 Noto CJK faces are deliberately skipped: they are per-culture fallbacks for
ja/ko/zh (irrelevant to a Hebrew build) and most are CFF/OTTO, where a glyf merge is a
silent no-op anyway.

Size/weight calibration is a POST-proof step (see the `hebrew-font-calibration` skill) —
the proof only has to answer "do the glyphs render at all".

## Deploy

**🔴 AN ADDED PAK IS NEVER MOUNTED ON THIS BUILD** (proven over two rounds: `~mods/`, the
flat `Paks/` folder, an invented `pakchunk999`, and a manifest-known
`pakchunk0-WinGDK_P.pak` — all ignored). It is a Microsoft-Store/GDK build whose
`package.manifest` + `layout_*.xml` enumerate every shipped pak by name.

**✅ THE LEVER: hijack a shipped 339-byte EMPTY pak stub.** 24 of the shipped paks
(`pakchunk0_s1..s24-WinGDK.pak`) report **`0 file entries`** — all their content went to the
IoStore `.ucas`/`.utoc` half. They are manifest-listed, so the engine definitely mounts them,
and overwriting one loses nothing.

```
pakchunk0_s2-WinGDK.pak   <- en/CoveGame.locres
pakchunk0_s3-WinGDK.pak   <- Content/StringTables/UI/*.csv   (a live SECOND surface)
pakchunk0_s4-WinGDK.pak   <- the Hebrew *.ufont
```

* `repak pack --version V11 --mount-point ../../../`
* Backups are **339 bytes each** (`work/stub_backups/`); the chunks' `.ucas`/`.utoc` are
  never touched. `deploy()` REFUSES to overwrite any pak whose entry count is not 0, so it
  can never destroy real content.
* Activation: **none**. `en` is `CulturesToStage[0]` and the game's default culture.

```bash
.venv/Scripts/python.exe games/corsair_cove/work/build_menu_proof.py --deploy
.venv/Scripts/python.exe games/corsair_cove/work/build_menu_proof.py --revert
.venv/Scripts/python.exe games/corsair_cove/work/build_menu_proof.py --status
```

The builder always rebuilds from the **pristine** extract, never from what is deployed,
and self-verifies by unpacking the pak it just wrote and re-reading the locres out of it.

## The Phase-1 proof — ✅ PASSED IN-GAME (2026-08-02)

Three shipped stubs, one screen. Every proof row is pinned to a menu item read off a real
screenshot (round 2's marker sat on `NewGame`, which this game's menu does not even have --
**pin proof strings to rows you have SEEN**).

| menu row | key | stored | rendered | gate |
|---|---|---|---|---|
| Resume | `ST_Options/Menu_Resume` | `ZZ-S2-LOCRES-ZZ` | ✅ shown | MOUNT + locres surface |
| Story Mode | `ST_Options/StoryMode` | `שלום` LOGICAL | ✅ readable | **bidi = LOGICAL** |
| Uncharted Mode | `ST_Options/FreePlay` | `םולש` VISUAL | mirrored | VISUAL is wrong |
| Load | `ST_Options/Menu_Load` *(CSV pak only)* | `ZZ-S3-CSV-ZZ` | ✅ shown | the CSV is a live 2nd surface |
| Settings | `ST_Options/Menu_Settings` | `אבגד` | ✅ correct | direction control |
| Credits | `ST_Options/Credits` | all 27 letters | ✅ **zero tofu** | glyph coverage |
| Quit | `ST_HUD/Quit` | `1 שלום` | ✅ correct | digit placement |

### Round 4 — the LONG-paragraph gate, on the Graphics description panel

| gate | result |
|---|---|
| WRAP (330 chars over 4 lines) | ✅ line order + every paren/digit/quote/Latin island correct |
| LINE ORDER (explicit `
`) | ✅ line 1 above line 2 |
| BASE DIRECTION (opens with `AMD FSR 2.2`) | 🔴 LTR base → left-aligned → **fixed by a leading RLM** |

**🔴 THE RULE THAT COSTS NOTHING TO GET RIGHT AND BREAKS THOUSANDS OF LINES IF MISSED:**
the UBA takes the paragraph base from the FIRST STRONG character, so a Hebrew line opening
with a brand / a number / a runtime-substituted `{VAR}` left-aligns with its punctuation on
the wrong side. `cc_rtl.to_logical` prepends **U+200F** to every line containing Hebrew
(pure-Latin strings are left alone). `cc_font._add_empty_controls` gives U+200E/200F/202A-E
a zero-width, zero-contour glyph so the mark can never render as tofu.

Still open (cosmetic only): font size/weight calibration against the shipped Latin.

## Phase 2 (after the proof)

1. Delegate the **11,914** unique strings ([[delegate-all-translation]] — a single pass,
   no fleet), feeding each line: `Context` (99.8 % coverage), Speaker/Addressee, the
   normalised gender, the scene ordering, and the **11-language New-Era panel**.
2. Key the community `/translate` pool by **`<namespace>|<key>`** — never by the English
   string (measured: fr 14.8 % of duplicate-English groups diverge).
   Order by visibility: UI/content (8,403) → VO dialogue (3,506).
3. Build via **`cc_rtl.to_logical`** (CONFIRMED: store natural Hebrew, never pre-reverse)
   → `cc_locres.save` → `repak pack V11` → the `pakchunk0_s2` stub.
4. Calibrate the font size/weight against the shipped Latin (`hebrew-font-calibration`).
5. Publish only on an explicit "פרסם".
