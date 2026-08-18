## Assassin's Creed Origins Hebrew — ✅✅ PHASE 1 COMPLETE, every gate closed in-game, 🟢 GO (2026-07-27)

**✅✅ ROUND 2 CAME BACK — the SUBTITLE surface is VISUAL, and the same row exposed the one
real Phase-2 build requirement.**
- **bidi (subtitles) = VISUAL ✅**, settled by the A/B pair landing on ONE screen exactly as the
  `id % 3` rotation was designed to do: `ZZ-SUB-L-ZZ` (stored LOGICAL) rendered **`םולש תירבע`**
  = mirrored, while `ZZ-SUB-V-ZZ` (stored VISUAL) rendered **`שלום עברית`** = correct, on
  adjacent lines of the same conversation. **Both surfaces are VISUAL — but it was PROVEN per
  surface, not inherited from the UI** ([[bidi-per-surface-not-per-product]]); the UI sits in an
  LTR slot and the subtitles in the game's real Arabic locale, two different renderers that
  could have disagreed. Within a line the layout is right too (`(סוגריים) "מרכאות" — מקף,
  נקודה. שאלה? 12.5% ואז` — every mark, paren, quote, digit and Latin island in place).
- **🔴 THE STORE-VISUAL WRAP TRAP FIRED, and it is the reason the layout row exists.** The
  90-char paragraph rendered with its **LINE ORDER INVERTED** — `סימני פיסוק:` (the logical
  START) on the BOTTOM line, `סוף!` on the TOP — because the engine wraps in **STORAGE** order
  (§8b rule 4). Every character inside each line was correct; only the line order was wrong,
  which is precisely why a short-label proof clears it and the real corpus breaks.
  **Measured exposure: 5,077 of 14,782 subtitle rows (34.3 %) are >60 chars** (median 45,
  p90 103, max 961), and **the shipped Arabic pre-wraps only 11 of 12,844 rows** — because it
  never has to (Arabic gets engine bidi, so logical-order wrapping is correct for it). ⇒
  **Phase 2 MUST pre-wrap** with a real `\n` (the break the corpus already uses on 30 rows),
  budgeted in **font units, never character count**.
- **🔴🔴 ROUND 3'S RULER WAS EATEN BY THE ENGINE — `[...]` CAN NEVER BE A PROOF MARKER HERE.**
  I tagged each rung `[N] ‹body› [N]`; **not one bracket or digit reached the screen** (the
  ruler rendered as bare Hebrew filler). Verified from BOTH sides so it is a render-side fact,
  not a build bug: **4,268 rows carry a `[N]` in the LIVE forge** and `--verify` matched on it
  ⇒ **Origins parses `[...]` as a control-name substitution and renders an unknown name as
  NOTHING.** **THE TRAP, and it generalises: I chose `[N]` *because* `aor_rtl` protects an
  all-digit bracket as an atomic engine token — but "my transform must not touch it" and "the
  engine claims it" are the SAME property read from two sides.** A proof marker must be a
  string the ENGINE has no meaning for. Phase-2 corollary, now backed in-game rather than by
  corpus counts alone: **a prose bracket left in a form the engine does not recognise is
  DELETED, not shown** — which is exactly why the shipped professional Arabic (which translates
  239 prose brackets and keeps 1) is the per-bracket oracle.
- **ROUND 4 — THE BOX IS MEASURED: 23.66 em, a 3 % bracket.** The fixed ruler
  (`W‹n› ‹filler› W‹n›`, whole string exactly n chars, rungs 36·40·44·46·48·50·54) came back:
  **W36/W40/W48 fit on one line, W54 wraps.** 🔑 **The WRAP POINT is worth more than the
  pass/fail** — W54 broke after **40** chars leaving a 13-char second line, and simulating a
  greedy wrap of that exact stored string shows the engine would have fit **50** (last line a
  lone `W54`) had the box been ≥ 24.355 em. So `box ∈ [23.66, 24.35)`. **Ship 23.66 em** (the
  lower bound — a string of exactly that width was SEEN to fit; ≈ 46 Hebrew chars). Falsifiable:
  W50 must wrap. **UNIVERSAL: always give a width ruler at least one rung that OVERFLOWS and
  read WHERE it broke — matching the observed split against a simulated greedy wrap turns a
  coarse "between 48 and 54" into a 3 % bracket, from the same screenshot.** Pre-converted to
  Heebo advances, so the number is **face-independent** (Heebo is in all 9 faces).
- **✅ THE PRE-WRAPPER IS BUILT, not just specified.** `aor_rtl` gained `text_em` /
  `wrap_logical` / **`to_visual_wrapped`** (+ `BOX_EM_SUBTITLE`). Order matters: wrap the
  LOGICAL text, THEN convert each line — wrapping after the conversion wraps reversed text.
  `text_em` is token-aware: markup (`<font…>`, `<i>`) draws nothing, and a runtime-substituted
  `{NAME}` / `[CT_*]` (real width unknowable at build time) is charged a nominal 4 em so a line
  carrying one is never wrapped over-optimistically. Validated on **all 14,782 subtitle rows: 0
  words dropped/added, 0 lines over budget, 0 token-multiset changes**; 40.4 % of rows wrap.
  Selftest 20/20.
- **⚠️ A STALE DOCSTRING THAT WOULD HAVE SHIPPED MIRRORED HEBREW.** `aor_rtl.to_logical` still
  described itself as "the SHIPPING transform" and `to_visual` as "the A/B counterpart used by
  the menu proof ONLY" — written before round 1 and **backwards ever since**. A Phase-2 build
  that trusted the docstring instead of the findings would have stored LOGICAL on both surfaces.
  Both are corrected, and `to_visual` now points at `to_visual_wrapped` for anything long enough
  to wrap. **UNIVERSAL: when a proof overturns a prediction, grep the TOOLING for the old claim —
  the doc you update is rarely the only place the wrong answer is written down.**
- **🟢 PHASE 1 IS COMPLETE. Nothing blocks Phase 2.** Candidate B was then tested: the user set
  `Text=ar-AR` by hand and launched — **the game itself reverted `Text` back to `en-US`** on that
  launch (`Subtitles=ar-AR` stayed untouched; confirmed by reading `ACO.ini` afterward). This is
  the game's own language-validation writing a known-good value over an unsupported one, not a
  failed load. ⇒ **`Text` has no Arabic option, only `Subtitles` does — candidate B was never
  reachable, and no installer trick changes that.** Candidate A remains the sole, already-proven
  UI path (zero user actions). Nothing left to test; Phase 1 is fully closed.


## Assassin's Creed Origins Hebrew — Phase-1 groundwork detail (2026-07-27)

New game at `games/acorigins/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` + `extract/`).
Install `F:\Games\Assassin's Creed Origins` (Ubisoft Montreal 2017, **AnvilNext 2.0**,
Uplay-emulated), exe `ACOrigins.exe`, proposed `games.id` = **`acorigins`** (⚠️ check the live
catalog first — Odyssey's real row was `acodyssey`, not the `ac-odyssey` I proposed).
The proof is **deployed and verified against the live forge; only a launch is left.**
Memory [[acorigins-groundwork-go]].

- **🔑 THE WHOLE CONTAINER/CODEC/LOC/FONT/DEPLOY WORKSTREAM WAS REUSE — one `head -c 16`
  decided it.** `scimitar` **v28**, header_size 1050 = byte-identical in layout to **AC
  Odyssey**, so `games/acodyssey/tools/*` copied over with the paths retargeted and parsed
  707/707 entries with 0 errors on the first run ([[engine-family-reuse-check-magic]]). CFD
  codec identical; the game ships its own `oo2core_4_win64.dll`.
- **🔴🔴 THE DEFINING FACT (the user said it, the data confirmed it exactly): Arabic ships for
  SUBTITLES ONLY.** `LocalizationPackage_Arabic` (**UI**) is a **457-byte / 20-record STUB**
  while `LocalizationPackage_Arabic_Subtitles` is **372,940 B / 12,844 records**. The AC Unity
  pattern. ⇒ **subtitles = Arabic-slot hijack · UI = LTR (English) slot hijack**, and **bidi is
  therefore decided PER SURFACE** ([[bidi-per-surface-not-per-product]]).
  The 20 stub rows are nevertheless REAL translations (`خيارات`=OPTIONS, `العربية`, `تجهيز`),
  so the package is a live object — worth laddering, not assuming dead.
- **🔑 ACTIVATION IS A PLAIN-TEXT INI WITH THREE INDEPENDENT FIELDS, AND THE CODE IS `ar-AR`.**
  `Documents\Assassin's Creed Origins\ACO.ini` → `[Language] Text=en-US · Sound=en-US ·
  Subtitles=ar-AR`. **`uplay_install.state` and `HKCU\SOFTWARE\Ubisoft\Assassins Creed
  Origins\Language` both say `ar-AA`** — that is Ubisoft's language-PACK id; the GAME reads
  `ar-AR`. Same trap as Odyssey: **the game's own config file is the tie-breaker, never the
  manifest or the registry.** ⇒ UI Hebrew costs the user **ZERO actions** (en-US is the
  default) and English VO is preserved for free.
- **Scope = 23,005 records / 21,924 GLOBAL unique English / 1,322,501 chars** (UI 8,223 rec /
  7,678 uniq, median 25 ch, max 2,699 · subs 14,782 rec / 14,269 uniq, median 46 ch; **id
  spaces disjoint, overlap 0**). A **single pass — no fleet**. There is **no
  `DataPC_patch_01.forge`**, so §8e does not fire for the base text; the DLC text is additive
  in `DataPC_22_dlc_patch_01.forge` (`DLC22-30_*`, +1,902 Arabic subtitle rows).
- **🔑 Oracle panel is free and wide — 12 languages at 100.0 % UI key parity** (fr de it es ru
  pl cs nl br ja ko + zh), 86.9 % on subtitles; ru+pl give speaker AND addressee gender and the
  shipped Arabic subtitles are the Semitic near-match.
- **🔴 DO NOT DEDUP BY THE ENGLISH STRING — measured on the game's OWN professional locales.**
  Subtitles: 288 duplicate-EN groups diverging at **ru 44.7 % · fr 38.8 % · de 36.5 % ·
  pl 32.2 % · ar 28.6 %**; UI: 368 groups at 6-15 %. **Key by id**
  ([[dedup-safety-from-game-langs]]).
- **🔴 Brackets are OVERLOADED here too** — 366 engine-token occ vs **310 prose**, and the pro
  Arabic **translates 239 of the prose ones and keeps 1** (`[sigh]`, `[Save Icon]`,
  `[Hem Netcher]`). ⚠️ **ORIGINS DELTA: `[KB_LeftShift]` / `[RightStick]` are engine tokens but
  are not ALL-CAPS**, so Odyssey's `_ENGINE_BR` called them prose — widened in `aor_rtl.py`.
  A small tail (`[A]` `[Bm]` `[Dpad]` `[0x00100100]`) still misclassifies; Phase 2 should use
  the pro-Arabic itself as the per-bracket oracle, which beats any regex.
- **🟢 FONT — better than Odyssey: 9 faces, ALL `glyf`, NOT ONE is CFF/OTTO**, so a glyf merge
  works on every one (Odyssey had to leave 2 `DINCond` faces un-injected). All 0/27 Hebrew →
  all injected to **27/27** from Heebo, original cmaps intact. Three carry Arabic (DINPro
  576 KB = the Arabic UI face, ACE-TrajanBold = titles, ACE-SimplifiedChinese-Noto).
- **🟢 DRM: Denuvo + VMProtect on the exe only** (`.vmp0`/`.vmp1`, 140 MB `.xtls`) but
  **0 EAC/BattlEye, 0 `tamper` strings, 3 `integrity`, 41 `SHA256`** — the AC-Shadows profile
  (asset mods load), not the Black-Flag-Resynced content-hash wall (×143/×5/×11). Large mature
  forge-mod scene corroborates.
- **✅ DEPLOYED + VERIFIED (12 resources, append-relocate, +13.7 MB).**
  `work/validate_offline.py` ran the whole chain on a COPY of the real forge first: entry count
  707→707, header byte-identical, 300 untouched resources byte-identical, 9/9 fonts 27/27,
  **revert byte-identical → PASS**. Then live, and `--verify` re-read the LIVE forge (never the
  builder): both markers present, 12,844/12,844 subtitle rows proofed, 9/9 fonts → **PASS**.
  Backup `DataPC.forge.he_backup` + `.he_journal.json`; revert
  `python games/acorigins/work/build_proof.py --revert`.
- **THE LADDER — both UI candidates ship in ONE deploy** ([[measure-with-a-ladder]]):
  **A** `LocalizationPackage_English` marker `ZZ-AOR-ENUI-ZZ` (default `Text=en-US`, zero user
  actions) · **B** `LocalizationPackage_Arabic` **filled to 8,223 ids** marker
  `ZZ-AOR-ARUI-ZZ` (`Text=ar-AR`) — if B loads we also get the engine's own RTL menu layout for
  free. Whichever marker appears names the winner.
  **Subtitles are proofed by ROTATION `id % 3`** (VISUAL · LOGICAL · punctuation paragraph), so
  any conversation shows both bidi modes on adjacent lines and the user never has to hunt for a
  specific scene. One deliberately-WRONG LOGICAL row with a Latin tag is kept on purpose.
- **bidi predicted VISUAL on both surfaces.** The shipped Arabic is 488,234 standard-block
  chars with **0 presentation forms / 0 bidi controls** and 10,388 lines ending in punctuation
  vs 26 starting — that proves the engine shapes and reorders **Arabic**, and says nothing
  about Hebrew ([[corpus-stats-measure-their-own-language]]); the engine siblings **Mirage and
  Odyssey** both turned out script-gated ⇒ VISUAL. The UI slot is LTR, so it gets no bidi at
  all. The A/B decides.
- **🔴 THE INT-KEY TRAP FIRED THREE TIMES IN ONE SESSION** — `decode_payload` returns **INT**
  ids, so a str-keyed `update()` silently ADDS 20 new ids (changing nothing) and a str-keyed
  `get()` returns `None` and reads as a failed deploy. It hit the builder, the offline
  validator and `verify()`. **The documented cure is the one that worked: grep the whole tree
  for the pattern instead of fixing the first hit** ([[json-roundtrip-hides-key-type]]).
- **🔴 A VERIFICATION PREDICATE WRITTEN AGAINST LOGICAL TEXT FAILS ON VISUAL DATA.** The
  `id%3==2` subtitle rows are stored pre-reversed, so the literal `אבגד` is not a substring —
  the validator reported 8,576/12,844 on a **perfectly correct** build. Match both forms, or a
  correct build reads as a two-thirds failure.
- **✅ `/translate` POOL LIVE — 28,537 rows, FOLDING IN THE DLC (2026-07-27).**
  `work/build_ct_strings.py` → `universal/community_translate.py import acorigins`. Ordered by
  VISIBILITY: **ממשק ותפריטים 11,094 → כתוביות עלילה 17,443** (114 dropped, token-only).
  `string_key` = `ui:<id>` / `subs:<id>` — **0 id overlap between base and DLC** (measured:
  disjoint ranges in both directions and both kinds), one key scheme covers both with no
  prefix. Every row carries the game's own **Arabic + Russian + Polish** in `context`. Verified
  live: both category chips exact-count, 0 round-trip mismatches.
  **🔴 Found while building it: the DLC's English package is named
  `DLC22-30_LocalizationPackage_English(US)`** (not `…_English`) — the `(US)` suffix silently
  evaded `scope_report.py`'s bare-`"English"` lookup, so the earlier "21,924 global-unique"
  headline was **BASE-ONLY** and missed ~2,868 new UI + ~2,611 new subtitle DLC lines.
  **True total = 28,537.** **UNIVERSAL: a language-suffix lookup keyed on a bare name
  (`"English"`) silently drops any package with a region/edition qualifier
  (`English(US)`, `Spanish(Mexico)`) — list a DLC/patch forge's packages BY NAME and diff
  against the lookup table, don't trust a clean parity report that just never mentions the
  missing language.**
- **NEXT (Phase 1 COMPLETE; nothing blocks Phase 2):** delegate the 28,537 lines
  ([[delegate-all-translation]], single pass, no fleet, **key by id**, 12-language oracle panel,
  gender from ru/pl + the shipped Arabic) → build the UI through **`aor_rtl.to_visual`** and
  every subtitle through **`aor_rtl.to_visual_wrapped`** (already measured + validated) →
  `aor_loc.rebuild` + `aor_deploy.apply` for BOTH `DataPC.forge` and
  `DataPC_22_dlc_patch_01.forge` → publish only on an explicit "פרסם".
- **STATE: the round-3 proof is DEPLOYED + verified** (12 resources, backup
  `DataPC.forge.he_backup` + `.he_journal.json`). Revert:
  `python games/acorigins/work/build_proof.py --revert`.


