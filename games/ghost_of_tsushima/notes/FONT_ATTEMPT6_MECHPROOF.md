# GoT DC font — round 6: the +14/+16/+18 contradiction RESOLVED (static) + a deployable mech-proof (2026-07-08)

**HEADLINE: the round-2 vs attempt-#5 contradiction is resolved by measuring the REAL records — and
BOTH were partly right. `(+14,+16,+18)` is a SHARED SENTINEL for Latin (attempt-#5's "cmap" evidence),
but PER-GLYPH-DISTINCT for Arabic (round-2's "outline ref"), and DEGENERATE for Hebrew. attempt-#5's
"nonzero `geom` -> notdef box -> tofu" theory is REFUTED. A same-size, gold-validated mechanism-proof
archive is built and ready for the human to deploy; one in-game look confirms causality.** All facts run
with the repo `.venv` python against the real `gapack_misc_g.psarc` / cached `ghost_title.xpps` (10,103,200 B).
Tools: `work/analyze_font_refs.py`, `work/analyze_inner_blocks.py`, `work/build_font_mechproof.py`,
`work/validate_mechproof.py`.

## 1. The measured resolution (`analyze_font_refs.py`)
| block | (+14,+16,+18) | distinct/N | geom | renders in-game? |
|---|---|---|---|---|
| Latin A..Z | (4, 39, 0xffff) — IDENTICAL | 1 / 26 | 0,0,0 | YES |
| Hebrew 0x5d0..0x5ea | (104, 1522, {11,12,13}) | **3 / 27** | per-glyph [x,y,5.0] | NO (tofu) |
| Arabic letters (0x62a..) | per-glyph varied | 46 / 71, 23 / 31 | mixed (many nonzero) | YES |

- **attempt-#5 was right about Latin:** A/O/i differ in EXACTLY one byte (+0 cp); Latin shares the ref
  `(4,39,0xffff)` — a **sentinel** ("no explicit outline; render from the default/base set"). So for the
  LATIN sub-table the record is cmap-like and carries no per-glyph shape id.
- **round-2 was right about Arabic:** real Arabic letters carry **distinct** `(+14,+16,+18)` per glyph
  (a page/kind at +14 that increments 129,130,131.. + a region base at +16 + an index at +18).
- **Hebrew is DEGENERATE:** 27 letters share `(104,1522)` with only 3 `+18` values -> cannot address 27
  distinct outlines -> the tofu. (Contrast: Hebrew *points* 0x591-0x5c7 have ~35 distinct refs = authored.)
- **attempt-#5's geom theory is REFUTED:** Arabic 0x62a `geom=(364,-152,5.0)` ≈ Hebrew alef `(262,-348,5.0)`
  (same z=5.0), yet Arabic renders and Hebrew tofus. Many Arabic letters have nonzero geom and render fine.
  And Hebrew ALREADY has rich per-glyph geom yet still tofus -> **geom is NOT the shape source and NOT a
  notdef-box trigger; the discriminator is the ref.** This is strong static evidence for round-2.
- **The one thing static analysis CANNOT exclude:** the shapes could instead live in the external
  hash-keyed FontVerts store keyed by *codepoint* (not by the ref), in which case Hebrew tofus because the
  store has no Hebrew entries and the ref field is inert. That alternative is EXACTLY what the in-game
  mech-proof rules in or out.

## 2. Container facts re-verified (`analyze_inner_blocks.py`)
- `/ghost_title.xpps` extracted from `gapack_misc_g.psarc` == the cached 10,103,200 B blob (md5-equal path).
- `entry.offset (F) = 0x7280000`, block_start=1837, block_size=0x10000, 155 inner-PSARC blocks.
- The 27 Hebrew records `[0x87ec92, 0x87f352)` fall entirely inside inner-PSARC **block 135 = RAW** (full
  64 KB, uncompressed). All 135 preceding blocks are RAW -> the **identity map `inner_off = F + xpps_off`
  holds** (confirmed by reading the inner stream and comparing bytes). So a same-size surgical edit is legal,
  exactly like the proven `gapack_misc_l` in-place proof.

## 3. The mechanism-proof (`build_font_mechproof.py`) — SAME-SIZE, gold-validated
Overwrites ONLY bytes `[+14:+20]` (=(+14,+16,+18)) of each of the 27 Hebrew records with the same 6 bytes
from **27 DISTINCT real Arabic letter records** (0x641,0x621,0x622,...,0x678). cp (+0), geom, colour and the
+62 sentinel stay byte-identical; record count + file size unchanged. Then `got_dsar.patch_inner` re-LZ4s the
**1** DSAR chunk that overlaps the edit (of 7441) and copies the other 7440 verbatim.
- Edit footprint: **105 bytes** changed across all 27 records (some fields already matched), 54 inner runs, all
  inside RAW block 135. Output `gapack_misc_g_mechproof.psarc` = 1,513,947,984 B.
- **GOLD validation (`validate_mechproof.py`):** all 2205 inner files md5-compared original-vs-mechproof ->
  **exactly ONE differs (`/ghost_title.xpps`)**; inside it exactly the 27 records' `[+14,+20)` windows differ;
  cp ladder 0x5d0..0x5ea intact; 2204 files byte-identical; archive re-reads via `dsar.py`.
- `--fields full` variant also copies `geom (+22..+45)` — a fallback IF the ref-only proof tofus (to rule out
  a geom interaction). Default = `ref` (the task spec + the cleanest single test).

## 4. Deploy (human) + read
Deploy is IN-PLACE (adding a 2nd archive with a duplicate internal path crashes boot — proven; the
`gapack_misc_l` proof was also in-place). Back up then overwrite the shipping `gapack_misc_g.psarc`:
```
Copy-Item -Force "F:\Games\Ghost of Tsushima DC\cache_pc\psarc\gapack_misc_g.psarc" "F:\Games\Ghost of Tsushima DC\cache_pc\psarc\gapack_misc_g.psarc.he_backup"
Copy-Item -Force "<SCRATCH>\gapack_misc_g_mechproof.psarc" "F:\Games\Ghost of Tsushima DC\cache_pc\psarc\gapack_misc_g.psarc"
# launch -> Settings -> Options -> General -> Text Language = العربية
# REVERT: Copy-Item -Force "...gapack_misc_g.psarc.he_backup" "...gapack_misc_g.psarc"   (or Verify Integrity)
```
**LOOK at the menu Hebrew (New Game / Load Game / Options / Subtitles):**
- **Arabic letters appear (not tofu)** => `(+14,+16,+18)` IS the per-glyph outline reference; the record is
  editable to change the glyph. The ONLY remaining font work = synthesise 27 Hebrew outlines into the
  FontVerts store and repoint these 3 fields (round-2 CONFIRMED, attempt-#5's "inert cmap" refuted).
- **Still tofu** => the shape is keyed elsewhere (external hash store by codepoint). Try the deployed archive
  built with `--fields full`; if that also tofus, the record-editing path is dead and the outline store must
  be cracked (attempt-#5's blocker stands).
