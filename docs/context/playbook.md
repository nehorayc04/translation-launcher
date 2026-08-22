# 🌍 UNIVERSAL Game-Translation Playbook (reusable for ANY future game)

Distilled from CP2077, Steam, and Spider-Man 2. **Read this first when starting a new
game translation** — it captures the architecture and the expensive lessons so a new
game reuses the proven path instead of re-discovering it. Per-game code lives under
`games/<game>/work/`; copy the SM2 trio (`sm2_translate.py` / `sm2_watchdog.py` /
`sm2_progress.py`) as the template.

> 📘 **Two standalone "new game" playbooks (2026-06-21)** — mined from EVERY chat + /compact
> summary + game folder across all games. When the user says **"מתחיל את הקרקע למשחק חדש"**,
> drive **Phase 1** with [`universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md`](universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md)
> (every pre-translation check: engine/format map, Arabic-slot, logical-vs-visual bidi, font
> injection + atmosphere fit, identity round-trip, menu-proof, UI-vs-subtitle count report, the
> "forgotten" traps, + a per-engine facts appendix for CP2077/SM2/WD2/GoWR/ACS/AC2/Steam). Then
> hand off translation via [`universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`](universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md)
> (**Phase 2** — a fill-in-the-`<...>` instruction for a fresh agent with no history, the proven
> autonomous loop + the 4 helper scripts, modeled on `games/watchdogs2/agent_handoff/`). The
> sections below remain the condensed reference; the two files are the expanded, checklist-driven versions.


## 0. The core trick — Arabic-slot hijack for free RTL Hebrew
Game engines almost never have a Hebrew locale but DO have **Arabic** (RTL). Ship the
Hebrew text **inside the Arabic locale slot** → you inherit the engine's tested RTL/bidi
pipeline for free. Proven on **CP2077** (CR2W `ar-ar`), **Steam** (`*_arabic-json.js`,
`language:"arabic"`), **SM2** (Arabic localization `variant_18`). The user sets the game's
interface language to Arabic; Hebrew renders correctly RTL.

### 0a. 🔴 FIRST, open the game's LANGUAGE SETTINGS and see which surfaces offer an RTL locale
Learned the expensive way on **AC Unity** (2026-07-20). Many games expose **two independent
language settings** — e.g. `Menu Language` (UI) and `Subtitles language`. AC Unity's
**`Menu Language` has NO Arabic at all** (LTR only) while `Subtitles language` does ⇒ menus are
*structurally* unreachable for Hebrew (a missing locale, not a font problem) and the game is a
**subtitles-only** target. That single screenshot would have saved an entire font
reverse-engineering campaign. **Do this BEFORE any font work**, and record per-surface which slot
is RTL. Same class as WD2's english-locked frontend. Corollary: **bidi is decided PER SURFACE** —
an LTR UI slot gets no engine bidi (store VISUAL) while the game's real RTL locale does (store
LOGICAL); never assume one mode for the whole game.

### 0b. 🔴 Font-hunt rules that prevent weeks of dead ends
- **An offline-perfect font injection that still renders tofu is PROOF the renderer uses a different
  font.** If the cmap has the glyphs, the outlines are real (`contours>0`, sane bbox/advance), and a
  re-read of the *deployed* archive confirms all of it — stop iterating on that font. On AC Unity,
  Hebrew was injected into **all 7** embedded TTFs (the only fonts in the entire game, verified by
  decompressing every resource in all 50 non-GI forges) and the menu still showed 8 boxes for an
  8-letter word. Trust the in-game pixel over the file.
- **A modding tool's "SupportedGames" list is NOT evidence the artifact exists.** AnvilToolkit lists
  AC Unity under its `FireData` (Scaleform SWF) class; the game ships **zero** FireData resources.
  Verify by scanning for the artifact, not by reading the tool's capability table.
- **Validate every "font found" hit.** The sfnt magic `\x00\x01\x00\x00` matches enormous amounts of
  random binary — require a plausible table directory *and* a successful fontTools load. Likewise
  resource names: AC Unity's `TGFX_*` are particle TEXTURES and `TACU`'s "BEP Rift Light" /
  "Reach Font" are **mission + lighting names**, not fonts.

### 0c. 🔴 A silently-failing codec dependency turns every scan into a false negative
The scanners' `try/except` swallowed `lzallright` (LZO) being absent from the machine's base
Python, so **every forge scan returned a convincing "0 hits"** — indistinguishable from a real
negative, and nearly the basis of a wrong conclusion. **Always run archive tooling with the repo
`.venv` python, and assert the decoder actually decodes a known-good resource before trusting any
"nothing found".** Two related environment rules: use **forward slashes** for Windows paths in Bash
(`"$G\\$f"` mangles backslash-followed-by-variable), and **parallelize CPU/disk sweeps with
background shell jobs, never a Workflow of LLM agents** — one agent per forge (50) hit server
rate-limits (40/50 failed, ~2.5M tokens for 10 forges) while plain background Bash did the lot free.


## 1. Pipeline shape (same for every game)
1. **Extract** the game's text: the **English source** (what you translate) + the **Arabic
   skeleton** (the structural target you fill). 2. **Translate** EN→Hebrew with the local LM,
   writing into the Arabic-slot structure (preserve every tag/placeholder). 3. **Build/pack**
   into the game's mod format. 4. **Deploy** to the game's mod folder. 5. **Publish** (GitHub
   release + Worker manifest + Supabase `games` row). The data files you translate ARE the
   resumable checkpoint.


## 2. Local LM (LM Studio) — the hardware reality
- Hardware here: **RX 9070 (RDNA4), 16 GB VRAM, Vulkan runtime** (NOT ROCm — ROCm fails on
  RDNA4). A **31B model (~20 GB) SPILLS to RAM** (`lms ps` DEVICE=Local) → **~1-2 tok/s**.
- **MUST serve serial `--parallel 1`** — concurrent requests on a RAM-spilled model split the
  fixed throughput and time out. Client workers = 1.
- **Reload recipe (reboot / drop / hang):** `attrib -R %USERPROFILE%\.lmstudio\.internal /S /D`
  (clears the recurring ReadOnly flag that blocks load) → `lms load <model> -y --gpu max
  --context-length 8192 --parallel 1`.
- **A quant that FITS VRAM is 5-15× faster** (full-GPU). Offer it as a quality/speed choice.
- **Hang signature:** `lms ps` STATUS=`GENERATING` for many minutes with zero output. **Never
  reload while a client holds the hung request** — kill the client FIRST, then `lms unload
  --all`, then load, then **probe with a tiny real request** (`lms ps` says "loaded" even when
  hung; only an end-to-end generation proves health).


## 3. Translator template (`<game>_translate.py`)
- **SHORT strict system prompt (~400 tok, NOT ~1000)** — it is re-prefilled on EVERY batch and
  prefill dominates on a slow model. Keep all HARD rules, cut prose/examples. Rules: Hebrew+Latin
  only · NO niqqud · copy tags/placeholders/format-specs EXACTLY (`<ts>`, `[TOKEN]`, `{VALUE}`,
  `%d`/`%%`, `&rlm;`/`<br>`) · character & place names stay English · `[sound cues]` translated ·
  output only numbered lines.
- **Type-aware / token-budget batching:** short UI/dialogue lines → fixed batch (e.g. 10).
  Subtitle/cutscene lines vary wildly (ONE key can be a whole multi-segment scene of hundreds of
  tokens) → **pack by ESTIMATED output tokens**, size `max_tokens` per batch from the estimate,
  let a huge scene go solo. Fixed-count subtitle batches TRUNCATE.
- **Serial loop, generous TIMEOUT, flush after EVERY batch attempt** so the done-count advances
  promptly (the watchdog's hang detector keys off it).
- **Resilience:** retry the missing subset once + singleton fallback; misses stay queued → no
  entry ever lost. **Atomic writes** (temp + `os.replace`) so a watchdog kill never corrupts the
  state JSON.
- **`validate()`** rejects foreign-script / niqqud / empty; ACCEPTS a no-Hebrew result only when
  the source is a **name/code** (no real lowercase word ≥2: "Miles?", "F.E.A.S.T.", "5x[CURRENCY]")
  — else those false-skip forever and waste retries. **Skip-list** for permanently-unfixable keys.


## 4. Self-healing watchdog template (`<game>_watchdog.py`) — RUN THIS, it owns the stack
- **ONE supervisor** brings up + babysits LM + translator + progress-pusher, unattended for the
  multi-day/week haul. Crash-protected loop, singleton-guarded, hourly structural QA.
- **Launch under BASE python**, NOT the venv `python.exe` — the venv exe is a **redirector stub
  that double-spawns** (two PIDs per logical process) → breaks singleton + cmdline-based process
  detection.
- **Liveness via `Popen.poll()`** on handles it launched (not fragile cmdline scans); relaunch on
  death. **Children detached** → survive a watchdog restart; a fresh watchdog clears orphans first.
- **Recovery order is ALWAYS: kill the client FIRST → reload LM (`unload --all`) → probe →
  relaunch.** Reversing this (reload while busy) is why SM2 lost 10 hours.
- **Hourly structural QA:** re-check lines translated since the last tick; remove bad ones (atomic)
  so they re-translate; park a key failing 3×.


## 5. ⚠️ The two killer gotchas (cost 10 h on SM2 — NEVER regress)
1. **UTF-8 stdout.** A Windows child launched without `PYTHONIOENCODING` gets **cp1255** stdout;
   the first `print` containing `→`/`…`/emoji raises `UnicodeEncodeError` and **kills the process**
   silently. ALWAYS `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at script start
   AND launch children with `env PYTHONIOENCODING=utf-8`.
2. **Reload-while-busy.** Never `lms unload/load` while a client holds a hung request, and never
   use `unload MODEL` on a hung model — use `unload --all` after killing the client.


## 6. Progress to the website (`<game>_progress.py`)
60 s loop → `POST /api/admin/progress` (`MONITOR_TOKEN` from root `.env`) with `{gameId, phase,
processed, total, meta.alive:true, aiModel, gpuModel}`. The homepage `pickActiveSnapshot` surfaces
the freshest live snapshot (others >2 h stale are filtered). The `gameId` must match the Supabase
`games.id` so the dashboard shows the right title. Keep `phaseLabelHe` short (the game name + % are
shown separately by the dashboard).


## 7. Structural QA checks (language-agnostic, reusable `qa_entry`)
For each translated line vs its English source + Arabic reference: `<ts>`/timing-tag multiset
preserved · `&rlm;` present iff the Arabic ref ends with it · `[UPPER_TOKEN]`+`{VALUE}` placeholders
preserved · printf `%`-specs preserved (Arabic-gated per-key: if `arabic[key]` has `%%` it's a
printf string) · no foreign script · no niqqud · not byte-identical to English (untranslated leak).
**⚠️ The "untranslated leak" check MUST share the translator's name/code passthrough rule** (accept a
no-Hebrew result when the source is a name/code — proper-noun ≤4 words OR no real lowercase word),
else QA churns forever on every character-name / reward-code entry and (if it kills the translator to
rewrite output) destroys throughput. Cost on SM2: ~4× slowdown until caught.


## 7b. 🔴🔴 COMPLETENESS audit — "100%" is a CONTENT measure, never a key count (GoWR 2026-07-07)
The single most expensive class of bug in this project: a game reported **100% translated** and the
user still saw untranslated text everywhere. GoWR shipped "48,885/48,886 = 100%" while **1,270 real
strings** were garbled, blank or English. Every rule below is game-agnostic — run them BEFORE
claiming a game is done, and re-run them on the DEPLOYED artifact after every bake.

1. **Measure by CONTENT, not by key presence.** `len(hebrew.json) == len(english.json)` proves
   nothing: a `validate()` name/code passthrough silently accepts a no-Hebrew result, so real prose
   sits in the spine as English and is counted "done". The only honest metric is
   **`has_target_script(value)`** per entry. GoWR's true state was 48,676 Hebrew of 49,700 keys.
2. **The corpus is not the container — audit the DEPLOYED file.** Ids can exist in the game archive
   that are absent from your spine (GoWR: **313 Arabic-only** ids with no English source, skipped by
   an EN∩AR pipeline, which then fell back to the pristine Arabic — and since font injection WIPES
   the Arabic glyphs, they rendered as garbage/blank). **Always diff `set(archive_ids)` against
   `set(spine_ids)`** and assert 0 missing; a "no subtitle at all" report is usually this.
3. **🔑 Define the fix set by EXCLUSION, never by an inclusion heuristic.** This is what caused three
   consecutive "you missed more" rounds. Inclusion filters keep missing whole categories:
   `has a lowercase word ≥3` missed **short Title-Case dialogue** (`Got it.`, `Hey, Loki.`,
   `Just do it.`, `For Lejre!`, `Quick Start`) and **accented-but-ASCII Old Norse** (`Skál!`,
   `Veggur bifröst!`, `Dynja íss!` — a þ/ð/æ regex misses á/í/ö). The correct sweep is
   **"everything non-target-script, MINUS explicitly enumerated junk classes"** (brands, roman
   numerals, aspect ratios `4:3`, multipliers `1.5x`, single button letters `L/R/C`, dev
   placeholders `Temp N.A.W. Desc`, `_`/CamelCase codes, pure symbols). Then PRINT the leftover and
   eyeball it — if every leftover is provably junk, you are genuinely done.
4. **Report three numbers, not one:** target-script · genuinely-blank-in-source · real-translatable
   remaining. Final GoWR: `Hebrew 49,102 · empty 26 (legit — EN+AR blank at source) · real 0`.
5. **A same-id join across languages is NOT a same-line join.** For GoWR, `arabic[id]` and
   `english[id]` are frequently DIFFERENT lines (id 102049 EN=`Hvat er at gerast?!` vs AR="Great. It
   will make water flow…"). This invalidated BOTH the cue-hash English match AND the
   [[gender-oracle-from-game-langs]] id-join (19 of 20 "gender errors" were misalignments where the
   Hebrew was already CORRECT — flipping them would have INTRODUCED bugs). **Before trusting any
   cross-language oracle, sample ~10 pairs and confirm they are the same line.** If they aren't, the
   only reliable source is the language whose text actually sits at that id.


## 7c. 🔴 Verifying a DELEGATED agent's output — the failure modes that pass a naive gate
[[delegate-all-translation]] means an agent does every translation, so **verification is the whole
job**. Beyond the attestation anti-cheat (§13), these bit hard on GoWR and are universal:
- **An agent that writes its own bulk-fill script will silently change STRUCTURAL ENCODING.** GoWR
  stores two different break kinds — a real `0x0A` (cue separator) and a **literal `\n`** (2-char
  in-value break) — and the agent's `dump_batch.py` converted literal→real on 24 entries. Content
  and token checks all PASSED. **Verify a per-entry ENCODING SIGNATURE against the source**
  (`(count("\\n"), count("\n"))` must match the source exactly), not just the visible text. Fix
  deterministically by rebuilding each translation with the source's exact break SEQUENCE
  (`games/godofwar_ragnarok/agent_handoff_fullenglish/fix_newlines.py` is the reusable template).
- **A REDUCTION-based validator pressures the agent to damage legitimate content.** A rule like
  "the Latin word count must DECREASE" is unsatisfiable on a line whose only Latin IS a URL or a
  product title — so the agent shaved `www.` off `playstation.com` and transliterated
  `God of War Ragnarök` → `God of War ראגנארוק` purely to pass. **Whitelist URLs/brands/product
  titles, or exempt lines whose source Latin is already all-whitelisted** — and diff the agent's
  output against its input to catch degradations it made to satisfy you.
- **A `.strip()` in a merge script destroys meaningful edge whitespace.** GoWR id 137887 is a 30 KB
  data blob (one visible line + a 934-line `>vo_..._stem` list); the merge stripped its trailing
  newline. Any entry that is DATA rather than prose must round-trip byte-identical except the
  translated span — verify with a line-by-line diff, not a length check.
- **Every merge needs a per-id GUARD**: write only if the current spine value still equals the value
  that was scanned/handed off (never clobber concurrent work), plus a timestamped backup and an
  atomic `os.replace`. Report `updated/skipped` — a non-zero skip means something moved underneath.


## 8a. RTL / font gotchas (cohtml / Coherent GameFace engines, e.g. SM2)
- cohtml **ignores CSS `direction`/`dir`** — honors only Unicode **bidi control chars**. Base RTL
  comes from the UI container; use **`&rlm;` anchors matched to the Arabic** positions.
- **NEVER use RLE/PDF (U+202B/U+202C)** if the shipped font lacks those glyphs → tofu box. If the
  font renders U+200F/U+200E (RLM/LRM) as visible marks, **empty those glyphs** in the TTF. The
  game's native Arabic font keeps them zero-width — match that.


## 8b. STORE-VISUAL engines (no bidi at all) — the full rule set (RDR2/GTA/AC2/Anno/TLOU/GoT/007)
Learned the hard way over 7 in-game proofs on RDR2 (2026-07-19/20). Every item below is INVISIBLE
in a short-line menu proof and wrong across the whole corpus. Reference impl:
`games/rdr2/work/{rdr2_rtl,rdr2_metrics}.py`; memory [[store-visual-use-real-uba]].

0. **Validate the output against the game's OWN shipping RTL locale, not against theory.**
   `python-bidi` does NOT apply L4 bracket mirroring, which looks like a defect on paper. Checking
   the professional Arabic that ships for RDR2 (also VISUAL-stored) settles it: every parenthetical
   there has `(` at the visual LEFT and `)` at the visual RIGHT — e.g. `(ﺖﻳﻮﺼﺗ) ﺔﻫﺩﺮﻟﺍ ﻦﻣ ﺔﻠﻛﺭ` —
   **exactly the pattern python-bidi produces**. So do NOT pre-mirror brackets. One grep of the
   shipping locale beats an hour of reasoning about Unicode rules.
1. **Run the REAL Unicode Bidi Algorithm** (`python-bidi` `get_display(s, base_dir='R')`), never a
   hand-rolled run-reversal. The hand-rolled pattern keeps every non-Hebrew run FORWARD, treating a
   punctuation run like a Latin island — but a NEUTRAL run belongs to the RTL flow and must be
   reversed, with brackets mirrored (UBA rule L4). **A 1-char neutral run reverses to itself**, so a
   one-clause label (`…?`, `… — …`) looks perfect while every real sentence is wrong. Verify the new
   output is byte-identical to the old on strings already confirmed in-game before switching.
   ⚠️ Does NOT apply where the engine shapes/reorders RTL itself (VirtualDJ → force RLE…PDF instead).
2. **Protect engine tokens:** leading control tokens stay at the FRONT (RDR2's `~z~` — 162,997/162,997
   of the shipping Arabic mod's lines start with it); order-bearing separators (`~n~`, `~sl:a:b~`)
   split the string and are re-emitted in place so line order + subtitle timing stay bound to the
   right text; inline tokens become private-use placeholders = atomic LTR runs.
3. **STRIP each segment's edge whitespace** before converting. Under an RTL base a logical-TRAILING
   space moves to the visual START — into the left margin, where it renders as a stray indent.
4. **PRE-WRAP anything the engine would wrap.** The engine wraps in STORAGE order, so an un-broken
   VISUAL paragraph renders with its LINE ORDER INVERTED (read bottom-up). Explicit newline tokens
   take that decision away from it.
5. **Measure the box with a RULER string** — lines of exactly N chars stamped `[N]` at BOTH ends;
   the largest N whose two markers stay on one line is the usable width. One screenshot, per surface.
6. **Wrap and pad by real GLYPH ADVANCES, never character count.** A space advances ~60 units and a
   Hebrew letter ~129, so **one letter ≈ 2.2 spaces** — char-count padding lands a paragraph in the
   MIDDLE, not at the right margin. The advances are already in the font you inject into (Scaleform
   `DefineCompactedFont` → `glyphInfo advanceX`; TTF → `hmtx`).
7. **🔴🔴 DO NOT JUSTIFY — RIGHT-ALIGN. (This REVERSES the earlier advice; the earlier advice was
   wrong and shipped a visible defect.)** Flush-both-edges sounds right, but the only lever you
   have is inserting whole SPACE characters, and a space is **58 of the 13,500 units** in the
   measure. A greedy wrap already fills **93-99 %**, so the slack is 5-15 spaces over ~20 gaps and
   `divmod` gives **+1 space to 15 of the 18 gaps and 0 to the rest** — a line of irregular
   double-gaps, landing *inside Latin brand names* too (`Rockstar  Games,  Inc.`). Measured on the
   shipped RDR2 splashes: 15 / 11 / 10 / 9 multi-space runs per line. A `MAX_GAP` cap does not help
   (0.83 extra spaces per gap passes any sane cap) — the holes are a property of the mechanism.
   **Put ALL the slack in one leading pad instead**: the RIGHT edge (where a Hebrew reader starts)
   is perfectly flush, every gap is a single space, and only the left edge is ragged — which is how
   RTL prose is normally set. Use the BALANCED wrap on this path so the pads stay small. After the
   switch: **0 inner multi-space runs on all 16 lines, every line at 99.6-100 % of the measure.**
   The one legitimate big pad is a line whose content is a long unbreakable token (a URL).
8. **Balancing and justification are ALTERNATIVES, never a pipeline.** Balancing shrinks lines to
   equalize them; justification stretches them back to the full measure — chained, the shrink becomes
   huge word gaps. Justified ⇒ greedy wrap at the full measure. Ragged ⇒ balance, so no line carries
   a big pad (the pad count MULTIPLIES every metric error). And never justify a line broken before a
   long unbreakable token (a URL): cap it at ~2 extra spaces per gap, else leave it flush-right.
9. **Floor, never round; one source per metric.** Rounding up can push a line over the box → the
   engine wraps it → the inverted-order bug returns. And if injected spaces are COUNTED with one
   space-advance but MEASURED BACK with another, each adds a hidden delta (12 of 18 lines silently
   went over budget this way). **Always verify the BUILT file's line widths, not the builder's intent.**

10. **GUARD pure-non-Hebrew values, and know the multi-word-Latin limit** (learned on Menyoo, applies to
   EVERY run-based `visual()`). A run-reversal that reverses the ORDER of runs will also reverse a value
   that contains **no Hebrew at all**: `"YSC Script [DEV]"` → `"[DEV] Script YSC"`. **Fix: `if not
   HEBREW.search(s): return s`** as the first line of the function. Same root cause, no clean fix: a
   **multi-word Latin phrase embedded in Hebrew** has its word order reversed (`'Welcome to Los Santos'`
   → `'Santos Los to Welcome'`), because each Latin word is its own run. Grouping the Latin words back
   together fixes the order but then steals the Hebrew↔Latin boundary space, which is worse across the
   whole corpus — so **leave such strings untranslated (English renders correctly as LTR)** rather than
   ship a mangled title. A *single* embedded Latin token (`HUD`, `(SP)`, `EMP`) is always safe.
   ✅ **Engine format tokens survive run-reversal correctly** — GTA `~r~`/`~b~`/`~s~` color codes
   reposition consistently for an RTL reader (`~r~Error:~s~ You are not in a vehicle.` →
   `.בכרב ךניא :~s~האיגש~r~` reads right); no special handling needed.

**Meta-rule: a short-line menu proof does NOT clear a store-VISUAL engine.** Long-paragraph wrap,
mixed-script sentences, neutral/bracket placement, box width and alignment are separate gates, each
needing its own screenshot. Use the game's OWN always-visible screens (boot/legal splash, quit
dialog) as free test surfaces, put a **Latin marker** in every proof so "file didn't load" is
distinguishable from "font has no glyphs", and A/B two variants per screen to halve the round trips.


## 8c. GTA V / RAGE native text = SCALEFORM fonts (the font map, verified 2026-06-23)

Applies to GTA V game text AND to any ASI mod that draws with the natives (Menyoo, trainers, HUD mods).
Web-grounded + adversarially verified (Autodesk Scaleform docs, gtamods wiki, and GTA font-replacement
mods whose pages state they change the font "in mods such as **Menyoo**").

- **`SET_TEXT_FONT` + `BEGIN/END_TEXT_COMMAND_DISPLAY_TEXT` / `_DRAW_TEXT` pull glyphs from the
  Scaleform GFx font libraries**, not from a separate RAGE bitmap-font system. Editing the embedded
  fonts inside a `font_lib_*.gfx` changes native HUD/menu/trainer text game-wide.
- **Native font ID → gfx export → face:** `0` = **`$Font2`** (Chalet-LondonNineteenSixty, the normal UI
  font) · `1` = HouseScript / Sign Painter · `2` = Monospace · `4` = **`$Font2_cond`**
  (ChaletComprime-CologneSixty, the condensed face) · `7` = Pricedown. **All are separate exports in the
  SAME file** — injecting into one does nothing for the others.
- **File + override path:** `x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.gfx` (note the
  `_pc` suffix; EFIGS locales only — a CJK game language loads `font_lib_chinese/japanese/korean_pc.gfx`
  instead and the efigs edit is ignored). OpenIV mods-folder override goes to
  `mods/update/update.rpf/x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.gfx`.
  Face mapping lives in `common/data/ui/fontmap.xml` — **untouched if you only swap glyphs under the
  existing export names.** Vanilla `font_lib_efigs_pc.gfx` ≈ **97 KB** (useful size baseline).
- **Injection method:** JPEXS/**FFDec** opens `.gfx` directly (magic `GFX\x08` = uncompressed; `CFX` =
  compressed). Add the U+0590–05FF block from a Hebrew-capable donor into the EXISTING DefineFont —
  **never rename the export symbol** (Scaleform resolves fonts by name; renaming → fallback/tofu), and
  **re-open after saving to confirm the added range survived** (Flash/Scaleform export can truncate the
  glyph table and silently drop it). Hebrew needs no contextual shaping (unlike Arabic) so glyph
  injection is the only font work required.
- **🔴 bidi: Scaleform GFx has NO RTL support** (Autodesk's own docs list Hebrew/Arabic as unsupported).
  It draws codepoints in storage order → **store VISUAL** (§8b). Every GTA Arabic fan-translation does
  the same ("we just reversed the words"); the tell-tale symptom of pre-reversal is word-wrap grabbing
  the wrong word, so keep lines short.


## 8d. 🔴 ENGINE-HARDCODED GLYPH-ATLAS BREADTH — a THIRD failure class (found on Anno 1800, 2026-06-22)

Until now a script that didn't render meant one of two solvable things: **the font lacks the glyphs**
(inject them) or **the bidi mode is wrong** (store VISUAL/LOGICAL). Anno 1800 exposed a third,
**unsolvable-by-data** class that every future game must be screened for.

- **THE SIGNATURE (learn to recognise it in one test):** the translation renders **FULLY and correctly
  after a LIVE in-game language switch**, but is **partial + "????" at COLD BOOT**. Same files, same
  fonts, same strings — only the boot path differs. That gap means the engine has **two glyph paths**:
  a **static prebake at boot** (a fixed, limited glyph set) and a **dynamic rasterizer** used on a
  language re-init (reads any codepoint from the active font's cmap). Your injected script is in the
  font, so the dynamic path shows it; the static prebake never included it.
- **THE ROOT CAUSE (Anno): the prebake breadth follows the LANGUAGE CLASS, decided in engine code.**
  A CJK language (Korean/Japanese/Chinese) forces the BROAD/dynamic atlas → the injected Hebrew
  preloads at boot. An LTR language (English/German/…) gets the NARROW static atlas → Hebrew omitted.
  **Not the font**: proven by re-pointing Korean→the Latin Meta font (a "narrow" font) — Korean STILL
  booted broad. Breadth follows the LANGUAGE, not the bound font.
- **THE SEARCH THAT PROVED "no data lever" (do this before concluding, and then STOP):** three
  independent deep scans over 373,000 archive entries found **no charset list, no Unicode-range table,
  no per-language "broad" flag, no glyph-preload config anywhere**. Specifically: the per-language
  binding records were **byte-identical CJK-vs-LTR except the name string and the font GUID**; the only
  Latin/CJK discriminator was a **per-FONT** descriptor flag (and flipping it 0→1 broke boot AND is
  logically refuted by the Korean→Meta result); the language config carried only audio/locale fields.
  ⇒ **When a per-language diff shows ONLY name+asset-pointer differing, there is no per-language
  attribute to flip — stop looking in data and go check the exe.**
- **⛔ THE EXE ESCAPE HATCH IS USUALLY CLOSED — screen for a PACKED binary FIRST (3 cheap checks):**
  (1) entry point in an odd section (`.xtls`), (2) a huge **writable+executable** section (Anno: 320 MB
  `.text1`, flags `0xE0000020`), (3) a `.reloc` far too small for the image (Anno: ~12 KB for 411 MB).
  All three ⇒ VMProtect/Denuvo-class packing: the decision code is **not in the on-disk bytes** (it is
  reconstructed at runtime), so a **static byte patch is dead** — do not plan one. Run these checks
  *before* spending a session designing a patch.
- **✅ THE ONLY SAFE LEVER: a SAME-SIZE binding swap to an ALREADY-VALID asset.** Don't edit the asset,
  and don't flip descriptor flags — **re-point a pointer/GUID** at an existing asset the engine already
  loads elsewhere. Anno: swap the CJK language's font GUID → the Latin font's GUID (keeps the broad
  cold-boot atlas that follows the *language*, while fixing the wide CJK Latin/digit metrics).
  **Prove the engine supports the combination by finding a SHIPPED config that already does it** (Anno's
  own "reduced" language sets already bound CJK→Latin) — that turns a risky edit into a documented one.
- **⚠️ ONLY APPENDING TO A FONT IS SAFE (static-atlas engines).** Adding new codepoints (cmap+glyf+OS/2)
  is tolerated. **Mutating anything that already exists** — an ASCII outline, an advance, the U+0020
  space metric, or the font descriptor's flags — makes the static prebake **reject the font → total
  "????" for everything at cold boot** (confirmed 3× on Anno). A live switch still "fixes" it via the
  dynamic path, which makes this bug look intermittent — always test COLD BOOT.
- **🔁 THE SAME RULE REAPPEARED ON A DIFFERENT ENGINE ⇒ treat it as a general law for ANY prebaked
  atlas (2026-07-20).** AC Shadows (Anvil v42) renders the UI from a baked SDF atlas (`PHXFD`), not from
  the TTF. Repurposing a glyph record while rewriting its **metrics** (advance / bbox / W / H) made the
  engine keep drawing the slot's **ORIGINAL** shape; an edit touching **only the raster pixels + the
  codepoint** reached the screen (proven by a flip probe rendering those glyphs upside-down). Same
  mechanism as Anno's rejection: the engine builds its GPU atlas from a second copy of the glyph box and
  falls back to the vanilla upload when the record disagrees. ⇒ **Rasterize the new letter INTO the
  existing slot's exact W×H canvas and leave every geometry field vanilla.** The glyph then inherits the
  donor slot's advance/bearings, so spacing and size come out uneven — accept that, get *something* on
  screen, and tune metrics afterwards one variable at a time. **Getting a shape to RENDER and getting it
  to SIT correctly are two separate gates; do not conflate them.**
- **⚠️ Live/CEF web panels can't be translated or decoupled.** An in-game browser / news ticker
  (mod.io, Twitch, store) fetches **server-side localized content keyed on the game's locale**. Hijack a
  CJK locale and those panels show CJK — not in any `texts_*.xml`, not fixable by a mod, and NOT fixed by
  setting the launcher/Ubisoft-Connect account language (verified). **Say this to the user up front** —
  it is the main hidden cost of a locale hijack.
- **THE PRACTICAL CONSEQUENCE — screen for this in Phase 1.** After the menu proof passes, **also test a
  COLD BOOT** (not just a live switch). If cold-boot differs, you are in this class, and the achievable
  end-states are usually only: **(A) run on the broad-class locale** = perfect from boot, no user action,
  but that locale's label + web content; or **(B) run on the desired locale** = right label/web content,
  but the user must fire ONE language re-init per launch. There is often **no third option** — ship the
  mod supporting BOTH (fill every locale slot + document both paths in the readme) and let the user pick.


## 8e. BASE + PATCH archive stacks — patch EVERY copy, verify the one the engine WINS with
Learned on AC Shadows (`DataPC_boot` + `_patch_01` + `_patch_02`), applies to any engine that layers
archives (Anvil forges, UE `pakchunk*_P`, RPF `mods/update*`, Frostbite patch TOCs, PSARC mount order).

- **The same string/asset commonly exists in SEVERAL packages**, and the engine resolves ONE by load
  order. Patching only the copy you happened to find leaves the winner vanilla — and everything
  *looks* fine on your side. On AC Shadows 11 main-menu lineIDs sat in three separate packages
  (10 / 11 / 11) and the visible menu was served by the one that had never been touched.
- **🔴 A verifier that only inspects what you patched can never tell you that you patched the wrong
  thing.** `verify(patched_only=True)` reported a perfect 11/11 while the screen stayed Arabic,
  because it filtered to packages that already had a backup sidecar. **Verify by scanning ALL
  archives for the key and asserting the WINNING copy is translated** — never by re-reading your own
  output.
- Corollary for restricting scope: an env override like `ACS_FORGES` that narrows the target set is
  a footgun — if you narrow it for one run, re-verify globally afterwards.
- The same shape shows up in the version-sync rule (§10) and in the launcher's catalog lookups: any
  time a value can exist in more than one source, decide which source WINS and check that one.


## 8f. ENGINE-FAMILY REUSE + index-redirect deploys (Insomniac TOC2/DAT1: SM2 · R&C Rift Apart, 2026-07-12)

Learned bringing up Ratchet & Clank: Rift Apart in ONE session because it shares Spider-Man 2's engine.
Every item below is **universal to any "same studio / same engine" second title**, and the payload-encoding
rule is universal to **any index-redirect (TOC/manifest) deploy**.

### The reuse play — check the CONTAINER MAGIC before anything else
When a new target smells like an engine already cracked in this repo, the FIRST probe is the archive/index
**magic + version**, not the text. R&C's `toc` opened with `0x34E89035` + `1TAD` = the exact TOC2/I29 branch
SM2 uses (dat1lib reports `version 202300 == VERSION_RCRA`), and that single read collapsed the whole
container/text/repack/applier workstream into "reuse". Cheap probe, enormous payoff — **always run it before
scoping a new game**. Then diff only what actually differs (here: no Arabic slot, and a TTF font instead of
SM2's DDS atlas). ⚠️ The corollary: **do NOT assume the rest matches just because the magic does** — R&C's
variant→language ordering differs from SM2's (SM2's Arabic `variant_18` is a Latin language in R&C).

### 🔑 `header_offset` decides how you encode the payload blob (THE deploy rule)
In an index-redirect deploy you rewrite a size/extent entry to point at your own file. What you put IN that
file is decided by whether the asset has a **separate header**:
- **`header_offset != -1`** → the engine stores a small header apart from the body and **re-prepends it** at
  load. Your blob must be the body with that header **STRIPPED**, and the entry's `value` = body length
  (= filesize − header). R&C loc: 36-byte header, `value == filesize − 36`.
- **`header_offset == -1`** → the asset is raw/whole (R&C's fonts are bare sfnt TTFs, `value == filesize`).
  Your blob is the **entire file**, nothing stripped.
Get this backwards and the engine reads a body that disagrees with its header → blank text or a crash.
**Read `header_offset` per asset and branch on it — never apply one rule to every asset in a payload.**
(Related: the stale header still carries the ORIGINAL body size. That is fine — the engine reads the length
from the size-entry `value` and the container's own internal size field, both of which you update. SM2 ships
this exact mismatch proven in-game.)

### Addressing: (span, asset_id), and a multi-variant asset is selected by SPAN
R&C's 32 language variants all share ONE `asset_id` (`0xBE55D94F171BF8DE` = crc64 of the asset path); the
**span** picks the language (variant *N* → span *N*×8). A `.stage` entry is literally `{span}/{UPPER_HEX_ID}`,
and the applier resolves it by walking that span's `[asset_index, +count)` slice of the id table. So
**"which language you overwrite" is a span number, not a different file** — and covering several regional
slots (en-US + en-GB) costs zero code, just more stage entries.

### ⚠️ Classify a language by the VALUES section ONLY — a whole-file script sniff LIES
Sniffing entire localization files for Unicode-script ratios reported ~3,400 "Arabic" + ~1,300 "Hebrew"
codepoints in **every one** of the 32 variants — pure noise from shared metadata/charset sections that are
byte-identical across languages. Parsing the container and classifying **only the per-language VALUES
section** gave the truth: 24 real languages and **zero** Arabic/Hebrew. Same trap at the archive level: raw
whole-archive codepoint scans yield ~0.5M spurious "Arabic units" out of compressed bytes. **Only decompressed,
per-language string data is authoritative** — and "is there an Arabic slot?" is exactly the question you must
not get wrong, because it decides Arabic-hijack vs LTR-hijack for the whole project.
Corollary: a **language ENUM can outlive its text** — R&C reserves Arabic audio slots (`wem.ar`/`soundbank.ar`)
and an ADR dub enum while shipping no Arabic text at all. A locale *name* in the framework proves nothing.

### 🔑 OFFLINE-VALIDATE the deploy on a temp copy of the INDEX before touching the game
Before the first real write, copy just the index file (`toc`) into a temp directory shaped like a game root and
run the **real applier** against it, then re-read the mutated index and assert every asset was redirected to a
file whose on-disk size equals the entry's `value`. This exercises the whole mutate→serialize→re-parse path —
the part that silently corrupts a game — with zero risk, in seconds. It caught nothing this time precisely
because the encoding rules above were followed; it is still the cheapest insurance in the pipeline and belongs
in every index-redirect deploy. (`games/ratchet_rift_apart/work/24_validate_deploy_offline.py` is the template.)

### 🔑 ONE menu-proof build can decide bidi — don't spend two deploy round-trips
The Playbook's earlier advice ("build BOTH a LOGICAL and a VISUAL payload and deploy each") costs two
launch/screenshot cycles. Better: patch **different keys on the SAME screen with different modes** —
LOGICAL / LOGICAL+RLM / VISUAL — plus a pure-Latin marker and mixed digit/Latin-island diagnostics. One
screenshot then answers everything at once: the marker proves the redirect MOUNTED (independent of font and
bidi), whichever mode reads correctly IS the mode, absent tofu proves glyph coverage, and no stray marks
proves the bidi-control glyphs are handled. Pick a screen that shows many labels together and is reachable
from anywhere — **a PAUSE menu beats a main menu** (no new game required, denser label set).

### Font: when injecting, MAP the bidi controls to an empty glyph (not just "empty the existing one")
SM2's lesson was "empty Heebo's visible U+200F/U+200E glyphs so `&rlm;` anchors don't render as marks". The
completion: if the target font has **no** cmap entry for U+200F at all (Latin fonts don't), an RLM anchor
falls to `.notdef` = a **tofu box**. So always **add a zero-width, zero-contour glyph and map the whole bidi
control set to it** (U+200F/200E/202A–202E). Both failure modes — visible mark and tofu — are then closed.
`anno_font._add_hebrew` is the reusable merge for any game whose fonts are loose/clean TTFs (vs the DDS-atlas
path); it also strips `vmtx/vhea/VORG` and sets the OS/2 Hebrew bits, both of which are load-bearing.


## 8g. FORCE-RTL-BASE engines — when pure RTL is fine but MIXED RTL+Latin breaks (VirtualDJ, 2026-07-12)

A third bidi class, distinct from §8a (logical+`&rlm;`) and §8b (store VISUAL). **Signature: pure
Hebrew renders perfectly, the game's own Arabic renders perfectly even with English brands embedded,
but YOUR mixed Hebrew+Latin lines come out mis-ordered.** That combination is diagnostic: the engine
*has* a working bidi implementation — it simply detects the **paragraph base direction** from the
script it knows (Arabic), and defaults a Hebrew-only line to the app's LTR base.

- **THE FIX: wrap every LINE in `RLE (U+202B)` … `PDF (U+202C)`.** This forces RTL base direction
  explicitly, so the engine bidis Hebrew exactly as it already does Arabic. Apply per line (split on
  `\n`, skip empty lines), at BUILD time — the stored translation stays clean logical Hebrew.
- **It is safe everywhere:** in a widget that already resolves RTL correctly the embedding is a no-op;
  in a widget that defaults LTR it supplies the missing base direction.
- **What does NOT work, and why (all tested in-game):**
  - `RLM (U+200F)` prefix — **silently ignored** by many engines; it is only a weak/neutral-resolving
    mark, not an embedding. Do not settle for it.
  - `python-bidi get_display` / any letter-level visual reversal — produces **mirrored Hebrew letters**,
    because this class of engine already shapes each RTL run correctly *within the word*. Pre-reversing
    double-applies. (This is the opposite of §8b engines — do not confuse the two.)
  - Reversing the order of runs/tokens yourself — breaks adjacent Latin+number groups (`VirtualDJ 2026`
    → `2026 VirtualDJ`) and is unnecessary once the base direction is right.
- **The order to test, cheapest first:** RLE/PDF wrap → RLM prefix → run-reorder → full visual. Stop at
  the first that renders correctly; do not "improve" it further.


## 8h. The A/B/C in-game isolation + the TRANSCRIPTION control string

How to settle any rendering question that screenshots alone can't (bidi mode, encoding, alignment):

- **Put several candidate encodings of the SAME sentence into ONE visible string, labeled `A:` / `B:` /
  `C:`.** One launch eliminates two hypotheses instead of one. Prefer a surface the user can re-trigger
  on demand and that holds multiple lines (a confirm dialog beats a splash).
- **🔑 When judgement answers keep conflicting, switch from "which is correct?" to "TRANSCRIBE exactly
  what you see, left to right" using KNOWN control strings** (e.g. store `שלום ABC 123` on one line and
  `123 ABC שלום` on the other). A transcription is *data* about the engine; a correctness judgement is
  an opinion filtered through unreliable OCR and through the reader's own RTL scanning habits — and for
  mixed-direction text those two genuinely diverge. This single move ended five failed guessing rounds.
- **Corollary:** a correct-RTL rendering *looks* wrong to many readers (sentence-final punctuation and
  trailing Latin sit on the visual LEFT). Before "fixing" it, confirm with a control string that the
  engine is actually misbehaving — otherwise you will break correct output chasing a perception.


## 9. Per-game add checklist
0. **Establish the REAL scope before translating.** If the target uses a lookup-based loc system
   (key → translated string), ship a PARTIAL language file, run it once, and **harvest the log for
   its "missing translation" lines** — that is the engine's own authoritative key universe (Menyoo,
   §Menyoo above). Then split UI labels from proper nouns that must stay Latin (vehicle/ped/weapon/
   mission names); a translated proper noun is a defect, and an untranslated UI label is a gap.
1. `games/<game>/work/` — copy the SM2 translate/watchdog/progress trio; adapt extract + build.
2. Supabase `games` row + `mod_version_history`; Cloudflare Worker slug; GitHub release repo.
3. Launcher (optional): card in the frontend + a `<game>_mod.py` lifecycle + RPCs.
4. **Version sync across the 4 surfaces that must agree:** Supabase `games`, `mod_version_history`,
   the GitHub release `manifest.json`, and the GitHub release zip (sha256 must match).


## 10. Publish + version sync (don't break `releases/latest`)
Keep ONE stable tag as `releases/latest` and **clobber its assets** each build — do NOT mint
`v…-beta.N` tags that semver-sort BELOW the stable tag (GitHub would keep the stable as latest and
the Worker would serve stale). Sync the website with `universal/publish_version.py <game> <ver>
--stage <s> --sha … --size … --archive-url … --apply`; edit the release `manifest.json` `version`
for the Worker. CP2077 reference: `pack_cp2077_mod.py <ver> --pack-only` →
`gh release upload <stable-tag> --clobber manifest.json <zip>` → `publish_version.py … --apply`.

**🔴🔴 FIRST, ASK GITHUB WHICH RELEASE IS ACTUALLY `latest` — never assume it's the tag the notes
name (cost a whole "published but nothing changed" round on WD2, 2026-06-27).** `releases/latest`
= the **highest-semver NON-prerelease, non-draft** release, NOT the oldest/canonical one. If a
`v…-beta.2` tag was ever minted (i.e. the rule above was broken at some point), it silently becomes
`latest` and **a clobber of `v…-beta.1` updates a release nobody reads.** The Worker
(`steam_mod_worker/src/index.js`) resolves `api.github.com/repos/<repo>/releases/latest` → its
`manifest.json` asset → so it kept serving the OLD version while `gh release view <old-tag>` proudly
showed the NEW asset. **Before every publish:**
`gh api repos/<repo>/releases --jq '.[]|{tag:.tag_name,prerelease,draft}'` +
`gh api repos/<repo>/releases/latest --jq .tag_name` → clobber **THAT** tag (clobber the others too,
for safety, so every release carries identical bytes).
**And VERIFY THROUGH THE CONSUMER, not the uploader** — `gh release view` reads the tag you name and
will happily confirm your upload while the live path is stale. The only proofs that count:
`curl <worker>/<slug>/manifest` shows the new version+sha, `curl -I <worker>/<slug>/archive` = 200
with the right Content-Length, and the site's `games.download_url` HEADs 200 at the new size.
⚠️ `npx wrangler deploy` does NOT fix a stale Worker manifest — the Worker reads GitHub live, so
staleness means you clobbered the wrong release (or GitHub really is stale), never a stale Worker
script. Don't redeploy to "bust a cache" before checking which release is `latest`.

**🏷 The canonical GitHub account is the ORG `hebrew-translation-hub`** — every mod repo and the
launcher were transferred there from the personal user `nehorayc04`. **BOTH names resolve**: GitHub
permanently redirects the old owner path, so `nehorayc04/<repo>` and `hebrew-translation-hub/<repo>`
fetch the SAME release asset (identical asset id). The API's `full_name` is the canonical answer —
`GET /repos/nehorayc04/x` returns `full_name: hebrew-translation-hub/x`. Live `games.download_url`
rows still carry the old owner and work fine. **Do NOT revert the org name in the source, and do NOT
"fix" the old URLs in the DB.**

**🔴 TWO FALSE-ALARM TRAPS when checking whether the mods are live (both hit on 2026-07-19, and
together they produced a confident, completely wrong "every published mod is about to go offline"):**
1. **An UNAUTHENTICATED GitHub API call can 404 a repo/account that exists.** Verify with a token
   (`GH_TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n
   's/^password=//p')`) and read `full_name` — and fetch the real asset URL with a
   `Range: bytes=0-0` GET before declaring anything broken.
2. **Cloudflare 403s the default `Python-urllib` User-Agent**, so a Worker health check from plain
   `urllib` returns **403 for EVERY slug** and looks exactly like a total outage. Send a browser UA
   (the same gotcha as the Supabase Management API above). With a real UA all 10 slugs answered 200.

**The 60-second health check — run it after any publish, and BEFORE raising any alarm:**
```
GET <worker>/<slug>/manifest   (browser UA)        -> 200 + expected version, for EVERY slug
GET <games.download_url>       (Range: bytes=0-0)  -> 206
GET https://hebrew-translation-hub.com/api/games   -> row present, right price/flags
```
**UNIVERSAL: never call an outage off a single negative probe — a 404/403 from one client is far
more often the client's auth or User-Agent than a real failure. Confirm through the path the USER
actually uses, and with credentials, before touching anything.**


## 10b. Gender source BEFORE translation — never accumulate gender debt (universal)

English drops gender/number, so a Hebrew translation made from English **guesses** it and defaults to
masculine — that is a debt you pay for later at 10× (CP2077 needed ~2,900 corrective fixes). The fix
is structural: **prepare the gender source BEFORE Phase 2 and attach it per line.** The game's OWN
gendered localization already made every decision (Arabic ≈ Hebrew: أنتَ/أنتِ/أنتم = אתה/את/אתם).
Rollout table + the 3 scenarios: `universal/GENDER_ORACLE_ROLLOUT.md`; oracle:
`universal/gender_oracle.py`; reference impl: `games/hogwarts_legacy/work/{build_gender_source,
enrich_pool_gender,gender_qa}.py` (Arabic) and `games/tlou1|tlou2` (no Arabic → Russian/Spanish).

**The per-game pattern (3 files, ~1 h of work, cheap insurance):**
1. `build_gender_source.py` → `extract/gender_source.json` = `{string_key: {"ar"/"ru": <parallel
   value>, "hint": "נמען=נקבה|רבים|זכר"|""}}`. **Every line carries the RAW parallel text** (that is
   the real source a translator reads); the `hint` is only where the strict oracle is unambiguous.
2. Attach it to whatever consumes the corpus — the agent handoff (`get_batch` joins per line) AND/OR
   the live `/translate` pool (`enrich_pool_gender.py` appends `· נמען=נקבה` to `context`, a
   **targeted PATCH of `context` alone** so `current_he`/`status`/`claimed_by` are never touched;
   re-runnable — it reconciles against LIVE state, stripping stale hints and adding new).
3. `gender_qa.py` at the END of Phase 2 → `gender_suspects.jsonl`, ranked fem-source-but-masc-Hebrew
   first (that ordering IS the systematic default-to-masc debt). Run it on the **LOGICAL** Hebrew,
   before any visual bake. Reports only; fix by re-inflecting the gender morpheme
   (`universal/dualgender_inflect.py`), never by re-translating.

**🔴 THE RULE THAT DECIDES WHETHER THIS HELPS OR HURTS: an auto-applied hint must be
MAX-PRECISION, because a WRONG hint creates exactly the debt it exists to prevent.** Two different
oracles, two different jobs — do not mix them up:
- **`ar_addressee`** (broader recall) — for a *review-then-verify* scan a human/model will check.
- **`ar_addressee_strict`** (added 2026-07-04) — for anything **written back** (a hint in a handoff
  or pool, an automated flag). Pronouns أنتِ/أنتَ + **vocalized** ـكِ/ـكَ + plural + a **curated
  2nd-fem verb whitelist**. It deliberately DROPS the generic `ت…ين` regex.

**Why the generic `ت…ين` heuristic must go (all four found on real Hogwarts data, all silent):**
masdar/verbal nouns (`تحسين`=improvement, `تعيين`, `تزيين`) — rampant in UI text; broken/sound
plurals (`تنانين`=dragons, `تمارين`); **verb + object suffix** (`تسامحني` = forgive **ME**, not
"you-fem forgive"); and a proper NAME (`ترينيتي` matched a whitelist entry `ترين` without both-side
`\b`). Hardening that benefits every Arabic game: `ت[..]{3,}ين` (a form-II masdar is ت+2+ين), drop
the `ي` branch of the particle rule, and require **no Arabic letter after** ك+haraka —
**`\b` after a combining diacritic is unreliable** and fired inside `الكَلب`/`ذكَر` → false masculine.

**UNIVERSAL, beyond Arabic:** a morphological hint is only safe when it comes from a **closed set**
(pronouns, a curated verb list). An **open-class ending** — a Romance article, a Polish `-ł`, an
Arabic `…ين` — matches ordinary nouns and manufactures confident garbage. When you cannot close the
set, **attach the reference SENTENCE and derive nothing** ([[gender-hint-needs-closed-set]]).
Corollary: build the oracle against the game's own data and *look at what it flags* before trusting
it — every FP above passed a plausible-looking regex and only surfaced on real strings.

### 10c. First-publish mechanics — 4 gotchas that each cost a round (Anno 1800, 2026-06-22)

Everything above assumes the release repo already exists. A game's **FIRST** publish has its own traps:

- **🔴 `gh release create` fails `HTTP 422 Repository is empty` on a brand-new repo.** GitHub refuses a
  release when the repo has **no commit / no default branch**. `gh repo create` alone does NOT seed one.
  Fix: push one file first via the API —
  `gh api repos/<owner>/<repo>/contents/README.md -X PUT -f message=init -f content=$(… | base64 -w0)`
  → creates the initial commit on `main`, then the release works.
- **🔴 A re-zip changes the SHA even when NO input file changed.** `zipfile.writestr(name, data)` with a
  plain string name stamps the entry with **`time.localtime()`**, so every packer run produces different
  bytes. Consequence: **manifest.json and the zip are only paired WITHIN a single run** — never publish a
  manifest from run A with a zip from run B. Our packers compute the sha immediately after writing and
  upload both together, so this is safe *as long as you don't re-run the pack between the two uploads*.
  Always verify after publishing by **downloading the live asset and re-hashing it** against the live
  manifest (`curl -sL <zip> | sha256sum` vs `curl -sL <manifest>`), not against your local file.
- **🔴 `publish_version.py` does NOT set `games.status` or `games.download_url`.** It writes only
  `version` / `release_stage` / `changelog` + the `mod_version_history` row. A first publish therefore
  leaves the row at `status='locked'` with `download_url=NULL` → **the site shows the game but no working
  download**. Always follow with a direct update:
  `update games set status='beta', download_url='<release zip url>', show_on_website=true where id='<id>'`.
  (Same for `price_cents` per [[mod-price-53-default]] when the mod is paid.)
- **⚠️ Don't put Windows paths inside a JSON heredoc.** `Documents\Anno 1800\mods` inside a
  `cat > x.json <<'JSON'` block makes `json.loads` die with `Invalid \escape`. Write the instruction
  without backslashes (or build the JSON in Python) — this bit the `claude_suggest.py` news push.
- **The 4-surface consistency check for a first publish** (run it, don't assume): live release
  `manifest.json` sha == live zip sha == `mod_version_history.sha256` == the size in both places, and
  `games.version` == `manifest.version`, and the `download_url` returns HTTP 200.

### 10d. When the user's literal request is physically impossible

A recurring, expensive pattern (Anno's "English + full Hebrew + no switch"): the user restates an
impossible requirement, and each new investigation re-derives the same wall. The discipline that ends it:

1. **Exhaust and RECORD.** List every avenue tried with its disproof (data / font / descriptor / config /
   debug-server / exe), so the next round can't silently re-tread. Put it in CLAUDE.md + memory.
2. **Get independent convergence before declaring impossible.** Run parallel agents with *non-overlapping*
   mandates; only declare when they converge — and **cross-check every proposal against the agent's OWN
   findings and the project's empirical history.** (Here one agent refuted the font-flag model with the
   strongest evidence in Q1, then *recommended flipping that exact flag* in Q2 — a proposal that was also
   already tried in-game and had broken boot. An agent contradicting itself is normal; catching it is the job.)
3. **Say it plainly, once, with the evidence** — then present only the **physically-possible end states**
   as a binary choice. Do not re-litigate and do not silently ship a default the user didn't pick: this is
   a genuine values tradeoff (which cost to bear), and it is the user's call.
4. **Ship the artifact supporting BOTH** end states where possible (Anno fills every locale slot and the
   readme documents both paths) so the release is never wrong for a downloader who chooses differently.

### 10e. ⚖️ Can this mod be SOLD? — the check to run BEFORE pricing a target (2026-07-12)

[[mod-price-53-default]] says every launcher mod ships at ₪53, but that default assumes a **game** mod.
Run this check per target, because the answer flipped for VirtualDJ:

1. **Is the artifact a DERIVATIVE of the vendor's own file?** If the build starts from the shipped
   language/asset file and keeps untranslated values (VirtualDJ's `Arabic.xml`, Qt `.qm`, a patched
   cache entry), it is a derivative work — far weaker ground than a from-scratch corpus.
2. **Is it live commercial SOFTWARE rather than a game?** An actively-sold product with a subscription
   business and an EULA that forbids commercial use/derivative distribution is the highest-risk case.
   Games with long-tolerated modding scenes are the lowest.
3. **Does the mod trade on the trademark?** Selling something named around the vendor's brand adds a
   trademark exposure on top of the copyright/EULA one.
4. **What exactly is being paid for?** The project's defensible model is "the translation is FREE to
   download; payment buys launcher **convenience** (auto-install/update)". Selling the *content* itself
   is a different, weaker claim.

**Outcome for VirtualDJ: FREE distribution only** (derivative of Atomix's own file + commercial
software + EULA + trademark) — a deliberate exception to the ₪53 default, recorded in its section
above. When the answer is "don't sell", say it plainly, offer the voluntary-donation middle ground,
and note that only written permission from the vendor makes paid distribution safe. Not legal advice —
but flag it BEFORE building a purchase flow, not after.


## 11. Multi-agent frontier-model LQA review (the highest-quality QA pass)
The deterministic scanners (§7) catch STRUCTURAL defects; they do NOT catch *semantic* ones —
mistranslations, broken half-transliterations, foreign-word leaks, unnatural Hebrew, wrong register.
For that you need a **frontier model** as the judge. **Measured fact:** the local qwen-32B audit was
low quality (precision ~32%, recall ~23%) and Haiku/Gemini-Flash over-flag — the quality floor for
nuanced Hebrew LQA is **Opus/Sonnet**. The proven method (built for CP2077, fully game-agnostic):

**Shape — a Workflow that fans out review + an INDEPENDENT adversarial verify (needs Ultracode/Workflow
opt-in; ~3.5M tokens per 600-line cycle):**
1. **Extract** a batch of `{pk, en, he}` rows (the English source + the live Hebrew) for unreviewed,
   *comparable* lines (skip structurally-broken + EN with <3 real words — those are other tools' job).
2. **Chunk** to ~30/file on disk (absolute path — agents Read it; MSYS only rewrites `/tmp` in argv).
3. **Review phase** — one Opus agent per chunk flags ONLY genuinely-wrong lines, returns
   `{pk, sec, new, reason}` (NOT `old`). Give it a SHORT strict GUIDE + the per-game glossary +
   an explicit "do NOT flag" list (brand/acronym/proper-noun passthroughs, protagonist-name policy).
4. **Verify phase** (pipeline, per chunk) — a SECOND, independent Opus agent re-checks each proposed
   fix and KEEPs only high-confidence real fixes (default REJECT) → kills over-correction, the #1
   failure mode. It WRITES the kept fixes to a per-chunk file.
5. **Apply** — reconstruct `old` BYTE-EXACT from the batch (never echo it through the LLM → control
   bytes/whitespace survive); apply only when `old == current spine value`; reject any `new` that
   fails the structural parser; QA-lock + per-file backup + atomic write; mirror to sibling sections.
6. **Bake + deploy** every ~1-2 cycles.

**Why each piece:** review-then-independent-verify ≫ single pass (a model won't refute its own proposal).
Returning `new`-only + reconstructing `old` from disk = the apply guard is reliable despite LLM string
drift. **SHORT-SAVE = commit ONLY completed chunks** (a chunk gets a fixes-file only if its verify
finished) so a mid-run interruption (session limit) loses 0 lines and re-reviews the rest. A failed
REVIEW must write NO fixes-file (else the chunk is falsely marked reviewed). **Session-limit handling:**
the workflow returns `keptTotal 0` + per-agent "session limit" failures → just retry; it succeeds once
the limit actually resets (an immediate retry that fast-fails in ~20s = still active → retry every
~10-15 min; do NOT precompute the reset time). Keep a checkpoint of reviewed keys so nothing is re-done.

**CP2077 reference implementation (copy as the template for a new game):**
`games/cyberpunk2077/qa_review_{extract,chunk,finish,commit_completed,apply}.py` +
`c:\tmp\opus_qa_workflow.js` (the review+verify GUIDE/glossary/schemas) + state in
`universal/opus_qa_{checkpoint,fixes.applied}.json[l]`. For a new game: swap the EN source + the spine
read/write + the per-game glossary in the GUIDE; the workflow shape and the apply guards are unchanged.
Review the highest-visibility text first (UI/menus/item text), then dialogue/subtitles.


## 12. 🔬 AUTONOMOUS in-game verification + differential rendering (built on GoT 2026-07-08, REUSE EVERYWHERE)
Until now every in-game gate (menu proof, bidi mode, font coverage) needed the USER to launch the game and send a
screenshot. That round-trip is now removable: **the assistant can launch, capture, read and iterate by itself.**
Reference implementation: `games/ghost_of_tsushima/work/{got_cap,memdump,live_trace}.py` — port per game by
changing the exe name. This is the single most transferable win of that session.

**(a) Launch a game whose exe demands admin, with NO UAC prompt.** Many cracked/AAA exes ship
`requestedExecutionLevel=requireAdministrator`, so `subprocess.Popen` dies with **WinError 740**. We are
non-elevated, cannot register a `/RL HIGHEST` scheduled task (Access denied from a filtered token), and cannot
accept UAC unattended. **Fix: launch with env `__COMPAT_LAYER=RUNASINVOKER`** — the AppCompat shim forces
asInvoker and IGNORES the manifest, no UAC, no elevation. Works whenever the game does not truly need admin
(i.e. it is not installed under Program Files). Proven on GoT; try it before ever asking the user to launch.

**(b) Capture a DX12 game: GDI returns BLACK — use DXGI Desktop Duplication.** `PIL.ImageGrab`/`mss` are GDI
BitBlt and return a black frame for a **flip-model** swapchain (modern DX12), even in windowed mode. **Fix:
`pip install dxcam`** and grab the window rect via Desktop Duplication. Keep the GDI path as a fallback (it still
works for GDI/launcher windows). Symptom to recognise: a black centre with thin coloured slivers at the edges.

**(c) Skip the publisher launcher.** A Nixxes/Ubisoft-style launcher window blocks the boot and **does not accept
synthetic clicks** (SetForegroundWindow fails under Windows focus-lock). Turn it off in the registry instead — for
GoT `HKCU\Software\Sucker Punch Productions\Ghost of Tsushima DIRECTOR'S CUT\ShowLauncher = 0`. ⚠️ **`reg.exe`
from Git-Bash silently FAILS** on keys containing an apostrophe ("DIRECTOR'S CUT") and mangles backslashes —
**use PowerShell `Set-ItemProperty`** and always read the value back to confirm (a silent no-op cost a whole boot).

**(d) Read the running exe's UNPACKED code without admin.** `OpenProcess(PROCESS_VM_READ|QUERY)` +
`VirtualQueryEx`/`ReadProcessMemory` works same-user/same-integrity — no SeDebugPrivilege. This **defeats
VMProtect-style section packing** (the code is decrypted in RAM). ⚠️ Dump **non-exec pages too**: strings and all
loaded/relocated data live in `PAGE_READONLY/READWRITE`, so an exec-only dump finds no `KCAP`/format strings and
wastes the trip. To find a loaded asset, search memory for a **byte signature taken from the file**.

**(e) DIFFERENTIAL RENDERING — the method that beats static analysis.** When you cannot decode a format, do not
keep guessing: **change one candidate region, redeploy, screenshot, and see what moves.** On GoT this settled in
two boots what 1.6M agent-tokens of static analysis got WRONG — overwriting the suspected "outline store" changed
NOTHING on screen (⇒ not the outline), while zeroing another region CRASHED the game (⇒ that one IS used). Rules:
edit **same-size** (so the container needs no re-layout), change **one** region per boot (else you cannot
attribute), keep a pristine `.he_backup` and revert between runs, and prefer a region whose glyph/string you can
SEE. A null result is as informative as a positive one — record both.

**(e3) A SIBLING TITLE ON THE SAME CLASS HASH ALREADY HAS YOUR SPEC — go read it before you
re-derive it.** Anvil's font atlas is class **`0xCBD4939A`** in BOTH AC Black Flag Resynced (v50)
and AC Shadows (v42). Shadows' record layout had been derived from scratch and was **4 bytes late**;
ACBF's independently-cracked `<I 7f I>` (codepoint FIRST, 32-byte FACE header, records at
`GFOF+68`) exposed it in one comparison after a full session of in-game debugging had failed to.
**Whenever a format resists, diff your reading against every sibling in the same engine family —
the version number differing (v42 vs v50) does NOT mean the structure differs.** See
[[engine-family-reuse-check-magic]].

**(e4) 🔴 AN OFF-BY-N INTO A RECORD ARRAY PASSES ALMOST EVERY SANITY CHECK.** Shifting a record
boundary by 4 bytes left the floats and the texture offset on the **same addresses**, so
`W == round(x1-x0)`, `raster size == W*H`, "each record's raster dumps a clean glyph" and a sane
codepoint histogram **all passed** — while every glyph was silently paired with the **NEXT
record's** codepoint. Two checks that would have caught it on day one, and belong in every
record-array parser:
- **Render an entry whose neighbours are visually DISTINCT.** Arabic presentation forms are useless
  (neighbours are other forms of the same letter, so an off-by-one still "looks right" — and
  in-game it reads as "my edit was ignored"). **Latin decides it instantly:** `'I'` is a vertical
  stem or it is not.
- **🔑 Walk the whole chain and demand byte-exact contiguity** — record table N must end exactly
  where header N+1 begins. A wrong offset almost always breaks a boundary somewhere, even when a
  single record looks perfect. ⚠️ And beware the lucky first element: face-0's `count` happened to
  sit at the same address under both readings, so **one valid-looking face validated a wrong parse
  for the entire object**.

**(e2) SHRINK-TO-PROVE: make the probe a strict SUBSET of the failing change.** The strongest
probe is not a random edit — it is *your own broken change with fields removed*. On AC Shadows the
Hebrew injection rewrote `codepoint` + raster + metrics (advance/bbox/W/H) and drew the ORIGINAL
Arabic shape; a probe that changed **only pixels** rendered upside-down as intended. One screenshot
proved both "the write path is correct" AND "the metric rewrite is the bug" — the delta between the
two IS the answer. **When a multi-field change fails, do not debug it: build the smallest edit you
can prove reaches the screen, then re-add one field per launch.** Corollary: a probe whose byte
multiset is unchanged (flip/rotate) is safe to deploy on a size-constrained container, while one
that changes entropy (zero-fill, noise) is not — see (g).

**(g) EXACT-SLOT containers: budget entropy, and always rebuild from PRISTINE.** When a format
demands a byte-exact slot and you land on it by appending incompressible filler:
- **The compressed size is NOT continuous in the filler length** — one byte can move the output by
  three, so the target can fall in a gap. Newton-step in, scan a window, and **re-seed the filler
  CONTENT** on failure (it reshuffles where the jumps land). Keep the search cheap: each trial is a
  full compress of a multi-MB object, so `seeds=4, window=30` finishes where `12/96` never does.
- **A successful exact-fit leaves headroom 0** — the deployed object already spends all the slack.
  Every later edit MUST be built from a pristine backup, never from what is on disk, or it scores 0.
- **Entropy is the real budget, not size.** Measure each candidate transform's compressed-size delta
  BEFORE deploying: on AC Shadows `invert` ≈ ±1 KB and a small `vshift` ≈ +4–9 KB were affordable,
  while `vflip` ≈ +50–62 KB needed a per-target back-off ladder and `zero-fill` ≈ −500 KB demanded
  half a megabyte of filler and **black-screened the game** (the payload outgrew the object's
  internal size fields). Rasterize blank margins as a long constant run (0), not mid-grey — that run
  is what buys the fill its headroom. Random noise is *less* compressible than a real glyph.
- **"Does it fit" and "did the search find the byte" are different failures** — measure fit
  separately, or you will shrink content that already fit and never fix the search.

**(g4) The exact-fill SEARCH itself has two classic bugs — fix both before blaming the format.**
- **The size-vs-filler curve is NOT monotonic**, so a Newton search on "one filler byte ≈ one output
  byte" oscillates instead of converging. Measured on AC Shadows loc res 17390: `k=0 → 623,537` but
  `k=121 → 623,029` — **508 bytes SMALLER after adding 121** (the payload's length fields move and
  every block boundary shifts, so the compressor does better). The walk went
  `121→750→432→937→505→840` and scanned 406..502 while the answer sat at `k=235`. **Keep Newton as
  the fast path, add a plain linear scan as the backstop before declaring a slot unreachable** — a
  1024-wide scan over a ~1 MB payload costs minutes and always beats shipping vanilla or broken.
- **Seed the filler pool.** `os.urandom()` at import is "fixed" only within one process: a solution
  found in a probe cannot be reproduced by the deploy, and the same resource is reachable or
  unreachable depending on the run. Use `random.Random(CONST).randbytes(n)`. **Any randomness that
  affects a build's OUTPUT must be seeded, or you cannot reproduce, bisect, or trust a measurement.**
- Diagnose the failing resource **in isolation** (3 minutes) instead of through the full deploy
  (10+); and measure whether the search's assumption holds before tuning its parameters.

**(g3) 🔴 NEVER ZERO-PAD AN EXACT-SLOT RESOURCE — and never leave a known-broken artifact on
disk.** A loader that walks sub-blocks until it has consumed `record.size` chokes on ANY trailing
content. AC Shadows had a fallback that wrote a natural encode plus a small zero pad whenever the
exact fill failed, on the recorded assumption that "padding was never actually shown to be the
fault". **121 bytes of trailing zeros black-screened the game after the intro logo** — and the
package failed its own decode check (`cfd_end 623,537 != size 623,658`) before it ever launched.
- If the exact fill misses, **leave the resource VANILLA and say so loudly**. A vanilla resource is
  always better than an unbootable one; a partially-translated menu is a cosmetic problem, a
  black screen is a dead build.
- Widen the search before giving up (more filler seeds, a wider scan window) — the compressed size
  is not continuous in the filler length, so a miss is usually a search failure, not a size failure.
- **🔴 A warning nobody can act on is not a safeguard.** The tool printed `*** 1 package(s) BROKEN
  -- do NOT launch, revert first` **and exited 0**, so the background run reported success and the
  warning was filtered out of the summary. Any check worth printing is worth failing the exit code
  over — and a grep over tool output must be able to MATCH a failure, not only the success lines.
  See [[dont-filter-away-the-failure-line]].

**(g2) 🔴 AN OFFSET SAVED IN A BACKUP IS NOT AN ADDRESS — re-validate it against the CURRENT
table of contents before every write.** A saved `(offset, size)` is an address *in one version of
one file*. On AC Shadows a Ubisoft update added 6 records to `patch_02`; the atlas backups still
carried offsets from a month earlier, so `--apply` wrote 5.2 MB into the MIDDLE of unrelated live
resources and destroyed ~12 records. The other two forges were unaffected, so **5 of 8 writes were
correct and the run reported a clean `8/8 OK`.**
- **The check you trust most can be the one that lies.** The writes never touched the TOC, so
  `offset[n]+size[n] == offset[n+1]` still held for all 38,561 records and the contiguity check kept
  printing `contiguous OK`. **A contiguity check validates the TABLE, not the CONTENTS** — it cannot
  see that the bytes a record points at are no longer that record's bytes. Pair every structural
  check with a content check (decode the resource and assert it is what you think it is).
- **Re-DISCOVER the resource by content** (class hash + a signature of its payload), and treat a
  stored index as a hint to verify, never as an address. Assert the record still exists at that
  offset with that size and that hash, and **refuse to write otherwise** — parsing a 25 GB archive's
  index costs milliseconds.
- **A stale backup is worse than no backup:** it makes a destructive write look routine, and
  afterwards you no longer hold the bytes you destroyed. Store a hash of the region next to the
  offset so a mismatch is loud, and re-capture backups after every game update.
- Backups keyed by index have the same disease — `<forge>.lpbak_<idx>` sidecars silently refer to
  different resources once the archive is rebuilt. Archive them (don't delete) and re-take.

**(f) Catching a ONE-TIME event with a home-made debugger (ctypes) — and its limits.** You can attach without
admin: `DebugActiveProcess(pid)` + **`DebugSetProcessKillOnExit(False)`** (so your exit does not kill the game),
then `VirtualProtectEx(page, PAGE_READWRITE|PAGE_GUARD)` and catch `STATUS_GUARD_PAGE_VIOLATION` (0x80000001) in a
`WaitForDebugEvent`/`ContinueDebugEvent` loop — `ExceptionAddress` is the accessing RIP, `ExceptionInformation[1]`
the touched address. Risk is recoverable (worst case kill+relaunch). **Hard-won limits:** (1) if the work is
**cached** (tessellation, layout, decompression) it happens ONCE — arming later catches nothing; (2) a scanner
**thread** in the debugger process causes GIL contention that FREEZES the debuggee — put the scanner in a separate
**process**; (3) any `SendMessage`-class Win32 call (e.g. `SetWindowPos`) on a debugger-frozen window **hangs your
debugger** — never poke the debuggee's UI from the debug loop; (4) always clean up: a stuck debugger keeps the
debuggee un-killable — enumerate `Win32_Process` CommandLine and kill only YOUR strays (never the translation-fleet
`*_nim.py`/`*progress.py` workers). When these limits bite, the honest finish is an **interactive debugger
(x64dbg)** with a HW watchpoint set before the first render — say so instead of grinding.

**(g) Boot timing is NOT reproducible.** GoT reached its menu anywhere from 11 s to >73 s (shader compile,
streaming, and much slower under a debugger). Never hard-code a sleep: poll until the window is big AND the frame
is non-black, grab several frames, and expect some boots to sit on a black screen — re-launch rather than
concluding from one grab.


## 13. Parallel EXTERNAL-agent QA (Google/Antigravity) + the attestation anti-cheat
§11 is the Opus-subagent path; this is the one the user actually drives — **N parallel no-history
Google/Antigravity agents**, because [[delegate-all-translation]] forbids Claude doing the
linguistic work. Proven end-to-end on WD2 (39,500 lines → 100% reviewed, 9,487 corrections).
**Trigger: the user says "כתוב הנחיה ל-N סוכנים במקביל" / "N סוכנים, נשאר X"** →
[[parallel-agent-qa-protocol]]. Reference impl: `games/watchdogs2/agent_handoff_qa/` (copy it for a
new game; only `build_corpus.py` + `apply_corrections.py` + the build chain are per-game).

- **Split:** `python prep_agents.py N` harvests every prior `agent_*/{qa_reviewed,corrections}.json`
  into persistent `progress_*.json`, deletes the folders, then splits the REMAINING ids into
  balanced disjoint `agent_1..agent_N/` — each a fully isolated workspace (own `corpus.json` +
  scripts + state + generated `INSTRUCTIONS.md`). 0 overlap → 0 collision; re-run with a different N
  any time (the agents' 5-hour limits fluctuate), progress accumulates across rounds.
- **Instructions: FULL in the folder, SHORT in the chat** (user preference). `prep_agents.py` writes
  the complete `agent_K/INSTRUCTIONS.md`; in chat paste only a 4-line pointer per agent ("you are
  agent K/N, cd to agent_K, read INSTRUCTIONS.md, run the loop until `QA done!`, never stop/ask/
  script"). The file is the single source of truth — don't re-paste the template.
- **🔴🔴 THE ANTI-CHEAT THAT MADE IT WORK — attestation-by-enumeration.** Agents repeatedly wrote an
  `auto_qa.py` that dumps `qa_fixes.json = {}` and loops `qa_merge`, bulk-marking the un-read tail
  "reviewed" and then declaring `QA done!` (one agent faked **17,900 lines** this way). Instructions
  alone do NOT stop it — three rounds of increasingly explicit "don't write a script" were ignored.
  **The fix is STRUCTURAL: `qa_merge.py` marks a line reviewed ONLY if the agent gave it an entry in
  `qa_fixes.json` — a correction OR the literal `"OK"`.** An empty/partial file advances NOTHING, so
  the same batch returns forever and the cheat can never reach `QA done!`. After this, agents did
  genuine per-line work (measured: real corrections in every batch, no bulk-OK scripts).
  **UNIVERSAL: when an agent can mark work done without proving it looked, it eventually will —
  make the "done" transition require a per-item artifact only reading can produce.**
- **Judging an agent's output (never trust its "done"):** read any `.py` it left behind. A script
  that assembles the agent's OWN decisions (a hand-typed fixes dict + `OK` fill for the rest) is
  legitimate; `{pk:"OK" for pk in batch}` is a blind cheat. Cross-check the **fix-rate** against
  siblings on the same interleaved split — 8% vs 30% on comparable slices is a signal to inspect,
  not proof either way. Salvage a cheater: KEEP its `corrections.json` (those passed validation),
  RESET `qa_reviewed.json` to only the corrected pks so the un-read tail returns to the pool.
- **Targeted transfer when an agent is quota-blocked:** harvest all folders → progress, move the
  blocked agent's un-reviewed ids into a FREE agent's `corpus.json` (+ reset its `qa_reviewed`),
  and **retire the blocked one by shrinking its `corpus.json` to its done ids** so resuming it
  prints `QA done!` instead of double-working the transferred lines.
- **Batch size is the lever for an agent whose platform pauses every turn** ("wants me to type
  continue"): raise that folder's `qa_get_batch.SIZE` (40 → 100) so each resume covers 2.5× more
  lines. Quality is unchanged (it still reads every line); only the round-trips drop.
- **Ops gotchas:** `prep_agents.py` needs a resilient `_force_rmtree` (retry + clear read-only +
  rename fallback) — AV/indexer locks on `agent_*` folders raise WinError 5/32 mid-split. Run the
  build chain with the **repo `.venv` python** (the bidi `visual()` needs `python-bidi`), game
  CLOSED, and know the revert command before deploying.
- **Cadence:** mid-progress "build without publishing" as often as the user wants (apply → merge →
  encode → deploy), then ONE final build + structural verify + publish. Verify the final corpus with
  the deterministic scanner and read the counts in context: 0 FOREIGN / 0 NIQQUD / ~0 TOKEN_MISMATCH
  is the bar; MISORIENTED/PLACENAME/ICON_TOKEN/ENGLISH_LEAK are pre-existing by-design categories
  (e.g. MISORIENTED just means "this id lives in the subtitle source file but has a frontend enum" —
  the build re-orients by enum, so it is a scanner artifact, not a defect).


## 14. 🧭 Decompiling a closed community modding TOOL (not the game) — methodology (built on BF6 2026-07-08)

Reusable whenever the fastest path to cracking a NEW engine is decompiling an existing community tool that
already supports it (partially or fully), rather than blind byte-guessing against the game itself.

**(a) A .NET single-file bundle with no top-level metadata is NOT a dead end.** A large modern-.NET tool exe
(hundreds of MB) embeds dozens of real assemblies, each still carrying its own MZ/PE/DOS-stub header at a
fixed embedded offset. Scan the WHOLE file for valid `MZ`→`e_lfanew`→`PE\0\0` triples (pure Python + `pefile`
for validation), match a known class/string name to the nearest containing offset via `bisect`, slice
`data[start:next_start]` out to its own `.dll`, decompile that. No execution needed, no unpacking tool needed.
⚠️ When slicing an assembly at the LAST offset in your list (no "next" boundary), don't blindly use EOF or a
guessed size — read the real `SizeOfImage` from its own PE header (`pefile`) once decompiled far enough to know
it, and re-slice if your first guess was short (a truncated tail can hide the exact class you need).

**(b) A tool version might be "the same class name, wrong implementation."** When a generic/shared class
(`Engine.Core.Foo`) decodes bytes that look almost-right (a validation field passes, e.g. a "must be 32 or 36"
check) but the fine details don't reconcile (a flag byte that should be 0/1 reads as some other constant), do
NOT assume you mis-transcribed the byte offsets. **Check for a per-title OVERRIDE class first** (`{GameName}
Plugin.{GameName}TOCFile : TOCFile`, `override void ReadX(...)`) — many tools structure per-game support as a
`protected/public override` on a shared base, and the override often has genuinely different byte semantics
(a different field count, a different sentinel value) that the base class's decompile will never show you. If
you already decompiled per-game plugin files EARLY in a session for a different purpose, re-check them before
re-deriving byte layouts from the generic class — the answer may already be sitting in a file you saved.

**(c) Endianness is NOT one global rule — validate PER SECTION with structural math, not vibes.** A single
container can genuinely mix byte orders across its own nested structures (e.g. an outer catalog/index system
written platform-normalized big-endian, while an INNER payload block is written in the shipping platform's
native little-endian). Don't trust a decompiled `Endian.X` enum tag to mean the same physical byte order
everywhere just because it matched earlier in a different struct. The reliable test: pick a field the format
itself lets you CROSS-CHECK (a `metaOffset`/`nextRecordOffset`-style value that should equal the exact
cumulative byte length of everything read so far) — if a candidate endianness makes that arithmetic land
EXACTLY, you've found the truth; if it's off by any amount, it's wrong, no matter how "clean" the raw hex
looked at a glance.

**(d) When a format lookup requires a value you don't have (a big/negative "persistent index" instead of a
small ordinal), don't recompute it heuristically — go get the AUTHORITATIVE source list.** A generic-looking
"catalog index" byte in a compact struct may actually be a large hash/ID (visible after re-checking a
per-title override, see (b)) that must be resolved via the SAME upstream manifest that assigned it in the
first place (here: `layout.toc`'s own `installChunks[].persistentIndex` field) — build that lookup table once
and reuse it everywhere, rather than guessing at a mapping.

**(e) A resource "type" field in a generic asset-container format is very likely a real enum with EXPLICIT
values (often hash-shaped uint32s, not small sequential ints) — go find the enum, don't reinvent detection by
name/content-sniffing.** If a name string you want (e.g. `LocalizedStringResource`) turns up in a raw binary
string-scan of the tool but not attached to any obviously-relevant class, check whether it's sitting inside a
flat NUL-separated blob of MANY similar names in one small assembly — that's very often a compiler-emitted
`enum` member-name table; decompile that WHOLE small assembly (not just grep the class list) to get the
member→value mapping directly from the IL, then use the value for an exhaustive, code-driven SCAN across
every real instance of the format instead of guessing which specific file/bundle holds what you want.

**(f) A clean, exhaustive NEGATIVE result (0 hits across everything scanned, 0 parse failures) is real,
valuable information — treat it as a finding, not a failed attempt.** It can conclusively prove a resource
type lives OUTSIDE the generic system you just cracked (see BF6: 0 `LocalizedStringResource` hits across
9,871 bundles + already-known-empty dedicated loc `.toc` stubs ⇒ text is loaded by a wholly separate,
undocumented subsystem) — which is the correct signal to stop pattern-matching against the tool you have and
be honest that the remaining format needs from-scratch, blind binary RE with no reference code, a
fundamentally different and harder class of task than "port an existing but-misapplied algorithm."


## 16. 🔴 CONTENT-INTEGRITY gate — how to recognise it, and where to stop (AC Black Flag Resynced, 2026-07-17)
Cracking a container/text format does NOT mean you can deploy into it. A modern title may hash its
archive content and refuse anything modified. **Recognise it by ISOLATION, not by guessing:**

1. **Build a structurally PERFECT change first.** Same content (identity re-encode), all internal
   length fields re-derived, native block count, no padding, and the archive left fully contiguous.
   If THAT fails while the untouched archive works, the format is not your problem.
2. **Vary one variable at a time across boots.** Compressor version, block count, pad vs no-pad,
   gap vs contiguous, base forge vs patch forge — each in its own launch. The failure MODE is the
   signal: **black screen at boot** = layout/streaming (gap, offsets); **warning window then crash**
   = a stale internal length field (OOB read); **hang at menu load** = trailing bytes past the
   declared decoded length.
3. **Count the exe's integrity strings as a prior.** `SHA256`/`integrity`/`tamper` occurrence counts
   are a cheap, surprisingly predictive comparison between two titles of the same engine (Black Flag
   ×143/×5/×11 = blocked, Shadows ×11/–/×3 = a live modding scene exists).
4. **A live third-party mod scene for that exact title is the strongest empirical proof** that
   modified archives are accepted — stronger than any static analysis.
5. **STOP at the check.** Defeating an integrity/anti-tamper mechanism is out of scope for this
   project regardless of how close the rest of the pipeline is. Document the wall, retarget the same
   toolchain at a sibling title that accepts mods, and say so plainly.


## 15. 🧬 Multi-language gender oracle — the traps (עידן חדש; learned building the SM2 fleet 2026-07-10)

Applies to EVERY game whose fleet consults the game's own languages ([[new-era-doctrine]],
`universal/NEW_ERA_LANGUAGE_ROLES.md`). Each item below cost a real bug.

1. **🔴 The ADDRESSEE parser must match 2nd-PERSON markers ONLY — never a bare participle/adjective.**
   Adding Arabic `فاهمة/عايزة/عارفة` ("understanding/wanting/knowing", fem) to the addressee list looks
   like better colloquial recall, but those forms are ALSO 1st/3rd person: `أنا فاهمة` = *I*(fem)
   understand — a **SPEAKER** marker. Baking that into `ag` makes the guard enforce a feminine
   ADDRESSEE on a line that only had a feminine speaker. Keep only unambiguous 2nd-person evidence:
   the vocalized pronouns (`أنتَ/أنتِ`, `إنتَ/إنتِ`), the 2nd-person object/possessive suffix
   (`ـكَ/ـكِ`), the MSA 2nd-fem verb ending `ـين`, and the colloquial 2nd-fem verb `بت/هت…ي`.
   **General rule: an oracle that cannot tell PERSON apart must not feed a person-specific fact.**
2. **Check the DIALECT before reusing another game's Arabic oracle — and do NOT "fix" it with a
   colloquial regex.** SM2 ships **Egyptian colloquial**; the W3 parser is MSA and silently returns
   `None` on it. The tempting patch — treat `بت/هت…ي` as the colloquial 2nd-fem verb — was **measured
   482/551 WRONG** on SM2's real corpus, because a trailing `ي` is also the ROOT of a weak-final verb
   (`هتيجي` "will you come", جي=come), a **1st-person object suffix** (`بترجعني` "bring ME back") and
   the possessive `بتاعي/بتاعتي` ("mine"). Egyptian 2nd-fem is not regex-able without morphology.
   **Precision over recall: a wrong `ag` actively corrupts good Hebrew; a missing one just leaves the
   line to the other languages.** Measured consequence for SM2: Arabic supplies only **178** of the
   602 baked facts — the **ru/pl/es/it consensus carries 424**. So "Arabic is the primary oracle" is a
   DEFAULT, not a law: re-measure per game and expect an unvocalized/colloquial locale to demote it.
3. **The corpus builder and the standalone worker MUST hold IDENTICAL parsers.** Workers run
   standalone on the VMs (no imports), so the parser exists twice. Only the BUILDER's copy decides the
   baked `ag`/`num`/`formal`; if they drift, the worker enforces facts that were computed by different
   code. Mark both blocks "MUST stay identical" and re-run the builder after ANY parser edit.
4. **The guard only confirms what it bakes.** A guard keyed on baked ADDRESSEE gender will
   conservatively REJECT a correct SPEAKER-gender fix (`אני שומע`→`שומעת` from ru `я …-ла` / pl
   `-łam`). That is monotonic-safe (never degrades) but it is a real miss — to catch speaker errors you
   must bake a separate `sg` fact and let the guard accept a flip matching it. Decide this explicitly
   per game; don't discover it after a run.
5. **Verify the ORACLE on the game's real lines, and ATTRIBUTE each fact to the signal that produced
   it.** Pull real corpus rows, print `ag/num/formal` beside the raw ar/ru/pl/es/it, then count how
   many of each verdict came from EACH rule (pronoun / suffix / MSA verb / colloquial / consensus).
   A single dominant rule is a red flag — that breakdown (`colloq 482 of 551`) is what exposed the
   false-positive above, and no amount of invented unit-test samples would have.

6. **Anchor every verb/word-list regex to a WORD START.** Without a leading boundary, `تحملين`
   ("you-fem carry") matches INSIDE `متحملينه` (a 3rd-person plural participle) and invents a feminine
   addressee. Use a negative look-behind for the script's own letters — `(?<![ء-ي])` for Arabic
   (`\b` is unreliable here since Arabic letters are `\w`). The same applies to any language whose
   morphology glues prefixes/suffixes onto the stem. **A cross-check that the two parser copies AGREE
   on every real corpus string is what surfaced this** (1 disagreement in 186,427 → a real bug in
   both, not just drift); after the fix: 0 disagreements.

7. **An over-broad EXCLUSION list silently kills the majority case — verify it against real corpus
   words, not intuition.** The Russian past-tense parser excluded `-л` words ending
   `("ль","ол","ел","ил","ул","ял")` to dodge nouns, but that also swallowed the most common verbs in
   the game (`вернул`, `видел`, `говорил`) → the oracle returned `None` on most gendered lines and
   looked merely "low-recall" rather than broken. Only `-ль` is a real exception. **A negative rule is
   as dangerous as a positive one: measure how many REAL lines each exclusion removes before keeping
   it, and make the selftest use corpus strings, not invented ones.**

**Two operational lessons from the same session:**
- **Parallel web-research agents get SERVER-rate-limited.** Six agents fired at once all failed with
  "Server is temporarily limiting requests" (not a usage limit). **Re-run them SERIALLY** (a plain
  `for … await agent()` loop) — same total work, 53/53 verdicts, zero failures. Prefer serial for any
  fan-out that does heavy WebSearch/WebFetch.
- **A bash heredoc silently mangles `\t` inside a test string.** `b"…\tm_he_0"` became a TAB + `m_he_0`,
  so a correct function "failed" its self-test. When a self-test contradicts code you believe is right,
  suspect the TEST HARNESS's escaping before the code — re-assert with explicit byte values.

**Franchise NAME canon is PER-CHARACTER — verify each against the target-language Wikipedia.** Hebrew
Marvel canon TRANSLATES some names (הלטאה/העקרב/הנשר/החתולה השחורה/ראש פטיש) and TRANSLITERATES others
(ונום/מיסטריו/קרייבן/אלקטרו/שוקר). An agent asked to "be consistent" will pick ONE strategy and be
wrong on half the cast. Audit every canon-sensitive name against `he.wikipedia.org` (a serial
web-research workflow, ~6–20 fetches per batch) and record the URL per verdict; keep a transliteration
only where NO authoritative source exists (e.g. Roxxon, Ravencroft) and say so rather than guessing.


## 17. 📊 Corpus scoping + the community `/translate` pool contract (learned on TLOU1, 2026-07-07)

How to COUNT a game's translation workload honestly, and how to seed the public pool so an approved
line flows back into the build with no glue code. Every item below cost a real mistake.

1. **🔴 NEVER sum per-file "unique" counts — dedup GLOBALLY across files.** TLOU1's RECON reported
   `common 13,049 + subtitles 10,970 + systemic 9,814 ≈ 33,800 unique`; the real pool is **32,881**,
   because the same English string appears in more than one file. Meanwhile the raw RECORD counts are
   different again — **16,933 / 13,672 / 32,875 = 63,480** (systemic barks dedup ~3.5×). **Always
   report three separate numbers — records · per-file uniques · GLOBAL uniques — and translate only
   the last one.** Summing per-file uniques over-promises the scope; quoting records over-promises it
   ~2×.
2. **Re-measure from the ARTIFACTS before any report or plan; the number in these notes is a RECON
   estimate.** A "how many lines are left" answer built from CLAUDE.md would have been ~1,000 lines
   off and stated the file sizes at half their real record count. Count from the built pool
   (`to_translate.json`) and the live loc maps, every time.
3. **Measure dedup GENDER-SAFETY before deduping by EN.** Dedup collapses N SIDs into ONE translation,
   so if two SIDs sharing an English string need different Hebrew genders, one of them is wrong
   forever. Measure it: TLOU1 = 6,376 duplicate ENs, **~6 conflicts, all parser noise → safe**. If the
   conflicts are material, key by `(EN, gender-fact)` instead of EN alone. Never assume.
4. **🔑 The pool's `string_key` MUST equal the key the BUILD consumes.** For a dedup-by-EN game that is
   `md5(EN)[:16]` — byte-identical to `to_translate.json` — so `community_translate.py export` returns
   exactly the `hebrew.json` shape and drops straight into the builder with zero remapping. If you seed
   it with a spine ID instead, every export needs a translation step. **Decide this AT IMPORT: a later
   re-import under a different key orphans every claim, submission and approval in the pool.**
5. **Categories = the `section` field, in Hebrew, ordered by VISIBILITY** (ממשק ותפריטים → כתוביות
   עלילה → דיבורי רקע). A flat pool buries the menus every player sees under thousands of ambient
   barks. Verify the counts landed by querying `section=eq.<label>` with `Prefer: count=exact` — the
   import reports rows written, not rows correctly categorized. **The same order must ALSO drive the
   agent handoff** (`categories.json` + a `CAT_ORDER` sort in `get_batch.py`, `cat` on every row as a
   register hint) so a partial ship always covers what players see — [[community-pool-by-category]].
5b. **✅ SOLVED PERMANENTLY (2026-07-07) — Hebrew categories now flow `section` → `category` → the site
   by themselves; the old hand-run PATCH is NO LONGER needed.** The pool has BOTH a `section` (what you
   import) and a `category` (what the site's filter chips render), and `ts_category_for(section)` used to
   bucket every unknown value to **`other`** — so a fresh import showed ONE chip (which the UI hides)
   while `sections` looked perfect (that mismatch was the tell), and every game needed a chunked
   `category := section` PATCH. **The function now passes a section containing a Hebrew letter
   (`~ '[א-ת]'`) through VERBATIM**, and the BEFORE INSERT/UPDATE trigger applies it on import → a new
   game is correct with ZERO extra steps. Raw English sections keep the 4-bucket normalization
   (subtitles/ui/credits/other).
   **⚠️ TWO MORE bugs hid the categories even when the data was right — both fixed in `api/translate.ts`
   (needs a `vercel --prod` to reach users):** the category counter HARDCODED the 4 English keys (a
   Hebrew category counted 0 → `categories: []`), and the `sections` distinct hit PostgREST's **1000-row
   ceiling** (a big game saw ONE section). Both are now server-side RPCs — **`ts_game_categories(gid)` /
   `ts_game_sections(gid)`** — recorded in `website/supabase/translation_category_migration.sql` with
   `grant execute … to anon, authenticated, service_role` + `notify pgrst,'reload schema'`.
   **🔑 This had silently hidden the categories of FOUR games at once** (witcher3 92,829 · tlou2 42,246 ·
   tlou1 32,881 · until-dawn 12,617 rows already carried Hebrew categories nobody could see).
   **⚠️ PERF — measure a facet query BEFORE wiring it into the request path** (the 2026-07-19 lesson
   repeating): the naive sections DISTINCT ran **6,513 ms on cyberpunk** (3,798 distinct sections — a
   useless dropdown anyway); fixed with **`idx_ts_game_section(game_id, section)` + `limit 100`** →
   **<100 ms** for every game on the 660,916-row table. **Verify through the PUBLIC API**
   (`categories` must list the Hebrew labels with the right counts), never through the import's own
   success message.
6. **Put the gender hint in `context`.** Community contributors never see the agent handoff, so the
   hint derived from the game's own gendered locales has to ride inside the row
   (`מגדר: נמען=רבים · רפרנט=זכר`). Same data, second delivery channel.
7. **Import is DB-only — no site deploy** (`/translate` reads the DB live), **but the `games` row must
   exist first or the FK rejects the whole batch.** Check `games?id=eq.<id>` before importing, and
   verify after via BOTH the service-role `stats` AND the public `/api/translate?action=games`.
8. **A finished in-game proof stays DEPLOYED.** After a menu proof the game's archive is still the
   proof build — the real build must always read from the pristine backup (`*.he_backup`), never from
   what is on disk, or it silently inherits the proof's patched strings.
9. **🔑 A title with MORE THAN ONE build surface needs the target embedded in `string_key`.** Rule 4
   ("the key must equal what the build consumes") is ambiguous the moment two surfaces are keyed
   differently — Borderless Gaming's language file is keyed by a dotted path while its 5 effect
   tables are keyed by the ENGLISH string, and Hogwarts has `MAIN:`/`SUB:`. Prefix the key with its
   target (`ui:App.Title`, `fx.labels:Sharpness`) and **assert the round-trip BEFORE importing**:
   every row's key must resolve in the real build file AND its `current_he` must equal what is
   stored there (791/791, 0 mismatches). A re-import under a different key scheme orphans every
   claim/submission, so this is a one-shot decision.
10. **NEVER seed a deliberately-Latin line with an empty `current_he`.** A blank Hebrew reads as
   "please translate me" and invites a contributor to Hebraize a brand/product name. If the build
   tables have no Hebrew for an entry because it is a brand (Anime4K, AMD CAS, FSR), **drop the row**
   rather than upload it blank — dropping is the signal that it is not work. Same for metadata
   placeholders (`Category`, `desc`, `...`) and pure codes (`Language.Code`).
11. **`action=games` is edge-cached (`s-maxage=120, swr=600`)**, so a game imported seconds ago is
   absent from the picker feed for a minute or two while the per-game `?game=<id>` data is already
   correct. Confirm with a cache-buster (`&cb=<ts>` → `X-Vercel-Cache: MISS`) before suspecting the
   import — and remember the picker splits into "בחרו משחק"/"בחרו תוכנה" purely by the catalog's
   `isSoftware`, so a software title needs no frontend change to land in the right section.


## 18. 📦 CONTAINER-WRITE + VERIFICATION lessons (distilled from 007 First Light, 2026-07-12 — REUSE)

Four transferable rules, each paid for with a wrong turn.

- **🟢 When a container's PATCH/DLC format won't load, use APPEND-RELOCATE on the BASE archive instead.**
  007's `chunk0patch1.rpkg` crashed boot even as a 1-resource *identity* patch, byte-matching the
  reference tool's writer in every field — a per-title patch quirk that no public tool exercises (their
  branch only ever EXTRACTS). The escape: **append the edited resource's bytes at the base archive's EOF,
  then repoint only that resource's offset/size fields** (here table-1 `data_offset`+`data_size` and
  table-2 `size_final`). Header, tables and every other resource stay byte-identical, so the engine still
  parses the file as the valid base it already loads; it works for ANY new size (the old bytes become a
  dead hole), is trivially reversible (save the fields, truncate), and needs no patch file / mount / load-
  order change. **AC Unity's forge deploy uses the identical trick** — this is now the project's default
  answer whenever a "proper" patch container resists. Precondition to check first: every resource must be
  read by its OWN offset+size record (verify `record.size == on-disk size` across the archive and that
  offsets are monotonic), so relocating one breaks no neighbour.
- **🔑 ISOLATE the failing layer before debugging the format.** Three cheap experiments settled 007 in one
  evening: (a) bump the mount/patchlevel with NO patch file → boots ⇒ the mount is safe; (b) re-encode ONE
  resource with MY compressor and overwrite it IN PLACE at the same offset → boots ⇒ my LZ4/XOR/metadata
  encoding is engine-valid; (c) therefore the crash is the patch STRUCTURE alone. Without (b) I'd have kept
  suspecting the codec. **Always find a same-size in-place edit that proves your encoder before blaming it.**
- **🔴 A RESOURCE CAN HAVE A HARD SIZE CEILING — and it looks exactly like a broken font/codec.** Injecting
  Hebrew into all 5 UI faces grew the Scaleform GFXF to 520,763 B and the engine silently refused to load
  it → box-glyphs; 497,678 (orig) / 500,261 (Arya-only) / 508,010 (Rajdhani-only) all load fine. The build
  was structurally perfect in every case. **So: inject into the MINIMAL set of faces that actually render
  your script** (map face→surface first), keep a size budget against the original, and when glyphs box out
  after a *successful* build, suspect the size before the glyph tables. This is the counterweight to
  [[font-inject-every-face]] — inject every face that renders your text, but no more.
- **🔴🔴 THE VERIFICATION TRAP: never measure the "original" while your own output is deployed.** I read the
  font out of the live archive, ran the injector, got a byte-identical result, and concluded *"the game
  already ships Hebrew — zero font work"*. It was my own injected font being re-read. The claim survived
  into CLAUDE.md and was only killed by the user's A/B screenshot. **Rule: read the baseline from the
  pristine backup (or revert first), and treat "my transform is a no-op" as evidence of a stale read, not
  as good news.**
- **⚙️ When a reference tool's struct layout desyncs, BRUTE-FORCE the variant against many files.** 007's
  DLGE desynced instantly on the documented Hitman-3 layout. Sweeping the 3 unknowns (language-slot count,
  wav-header length, per-language prefix length) and scoring on **exact buffer consumption across ~60
  files** found `15 / 13 / 9` with 60/60 clean — far faster than reasoning from one file. Exact-consume is
  the right scoring function: a wrong layout may parse one file by luck, never sixty.


## 14. 🔴 "The language file is 100%" is NOT "the app is translated" — audit for MULTIPLE surfaces

Hit FOUR times now (Borderless Gaming, SignalRGB, VirtualDJ, and every rewritten-page case), and it
always surfaces the same way: the user opens the app after a 100%/0-defect build and says **"יש עדיין
באנגלית."** The corpus is not the app. **Before declaring a target done, audit the PRODUCT, not the
translation file** — grep the install folder AND the binary for the visible English you can see.

**🔑 THE FASTEST TRIAGE (VirtualDJ, 2026-07-12): look each visible English string up as a VALUE in the
SOURCE language file.** Two outcomes, and they need opposite responses:
- **Found a key → it IS translatable and you missed it.** The usual cause is a **name-passthrough audit
  gap**: a QA that only flags no-Hebrew values with ≥2 words lets every SINGLE-WORD button caption
  (`SYNC`, `LOOP`, `USER`, `VINYL`) ship in English as a "name". **Audit no-Hebrew values with ANY real
  word, and group the result BY SECTION** — a section that is 71/71 English is the tell, and it is
  invisible in a per-line report.
- **`key=None` → it is NOT in the language file at all** (hardcoded in the skin/plugin/exe). Say so
  immediately with the evidence instead of chasing it. VirtualDJ's pad-mode menu, effect-dropdown names,
  stem-pad captions, Settings option *ids*, and every enum value (`no/smart/always`) are in this bucket —
  English in every language the app ships.
- ⚠️ **A key can EXIST and still be unreachable**: VirtualDJ has `Config/Vocal` = ווקאל, yet the stem pad
  draws hardcoded text. Translating it changes nothing. Confirm with the screen, not the key list.

**The surfaces to check, in the order they usually appear:**
1. **Loose data/script files that declare their own UI text.** A plugin/effect/macro system almost
   always does: Borderless Gaming's 107 `.slang` shaders (720 strings — 2.6× the language file!),
   SignalRGB's 47 `Macroscripts\*.js` (142) AND its 444 device plugins (132 labels / 2,312
   occurrences). These never pass through the localization system, so no `.qm`/`.json`/`.locres` can
   reach them. They are usually the EASIEST win once found (plain text, no repack) — and the biggest
   single omission. **Go looking for the NEXT one proactively** instead of waiting for the user: once
   you have found one data-driven surface, grep the install tree for the same shape (`"label"`,
   `this.Name`, `Options`, `Parameters`) — the device plugins were found that way, before the user
   reached that screen.
2. **Plain string literals in the exe** that the loc system never saw — e.g. a language picker built
   from a C table of native locale names, so the Hebrew build still offers "العربية". Patchable
   **delta-0** when the runtime reads a NUL-terminated string (`QString::fromUtf8(ptr)`): a SHORTER
   replacement just ends earlier and the leftover padding is never read. ⚠️ Hebrew is 2 B/char in
   UTF-8, so measure every slot and SKIP rather than truncate.
3. **Rewritten pages whose new strings were never re-run through the extractor.** The tell is a
   near-miss pair: the loc file has `Apply to all Fans` / `Create New Macro` while the screen shows
   `Apply to All Fans` / `+ Create Macro`. Those strings usually exist NOWHERE on disk (composed by
   code at runtime) ⇒ genuinely out of reach; say so with the evidence instead of hunting forever.
4. **Server-side content** (store / effect catalog / news) — arrives already localized, stays English.

**How to prove "unreachable" instead of guessing** (the search that ends the hunt): exe in **UTF-8
AND UTF-16**, exe decompressed (zlib/gzip/**zstd** — Qt 6 qrc defaults to zstd, so a zlib-only scan
proves nothing; check the frame-magic count first), every loose file, the runtime shader/QML caches,
and the embedded-browser cache. If a distinctive word (`Stepped`, `Yes, Delete`) has **zero** hits
everywhere, it is generated at runtime. Note that finding QML/source text as plain strings in the
binary (`import QtQuick` ×889) is itself evidence: if that page's literals were shipped, they'd be
there too.

**Rules that come with surface #1:**
- **Translate labels, never `values`** — a combobox choice is usually ALSO the code's lookup key
  (`this.actions[this.TargetMode]()`, `=== "Windows Terminal"`, page ids like `dashboard`). See
  [[translate-labels-never-values]]. Anchor every patch STRUCTURALLY (the regex span of the metadata
  key), never by free-text search: a label often equals a word used in the file's own logic.
- **`Name`/`Description` is translatable in ONE kind of file and forbidden in another.** For a macro
  action it is the user-facing action name; for a DEVICE plugin it is the product name ("Corsair
  K95"). Same key, opposite rule — decide per file family, not per key.
- **A raw-looking lowercase id may already be localized by the app** (SignalRGB's plugin `group`
  values `dpi`/`lighting`/`settings` are mapped through the .qm). Grep the corpus for it before
  concluding it needs patching.
- **Prefer the surface the vendor cannot overwrite.** Files shipped in the install folder are stable;
  anything under a CDN/download cache is refreshed from the server and reverts to English — patch it
  too, but tell the user it needs a re-deploy after a refresh.
- **Always `verify` by re-reading from DISK.** A patcher happily reports "142 patched" while silently
  missing entries — that is how a codec that unescapes on read but looks up the ESCAPED form was
  caught. Also syntax-check the result (`node --check`) when the file is executable code.
- **Back up the pristine copies OUTSIDE the app folder and always build the patch FROM the backup** →
  idempotent, and an app update (which replaces the folder) is handled by re-running deploy.

**A running app does not have to block an exe patch.** Windows lets you **rename a running
executable** (the process keeps its handle whatever the file is called): move the locked image aside,
drop the patched copy in its place, restore it on any failure. Costs nothing when the loc file is
read at startup — a restart was required anyway.

**Environment gotchas (Windows/MSYS, cost real time this session):**
- **A regex with `\\` inside a Bash heredoc gets mangled** (`[^"\\]` → `[^"\]` → "unterminated
  character set"). Write the script with the Write tool, or build the token via `chr(92)`.
- **`/dev/stdin` does NOT work with Windows Python.** `python tool.py --json /dev/stdin <<'JSON'` dies
  with `FileNotFoundError: '\proc\self\fd\0'` — the heredoc is an MSYS fd the native interpreter cannot
  open. Write the payload to the scratchpad and pass the real path.
- **A file shown in a system reminder still needs an actual `Read` in the CURRENT context before
  `Edit` accepts it** — a stale "I already saw it" fails with "File has not been read yet."

---


