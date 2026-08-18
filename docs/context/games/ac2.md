## Assassin's Creed II (2009 classic) Hebrew — foundation built, GO (2026-06-18)

The **classic AC2** (`D:\Games\Assassin's Creed II`, Ubisoft Montreal, Scimitar
engine) — NOT to be confused with AC Shadows above (different generation,
different repacker). Feasibility researched + the read-side foundation built.
Verdict **🟢 GO**: Persian AND Arabic AC2 fan-translations (both translate the
menus) prove the entire chain works on this engine. No game file modified yet
(read-only recon). Full writeups: `games/assassinscreed2/{FEASIBILITY,RECON,
PIPELINE}.md`; memory [[ac2-feasibility-go]].

- **Format (read-side fully cracked):** `.forge` = magic `scimitar` + **version 25**
  (AC Shadows=42). `tools/ac2_forge.py` (pure Python, no deps) parses the container:
  record table 16B `[i64 data_offset (0x800-padded)][u32 hash][u32 SIZE]`; resource
  names read authoritatively from each resource's `FILEDATA`(8)+name(128) header.
  Verified: extracts any resource by name. CLI list/grep/extract.
- **Text** = `DataPC.forge` (81 resources) → `LocalizationPackage_<Lang>` +
  `_Subtitles`. **14 LTR languages (English…Chinese), ZERO Arabic/Hebrew/Persian** →
  the Arabic-slot hijack does NOT apply; must **hijack an LTR slot** (e.g. English).
  Payload = **char-INDEX serialization** (`[u32 key_hash][u32 count][count×u16
  index]` into a char table) + checksums = the community's known-hard repacker part.
- **Fonts** = `DataPC_extra.forge` (1213 resources) → per-script **DDS bitmap
  atlases** `*_<Script>CharacterSet_1_MapDesc` (Latin/Numbers/**Russian-Cyrillic**/
  Korean/Japanese/Chinese). The engine renders non-Latin scripts via these → add
  Hebrew glyphs to an atlas (over unused Latin slots, Persian-patch style). DDS, NOT
  TTF.
- **RTL = no engine bidi** (2009) → **bake visual order into the data**:
  `work/ac2_rtl.py to_visual()` (built + unit-tested 7/7) — reverse, keep numbers/
  Latin/tokens forward, mirror brackets, preserve `[TOKEN]`/`{VALUE}`/`%s`/tags.
  Hebrew needs no joining (unlike Arabic's reshape).
- **Container round-trip — format DECOMPILED, NO GUI needed.** AnvilToolkit
  (`Downloads\AnvilToolkit_Release_v1.2.10…`, free, AC2-capable) does the round-trip
  but is GUI-only — so it was **decompiled** to get the exact format instead:
  extracted `AnvilToolkit.dll` from its .NET-5 single-file bundle + `ilspycmd`
  (`DOTNET_ROLL_FORWARD=LatestMajor`; only .NET 7/8 installed) → read+write of
  `LocalizationPackage`/`StringTable`/`StringFragment`/`IndexedData` +
  `DataFile`/`ForgeFile` + CRC32/64. Spec → `games/assassinscreed2/FORMAT.md`.
  Strings = byte-codes indexing a sorted unique-char dict (<256 chars → 1 byte/char);
  the discarded u32 is a constant marker, NOT a content checksum. **The whole
  pipeline is reproducible in pure Python (like WD2/GoWR) — no GUI.** `texconv.exe`
  (CLI, bundled) handles the DDS font atlas. Decompiled C# kept in `c:\tmp\anvil_src\`.
- **NEXT (gated on user choices, see PIPELINE.md):** pick the LTR slot to hijack;
  AnvilToolkit-assisted vs full Python repacker; UI-only vs +subtitles. Then:
  identity round-trip (prove repack) → Hebrew font glyphs (`work/ac2_font.py` TODO)
  → 1 test string → in-game proof → translate trio (copy SM2) → publish like
  SM2/CP2077.

### ✅✅ AC2 UI Hebrew RENDERS CORRECTLY — native size/weight, RTL (2026-07-19, self-verified in-game)

The main menu shows **מצב עלילה / תוספות / הגדרות / יציאה** — right-to-left, clean, and at the SAME
size as the game's own Latin (42px atlas cell → 28px on screen, identical to `SELECT`). Build:
`games/assassinscreed2/work/build_hebrew_final.py` (`--dry` prints the per-letter layout plan first).
Getting from "readable but ugly" to "native-looking" was three measured findings, not guesses:
- **🔑 THE SOLID-BLOCK PROBE (reusable for ANY bitmap-atlas font).** Paint every carrier cell's FULL
  bbox solid white, put those carriers in a menu string, screenshot, measure. It answered three
  questions in ONE launch: (a) the engine's UV rect does **not** exceed the blob bbox → no leftover
  original ink, so the "striped box around some letters" the user reported was the game's **own red
  striped selection bar**, not an atlas artifact; (b) the **advance ≈ bbox width + ~4px** → wide gaps
  can only come from drawing the glyph smaller than its cell; (c) atlas→screen scale = **0.64**.
  Tool: `work/probe_cell_metrics.py`.
- **🔴 "Letters too small / inconsistent" = FONT-ASPECT MISMATCH, not a scaling bug.** ProLight's Latin
  caps are narrow (w/h ≈ **0.71**); Hebrew letters are near-square. **David = 0.915**, so filling the
  cell height demanded 65-83% horizontal condensation and the code shrank everything instead → 71%
  height + big gaps. Measured EVERY Hebrew font on the machine (fontTools cmap filter so `.notdef`
  fallbacks don't pollute the ranking, then median `textbbox` width/asc) and picked
  **`FrankRuhlLibre-Light.ttf` (0.846)** — closest aspect AND the right weight for a "Pro **Light**"
  Latin (classic Frank-Ruehl serif suits AC2's Renaissance UI). Condensation drops to 79-95%.
  **UNIVERSAL: when injecting a script into a foreign bitmap font, match the CELL's aspect ratio first
  — the donor font choice, not the scaling code, decides whether it can look native.**
- **The layout rule that produces consistency:** ONE uniform scale `s = cell_h / median(asc of the
  STANDARD letters)` so every ordinary letter fills the cell height (98-100%); condense **horizontally
  only** when a glyph exceeds its cell; crop each glyph from `baseline-asc` to `baseline` (NOT its ink
  box) so a short letter like **י** keeps its natural raised position; paste on the cell bottom =
  shared baseline; V-flip. Descenders **ק ך ן (ף ץ)** use `DESC_KEEP=0.62` (cells end at the baseline,
  so a full tail would shrink the body); **ל**'s ascender is trimmed to 75% of its excess. ⚠️ The
  earlier bug was scaling EACH letter to fill its OWN cell (`min(capH/h, w/gw, h/gh)`) — that destroys
  relative proportions and is what made **י** render huge.
- **🔴🔴 TWO DEFECTS THAT ONLY A PHOTO OF THE SCREEN EXPOSED (fixed).** After the font matched, the
  user reported "noise around the letters" and "ו/ג/ק sit lower than the rest". My own atlas analysis
  said everything was clean — a phone photo of the monitor, cropped from the 16320×12240 original,
  showed the truth. Both fixes are universal to any bitmap-atlas font hijack:
  - **The noise = ATLAS FRINGE BLEED.** The engine samples slightly BEYOND the blob bbox and drags in
    the anti-aliased fringe of the neighbouring glyph — faint marks floating just above the letters
    (worst on ל and ע). Measured: **142 px of ink in a 3px ring around the Hebrew cells, and 0 px of
    it lies inside ANY glyph's bbox** — sub-threshold fringe in the gutter that no glyph rect reads.
    **FIX: erase the ring wherever the pixel is outside EVERY blob bbox** (`ring & ~inbox`) — provably
    damage-free, took the fringe to 0. ⚠️ The solid-block probe does NOT reveal this (a solid block
    hides a faint neighbour), so "the probe showed no frame" was not sufficient evidence.
  - **A per-letter `textbbox` ascent varies by 1–3 units**, which after the ~9× downscale becomes a
    visible 1px height difference — that is the "ו/ג/ק are shorter" report. **FIX: force ONE pixel
    ascent for every standard letter** (`GA_STD = round(median_std_asc * s)`) instead of each letter's
    own ascent; ל gets `GA_STD*lamed_ratio`, descenders `GA_STD` + tail. Verified in the atlas: every
    standard letter has ink top row **7**, bottom **37**, height **31** — zero variation; ל tops at
    row 2, ך/ן/ק bottom at 41. Also **rasterise at 4× the target, not ~10×** — the huge downscale
    warped diagonals (crooked צ).
- **Font choice (final): `lvnm.ttf` Levenim MT** — a clean Hebrew sans whose stroke weight matches the
  game's thin geometric Latin, aspect 0.88 so it needs no condensation, and ל is 36px vs 31px for the
  standard letters. Selected by measuring EVERY Hebrew font on the machine for aspect / lamed-ratio /
  ink-density against the cell geometry, not by eye.
- **⚠️ Three environment traps:** (a) `launch_cap` matched the window by TITLE and the **Antigravity
  IDE window title contains "Assassin's Creed II"**, so it foregrounded the IDE and screenshotted the
  desktop — match by **PID**. (b) Force-killing the game leaves **Uplay's `UplayWebCore.exe`/`upc.exe`**
  running, and that overlay swallows mouse clicks system-wide (the user lost the mouse twice) — always
  `taskkill` those + `ClipCursor(None)` after a run. (c) A menu string containing a character **not in
  the loc package's char dict** (`*`) produced a black screen — only use chars the package already has
  (112 printable ASCII), and round-trip the rebuilt loc before deploying.
- **Tools in `work/`:** `build_hebrew_final.py` (`--dry` layout plan, `--preview` renders the result
  WITHOUT launching the game, `--font X`), `verify_install.py` (reads the files back OUT of the game:
  every cell, every string, and that no glyph ink was destroyed), `check_heights.py`, `check_fringe.py`,
  `probe_cell_metrics.py`, `launch_cap.py`; rendered previews in `games/assassinscreed2/preview/`.
- **Remaining (not blockers for the render):** translate the rest of the menus (pause/options/extras),
  and move the carriers from base Latin A-Z to the accented cells so untranslated English drawn in
  ProLight stays readable — ⚠️ each accented cell's diacritic is a SEPARATE blob that must also be
  cleared, or it renders as a stray mark above the Hebrew letter. Note `SELECT`/HUD use a DIFFERENT
  atlas (ProMedium/ProBold), so they were unaffected. REVERT = copy `_HE_BACKUP\*.forge` back.

### AC2 TRANSLATION run — New-Era on 2 streams + /translate pool LIVE (2026-07-19)

Rendering accepted ("זהו, מושלם") → the font work was PARKED (the 4 follow-ups above +
[[ac2-translation-run]] — the user asked to be REMINDED) and the 2 free streams (**vm3 + desktop**)
were pointed at the translation.

- **Scope (measured from the forge, not guessed):** `LocalizationPackage_English` 4,458 entries
  (**4,403 translatable**) + `_English_Subtitles` 5,604 (**5,600**) = **10,003 lines / 664,947 EN
  chars** (median 18, p90 102, max 2,148).
- **🔑 AC2 is the richest New-Era case so far — NINE oracle languages.** The forge ships 26
  LocalizationPackages; every UI line exists in fr/it/es/de/pl/nl/da/no/sv at 100%, subtitles ~70%
  each → **avg 7.5 oracles/line**. Read by STRENGTH: **pl** = speaker AND addressee gender (past
  `-ł/-ła`), **it/es/fr** = referent gender + formal-vs-familiar, **de** = register,
  **nl/da/no/sv** = number. ⚠️ The Spanish resource is `Spanish(Spain)` for UI but plain `Spanish`
  for subtitles — one name map silently zeroed es coverage until fixed. Korean/Chinese subtitle
  packages fail to decode (different blob layout) — not needed.
- **Fleet `games/assassinscreed2/fleet/`:** `ac2_nim.py` (New-Era worker, 4 strongest refs,
  preserves `<br>`/`<font>`/`[A]` glyphs/`{CUT}`/printf, stores **LOGICAL** — the VISUAL bake is at
  BUILD), `build_slices.py` (stable md5 partition, **UI before subtitles + short before long** so
  the first-seen menus land first), `pull_ac2.sh` (scp → `banks/` → merge → `hebrew.json`, applying
  `name_registry.json` at **MERGE** time so a name correction never costs a re-translation),
  `selfheal_ac2*.ps1`, `ac2_progress.py` (gameId=`ac2`, sentences). Remote dir `C:\ac2w`.
- **⚠️ Scheduled-task pattern (several failed attempts):** `pythonw` on PATH, `/TR "'…pythonw.exe'
  script.py"`, and a `hidden.vbs` all **silently do nothing** on these VMs. The ONE that works is the
  fleet's: `schtasks /TR "powershell -NoProfile -ExecutionPolicy Bypass -File …\selfheal.ps1"
  /RU SYSTEM`, where the ps1 uses `Invoke-CimMethod Win32_Process Create` (anything launched over the
  SSH session dies with it). Added a **PID singleton lock** to the worker — without it the 5-minute
  task stacks duplicates on one slice.
- **⚠️ When surveying the fleet, match the ACTUAL script name** — a coarse "cp2077" pattern matched
  `cpqa_progress.py` (a progress REPORTER, not a worker) and I killed it. Same sweep found **Plague
  Tale finished yet still running on 4 boxes**, burning NIM quota → killed + tasks disabled.
- **✅ /translate pool LIVE — 10,062 rows, uploaded WITHOUT filtering (user: "לעלות בלי סינון").**
  `work/build_ct_strings.py` (10,003 categorized: ממשק ותפריטים 4,403 → כתוביות עלילה 5,600) +
  `work/build_ct_extra.py` (the 59 the corpus filter had dropped — `%d/%d`, `R.I.P.`, `1476`, `[X]`).
  `string_key` keeps the fleet's `ui:<id>` / `sub:<id>` so an approved line maps straight back onto
  the right package. Live: `total 10062 / open 9692 / had_existing 370`.
- **🔴🔴 CLOSING THE TAIL: the LAST 1% is never "more of the same" — classify it before touching it.**
  At 99.1% the fleet flatlined at **rate=0/h with 88 lines left**, which reads like a stall and is not.
  Splitting them by ONE rule — *is there a lowercase word left after the engine tokens are stripped*
  (`re.search(r'[a-z]{3,}', STRUCT.sub(' ', en))`) — separated them exactly: **62 non-translatable**
  (pure `{CUT}` cut-content, `[Left]/[Back]` buttons, `[SHARP PAIN]` cues, the Subject-16 **Atbash
  cipher**, `®`-brands, ALL-CAPS dev codes) vs **26 real dialogue**. The 62 got a verbatim
  passthrough (they MUST stay Latin — translating the cipher destroys an in-game puzzle); the 26 went
  back to the fleet. **A tail is a MIXTURE, and passing the whole thing through would have shipped 26
  English subtitle lines while "reaching 100%".**
- **🔴 A worker reads its park list ONCE, at startup — editing the file under a RUNNING worker is
  worse than useless.** Un-parking the 26 keys had no effect until the workers were restarted: the
  live process still held the old set in memory and would have **written it back over the edit** on
  its next save. Any park/skip/state file edited out-of-band requires a restart of every consumer
  (here: 3 provider workers × 2 machines, via `Start-ScheduledTask AC2Desktop` / `schtasks /run /tn
  AC2MP`). Verify by re-reading the file AFTER the restart, not before.
- **🔴🔴 A DETERMINISTICALLY-REPAIRABLE DEFECT MUST BE REPAIRED, NEVER STRUCK — the niqqud lesson, a
  second time (SILENT-FAILURE CLASS #5).** The model reliably translates a stage-cue bracket
  (`[Laughs]` → `[צוחק]`), which trips `token-mismatch`, and 3 strikes then PARK a perfectly good
  translation of the entire sentence. Fix = `_restore_bracket_tokens()` inside `normalize()` (which
  now takes `en`): positionally restore any bracket whose ENGLISH side is an engine token, **only
  when the bracket COUNT matches** so the mapping is unambiguous. Proven in-flight — `sub:218288`
  banked as `…אין לי את הכסף שלך! [Laughs]` on the first pass after the fix. Critically it does NOT
  mask real failures: a PROSE gloss (`[It's nothing!]`) stays Hebrew, and a **dropped** bracket still
  fails the guard. **UNIVERSAL: before letting a guard strike, ask whether the defect has exactly one
  correct mechanical answer — if it does, fixing it is not a translation decision.**
- **🔴 DO NOT "fix" a guard rule to unblock the tail — measure the CONVENTION the corpus already
  established.** The obvious move was to reclassify `[Laughs]`/`[Anyway]` as prose so they could be
  translated. Measuring first killed it: **all 15 banked lines containing `[Laugh]`/`[Laughs]`/
  `[Sigh]`/`[Gasp]`/`[Good]`/`[Sir]` keep them LATIN, 100% consistent** — and the regex genuinely
  cannot separate them from the real buttons `[Start]`/`[Back]`/`[Left]`/`[Right]`, which share the
  identical Capitalised-mixed-case shape (measured: `[Am]`×81, `[Bm]`×56, `[Start]`×7 vs `[Laughs]`×3,
  `[Anyway]`×1). Changing the rule would have made 2 lines inconsistent with 15. **The guard was
  right; the repair belonged one layer earlier.**
- **⚠️ Read a stuck line's rejection reason from the WORKER LOG, not by inference.** `REJECT
  sub:212305 [no-hebrew] en='jhfhf'` (a dev placeholder — correctly parked forever) and `step1 fail
  (HTTP Error 429) — skip batch` (blameless, retried) look identical from the outside as "0/h", and
  they need opposite responses. Single-line batches log `why_invalid` precisely for this.
- **🔴 THE GENDER-HINT LESSON (two false-positive rounds): do NOT auto-derive a gender guess from a
  reference language without a lexicon — attach the reference SENTENCE instead.** Round 1 read
  Romance articles (`una lancia` → "נקבה") — that marks the NOUN's gender, not the addressee's.
  Round 2 read Polish endings — `Forli` → "רבים" and `dół` → "זכר", because `-li`/`-ł` hit ordinary
  nouns too. A wrong hint is worse than none. The pool now ships the real **Italian** (the game is
  set in Italy) + **Polish** (speaker+addressee gender) sentence in `context`, and the only
  auto-derived hint left is **German register** (`Sie`/`du` — a genuinely closed pronoun set),
  1,051 lines. **UNIVERSAL: a morphological hint needs a closed set to be safe; open-class endings
  need the human to read the source line.**

### 🔴🔴 AC2 "6 streams but 1.6 lines/min" — 87% of the work was thrown away (2026-07-21)

The fleet looked healthy (6 provider-streams, all "alive", dashboard green) and produced almost
nothing for hours. **The parallelism was fine — the OUTPUT was being discarded and re-queued.**
Every rule below is universal to any fleet worker with a validation guard.

- **THE EVIDENCE THAT NAILED IT — the worker logs, not the dashboard.** Every batch printed
  `+0/N` with a FROZEN total (`[18/37] +0/3  total 1524/1622`). Counted over the desktop's three
  logs: **1,465 batches ran, only 186 (12.7%) banked a single line.** A dashboard that reports
  *processed* can never show this; the per-batch accept ratio is the health metric.
- **ROOT CAUSE 1 — `valid()` with no strike/park (the SM2 lesson, violated again).**
  `ac2_nim.py` had 5 rejection conditions and **zero** `strike`/`park`/`retry` logic, and `main()`
  rebuilt `todo` from *everything not banked* on every pass. So any line the guard cannot accept
  is re-served **forever**, to all 6 streams, crowding out real work. **Adding streams multiplies
  the wasted work, not the output.** Fix: 3 strikes → park to `ac2_skip_<provider>.json`
  (per-stream file is race-free because each key belongs to exactly one machine×provider slice
  via `md5 % 3`).
- **ROOT CAUSE 2 — 71 structurally UNWINNABLE lines.** Strings that are 100% engine tokens
  (`{CUT} {MAILS}`, `{CUT} {PRESS [B] to open.}`): translating the inner text changes the token
  multiset (guard 3), and returning them unchanged trips the copy-EN rule (guard 5, because `{`
  is not `[A-Z0-9]` so `is_namey` says no). **No output can ever pass.** They are now parked into
  a dedicated `token_only` list. **Do NOT "fix" this by banking the English** — that fakes a 100%
  and hides real untranslated text; park it honestly so a targeted pass can take it.
- **ROOT CAUSE 3 — silent id-drop.** 78 of the stuck lines are ones **no output could fail**
  (`RELEASE`, `BLACKSMITH`, `SANTO STEFANO`) — proof they were lost *before* the guard: the model
  omits ids from its JSON and `do_batch` skips them with no error and no strike. Fix: when a
  multi-line batch returns EMPTY, re-ask each line **singly** (highest hit-rate) before striking —
  pure recovered throughput — and wrap the batch in try/except so one bad batch can't kill the worker.
- **🔑 ANALYTICS THAT REPLACE GUESSING: classify the stuck set against the guard offline.** For
  each remaining line ask *does ANY output pass?* (all-token → no; copy-EN rejected → must produce
  Hebrew; else → anything passes). That split (71 / 583 / 78) told me exactly which mechanism was
  firing without a single API call, and proved 0 over-catch before deploying.

### 🔴 Four environment traps that made the diagnosis wrong before it was right

1. **`wmic ... where "commandline like '%x%'"` over ssh returns 0 matches when the quoting breaks
   — and a kill built on it silently kills nothing.** I "killed" vm3's workers, saw 0 processes,
   and concluded the VM was idle; in fact 3 old workers were still running and holding the
   singleton locks, so every relaunch exited instantly (task `Last Result: 1`). **Never trust a
   remote process filter that returns 0 — cross-check with a filter-free `tasklist` count first**
   (it said 3). The fix was to stop fighting ssh quoting and scp a small control script
   (`ac2_ctl.ps1 list|kill|ensure|restart`) that runs locally on each machine.
2. **PowerShell variable names are CASE-INSENSITIVE — `$STATE` (a path) and `$state` (a hashtable)
   are the SAME variable.** The data silently overwrote the path, `Set-Content $STATE` got a
   hashtable instead of a filename, and the watchdog's state file was never written — so stall
   detection could never fire, with no error anywhere. Keep path names lexically distinct from
   data names (`$StatePath`).
3. **`ssh` is NOT on PATH in a PowerShell/SYSTEM context** (only Git's, at
   `C:\Program Files\Git\usr\bin\ssh.exe`). A watchdog that shells out to `ssh` therefore reports
   every remote stream as **DOWN** — a false alarm that looks exactly like a real outage. Resolve
   the binary by absolute path with a candidate list.
4. **`count_streams()` counts BANK FILES, not live processes** — so the dashboard proudly showed
   "6 זרמים" while 3 of the 6 workers were dead. **A stream count derived from artifacts is a
   count of past work, not of current capacity.**

### ✅ The guard-dog layer that was missing (`ac2_watchdog.ps1`, task `AC2Watchdog`, 5 min, hidden)

The existing self-heal only asked *"is the process alive?"* — which is precisely why a fleet that
was alive-but-producing-nothing ran for hours unnoticed. The new watchdog judges a stream by its
**output**: it reads each worker's banked count from its log, compares with the previous tick, and
**distinguishes "banked nothing but still printing" (working) from "printed nothing at all"
(hung)** using the log's last line as a signature. Only a genuinely frozen stream is recycled, and
only after **3 ticks = 15 minutes of complete silence**, so a merely slow worker is never killed.
It also re-ensures 3 providers per machine (desktop locally, vm3 via the SYSTEM `AC2MP` task —
never over ssh, whose children die with the session), keeps the pusher alive, and writes
`ac2_watchdog_status.json`. **UNIVERSAL: a liveness probe and a productivity probe are different
instruments — ship both, and make the productivity one able to tell "busy" from "stuck".**

### Dashboard pushers — never publish a 0 from a failed read

All three pushers (`cpqa`/`ac2`/`w3qa`) computed `done` inside a `try` whose `except` set
`done = 0`, so a single failed read (file mid-write, or the disk being 100% full) published a
**0**, which poisoned the rate window and showed `0.0/min` for a healthy fleet. Fixed: keep the
last good value and re-publish it (`done = last_done`) — a stale number is honest, a zero is a lie.
Also added `meta.countUnit = "sentences"` so the site labels every one of these games in
**משפטים** (never "שורות"), with the phase-correct verb (QA = אומתו/קצב בקרה, translation =
תורגמו/קצב תרגום).

⚠️ **A 100%-full disk is a fleet-wide outage that presents as data glitches** — the merge can't
write, so counts jump to 0 and the dashboard flickers. Check free space before debugging a
"weird number" (C: was 0 GB of 3.7 TB this session).


