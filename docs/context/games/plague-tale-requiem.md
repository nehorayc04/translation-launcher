## A Plague Tale: Requiem — TRANSLATION 100% + GENDER REVIEW 100%, full mod BUILT LOCAL, NOT published (2026-07-10)

Both the translation AND a full addressee/number **gender review vs the game's own Arabic** are
DONE; the complete Hebrew mod artifact is built + verified locally. **NOT deployed to the live game
and NOT published** (both gated — deploy overwrites game files, publish needs an explicit "פרסם").

- **Translation:** 17,964/17,964 real translatable lines (2,697 non-translatable markers kept as the
  pristine Arabic/native, per `fleet/marker_keys.json`) → `fleet/hebrew.json` (20,661 total keys → 17,964
  values; `hebrew.json.bak.gender` = the pre-review baseline).
- **Gender review (new this session):** the fleet LLM defaulted to masculine-singular and ignored the
  Arabic's feminine/plural. Built a dedicated review pass under `games/plague_tale_requiem/fleet/gender/`
  — reviewed **all 4,148 lines whose Arabic carries a gender signal**, applied **785 pure-inflection
  fixes** through a SAFE merge guard (accept only: no niqqud/foreign, STRUCT tokens preserved, non-Hebrew
  scaffold IDENTICAL, each changed Hebrew word Levenshtein ≤3 → blocks any LLM paraphrase/degradation).
  hebrew.json stays **17,964 (zero data loss)**; fixes protected by a `gender_overrides.json` overlay that
  `pull_pt.sh` re-applies after any bank rebuild. `gender_oracle` before/after on the strict-determinable
  subset: addressee mismatches **45→30 (15.8%→10.4%)**, 15 clearly resolved there (most of the 785 are
  plural/referent/feminine-verb the strict oracle doesn't classify). Full hardening lessons →
  [[fleet-qa-review-hardening]] (PID-lock singleton worker, heartbeat-mtime heal, cp1255-safe detached
  launch, Scheduled-Task persistence, "disabling a task ≠ killing its running instances", Tailscale off-LAN).
- **⚠️ 43 one-word interjections** (Yes./What?/No.../*Cough*/Boom!/Amicia!…) the throttled fleet stalled on
  were translated by Claude one-time **at the user's explicit override** of [[delegate-all-translation]]
  ("תרגם אתה את ה43 שורות חד פעמי") — merged via `agent_tail/`.
- **Full mod built + verified:** `python work/build_proof.py --hebrew fleet/hebrew.json` →
  `work/_proof_tt23.pc` (2,053,051 B, 17,964 strings, RTL baked via `pt_rtl.to_stored`). Verified:
  `pt_text.load_map` sample **300/300 == to_stored(hebrew)**, 0 stray Arabic (only the 2,697 markers kept,
  all Latin/CJK/empty). **Codec gotcha fixed:** the tt format uses `"` as the value delimiter so a value
  can NEVER contain ASCII `"`; 4 Hebrew values had gershayim typed as ASCII `"` (מנכ"ל / בע"מ / two dialogue
  scare-quotes) → deterministically replaced with the Hebrew gershayim **`״` (U+05F4)** in hebrew.json
  (backup `hebrew.json.bak.gershayim.*`). Font gate was already solved+deployed (David Libre Hebrew glyphs
  in `FONT/ENGLISH.DPC`).
- **Fleet cleaned up:** PTGenderPull/Progress/Desk scheduled tasks disabled + local gender worker/pusher
  killed (remote PID-locked workers self-exit when their slice drains). The zombie `pt_progress.py` that
  had pinned the site to 100% were already killed; the live snapshot now reflects the gender pass.
- **NEXT (gated):** deploy `_proof_tt23.pc` → the game's `TRTEXT/tt23.pc`+`.IGN` (`build_proof.py --deploy`,
  backup `.he_backup`, revert `--revert`) for the user's in-game confirm; then publish like SM2/WD2/Anno
  (GitHub `plague-tale-requiem-hebrew-mods` + Worker slug `plague-tale-requiem-hebrew` + Supabase `games`
  id=`plague-tale-requiem` + `mod_version_history`) — ONLY on an explicit "פרסם".

### ✅✅ PT FONT — the SIZE MODEL is PROVEN to the pixel, and the dots are ROOT-CAUSED (2026-08-11)

Deployed + verified. Supersedes the "size is engine-locked / atlas ink is the only lever" reading
below. Memory [[bitmap-font-size-is-box-over-ink]]. Tools:
`work/font/{_diag_policy,_diag_span,_verify_deployed,_measure_shot}.py`.

- **THE MODEL, validated on a fresh in-game capture:** `screen_ink = REQ × ink_h / declared box_h`.
  Start-screen prompt REQ=48 ⇒ `48 × 40/59 = 32.5` predicted, **32.4 measured** (900p capture,
  normalised ×1.2 — the game runs `Resolution 1600 900`). **REQ is PER SURFACE** — the settings menu
  is a different widget at REQ≈30, so the SAME build renders **20.3 px** there. That single fact
  explains several rounds of contradictory "too big / never changes" reports: they were measured on
  different screens. **Never carry a size measured on one surface to another.**
- **The vanilla policy, measured across ALL 8 shipped fonts: a TIGHT box** — `ink/box = 0.955-0.985`
  (mean 0.97), gap top 1-2 px / bottom 0-1 px, and `box_h` AND `adv` BOTH per-glyph (BIG_ARABIC: 36
  distinct box heights over its Arabic, 23 over its Latin). A tight box makes every LINE
  self-normalise ⇒ a line containing ל renders ~18 % smaller than one without = the inconsistency.
  We therefore ship a **UNIFORM box** (one shared baseline, `adv` identical); the price is the wasted
  head/foot room, which makes `BOX_H` the single honest size knob.
- **🔴🔴 THE DOTS = 22,191 px of the slot's OWN Arabic ink left alive.** The em-box loop cleared only
  the NEW (smaller) box; a smaller box makes the engine DOWNSCALE, and its mip/bilinear tap reaches
  far enough to drag those leftovers in as dots beside every letter (a tight box never showed it —
  no downscale). Fix: clear the **FULL ORIGINAL** box in alpha + colour + rmap and mark it dirty.
  Verified on the deployed file **22,191 → 0**, and confirmed clean in the in-game zoom.
- **The second size knob, once the box is uniform:** `screen = REQ × body/(max_ascent+max_descent)`,
  so the typeface's two EXTREME glyphs set the size of all 21 ordinary letters. Ranked all **422**
  Hebrew-complete fonts on the machine: Open Sans Hebrew Light is **89th** (lamed 1.18×body, tails
  0.38×body, ratio 0.645) vs Mehir 1.07/0.20, Miriam 1.15/0.20, Levenim 1.15/0.25. Rather than swap
  the calibrated typeface, `cap_span()` compresses **only** lamed's rows above the body top and the
  finals' rows below the baseline (`LAM_CAP=1.12`, `DESC_CAP=0.30`) — the other 21 letters stay
  byte-identical. `BOX_H 65 → 59`, +10 % size, no visible distortion.
  ⚠️ A font-ranking script that skips the cmap check ranks **Latin-only** fonts FIRST (PIL renders 27
  identical `.notdef` boxes = a fake ratio of 1.000) — require every codepoint present AND ≥20
  distinct glyph names.
  ⚠️ A vertical-clipping check must ignore the LEFT/RIGHT edges when the box width is deliberately
  tight, or a correct build reports 26/27 "clipped".
- **Deployed state:** 27/27 glyphs · box uniform 59 · `adv` identical 81.0 · halo 0 px · 0 clipped ·
  ratio 0.678 ⇒ menu ~20.3 px. In-game zoom shows clean, correctly-proportioned RTL Hebrew.
- **🔴🔴 WEIGHT: calibrate against the language you SIT NEXT TO, not the script you replace.** The
  weight had been matched to the game's own ARABIC (0.138 ink density, 5.5 % stroke) and the Hebrew
  read "washed out" beside the English. Arabic is a genuinely thin script; Hebrew is not. The right
  ruler is the **vanilla ENGLISH in the SAME widget** — one screenshot with Text-language=English.
  Measured there: English **stroke/x-height 0.167** (2.0 px stroke on a 12 px x-height) vs our
  shipped Light **0.100** — 40 % thinner. Family weights at body 30: Light 0.100 · Regular 0.133 ·
  **Regular + `WEIGHT_SS=2` → 0.161** ✅ · Bold 0.241 · Alef-regular 0.172.
  **`WEIGHT_SS` is a sub-pixel weight knob**: `ImageDraw.text(..., stroke_width=N, stroke_fill=255)`
  in the SUPERSAMPLED domain = `N/SS` real px of extra radius, so at SS=8 `N=2` adds exactly
  +0.5 px — continuous weight tuning without leaving the approved typeface. ⚠️ It also grows the ink
  by ~1 px, so re-check the size. Result: stroke 2 px → **5 px** (shipped 5-8), AA mid/solid 0.42 →
  **0.25** (shipped 0.24). **Hebrew body should land BETWEEN the Latin x-height and cap** — measured
  in-game English x-height 11-12 / cap 16, Hebrew at 14 reads correctly matched.
- **🔴🔴 NORMALISE THE GLYPH EXTENTS IN THE SUPERSAMPLED DOMAIN, NEVER ON THE FINISHED BITMAP.**
  `render_set` anchored each letter to the MEDIAN ink-top and let a letter whose ink starts a row
  lower keep a transparent row — invisible when the glyph is magnified, but with a FIXED box the
  engine MINIFIES ~0.46× and that one row is the difference between a 14 px and a 15 px letter
  (measured in the deployed atlas: **א ד ו ז צ ש at 30, the other 14 at 31**) = the user's
  "אין עקביות בין האותיות". **And the obvious fix is a trap**: resampling the finished 31 px bitmap
  stretches only SOME letters (30→31) and leaves the rest untouched, so the resampled ones come out
  softer — a NEW inconsistency for the old one. Do it inside `_render_set_ss` at SS=8, where the
  same correction is 240→248 rows (8× finer than a pixel) and EVERY glyph takes the identical path.
  Now: ordinary letters **top 16 / bottom 46 / height 31, one value each**; descenders one body +
  one tail; and — verified by simulating the engine's own bilinear minification — the SCREEN result
  is **one height, one baseline** (was [14,15] / tops [7,8]).
  ⚠️ **The gaps are part of the metric.** Cropping each glyph to its ink and calling that the ascent
  dropped **yod onto the baseline** (it must float ~9 rows above it) — the user's "רק ה-י' ירדה
  למטה". Keep every gap and carry it into `ascent`; resample only the INK.
- **🔴🔴 THE DECLARED BOX NEEDS A 1 px TRANSPARENT MARGIN ON EACH SIDE — measured from the vanilla,
  not assumed.** Every shipped glyph leaves `gapL/gapR = 1/1` (and 1/0-1 vertically); ours had
  **0/0**, the ink touching the box edge. Under bilinear minification the outermost column is
  blended away, and on a letter whose defining feature IS an edge stroke that is fatal: **ה lost its
  left leg and read as ר** ("לשולחן העבוד**ר**") = the user's "האותיות בסוף המשפט נחתכים". Fix:
  `PAD_X = 1` — draw the ink at `+1`, declare the box `gw + 2`, and **pay the 2 px back in `bx`**
  (advance = box width + bearing) so the tracking does not open up. Verified after: Hebrew AND the
  repacked Latin both at `gapL/gapR min = 1`.
- **🔴🔴 …AND `PAD_X` DID NOT FIX IT — "האותיות בסוף המשפט נחתכים" IS A LINE OVERFLOW, NOT A GLYPH
  DEFECT (2026-08-11). Four rounds of font work chased the wrong thing.** The tell that ends the
  argument is cheap and belongs FIRST: **read the DEPLOYED TEXT back and compare it with the
  render.** `tt23.pc` really holds `MENU__START_PC = 'לחץ על מקש כלשהו'`, but the start screen
  draws `לחץ על מקש כלשה` — **the final ו is gone ENTIRELY**; on `MENU__QUIT = 'צא לשולחן העבודה'`
  the final ה loses its detached left leg and reads as **ר**. Data right, engine clips — and in RTL
  the clipped end is the LEFT = the end of the sentence.
  - **The size dependence is the proof.** The settings rows (a wide, right-aligned column) measure
    **pixel-perfect — every letter, including a line-final ה and ת, within ±0.7 px of its atlas ink
    width**; only the big centred/left-aligned widgets (start prompt, title) clip. A glyph defect
    cannot be surface-dependent; a widget too narrow for the line is.
  - **ה and ו are the canaries.** ו is a 5 px stroke at the far left of its box, so a 2-3 px clip
    erases the whole letter; ה's left leg is a DETACHED contour, so the same clip turns it into ר.
    Every other letter merely loses an edge column nobody notices. **When a user reports "ה looks
    like ר", suspect a line-end clip before suspecting the font.**
  - **🔴 DO NOT diagnose this with mismatched alpha thresholds.** Measuring the rendered ink at
    `thr=110` while measuring the atlas at `thr=90` made a perfectly good ת look "6 px short" and
    burned a whole round on a phantom clip in the title. Use the SAME threshold on both sides and
    settle identity by putting the rendered glyph NEXT TO the atlas glyph at the same ink height —
    the shapes matched exactly (ת kept its foot, ה its detached leg).
  - **THE FIX MUST SCALE WITH LINE LENGTH ⇒ shrink the BODY, never the tracking.** Measured against
    the vanilla English our letter gap is ALREADY ~19 % tighter than English, so cutting tracking is
    both wrong and nearly ineffective. `LADDER_INK[0] 30 → 28` makes every line **7 % narrower**
    (start prompt 238 → 220 px = 18 px recovered against a ~6.5 px clip; `צא לשולחן העבודה` −26
    atlas units) while preserving everything already approved — letterforms, uniformity, weight
    ratio (stroke/body stays 0.167), vertical metrics. ⚠️ `SIDE_BEARING` is derived from
    `LADDER_INK[0]`, so the tracking ratio follows the body automatically.
  - **UNIVERSAL: Hebrew is all cap-height, so a Hebrew line is WIDER than the Latin the widget was
    sized for. On an engine that clips instead of shrink-to-fit or wrapping, that overflow is
    invisible everywhere except the last glyph — which is exactly the complaint you will get.**
  Diagnostics kept: `work/font/{_diag_lineend,_diag_pos,_diag_identify,_diag_startline,_diag_lineoverlay}.py`.
- **NO EXTERNAL MOD — confirmed by inspection** (the user asked): the game root has no `dinput8.dll`,
  no ASI loader, no `mods\` folder. We edit the **vanilla files in place** —
  `FONT\ENGLISH.DPC` and `TRTEXT\tt23.pc`+`.IGN` — each with its pristine `.he_backup` beside it.
- **🔑 `LangDef.tsc` (game root, 974 B, PLAIN TEXT) is the language table** —
  `AddLangDefine <TSC_ID> <MPEG_ID> <VR_ID> <CONSOLE_LANG> "<WWISE_DIR>"`. Arabic is
  `23 -1 09 ARABIC "English(US)"`, and **TSC_ID == the `TRTEXT\ttNN.pc` number** (23 = our slot ✓).
  Japanese sits commented-out (the repack's own note: copy `_GOGLangDef.tsc` over it to expose
  Japanese) ⇒ **this file decides which languages appear in Settings.** `ITALIAN`/`POLISH`/… have no
  `BIG_<LANG>` font, so `CONSOLE_LANG` (NOT `VR_ID` — Arabic and Korean share VR_ID 09 yet use
  different fonts) is what routes a language to its font family. **Untested lever:** pointing the
  Arabic row at a Latin `CONSOLE_LANG` would move Hebrew off the magnified BIG_ARABIC family onto
  BIG_FONT/SMALL_FONT (correct per-context sizes, no ~2.8× upscale) — but it very likely also turns
  the engine's RTL positioning off, which would require re-baking all 17,964 lines with a different
  transform. High value, high risk; test with a mixed Hebrew+digit line so a tofu render still shows
  direction, and revert by restoring the 974-byte file.

### ✅ PT FONT — FINAL CALIBRATION, every number landed on the English reference (2026-07-24)

The shipping build is no longer tuned by eye: all four metrics were derived from the user's own
English|Hebrew side-by-side ([[screenshot-is-a-calibrated-ruler]]) and then **read back out of the
DEPLOYED file** to confirm. Shipping constants in `work/font/build_hebrew_font.py`:
`DEF_FONT=Assistant-Regular · LADDER_INK[0]=21 · SIDE_BEARING=1.1 · CONDENSE=1.00 · SS=8 ·
EDGE_SOFT=0.0 · curve (a-22)*1.90, floor 10 · CENTER_IN_LINE=True`.

| metric | shipped | English reference |
|---|---|---|
| body | 21 atlas px → **69.5** screen | cap **69** |
| letter gap | **17.6 %** of body | **17.6 %** |
| cap line | **20 of 20** standard letters identical | — |
| AA mid/solid | 0.43 at 21 px | 0.24 at 62 px (same edge character once scaled) |

**⚠️ CAP-MATCH STILL READ AS "TOO BIG" — dropped to 17 px atlas (2026-07-24, confirmed in-game).**
Matching the English CAP (21 px → 69 screen) was correct arithmetic and still felt oversized,
because English UI text is mostly lowercase so a reader compares Hebrew to the **x-height** (~51),
not the cap — and Hebrew has no lowercase, so at equal cap it carries far more mass. Shipping size
is now **`LADDER_INK[0]=17` (≈56 screen), the perceptual midpoint between cap and x-height**, with
`SIDE_BEARING` re-derived to **0.4** (keeps the 17.6 % gap). `_preview_weight17.py` confirmed
Assistant-Regular still lands at the English's 12 % stroke at 17 px (the heavier fonts came out at
24 %). **In-game capture (`_autocheck.py --attach`, fresh pid past the stale-instance guard) shows
the start-screen Hebrew clean, uniform (standard letter 28 px at 1080p, no noise, no black frame,
correct RTL) at a clearly reduced size.**
**🔑 The on-screen magnification is RESOLUTION-DEPENDENT** — ~3.31× on the user's ~3250-wide
reference shot but ~1.65× at 1920×1080. So absolute-px targets do not transfer between captures;
only the RATIO of Hebrew-height to English-height within ONE frame is comparable, and the menu
never shows both scripts at once. The cap/x-height reasoning (a resolution-independent ratio) is
what drives the size, not a pixel count.

Four universal rules came out of this round, each paid for with a wrong build:

- **🔴 A unified cap line needs BOTH anchors.** Forcing only the ink TOP left the variance to
  reappear at the BOTTOM: the letters all sit on one baseline, but a curved foot bleeds one AA row
  further than a flat one, so the split merely moved (13 letters at 20 px, 7 at 21 px). Height is
  bottom-minus-top — pin both, and exempt only the glyphs that genuinely differ (here lamed rises
  above the cap, yod stops short of the baseline, five finals + qof drop below it).
- **🔴🔴 Define the anchors by SUBSTANTIAL ink (>=128), never by the first non-zero pixel.** The
  faint fringe row moves with the alpha curve, so a fringe-based anchor makes the unification
  curve-dependent — sharpening the curve silently broke a cap line that had been perfect an hour
  earlier. And the first attempt, `t = min(t, top)`, only ever pads upward, so the letters that
  were already too TALL kept their extra row and nothing was unified at all.
- **🔴 TARGET ≠ RENDERED, and the offset MOVES with the curve.** A target of 21 px shipped a 22 px
  box under the soft curve (5.5 % over the English cap) and exactly 21 px under the crisp one.
  **Always read the box heights back from the deployed artifact** instead of trusting the constant.
- **🔑 Pick the alpha curve at the MAGNIFIED size, not in the atlas** (`work/font/_preview_curve.py`
  renders 4 candidates at the shipping body and upscales them ×2.8 like the GPU). The bilinear
  magnification supplies all the smoothing that exists, so a blur added in the atlas is applied
  twice and the result is mush — `EDGE_SOFT` went 0.15 → **0**, against the usual instinct. Crisper
  also hands DXT5 fewer mid-tones to quantise. One image replaced a game launch.

⚠️ **Do NOT re-try multi-font injection to beat the blur.** Injecting Hebrew into the small
subtitle font was already tested in-game and did NOT shrink subtitles — the game hardcodes
BIG_ARABIC for every Arabic-slot surface, so the ~2.8× magnification is a genuine ceiling
(the game's own menu font is magnified only ~1.24×). The comment at `FONT_OIDS` records this.

### 🔒 PT FONT — the NOISE was OURS (fixed); the SIZE is engine-side except for ONE untested lever (2026-07-12)

Many in-game rounds were burned chasing "the Hebrew is too big" and "there is still noise in the
subtitles". Both were finally settled with OFFLINE evidence. **Neither is fixable by editing the
font.** Everything below is reusable for ANY bitmap-atlas game font.

- **🔴 ON-SCREEN SIZE IS NOT IN THE FONT FILE — proven 6 independent ways.** The engine NORMALIZES
  every font to a requested point size that lives in the game's compiled UI code:
  1. **Atlas-shrink test** (Hebrew rendered 40→28→18 px, tight box): text stayed the SAME size and
     merely went BLURRY ⇒ the engine upscales whatever it finds to a fixed target. Kills the
     "box height ∝ screen" and "ink ∝ screen" models at once.
  2. **em-box test** (declared box much larger than the ink, so the glyph fills ~50 %): no change ⇒
     the engine crops to the ink / ignores box padding.
  3. **Footer is byte-identical in all 8 fonts** (`08 00 00 00 41 00 00 00`) ⇒ no per-font
     size/line-height field in the `Fonts_Z` tail.
  4. **Object census (`_diag_objs.py`): 565 objects, only 3 otypes** — 279 textures
     (`E9659CD1C3F3326D`), 278 materials (`310BB7F1CFC1D4FF`), 8 `Fonts_Z` (`87218B06F6FE91FD`).
     There is **NO separate font-descriptor object**, **no object references a font oid**, and each
     font's `info` block is only 8 bytes (an Asobo name-hash, decodes to nonsense as f32/i32).
  5. **Cross-font atlas comparison kills "atlas ∝ screen" outright**: `C20BD87B` (the *small*
     subtitle font) draws `'o'` at **53 px** in the atlas while BIG_ARABIC draws `'o'` at **47 px** —
     yet C20 renders SMALLER on screen. Atlas pixel size does not predict screen size.
  6. **No size in ANY editable config**: `LangDef.tsc` (language table only), `InitFont.tsc` (just
     `LoadFont` lines), `All.psc` (1.4 MB bundle of `.tsc` scripts) — grep for
     `font|size|scale|arab|subtitle|hud|ratio|height|zoom` returns **0 hits**.
  ⇒ The size is compiled into `APlagueTaleRequiem_x64.exe` / the binary UI layouts in `DATAS`.
  Changing it would mean patching game code or cracking a 31 GB DPC's UI format — not worth it.
  ⚠️ **Caveat on proof #2 (the one weak link): every past "size test" changed the INK and the BOX
  TOGETHER**, so none of them could separate "size follows the atlas ink" from "size follows the
  declared box". A **single-variable LADDER** now settles it in ONE restart — `LADDER=True` in
  `build_hebrew_font.py` gives all 27 letters IDENTICAL ink and only varies the declared box
  height, in 3 groups interleaved across the alphabet so any sentence shows all three:
  **A `fill 1.00` (= the current build, control) `אדזילןעץר` · B `0.72` `בהחךםנףצש` ·
  C `0.52` `גוטכמספקת`**. Read it: `A > B > C` ⇒ the box drives the size, pick a fill and ship it;
  `A == B == C` ⇒ the size is genuinely engine-locked and proof #2 stands, forever.
  **⚠️ ROUND-1 RESULT: `A == B == C` — and that is NOT the refutation it looks like.** The box was
  extended DOWNWARD into empty atlas space, and under the ordinary model (screen = ink × per-font
  scale) an empty box extension changes nothing either. **So round 1 was confounded too.** The only
  untested single variable left is the INK ITSELF with a tight box → `LADDER_INK = (40, 26, 16)`
  (A control · B −35 % · C −60 %), same interleaved groups.
  **✅✅ ROUND-2 RESULT, IN-GAME: `A > B > C`, unmistakably** — the menu word `תוספות` (every letter
  in group C) rendered visibly smaller than `צא לשולחן העבודה`, and mixed-group words showed three
  sizes inside one word. **⇒ THE ON-SCREEN SIZE FOLLOWS THE ATLAS INK. The whole "the engine
  normalises every glyph to a fixed cell, the size is unreachable" conclusion was WRONG** — it
  rested entirely on the atlas-shrink test (proof #1), which must therefore have been misread.
  The user picked group B ⇒ ship a UNIFORM **26 px** ink (`LADDER=False`, `LADDER_INK[0]=26`).
  **UNIVERSAL — the most expensive lesson of this whole font effort: when several rounds of a
  costly manual test all say "nothing changed", the test is probably CONFOUNDED, not the
  hypothesis. Build a LADDER that varies ONE field across groups in a SINGLE deploy, and before
  believing a NULL result ask whether the variable you moved could have been ABSORBED (round 1:
  empty padding below the ink). A ladder is decisive only if the field you vary is one the
  renderer actually consumes — and a "proven impossible" that rests on ONE old observation should
  be re-tested with a ladder before it is written down as fact.**
- **📐 VERTICAL POSITION: `adv` puts the ink BOTTOM on the baseline, so a small glyph hugs the
  FLOOR of a line box sized for the 79 px Arabic** (the user: "צמוד ללמטה" — a big gap above, none
  below). Fix = centre the ink in the band `[baseline−capH, baseline]`:
  `baseline_eff = baseline − (capH − ink)/2` (127 → 100 for a 26 px ink), applied to the Hebrew
  AND the repacked Latin so they stay on one line. **UNIVERSAL: baseline alignment is correct for
  same-size text; the moment you inject glyphs much smaller than the font's own em, you must also
  re-centre them or they sink to the bottom of every row.**
- **🖨 "It looks like it came off a 1930s printing press" = low-res rasterisation, not the
  typeface.** At a 26 px body a Light stroke is only ~2.6 px, and the old pipeline was `SS=4` with
  a hard contrast boost `(a−14)·1.30` + `a[a<10]=0` that CLIPPED the faint anti-aliasing — chunky,
  unevenly-weighted stems. Fix: **`SS=8`** (free offline) + a gentle `(a−6)·1.10`, `a[a<4]=0` that
  keeps the AA. **UNIVERSAL: a crispness curve tuned at a large body size becomes a defect at a
  small one — re-tune the supersample and the alpha curve whenever the target size changes.**
- **🔴🔴🔴 "לא ישנה כלום" HAD A MECHANICAL CAUSE: a leftover ELEVATED game process + a
  SINGLE-INSTANCE game. Check this BEFORE touching a build, ever again.** The game reads the
  font ONCE at startup and refuses to run twice — a second launch **exits immediately** and
  Windows re-focuses the OLD window, so a user who "restarts" is still looking at the process
  they started hours ago, with the font from that moment. And when that process is **ELEVATED**,
  `taskkill /F` answers **"Access is denied"** from this environment, so nothing automated can
  end it. Every build deployed after it started is invisible, with no error anywhere.
  **It also silently poisoned my own autonomous captures**, which is how it hid for three cycles:
  locating the window by IMAGE NAME grabbed the FOREIGN instance, so reverting the font "changed
  nothing" and even **deleting `FONT/ENGLISH.DPC` outright still rendered perfect Hebrew** — which
  reads exactly like "the game never reads this file". It does; I was photographing someone
  else's window. **The 60-second proof:** `Get-CimInstance Win32_Process -Filter
  "name='X.exe'" | Select ProcessId,ExecutablePath,CreationDate` — an **empty ExecutablePath**
  means the process outranks you, and `CreationDate` vs the deploy time tells you whether it
  could ever have seen your build. Now enforced in code: `_autocheck.game_pids()` accepts **only
  a process whose ExecutablePath it can READ and that equals the exe it launched**, and
  `build_hebrew_font.py --deploy` prints a red warning when any instance is running.
- **🤖 `work/_autocheck.py` — the game now verifies ITSELF: launch → capture → measure → kill.**
  Everything needed turned out to be scriptable: (a) `%APPDATA%\A Plague Tale Requiem\
  ENGINESETTINGS` is **plain text** (`Windowed`, `FullscreenBorderless`, `Resolution`,
  `PosX/PosY`) so the window is fully controllable with no in-game navigation; (b) the exe's
  manifest demands admin, so a plain `Popen` dies with **WinError 740** — launch with
  `__COMPAT_LAYER=RUNASINVOKER`, which makes the AppCompat shim ignore the manifest (safe outside
  Program Files) and needs no UAC; (c) the game is D3D12 so GDI/ImageGrab returns black — capture
  with **dxcam** (DXGI Desktop Duplication); (d) the menu is the first interactive screen and
  already contains Hebrew, so no clicking. It reaches a measurable menu in **~8 s**.
  ⚠️ `%APPDATA%` resolves to the Antigravity sandbox — build the path from
  `SHGetKnownFolderPath(FOLDERID_Profile)` ([[env-redirection-real-home]]).
  ⚠️ It cannot run at all while a foreign instance is alive (single-instance ⇒ our process exits);
  that one action still belongs to the user.
- **📏🔴 THE SCREENSHOT IS A CALIBRATED RULER — measure the target off the USER'S OWN image.**
  A side-by-side of the game in English vs in Hebrew contains BOTH scripts drawn by the SAME
  engine at the same UI scale, so every question ("how much too big?", "how much too thick?")
  becomes arithmetic. `work/_diag_screenshot.py` splits the panels, segments text rows, splits
  rows into letter blobs by empty columns, and reports median letter height / 90th-pct height /
  stroke width / letter gap for each side. Result here:
  `EN x-height 51 · cap 69 · stroke 11.8 % · gap 17.6 %` vs `HE body 86 · stroke 10.5 % · gap
  18.6 %` ⇒ **Hebrew was 1.25× the English CAP** (weight and spacing already matched — only the
  size was wrong) ⇒ target `body = 0.85 × cap` ⇒ `HEB_BODY = 26 × 59/86 = 18 px`.
  ⚠️ **Cut the panel separator out first**: a full-height black bar contributes ink to EVERY row,
  so no row ever reads as blank, the band splitter returns ONE band, and the script silently
  reports a single 648 px "letter". Find columns that are ~100 % ink and exclude them.
  **UNIVERSAL: never eyeball a "make it match" request — the user's comparison screenshot IS the
  measurement instrument, and it also tells you which properties are ALREADY correct so you don't
  change them by accident.**
- **⚠️ WEIGHT MUST BE RE-PICKED WHENEVER THE BODY SIZE CHANGES.** Assistant-Light (10 % stroke)
  was right at a 26-40 px body and became wrong at 18 px: a 1.8 px stroke never forms a solid
  core, so the glyph is pure anti-aliasing (measured AA mid/solid **1.38**, only 25/27 glyphs with
  a solid centre) and, magnified by the engine, reads as washed out. Assistant-Regular (12.5 % ≈
  the English's measured 11.8 %) restores it (**0.90**, 27/27 solid). Pick the weight from the
  ratio the TARGET renders at, not from a previous round's preference.
- **🔴🔴 SHRINKING THE GLYPH DOES NOT SHRINK THE LETTER SPACING — and that one fact made an
  18 px build "worse in every way", including defects that looked like a layout bug.** `bx` is
  the only additive spacing term we control and the engine adds a FIXED component (~2.6 atlas px)
  on top of it, so the gap barely moves when the body does. Measured as a % of the body
  (scale-invariant, so it compares across screenshots of different sizes):
  **English 17.6 % · 26 px build (bx=2) 18.6 % ✓ · 18 px build (bx=2) 24.1 % ✗.**
  Consequence chain, all from that one number: the text reads as sparse/scattered → **a word keeps
  almost its old WIDTH at a smaller height** → labels still overflow their box → they still wrap →
  the wrapped line collides with the next row. **The overlapping text in the save-slot list and
  the date line was a SPACING bug, not a layout bug.** Fix: solve `gap = bx + 2.6` for the English
  ratio ⇒ `bx = 0.176·body − 2.6` (body 21 ⇒ **1.1**). **RE-DERIVE `SIDE_BEARING` EVERY TIME
  `LADDER_INK[0]` CHANGES.**
  **UNIVERSAL: a font's on-screen metrics are body height AND advance. Changing one without the
  other breaks typography in ways that present as unrelated bugs (overlap, wrapping, "scattered"
  text) — always re-derive the spacing after a size change, and verify it as a RATIO.**
- **⚠️ "Match the English size" means the CAP, not a refined fraction of it.** I first applied the
  typographic 0.85×cap → 18 px, which makes the Hebrew *smaller* than the text it must match and
  also throws away 17 % of the atlas resolution in a font the engine already magnifies. The user
  judged it worse. Hebrew has no ascenders/descenders, so **body == Latin cap** is the correct
  conservative pairing: 26 px (=1.25×cap, "too big") → **21 px (=1.00×cap)**.
- **🔬 THE QUALITY CEILING, measured and honest: the engine magnifies BIG_ARABIC glyphs ~2.8×
  MORE than its own menu font.** From the same screenshot: our Hebrew stroke is 7.4 screen px
  from a 2.6 px atlas stroke (~2.8×), while the English font renders near 1:1. That is the entire
  sharpness gap, and it is NOT our rasterisation. Cause: there is no `SMALL_ARABIC`, so the whole
  Arabic slot falls back to the **BIG (title) family**, whose requested point size is huge — so
  every Arabic-slot glyph is a small atlas bitmap blown up. **And there is no scale field to
  fight it with:** the 40-byte `Fonts_Z` entry's `z` is **0.000 on all 349 entries** (single
  distinct value), `bx`/`by` are bearings, and the tail's leading u32 is just the material count.
  ⇒ At the requested size the atlas glyph is inherently small; all we control is that it is
  well-sampled (SS=8) and crisp (a soft edge magnified 2.8× becomes a wide mushy edge — which is
  why the *gentle* curve tried at 26 px was the wrong direction). Say this plainly instead of
  promising English-level sharpness.
- **🔎 `work/_preview_upscaled.py` PREDICTS the in-game look offline** — it lays a word out from
  the BUILT atlas, applies the measured magnification bilinearly (as the GPU does), composites
  the outline, and puts a simulated English line beside it at ITS measured magnification. Judge
  size and sharpness from that image instead of from a launch.
- **🔎 `work/_preview_final.py` renders the FINAL look offline** — a real subtitle line at the
  shipping body height, composited the way the game does it (black outline from the ramp, then
  white ink), for several weights at once. A weight change costs a chat message, never a game
  restart. ⚠️ The preview text reads reversed because PIL does no bidi; it is for judging
  weight/quality only.
- **🔑 WHY Hebrew is always big (game design, from `InitFont.tsc`).** The game loads
  `BIG_FONT · SMALL_FONT · SMALL_FONT_02 · BIG_RUS · BIG_JAP · BIG_KOR · BIG_CHI · BIG_ARABIC`.
  **There is no SMALL_ARABIC.** So EVERY Arabic-slot line — including subtitles — falls back to the
  BIG font family. Hebrew inherits exactly the size the official Arabic renders at. This is the
  root cause, and it is a game-design fact, not a mod defect.
- **🔴🔴 THE NOISE WAS OURS, IN THE COLOUR CHANNEL — and it took THREE root-cause attempts, each
  refuted by a better MEASUREMENT (final answer 2026-07-12, `_diag_glow.py`).** The colour (BC1)
  channel is a separate depth/emboss layer, and reproducing it wrongly is what the user saw as
  "noise". The three attempts, in order:
  1. ❌ *"stray ink around the glyphs"* — `_diag_noise.py` measured a 10 px ring outside every
     declared box: **0 stray on all 27 letters.** (The ring was also too small to reach the real
     culprit — see #3.)
  2. ❌ *"a flat fill / a graded floor"* — `_diag_ink.py` measured, INSIDE the box,
     ink 156.6 / edge 126.2 / background 37.1 and I concluded "the colour has a 37 floor and a
     gamma-lifted edge". **That reading was an artifact of only ever looking inside the box.**
  3. ✅ **THE TRUTH — the colour channel is a LINEAR DISTANCE RAMP that decays to exactly 0.**
     Measured over the WHOLE page (colour vs 4-connected distance from the nearest ink):
     `d=0 157 · 1 120.7 · 2 106.1 · 3 91.6 · 4 77.2 · 5 63.0 · 6 49.0 · 7 35.0 · 8 21.2 ·
     9 10.4 · 10 4.9 · 11 1.7 · 12 0.3 · ≥13 0.0 · far-from-any-ink 0.0`. The deltas are
     −14.6,−14.5,−14.4,−14.2,−14.0,−14.0,−13.8 = a **perfect linear ramp, 135 at d=0 falling
     14.3/px**, clamped at 0. It is NOT a gaussian (best gaussian fit rms 15.5, wrong shape) and
     NOT a floor — the "37" of attempt #2 was just the ramp's tail sampled inside a tight box.
  **What my #2 fix actually shipped:** a flat 37 over the entire repurposed Arabic slot. Measured
  on the deployed atlas that gives **far-background 14.4 (must be 0.0)** — i.e. a hard-edged dark
  RECTANGLE larger than the letter, and inside the box the letter's counters sat at 37 (dark)
  where the original has 120→90 (bright). That is *precisely* the user's report, phrase by phrase:
  "a darker background **inside the letters' cavity** and not outside" (the counters), "a perfect
  cut with no transition" (no ramp), "noise around the square, like **bigger text behind it**"
  (the removed Arabic glyph's own glow, which spills up to 12 px OUTSIDE its slot and survived a
  slot-only clear).
  **THE FIX, and it is the generalisable one: don't paint the colour per glyph at all — REBUILD
  THE WHOLE COLOUR CHANNEL FROM THE FINAL ALPHA** (`rebuild_colour()`:
  `colour = max(clip(135 − 14.3·dist_from_ink), 157·coverage)`, applied over every dirty region
  dilated by `GLOW_MAX+4`). Because the shipped colour is a pure function of distance-from-ink,
  regenerating it is exactly correct AND is the only thing that erases a REMOVED glyph's halo and
  leaves no seam at a slot edge. Verified per page, built vs original: ramp at d=1 **120.2–120.4**
  (orig 120.0–120.7), d=8 within ~1.5, **far-background 0.00 on every edited page**, and the one
  page we never touch stays byte-identical (it is a different atlas style with no glow at all —
  don't measure it against this profile).
  Also re-tune the alpha curve so the mid/solid AA ratio lands near the original's 0.24 (a too-soft
  0.43 both looks fuzzy AND hands DXT5 more mid-tones to quantise): `(a-14)*1.30` → 0.30.
  **UNIVERSAL — three lessons, all transferable:** (a) *measure a channel's profile as a function
  of DISTANCE FROM THE INK over the whole page, not inside the glyph box* — a box-local sample of a
  ramp looks exactly like a floor, and that misreading cost a whole round; (b) *the far-from-any-ink
  background is the single most diagnostic number* — the shipped value was 0.00 and mine was 14.4,
  which alone proves a rectangle was painted; (c) *when a channel is a pure function of another
  channel, regenerate it globally instead of painting it per glyph* — per-glyph painting cannot
  remove what a REMOVED glyph left outside its own slot.
  **✅ CONFIRMED IN-GAME 2026-07-12: "זה הצליח אין רעש" — the noise is gone.**
- **🔴 …AND THE COLOUR CHANNEL IS THE BLACK OUTLINE — so its RAMP LENGTH IS THE OUTLINE
  THICKNESS, and it must scale with the glyph.** The moment the ramp shipped, the user's report
  changed from "a dark rectangle" to "a thick black FRAME hugging the letter" — which identifies
  the channel: the shader draws a black outline whose alpha is this ramp (bright = opaque black
  halo, fading to 0). Consequence: a ramp of a FIXED pixel length is a CONSTANT-WIDTH outline, so
  a smaller letter gets a proportionally fatter frame. Shipped Arabic = 62 px ink with a 9.44 px
  ramp (`GLOW_D0/14.3`) = **14.5 % of the body**; our 40 px Hebrew with the same 9.44 px ramp =
  **21 %** = exactly the "1.6× too thick" frame. Fix: `ramp_len(ink_h) = 9.44 · ink_h / 62`,
  carried **per glyph** through the distance propagation (`rebuild_colour` stamps each written
  glyph's ramp length on its ink and spreads it outward with the distance), so glyphs of
  different sizes coexist and each keeps a proportional outline. Measured after:
  **11.9 % / 10.6 % / 12.0 %** across the three ladder groups.
  **UNIVERSAL: any "halo/glow/outline" channel expressed in ATLAS PIXELS is a RATIO on screen —
  scale it with the glyph or every size change silently rescales the outline too.**
- **⚖️ WEIGHT is chosen by MEASURING the stroke-to-body ratio, not by eye.** At a fixed 40 px
  body: FrankRuhl-Reg 7.5 % · **Assistant-Light 10.0 %** · Heebo-Light 10.0 % · Assistant-Reg
  12.5 % · Heebo-Reg 15 % · Heebo-Medium 17.5 % · Arial 17.5 % · Heebo-Bold 25 %. The shipped
  Arabic sits at **8-13 %**, so Assistant-Regular (12.5 %) was at the very TOP of the range =
  the "too thick" report; Assistant-Light lands mid-range and keeps the family the user picked.
  One offline script ranks every Hebrew font on the machine — do that instead of another restart.
- **⚠️ The game DOES also have a subtitle background** (`MENU__SUBTITLES_BACKGROUND` = "Enables a
  dark background behind the subtitles", plus `_OPACITY` and `_COLOR`) — a normal in-game setting the
  user can switch off. Useful to know, but it was NOT the reported noise.
- **✅ WEIGHT is the ONLY lever that visibly changes anything** (height is normalised away, so only
  stroke thickness + letterform differ on screen). **Judge it OFFLINE — never burn a game restart on
  a subjective look.** `work/font/_preview_weights.py` renders every candidate at a FIXED body height
  on a dark subtitle band → `WEIGHT_COMPARE.png`, and the user picks from one image.
  Font history (all in-game verdicts): **David Libre = too bold/"silky" · Heebo Light = too thin/weak ·
  Heebo Medium = too heavy (10 px stroke, reads as "too big") · → Assistant Regular = CHOSEN**
  (7 px median stroke, inside the shipped font's own 5-8 px range). `DEF_FONT` in `build_hebrew_font.py`.
- **Digit/Latin size-consistency fix (keep it).** `repack_latin` must render Latin at **cap = tgt**
  (the same size as the Hebrew body), NOT at `capH` (79). At 79 the glyphs overflowed the freed boxes
  → the Kuhn matcher fell back to per-glyph shrink → visibly inconsistent digit sizes AND a mismatch
  with the smaller Hebrew.
- **`--no-shrink` / em-shrink experiment (left in, harmless).** Clamps the ~180 tall **unused** Arabic
  glyph boxes to 48 px (metrics only, no atlas edit — they are never displayed) on the theory that the
  engine derives its em from the tallest declared box. Kept as a free long-shot; it does NOT change the
  proven conclusion above.
- **Reusable diagnostics** (`games/plague_tale_requiem/work/font/`): `_diag_fonts.py` (enumerate every
  `Fonts_Z` + its Latin ink/cap sizes) · `_diag_scale.py` (same letter across fonts + tail/footer decode
  — the decisive size probe) · `_diag_objs.py` (object census + descriptor hunt) · `_diag_noise.py`
  (stray-ink ring on the DEPLOYED atlas) · `_preview_weights.py` (offline weight picker) ·
  `_diag_metrics.py` / `_diag_size.py` (box-vs-ink fill ratios; original boxes are TIGHT, fill ≈ 0.98).
- **🔑 UNIVERSAL PROCESS LESSON.** When the user reports **"it's the same every time"**, stop iterating
  builds: that sentence is evidence the lever is **not in the file you are editing**. Go PROVE where the
  value lives — enumerate the container's object types, look for a descriptor object, decode the
  footer/header, compare the same glyph across sibling fonts, and grep every editable config — before
  asking for one more restart. And for anything the user must judge subjectively, build an OFFLINE
  preview so they choose from an image instead of from a game launch.

---


## A Plague Tale: Requiem — FLEET TRANSLATION STARTED (7 streams, 2026-07-08)

The NIM cloud fleet was pointed at PT Requiem IN PARALLEL with W3 finishing (user: "במקביל התחל לתרגם").
New `games/plague_tale_requiem/fleet/` mirrors the W3 fleet: `pt_nim.py` (NIM worker; PT prompt = 1349 plague
France / Amicia·Hugo·Lucas; STRUCT tokens = `{STR_...}` + the pipe `|` line-break preserved; stores LOGICAL —
`pt_rtl.to_stored` bakes RTL at BUILD, never in the worker), master corpus = `extract/gender_source.json`
(20,661 × {en,ar} — the gender oracle doubles as the ready-made fleet corpus), 7-way disjoint
`splits/corpus_pt_<stream>.json` (~2,951 each), `pull_pt.sh` + `PTFleetPull` task (3 min, hidden.vbs), sentence-
based `pt_progress.py` (gameId=`plague-tale-requiem`, total 20,661), `selfheal_pt.ps1`(+`_laptop`). Deployed to
all 7 streams in a SEPARATE dir `C:\ptw` (coexists with `C:\w3w`; selfheal matches only `pt_nim` so it never
kills the w3 worker) + PTWorker/PTWorkerBoot SYSTEM tasks; key copied `C:\w3w\key.txt`→`C:\ptw\key.txt`; laptop
`pt_laptop_worker`; desktop `fleet/desktop_worker` (local). **vm3 RE-ADDED as the 7th stream** (127.0.0.1:2224;
its key was already on the VM's Desktop → copied). Live: banking climbs (259/20,661 in ~5 min, all 7 producing).
W3 = 99.8% (vm3 mops the ~220-line book tail). **When W3 finishes → build its mod LOCALLY, NO publish** (publish
ONLY on explicit "פרסם"). Each VM now runs BOTH w3_nim+pt_nim on ONE key (serial; W3 idles as it drains → PT
gets full cycles). Memory [[nim-fleet-game-queue]].

**PT fleet ops (2026-07-09):** user borrowed desktop+vm+vm2 for a W3 sub-task → **resliced PT onto the 4 remaining
streams only** (`fleet/reslice_split.py [streams]` + `fleet/reslice_deploy.sh` — mirror W3's; default = vm3 vm4 vm5
laptop; scp each `reslice_<n>.json`→stream `corpus.json` + relaunch pt_nim; keeps out.json; disjoint+complete over the
remaining). Remaining tail ≈ **2,045 (banked ~18,616/20,661)** = the LONGEST lore/book lines → NIM free-tier throttles
the keys (0.27–8 tok/s) so fleet throughput on the tail is only **~0.5 sentence/min** (~68h). **Freed the 4 streams to
PT-only** (disabled `W3Worker`+`W3WorkerBoot` + killed `w3_nim` on vm4/vm5/laptop; reversible via `Enable-ScheduledTask
W3Worker`/`W3WorkerBoot`) — helps, but the throttle is the hard ceiling. **FAST-FINISH = agent handoff**
`fleet/agent_tail/` (mirrors W3's): `build_tail.py`→`to_translate.json` (2,045 {en,ar}), `get_batch.py [N]`→
`current_batch.json`, `merge_batch.py` (PT anti-cheat: `{STR_}`/`|`/`%` token multiset + no-Hebrew-prose reject +
LOGICAL) writes to **`fleet/banks/out_agent.json`** → the pull folds it into `hebrew.json` → the **home-page dashboard
moves live** (pusher `pt_progress.py` alive, `/api/progress` fresh, W3+PT tab dashboard polls 60s; verified). The
real-time site display is WORKING — the only slowness is NIM throughput on the tail → hence the agent. `INSTRUCTIONS.md`
= the PT agent prompt (1349 France, Amicia/Hugo/Lucas, gender from `ar`). **3-agent parallel** via
`agent_tail/build_parallel.py [N]` (disjoint md5%N isolated `agent_K/` folders, each own bank `out_agent<k>.json`).
**⚠️ MARKER FIX (2026-07-09):** verifying the agents caught that the has-Hebrew gate FORCE-TRANSLATED **2,697
non-translatable markers** (`onom`/`mono`/`EMPTY`/URLs/native language-names) — the game's pro Arabic keeps them as-is
(`onom`→`mono`, `한국어`→`한국어`). Fixed: `agent_tail/purge_markers.py` → `fleet/marker_keys.json`; `pull_pt.sh` +
`build_tail`/`build_parallel`/`reslice_split`/`pt_progress` all EXCLUDE markers (kept as Arabic, like the pro loc). So
REAL translatable = **17,964** (not 20,661); after cleanup **99.7% done, 51 real lines left** (resliced to the fleet).
UNIVERSAL LESSON: a has-Hebrew gate must exclude non-translatable markers (sound-cues/EMPTY/URLs/native-names) or
agents invent Hebrew for them = silent corruption; the game's own Arabic is the oracle for what to leave untranslated.
**NAME CONSISTENCY (2026-07-09, verified + fixed + made a standing rule [[name-registry-and-internet-check]]):** with
3 agents + the fleet each transliterating independently, the SAME name got spelled several ways — **Hugo `היוגו`×203
vs `הוגו`×155**, Milo מיילו/מילו, Basilius בזיליוס/בסיליוס. Internet-verified canonical (teenights.com Hebrew review:
Amicia=אמיסיה, Hugo=הוגו; he.wikipedia: Basilius=בסיליוס). Fixed permanently: `name_registry.json` (canonical EN→He)
+ `fleet/name_fixes.json` (wrong→right substring pairs) applied by `pull_pt.sh` `canon()` on EVERY merge → hebrew.json
always consistent (403 הוגו / 0 היוגו, etc.), even for future variant output. Verify tool:
`fleet/agent_tail/name_consistency.py` (⚠️ its prefix-grouping misses different-prefix variants like היוגו/הוגו and
false-flags gender-inflected verbs — eyeball the PROPER NOUNS). STANDING RULE for every future game: build the name
registry + web-verify the real Hebrew spelling BEFORE translating, enforce it in every line.


## A Plague Tale: Requiem Hebrew — Phase-1 groundwork DONE, GO (easy tier) (2026-07-03)

New game scaffolded at `games/plague_tale_requiem/` (RECON.md / FEASIBILITY.md / PIPELINE.md +
`work/`). **Verdict 🟢 GO — the TEXT pipeline is PROVEN end-to-end IN-GAME (2026-07-03); the ONE
remaining gate is the Hebrew font.** Menu proof (user-confirmed): raw Latin markers rendered
REVERSED (`ZZ-CH-ONE`→`ENO-HC-ZZ`) → proves the file is read + Latin font works + engine does
RTL char-layout; the SAME markers via `pt_rtl.to_stored` rendered FORWARD/correct → transform
confirmed; Hebrew rendered BLANK (no glyph, not tofu) → **font lacks Hebrew, injection required**.
Game files reverted to pristine Arabic after the proof. Memory [[plague-tale-requiem-groundwork-go]].

- **Install:** `D:\Games\A Plague Tale - Requiem` (GOG+Steam dual build, `steam_emu.ini`). Engine =
  Asobo **Zouna** (same family as Plague Tale Innocence + MS Flight Sim). exe `APlagueTaleRequiem_x64.exe`.
  **No Denuvo / no anti-cheat.** Detector key + Supabase `games.id` = **`plague-tale-requiem`**
  (already in `game_detector.py`; the `games/plague_tale_requiem/` dir pre-existed with only art).
- **🟢 Text = LOOSE plain-text, the easiest possible.** `TRTEXT/ttNN.pc` where `NN` = the TSC_ID in
  `LangDef.tsc`: **`tt01.pc`=English (SOURCE), `tt23.pc`=Arabic (our Hebrew SLOT)**, tt02..22 = 13
  other langs. Format (UTF-8, CRLF, NO BOM): `FreeLanguage` / `ResetEnumTT` / `TT <idx> "<value>"
  <KEY>` ×20,661 / `EndLoadTT`. Values NEVER contain a `"` (unambiguous parse); `<KEY>` shared
  across every language → EN↔AR↔HE map 1:1 by KEY/index; in-value line-break = **`|`** (no `\n`);
  `{STR_…}` = runtime button tokens (31 distinct). Files read **loose at runtime** (NOT packed in
  the 31 GB `COMMON.DPC` — verified). **Deploy = overwrite `tt23.pc`. NO repack, NO compression.**
  One quirk: key `OBJECTIVE__CH14_PROTECTSOPHIAANDLUCAS` has a trailing space — the codec preserves
  it byte-for-byte. `.IGN` = a second divergent variant of each file (deploy to both; `.pc` is the
  PC-live one — confirm in the proof).
- **🔑 bidi = a THIRD engine class (reverse-engineered from the game's own Arabic tt23.pc).** The
  engine positions stored chars **right-to-left** but does **NO** bidi reorder of LTR runs and **NO**
  Arabic shaping. So STORED = LOGICAL with: RTL scripts kept logical, **LTR islands (Latin/digits)
  pre-reversed in place**, `{STR_}` tokens verbatim, **run order preserved**. Ground truth: digit
  `"12"→"21"` (ACHIEVEMENT__DESC_12); roman `"XVII"→"IIVX"` (MENU__CHAPTER17; IV→VI, IX→XI…), the
  `" - "` separator STAYS after the numeral; `"Asobo Studio"→"oidutS obosA"` (multi-word Latin
  reverses as a unit); embedded Latin reverses IN PLACE with the Arabic staying logical. **Hebrew is
  EASIER than Arabic (no shaping):** store base Hebrew U+05D0–05EA logical + reverse LTR islands only.
  Implemented + self-tested in `work/pt_rtl.py` — the proof output is byte-structurally identical to
  the game's Arabic → high confidence (still must confirm in-game per playbook).
- **Scope (tt01.pc, 20,661 strings):** 17,476 subtitles (`VO__`) + 1,433 UI
  (MENU/HUD/OBJECTIVE/TUTO/ACHIEVEMENT/LOOT/GAME…) + 1,752 credits (`CREDIT__`, low priority).
- **Font = the ONE gate.** Zouna fonts are **bitmap texture ATLASES** (`Fonts_Z` class:
  Map<CharacterID, Character> → material_index + UV rect + descent, glyphs in a `Bitmap_Z` atlas;
  `CharacterID` = glyph UTF-8 bytes reversed+null-padded). The Arabic slot renders with **BIG_ARABIC**
  (inside `FONT/ENGLISH.DPC`, 19 MB); no embedded TTF. Almost certainly **no Hebrew glyphs** → the
  menu proof decides: renders ⇒ zero font work; tofu ⇒ inject 27 Hebrew glyphs into the atlas +
  metrics (SM2/WD2/GoWR/Anno atlas-injection class). DPC = Asobo BigFile (64-bit hashes + **LZ4**,
  `compressedSize==0`=raw). Community tools: **amrshaheen61/APT_DPC_Tool** (Plague-Tale-specific;
  extract OK, import buggy), **widberg/bff** (Requiem PARTIAL), **widberg/fmtk** wiki (spec),
  **widberg/ImZouna** (ImHex hexpat). Repacker may need fixing/RE before the DPC re-loads.
- **🟢 FONT GATE SOLVED (2026-07-03 — built + offline-verified via Pillow(=GPU) 27/27 + DEPLOYED,
  awaiting user in-game confirm).** Pipeline in `work/font/`; backup `FONT/ENGLISH.DPC.he_backup`;
  revert `python build_hebrew_font.py --revert`.
  - **`dpc_repack.py`** — pure-Python DPC REPACKER (bff/APT can't repack v2.128): untouched objects
    verbatim + re-lay + patch moved offsets; no-edit rebuild is BYTE-IDENTICAL. Wrapper `<QQqiiiihB>` =
    type|id|**unk16(FILETIME, PRESERVE)**|buf|infoSz|origSz|comp+8|padding|**isComp(4=zlib, PRESERVE)**;
    `padding=(16-(43+infoSz+8)%16)%16`. **Textures sit in the FileMap with a `csize` — on re-emit patch
    BOTH offset AND csize (`off_pos+4`) or the game reads a truncated object → crash/"disc removed".**
  - **⚠️ THE ROOT-CAUSE of the entire prior "noise/dots" saga:** the texture body = **512×512 DXT5 at
    BYTE 0 with a 4-byte TRAILER** (`00000000`), NOT a 4-byte prefix header. The old code split
    `body[:4]/body[4:]` → desynced EVERY DXT5 block by 4 bytes → the game rendered our writes as speckle.
    Proof via Pillow (GPU DXT5 truth): `body[0:262144]` decodes **97% bimodal (clean binary coverage)**;
    `body[4:]` = 13% (gray noise). Format authoritative via widberg ImZouna `patterns/fuel/Bitmap_Z.hexpat`
    (`BmFormat_Z: DXT1=14, DXT5=16` — **NO BC7 in Zouna**); info block confirms 512×512, format=16.
  - **Atlas/metrics:** glyph = crisp binary in DXT5 **ALPHA** (a0=255,a1=0); COLOR(BC1)=soft gray copy
    (ink≈156) — we write both. `Fonts_Z` entry (40B) = cid,mat,**adv(=topY, NOT advance!)**,x0,y0,x1,y1
    (atlas box px),bx,by,z. **Metric: adv = baseline(≈129) − ascent** (box-top→glyph baseline); horizontal
    advance ≈ box_width+bx. (fonts_z.py's "advance" label for float#1 is WRONG — it's topY.)
  - **`build_hebrew_font.py` = the solution:** 27 letters **Frank Ruehl Bold** (`FRANKB.TTF`, dark serif,
    BODY_TARGET=48 → ≤47×68px), **REPURPOSE** 27 Arabic slots (cid→Hebrew, constant FontMap size ⇒
    guaranteed load, proven; ~38 slots ≥50×70), clear each Arabic box + draw the glyph, re-encode touched
    blocks (both channels), box=tight rect, adv=129−ascent. `verify()` decodes the built DPC via Pillow →
    contact sheet 27/27 clean. Deployed delta −32,608 B; re-parses valid (349 entries, 27 Hebrew, mats 0–5).
    Repurpose lookup was already PROVEN in-game (Hebrew→'A'); the noise was ONLY the 4-byte bug.
  - **✅ CONFIRMED WORKING IN-GAME (user 2026-07-03)** — clean Hebrew in menus/titles.
  - **Hebrew = ONE font only (game design, proven from data).** FONT/ has only `ENGLISH.DPC`
    (no per-language pack); it holds **8 Fonts_Z objects** but **only BIG_ARABIC has a full Arabic
    alphabet (125 letters)** — the other 7 each carry the SAME 8 Arabic presentation-form letters
    (a fixed marker) and CANNOT render Arabic words; BIG_ARABIC has no duplicate letters → the engine
    SCALES one glyph for all sizes. So ALL Arabic-slot text (titles, menus, **subtitles**) routes
    through BIG_ARABIC. The game's serif-title + sans-subtitle split is **Latin-only** (the sans
    subtitle font has no Arabic → Hebrew subtitles fall back to BIG_ARABIC). ⇒ choose ONE Hebrew font
    good for both roles (elegant serif; avoid heavy display). Style-ID helper `_identify_fonts.py`
    (all 8 are serif). **DECISION (user): `David Libre` uniform — David Libre Bold DEPLOYED**
    (`fonts_pdf/DavidLibre-Bold.ttf`). Options PDF: `work/font/PLAGUE_TALE_hebrew_fonts.pdf`
    (12 period fonts; `build_font_pdf.py`).
- **Tooling built (`work/`, all self-tests PASS):** `pt_text.py` (codec — identity round-trip
  byte-identical, surgical value-only override), `pt_rtl.py` (`to_stored` transform), `build_proof.py`
  (menu proof: `--deploy`/`--revert`, backup `.he_backup`, writes both `.pc`+`.IGN`), `extract_corpus.py`
  (→ `extract/en.json` + `ct_strings.json` community-pool format + `report.txt`).
- **NEXT (Phase 1 finish):** user runs `python build_proof.py --deploy` → launch → Options → Text
  language = العربية → confirm Hebrew glyphs + RTL + numbers + `{STR_}` + no crash. If tofu → font
  injection sub-project. Then Phase 2 = delegate translation ([[delegate-all-translation]]) → build via
  `to_stored` → deploy → publish like SM2/WD2/Anno (GitHub `plague-tale-requiem-hebrew-mods` + Worker
  slug `plague-tale-requiem-hebrew` + Supabase `games` + `mod_version_history`). Activation = in-game
  Text language = Arabic; English VO kept (audio language independent).

---


