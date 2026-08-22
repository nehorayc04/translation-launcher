# Forza Horizon 6 — FEASIBILITY

## Verdict: 🟢 **GO** — every gate closed offline, one launch left

The install was repaired to **v403.798** (2026-07-27) and **all 27 critical files
now xxh128-MATCH** the game's own manifest: `forzahorizon6.exe`,
`media\UI\Fonts.zip`, `media\ObjectModelGame.zip` and all 24 language zips.
Only 700 files are missing and every one of them is per-language audio — a
deliberate English-only install.

| # | Gate | Status |
|---|---|---|
| 0 | RTL locale available? | 🔴 **No** — 24 languages, none RTL → LTR-slot hijack |
| 1 | Container | 🟢 **SOLVED** — plain ZIP + a 4 KB alignment convention; writer's no-op rebuild is byte-identical |
| 2 | Text format | 🟢 **SOLVED** — `.str` codec, surgical `edit()`, **287/287 byte-identical round-trip** |
| 3 | Deploy mechanism | 🟢 **SOLVED** — replace one language zip (**`EN.zip`**); backed up + hash-guarded + reversible |
| 4 | Activation | 🟢 **SOLVED — ZERO user actions**: English is the default. `GB.zip` ("English UK", only 12.6 % from EN) is the untouched escape hatch |
| 5 | Scope + oracle panel | 🟢 **MEASURED** — 37,099 lines; 22 reference languages at ~100 % id parity |
| 6 | bidi mode | 🟢 **SOLVED = VISUAL** — confirmed in-game 2026-07-27 by an A/B pair on one screen |
| 7 | Font | 🟢 **SOLVED + INJECTED** — `.vfont`/`.vfontN` decoded (a VECTOR MESH) and 27/27 Hebrew emitted into `Horizon_RU_A/C/D`, which the `lang="*"` fallback chain routes every UI face into |
| 8 | In-game proof | 🟢 **PASSED** — mount + text-reaches-renderer + bidi all confirmed; only glyphs missing |

## Scope (from the xxh128-verified pristine EN.zip)

| | |
|---|---|
| tables | 287 |
| records `(table,id)` | **58,179** |
| per-table unique values | 43,173 |
| **GLOBAL unique values** | **37,488** |
| ...real prose (token/number/code-only dropped) | **37,099** |
| characters (global unique) | 1,930,251 |

Length: median 22 · p90 118 · p99 422 · max 995 → `<=25` 20,703 · `26-140` 13,421 · `>140` 2,975.

Surface split by the engine's own table names: **UI / content 31,094** ·
**dialogue-VO 11,474**. Biggest tables: `ChallengeData` 4,487, `Dialogue` 3,501,
`ChallengeStatObjective` 1,753, `Dialogue_Gameplay` 1,697, `PlayerNames` 1,692,
`Dialogue_DJs` 1,667.

**Single fleet-sized pass** — comparable to Uncharted LoT (36.6 k), well under
Witcher 3 / Skyrim.

## Tokens that must survive verbatim

| token | occurrences | distinct | examples |
|---|---:|---:|---|
| `{0}` positional | 1,405 | 8 | `{0}` `{1}` `{2}` |
| `[TOKEN]` | 1,108 | 486 | `[PLAYERICON]` `[MC]` `[GAMERTAG]` **`[HIGHLIGHT:{0}]`** `[Alt:…]` `[SMALL:…]` |
| `<tag>` | 583 | 277 | `<PLACEHOLDER>` `<Hi>` |
| real newline | 825 | 1 | `\n` |
| printf | 20 | 10 | `%s` — rare |
| `&entity;` | 0 | — | none |

⚠️ **`[HIGHLIGHT:{0}]` nests a `{0}` inside a `[...]`** — the token regex must be
longest-first or the brace match will split it. `tools/fh6_rtl.py` already is.

## The font gate — MAPPED (2026-07-27)

### `.vfont` format, solved exactly

`tools/fh6_font.py`. Solved arithmetically from four fonts and then verified with
**zero slack on all 21 shipped descriptors**:

```
len == 204 + 8*pageCount + 36*glyphCount + 12*kernCount
```

* `char[128]` name · `u32` version(2) · `u32` 4 · **`u16 glyphCount, u16 kernCount, u16 pageCount, u16 pageCount`** at `0x80` · metrics floats → 204 B header
* page table `8 B × pages`, glyph table `36 B × glyphs`, kern table `12 B × kerns`
* glyph record: `f32` bearing · `u16 w, u16 h` · **`u32` byte-offset into the `.vfontN` page** · `0xFFFFFFFF` sentinel · **`u32` CODEPOINT @ +0x18** · 2 advance floats
* the codepoint table is **sorted ascending and ends at U+FFFD**, followed by a
  short alias tail — so a naive "is it sorted" check says False; test the prefix.

### Coverage — measured, not assumed

**0/27 Hebrew (U+05D0–05EA) in every single family.** `Horizon_A/B/C/D` carry 242
glyphs (ASCII + Latin-1 + punctuation + a few maths symbols), the `_tf` tabular
variants 21 (digits only), `Horizon_RU_A/C/D` **440** (= 242 + 66 Cyrillic + …),
and the CJK families 1,650–3,299.

### 🔑 The injection target — `Horizon_RU_A/C/D`, and NO config edit

`fontsettings.xml` declares an explicit **`fallback=` chain per language**, and the
catch-all `lang="*"` block (which is what GB, EN, DE, FR … resolve to) already
loads 15 fonts including the RU family:

```
Horizon_A → Horizon_RU_A → Horizon_KO → Horizon_JP → Horizon_CHS → Horizon_CHT
Horizon_C → Horizon_RU_C → …          Horizon_D → Horizon_RU_D → …
```

So a codepoint `Horizon_A` lacks is looked up in `Horizon_RU_A` automatically.
⇒ **inject Hebrew into the three `Horizon_RU_*` files only** (not into eight Latin
fonts), and `fontsettings.xml` needs no change at all. This mirrors exactly what
Playground themselves did for Cyrillic — extend the *fallback* font, 440 vs 242
glyphs, rather than grow the primary. The precedent is inside the game.

### 🔑🔑 `.vfontN` SOLVED — it is a VECTOR MESH, not a pixel atlas

The "compressed atlas / SDF / custom RLE" guess above was **wrong**, and the
correction is the best news of the whole project. `.vfontN` stores, per glyph, a
**triangulated outline**:

    u32 sentinel
    per glyph, in glyph order:
        u32 vertexCount
        u32 indexCount
        vertex[vertexCount]     8 B each
        u32 codepoint           <- terminator

**`payload == 8*vertexCount + 2*indexCount`, verified on 2,487 glyphs with ZERO
exceptions** — so the record's `+0x04`/`+0x06` u16 pair is *vertexCount /
indexCount*, NOT a width and height as first assumed.

Vertex = **4 × fp16 `(x, y, cu, cv)`**. `x, y` are normalised em coordinates;
`cu, cv` are shader curve/AA parameters — **exactly 0 across all of `H`** (straight
edges only) and large on `O` (curves), in ± pairs straddling each edge. Indices are
a plain u16 triangle list.

**PROVEN BY RENDERING**: decoding the meshes and rasterising the triangles produces
readable letterforms — `extract/mesh_render.png` shows **H O A 1 Z W**, correct
counters and all. That single image settles the format beyond argument.

Why this is a much better position than a bitmap atlas:

* **no rasterisation, no SDF constants to fit, no atlas packing or page-size cap**
  — all the expensive machinery of the GoWR / Plague Tale / 007 font jobs is moot;
* Hebrew injection becomes *outline → flatten → triangulate → emit*, which is a
  solved problem with fontTools + ear clipping;
* it also explains why FH6 text stays crisp at any size.

**Remaining unknown: only `cu, cv`.** They matter for analytic anti-aliasing, not
for geometry. The pragmatic first build emits flattened polygons with `cu=cv=0`
(the state `H`'s straight edges already use for `cu`) and lets the proof say
whether that renders acceptably.

⚠️ `Horizon_CHS`, `Horizon_CHT` and `Horizon_KO` store something else at `+0x18`
(their "codepoints" decode as f32 bit patterns), so their cp tables are not
authoritative. **Every family this project touches — `Horizon_A/B/C/D` and
`Horizon_RU_A/C/D` — is clean** (0 out-of-range codepoints), so this is a curiosity,
not a blocker.

## What the user must do

**Launch → Settings → Language** → screenshot the language list.

The mod sits in the **EN ("English US")** slot, so if the game is already on
English it is live with **zero actions**. Every bidi/layout probe is on that one
screen, labelled by a leading DIGIT (which renders through total tofu):
**odd digit = stored LOGICAL, even digit = stored VISUAL**, so the row whose digit
sits on the RIGHT names the correct storage mode.

`GB` ("English UK") is left pristine as the way back to English.

## The one screenshot answers all of this at once

| what you will see | what it proves |
|---|---|
| `ZZ-FH6-OK-ZZ` on the button prompts | the patched zip **mounts** (Latin — independent of the font) |
| the right **number** of boxes per row | the text reaches the renderer; only glyphs are missing |
| the digit on the RIGHT of an **odd**-numbered row | engine runs bidi → store **LOGICAL** |
| the digit on the RIGHT of an **even**-numbered row | engine runs none → store **VISUAL** |
| rows 3 / 4 (quotes, parens, `Forza Horizon 6`) | punctuation + Latin-island placement |
| the 27-letter row rendering as letters | the font covers Hebrew (it does not — 0/27 measured) |

## RESULT — the proof PASSED (2026-07-27)

**Round 1 (GB slot):** `ZZ-FH6-OK-ZZ` rendered ⇒ **mount ✅**; `Esc` showed exactly
4 boxes for `שלום` and the language row exactly 5 for `עברית` ⇒ **the text reaches
the renderer**; everything Hebrew was tofu ⇒ **font ✗**, exactly as the 0/27
measurement predicted. bidi was NOT settled — those rows carry no digit or
punctuation, so they hold no ordering information.

**Round 2 (EN slot, all probes on the language list): ✅✅ bidi = VISUAL, and it is
not a judgement call — EIGHT rows agree unanimously.**

| rows | stored | digit rendered | verdict |
|---|---|---|---|
| 1, 3, 5, 7, 9 | LOGICAL | **LEFT** | wrong |
| **2, 4, 6, 8** | **VISUAL** | **RIGHT** | **correct** |

The decisive row is **4** (the full sentence, stored VISUAL). It rendered
byte-for-byte as stored — `!▯▯▯ .Forza Horizon 6 ,▯"▯▯ 240 — (5 ▯▯▯▯ 3) "▯▯▯▯▯▯" :▯▯▯▯▯▯ 4`
— which read right-to-left reconstructs the original sentence exactly, Latin island
forward, `240` in place, final `.` and `!` at the correct end. Row 3 (the identical
sentence stored LOGICAL) also rendered exactly as stored, i.e. unreadable RTL.

⇒ **the engine draws in STORAGE ORDER and performs no bidi at all**, precisely as the
XAML predicted (`FlowDirection` is never anything but `LeftToRight`).
**`fh6_rtl.to_visual` is validated end-to-end in the live game.**

⚠️ The `(` / `)` look "inverted" to a Hebrew reader — that is **correct** and must
NOT be "fixed": it is exactly what the professionally-shipped Arabic does on this
class of engine (see the RDR2 note in the Playbook, §8b rule 0).

The 27-letter row rendered as exactly **27 boxes** — a visual confirmation of the
`0/27` coverage measured offline.

## Risks

* **Font** — CLOSED. 27/27 Hebrew glyphs render in-game in all three target
  faces, with an analytic AA band matching the game's own edge quality (see
  below) — the only remaining step is the user's in-game screenshot confirming
  the graininess complaint is resolved.
* **Content integrity** — no evidence of a runtime hash check, but unverifiable
  without the exe. If a modified `EN.zip` is rejected, revert is one command.
* **Game updates** rewrite these zips (`Update.AlignmentChunk`, `Game.ChunkMeta`);
  the deploy records the deployed hash and **refuses to revert onto a changed file**.
* **Live-service text** — leaderboards, the Festival Playlist and store copy may be
  served online and stay English regardless of the local tables.


## 🔴 The `.vfont` declares its own page size — in a TRAILER (2026-07-27)

The last `4 + 8*pageCount` bytes of every `.vfont` are the REAL page table:

    u32 slotCount
    per page:  u32 pageByteSize,  u32 glyphsInPage

Every declared size equals the true `.vfontN` length on every shipped font,
Horizon_CHS's 15 pages and Horizon_JP's 10 included. **The engine trusts it over
the actual file**, so leaving it stale truncates the page:

| glyph | block end | vs the STALE declared 516,340 | on screen |
|---|---:|---|---|
| ר | 514,488 | under | perfect |
| **ש** | 517,116 | **straddles** | half a letter |
| **ת** | 519,920 | **past** | garbage |

Letters breaking by POSITION in the injected run — on a file that parses perfectly
— is the signature. The field was found by scanning the container for a u32 equal
to the page length, after an engine-side cap, a u16 vertex-index limit (the page
holds 46,864 of a possible 65,536) and a ZIP header mismatch had each been
measured and cleared.

Two structural errors came with it, both of which cancel out only when
`pageCount == 1`: the 8-byte block after the header is NOT a per-page table
(RU_C and RU_D have identical records there, pages 20 KB apart), and the glyph
region has no 12-byte "suffix" — those bytes were the trailer. Together they made
every multi-page CJK font decode as garbage, which went unnoticed because the
selftest skipped them. Corrected model, exact on all 20 fonts:

    204 + 8 + [24 + 36*N] + 12*kernCount + [4 + 8*pageCount],  slotCount == N+1

`serialize(page_sizes)` regenerates the trailer, the identity round-trip proves it
reproduces the shipped bytes, and `validate()` refuses to deploy unless the trailer
describes the page actually written.

The 7 math operators (`∨∩∪∫∬∭∮`, 19,370 B) are still dropped for free headroom —
free, since `Horizon_JP` carries all seven and sits in this font's own fallback
chain — and the builder (`inject_fitting()`) picks the finest flattening
tolerance that fits within a `HEB_BUDGET` of bytes.

## 🔴🔴 The first font build was flat/opaque — no anti-aliasing at all (2026-07-27)

27/27 Hebrew rendered in-game, but the user reported the SAME "noise" complaint
seen in three earlier projects (AC2, God of War Ragnarök, A Plague Tale
Requiem) — with a DIFFERENT root cause, because this format is a vector mesh,
not a bitmap atlas. `fh6_glyphgen.mesh_for()` had only ever emitted the solid
interior (`cu=0, cv=1`), which is a valid, fully-opaque glyph but has NO
anti-aliasing vertices — every edge rasterizes hard, and a hard edge on a
small vector glyph reads exactly like graininess.

`fh6_font.py`'s own reverse-engineering had already measured the native
glyphs' AA mechanism: `cv=1.0` on the solid interior, `cv=±W/edgeLength` on a
miter-inset AA-band quad straddling every outline edge, `W = 0.0283 em`
(measured off the game's own 'H'). The fix reproduces it: `fill_side()` picks
ONE inset direction for the WHOLE glyph from its LARGEST contour (a per-contour
attempt inverted counters — ם/ס measured 18-20% off, because a hole's own
winding disagrees with the glyph's overall fill direction), `inset_polygon()`
miter-offsets every contour by `W` toward that side, and one AA quad per
outline edge gets `cv = ±W/L` at both corners.

Validated against an INDEPENDENT ground truth (`work/test_aa_band.py`):
simulates the shader's own analytic-AA formula (`alpha = cv/fwidth(cv) + 0.5`)
per triangle and compares the `cv>=0` region to a winding-number scanline
rasterizer of the TRUE outline — worst case **0.09%** area error (ת), median
**0.00%**, all 27 letters, confirmed visually in `extract/aa_band_check.png`.

The AA band roughly triples vertex/index counts, so the pages GROW now instead
of shrinking — safe only because the trailer bug above is fixed and every
build regenerates it from the real page length:

| font | page (pre-AA → +AA band) | coverage |
|---|---|---|
| Horizon_RU_A | 516,340 → 547,362 (+31,022 B) | 27/27 |
| Horizon_RU_C | 526,186 → 557,148 (+30,962 B) | 27/27 |
| Horizon_RU_D | 546,602 → 573,306 (+26,704 B) | 27/27 |

## מסמכים קשורים
- באותה תיקייה: [[games/forza_horizon6/PIPELINE|PIPELINE]], [[games/forza_horizon6/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#forza_horizon6|CLAUDE_INDEX_games]]
