# Ghost of Tsushima DC — FONT research + experiment plan (2026-07-27)

**The one unsolved gate:** Hebrew renders as tofu (▯). The menu/subtitle font is a
Sucker-Punch proprietary **compressed vector font**; it covers Arabic but has zero Hebrew
outlines. Container + text codec + in-place deploy + bidi are all PROVEN; the font is the
sole blocker.

---

## VERDICT: **RESEARCH-GRADE** (a real path exists; it is a multi-session RE + font-authoring
project; there is no shortcut and no community crack to borrow).

Not DEAD — two concrete, un-exhausted paths remain (empirical bisection → Rosetta →
recombination; and a RenderDoc GPU-vertex capture as a cleaner Rosetta). Not LIKELY — every
angle that could have made it cheap is now closed with evidence: **no bitmap-atlas escape, no
OS/system-font fallback, no community tool that adds a non-shipped glyph, and the on-disk
coordinate codec is statically ambiguous with no locatable known-glyph.** Getting shippable
Hebrew realistically costs **~8-14 game launches** to crack the encoding, then a font-authoring
sub-project.

---

## 1. PRIOR ART — the decisive result: **NO localization or tool has ever added a non-shipped
glyph to this engine. Every working GoT translation hijacks a script the font ALREADY covers.**

This is the single most important finding, and it kills the hope that the reported Persian
localization cracked the font.

### Why the commercial Persian/Farsi RTL localization "works" — it needs ZERO font work
The shipped `ghost_title.xpps` cmap was censused (`extract/ghost_title.xpps`, 4,299 distinct
codepoints). **The Persian-only letters — which do not exist in Arabic — have their own
distinct, well-formed glyph records, structurally identical to the rendering Arabic letters:**

| glyph | codepoint | face | ref | cnt | vs Arabic baseline |
|---|---|---|---|---|---|
| پ (peh) | U+067E | 140 | 1770 | 1 | same shape as ا/ب (face 129, ref 1680) |
| چ (cheh) | U+0686 | 140 | 1783 | 0 | same shape as ج (face 129, ref 1690, cnt 0) |
| ژ (jeh) | U+0698 | 145 | 1800 | 6 | — |
| گ (gaf) | U+06AF | 155 | 1825 | 0 | — |
| ک (keheh) | U+06A9 | 154 | 1800 | 3 | — |
| ی (farsi yeh) | U+06CC | 168 | 1849 | 1 | — |
| ڑ (urdu rreh) | U+0691 | 144 | 1791 | 2 | — |
| ۀ (heh+hamza) | U+06C0 | 165 | 1754 | 5 | — |

The Arabic-script faces span **129–168** and the 0x600 block has **250 records** with real
varied geometry (SIZE field up to 900). **Sucker Punch shipped full Arabic + Persian + Urdu
coverage.** So a Farsi localization = the identical Arabic-slot text hijack we already use
(set Text/Subtitles = Arabic, drop a repacked `lang_arabic_text.xpps`) — the font is untouched.

The Iranian-market sellers confirm the mechanism verbatim (install step: **"change text +
subtitle language to Arabic, then run the installer"** — the Arabic-slot hijack) and one
advertises "translates all menus and UI to Persian **with an optimal font**" — i.e. the
shipped font already renders Persian. Sources (Persian storefronts, subtitle-only or
Arabic-slot text): hajgame.ir, elaymedia.ir, gamesub.net, avaltechno.ir, virgool.io/@farsisaz.
None ship or modify `gapack_misc_g` / the font; none expose font tooling.

### The other communities — same story, all use covered scripts
- **Nexus #807** "Austronesian Lang Pack" (Bahasa Indonesia / Melayu / Filipino): injects
  **Latin** text into the **Greek** language slot (Greek's `.xpps` has "the most generous byte
  allocation"). Latin glyphs already ship → no font edit. Ships an additive
  `gapack_misc_z<lang>.psarc`.
- **Nexus #809** "GoT Translation Tool": a **hex-editor for `.xpps` TEXT** (locate/map strings).
  Explicitly text-only; the community itself states **"editing .xpps for proper translations
  requires repacking, which is currently not possible"** and pointer-moves "crash / cut off."
- **GoTExtractor (Glumboi, MIT)** — a PSARC/XPPS repacker built on UnPSARC. Confirmed via its
  GitHub README: **"a GoT game file repacker/extractor using UnPSARC"** — zero font/glyph/fOnk
  handling.
- **Chinese / Korean / Thai / Turkish / Arabic / Russian searches** (incl. CJK/폰트 terms):
  no font/glyph mod exists. CJK is impossible via the shipped font anyway — the `.msac` texture
  files are ~87 KB regardless of language (a CJK atlas can't fit), and CJK codepoints are
  **absent from the cmap** (U+3042/U+4E00/U+AC00 → ABSENT).
- **ResHax PSARC thread** (from prior sessions): archive tools only; a user asking to swap
  Arabic→Persian got **no technical answer**; the font format "**remains undocumented.**"
- **Sibling-title transfer is impossible:** the Sprig engine's other titles (inFAMOUS Second
  Son/First Light, Sly Cooper) are **PS4/PS3-only** — no PC build to borrow a parser or a
  cracked font from. The Nixxes GoT PC port is the only PC Sprig title.

**Conclusion: Hebrew is genuinely, uniquely unsupported. There is no prior-art shortcut — the
tag `fOnk`/`SFontData`/`FontVerts` has zero hits anywhere on the internet, and no glyph has ever
been added to this font by anyone.**

---

## 2. NEW architectural findings this session (they reshape the problem)

### 2a. The font has TWO rendering strategies, split by the record's `+18 cnt` field
Censusing every 64-byte cmap record (`+20==0xF8`, `+62==0xFFFF`):

| strategy | `cnt` | scripts | mechanism |
|---|---|---|---|
| **resolve-by-CP** | `0xFFFF` | Latin (face 4), Cyrillic (23), Greek (20/22), Thai (573) | glyph chosen by codepoint against a face; **no per-glyph vector block** |
| **per-glyph vector block** | small int | Arabic/Persian/Urdu (129–168), **Hebrew (104)** | outline = a block in the vector store |

Hebrew sits in the **vector-block** system (face 104, ref 1522) but its blocks are notdef → tofu.

### 2b. The "cheap bitmap-atlas escape" is DEAD — the font is 100% vector
I tested whether the resolve-by-CP faces render from a bitmap atlas (the SM2/WD2/GoWR-style
cheap path). **They do not:**
- `game.sprig.texmeshman` (108 MB): **0 DDS textures**, exactly **1 `fOnk` chunk**.
- The `.sps` font/legend files (`debugfont`, `lang_arabic.msac`, `lang_japanese.msac`): **not
  even DDS** (proprietary `XTBS` header), all ~87 KB — button-legend images, not glyph sheets.
- No sfnt/TTF/OTF anywhere (confirmed across 6 prior sessions).

So there is **no bitmap to extend** — even the resolve-by-CP scripts are vector. The only
encodings in the game are the two proprietary vector stores below.

### 2c. Two font resources — the analyzed one IS the menu font
- **`ghost_title.xpps`** (10,103,200 B, in `gapack_misc_g.psarc`) — **the Arabic-slot menu/title
  font.** Per `notes/arabic_font_table.md`: "when Text=Arabic, the title/menu renders from
  ghost_title's per-script sub-tables." Its vector store (`tail-kind2` @0x97c8d0) is
  **~48.9% clean-f32** — partially readable, and the correct injection target. **All prior
  `tail-kind2`/cmap work targeted this correct file.**
- **`fOnk` in `game.sprig.texmeshman`** (also `gapack_misc_g`) — a second font resource,
  **fully compressed (7.48 bits/byte)**, harder. Likely the subtitle/HUD face. Secondary target.

### 2d. The `SIZE` geom field is NOT a notdef discriminator (corrects a prior note)
The notes claimed "SIZE=5 = notdef." False: rendering Arabic has SIZE ∈ {0, 5, 10, 50}; Cyrillic
maxes at 20. SIZE cannot be used to detect a broken glyph — only the in-game pixel can.

### 2e. The memory dumps in `work/_glyph_*.bin` are NOT a Rosetta
The latest session dumped runtime "glyph objects." Re-analyzed: they are **C++ object headers +
pointer arrays** (`{u64 0, u64 ptr}` pairs stepping +0x18 into other heaps), not decoded
geometry. The "87% floats in range" reading is the tautological-range trap the notes warn about
(mostly zero bytes). **No Rosetta pair is obtainable from the existing dumps.** (Consistent with
the proven fact that the runtime is a relocated multi-heap object graph, not flat coordinates.)

---

## 3. RANKED EXPERIMENT PLAN (feasibility × impact), with explicit game-launch counts

The deploy rig is proven (`work/got_dsar.py patch_inner` = ~1 s in-place edit; boot→menu ~11 s
with `ShowLauncher=0`; `work/got_cap.py` = RUNASINVOKER launch + dxcam screenshot). Baseline for
every experiment: revert both gapacks to pristine, set `TextLanguage=21` (Arabic) so the menu
shows the game's own Arabic glyphs (the known-good reference).

### PATH A — Empirical bisection → Rosetta → author by recombination  ★ TOP PICK, ~8-14 launches
This is the highest feasibility × impact: it needs **no codec theory, no debugger, no live
memory** — only screenshots of edits, and the file bytes ARE consumed at load (proven: edits
crash or change the screen). It manufactures the Rosetta that every static attack has lacked.

**Why it can work now:** the 2026-07-22 session PROVED a surgical clean-f32 edit of `tail-kind2`
**survives and boots to a clean Arabic menu** (no per-block checksum). The only reason it saw
"no visible change" was that it edited block-0, which isn't a menu glyph. The bisection finds a
block that IS a menu glyph.

**Step A0 — go/no-go that `tail-kind2` drives the menu (2 launches).**
Split the clean-f32 vertex pool (~76 KB ≈ 19,000 floats) into **8 coarse regions**. In ONE
build, mutate **4 disjoint regions** with **4 visually-distinct, same-size transforms** so one
screenshot distinguishes all four:
- Region A: `x,y *= 3.0` (glyph explodes/oversizes)
- Region B: `x += 0.6` (glyph shears/shifts right)
- Region C: `x,y *= 0.1` (glyph collapses to a dot)
- Region D: `y = -y` (glyph flips vertically)

Only touch CLEAN-f32 runs; **skip every `0x74XX74XX` pack-run** (editing those crashed at load —
2026-07-22). Two builds cover all 8 regions.
- **If ANY menu glyph visibly distorts** → `tail-kind2` drives the menu; proceed to A1.
- **If NOTHING in the menu ever changes** → the menu renders from the compressed `fOnk`
  (§2c), not `ghost_title.xpps`; abandon this file and retarget the `fOnk` (much harder — it's
  compressed; realistically needs Path C first). This 2-launch test is a decisive fork.

**Step A1 — binary-search to one glyph's bytes (~4-6 launches).**
Take the coarse region that distorted a KNOWN menu glyph (e.g. the ا in لعبة). Subdivide it into
4 sub-regions per build, each with a distinct transform; the sub-region whose transform hits the
target glyph is the next parent. Each build is a 4-way split ⇒ ~2 bits/launch. Narrowing
~2,400 floats → the exact ~10-30-float glyph block ≈ **4-6 launches**.

**Step A2 — read the encoding off the known glyph (~1-2 launches).**
With a known simple glyph (ا alef = one near-vertical stroke) pinned to its ~10-30 floats, the
f32-vs-s16 ambiguity collapses — you can SEE a vertical stroke in the numbers. Confirm the
pack-run/topology meaning by perturbing single coords and watching the shape (1-2 launches).
**Output: the coordinate codec + the `+16/cnt → tail-offset` mapping = the Rosetta.**

**Step A3 — author 27 Hebrew glyphs by RECOMBINATION (offline + a few verification launches).**
Do NOT try to author outlines from scratch. Hebrew letters decompose into strokes that already
exist in the shipped Arabic/Latin glyphs (vertical from ا, horizontal bars, corners). Once A2
reveals (a) which byte-run draws a stroke and (b) how the `x += k` transform moves it, **compose
each Hebrew letter by copying + translating known stroke-runs** — no full codec synthesis needed.
Handle store growth via append + the record's `cnt`/offset fields, and wire the 27 Hebrew records
to the new blocks (⚠️ editing a record's `+16/+18` crashed cross-face historically — keep the
edits WITHIN face 104, which owns the Hebrew records). Budget verification launches per letter
batch; the whole authoring pass is offline between launches.

**Total to shippable-Hebrew via A: ~8-14 launches** (2 go/no-go + 4-6 bisect + 1-2 decode +
a handful to verify the authored letters).

### PATH B — RenderDoc GPU-vertex capture (a cleaner Rosetta, ~1-2 launches + install)  ★ 2nd
The single cleanest anchor: capture the Arabic menu frame in **RenderDoc** and read the
tessellator's OUTPUT vertex buffer for a known glyph → known-glyph→GPU-verts, then correlate to
its on-disk `tail-kind2` block. This replaces A0-A2's bisection with one purpose-built capture.
- **Feasibility just improved:** the 2026-07-22 correction proved **`GhostOfTsushima.exe` is a
  plain PE, NOT VMProtect-packed** (only the in-memory header is erased). RenderDoc has a good
  chance of attaching. Launch with `ShowLauncher=0` + RUNASINVOKER.
- Cost: RenderDoc install + ~1-2 launches to capture. If it attaches, it is faster and more
  certain than the blind bisection; if anti-tamper blocks the D3D12 layer, fall back to Path A.
- Correlating GPU-verts (post-transform, screen-space) back to on-disk (pre-transform, glyph
  space) still needs the store located — so run **A0 (2 launches) first** to confirm the file,
  then use RenderDoc to shortcut A1/A2.

### PATH C — Crack the compressed `fOnk` codec (fallback, research-grade, many launches)  ★ last
Only if A0 proves the menu renders from the `fOnk`, not `ghost_title.xpps`. The `fOnk` chunk is
compressed (7.48 bits/byte) with LZ-style back-refs and no `oo2core` in the game → an unknown
Sucker-Punch codec that must be decompressed BEFORE any vector work. This is the hardest gate in
the project; pursue only after A0 forces it.

### Explicitly DE-PRIORITIZED (evidence they are dead — do not spend launches)
- **Live-debug / watchpoint / x64dbg content anchor:** the runtime is fully transformed at load
  (two full-memory scans → 0 verbatim matches for a 20-float run AND a 64-byte cmap sig). No
  content address to arm. The font-string code anchors (GENERATE_QUAD/FONT_KIND) are **reflection
  registration**, not the tessellator (disassembled 2026-07-22). A code-breakpoint on the real
  tessellator has **no locatable anchor**. 0 launches — ruled out.
- **`@0x8b0000` store edits:** inert to rendering (disproven twice in-game). 0 launches.
- **Bitmap-atlas / OS-fallback / TTF-swap:** no atlas (§2b), no DirectWrite/GDI in the in-game
  renderer (GDI is launcher-only), no embedded sfnt. 0 launches.
- **Sibling-title parser transfer:** no PC Sprig sibling exists. 0 launches.

---

## 4. What was ruled OUT, with evidence

| Ruled out | Evidence |
|---|---|
| Any community font crack / tool | `fOnk`/`SFontData`/`FontVerts` = 0 internet hits; ResHax "format undocumented"; #809 = text hex-editor; GoTExtractor = PSARC/text repacker; format uncracked by all non-Latin communities |
| Persian loc proves a codec crack | FALSE — Persian glyphs SHIP (distinct face/ref records, structurally identical to rendering Arabic); Persian loc = Arabic-slot text hijack, font untouched |
| Bitmap-atlas escape | 0 DDS in texmeshman; `.sps` are 87 KB legend images, not glyph sheets; no sfnt anywhere; the font is 100% vector |
| OS/system-font fallback | GDI/DirectWrite is launcher-only; in-game renderer has no font-linking; `debugfont.dds` is dev-only |
| Live-debug Rosetta | runtime fully transformed (0 verbatim matches, ×2 scans); the existing `_glyph_*.bin` dumps are object headers, not geometry |
| exe code-anchor to the decoder | GENERATE_QUAD/FONT_KIND xrefs are reflection/schema registration; no `lea`→FontVerts/SFontData; tessellator has no string anchor |
| `@0x8b0000` = outline store | editing it changes nothing on screen (disproven ×2 in-game) |
| CJK via shipped font | CJK codepoints absent from cmap; `.msac` textures too small for a CJK atlas |
| Sibling-title transfer | inFAMOUS/Sly are PS3/PS4-only; no PC Sprig binary to borrow from |

---

## 5. The single most valuable next action
Run **Path A / Step A0 (2 game launches)**: 8 coarse regions, 4 distinct transforms per build,
one screenshot per build. It is decisive two ways at once — it either (a) confirms
`ghost_title.xpps`'s `tail-kind2` drives the visible menu and hands you the first coarse
localization of a real glyph (→ proceed to bisection), or (b) proves the menu renders from the
compressed `fOnk` and redirects the whole effort. Either way, 2 launches remove the biggest
current uncertainty. In parallel, install **RenderDoc** and confirm it attaches to the (plain-PE)
exe — if it does, it likely collapses A1/A2 into a single capture.

**Reusable rig already built:** `work/got_dsar.py` (patch_inner), `work/got_cap.py`
(launch/shot), the clean-f32 run-detector + surgical-edit differential rig from the 2026-07-22
session. Baseline = revert both gapacks, `TextLanguage=21`.

## מסמכים קשורים
- באותה תיקייה: [[games/ghost_of_tsushima/FEASIBILITY|FEASIBILITY]], [[games/ghost_of_tsushima/PIPELINE|PIPELINE]], [[games/ghost_of_tsushima/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ghost_of_tsushima|CLAUDE_INDEX_games]]
