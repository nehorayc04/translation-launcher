# Ghost of Tsushima DC (PC) — Phase-1 Precedent + RTL/bidi Research

Date: 2026-07-07. Engine: Sucker Punch proprietary (Nixxes PC port). Detection/games.id = `tsushima`.

## Q1 — Does the engine bidi-render Arabic (store LOGICAL) or draw raw bytes (bake VISUAL)?

**Verdict: LEANS LOGICAL — the engine almost certainly bidi-renders RTL — but NOT proven for Hebrew
specifically. Confidence: MEDIUM. The menu-proof must decide (test both), and FONT (Hebrew glyph coverage
in the Arabic-slot face) is the more probable blocker than bidi.**

Evidence FOR the engine doing real bidi + RTL:
1. **The official Arabic `.xpps` is stored in LOGICAL reading order** (natural Arabic, first Arabic run
   @0x457/1111; confirmed inline in the task context). If the engine drew raw byte order, the shipped
   Arabic would render reversed/broken. Sony ships GoT's Arabic as a polished first-party locale → the
   engine MUST reorder + shape at draw time. So RTL reordering + Arabic-script shaping exist in-engine.
2. **A commercial Persian (فارسی) localization of GoT PC exists** (farsisaz.com, gamesub.net, hajgame.ir,
   elaymedia.ir/PersianMaker #11104) covering "all subtitle and non-subtitle text" in the main game + Iki
   Island DLC. Persian is **RTL and NON-shipped** by GoT → someone hijacked a slot (Arabic-script) and it
   renders correctly RTL in-game. This is the closest working precedent to our Hebrew case for RTL.

The Witcher-3 caveat (why this is NOT a guarantee for Hebrew):
- Persian uses the **Arabic script** (same joining/shaping, same broad Unicode neighbourhood) → it rides the
  engine's Arabic pipeline directly. **Hebrew is a different block (U+0590–05FF), needs bidi-reorder but NO
  joining.** An engine that implements a proper Unicode Bidi Algorithm treats Hebrew and Arabic identically
  as strong-RTL → Hebrew would reorder for free (it only needs the easier half, no shaping). BUT a hand-rolled
  *Arabic-specific* reshaper (triggered by Arabic-script codepoints or by `language:"arabic"`) might NOT
  reorder Hebrew — exactly the Witcher 3 outcome (shipped Arabic logical+RLO, yet Hebrew needed VISUAL) and
  the GoWR outcome (engine honored bidi controls but the Hebrew codepoint range was gated out of a metric field).
  Sucker Punch is a **proprietary** engine (not Unreal/ICU), so treat it like W3/GoWR: do not assume.
- **FONT is the likelier blocker.** The Arabic-slot font is an Arabic/Latin face and probably lacks Hebrew
  glyphs → tofu even if bidi is correct (recurring gate: Hogwarts had coverage, GoWR/Plague Tale/TLOU did not).

**Action:** menu-proof stores ~6 Hebrew strings BOTH logical and pre-reversed (VISUAL) into `lang_arabic_text.xpps`;
one in-game screenshot resolves bidi + font at once (playbook pattern). Have a Hebrew glyph-inject/font-replace
fallback ready if tofu.

## Q2 — Existing GoT PC text mods proving edit+load (incl. non-shipped languages)?  YES — strong.

- **Nexus #807 "Bahasa Indonesia / Melayu / Filipino (Austronesian Lang Pack)"** — full fan translation into
  NON-shipped languages. Edits `lang_greek_text.xpps` (Greek chosen = most generous byte budget, LTR), ships as
  `gapack_misc_z<lang>.psarc` dropped into `<install>/cache_pc/psarc/`. Proves text edit → repack → load works.
- **Nexus #809 "GoT Translation Tool"** — a localization editor specifically for the `.xpps` files inside
  `gapack_misc_l.psarc`; workflow = extract with GoTExtractor → edit → repack.
- **Commercial Persian (RTL, non-shipped)** localization (multiple Iranian sites) — RTL edit+load precedent.
- **karyain.net** — Indonesian/Malay/Filipino subtitle project.

**Byte-length constraint (important for the writer):** community tools require **new text ≤ original byte
length** (padded if shorter, truncated if longer). This matches the KCAP near-EOF step-4 u32 array = a string
**offset table**; editing in place preserves offsets. To allow longer Hebrew we must properly REBUILD the
offset table + the 0x2c size/trailer fields — a Phase-2 writer improvement (our own psarc_write already exists;
the KCAP codec is the new piece).

## Q3 — Community tools for Sucker Punch / GoT PC formats

- **GoTExtractor** — Glumboi, C# (MIT), open source: https://github.com/Glumboi/GoTExtractor . Repacker/extractor
  built on **UnPSARC**. Also on Nexus #65.
- **UnPSARC (NoobInCoding), v2.2+** — full pack/unpack of GoT archives.
- **GoT Translation Tool** — Nexus #809, `.xpps` localization editor.
- **LinkOFF `dsar_dec.exe`** — drag-and-drop DSAR decompressor.
- **DKDave** — QuickBMS script + Python rewrite handling DSAR/PSAR (3.2 GB in ~30 s); noted `zsize==0` blocks in
  large archives (e.g. `gapack_bitmaps_c.psarc`) need padding handling.
- **Brink.bms** QuickBMS — secondary unpack of `.dec` files.
- ResHax threads #746 (PSARC archive) and #759 (`.xpps`/`.xmesh`; #759 is mostly 3D-mesh, not text).
- **In-repo (already validated):** `games/tlou2/tools/dsar.py` (reader), `dsar_write.py` + `psarc_write.py`
  (writer). Per the task context these already read/validate GoT's DSAR→PSARC files.

## Q4 — Do sibling Nixxes/Sony PC ports share this container / text format?

- **DSAR→PSARC container: SHARED across Nixxes Sony first-party PC ports** regardless of studio engine. DSAR
  ("DirectStorage Archive") is a Nixxes DirectStorage wrapper; the inner is stock **Sony PSARC v1.4**. The repo's
  `games/tlou2/tools/dsar.py` (Naughty Dog TLOU II) documents the byte-identical DSAR header/entry layout that
  GoT uses (outer LZ4-block flags low-byte 0x03 → inner PSARC v1.4 zlib 64 KB) → **TLOU II and GoT share the
  container + the reader/writer tooling.** Horizon FW / Spider-Man / Ratchet PC ports use the same DirectStorage
  PSARC packaging family.
- **KCAP `lang_<x>_text.xpps` TEXT format: Sucker-Punch-SPECIFIC, NOT shared.** Insomniac ports (Ratchet Rift
  Apart, Spider-Man R/MM/2) store text as Insomniac **`.localization` (DAT1)** — the repo uses `dat1lib`
  (`games/spiderman2`), and Rift Apart's Nexus "Localization Tool" edits `.localization`. Naughty Dog (TLOU1/2)
  uses **ND loc-v2** (`text2/<lang>.{common,subtitles}` + `sid-lookup`, `tlou_loc.py`). **GoT's KCAP/.xpps is its
  own container** → the text codec must be built specifically for GoT (verify against the real file; don't assume
  ND's `count; count×{u64 id,u64 off}; NUL blob` shape). `games/ratchet_rift_apart` in the repo has only art +
  PUBLISH.md (no text tooling) — consistent: different (Insomniac) text format.

## Bottom line for Phase 1
- Container = SOLVED (reuse tlou2 DSAR + psarc_write).
- Text format = build a KCAP/.xpps codec (offset-table aware). Precedent tools exist (GoTExtractor/GoT
  Translation Tool) to cross-check.
- RTL = build menu-proof (LOGICAL vs VISUAL) into the Arabic slot; FONT (Hebrew glyph coverage) is the key gate.
- Deploy = additive `gapack_misc_z<lang>.psarc` into `cache_pc/psarc/` (mod scene's proven mechanism).
