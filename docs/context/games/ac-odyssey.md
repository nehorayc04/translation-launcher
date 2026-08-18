## Assassin's Creed Odyssey Hebrew — ✅✅ PHASE 1 COMPLETE, EVERY GATE CLOSED IN-GAME, 🟢🟢 GO (2026-07-27)

**✅✅ THE PROOF CAME BACK (user-confirmed 2026-07-27) — mount, package-ladder and font closed
on the first screenshot; bidi took a correction.**
- **MOUNT ✅** — `ZZ-ACO-A22-ZZ` rendered ⇒ the rebuilt LocalizationPackage loads, and the
  **LADDER ANSWERED: `LocalizationPackage_Arabic` (lang 22) is the LIVE package**, NOT
  `_Arabe_MTM` (lang 24). Phase 2 only has to patch the lang-22 pair (patching both stays as
  cheap insurance). Shipping two full Arabic sets is exactly the case where guessing costs a
  launch — [[measure-with-a-ladder]].
- **FONT ✅ ZERO TOFU** — all 27 letters rendered as real glyphs; Heebo→DINPro injection works
  and the size/weight sit naturally beside the Arabic.
- **🔴🔴 bidi = VISUAL, NOT LOGICAL — I called it wrong twice and the USER was the authority.**
  The deployed LOGICAL build came back as **"עברית ראי"**. Two compounding errors:
  1. **The corpus measurement answered the wrong question.** 0 presentation forms + 0 bidi
     controls + 32,749 lines ending in punctuation proves the engine shapes and reorders
     **ARABIC** — it says NOTHING about whether that pipeline is **gated to the Arabic
     SCRIPT**. It is. Odyssey behaves exactly like its engine sibling **AC Mirage** (and
     Witcher 3 patch 4.00): Arabic correct, Hebrew drawn in storage order. **I had the answer
     in this very file and didn't apply it — for an Anvil title, read the SIBLING game's
     verdict before trusting a fresh corpus inference.**
  2. **I then "confirmed" LOGICAL off the screenshot** — the exact
     [[hebrew-screenshot-transcription-trap]]. Transcribing Hebrew from an image returns
     READING order, not PIXEL order, so a mirrored line and a correct line transcribe
     IDENTICALLY. My "the digit landed on the right" reasoning was built on that same bad
     transcription, so the digit trick does NOT rescue a judgement made from an image.
     **The only reliable instruments are the user's eyes, or an A/B pair of the same word
     stored both ways on ONE screen where exactly one can be the readable word.**
  ⇒ `aco_rtl.to_visual` (real UBA, RTL base, engine tokens stashed as atomic PUA runs) is the
  **SHIPPING** transform; `to_logical` is the A/B counterpart only. Rebuilt + redeployed.
  **✅ CONFIRMED FROM BOTH SIDES:** every VISUAL row now reads correctly (`המשך משחק` ·
  `משחק חדש` · `חנות` · `אפשרויות` · `פקדים`) while the single deliberately-LOGICAL control row
  (`ZZ-A22-LOGICAL םולש`, id 456223 / Sound) renders **mirrored**. 🔑 **Keep ONE deliberately-
  wrong control row in every proof** — it turns "this looks right" into "exactly one of these
  can be right, and it is this one", and its Latin tag makes a stale deploy impossible to
  mistake for a fix. Cost: one string.
- Untouched Arabic (`تحميل اللعبة`) and Latin (`UBISOFT CLUB`) render correctly alongside ⇒ a
  PARTIAL translation degrades gracefully and can ship incrementally.

**✅ COMMUNITY `/translate` POOL LIVE — 59,430 rows (2026-07-27).**
`work/build_ct_strings.py` → `extract/ct_upload.json` → `universal/community_translate.py
import acodyssey`. **⚠️ `games.id` is `acodyssey`** (the row already existed: planned/final,
free, shown on both surfaces) — **NOT the `ac-odyssey` I had proposed; the detector key must
match the EXISTING row.** Ordered by VISIBILITY: **ממשק ותפריטים 25,658 → כתוביות עלילה
33,772**, from the engine's OWN surface metadata (which package a string lives in), never a
length heuristic. Only **123 dropped** (no real letter survives token removal).
`string_key` = **`ui:<id>` / `subs:<id>`** — the two id spaces are disjoint but the prefix says
which package an approved line goes back into. **Round-trip verified before importing: 0
unresolvable keys, 0 `source_en` mismatches.** **55,273 rows carry the game's own ARABIC *and*
RUSSIAN in `context`** as the gender source (Arabic = the Semitic near-match, Russian past
tense marks speaker AND addressee); **no auto-derived hint** — Odyssey's Arabic is largely
unvocalized and an open-class guess manufactures confident garbage
([[gender-hint-needs-closed-set]]). Verified through the PUBLIC API, not the importer's
message: total 59,430 / open 59,430, both Hebrew category chips with exact counts, first
served batch is UI.


## Assassin's Creed Odyssey Hebrew — Phase-1 groundwork detail (2026-07-27)

New game at `games/acodyssey/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` + `extract/`).
Install `F:\Games\Assassin's Creed Odyssey` (Ubisoft Quebec 2018, **AnvilNext 2.0**, Uplay-
emulated). **`games.id` = `acodyssey`** (the catalog row already existed — always check before
proposing an id; the detector key must match it). Detector exe `ACOdyssey.exe`. Memory
[[acodyssey-groundwork-go]].

- **🔑 THE WHOLE CONTAINER WORKSTREAM WAS REUSE — check the magic FIRST.** `scimitar` **v28**
  sits between AC Unity (v27) and Mirage (v29), and **`mirage_forge.py` parsed EVERY Odyssey
  forge unchanged** (total_count == entries read, 0 contiguity errors on all 33 readable
  forges, 443,356 entries). The CFD codec (`0x1004FA9957FBAA33`) is Shadows'/Mirage's verbatim,
  and the loc payload is the same char-index fragment tree as AC2 v25 / Unity v27
  ([[engine-family-reuse-check-magic]]).
- **🔴 ODYSSEY MIXES OODLE CODECS PER RESOURCE** — entry #1 is **Mermaid**, entry #60 is
  **Kraken**. Read it off `byte1 & 0x7F` of a real block, never assume one per game
  ([[oodle-codec-is-byte1-not-byte0]]). With per-resource sniffing the re-encode is
  **BYTE-IDENTICAL to disk** on both. The game **ships its own `oo2core_4_win64.dll`**.
- **🟢 Arabic is a FIRST-CLASS shipped text locale — and there are TWO full sets**:
  `LocalizationPackage_Arabic` (lang 22) and `LocalizationPackage_Arabe_MTM` (lang 24), each
  with UI + Subtitles, all populated. 66 packages total. Which one `ar-AR` resolves to is
  **laddered in the proof** (distinct Latin markers) rather than guessed.
- **🔴 ACTIVATION IS A PLAIN-TEXT INI, AND THE CODE IS `ar-AR`, NOT `ar-AA`.**
  `Documents\Assassin's Creed Odyssey\ACOdyssey.ini` → `[Language] Text/Subtitles/Client=ar-AR`
  with **`Sound=en-US` independent ⇒ English VO for free**. `uplay_install.state` pairs the two
  codes (`…\Language` + `ar-AA` + `ar-AR`): `ar-AA` is Ubisoft's language-PACK id, `ar-AR` is
  what the game reads — and **every other locale has that pair identical** (`en-US`/`en-US`),
  which is exactly why the difference is easy to miss. I first wrote `ar-AA` from the pack list
  and only caught it by reading the game's own config. **UNIVERSAL: when a manifest lists two
  codes for one locale, the game's own settings file is the tie-breaker — never the manifest.**
- **🔴 §8e FIRED: `DataPC_patch_01.forge` shadows the base.** The same 62 package ids exist in
  both forges with **different, larger payloads** (EN UI 639,263 vs 612,481 B; 25,763 vs 24,590
  strings). Both are patched. Fonts are duplicated too — 15 in each forge under **different
  ids** but with **byte-identical TTFs** — so both sets are injected.
- **Object names are PLAINTEXT here** (unlike Mirage's encrypted patch-forge names), so a
  package is addressed by name. **⚠️ The language-id enum is NOT standard** — a plausible guess
  was wrong by an offset on the European block; it was DERIVED by reconciling each id against
  its own package name (1 English · 2 French · 3 Italian · 4 German · 5 Spanish · 22 Arabic ·
  24-39 the parallel `_MTM` family · 39 LocTest).
- **Scope = 59,553 unique ids / 48,583 unique strings / 3.48 M chars** (UI 25,763 + subtitles
  33,790, **0 id overlap**), median 42 ch, max 1,736 — a FLEET job like Witcher 3 / Skyrim.
- **🔑 Oracle panel is FREE and complete: every shipped locale is a 100 % subset of English by
  id** — ar/fr/it/de/es/ru/pl/nl/cs/pt-BR/ja/ko/zh ×(UI+subs). ru+pl give speaker AND addressee
  gender, fr/it/es referent, de register, Arabic the Semitic near-match.
- **🔴🔴 DO NOT DEDUP BY THE ENGLISH STRING — measured, not assumed.** 1,763 duplicate-English
  groups (9,551 ids); against the game's OWN professional locales they diverge at **ru 36.7 % ·
  de 37.2 % · fr 34.0 % · it 20.6 % · pl 12.7 % · ar 10.6 % · es 10.0 %**. Seven independent
  locales agree a third are context-dependent ⇒ **key by id** ([[dedup-safety-from-game-langs]]).
- **🔴🔴 BRACKETS ARE OVERLOADED — a verbatim `[...]` guard would delete ~1,350 dialogue lines**
  (the AC2 failure class). The shipped professional Arabic settles it: it **translates 1,160 and
  keeps only 30** — `[&gasp]`→`[&شهقة]`, `[sigh]`→`[تنهيدة]`, `[[knock out]]`→`[[طرح على الأرض]]`.
  Split: **engine token** 515 occ/163 distinct (`[CT_ParkourUp]` `[LT]` `[NYI]` `[2105455]`) vs
  **translator prose** 1,554 occ/216 distinct. `aco_rtl.is_engine_token()` = inner is `CT_*`,
  ALL-CAPS, or all-digits. ⚠️ Also `{PLACEHOLDER}` is **NAMED as well as numeric**
  (`{NAME}` `{FULLNAME}` `{TARGET_NAME}` `{price}`) — Mirage's `\{\d+\}` regex would miss most.
- **bidi = VISUAL (store pre-reversed).** The corpus stats (2,101,526 Arabic chars, 0
  presentation forms, 0 bidi controls, 32,749 lines ending `. ! ? ،` vs 108 starting) prove the
  engine handles **ARABIC** — that pipeline is gated to the Arabic SCRIPT, so Hebrew is drawn
  in storage order. Same as AC Mirage. See the correction at the top of this section.
- **🟡 Font: 15 faces, 0/27 Hebrew → injected 9/9 at 27/27** (Heebo donor into DINPro ×7 +
  Friz Quadrata; the Arabic UI face is the 511 KB DINPro at 37/43 Arabic). **2 faces are
  OTTO/CFF (`DINCond-Medium`/`-Bold`) and a glyf merge is a NO-OP on them** — skipped rather
  than shipped un-injected. If the proof shows tofu on a DINCond surface they need the
  TLOU1-style whole-font REPLACE.
- **🔑 OFFLINE VALIDATION ON A COPY CAUGHT TWO REAL BUGS BEFORE THE GAME WAS TOUCHED**
  (`work/validate_offline.py`, run against a copy of the real 3.26 GB patch forge):
  1. **`decode_payload` returns INT keys**, so `str(sid)` matched nothing and the build reported
     *"0 edits applied"* — which reads exactly like *"this package doesn't carry the menu"* and
     had already produced a wrong conclusion in my notes. **Masked because dumping the dict to
     JSON turns int keys into strings.** The same bug existed in the validator's own check and
     had to be fixed twice. **UNIVERSAL: after a JSON round-trip you can no longer tell a dict's
     real key type — assert it, and grep for the pattern rather than fixing the first hit.**
  2. **Journal-revert left the appended tail**, so revert was correct but not byte-identical.
     The journal now records the pristine EOF and truncates ⇒ **a multi-GB forge reverts
     byte-perfectly without a multi-GB backup copy.**
  Final: 277,319 entries unchanged · 13/13 edits in both packages · 9/9 fonts 27/27 · **301
  untouched resources byte-identical** · header/FileSet changed only in the edited records ·
  revert byte-identical → **PASS**.
- **STATE: DEPLOYED + VERIFIED in the live game** — 11 resources in `DataPC_patch_01.forge` +
  11 in `DataPC.forge`, `ACOdyssey.ini` at `ar-AR` with `Sound=en-US`. Backups
  `<forge>.he_backup` + `.he_journal.json`. **Revert:
  `python games/acodyssey/work/build_menu_proof.py --revert`.**
- **NEXT (Phase 2, all gates closed, pool already live):** delegate the 59,430 lines
  ([[delegate-all-translation]], fleet + the free 100 %-parity oracle panel, **key by id, never
  by the English string**) → build via **`aco_rtl.to_visual`** → `Package.rebuild` →
  `aco_cfd.encode_resource` (sniffed codec) → `aco_deploy.apply` into the **lang-22** Arabic
  UI + Subtitles pair in both forges → publish only on an explicit "פרסם".
  Optional polish: the 2 CFF `DINCond` faces (whole-font REPLACE) if a HUD surface shows tofu,
  and the Options-page layout row (punctuation/parens/digits) which is the one proof row not
  yet eyeballed.


