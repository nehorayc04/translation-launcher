## God of War: Ragnarök Hebrew — foundation built, feasibility GO (2026-06-17)

New game scaffolded at `games/godofwar_ragnarok/` (FEASIBILITY.md / RECON.md /
PIPELINE.md + `work/` trio). **Read side proven end-to-end; nothing in the game
folder modified yet.** Two engineering gates remain before a full run.

- **Format (fully cracked):** localization = `exec/wad/pc_le/r_lang_<loc>.wad` =
  **LZ4 frame** (magic `04 22 4D 18`, Python `lz4.frame` round-trips, ~2.3×) →
  inner **WAD** with `WTOC` table-of-contents @0 → **`MSGS_TXT`** section holding
  newline-delimited records `*<numeric_id>*\n<value>\n`, **UTF-8**, ids identical
  across locales. So Hebrew (UTF-8) stores byte-for-byte like the Arabic slot.
- **Arabic-slot hijack applies cleanly** (playbook §0): Arabic is an OFFICIAL full
  locale (`r_lang_ar.wad` present; `21 ar ARABIC` in `exec/languages/LANGS_GOWR09000.txt`;
  `"ar"` in `boot-options.json`) → the engine's RTL/bidi is dev-tested. Mechanism =
  edit `r_lang_ar.wad`, drop in `pc_le/`, set in-game language=العربية — identical
  to the existing Nexus lang-mods (Indonesian/Vietnamese) and CP2077/SM2/WD2.
  Community packer exists: **"God of War Localization Tool" by Delutto** (fallback).
- **`work/gowr_wad.py`** — read-only WAD reader: `decompress` / `extract` (→`{id:str}`)
  / `stats`. Verified on both reference WADs (EN `Vanir Summon` ↔ AR `استدعاء فانير`
  under `*372*`). Corpus dumped: `work/english.json` (53,199) + `work/arabic.json`
  (49,199). **Translatable scope = 48,886** shared EN∩AR ids (EN value = source →
  Hebrew → AR-slot id). Preserve tokens verbatim: `[[S:CHAR:vo_…]]` voice cues, `\n`,
  `[style=Highlight]`/`[/style]`, `[i]`/`[/i]`, `%d`, `[Icons:…]`. Lengths median 83 /
  max 2,279 chars → token-budget batching.
- **Trio templates laid** (adapted to this format, compile-clean, ready for gate-1):
  `work/gowr_translate.py` (EN→He, serial gemma-4, token-budget batches, validate(),
  atomic flush, seed GoW glossary), `work/gowr_watchdog.py` (self-healing supervisor —
  kill-client→`unload --all`→probe→relaunch; UTF-8 children), `work/gowr_progress.py`
  (60 s push to `/api/admin/progress`, `gameId="godofwar_ragnarok"`).
- **Install:** `Game Lab/God of War - Ragnarok/` (FitGirl repack, app v01.01 — the
  staging/test copy; ignore the `C:\Games` one). Reference WADs + decompressed `.bin`
  + corpus JSONs are gitignored (copyrighted/derived); only our code+docs are tracked.
- **Open gates (see FEASIBILITY.md):** (1) **re-pack round-trip** — rebuild the inner
  WAD `WTOC` offsets for a resized `MSGS_TXT` + re-LZ4 (or use Delutto), prove a
  test-string shows in-game; (2) **Hebrew font glyphs** — the Arabic font (`copperplate_*`/
  `godofwar_*` resources) almost certainly lacks Hebrew letters → inject like SM2/WD2.
  Translation can run in parallel with solving repack; only DEPLOY is gated. Backup
  `r_lang_ar.wad.he_backup` before any game-file write.

### BOTH gates SOLVED — Hebrew renders readable RTL in-game (2026-06-18)

The two open gates (repack + Hebrew font) are **closed and user-confirmed in-game**:
the menus render readable, correctly-ordered Hebrew (titles, settings rows, calibration
screens, the long data-collection paragraph). This is the hard, novel engineering done.

- **🟢 GATE 1 — WAD repack (`work/gowr_wad.py`).** Two breakthroughs:
  1. **LZ4 `compression_level=0`** is BYTE-IDENTICAL to the game's packer
     (`pack({})` reproduces the original WAD, MD5 `10963861a94343cf72d4a4174fd59e2b`).
     The engine **REJECTS level-9 frames** (valid LZ4, different 64 KB-block layout) →
     blank text + crash. So `pack()` MUST use `lz4.frame.compress(..., block_linked=False,
     content_checksum=True, store_size=True, compression_level=0)`.
  2. **Constant-size MSGS_TXT pad (delta=0).** Growing `MSGS_TXT` shifts the downstream
     streams (font atlas / SMF) → font corruption → all text blank. Hebrew is MORE compact
     than Arabic (≈ -30 KB), so `pack_blob()` pads MSGS back to the EXACT original byte
     size with trailing `\x00` (and re-appends the original single `\x00` terminator —
     dropping it caused a delta=-1 corruption). With delta=0 the WTOC header stream-0 size
     (+0x14), entry-31 size (+0x04) and SMF entries 43-46 (+0x78) updates are all no-ops →
     nothing downstream moves → bulletproof. (If a build ever can't fit, those four fields
     ARE patched by the same code, but stay in delta=0 for safety.)
- **🟢 GATE 2 — Hebrew font injection (`work/gowr_font.py` `inject_hebrew`).** Atlas =
  `copperplate_ar` (entry 41, BC4 1024×1024); glyph table = `SMF_1` (entry 43, 0x70 header
  + 28-byte records sorted by codepoint + ~27 KB kerning tail). Record layout: +0 cp(u16),
  +12 atlasX×8, +14 atlasY×8, +16 height×8, +18 y_off(**signed** i16), +20 bearingX×8,
  +22 width×8, +24 advance×8. The breakthroughs:
  1. **OFF-BY-ONE codepoint mapping (the root cause of the early garble).** The format
     stores, in record(cp=X), the glyph OUTLINE for codepoint **X+1** (verified: record
     'A'=0x41 holds the 'B' outline). The engine renders codepoint C by exact-matching a
     record cp==C, then drawing the **previous** record's glyph. So Hebrew letter L needs
     (a) glyph(L) written into the record at **cp=L-1**, AND (b) a record AT cp==L to be
     the match-anchor. → write 27 records at cp=0x5cf..0x5e9 holding א..ת, PLUS a **28th
     blank anchor record at cp=0x5EA** so ת (the highest cp) gets an exact match (without
     it, "הגדרות"→"הגדרו", "התחבר"→"החבר" — the last letter dropped). Diagnosed
     definitively via `work/diag_latin.py` (inject LATIN markers into the Hebrew slots →
     read which letters appear in-game → revealed the -1 shift with zero font ambiguity).
  2. **Union-extent fixed cell** (kills clipping + stray dots). Render all 27 glyphs on a
     tall canvas at one fixed baseline, take the UNION ink extent across all of them as the
     cell height (so ל's ascender isn't clipped), clear+mark each atlas box fully dirty
     (removes speckle), align the cell baseline to the **Latin baseline (row 37)** via the
     signed `y_off` → Hebrew sits at the same size/position as English.
  3. **Font = David Regular** (`C:\Windows\Fonts\david.ttf`) — the user's stated
     light/airy preference; `pick_font()` prefers it. A GoW-themed Hebrew font does NOT
     exist (the game's Latin `copperplate`/`godofwar` fonts carry **zero** Hebrew glyphs —
     that is exactly why we inject). `inject_hebrew(blob, font, letter_h=34, ...)`,
     length-preserving (no stream shift).
- **`work/build_wad.py`** — the end-to-end builder: reads `hebrew.json`, `W.pack` (level-0
  + delta-0), injects the font, deploys to the Game Lab `r_lang_ar.wad`. Activation: in-game
  Settings → Text Language = **العربية** (Arabic slot). Offline verifiers (iterate WITHOUT
  burning an in-game test): `c:\tmp\gowr_verify2.py` (faithful engine model — sort by cp,
  render C via exact-match-then-previous-glyph) + `gowr_ingame_sim.py`.
- **⚠️ ENGINE-NATIVE limits (NOT mod-fixable — same for the official Arabic build).** Verified
  by dumping EN/AR/HE for the visible menu strings: **Arabic uses ZERO bidi control chars**
  (no RLM/RLE/LRM), spaces + translations are correct in our `hebrew.json`, and we match the
  Arabic byte-structure exactly. So the remaining cosmetic items the screenshot analysis
  raised are the engine's per-widget layout for the Arabic locale, identical in the shipped
  Arabic game, and CANNOT be changed via a localization WAD: (a) some description/explanation
  panels render **LTR / left-aligned**; (b) bullet markers sit on the LTR side; (c) the
  nav-hint icons (ESC/ENTER/H/«) sit on the LTR side of their label. These are the
  Arabic-slot-hijack tradeoff (cf. WD2's english-locked frontend), not data defects. Adding
  RLM marks where Arabic doesn't is risky (tofu) and unproven on this engine — deferred as an
  optional future experiment, not chased blind.
- **Translation status: 100% COMPLETE (2026-06-19)** — 48,885 / 48,886 translatable strings in
  Hebrew (the 1 untranslated = id 62333 = `\x{A0}`, a non-breaking-space code, not translatable).
  `hebrew.json` = 49,387 keys. Done via the `work/` trio (gemma-4) + a parallel Gemma/Antigravity
  agent looping 500-string batches (`get_batch.py`→split→translate→`loop_merge.py`).
- **⚠️ POST-TRANSLATION QA FIX (2026-06-19) — the agent's "100% clean" claim was WRONG.** A full
  token-integrity sweep found **560 structural mismatches** the agent's merge let through (a prior
  local-loop merge had a looser check): (a) **377 `\n`→real-newline conversions** + 17 nl-count
  diffs (the `\\n`/`\n` confusion — fixed deterministically by `c:\tmp\gowr_detfix.py`: protect the
  cue-separator newline, convert in-prose real newlines back to literal `\\n`); (b) **150 entries in
  ONE corrupted batch (ids ~119833-120767, Vanaheim Wisp dialogue) where the Hebrew belonged to a
  NEIGHBORING line** (wrong `[[S:...]]` cue proved it) — these + 16 tag-variant entries (196 total)
  were **RE-TRANSLATED by Claude** from the correct EN (`c:\tmp\gowr_apply_fixed.py`, token-validated
  before apply); (c) 2 niqqud stripped. Re-verify: **0 token mismatches, 0 niqqud, 100% coverage.**
  Backups: `hebrew.json.bak.detfix.*` + `.bak.claudefix.*`. LESSON: always run a full
  `TOK.findall(en)==TOK.findall(he)` sweep over the whole spine after a bulk agent run — do not
  trust the agent's own merge-time check; a wrong `[[S:]]` cue is the signal of a misaligned batch.
- **✅ delta>0 CRASH — SOLVED + CONFIRMED IN-GAME (2026-07-02).** Build #4 loads and renders full
  Hebrew (David font, correct RTL) with NO crash — the settings menu is Hebrew end-to-end. The 100%
  translation + a working delta>0 repack are DONE. Remaining = **display polish only** (RTL rendering
  of neutral punctuation / numbers / button-tokens; some issues are engine-native = identical in the
  shipped Arabic, not data-fixable). **Key enabler for the polish:** the engine DOES honor bidi
  control chars — the shipped Arabic slot uses **U+200F (RLM ×69), U+202E RTL-override ×28, U+202C ×41,
  U+202D ×13, U+200E ×6** and renders them with NO tofu, so the earlier "RLM risks tofu → deferred"
  concern is RESOLVED: Hebrew anchoring is safe, and the exact control-char placement can be ported
  from the 81 Arabic strings that carry them (mostly `X:‏ %d من %d` counters + `[Button]` icon
  sequences with `‮…‬`). Data is CLEAN (verified id=918 etc. store logical Hebrew correctly).
- **⚠️ delta>0 grow — full layout mapped, BOTH fixes combined (the crash fix above).**
  The 100% build crosses into the **delta>0 path** (Hebrew MSGS_TXT **+303,526 B > Arabic**; all
  proven-in-game builds ≤72% were **delta=0**, byte-stable). It CRASHED on selecting Arabic across
  THREE builds, each doing only ONE of the two required things. **Measured facts (from the pristine
  `.he_backup`; `c:\tmp\gowr_layout.py` + `gowr_smf_true.py`): first, decompressed SIZE is NOT the
  issue** — shipped `r_lang_en/ko/th` decompress to 8.5–9.6 MB (BIGGER than our 7.85 MB grow) and load
  fine; the header `+0x0c` = 12 MB capacity fits; there is no external `.toc`/manifest for the lang
  WADs (`gowr_diff.py`, `gowr_hdr.py`). So a correct grow IS loadable → **zero content loss is
  achievable** (do NOT strip the `[[S:SPEAKER:clip:timing:hash]]` cues — the working Arabic slot has
  them too, they drive subtitle speaker+sync). **The two things a grow MUST do together:**
  (1) **256-align `delta`** — the engine re-applies each resource's 16-byte alignment (the atlas is
  exactly 16-aligned), and a flat blob-splice matches the engine's layout only when `delta % 16 == 0`;
  (2) **shift the stream-0 post-MSGS font-metric entries' `+0x78` by `delta`** — stream-0 is one
  contiguous chain in +0x78 order `[1024 hdr] MSGS(31) → SMF(43)→44→45→46` that ends EXACTLY at the
  stream-0 size, so growing MSGS slides 43-46 right by `delta` and their `+0x78` must track it, or the
  engine reads the glyph table from stale bytes. (The texture chain 35→38→41=atlas is a SEPARATE
  stream-1 that relocates via the `+0x14` update with its internal `+0x78` fixed — do NOT touch it;
  entries 0-30/32-42 sit in the 1024-byte header before MSGS — unaffected.) The three crashed builds:
  #1 patched 43-46 but `delta` mod16=6; #2 neither; #3 aligned `delta` but dropped the 43-46 patch —
  **NONE did both.** **FIX = both, in `gowr_wad.py` `pack_blob` delta>0 branch:** pad MSGS so
  `delta`%256==0 (`assert`) AND `for e in (43,44,45,46): +0x78 += delta`, alongside entry-31 size
  (+0x04) and stream-0 size (+0x14). Rebuilt: delta **+303,616** (256×1186). **Verified maximally
  consistent** (`gowr_smf_true.py`): the SMF sits at 7,781,607 = old+delta with **27/27 Hebrew glyph
  records physically present**, and ALL THREE location models agree there (flat-shift, off78+base
  [base 2,266,599 preserved], index-cumulative); stream-0 chain fills exactly; stream-1 untouched;
  text 1499/1499. Deployed to BOTH Game Lab AND `C:\Games\God of War - Ragnarok`. Community pool
  `/translate` (`gowragnarok`) = 48,886 (0 open). **If build #4 STILL crashes**, delta>0 is likely
  gated on an unfound whole-blob validation → fall back to delta=0 with a lossy cue-trim (`gowr_cues.py`:
  stripping cues frees 1.74 MB, guaranteed fit, but drops speaker/sync). **User: launch → Arabic; revert
  = copy `r_lang_ar.wad.he_backup`.**
- **DISPLAY POLISH pass 1 — font vertical + noise (2026-07-02, deployed, awaiting confirm).** User
  in-game (crash-fixed build): 3 issues — (1) **Hebrew too HIGH** vs Latin/punctuation, (2) **dots +
  streaks** (נקודות ופסים) near letters, (3) **parens misplaced**. Diagnosed offline (`c:\tmp\gowr_font_diag.py`
  + `gowr_native.py`): the DATA is clean (logical Hebrew, verified); (1) the shared-cell font injector
  made every Hebrew letter **42 px tall + carry 13 px descender space** vs native caps **36 px, yoff=0
  bottom-on-baseline** → Hebrew towered/floated; (2) the `max(sharp, glow*1.4)` alpha sprayed a **wide
  faint halo** whose sparse low-alpha pixels **BC4-banded** into dots/streaks. **FIX (`gowr_font.py`
  `inject_hebrew`, rebuilt+deployed):** per-letter placement — each glyph rendered to its OWN ink extent,
  **`y_off = iy1 - R`** so a normal letter anchors EXACTLY like a Latin cap (yoff=0, bottom on baseline)
  and only ך/ן/ף/ץ/ק drop below (no shared descender space); `letter_h` 34→29 so **body ≈ 35 px = caps**;
  alpha reworked to native's DENSE-soft profile (supersample→LANCZOS→one mild `GaussianBlur(1.15)`→peak
  rescaled to 180→drop <20 specks) — **margin specks now 0**, max 180 = native. Verified: א = yoff 0, h 28
  (identical anchoring to cap 'A'). **(3) parens** = partly UNFIXABLE (e.g. "מהדר הצללות **(92%)**" — the
  `(92%)` is engine-composed at runtime, NOT in our string id=81385) and partly anchorable (the shipped
  Arabic wraps paren+button/number spans in **U+202E…U+202C**; 81 AR strings carry control chars, ours 0
  — port next). **User: test the font (height + noise) first; then I port the paren anchoring.**
- **DISPLAY POLISH pass 2 — the dots ROOT-CAUSED (2026-07-02).** After pass 1 the position was RIGHT
  but the user reported it got smaller + lower quality, then persistent **dots beside letters** — SAME
  dots with David AND Arial (so NOT the font's serifs, and NOT the data — a faithful no-bilinear engine
  sim `c:\tmp\gowr_sim2.py` rendered every word CLEAN). **Real cause = atlas NEIGHBOUR BLEED via the
  engine's mip/bilinear font-texture sampling:** `find_empty_boxes` packed the injected glyphs only
  ~6 px apart, so a neighbour's ink leaked into the sampled rect (measured: strong left-neighbour ink
  **max=154 on ת**, the letter whose word showed a dot). **FIX (`inject_hebrew`): PAD=8 → CW/CH gain a
  wide empty border, `find_empty_boxes(..., thr=2)`** so adjacent glyphs sit ≥16 px apart → mip-safe;
  re-measured **worst neighbour ink 154 → 0** across all 27 letters. ALSO in this pass: size bumped to
  match native caps (`letter_h` 29→33→ px≈62, Hebrew ≈35 px = native 36-37, uniform), weight boldened
  (`stroke_width=bold*SS`), crisped (`SOFT`=1.15→0.35, cutoff `<26`), and **switched pick_font David→
  Arial** (David's foot-serifs were reading as dots at small size; Arial is serif-free, matching the
  user's clean mockup). Per-letter baseline `y_off` from pass 1 kept (position stays correct). All
  offline-verified (heights, 0 neighbour-ink, clean word renders) before deploy.
- **DISPLAY POLISH pass 3 — David restored + per-letter y_off was the y-bug (2026-07-02).** User: noise
  GONE (the PAD neighbour-bleed fix held), but wanted **David back** + the letters mis-positioned
  (**י floated LOW, ק rode HIGH** — inverted) + still a touch blurry. Root cause of the y-bug: the
  **per-letter `y_off`** (pass 1) — the engine wants a **CONSISTENT per-font y_off** with each letter's
  true position baked into a SHARED-height cell; a varying per-letter y_off inverted the off-baseline
  letters. **Fix: reverted to a SHARED cell** (union ink extent [top..bot], uniform `y_off = bot - R`)
  so every glyph's vertical position is exact (yod high, qof/final-letters drop below) — offline-render
  confirmed. Also `pick_font` David→(the serif "dots" were the neighbour-bleed, now fixed by PAD, so
  David is clean), `SOFT` 0.35→0 + `SS` 4→5 (crisper, no blur). WAD re-verified structurally valid.
- **⚠️ RED-HERRING that cost hours: "the game won't open (taskbar icon, no window)" was NOT the mod.**
  After a David build the game showed only a taskbar icon; it persisted through killing the process,
  reverting the WAD to vanilla (`.he_backup`), AND a reboot. Root cause: the game's
  `<gamedir>\settings.ini` had **`WindowPosition=-31984, -31938`** (an int16-underflow off-screen
  position, corrupted by one of the earlier crashes) → the window is created far off-screen (exists in
  the taskbar, invisible). **Fix: set `WindowPosition=0, 0`** in settings.ini (BOTH the Game Lab copy —
  which had the bad value — and the C:\Games copy; backed up first). Game opened immediately. **Lesson:
  if GoWR shows a taskbar icon but no window, check `settings.ini WindowPosition` FIRST — it is a
  game-config red herring, unrelated to the localization WAD.** The David font build was then restored
  from `.david_build`. **User: now test the David font (י/ק positions + crispness + no dots).**
- **FONT FINALIZED — measure-driven quality match + descender dropped (2026-07-03, `gowr_font.py`).**
  After ~12 in-game iterations chasing the ק descender + "bad quality", switched to a rigorous
  MEASURE-not-guess method (all offline vs the game's own English, which shares the screenshot):
  - **The `+18` vertical field is UNRELIABLE on the Arabic slot.** Raw-byte-diff proved +18 is the
    descender control (native descenders p/g/y/j all = exactly 99; caps 0; round 4), and it lives in
    the GLYPH record (cp=L-1), matching my construction. But in-game my ק at 99 didn't move; a
    diagnostic (`c:\tmp\gowr_yo_diag_build.py`, ד=+240 dropped ~40px / ה=−240 rose) proved the engine
    DOES apply +18 to Hebrew but at a **nonlinear/uncalibratable scale** (160 raw = 0px, 240 = ~40px)
    — so a clean ~12px tail can't be dialed in (240 shoved ק's tail 43px down, head floating = the
    "ק up" report). **Decision: DROP the descender — crop every glyph to end at the baseline R
    (yo=0) → clean stub finals (ק ך ן ף ץ, standard in many Hebrew UI faces), normal letters on the
    line, yod floats high.** Robust, no dependency on the flaky field.
  - **"Bad quality" root cause = WEIGHT + anti-aliasing, both measured from the native atlas.** Native
    ink density (>90 alpha) = **0.617** (heavy engraved stroke) and mid-tone fraction = **0.72** (soft
    gradient). My earlier renders were EITHER blocky-bimodal (hard `a[a<26]=0` threshold → midfrac 0.21)
    OR thin/faint (David regular, no bold → density 0.278). Fix (`inject_hebrew`): **David BOLD**
    (`davidbd.ttf`, `pick_font` reordered) + a **MaxFilter(3) dilation** for weight + a **moderate
    GaussianBlur(0.8)** + peak 210 + keep the AA (`a[a<6]=0`, not <26). Deployed atlas: density **0.529**
    (≈native), and the ON-SCREEN mid-tone fraction measured **0.74 ≈ native 0.72**. Heavy, smooth,
    clean — user-confirmed acceptable. **LESSON: for an in-game font match, measure the native glyphs'
    (a) ink density = weight and (b) mid-tone fraction = softness, and match BOTH; guessing blur/bold
    blind oscillates between blocky and faint.** Params live at the top of `inject_hebrew`
    (NATIVE_MAX/SOFT/DILATE/bold) + the descender `cbot = R` block.
  - **Next:** publish like SM2/CP2077 (GitHub `godofwar-ragnarok-hebrew-mods` repo + Worker slug
    `godofwar-ragnarok-hebrew` + Supabase `games` id + `mod_version_history`) once the user OKs. The
    100% translation + delta>0 crash-fix + font are all done. Community `/translate` pool
    (`gowragnarok`) already live (48,886, 0 open).
- **DISPLAY POLISH pass 4 — vertical placement SOLVED DEFINITIVELY via measure+validate (2026-07-03).**
  After several more disproven-in-game y_off guesses (per-letter tight-crop → "ק floats above";
  sign-flip → "didn't change"; shared-cell uniform-h → descenders CLIPPED to stubs), stopped guessing
  and did two rigorous things. **(A) Ground-truth pixel measurement** from the user's own screenshot
  (which contains BOTH the engine-rendered English *and* Hebrew on the SAME baselines): on the
  PLAYSTATION line the current Hebrew body-bottom (1130) == the English baseline (1130) → **baseline was
  already correct**; 21/22 letters on a line shared the exact baseline row (the 1 outlier = yod,
  correctly high); Hebrew stroke width (10px) == native English (9–10px) and Hebrew softness (soft/ink
  1.51) is LESS than the native English (2.26) → **"too thick/blurry" is relative to the idealized PIL
  reference; the game's own English copperplate is inherently soft — not a real defect.** The ONE real
  remaining defect = **clipped descenders** (ק ך ן ף ץ lost their tails → stubs, vs the target's hanging
  tail). **(B) Validated the placement model against native ground truth** (`c:\tmp\gowr_validate_model.py`):
  feeding the sim the NATIVE Latin records reproduces reality EXACTLY — caps A/H (yo_raw=0) sit
  bottom-on-baseline, x-height n (yo=0) on baseline, descenders p/g/y (yo_raw=**99** ⇒ +12.4px) hang 12px
  below → model is `bottom_screen = baseline + yo_px`, yo POSITIVE = down, and yo IS x8-fixed-point. **The
  "y_off has no effect" was a RED HERRING: in an earlier session `write_record` wrote y_off RAW (unscaled),
  so a tight-crop build wrote ~11 instead of ~88 → a ~1.4px nudge → invisible → descenders never dropped.**
  With `write_record` now scaling **×8** (added this session), the correct construction is a **TIGHT
  full-ink per-letter crop** that faithfully transfers each glyph's own David metric: `crop=a[iy0:iy1+1]`,
  `h=iy1-iy0+1`, `yo=iy1-R` (R = the shared rendering baseline). Result records (verified): ק/ך/ן `yo_raw=88`
  (≈ native p's 99, tail 11px below), normal letters `yo_raw≈0` (on baseline like A), yod `yo_raw=-48` (high).
  **Offline-rendered the full menu with the validated model → ק hangs its tail below, all others on baseline,
  yod high — matches the target reference.** Deployed both copies + refreshed `.david_build`. Rendering
  params kept (bold=1, SOFT=0, SS=5 — measured to already match the native weight/sharpness). **LESSON: when
  an in-game visual param resists guessing, MEASURE it from a screenshot that contains a known-good reference
  rendered by the same engine (here English on the same line), and VALIDATE the model by simulating the
  native records — never iterate blind.** **User: confirm ק's tail now hangs below the line in-game.**
- **FONT — the working "soft engraved" tuning (2026-07-03, in-game GOOD, user fine-tuning size/pos).**
  A long in-game iteration (the user drove by eye) settled the WHOLE font question. Path + hard results:
  - **RESOLUTION IS AN ENGINE CEILING (decisive 2x test).** Rendered the atlas glyph at 2x resolution
    (`build_wad.py --letter-h=60`) → in-game the **text got BIGGER**, proving **display size is tied to the
    record's W/H field** (W/H = the atlas source rect, and display = W/H × a global scale). So we CANNOT
    raise atlas resolution to beat the blur — the upscale-softness is a bitmap-atlas / no-SDF engine limit
    that hits the game's OWN English too (measured: native English caps are the SAME ~37px atlas size as
    our Hebrew). "Perfectly crisp at any size" (SDF) is an engine feature we can't add via a texture mod.
  - **SHARP WAS THE WRONG DIRECTION.** Measured the native English glyphs directly (exact record crop):
    they are **SOFT — peak ~180 (NOT 255), midtone ~0.72, low hardness ~0.3** = a thick stroke with a wide
    soft AA edge = the engraved "depth". A sharp/bimodal source (my `SOFT=0`/`peak=255` build) upscales into
    jaggy halos and looked WORSE; the user's own instinct ("try the opposite — blur a bit + add depth") was
    correct. **The BC4 encoder was verified LOSSLESS** for this gradient (native 0.71 midtone → 0.71 after
    `bc4_encode_block` round-trip), so the fix is purely in the render: soften + thicken toward native.
  - **WORKING PARAMS (`gowr_font.py inject_hebrew`):** `NATIVE_MAX=185` (soft peak like native, not full
    black), `SOFT=1.2` (GaussianBlur — the wide soft edge = depth), `DILATE=1` (light thickening; the user
    asked thinner than the dil=3 first pass), `SS=4`, David Bold (`davidbd.ttf`). Native's exact 0.72
    midtone is unreachable at 37px (it was authored high-res + downsampled) — dil+blur gets the closest
    soft+deep look this size allows, and it reads well in-game.
  - **SIZE + POSITION are user-driven knobs:** size via `build_wad.py` `letter_h` (30→34→40→**46** as the
    user asked to enlarge; `--letter-h=N` overrides for a one-off); vertical position via the internal-shift
    `RAISE` in `inject_hebrew` (`round(px*0.09)` now — was 0.16, lowered per "המיקום נמוך יותר"). The #2
    internal-shift geometry (shrink + `RAISE` band + `y_off=0` bottom-anchor, NO reliance on the flaky +18
    field) is kept as the position mechanism (ק/ן tails fall into the RAISE band, normal letters float).
  - **DEPLOY IS PROJECT-FOLDER ONLY + AUTO-RELAUNCH.** Per the user: (a) `build_wad.py` deploys ONLY to the
    Game Lab copy `…\Game Lab\God of War - Ragnarok\` (the exe the user runs is `…\Game Lab\…\GoWR.exe`);
    C:\Games is NEVER touched (its earlier deploys were reverted to vanilla + cleaned). (b) **Every build
    now auto-closes GoWR.exe if running and relaunches it** (`relaunch_game()`: taskkill → `os.startfile`)
    so the fresh atlas reloads without a manual restart — the user still navigates in-game to Arabic →
    Settings manually. **A texture change is NOT visible until the game is FULLY restarted** (the atlas is
    cached in VRAM; main-menu reload is not enough) — the auto-relaunch handles this.
- **DESCENDER DROP — root cause FOUND: the +18 field is CODEPOINT-RANGE-GATED (2026-07-03, awaiting
  in-game confirm).** After ~10 failed y_off guesses (glyph record, match record, magic 99, per-glyph
  vs uniform — all either did nothing or made the "פסים" dash artifact), a probe of the PRISTINE
  `r_lang_ar.wad` SMF settled it: the engine DOES honor +18, but **per codepoint RANGE**. Native
  ranges that DROP: ASCII/Latin (values incl. 99), **Arabic 0x600** (ج=120, و=90, deepest ى=174 =
  21.75px), **Arabic-pres 0xFE80** (up to 174). The **Hebrew range U+05xx is IGNORED** — the deployed
  build literally had `99` on all 5 Hebrew descender MATCH records and it moved NOTHING in-game, while
  the identical value drops Arabic 2 codepoints over. So switching the game to English alone would NOT
  fix it (it's the codepoint, not the language). **FIX (implemented): remap the 5 descender finals
  (ך ן ף ץ ק) to spaced Arabic-PRESENTATION-FORM codepoints** (0xFEB0/B4/B8/BC/C0 — RTL-strong like
  Hebrew, so logical storage + bidi are UNCHANGED, no visual re-store) **that the engine DOES drop**.
  `gowr_wad.DESC_REMAP` (str.maketrans) rewrites the TEXT at build (source stays Hebrew; pushes into
  the proven delta>0 path, +362,752 B, 256-aligned); `gowr_font.DESC_PRESFORM` places each Hebrew
  descender glyph (the SAME atlas box, reused) on both the glyph record (cp=C-1) and the match record
  (cp=C) with a real tail `y_off = iy1-R` (≈13px). Overwriting native Arabic-pres records is harmless
  (zero Arabic in Hebrew content). Off-by-one honored (glyph in C-1, y_off on both C-1 and C).
  Verified offline: text round-trips 400/400 ("נשק"→"נשﻀ"), all 10 pres-form records carry the glyph
  box + yoff=104. **Deployed to Game Lab (NOT launched — user rule). User to confirm in-game: do
  ך ן ף ץ ק now hang their tail below the baseline with the body aligned + no dashes?** If YES → this
  is the production descender fix; if the pres-form range is somehow gated too → the y_off path is
  fully exhausted (fall back to CUT-at-baseline, the clean/aligned/no-dash look the user earlier OK'd).
- **Next when in-game confirmed:** publish like SM2/CP2077 (GitHub release repo + Worker slug +
  Supabase `games` row + `mod_version_history`).
- **ENGLISH RAISED TO MATCH HEBREW — SOLVED + VERIFIED IN-GAME BY CLAUDE (2026-07-04).** After the
  uniform-Hebrew-raise ("מצוין"), the user wanted the ENGLISH/digits/punct/parens raised the same
  ~14px so mixed lines (`ל-PLAYSTATION`, `1100 × 620`, `(anti aliasing)`) align. Journey + the
  reusable facts (all in `work/gowr_font.py`):
  - **`+18` (y_off) is a TEXTURE-V SAMPLING offset, NOT a screen anchor** (user-confirmed: "the crop
    rose, not the text"). Shifting a native Latin record's y_off CLIPS the glyph (moves the visible
    crop), it does NOT reposition it. So English can't be raised via y_off. (The `GOWR_LATIN_YOFF`
    path is kept but DISABLED.) The Hebrew range ignores +18 entirely; Latin honors it as a crop.
  - **Raising native Latin = RELOCATE each glyph into a TALLER cell** = [native copperplate pixels at
    the TOP] + [RAISE empty rows below], bottom-anchored → the glyph lifts by RAISE with NO clip and
    NO resize. Keep the record's native y_off/bearing/advance/w/cp; only change atlasX/atlasY and
    `h += RAISE`. **`h` POSITIONS, it does not SCALE** — proven by the game's own glyphs (period h=5
    renders small, cap h=37 renders tall = proportional → h is ink-height at a fixed atlas→screen
    scale, so extra empty rows = raise, not zoom). Verified in-game: copperplate look kept, same size.
  - **THE DOTS (niqqud-like marks under every letter) = atlas neighbour-bleed**, two causes, both
    fixed: (1) **per-glyph clearing left faint AA borders** (value >2) around each vacated glyph →
    they read as "occupied" and fragmented the packer into thin columns (`dot_diag.py`/`freemap.py`
    proved it); (2) packing Latin into the freed space put a neighbour directly below a glyph's RAISE
    band / inside a Hebrew glyph's PAD → the engine's bilinear/mip sample of the cell bottom picked up
    the neighbour = a stray dot (`ink-below-cell` was 117-185; must be **0**).
  - **THE FIX (packs clean, 0 dots):** read ALL non-Hebrew glyph pixels → **clear the ENTIRE atlas
    EXCEPT the just-placed Hebrew boxes** (`atlas[~_keep]=0`, mark all dirty) → ONE ~98%-free clean
    region → **`pack_boxes` = a bottom-left, tallest-first, integral-image packer** with `reserved`
    (the Hebrew boxes, so no Latin lands in a Hebrew's pad) + **NPAD=3** (≥6px between cells so no
    neighbour bleeds the raise band). Relocates all **186 non-Hebrew glyphs** (Latin + Latin-1 «»® +
    punct + Runic + PUA) raised 14px. (First-fit-top-left + per-glyph clears FAIL — fragmentation;
    the whole-wipe + bottom-left packer is the working combo.) Free the unused **Arabic/CJK/Hangul/
    Arabic-pres** atlases early (never in Hebrew/English text) for headroom.
  - **VERIFIED IN-GAME BY CLAUDE (screenshots, user away):** main menu (GOD OF WAR / PLAYSTATION® /
    Hebrew), Graphics (AMD Radeon RX 9070 / 1100 × 620 / VSync), the AA description ((anti aliasing) /
    (upscaling) / NVIDIA DLSS, AMD FSR 1, XeSS 1), VRAM 30% PSOs 100% — ALL clean, no dots, English/
    digits/parens/% raised + aligned with Hebrew, `ink-below-cell=0` for every glyph.
- **AUTONOMOUS LAUNCH + SCREENSHOT + NAVIGATE tooling (`work/`, built 2026-07-04):** `capture.py`
  (find the GoWR window by **PID** via tasklist+EnumWindows, GetWindowRect, ImageGrab; `move` arg →
  SetWindowPos/MoveWindow to **top-right** — the user wants the game windowed top-right for viewing;
  **MoveWindow works, SetWindowPos HWND_TOPMOST did not**); `click.py fx fy` (fractional mouse click).
  **KEY: GoW Ragnarök's MENU is MOUSE-navigable — click the sidebar tabs — but synthetic KEYBOARD
  input (SendInput scancode/VK) does NOT reach it** (`sendkeys.py` kept but ineffective; the game
  uses raw input for the menu). Launch detached via PowerShell `Start-Process` so it survives; the
  game takes ~80s to reach the menu (shader compile). **settings.ini `WindowPosition` still corrupts
  to the int16-underflow `-31992,-31969` off-screen "taskbar-only" state on some exits — fix to an
  on-screen value before launch** (or `DisplayMode=Fullscreen`); set a small `WindowSize` (e.g.
  `1100 x 620`) for a viewable windowed capture. Screenshots proving each state live in the scratchpad.
- **PAREN bidi fix + Hebrew shrink (2026-07-04, PROVEN in-game, `build_wad.py`).** User: the Hebrew
  looked messier/bigger than the English (esp. `((upscaling)` garbage). Two build-time transforms
  (source `hebrew.json` UNCHANGED — reversible):
  - **Parenthetical-Latin unwrap** (BIDI FIX #2). Root-caused by an Arabic-context A/B test (inject
    variants into id 81432 → `--no-font` build → in-game zoom): the Zouna engine **cannot render a
    parenthetical wrapping a Latin term in RTL**. A single Latin token `(upscaling)` renders
    `upscaling))` (both parens collapse to one side as the same glyph); tested `(upscaling )` /
    `( upscaling)` / `( upscaling )` — **all** cluster the parens (NO spacing/splitting fixes it). A
    multi-word `(anti aliasing)` was borderline. Since the parenthetical English is a translator-added
    GLOSS (the game's own Arabic drops it entirely), the fix **unwraps** the parens around any
    Latin-only term → the term sits inline, which ALWAYS renders clean (like `NVIDIA DLSS`). Regex
    `\(([^()]{1,60})\)` unwrapped only when content has a Latin letter, no Hebrew/Arabic, and matches
    `[A-Za-z0-9 .,\-'&/]+` (so `(מתפוצץ)`/`(92%)`/`(%d)`/`(3.1)` are LEFT). Runs AFTER hyphen→space.
    **271 strings** unwrapped. Verified in-game: `החלקת קצוות anti aliasing ושדרוג קנה מידה upscaling.`
    — clean inline, no parens, matches the English's look.
  - **Hebrew shrink** `letter_h` 44→**40** (better matches the English cap height). Verified in-game:
    clean, smaller, no dots (NPAD=10 atlas spacing intact). Backups: `work/build_wad.py.bak-paren-shrink-20260704`,
    `out/r_lang_ar.wad.bak-paren-shrink-20260704`.
  - **⚠️ Known SEPARATE issue — decimal-number bidi (diagnosed via Arabic-context A/B test, NOT yet
    fixed).** The engine **splits a decimal number at the `.`** (same class as the hyphen bug): `3.1`
    → `3 1.` and `12.34` → `12 34.` — the **digits stay in the correct ORDER**, but the `.` moves to
    the end and a gap appears (so it's readable, just cosmetically off; my earlier "the 3 drops" read
    was WRONG). Tested + REFUTED: **LRM-wrap `‎3.1‎` (engine ignores marks) and digit-reversal `1.3`
    both split identically.** Only **9 strings** hold a decimal (`games/godofwar_ragnarok`: version/
    spec numbers 3.1/3.7/1.5/5.1/7.1/1.0 — ids 9625/53962/65455/81352/81354/81361/81362/81364/81432).
    A clean fix needs an **atlas-safe non-splitting separator** (comma likely splits too, being a CS;
    middle-dot U+00B7 / Arabic U+066B risk tofu since the font build clears/relocates glyphs) — could
    NOT be verified because GoWR's in-game loads became prohibitively slow/stuck (~8 min, often hung at
    ~40%) after many relaunches. **Deferred** until the game loads reliably to A/B a separator. NOT
    shipped blind (tofu risk). Everything else in the AA description renders clean.
- **ITALIC `[i]...[/i]` STRIPPED — clean slanted Hebrew is NOT achievable on this engine (2026-07-04,
  user chose to strip via AskUserQuestion).** Subtitle report: italic runs shifted right / ate the
  adjacent space (`אוכל [i]להשתמש[/i]—`→"אוכללהשתמש" glued; `[i]זה[/i] מה`→gap after זה). **Root-caused
  from the WAD's 4 SMF glyph tables** (`extract/fonts/`): **`SMF_1---43.bin` (40 KB) is the ONLY table
  with Arabic** (51 Arabic + 131 Arabic-pres + Latin/CJK/Runic); `SMF_3---44`/`SMF_2---45`/`SMF_0---46`
  are **Latin-only** (no Arabic). So ALL Arabic *and* Hebrew text — including italic — renders from
  SMF_1, and the engine applies a **SYNTHETIC italic slant** to it. Native Arabic italic renders fine
  (glyphs at the position the shear expects); our injected Hebrew is **raised/shrunk** (SHRINK=0.90 +
  RAISE), so the shear **over-shifts** it, PLUS the space next to the `[i]` tag (Latin "i" inside) is
  bidi-mishandled. NOT fixable by spacing (the official Arabic renders `[i]…[/i]` fine at ANY spacing →
  glyph-slant-specific; and gluing merges non-cursive Hebrew words), and italic can't get metrics
  separate from regular (same SMF_1 records serve both; no separate italic table). **Fix in
  `build_wad.py`:** `_ITAL = re.compile(r"\[/?i\]")` literal-strips `[i]`/`[/i]` from **1024 strings**
  (runs FIRST, before hyphen/paren/decimal/spacing; tags are glued to content so no double-space is
  created; source `hebrew.json` UNCHANGED — reversible). `[style=…]` highlights are LEFT (different
  visual, not reported). Result: what was italic renders as plain Hebrew, positioned correctly.
- **FONT final tuning (2026-07-04, user-accepted) + the resolution ceiling.** `gowr_font.py`
  `inject_hebrew`: **DavidLibre-Bold**, **SOFT=0.8** (measured trade-off: 0.5 Bold = too hard/reads
  low-res, 1.3 = too blurry → 0.8 = softened edges without the muddy blur), **FAINT_CUT=6**, **TRACK=8**
  (letter-spacing decouple: `advance = gw + PAD − TRACK`, PAD=10, so inter-letter gap is independent of
  atlas padding), DILATE=1, `letter_h=34`. **⚠️ RESOLUTION is an ENGINE CEILING** — bitmap-atlas font,
  no SDF; on-screen size = the record's W/H field × a fixed global scale (a 2× `--letter-h=60` atlas
  test just made the text BIGGER, not sharper), and it caps the game's OWN English too. Crisp-AND-soft
  is bounded; cannot be beaten via a texture mod.
- **g-descender clip FIX:** in `inject_hebrew` the Latin-glyph bottom scan is **gap-tolerant** (stop
  after 3 consecutive empty rows) for `_DESCCP = {g p q y j , ; ( ) [ ] /}` only, and **tight**
  (first-empty stop) for every other glyph so a non-descender never grabs a neighbour's ink (dots).
  `_LATMB = RAISE + 3`. (The native atlas 'g' has ~12px strong / ~18px soft ink below the tight record
  box — a first-empty scan stopped at a thin AA gap and clipped the tail.)
- **Decimal `3.1`→`3 1` (period removed).** With the literal `.` kept, the engine splits the number at
  the `.` and the `.1` ESCAPES left; no atlas-safe non-splitting baseline dot exists in David → replace
  the inter-digit `.` with a space in Hebrew-context strings (`_DECIMAL`, 7 strings). Readable, no escape.
- **Arabic-leak repair in `hebrew.json` (27 strings).** The "ק חיל…"/"م חיל" bug was NOT a render bug —
  27 strings had **leaked Arabic letters** mid-Hebrew (e.g. id 10349 `مחיל…`→`מחיל…`; whole Arabic words
  like id 4174 بيفروست→ביפרוסת became readable transliterations). Fixed deterministically via a **cognate
  Arabic→Hebrew char map** (م→מ, و→ו, ل→ל, …). Backup `hebrew.json.bak_arabicfix`; residual Arabic = 0.
- **Launch/window (standing rule):** `build_wad.py` auto-launch is now **opt-in** (`--launch`);
  `relaunch_game()` = taskkill GoWR.exe → `force_windowed()` → `subprocess.Popen([exe], cwd=GAME_LAB,
  DETACHED|NEW_PROCESS_GROUP)`. `force_windowed()` patches `settings.ini` → `DisplayMode=Windowed` +
  `WindowPosition=636, 20` (top-right) before every launch. **`os.startfile` inherited the `work/` CWD →
  the game couldn't find `settings.ini` → fullscreen black screen;** launching via `Popen(cwd=GAME_LAB)`
  (mimics a double-click) fixes it. Deploy is **Game Lab ONLY** (`C:\Games` left vanilla).
- **✅ PUBLISHED v1.0.0-beta.1 (2026-07-04, user said "פרסם").** Free website-download mod (like
  SM2/WD2). The mod = the single Hebrew `out/r_lang_ar.wad` shipped with a self-contained `install.py`
  (auto-finds the game, backs up `r_lang_ar.wad`→`.he_backup`, copies the WAD, `--revert`) + a Hebrew
  readme. **New tooling:** `games/godofwar_ragnarok/pack_and_release.py` (zips `release_files/` +
  manifest, `gh release create`, `--pack-only`) + `release_files/{install.py,קרא_אותי.txt}`.
  - **GitHub:** repo `hebrew-translation-hub/godofwar-ragnarok-hebrew-mods` (created this session; a `README.md`
    init-commit via the Git contents API was REQUIRED first — `gh release create` 422s "Repository is
    empty" with no commit). FULL release **`v1.0.0-beta.1`** (so `releases/latest` resolves) =
    `godofwar_ragnarok_hebrew.zip` (**2,708,994 B**, sha `3b9f095293e86e0a17c4235b25fc5de53f0127b1d470d2bc12bd2cc94fb3b87d`)
    + `manifest.json`. Download HEAD → 200, size matches.
  - **Supabase:** `publish_version.py gowragnarok 1.0.0-beta.1 --stage beta --sha … --size 2708994
    --archive-url …/v1.0.0-beta.1/…zip --apply` (games version/stage + `mod_version_history` is_current),
    then a direct PATCH `games` → `status='beta'`, `download_url`→the zip, `show_on_website=true`,
    **`show_on_launcher=false`** (NO launcher applier exists for GoWR — it's not a generic download-mod;
    a `godofwar_ragnarok_mod.py` native applier is a separate future task). Price stays **0 (free)**.
    games.id = **`gowragnarok`** (NOT `godofwar_ragnarok` — that's only the progress/detector key).
  - **Worker:** slug `godofwar-ragnarok-hebrew` added to `steam_mod_worker/src/index.js` REPOS (for a
    future launcher applier); **NOT deployed** (needs the CF token) and **NOT needed** — the website
    Download button uses `games.download_url` → GitHub directly.
  - **Verified consistent (2026-07-04):** `/api/games` gowragnarok = beta + downloadUrl + cover + free;
    `/api/translate?action=games` = 48,886 total / 0 open (100%); `mod_version_history` is_current with
    matching sha/size. 4 Claude news drafts pushed ([[claude-news-suggestions]]).
  - Community `/translate` pool (`gowragnarok`) live (48,886, 0 open). Re-release = re-pack +
    `gh release upload v1.0.0-beta.1 --clobber` + PATCH the Supabase sha/size.
- **✅ LAUNCHER native applier SHIPPED (2026-07-04, dev_build 40, BUILD_ID `20260704221204`).** GoWR
  is now a one-click install in the launcher (free), the safest possible: a SINGLE-FILE swap that
  never harms the game. `translation_manager/gowr_mod.py` — atomically replaces
  `exec\wad\pc_le\r_lang_ar.wad` with the bundled Hebrew build, backs up the ORIGINAL in the launcher
  cache (`~/.translation_manager/mod_cache/gowragnarok/backup/r_lang_ar.wad.orig` — OUTSIDE the game,
  so a Program-Files install still reverts); ONLY that one file is touched; writes are atomic (temp +
  os.replace, no half-write); revert restores the exact original; **game-update-aware** (if a patch
  rewrote the WAD, the backup refreshes so revert stays exact) → portable to every Windows version
  (pure file ops) + every store/version (Steam/Epic/FitGirl; the only signal is the WAD's fixed
  relative path). Self-tested (backup/apply/revert/idempotent/game-update/missing-wad all PASS).
  - **Wiring** (mirrors the WD2/GTA native-applier pattern): bundled payload
    `translation_manager/assets/godofwar_ragnarok/r_lang_ar.wad` (rides the `('translation_manager',
    …)` spec datas entry — no spec change; `_keep()` doesn't drop `.wad`); `main_eel` `_GOWR_ID=
    "gowragnarok"` + `_GOWR_BUNDLED_VERSION` + RPCs `get/install/remove_gowr_mod` + `_run_gowr_install`
    + `_mod_state`/`_enrich_game_row`/`_native_update_status`/`check_game_mod_update`/`get_mod_updates`
    branches (joined the `(_SM2_ID,_WD2_ID,_GTAV_ID)` tuples); `qt_shell/bridge.py` slots; `eel.ts`
    `GowrState` + `getGowrModState`/`installGowrMod`/`removeGowrMod`; `GameDetailPanel` `isGowr` branch
    (install/remove + progress + an in-game activation note). `game_detector` ALREADY had
    `gowragnarok`+`GoWR.exe`. Supabase `games.show_on_launcher=true`. Activation stays in-game.
  - **⚠️ "Play game" WinError 740 (elevation) FIXED.** GoWR.exe (FitGirl repack / some AAA exes)
    ships `requestedExecutionLevel=requireAdministrator`, so the non-elevated launcher's
    `subprocess.Popen` raised `[WinError 740] requires elevation`. `launch_game` now catches winerror
    740 → re-launches ELEVATED via `ShellExecuteW(None,"runas",exe,…)` (a UAC prompt); rc 1223 (user
    declined UAC) → a clean Hebrew message. This is a GENERIC launch fix (helps any elevation-required
    game, not just GoWR).
  - **Toast → TOP-center + narrower action buttons** (user report). The status toast was `top-6`
    (overlapping the game banner); the user wanted it TOP-center (NOT mid-screen — a first attempt
    that centered it vertically was wrong). `App.tsx` → `fixed top-5 left-1/2 -translate-x-1/2`
    rounded-2xl + ring. The action-buttons column is capped `max-w-[190px]` (all games) — "a touch
    narrower" per request.
- **✅ Language-label patch "ערבית"→"עברית" — beta.1 RE-PUBLISHED (2026-07-04, like CP2077/SM2).** The
  in-game Text-Language menu listed the Hebrew-slot option as **"ערבית" (Arabic)**; renamed it to
  **"עברית"** so users pick a menu entry that says Hebrew. The language names are real MSGS_TXT strings
  (corpus id **764**, EN="Arabic", the ONLY `ערבית` in the spine — the list at ids 743-768 shows each
  language's Hebrew name: יפנית/אנגלית/צרפתית/…). Changed `hebrew.json["764"]="עברית"` → rebuilt WAD
  → re-bundled (launcher assets) → re-published beta.1: `gh release upload v1.0.0-beta.1 --clobber`
  (new zip sha `f34d70838aaf3bd572ed1a4cdde20a64c8b34d5884e24b03861dd72e7939fb6b`, 2,709,009 B) +
  Supabase `mod_version_history` sha/size. **Only the ARABIC WAD is edited** (the slot the user runs);
  to also make the Arabic option read "Hebrew" while the UI is in English/other, each
  `r_lang_<lang>.wad`'s id-764 would need editing (a future cross-locale pass, like CP2077's 18-locale
  static archive). **Re-published AGAIN** for the activation-copy change (zip sha `a5eb31d0428d…`,
  2,708,987 B + Supabase). **ALL GoWR activation MESSAGES now say to select "עברית"** (not "العربية"):
  the launcher panel note + install toast (`GameDetailPanel` `isGowr` / `main_eel` `_run_gowr_install`),
  the release `install.py` + `קרא_אותי.txt` + `pack_and_release.py` notes + the repo `README.md`.
  **Watch Dogs 2 got the SAME in-game label fix in its MOD (beta.4 — done by a PARALLEL session;
  Supabase + `_WD2_BUNDLED_VERSION` both `1.0.0-beta.4`); its launcher note + install toast were
  updated to "עברית" here too** (WD2's "Arabic" label lives in the oasis strings, NOT the
  main_english.loc language list 698036-698063). **⚠️ Concurrency note:** a parallel session also added
  a **Worker-DOWNLOAD path** for native appliers — `_gowr_download_payload` / `_GOWR_SLUG=
  "godofwar-ragnarok-hebrew"` + generic `_native_download_payload`/`_native_latest_version` — so GoWR
  pulls the latest WAD from the Worker with the bundled WAD as OFFLINE FALLBACK (the slug is in
  `steam_mod_worker/src/index.js` but UNDEPLOYED → currently always falls back to bundled). Shipped in
  launcher **dev_build 43 (BUILD_ID `20260704230155`)**. `main_eel.py` is being concurrently edited by
  another session — always `Read` before `Edit` + `py_compile` before every build.
- **⚠️ In-launcher language SWITCH (אוטומטי/עברית/אנגלית) is NOT safely feasible for GoWR — by design,
  do NOT attempt a blind edit.** GoWR stores the ACTIVE text language ONLY in a **binary**
  `%USERPROFILE%\Saved Games\God of War Ragnarök\6144\userpreferences` (696 B, magic `DjIj`, packed
  struct, almost certainly checksummed) — NOT in `settings.ini` (graphics only) and NOT in
  `exec\boot-options.json` (a PlayGo content manifest listing which lang packs exist: en/fr/…/ar/ja —
  not the active selector). Editing that blob risks corrupting ALL the user's preferences/saves and
  violates the GoWR "NEVER touch Saved Games" rule (unlike SM2's clean HKCU DWORD / CP2077's JSON). So
  there is **no `game_language.LANG_CONFIGS` entry** for GoWR; activation stays the one-time in-game
  toggle (the install note tells the user). Finding the language offset would need an in-game A/B diff
  + a checksum bypass — not worth the corruption risk.
- **🐛 IN-GAME BUG DIAGNOSED (2026-07-05, user reported garbled/empty/English subtitles) — 313
  UNTRANSLATED Arabic-only dialogue lines.** The "100% translation" was measured against the 48,886
  EN∩AR translatable set, but the shipped `r_lang_ar.wad` has **49,199 ids** and **313 of them are NOT
  in `hebrew.json`** (they are **Arabic-only** — present in `arabic.json`, absent from `english.json`,
  so the original run skipped them with no EN source). At build they fall back to the pristine **Arabic**,
  and since `inject_hebrew` **WIPES the Arabic glyphs from the atlas** (to make room for Hebrew + raised
  Latin), those 313 render as garbage/tofu in-game (the user's "מכורסח/סימנים מוזרים" screenshot: a Hebrew
  speaker name `ת'ור:` — resolved from a translated name string — over an Arabic-garbled dialogue value).
  Deployed-WAD audit (`_bug_diag.json`, `work/gowr_wad.extract`): **47,829 Hebrew · 312 Arabic(garbled) ·
  1,014 English · 26 empty**. The 1,014 "English" are **mostly legit codes/proper-nouns** (`RuneAttribute6`,
  `WAD`, roman numerals, `© Sony…`) — NOT bugs; only ~30 are real half-translated leaks (`half_english.json`).
  **Cue-hash match to English is UNRELIABLE** (the `[[S:…:HASH]]` hash groups a whole SCENE, not a line —
  id 100002 AR="When I came to these shores" mis-matched EN="The boy's mother is dead") → **the Arabic is
  the only reliable source; translate the 313 Arabic→Hebrew.** **FIX = delegate** ([[delegate-all-translation]]):
  self-contained handoff `games/godofwar_ragnarok/agent_handoff_fix/` (`to_translate.json`=313 {id:arabic},
  `get_batch.py`/`merge_batch.py` loop with anti-cheat [reject: no-Hebrew / Arabic-left / dropped-cue /
  newline-mismatch], `INSTRUCTIONS.md`). After the agent fills `done_translate.json` → merge into
  `work/hebrew.json` (backup + per-id guard) → `python work/build_wad.py` → deploy → re-publish on "פרסם".
  Also scanned: **`gender_oracle_suspects.json` = 20 addressee gender conflicts** (GENDER_TASK.md — Arabic
  vs Hebrew, e.g. id 100001 "אתה אל…" should be "את"; ~half are false-positive descriptions the agent filters).
- **✅ 313 FIXED + DEPLOYED (2026-07-07) — garbled + empty subtitle bugs RESOLVED.** A Google/Antigravity
  agent translated all 313 Arabic→Hebrew via `agent_handoff_fix/` (loop → `done_translate.json`). Independently
  verified (never trust the agent's "done"): 0 no-Hebrew / 0 Arabic-left / 0 dropped-cue / 0 copies; only
  **id 137887 needed a structural fix** — it's a 30 KB DATA blob (a MIMIR minigame callout + a 934-line
  `>vo_..._stem` cinematic-stem list); `merge_batch.py`'s `.strip()` had removed its trailing `\n` → restored
  it deterministically (only the ONE visible Arabic line translated, the whole stem block byte-preserved).
  Merged into `work/hebrew.json` (backup `.bak.fix313.<ts>`, per-id ADD-only guard — all 313 were genuinely
  absent) → **49,387→49,700 keys** → `python work/build_wad.py` (delta +301,824 B) → deployed to Game Lab.
  **Re-audit of the deployed WAD: Arabic-garbled 312→0, empty 26→1, Hebrew 48,176.** The two biggest reported
  bugs (garbled + empty subtitles) are closed. **⚠️ GENDER is UNRELIABLE for GoWR — do NOT blind-flip.** The
  id-join oracle produced ~19/20 FALSE POSITIVES: AR and HE at the same id are DIFFERENT lines (e.g. id 103897
  HE="אתה בסדר!" vs AR="את יודעת מי אני?", id 112134 HE="אטראוס... אתה בבית" vs AR addresses a female) — the
  Hebrew is CORRECT and flipping it would INTRODUCE bugs. Only ~1 (id 100001 "אתה אל"/"أنتِ إلهة" = same short
  line) is a genuine same-line gender error. So the gender-flip is NOT worth an agent round (risk > reward);
  the id≠same-line problem is the same one that made cue-hash EN-matching unreliable. Left un-run.
- **✅ 30 half-English UI/cue strings FIXED + DEPLOYED (2026-07-07, `agent_handoff_english/`).** Bug #2
  ("some subtitles/UI still English") = 1,022 English/code ids in the WAD, of which **~992 are legit
  codes/proper-nouns** and **30 were real partial translations** (Hebrew start + English continuation —
  audio-cue descriptions like `[HeavyAttackButton] to ignite oil`, the Blind Guest paragraph, PS privacy text).
  A Google agent completed them via the handoff (`to_translate.json`=30 {id:{he_partial,en,ar}},
  `get_batch.py`/`merge_batch.py` anti-cheat: tokens-multiset unchanged / `\n` unchanged / has-Hebrew /
  English-word-count REDUCED, brands exempt). **Independently verified** (never trust "done"): 0 token/nl
  mismatch, translations genuinely good (e.g. "Audio Cues can be enabled from the Accessibility Menu" → "ניתן
  לאפשר רמזי שמע דרך תפריט נגישות"). **CAUGHT 2 validator-hacks the agent made to pass `english-not-reduced`
  on URL/title-heavy lines** — it shaved `www.` off `playstation.com` URLs and transliterated the product
  title `God of War Ragnarök`→`God of War ראגנארוק` (a Hebrew-Latin hybrid) just to reduce the Latin count;
  **restored both deterministically** (regex, 3 entries) keeping the rest of the agent's work. Merged into
  `work/hebrew.json` (backup `.bak.eng30.<ts>`, per-id UPDATE guard — only if unchanged since scan; 30/0) →
  rebuilt → deployed to Game Lab. **LESSON: an `english-not-reduced` validator wrongly pressures the agent to
  degrade legit URLs/titles on lines whose only Latin IS a URL/brand — the guard should whitelist URL paths +
  product titles, or exempt lines whose partial already had only whitelisted Latin.**
- **🐛 BIGGER MISS FOUND — 591 FULL-ENGLISH untranslated strings in `hebrew.json` (2026-07-07, user
  pushed back "היו הרבה באנגלית מלאה").** The original "100% (48,885/48,886)" was measured by KEY PRESENCE,
  NOT actual Hebrew content — so entries whose translation slipped through as English (the `validate()`
  name/code passthrough over-accepting) were counted "done". A rigorous deployed-WAD + `hebrew.json` audit:
  of 49,700 keys, **48,676 Hebrew · 25 legit-blank (EN+AR both empty, NOT a bug) · 1 `\x{A0}` code · 48
  code/roman-only · 950 no-Hebrew, of which 591 are REAL translatable prose/UI** with a lowercase English
  word (`"Did you want to find Father or not?"`, `"A bow fit for a prince of Asgard."`, `"It is time for
  Odin to face justice."`). Split: **402 plain English + 189 Old-Norse-flavor** (`Hvat er at gerast?!` —
  the game keeps these Norse; the Arabic at the same id is a DIFFERENT line, so AR is useless → EN is the
  only source; Norse → transliterate to Hebrew letters). The "empty subtitle" the user saw = the 313 garbled
  (now fixed, render blank/tofu when font-wiped); coverage audit confirms **0 WAD ids missing from
  hebrew.json, 0 Arabic-garbled** after the 313 fix. **FIX = delegate** (`agent_handoff_fullenglish/`:
  `to_translate.json`=591 {id:{en}}, `get_batch.py`/`merge_batch.py` anti-cheat [reject: no-Hebrew /
  tokens-changed / `\n`-changed / any Latin word ≥3 left except brands], `INSTRUCTIONS.md` — plain→Hebrew,
  Norse→Hebrew transliteration). After the agent fills `done_translate.json` → merge (backup + per-id guard)
  → rebuild → deploy → re-publish on "פרסם". **LESSON: "100%" must be measured by actual has-Hebrew content,
  NOT key presence — a `validate()` name/code passthrough silently lets real prose through as English.**
- **✅ 591 FIXED + DEPLOYED, then +336 MORE found + queued (2026-07-07).** The agent translated the 591; I
  **independently verified** (0 no-Hebrew/tokens/Latin/copy) and **CAUGHT a newline-encoding corruption**: the
  agent's `dump_batch.py` converted GoWR's literal `\n` (2-char in-value break) into REAL 0x0A on 24 entries —
  GoWR uses BOTH per-entry (a real 0x0A cue-separator + literal `\n` internal breaks; proven from 634 working
  entries). Fixed deterministically (`fix_newlines.py`: rebuild each HE with its EN's exact break SEQUENCE,
  `re.escape` the literal — a bash-mangled regex first mis-flagged all 24) → merged (guard 591/0) → rebuilt →
  deployed. **Deployed-WAD re-audit: FULL-ENGLISH prose 348→0, Arabic-garbled 0, Hebrew 48,767.** THEN an
  EXHAUSTIVE sweep of ALL remaining non-Hebrew found **336 MORE the lowercase-word-≥3 filter had missed**:
  short capitalized dialogue (`Got it.`/`Hey, Loki.`/`Just do it.`/`For Lejre!`/`Quick Start`) + ~100
  **Old-Norse combat callouts** in plain/accented ASCII (`Skál!`, `Veggur bifröst!`, `Dynja íss!`,
  `Dauðahögg!` ×18 dup — my Norse regex only had þ/ð/æ, missed á/í/ö). Appended to the same handoff
  (`to_translate.json` 927 total; `remaining2.json`). **✅ ALL 927 DONE + DEPLOYED (2026-07-07)** — agent
  finished, independently verified (0 no-Hebrew/tokens/**newline-sig**/Latin/copy — this round the agent kept
  newlines correct), merged (336 guard 336/0) → rebuilt → deployed. **FINAL deployed-WAD audit: Hebrew 49,102 ·
  Arabic-garbled 0 · empty 26 (legit-blank) · REAL translatable non-Hebrew remaining = 0.** The mod is now
  100% Hebrew; the ONLY non-Hebrew left = **71 genuine junk** (roman I–X, aspect ratios 4:3, multipliers 1.5x,
  button letters L/R/C, `Temp N.A.W. Desc` dev placeholders, `RuneAttribute6`, Sony brand). Local Game Lab
  updated; public re-publish (GitHub clobber + Supabase sha/size) awaits "פרסם".
  **LESSON: a lowercase-word filter misses short Title-Case dialogue AND accented-but-ASCII Norse — sweep by
  "non-Hebrew, non-junk", not by "has a lowercase word".**
- **~59 remaining mixed Hebrew+Latin entries are NOT bugs (assessed, left by design 2026-07-07).** A full
  deployed-WAD audit finds ~59 ids with Hebrew + a Latin word: **~1 = the 137887 stem-list data-blob**
  (`>vo_..._stem`, not visible), **~20 = DEV/DEBUG journal keys** (`Quest_Treasure_Temp_Objective`,
  `XPL_Midgard1_...`, `*TEMP*`, `wads`, `Lams` — not player-facing), **~25 = enemy/item NAMES with a Latin
  gloss** (Draugr/Wulver/Tatzelwurms/Brood/Ancient/sauroter/Valor — render fine as "עברית Name", bestiary/tip
  text, arguably intentional), **~10 = tech/brand terms** (DualSense™/FidelityFX/Checkerboard/Reflex —
  legitimately Latin). **None are the garbled/empty/visible-English bugs the user reported** — those are all
  closed. Optional future polish only if the user flags the name-glosses specifically (would be a small
  delegate pass to drop the redundant Latin name).
- **Font polish (2026-06-18, after in-game review):** `inject_hebrew` calibrated past the
  first readable build — (a) **vertical**: `y_off = cell_h - baseline_in_cell` (engine is
  first readable build — (a) **vertical**: `y_off = cell_h - baseline_in_cell` (engine is
  baseline-anchored: `bitmap_bottom = line_baseline + y_off`, native caps use y_off=0; the
  earlier `37 - baseline_in_cell` put Hebrew ~16 px too high); (b) **soft engraved look**:
  native copperplate glyphs peak at alpha ~180 (NOT 255) and are dominated by a mid-range
  glow (~84-100% box fill) — so render supersampled + add a `GaussianBlur` GLOW
  (`max(sharp, glow*1.4)`, peak clamped to 180) to reproduce the per-letter shadow the user
  asked for; the old hard `a[a<28]=0`/max-255 looked flat + "מקוטע". `:`/`.`/`,` stay native
  baseline glyphs (also used inside `[Icons:…]` tokens — not safe to move). `build_wad.py`
  reads `hebrew.json` each build, so font + translation co-ship.


