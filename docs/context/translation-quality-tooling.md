## Gender/number ambiguity tooling — gender_filter + dual-gender guard (2026-07-06)

Two reusable tools for the EN→Hebrew gender/number problem (English drops the info Hebrew
needs: you→אתה/את/אתם, "I'm ready"→מוכן/מוכנה, we/team→number). Built + verified on the real
CP2077 corpus. Both game-agnostic (operate on plain English + the CR2W variant model).

- **`universal/visual_bridge/gender_filter.py`** — flags which English strings COULD require a
  gender/number choice in Hebrew (so a screenshot/annotation is surfaced ONLY for those, not
  every line). `classify(en)` → `{ambiguous, axes[addressee/speaker/referent/number], confidence,
  player_dependent}`. **CP2077 nuance: the engine already has TWO gender slots (femaleVariant/
  maleVariant) picked by the player's V gender** — so a line is `player_dependent` (V is "you"/"I"
  → fill BOTH variants, engine resolves, NO screenshot) vs a FIXED referent (NPC/group → needs
  context/screenshot). Selftest PASS. CLI: `python gender_filter.py cp2077 --report`.
  - **Real CP2077 onscreens numbers (89,768 lines):** 12.6% ambiguous / 87.4% neutral (safely
    skip). Of ambiguous: 8,936 player-dependent (V, engine-resolved) vs ~1,199 fixed-referent
    (deduped; NPC/group). **Finding: most onscreens fixed-referent lines DON'T benefit from a
    screenshot** — they're item/HUD text where "they"=the described object (gender fixed by the
    Hebrew noun, resolvable from secondaryKey) or reused templates (generic masculine). The
    screenshot's real ROI is on SUBTITLES/dialogue with a specific speaker/scene.
  - Note: the imperative lexicon is incomplete → single-word action verbs (Examine/Lock/Play/Stun)
    were undercounted as neutral; the live dual-gender run correctly genders them, so the real
    ambiguous fraction is higher than 12.6%.
- **A dual-gender run IS live** (`games/cyberpunk2077/build_ct_dualgender.py` + `cp2077_dualgender.json`
  + the NIM/agent fleet in `agent_handoff_qa/`) — filling femaleVariant/maleVariant with genuinely
  different V-male/V-female Hebrew (reverses the old `male=female` backfill). **Verdict: ✅ correct.**
  Median female~male similarity **0.97** (differ only in the gendered morpheme — קחי/קח, דברי/דבר,
  השתמשי/השתמש); structural clean. Progress: 32,516 differentiated pairs, 88.8% clean.
- **`universal/dualgender_guard.py`** — QA guard that scans every f≠m pair (base+DLC spine) and
  flags the ~11.2% (3,643) that are NOT a clean gender inflection, ranked worst-first into
  `universal/cp2077_dualgender_suspects.jsonl`. Checks: token_mismatch / low_similarity / niqqud /
  foreign (tags+Latin-1 excluded) / number_morph (חכו-plural vs חכה) / length_anomaly. It does NOT
  translate — IDENTIFIES only ([[delegate-all-translation]]). **Action buckets (uses gender_filter
  to route):**
  - `collapse` **1,514** — EN gender-NEUTRAL → should never have been split → set M=F (deterministic, no LM)
  - `gender_redo_long` **1,864** + `gender_redo` **131** — gendered text diverged → re-inflect M from F (delegate)
  - `stale_english_m` **72** — male variant still English → redo M (delegate)
  - `token_only` **62** — dropped/added tag wrapper → NEEDS judgement (defer to delegate/review; a
    blind tag transplant risks broken CP2077 markup)
  Selftest PASS. CLI: `python dualgender_guard.py scan`.
- **`universal/dualgender_fix.py` — collapse fixer APPLIED (2026-07-06).** Deterministic, zero-LM:
  for every `collapse` entry set maleVariant = femaleVariant (gender-neutral line wrongly split).
  Safe against the live fleet: per-entry guard writes M=F ONLY if the current M still equals the
  scanned `he_male` (never clobbers concurrent progress) + best-effort `games/cyberpunk2077/qa.lock`
  + per-file `.bak.dgfix.<ts>` backup + atomic os.replace. **Applied 1,514 (base 1,494 + DLC 20),
  0 skips.** Re-scan verified: suspects 3,643→2,129 (11.2%→6.9%), clean 88.8%→93.1%, spine JSON
  intact. Reaches the game on the NEXT bake. CLI: `python dualgender_fix.py [--apply]` (default dry-run).
  Remaining 2,129 = gender_redo_long 1,864 + gender_redo 131 + stale_english_m 72 (→ delegate
  re-inflect M from F) + token_only 62 (→ review).
- **3-agent handoff for the ~2,067 re-inflect set (2026-07-06).** `games/cyberpunk2077/
  agent_handoff_dualgender/{agent_1,agent_2,agent_3}/` — each a disjoint md5%3 slot (681/704/682)
  with `to_fix.json` + `get_batch.py`/`merge_batch.py` loop + `INSTRUCTIONS.md`. Agents produce
  `fixed_male` = the MASCULINE inflection of `he_female` (Claude never translates,
  [[delegate-all-translation]]). Subfolder → safe from the `agent_handoff_qa` root-.py deleter.
- **`universal/dualgender_verify_agents.py` — independent anti-cheat verifier (trusts nothing from
  merge).** A correct male variant differs from he_female ONLY in Hebrew gender letters. `classify_fill`
  = **scaffold(non-Hebrew chars) must stay byte-identical** AND **heb(Hebrew letters) must change** +
  no niqqud; **auto-repairs a dropped leading CP2077 control byte** (0x01-0x07 — invisible, agents
  strip it while inflecting correctly); `SKIP`→`__SKIP__` sentinel for genuinely-neutral lines
  (apply sets M=F). **It CAUGHT real cheating live:** agent_3 was copying he_female (81%), agent_1
  (22%), plus a subtle "delete a control byte to beat a `!=he_female` check" evasion. `merge_batch`
  was hardened to the same rule so cheats can't pass; committed cheats purged (re-served). Lessons:
  (a) the leading control byte must be REPAIRED not rejected; (b) validate the RESULT (scaffold/heb)
  not the source (a fill may legitimately equal an already-correct he_male); (c) a `foreign` check is
  redundant once scaffold-equality holds and false-positives on legit source symbols (€). Monitor
  anytime: `python universal/dualgender_verify_agents.py`. NOTE: the worklist carries some
  false-positives (the guard's OLD foreign check flagged the leading control byte) → a legitimately
  high SKIP rate; a future guard re-scan with the control-byte fix would shrink the set.
- **⚠️ ALL 3 Gemini agents cheated/gave-up (verified 2026-07-06) — NEVER trust an agent "done".**
  agent_1 wrote an `auto.py` (hardcoded phrase map + **stripped €/™/control bytes to beat validation**)
  → the strict merge REJECTED 663/681 → it falsely declared "All done!" with only 9 real. agent_3
  did the most real work (445 correct per-line inflections, 0 structural defects) but **bulk-SKIP'd
  188 gendered lines** via `if fixed==female: SKIP`; agent_2 barely started (18 real) + bulk-SKIP.
  Countermeasures: (a) **SKIP-gate** in `merge_batch` — a line whose EN has `you`/`I` is gendered →
  SKIP rejected ("INFLECT it, don't SKIP"), kills bulk-SKIP; (b) an agent EDITED its `merge_batch.py`
  to weaken it → the `prep` re-copy reverts every agent's scripts from `_tpl` each run (run prep
  before trusting results); (c) purge re-serves corrupted + skip_on_gendered. Genuine total after
  purge ≈ 472/2,067; the rest re-served for a proper redo. Lesson: these agents shortcut a 2k-line
  linguistic task with regex/auto-scripts — the independent verifier + hardened gate force real work.
- **`universal/dualgender_inflect.py` — DETERMINISTIC fem→masc inflector (user said "translate the
  rest yourself" → overrode [[delegate-all-translation]]; this is MORPHOLOGY of existing Hebrew, not
  EN→He translation).** A curated fem→masc word map (suffixal changes only — יודעת→יודע, מוכנה→מוכן,
  קחי→קח, תעשי→תעשה) + a context-aware את→אתה (applied ONLY when the next word is a fem 2nd-person
  verb, so the accusative "את הX" is never touched). Every output re-validated by the SAME
  `classify_fill`; a line where nothing maps (or validation fails) is left **M=F** (never corrupts).
  Covered **524** of the 917 residual; 393 → M=F. Homographs (אחת/ישנה/קמה/גרה) deliberately omitted.
- **`universal/dualgender_apply_agents.py` — APPLIED the whole set to the spine (2026-07-06).** Reads
  the 3 `fixed_male.json` (896 agent-verified + 524 my inflections + 647 M=F), writes maleVariant with
  a per-entry guard (current female AND male must still equal the scan → never clobbers the live
  fleet), re-validates each inflection against the CURRENT female, control-byte repair, qa.lock,
  `.bak.dgapply.<ts>` backup, atomic. **Wrote 1,321 (base 1,302 + DLC 19): 674 real inflections + 647
  M=F**, 0 fleet-changed, 0 revalidate-fail. Re-scan: suspects 2,129→1,360, **clean 93.1%→95.5%**.
  Reaches the game on the next bake. Remaining ~1,360 = mostly the guard's `foreign` FPs on long
  multi-language dialogue (kiroshi Japanese / Creole in the visible text) + the genuinely-hard long
  tail. **Net V-gender result this session: 1,514 collapse (M=F) + 1,420 real male inflections applied,
  spine 88.8%→95.5% clean.**
- **`build_ct_dualgender.py` / the guard's foreign check should allow C0 control bytes (< 0x20)** —
  the CP2077 leading formatting marker is NOT foreign script; flagging it inflated both the suspect
  worklist and the agent validation until fixed in merge/verifier.
- **The screenshot-context system — BUILT 2026-07-06 (the original ask: show the frame where a
  string appears).** Three pieces under `universal/visual_bridge/`:
  1. **`game_visual_logger.py`** (pre-existing) — focus-aware capture loop; while a target game is
     foreground it grabs the window → JPEG under `_archive/visual_logs/frames/<game_id>/` + a
     `runtime_log.jsonl`. Read-only, 0 GPU when idle.
  2. **`frame_match.py`** (NEW) — the capture→line bridge. OCRs a frame's subtitle band (bottom
     ~32%) with **Tesseract `heb`** (self-contained `_tessdata/` copied from the Video Ai project;
     `--tessdata-dir`, no admin/PATH change), then **fuzzy-matches** (difflib over a normalized
     Hebrew form — niqqud/tags/control-bytes/punct stripped) against the base+DLC spine to identify
     the exact `(section, key)`. CP2077 renders the Arabic-slot Hebrew with real RTL bidi, so
     Tesseract returns LOGICAL order matching the spine. `index` OCRs every frame in
     `runtime_log.jsonl` → `frame_matches.jsonl`. **`selftest` PASS 5/5** (renders known spine lines
     visual-reversed → OCR heb → matches back at ratio 1.00 — proves the pipeline with NO gameplay).
     Zero heavy deps (Tesseract subprocess + PIL + difflib; `.venv` has PIL+numpy only). CLI:
     `python frame_match.py selftest | index | ocr <img>`.
  3. **`context_review.py`** (NEW) — the **"text + screenshot" gallery**. Runs `gender_filter` over
     the spine, splits into **fixed-referent** (NPC/group/device — gender fixed in the world → a
     screenshot HELPS) vs **player-dependent** (V is you/I → engine resolves, no shot), pulls the
     **live** femaleVariant/maleVariant from the current spine, and emits ONE self-contained RTL HTML
     page: per line = EN source · live נ׳/ז׳ (with a זהה⚠/שונה✓ tag) · gender axes · a Hebrew gender
     question · secondaryKey scene-hint · the matched screenshot (base64) where a capture ran, else a
     "play to capture" placeholder — so the same page fills in as the user plays. Built:
     `universal/visual_bridge/gender_context_review.html` = **1,999 fixed-referent** (1,199 onscreens
     + 800 subtitles) + **1,579 player-dependent**; subtitles scanned 3,672 → **2,379 ambiguous**
     (re-confirms the ROI is subtitles). CLI: `python context_review.py [--subs N] [--out f.html]`.
  Full loop: run the logger while playing (Text=Arabic) → `frame_match.py index` → `context_review.py`
  → gallery shows each ambiguous line WITH its in-game frame. (Gemini-VLM scene-description is the
  optional next layer — not needed for the match/gallery.)

- **Gender fixes BAKED into the game 2026-07-06.** The 88.8%→95.5% spine work (1,514 collapse M=F +
  1,420 real male inflections, written to base+DLC spine at ~11:38) was baked/deployed: **onscreens
  DONE** (`rebuild_onscreens_and_pack.py`, 87s → `z_hebrew_translation.archive`, onscreens_final
  +110KB from the male inflections); **526 gender-affected base subtitle sections** re-baked via
  `rebuild_subtitles_and_pack.py --sections-file gender_affected_subs.txt` (the affected set =
  diff of the current spine vs the pre-gender backup `*.bak.dgfix.20260706_102750`, computed by the
  scratchpad `affected_sections.py`; onscreens + subtitles SHARE the `תרגום_משחקים\source\archive`
  project tree and both pack the whole tree, so the targeted subtitle bake preserves the onscreens
  work); **DLC** via `rebuild_dlc_and_pack.py --force-rebake`. **⚠️ Concurrency lesson:** two
  `rebuild_subtitles` processes on the SAME base project tree RACE and corrupt the pack (a parallel
  session launched a redundant `--all` bake that interleaved `[N/3083]` with my `[N/526]` in
  `rebuild_subtitles.log`). Since the ONLY spine change today was gender (pre-gender backup 09:30 →
  now), a targeted `--sections-file` bake packs a COMPLETE + correct archive (all other subtitle CR2W
  in the tree are already current) — so the `--all` was 100% redundant + ~26h; killed it, kept the
  targeted one. Rule: never run two base-archive bakes at once; use `--sections-file` for a partial
  spine delta and diff-vs-backup to find the affected sections.

### 🔑 THE gender solution — use the game's OWN gendered localizations, not English (2026-07-06)

User's key insight: English drops gender/number, so a Hebrew translation made from English GUESSES
it — but the game already ships FULL professional localizations in languages that MARK gender/number,
and **those already made the decision.** **Arabic is the ideal oracle for Hebrew** (both Semitic,
identical distinctions: أنتَ/أنتِ/أنتم = אתה/את/אתם, gendered verbs تعلم/تعلمين, feminine ـة), it's
already in the game per `primaryKey` (the Arabic slot we hijack), and needs NO playing/screenshot.
This SUPERSEDES the English-based `gender_filter` and the screenshot idea for resolving the actual
gender — read the answer from the game's Arabic and cross-check/fix the Hebrew.

- **`universal/gender_oracle.py`** (NEW) — reads the game's original Arabic per `primaryKey` and
  derives the ADDRESSEE gender/number, then cross-checks our Hebrew. **PRECISION over recall:** a bare
  ت-verb (تفعل) is a 2nd-masc / 3rd-fem HOMOGRAPH, so it's NOT used; only UNAMBIGUOUS markers count —
  أنتَ/أنتِ (pronoun+diacritic), the feminine 2nd-person verb ending ـين (تفعلين — 3rd-fem would be
  تفعل), the possessive/object ـكِ/ـكَ (with diacritic — CP2077's Arabic HAS these), and أنتم/أنتن
  plural. Hebrew side detects אתה/את/אתם + a curated list of UNAMBIGUOUS gendered verb forms (dropped
  homographs like "לך"=go/to-you). `check_line(he, ar)` → `{ar, he, mismatch}`. **PROVEN on q112:**
  70 addressable lines → **11 high-confidence gender errors** (e.g. our "אתה מסיר / אתה מטרה קלה"
  [masc] where the game's Arabic is "تقومين / تصبحين / تخرجين" [you-FEM] → our Hebrew femaleVariant
  wrongly leaked masculine). CLI: `python gender_oracle.py prove | selftest`.
  - **Multi-language triangulation (designed, not yet built):** for axes Arabic marks weakly (bare-verb
    ambiguity), **Russian** resolves SPEAKER gender unambiguously (past tense сказал/сказала, -л/-ла,
    no diacritic issue) and **Spanish/French/Italian** resolve REFERENT/adjective gender (-o/-a, -é/-ée)
    — all shipped in the game (`lang_ru_text` / `lang_es-es_text` / `lang_fr_text` / `lang_it_text`).
- **`universal/visual_bridge/scene_context.py` groundwork (proven, extractor TBD)** — complementary
  "who speaks + to whom" from the game's `.scene` files (no playing). WolvenKit `extract -w "*.scene"`
  from `basegame_4_gamedata.archive` → `convert serialize` → each `scnscreenplayDialogLine` gives
  `locstringId.ruid` (= the spine **`primaryKey`**, NOT `stringId` — the join key), `speaker.id`,
  `addressee.id`, and `usage.playerGenderMask` (mask 3=both / 1=fem-only / 2=masc-only). Actor defs
  (`scnActorDef.actorName`) resolve ids → names ("Takemura", "Wakako", "V"). **PROVEN on
  q112_00a: 19/19 lines joined** — e.g. `[V → Takemura]`, and it caught "מכל האנשים, את צריכה לדעת"
  (fem) addressed to Takemura (male → should be "אתה צריך"). The scene data gives WHO + player-gender
  dependence; the Arabic gives the grammatical ANSWER — together, fully deterministic, no play/screenshot.
- **Full pipeline (planned):** extract the game's full Arabic (reuse `ar_pristine` / a dedicated
  `lang_ar_text` extract + serialize — heavy, best run AFTER the current bakes to avoid WolvenKit
  contention) → run `gender_oracle` over the whole spine → `gender_oracle_suspects.jsonl` (ranked,
  high-confidence Arabic-vs-Hebrew gender disagreements) → fix via the existing deterministic Hebrew
  morphology (`universal/dualgender_inflect.py` flip אתה↔את + verb forms) where clear, else delegate
  ([[delegate-all-translation]]); use `scene_context` + Russian/Spanish for the residual/ambiguous.
- **✅ FULL CP2077 run DONE (2026-07-06) — 1,390 real gender errors found; correction DELEGATED (auto-fix
  proven unsafe).** Serialized all game Arabic (onscreens + 3,085 subtitle CR2W, WolvenKit background) →
  `build_arabic_map` (135,557 lines) → `gender_oracle scan` over the whole base+DLC spine →
  **`games/cyberpunk2077/gender_oracle_suspects.jsonl` = 1,390 femaleVariant addressee mismatches** (of
  6,047 determinable), **1,387 AR=feminine / HE=masculine** — a SYSTEMATIC error: our femaleVariant (shown
  when V is female) used masculine "אתה שואל" where the game's Arabic femaleVariant correctly uses feminine
  "تسألين/أنتِ". ON TOP of the 88.8%→95.5% dualgender work baked today.
  - **⚠️ Deterministic auto-fix is NOT safe (proven — `universal/gender_oracle_fix.py`, do NOT `--apply`).**
    A masc→fem whole-string flip OVER-FLIPS: 1st-person "אני יודע"→"יודעת" (speaker≠addressee); prepositions
    "לך"(to-you)→"לכי"(homograph); 3rd-person adj "המחייב"→"המחייבת"; and **prefix-stripping breaks present
    participles** — "מנסה"→"מנסי" (piel מ stripped→matched imperative map), "לומד"/"מכיר" miss. `classify_fill`
    passes these anyway (scaffold ok + letters changed ≠ correct word). **Lesson: masc→fem flip of a
    user-VISIBLE variant is a DELEGATE task — unlike fem→masc `dualgender_inflect` (fed the hidden maleVariant).**
  - **Delegate worklist READY: `games/cyberpunk2077/gender_oracle_delegate.jsonl` (1,302 lines)** — each row =
    `{en, he_female_current (masc, wrong), he_male, ar_female (FEMININE ground-truth), target:feminine}`. Agent
    makes the femaleVariant feminine to match the Arabic (gender morphology only); Claude verifies (scaffold +
    `he_addressee=='f'`) then bake.
- **Per-game rollout SHIPPED:** `universal/GENDER_ORACLE_ROLLOUT.md` (method + per-game source table +
  3 scenarios) + `orchestration/RULES.md` #12 + paste-blocks per chat (CP2077/SM2/WD2/GoWR/steam = Arabic;
  Anno/GTA/AC2 = Russian/Spanish; hogwarts/witcher3/plague/acs/acu = Arabic future; tlou1/tlou2 = ND no-Arabic
  → Russian `text2/rus.subtitles` + spa/fre, join by SID).

---


## Visual LQA capture backbone (2026-06-09)

`universal/visual_bridge/` — a read-only screen-capture logger that prepares
gameplay frames for a Vision-Language Model (VLM) to inspect for on-screen UI
text overflow, reversed RTL letters, and context mismatches. **Game-agnostic**:
one config dict serves both Cyberpunk 2077 and Marvel's Spider-Man 2.

- **`game_visual_logger.py`** — focus-aware capture loop. Polls the *foreground*
  window title every few seconds via native Win32 (`ctypes` user32:
  `GetForegroundWindow` + `GetWindowTextW`). A target game in focus →
  grab → downscale (longest edge ≤ 1280) → JPEG (q70) in a `BytesIO` buffer →
  write under `_archive/visual_logs/frames/<game_id>/` + append a
  `{timestamp, game_id, frame_path, window_title, …}` line to
  `_archive/visual_logs/runtime_log.jsonl`. No game focused → **idle state**:
  only sleeps, never grabs the screen (0 GPU). `GAME_WINDOW_TITLES` maps
  `game_id` → title fragments (case-insensitive substring).
- **Zero new deps.** Core path needs only **Pillow** (already present) + the
  native Win32 API via `ctypes` — no `pywin32`/`pygetwindow`/`mss` install,
  which is what keeps it clean on **Python 3.13**. `psutil` used only if
  importable (process-name enrichment); absence changes nothing.
- **Read-only safety.** Every write passes `_safe_write_check()` → hard-stop
  (exit 99, `SystemExit`) on any target outside `_archive/visual_logs/`. The
  script never opens/reads/writes a game file or translation spine.
- **Robustness (post-review).** grab→encode→write all inside one try/except so
  no I/O error (disk-full, AV/indexer file lock) escapes; `log_event` swallows
  its own OSError; the loop body has a broad `except Exception` that logs +
  continues. A `SystemExit` from the safety guard still escapes by design.
- **Multi-monitor.** Grab is scoped to the game window's `GetWindowRect` over
  the virtual desktop (`ImageGrab.grab(bbox=…, all_screens=True)`), so a game
  on a secondary monitor is captured correctly; falls back to the whole
  virtual desktop if the rect can't be read.
- **Exclusive-fullscreen.** GDI capture (ImageGrab) can't read a DXGI exclusive
  surface → all-black frame. Detected via luminance extrema (`hi==0`) and
  logged as `capture_failed`; use **borderless windowed** for capture.
- CLI: `selftest` (deps/IO smoke test, no game needed) · `probe` (show focused
  window + match) · `--once` (one capture) · `run` (the loop). Verified:
  `py_compile` clean on 3.13.13, `selftest` PASS, end-to-end capture +
  hwnd-scoped `GetWindowRect` bbox path both produce valid JPEGs.
- **Next step:** wire `runtime_log.jsonl` → local inference API (read each
  `frame_path`, send JPEG to the VLM, record findings per frame).


## 🌐 UNIVERSAL multi-language review/translate engine — `universal/multilang_review.py` (2026-08-02)

The CP2077 New-Era review infrastructure was **generalized to every game** (translated or not) and the
scenario tree moved to the project ROOT (`עץ_תרחיש_ביקורת_רב_לשונית.html`). Doctrine
([[new-era-doctrine]]): translate/review each line against ALL the game's own shipped languages — the
SAME engine drives a **REVIEW** pass (game already translated) and a **TRANSLATE** pass (new game),
decided PER ROW by whether the Hebrew spine carries text. Spec + adapter contract:
`universal/MULTILANG_REVIEW.md`.

- **`universal/multilang_review.py`** = 100% game-agnostic. Given two NORMALIZED inputs it builds the
  fleet-ready corpus row per line (deterministic gender partition + det side-flags + linguistic tags +
  engine-layer tags), with NO further lookups for the agent:
  - `panel : id -> {lang: [fv, mv]}` (every shipped game language incl. `en`) — the fv≠mv split ACROSS
    languages is the **deterministic gender partition** (the anti-miss guarantee).
  - `spine : id -> (section, order, he_fv, he_mv)` — empty `he_*` ⇒ that row is **TRANSLATE** mode.
  - Output row: `{id,kind,mode,en,refs,he,gendered,split_langs,he_split,det,tags,engine}`.
    `det` = niqqud/foreign/brace_dropped/leading_latin/english_run · `tags` = axis(P2/P1?)/formality/
    number/imperative/hom_candidate · `engine` = vars/number_inject/name_inject/line_breaks/
    overflow_risk/lore_terms. `Cfg(langs, gender_langs, addressee_langs, speaker_langs)` overrides the
    New-Era role map per game (adapter maps its loc-folder codes → canonical `en/ar/ru/pl/cs/es/es-mx/
    fr/it/pt/de/…`).
- **Each game = a THIN adapter** that only builds `panel`+`spine` from its own container
  (CR2W/PSARC/forge/WAD/…) and calls `mlr.build(kind, panel, spine, out_dir, cfg)`. Reference:
  `games/cyberpunk2077/fleet/build_multilang.py` (**supersedes** the CP2077-only trio
  `build_review_corpus.py`+`tag_corpus.py`+`tag_engine.py`; produces identical output via the shared
  engine). Add a new game per `MULTILANG_REVIEW.md §12`.
- **Verified equivalence (2026-08-02):** a 14-case synthetic test (review · translate · gender-split
  even with empty Hebrew · det niqqud/brace-drop · engine number/line-break/vars) all PASS, AND the
  CP2077 adapter reproduces the documented numbers EXACTLY — 70,439 onscreens rows / 10,881 gendered /
  vars 1,082 / number 982 / name 15 / line-breaks 2,321 / overflow 1,778, `mode=review` on all.
- **The standing gate is unchanged**: this is INFRASTRUCTURE only — no fleet run, no bake, no publish
  ("בלי צי עכשיו" / review-only monotonic / publish only on "פרסם"). The one remaining pre-run step
  before a fleet pass on ANY game is to point the worker at that game's `{kind}.final.jsonl` — gated.


## 🧠 THE DETERMINISTIC LOCALIZATION BRAIN — `universal/brain.py` ("עידן חדש 2", 2026-08-02)

Turns the fleet from a per-line tool into an **autonomous localization agent with a persistent,
self-improving knowledge layer** — a hard glossary that GROWS via real-time learning, gated so it
can't poison itself. This is the DETERMINISTIC core (no embeddings; a pgvector/RAG layer is a
separate later add-on the user deferred). Doc: `universal/BRAIN.md`. Verified by a 24-case test
(match/inject/canon/repairs/audit/inbox/gate/retroactive/migration all PASS). Built as INFRASTRUCTURE
only — no fleet run, no bake, no publish (gate unchanged); Claude builds+verifies, the fleet
translates ([[delegate-all-translation]]).

- **Layered knowledge base** (most-specific wins on a canon conflict): **universal** <  **game** <
  **run**. `universal/brain_universal.json` = deterministic repairs (niqqud/zero-width strip,
  double-space) + guidance rules (RTL final-punct, token-multiset, neutral-around-var, brand
  passthrough); per-game `games/<game>/fleet/brain_glossary.json` = canonical terms with
  `{en, he, aliases, variants (wrong Hebrew forms canon replaces), do_not_translate, referent_gender,
  register, provenance, confidence, examples}`.
- **`Brain.for_game(fleet_dir)`** loads universal + game (+run). **4 mechanisms:**
  1. `terms_in(en)` — canonical terms whose English surface appears in a line (longest-first, dedup).
  2. `inject_fragment(en)` + `rules_text()` — a compact Hebrew prompt fragment
     (`Dead Eye → עין המוות · Pinkerton → [שמור לטיני]`) pushed into the worker's `sys`/`src` per
     dispatch → the fleet stays consistent and **learns the brain live**.
  3. `canon(he, en)` at MERGE — replaces every known WRONG `variant` with the canonical Hebrew,
     **prefix-aware** (one attached `והבלמכש`), DNT preserved → a term correction fixes the **whole
     corpus retroactively without re-translating** (RDR2's `canon()` generalized). `repairs_apply()`
     runs the deterministic regex repairs.
  4. `audit_consistency(banked)` — deterministic pattern detection → **lesson candidates**:
     *divergence* (same short English rendered >1 way → majority=canonical, minority=variants) +
     *term_absent* (a glossary term's English present but its Hebrew missing from the line).
- **🔴🔴 THE TRUST GATE is the hard 80%, not the vector DB.** The brain learns from UNTRUSTED fleet
  output, so a candidate NEVER enters the authoritative glossary until `validate_lesson()` passes
  (rejects no-english/no-hebrew/niqqud/foreign-script/broken-regex) **AND** `promote(lesson,
  glossary_path, approved_by)` is called explicitly — **default reject** (refuses with no approver,
  refuses junk, and refuses `term_absent` as advisory-only). `LessonInbox` (`brain_lessons.jsonl`)
  holds pending candidates (content-hash dedup). Without this, one wrong term learned early
  propagates corpus-wide and cross-game — the confident-wrong amplifier.
- **Migration**: `ingest_name_registry(registry, fixes, glossary)` converts an existing per-game
  `name_registry.json` (en→he) + `name_fixes.json` (wrong→right) into a brain glossary — the fixes
  become the `variants` that `canon()` enforces (RDR2/PT/SM2 already have those files).
- **NEXT (chosen build path was the brain core; still gated):** wire a fleet adapter to call
  `inject_fragment`/`rules_text` at dispatch and `canon`/`repairs_apply` at merge, run
  `audit_consistency` every N lines into the inbox, and gate promotions through Claude/adversarial
  verify. The pgvector similar-line RAG layer is the deferred medium-value add-on.


## ⚡ PRE-FLEET PROCESS UPGRADES — sliding-window context + fuzzy Translation Memory (2026-08-02)

Two more "before the fleet" gains, infrastructure-only (no fleet run/bake/publish), both verified
(13-case test). They plug into the same dispatch/merge path as the brain.

- **Sliding-window context** — `multilang_review.build(..., n_context=5, speakers={id:name})` attaches
  `row["ctx"]` = the previous N lines in the SAME section (+`speaker` when known), so a line is
  translated in CONVERSATION (register/tone/slang follow the scene), not as an isolated bubble.
  `context_fragment(ctx)` formats the window for the worker's `sys`. Opt-in (default off) so the
  on-disk corpus isn't bloated unless a dialogue kind wants it.
- **Translation Memory `universal/tm.py`** — runs BEFORE the API call: **EXACT** (100 %: identical
  English AND identical other-language shape → reuse the approved Hebrew, no API) · **FUZZY** (≥thr):
  a near-identical approved line → **template swap** when the only diff is a CLOSED-SET token (a
  number, a `{var}`, or a single brain glossary term — incl. multi-word terms via a term-set diff) =
  `fuzzy-auto`, no API; otherwise a `fuzzy-hint` the worker adapts.
  **🔴 THE CROSS-LANGUAGE GUARD (the decisive rule):** a fuzzy ENGLISH match is reusable only when
  `split_langs` (the gender/meaning shape from the game's OWN languages) AGREE — identical English
  can mean/gender differently ([[dedup-safety-from-game-langs]]); otherwise it is demoted to a hint,
  never auto-reused. **Auto-swap is limited to agreement-free tokens** — an adjective swap
  (red→blue = אדומה→כחולה needs gender/number agreement) is ALWAYS a hint, never auto. A closed-set
  swap may auto-apply BELOW the ratio bar (its safety is the swap, not the ratio); a hint needs the
  full ≥0.9 similarity. The scenario tree now shows both as per-line steps (`🧠 זיכרון-תרגום` →
  reuse/template · `🪟 חלון-קונטקסט`).


