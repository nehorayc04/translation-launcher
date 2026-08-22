# AC Origins — FEASIBILITY: ✅✅ PHASE 1 COMPLETE — every gate closed in-game, 🟢 GO

| # | Gate | Status |
|---|---|---|
| 0 | RTL locale, per surface | 🟢 **subtitles YES** (12,844 real Arabic rows) · **UI NO** (457-B stub) |
| 1 | Container | 🟢 scimitar **v28** — the Odyssey reader parsed 707/707, 0 errors, unchanged |
| 2 | Text codec | 🟢 identity round-trip **semantic PASS** on all 4 key packages |
| 3 | bidi — **UI** | ✅ **VISUAL, CONFIRMED IN-GAME** (round 1) |
| 3b | bidi — **subtitles** | ✅ **VISUAL, CONFIRMED IN-GAME** (round 2 — the A/B pair on ONE screen) |
| 4 | Which UI package wins | ✅ **candidate A** — Hebrew rendered with `Text=en-US` untouched ⇒ **zero user actions** |
| 5 | Font | ✅ **CONFIRMED IN-GAME — zero tofu**, every Hebrew word real glyphs (9/9 faces) |
| 6 | Deploy | 🟢 append-relocate, offline-validated on a copy, then live, `--verify` PASS |
| 7 | DRM / integrity | 🟢 Denuvo on the exe only; 0 anti-cheat, 0 `tamper` strings |
| 8 | Activation | 🟢 UI = **zero user actions**; subtitles = one in-game setting |
| 9 | Subtitle **wrap** | ✅ **MEASURED + TOOLED** — box = **23.66 em** (3 % bracket); `aor_rtl.to_visual_wrapped` validated on all 14,782 rows |

## ✅✅ Round 2 — the subtitle surface is VISUAL, settled by the A/B on ONE screen

The rotation put both tagged variants on adjacent lines of the same conversation, exactly as
designed — no scene to hunt for:

```
ZZ-SUB-L-ZZ   תירבע םולש     <- stored LOGICAL -> renders MIRRORED
ZZ-SUB-V-ZZ   שלום עברית     <- stored VISUAL  -> renders CORRECT
```

Exactly one of the pair can be the readable word, and it is the **VISUAL** one. So **both
surfaces are VISUAL** — but note that this was *proven per surface*, not inherited from the UI
([[bidi-per-surface-not-per-product]]): the UI sits in an LTR slot and the subtitles in the
game's real Arabic locale, which are different renderers and could have disagreed. ⇒
**`aor_rtl.to_visual` is the shipping transform on both surfaces.**

Within a line the layout is also correct — the punctuation paragraph rendered
`סימני פיסוק:` · `(סוגריים) "מרכאות" — מקף, נקודה. שאלה? 12.5% ואז` with every mark, paren,
quote, digit and the Latin island in place.

## 🔴 …and the same row exposed the ONE real defect: the store-VISUAL wrap trap

The 90-char paragraph rendered with its **LINE ORDER INVERTED** — `סימני פיסוק:`, the logical
START, came out on the **BOTTOM** line and `סוף!` ("end!") on the TOP. That is §8b rule 4: the
engine wraps in **STORAGE** order, so a long VISUAL string is laid out bottom-up.

Measured exposure, so Phase 2 is planned honestly rather than guessed:

| | |
|---|---|
| subtitle rows > 60 chars | **5,077 of 14,782 = 34.3 %** |
| > 80 chars | 2,956 (20.0 %) · median 45 · p90 103 · max 961 |
| rows that already carry a real `\n` | **30** (English) / **11** (Arabic) |

The shipped Arabic almost never pre-wraps because **it does not have to** — Arabic gets engine
bidi, so wrapping in logical order is correct for it. Hebrew stored VISUAL gets no such help.
⇒ **Phase 2 MUST pre-wrap every subtitle the engine would wrap** (insert real `\n`, the break
character the corpus already uses), and a pre-wrapper needs a width budget — hence the ruler.

## 🔴🔴 Round 3 — the ruler's tags were EATEN BY THE ENGINE (and that is itself a finding)

Round 3 tagged each rung `[N] ‹body› [N]`. **Not one bracket or digit reached the screen** — the
ruler rendered as bare Hebrew filler. Verified from BOTH sides, so it is a render-side fact and
not a build bug: **4,268 rows carry a `[N]` in the LIVE forge**, and `--verify` matched on it.
⇒ **Origins parses `[...]` as a control-name substitution and renders an unknown name as
NOTHING.**

**The trap, and it is a good one:** I chose `[N]` *because* `aor_rtl` protects an all-digit
bracket as an atomic engine token. But **"my transform must not touch it" and "the engine claims
it" are the same property read from two sides** — the very thing that made the tag survive the
pipeline is what made it vanish on screen. **A proof marker must be a string the ENGINE has no
meaning for.**

This also gives Phase 2 a hard, in-game-backed rule that until now rested only on the corpus
counts: an unrecognised `[...]` is **deleted**, not shown. A translator who leaves a prose
bracket in a form the engine does not know loses that text silently — which is exactly why the
shipped professional Arabic is the per-bracket oracle (it translates 239 prose brackets and
keeps 1).

## ✅✅ Round 4 — THE BOX IS MEASURED: 23.66 em (a 3 % bracket)

Eight screenshots, and the ruler answered far more precisely than a fit/no-fit ladder can:

| rung | result |
|---|---|
| W36 (18.01 em) | fits on one line |
| W40 (20.04 em) | fits |
| **W48 (23.66 em)** | **fits** — seen twice |
| **W54 (26.61 em)** | **wraps** |

🔑 **The WRAP POINT is worth more than the pass/fail.** W54 did not just break — it broke
after **40** characters, leaving `W54 אבגדהוזחט` (13 ch) on the second line. Simulating a
greedy wrap of that exact stored string shows the engine would have fit **50** characters had
the box been ≥ 24.355 em, and the last line would then have been a lone `W54`. It was not. So:

```
  W48 fit on one line          ->  box >= 23.655 em
  W54 broke at 40, not at 50   ->  box <  24.355 em
  =>  box in [23.66, 24.35) em      (a 3.0 % bracket)
```

**Ship budget = 23.66 em** — the lower bound, because a string of exactly that width was *seen*
to fit. Erring low costs at most one extra break per paragraph; erring high lets the engine wrap,
which is the only failure that matters. ≈ **46 Hebrew characters** at Heebo's average advance.
Falsifiable prediction, if anyone wants to re-check: **W50 (24.82 em) must wrap.**

**UNIVERSAL:** a width ruler should include at least one rung that OVERFLOWS, and you should read
*where* it broke — simulating the greedy wrap at candidate budgets and matching the observed split
turns a coarse "between 48 and 54" into a 3 % bracket, from the same screenshot.

## ✅ The pre-wrapper is BUILT, not just specified

`aor_rtl` gained `text_em` / `wrap_logical` / `to_visual_wrapped` + `BOX_EM_SUBTITLE = 23.66`.
`to_visual_wrapped` is **the Phase-2 subtitle transform**: wrap the LOGICAL text, then convert
each line — wrapping after the conversion would wrap reversed text. `text_em` is token-aware:
markup (`<font …>`, `<i>`) draws nothing, and a runtime-substituted `{NAME}` / `[CT_*]`, whose
real width is unknowable at build time, is charged a nominal 4 em so a line carrying one is never
wrapped over-optimistically.

Validated on the whole corpus (all 14,782 subtitle rows): **0 words dropped or added, 0 lines
over budget, 0 token-multiset changes.** 40.4 % of rows need wrapping, 22,579 lines in total.
Selftest 20/20.

⚠️ Also fixed while here: `to_logical`'s docstring still claimed it was "the SHIPPING
transform" and `to_visual` was "the A/B counterpart used by the menu proof ONLY" — **backwards
since round 1**, and a Phase-2 build that trusted it would have shipped mirrored Hebrew.

## ✅ Round 1 came back — three gates closed by four screenshots (2026-07-27)

- **MOUNT ✅** — `Options` rendered as **אפשרויות** in the live main menu with
  `Text=en-US` **untouched** ⇒ candidate **A** is the live package and the shipping build
  costs the user **zero actions**. (Candidate B was later tested and CLOSED — see below: the
  game itself rejects `Text=ar-AR` and reverts it, so candidate A is the only path.)
- **FONT ✅ — zero tofu.** Every Hebrew string rendered as real glyphs at the same weight and
  size as the surrounding Latin: `אפשרויות` in the main menu, `פועל` ×2 and `כבוי` ×3 in the
  graphics settings, and the full A/B strip in Options.
- **bidi (UI) = VISUAL ✅.** Everything stored through `to_visual` reads correctly
  (`אפשרויות` · `פועל` · `כבוי`), while the one row deliberately stored LOGICAL — tagged
  `ZZ-LOGICAL` — reads mirrored beside it. Exactly one of the pair can be the readable word,
  which is what makes the A/B decisive instead of a judgement call
  ([[hebrew-screenshot-transcription-trap]]). Matches the Mirage/Odyssey sibling verdicts:
  the engine's RTL pipeline is gated to the Arabic **script**, so Hebrew is drawn in storage
  order. **`aor_rtl.to_visual` is the shipping transform for the UI.**
- **Layout ✅** — Hebrew rows sit exactly where the English did (`פועל` beside its checkbox,
  aligned with `High` / `Ultra High` above it). No mirroring, no misalignment, no clipping.

## 🔴 The round-1 miss, and the rule it produces

`Play`, `Discovery Tour`, `Store`, `Ubisoft Club` and `Quit to Desktop` stayed English —
**not a mount failure, wrong ids.** I had carried Odyssey-shaped guesses across, and Origins
keys those rows differently:

| I patched | is actually | the menu really uses |
|---|---|---|
| `850446` | `STORE` (upper-case) | `Store` = **1011737** (+1012623, 1012625) |
| `1080069` | `Exit` | `Quit to Desktop` = **1014351** (+60000099) |
| `1043183/4` | `CONTINUE` / `Continue` | not on the main menu at all (Play submenu) |
| `456221` | `CREDITS` | not a main-menu row ⇒ **the marker never showed** |

Only `663085`/`532106` (`Options`) happened to hit — which is the single reason the mount was
provable at all. **UNIVERSAL: resolve a menu id by looking its ENGLISH VALUE up in the game's
own package; never carry an id across from a sibling title, and put the mount marker on a row
you have CONFIRMED is on that screen — a marker on an absent row is indistinguishable from a
failed deploy.** Round 2 (deployed) fixes all of them and moves the marker to
`Discovery Tour` (1083812).

## What is deployed right now

`work/build_proof.py --deploy` wrote **12 resources** into `F:\Games\Assassin's Creed
Origins\DataPC.forge` (backup `DataPC.forge.he_backup`, +13.7 MB by append-relocate):

- `LocalizationPackage_English` — 8,223 strings, marker **`ZZ-AOR-ENUI-ZZ`**
- `LocalizationPackage_Arabic` (the UI stub, **filled to 8,223**), marker **`ZZ-AOR-ARUI-ZZ`**
- `LocalizationPackage_Arabic_Subtitles` — all 12,844 rows carry a proof variant
- the 9 Hebrew-injected fonts

`--verify` re-reads the LIVE forge (never the builder's own output): markers present in both
packages, 12,844/12,844 subtitle rows proofed, **9/9 fonts at 27/27 Hebrew** → **VERIFY PASS**.

## The ladder — two UI candidates in ONE deploy

Origins has no Arabic UI locale, so the UI must hijack an LTR slot. But the Arabic UI package
is a *live object* holding 20 genuinely-translated strings, so it may still load if the engine
is told to. Both are shipped, each with its own Latin marker, and whichever marker appears
names the winner ([[measure-with-a-ladder]]):

| | package | how the user selects it | if it wins |
|---|---|---|---|
| **A** | `LocalizationPackage_English` | nothing — `Text=en-US` is the default | ships with **zero user actions** |
| **B** | `LocalizationPackage_Arabic` | `ACO.ini` → `Text=ar-AR` | we also get the engine's **RTL menu layout** for free |

B is the better product if it loads; A is the guaranteed fallback. One session answers it.

## The proof rows, and why each exists

| row | content | closes |
|---|---|---|
| `456221` CREDITS | pure-Latin marker | **mount** — independent of font AND bidi |
| `456219` Controls | `שלום` **VISUAL** | bidi A |
| `456223` Sound | `שלום` **LOGICAL** + `ZZ-LOGICAL` | bidi B — the deliberately-wrong control row |
| `456235` Brightness | `אבגד` VISUAL | direction, 4 non-confusable letters |
| `456233` Menu Language | all 27 letters | glyph coverage / tofu |
| `456237` / `456230` | the same punctuation+parens+digits+Latin paragraph, VISUAL / LOGICAL | layout |
| main menu + options | real Hebrew labels, VISUAL | what the shipping build looks like |
| every subtitle | rotated by `id % 3`: VISUAL · LOGICAL · **ruler** | the subtitle surface's own bidi (✅ answered) + the box width, on whatever line fires |

🔑 Keeping ONE deliberately-wrong row turns "this looks right" into "exactly one of these can
be right, and it is this one", and its Latin tag makes a stale deploy impossible to mistake for
a fix. The subtitle rotation means the user does not have to hunt for a specific scene — any
conversation shows both modes on adjacent lines.

## Why the corpus could not have answered bidi (kept — it is the reusable rule)

The shipped Arabic subtitles are 488,234 standard-block chars with **0 presentation forms and
0 bidi controls**, and 10,388 lines end with `. ! ? ،` against 26 that start with one ⇒ the
engine shapes and reorders **Arabic** itself. That says **nothing** about Hebrew
([[corpus-stats-measure-their-own-language]]): on Mirage and Odyssey — the same engine — the
RTL pipeline turned out to be gated to the Arabic *script*, and Hebrew was drawn in storage
order. Both sibling verdicts said VISUAL, the prediction held on both surfaces, **and the A/B
pair is what turned it from a prediction into data.** The UI sits in an **LTR** slot and gets no
bidi at all; the subtitles sit in the game's real Arabic locale and still got none for Hebrew.

## ✅ Candidate B TESTED and CLOSED — the game rejects it, definitively

The user set `Text=ar-AR` by hand in `ACO.ini` and launched. **The game itself reverted it back
to `Text=en-US` on that launch** (confirmed by reading the ini afterward — `Subtitles=ar-AR`
stayed untouched, only `Text`/`Client` reset). This is not "didn't load" — it is the game's own
language-validation writing a known-good value back over an unsupported one. ⇒ **`Text` has no
Arabic option; only `Subtitles` does.** Candidate B was never reachable via the ini, and no
installer trick changes that. **Candidate A remains the ONLY UI path, and it was already the
proven, zero-action one.** Nothing about the shipping plan changes — this only removes an
"optional upside" that turned out not to exist.

## Nothing left to test. Phase 1 is fully closed.

Every gate in the table above is ✅/🟢. Both bidi surfaces, the font, the deploy mechanism, the
UI candidate, and the subtitle wrap budget are all measured and validated. Phase 2 can start
with no further in-game verification.

Revert everything: `python games/acorigins/work/build_proof.py --revert`.

## ✅ `/translate` pool LIVE — 28,537 rows, folding in the DLC

`work/build_ct_strings.py` + `universal/community_translate.py import acorigins`. Ordered by
VISIBILITY: **ממשק ותפריטים 11,094 → כתוביות עלילה 17,443** (114 dropped — token-only, no real
letter survives). `string_key` = `ui:<id>` / `subs:<id>` — **0 id overlap between base and DLC**
(measured: base ids 287,239–60,000,220, DLC ids 4,000,003–4,011,389, disjoint both directions
and both kinds), so one key scheme covers both sources with no prefix needed. Every row carries
the game's own **Arabic + Russian + Polish** in `context` as the gender source. Verified through
the public API: both category chips with exact counts, 0 round-trip mismatches.

**🔴 The DLC's English package was invisible to `scope_report.py` — it's named
`DLC22-30_LocalizationPackage_English(US)`, not `…_English`.** The `(US)` suffix silently
evaded the `LANGS` lookup (keyed on the bare string `"English"`), so the earlier headline
"21,924 global-unique" was **BASE-ONLY** and undercounted the DLC's real content by ~2,868 new
UI + ~2,611 new subtitle lines. Fixed in `build_ct_strings.py` by reading the exact package
name rather than a language-suffix map. **True total = 28,537.**
**UNIVERSAL: a language-suffix lookup keyed on a bare name (`"English"`) silently drops any
package whose name carries a region/edition qualifier (`English(US)`, `Spanish(Mexico)`) —
when scoping a DLC/patch forge, list its packages by NAME and diff against the lookup table
instead of trusting a clean parity report that never mentions the missing language at all.**

## Phase 2 (gated on the proof)

Delegate all 28,537 lines ([[delegate-all-translation]]) — a single pass, no fleet — with the
free 12-language oracle panel, **keyed by id**, gender from ru/pl (+ the shipped Arabic
subtitles as the Semitic near-match), then build through **`aor_rtl.to_visual` on BOTH surfaces**
(the A/B answered VISUAL for each) → **pre-wrap the subtitles** to the em budget above →
`aor_loc.rebuild` → `aor_cfd.encode_resource` → `aor_deploy.apply` — for BOTH `DataPC.forge`
(base) and `DataPC_22_dlc_patch_01.forge` (DLC). Publish only on an explicit "פרסם".

## מסמכים קשורים
- באותה תיקייה: [[games/acorigins/PIPELINE|PIPELINE]], [[games/acorigins/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acorigins|CLAUDE_INDEX_games]]
