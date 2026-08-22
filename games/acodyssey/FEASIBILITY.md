# AC Odyssey — FEASIBILITY: 🟢🟢 GO — PHASE 1 COMPLETE, every gate closed IN-GAME

| # | Gate | Status |
|---|---|---|
| 0 | RTL locale on the right surface | 🟢 Arabic ships as a full **text** locale, UI **and** subtitles |
| 1 | Container | 🟢 scimitar v28 — the Mirage v29 reader parsed it unchanged |
| 2 | Text codec | 🟢 CFD + char-index payload; identity round-trip **semantic PASS** |
| 3 | Mount | ✅ **CONFIRMED in-game** — `ZZ-ACO-A22-ZZ` rendered on the title screen |
| 4 | Which Arabic package | ✅ **`LocalizationPackage_Arabic` (lang 22)** — the ladder answered it |
| 5 | bidi | ✅ **VISUAL** — store pre-reversed (the shipped-Arabic stats measured the ARABIC path only) |
| 6 | Font | ✅ **zero tofu, 27/27 rendered**; 2 CFF `DINCond` faces remain un-injectable |
| 7 | Deploy | 🟢 append-relocate, **offline-validated on a copy of the real 3.26 GB forge** |
| 8 | DRM / integrity | 🟢 no Denuvo, no anti-cheat |

## The in-game proof (2026-07-27, user screenshots of the title screen)

- **`ZZ-ACO-A22-ZZ` rendered** ⇒ the rebuilt package loads, **and the ladder named lang 22 as
  the live Arabic package** — the game ships two full Arabic sets, so this was never guessable.
- **All 27 Hebrew letters rendered with zero tofu**, at a weight/size that sits naturally
  beside the shipped Arabic.
- **🔴🔴 bidi = VISUAL — the first build shipped LOGICAL and the user reported "עברית ראי".**
  Two compounding mistakes, both worth keeping:
  1. **The corpus measurement answered the wrong question.** 0 presentation forms + 0 bidi
     controls proves the engine shapes and reorders **ARABIC**; it says nothing about whether
     that pipeline is **gated to the Arabic SCRIPT**. It is — exactly like the engine sibling
     **AC Mirage** and Witcher 3 patch 4.00. The sibling's verdict was already recorded in this
     repo and outranked a fresh corpus inference.
  2. **I then "confirmed" LOGICAL from the screenshot** — the
     [[hebrew-screenshot-transcription-trap]]. Transcribing Hebrew from an image returns
     READING order, not PIXEL order, so a mirrored line and a correct line transcribe
     IDENTICALLY. The "the digit landed on the right" argument was built on that same bad
     transcription, so **a digit does not rescue a judgement made from an image** — only the
     user's eyes, or an A/B pair of one word stored both ways on ONE screen, can settle it.
- **✅ THE VISUAL REDEPLOY CONFIRMED IT FROM BOTH SIDES (user screenshots, 2026-07-27).**
  Every VISUAL row reads correctly — `המשך משחק` · `משחק חדש` · `חנות` · `אפשרויות` · `פקדים` —
  while the single LOGICAL control row (`ZZ-A22-LOGICAL םולש`, id 456223 / Sound) renders
  **mirrored**, exactly as designed. Exactly one mode can be right, and the A/B says VISUAL.
  The Latin tag on the control row also proves the screenshot is of the NEW build.
- Untouched Arabic and Latin render correctly beside the Hebrew ⇒ a partial translation
  degrades gracefully and can ship incrementally.

🔑 **Keep ONE deliberately-wrong control row in a proof.** It converts "this looks right" into
"exactly one of these can be right, and it is this one" — and its Latin tag makes a stale
deploy impossible to mistake for a fix. Costs one string.

## What was proven offline

**Container + codec.** `aco_cfd roundtrip` re-encodes a shipped resource **byte-identically to
disk** for both a Mermaid resource and a Kraken one — the strongest possible codec proof.

**Text.** `decode → encode → decode` over the four biggest packages is a **semantic PASS**
(identical `{id: text}`) but **not** byte-identical: the payload comes out ~2.0–2.4× larger,
because the game uses a multi-char fragment dictionary and our encoder is single-char. Same
behaviour as AC Unity and Mirage, both of which shipped. ⇒ resources GROW ⇒ **append-relocate,
not in-place**.

**Deploy** (`work/validate_offline.py`, run against a copy of `DataPC_patch_01.forge`):

```
[ok] entry count unchanged                      277,319 -> 277,319
[ok] file grew (append-relocate)                +1,939,540 B
[ok] header/FileSet changed ONLY in edited records   66 B, <= 220 expected
[ok] LocalizationPackage_Arabic       13/13 edits + 25,401 strings
[ok] LocalizationPackage_Arabe_MTM    13/13 edits + 25,401 strings
[ok] every injected font re-reads 27/27 Hebrew with Latin intact   9 ok / 0 bad
[ok] untouched resources byte-identical          301 sampled, 0 differ
[ok] contiguity violations == relocated count    11 / 11
[ok] revert restores the file BYTE-IDENTICALLY (journal-only, no backup)
OFFLINE VALIDATION PASS
```

### 🔴 Two real bugs the offline validation caught before the game was touched

1. **`decode_payload` returns INT keys**, so a `str(sid)` lookup matched nothing and the build
   reported *“0 edits applied”* — which reads exactly like *“this package doesn't carry the
   menu”* and would have sent the investigation the wrong way. It was masked because dumping
   the dict to JSON turns int keys into strings. Fixed with a shared type-agnostic `_key()`.
   **The same bug existed in a second place** (the validator's own check) and had to be fixed
   twice — a reminder to grep for the pattern, not just fix the first hit.
2. **Journal-revert left the appended tail**, so the file was correct but not byte-identical.
   The journal now records the pristine EOF and truncates on revert ⇒ a **multi-GB forge can
   be reverted byte-perfectly without a multi-GB backup copy**.

## Scope (from the PATCH forge — the copy that shadows the base)

| | records | |
|---|---:|---|
| UI (`_English`) | 25,763 | |
| Subtitles (`_English_Subtitles`) | 33,790 | |
| id overlap | **0** | the two spaces are disjoint |
| **GLOBAL unique ids** | **59,553** | the key space |
| **GLOBAL unique strings** | **48,583** | the workload |
| EN characters | 3,481,949 | median 42, p90 133, max 1,736 |

A **fleet job**, comparable to Witcher 3 / Skyrim.

## Oracle panel — free and complete

**Every shipped locale is a 100 % subset of English by id**, so EN→HE maps unambiguously and
the New-Era panel costs nothing: **ar · fr · it · de · es · ru · pl · nl · cs · pt-BR · ja ·
ko · zh-TW · zh-CN**, each in UI + Subtitles. Read by strength: **Russian + Polish** give
speaker *and* addressee gender (past tense), **fr/it/es** give referent gender, **de** gives
register, and **Arabic** is the Semitic near-match Hebrew wants
([[gender-oracle-from-game-langs]]). There is also a parallel `_MTM` family for every locale
and a `LocTest` package (dev/QA sets — not translation targets).

## 🔴 DO NOT dedup by the English string — measured, not assumed

1,763 duplicate-English groups exist in the subtitles (9,551 ids). Against the game's OWN
professional locales those groups get **different** translations at:

| ru | de | fr | it | pl | ar | es |
|---:|---:|---:|---:|---:|---:|---:|
| 36.7 % | 37.2 % | 34.0 % | 20.6 % | 12.7 % | 10.6 % | 10.0 % |

Seven independent locales agree that a third of them are context-dependent. **Key the pool by
id**, not by English ([[dedup-safety-from-game-langs]]).

## 🔴 Brackets are OVERLOADED — a verbatim `[...]` guard would delete content

Measured against the shipped professional Arabic, which **translates 1,160 of them and keeps
only 30 verbatim**:

| class | count | examples | rule |
|---|---:|---|---|
| **engine token** | 515 occ / 163 distinct | `[CT_ParkourUp]` `[LT]` `[NYI]` `[2105455]` | keep verbatim |
| **translator prose** | 1,554 occ / 216 distinct | `[sigh]` `[beat]` `[&gasp]` `[Save Icon]` `[[knock out]]` | **must be translated** |

The game's Arabic renders `[&gasp]` as `[&شهقة]`, `[sigh]` as `[تنهيدة]`, `[[knock out]]` as
`[[طرح على الأرض]]`. A structural guard comparing every bracket would silently strike ~1,350
real dialogue lines — the AC2 failure class. `aco_rtl.is_engine_token()` encodes the split:
a bracket is a token only when its inner text is `CT_*`, ALL-CAPS, or all-digits.

Other tokens (measured): `<tag>` 16,439 occ / 86 distinct (`<font face='DINPro_Bold'>`,
`</font>`, `<i>`, `<style name='Quest'>`), **`{PLACEHOLDER}` 2,705 occ / 88 distinct and
NAMED as well as numeric** (`{NAME}`, `{FULLNAME}`, `{TARGET_NAME}`, `{price}` — a `\{\d+\}`
regex would miss most of them), `%spec` 7, `\n` 1,416, HTML entities 0.

## bidi — VISUAL (store pre-reversed)

From 2,101,526 Arabic characters in the shipped locale: **0 presentation forms, 0 bidi control
characters**, and 32,749 lines end with `. ! ? ،` against 108 that start with one. That proves
the engine shapes *and* reorders **ARABIC** — and the RTL pipeline is gated to the Arabic
SCRIPT, so **Hebrew is drawn in storage order**. Confirmed in-game.

⇒ ship `aco_rtl.to_visual`: the real Unicode Bidi Algorithm with an RTL base, engine tokens
stashed as atomic PUA placeholders, and each `\n` segment converted independently so line order
survives ([[store-visual-use-real-uba]]). Never hand-roll run reversal — a 1-char neutral run
reverses to itself, so a menu label looks perfect while every real sentence is wrong.

**A corpus statistic measures the language it was computed on.** To predict Hebrew, look at
what a SIBLING title on the same engine actually did ([[bidi-is-version-dependent]]).

## 🟡 The one open item — 2 CFF faces

`DINCond-Medium` and `DINCond-Bold` are **OTTO/CFF**, and `_add_hebrew` is a `glyf` merge —
a **no-op** on them, so they are skipped rather than silently shipped un-injected. They are
condensed HUD/subtitle faces. If the proof shows tofu on a surface the other faces don't
cover, those two need the TLOU1-style **whole-font REPLACE** (donor font + masqueraded `name`
table) instead of a merge. All 9 other faces are at 27/27.

## Verdict

🟢🟢 **GO.** The container, codec, text format, deploy and activation are all solved and
verified against the real game files; the font is injected on every face that can take a merge.
Phase 1 ends at the deployed proof — see PIPELINE.md.

## מסמכים קשורים
- באותה תיקייה: [[games/acodyssey/PIPELINE|PIPELINE]], [[games/acodyssey/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acodyssey|CLAUDE_INDEX_games]]
