## Spider-Man 2 through the launcher — BLOCKED on Overstrike (2026-06-09)

Investigated wiring SM2 into the launcher like CP2077. **Not feasible as a
drop-in:** the SM2 Hebrew mod ships as two `.modular` files
(`hebrew_full.modular` ~2.5 MB + `hebrew_font_v7.modular` ~716 KB) that are
applied ONLY by **Overstrike** (a 3rd-party .NET GUI mod manager, no CLI) into
a separate "Mods Library" folder — NOT copied into the game folder like
CP2077's `archive/pc/mod/`. dat1lib (`games/spiderman2/tools/ALERT`) can
read/write DAT1 but has no end-user apply path. No Cloudflare Worker is deployed
for SM2 yet (the `hebrew-translation-hub/spiderman2-hebrew-mods` repo + `pack_and_release.py`
exist but no release pushed). The in-game language switch (Arabic-slot
TextLanguage DWORD) already works via `game_language.LANG_CONFIGS['spiderman2']`.
Realistic paths (pending user choice): (a) guided semi-auto — launcher
downloads + drops `.modular` into Mods Library, bundles/opens Overstrike, sets
the language, user clicks Apply once; (b) re-implement Overstrike's
toc-rewrite/DAT1 injection in Python (large, fragile to game patches); (c) keep
SM2 as a manual website download + the existing language switch.


## SM2 — "עידן חדש" line-by-line QA fleet PREPARED (2026-07-10, NOT run — awaiting the user's go)

Applied the **עידן חדש** doctrine ([[new-era-doctrine]] + `universal/NEW_ERA_LANGUAGE_ROLES.md`) to
SM2. SM2 is an already-translated game → **review-only, line-by-line, monotonic** (fix only real
errors, never degrade a good line). Built by copying the W3 reference
(`w3_lang_oracle`/`w3qa_nim`/`w3ut_nim`). **Prepared, deliberately NOT started.**

- **`games/spiderman2/fleet/`** — `sm2_extract_langs.py` + `extract/` (**11 shipped languages**
  pulled from the localization variants: `ar ru pl es esmx it fr pt de zh en`) · `sm2_build_corpus.py`
  → `corpus.json` (line-by-line, with `ag`/`num`/`formal` **baked** from the multi-language consensus)
  · `sm2qa_nim.py` (the review-only NIM worker: STRUCT-preserving for SM2's `<ts="a;b">` / `&rlm;` /
  `[TOKEN]` / `{VALUE}`, canonical-name aware, monotonic guard) · `README.md`.
- **SM2's Arabic is EGYPTIAN COLLOQUIAL and unvocalized → a MINORITY oracle here.** The MSA parser was
  extended with `إنتَ/إنتِ` + `إنتوا`; a colloquial `بت/هت…ي` 2nd-fem rule was tried and **removed after
  measuring it 482/551 WRONG** (weak-final verb roots `هتيجي`, object suffix `بترجعني`, possessive
  `بتاعي`) — see §15 trap #2. **Final corpus: 38,948 lines, 602 baked facts (f=88 · m=365 · pl=149),
  937 formal-traps — of which Arabic supplied 178 and the ru/pl/es/it consensus 424.** For SM2 the
  Slavic/Romance consensus, not Arabic, carries the gender signal.
- **Verified before the run:** 11/11 parser tests (incl. colloquial `إنتِ`→f, `بتعملي`→f, `أنتم`→pl),
  STRUCT guard rejects a fix that drops a `<ts>`/`&rlm;`/`[TOKEN]`, gender guard flips m→f only when
  `ag` confirms and rejects a →אתם that comes from a formal-you trap.
- **Known limitation (same as the W3 reference), stated to the user:** the guard hard-confirms
  **ADDRESSEE** gender only. A **SPEAKER**-gender fix (Hebrew `אני שומע`→`שומעת`, evidenced by Russian
  `я …-ла` / Polish `-łam`) is proposed by the LLM from the raw ru/pl but is NOT guard-confirmed, so it
  is conservatively rejected. Strengthening it = bake an `sg` fact and let the guard accept a flip
  matching `sg` — offered, not built.
- **Pending:** one corpus rebuild to apply the parser fix (was blocked on a transient Bash-classifier
  outage). Then: 5 streams like CP2077/W3, on the user's explicit go.


## SM2 native applier — GAME-UPDATE-AWARE (2026-06-25, local build)

The SM2 applier (`translation_manager/spiderman2_mod.py`) was made update-safe after the user
updated the game (FitGirl patch = graphics/perf only — FSR/DualSense/raytracing; touches NO
localization/text/font, so the Hebrew content stays compatible — but any patch **rewrites the
`toc`**, silently resetting the mod). Two bugs fixed: (1) `is_applied` was a bare manifest-file
check → false "installed" after an update while the game shows English; now it ALSO requires the
live `toc` `stat` (size+mtime) to equal the stat recorded at apply (stored in the manifest) → a
patch changes it → reports NOT applied → UI prompts a clean reinstall. (2) `apply`/`revert`
restored a PRE-update backup over the fresh `toc` → toc/archive mismatch → possible crash; now they
decide from the toc ITSELF via **`_toc_is_ours(t)`** (does it still reference our `tm_he_*`
archives?) — if yes the backup is valid (restore it), if no (game updated) **`_discard_stale` drops
the stale backup WITHOUT restoring** and re-applies on the current clean toc. Helpers +
logic self-tested; py_compile clean; built+installed LOCALLY (no publish). Universal rule now in
[[launcher-native-mod-and-gotchas]]: every native applier must verify the live file still matches
and never restore a backup older than a game update. **User guidance after a game update: just
re-Install in the launcher (or re-Apply in Overstrike) — nothing to re-download/translate.**


## Spider-Man 2 native applier — SHIPPED (2026-06-10)

The Overstrike blocker (above) is **resolved**: the launcher now applies the SM2
Hebrew mod itself, no Overstrike, by reproducing Overstrike's exact TOC
transformation in Python.

- **`translation_manager/spiderman2_mod.py`** (NEW) — the native applier.
  Reverse-engineered from the Overstrike C# source + `dat1lib` + the live
  `Game Lab/Marvel's Spider-Man 2/` (pristine `toc.BAK` vs Overstrike-modded
  `toc` + `d/mods/`). Mechanism, **validated byte-for-byte locally**:
  - The game's `toc` is I29/TOC2: `[u32 0x34E89035][u32 logical_len][raw DAT1
    '1TAD']` — UNCOMPRESSED. `dat1lib.read` parses it; with
    `RECALCULATE_ORIGINAL_ORDER` the inner DAT1 round-trips byte-identically
    (the ~3.6 KB tail is padding excluded by the length field).
  - `.stage`/`.modular` are ZIPs; each patched asset is an entry named
    `{span}/{UPPER_HEX_ID}` of raw DAT1 bytes (`.modular` nests `.stage`s under
    `modules/`).
  - apply(): write each asset's bytes as a RAW DAT1 file `d/mods/tm_he_<i>`,
    append a 66-byte RCRA ArchiveFileEntry naming it, and redirect the asset's
    `RcraSizeEntry` → {archive_index=new, offset=0, value=len}. Header unchanged
    (the engine prepends the 36-byte header from the headers section — exactly
    why `extract` returns len+36). dat1lib's stock `SizesSection`/`ArchivesSection`
    `.save()` emit the OLD MSMR layout, so we override them with correct RCRA
    serializers (`<IIIi>` / `filename[40]+<QQIHI>`) before refresh, then wrap
    the DAT1 ourselves (dat1lib's `toc2.save()` wrongly zlib-compresses).
  - Fully reversible: backs up the live `toc` → `toc.tm_he_backup` before the
    first write; `revert()` restores it + deletes our `d/mods/tm_he_*` + manifest
    (other mods stay intact — we only append + redirect).
- **`dat1lib` vendored** → `translation_manager/vendor/dat1lib` (1.9 MB pure
  Python; loaded as a TOP-LEVEL package via a sys.path entry — it uses absolute
  internal imports). Mod payloads bundled → `translation_manager/assets/spiderman2/`
  (`hebrew_full.modular` + `hebrew_font_v7.modular`). Both ride the existing
  `('translation_manager','translation_manager')` spec datas entry — no spec change.
- **RPCs** (`main_eel.py`): `get_spiderman2_mod_state` / `install_spiderman2_mod`
  (background worker → apply + `game_language.set_mode('hebrew')`, streams
  `mod_install_progress`) / `remove_spiderman2_mod` (revert + language→english).
  Pre-flight `game_mod.is_writable` guard. Bridge slots + `eel.ts`
  `SpiderMan2State` + a dedicated SM2 branch in `GameDetailPanel` (install /
  remove + progress), distinct from the CP2077 download-mod and legacy paths.
- **CAVEAT — in-game verification is the user's:** the applier is structurally
  byte-correct (23/23 assets redirect + extract correctly; revert restores the
  TOC byte-identically) and reproduces the Overstrike transformation already
  proven on this machine, but whether SM2 actually boots + renders Hebrew can
  only be confirmed by launching the game. Failure mode is graceful (missing
  asset → English fallback) and one-click revert restores the original TOC.


## SM2 Full Subtitle/Dialogue Translation — IN PROGRESS (2026-06-16)

Translating all 41,324 remaining SM2 entries (29,184 subtitles with `<ts>` + 12,140 dialogue/UI)
using **gemma-4-31b-it** via LM Studio. Scripts in `games/spiderman2/work/`:
`sm2_translate.py` (translator) + `sm2_progress.py` (site push) + `sm2_watchdog.py` (supervisor).

- Output files (these ARE the resumable state): `subtitles_he.json` (ts-tagged) +
  `dialogue_he.json` (plain). `10_build_patched_localization.py` loads both. Skip
  categories: credits (6,406), empty-EN, SFX-only. Done = `len(subs)+len(dial)`.

### LM reality — gemma-4-31b-it is RAM-spilled + slow (MEASURED 2026-06-16)
The model is **19.89 GB > 16 GB VRAM** → `DEVICE=Local` partial-GPU → **~1.1 tok/s
effective** (measured: prompt 1419 tok + 200 gen = 180 s). **MUST be served serial
`--parallel 1`** (concurrent requests on a RAM-spilled model just split throughput and
time out — same lesson as the CP2077 audit). After any reboot/drop, reload with:
`lms load gemma-4-31b-it -y --gpu max --context-length 8192 --parallel 1` (and first
clear the known ReadOnly flag: `attrib -R %USERPROFILE%\.lmstudio\.internal /S /D`).

**UPDATE 2026-06-17 — moved to a VRAM-fitting quant + SHARED parallel-2 with Watch Dogs 2.**
`MODEL` in `sm2_translate.py` is now **`gemma-4-31b-it@q2_k_xl`** (14.08 GB — fits ~16 GB VRAM,
near-zero spill, "maximum speed"). The same loaded model is **shared with a 2nd parallel run
(WD2 `wd2_ui_translate.py`)**, so LM Studio serves **`--parallel 2 --context-length 2048`** (NOT
the single-run `--parallel 1`). Accordingly `sm2_watchdog.py reload_lm()` no longer hardcodes
`--parallel 1`: a new `capture_lm_config()` reads the LIVE ctx/parallel from `lms ps` before each
reload and re-applies them, so a recovery never downgrades the shared slot (env override
`SM2_LM_PARALLEL`/`SM2_LM_CONTEXT`, default 2/2048). Reload now:
`lms load gemma-4-31b-it@q2_k_xl -y --gpu max --context-length 2048 --parallel 2`. ⚠️ Caveats:
(a) ctx 2048 ÷ 2 slots = 1024/slot → big multi-`<ts>` subtitle scenes may truncate (raise ctx if
seen); (b) q2_k_xl is a 2-bit quant — lower fidelity than IQ3/Q4, spot-check output; (c) the WD2
translator is NOT auto-launched by the SM2 watchdog — start it separately to actually get 2 runs.

**Stall fix 2026-06-19 — `validate()` was looping the queue on un-translatable entries.** SM2
froze at done=12603 (idle climbing, tr=up, lm=ok — NOT an LM hang; the LM was serving WD2 fine).
Root cause: entries that legitimately have NO Hebrew were REJECTED by `validate()` and re-queued
forever ("stays queued") with no park, blocking all progress: (1) social-media **handles** like
`purplepowah` / `lilMamasPancakes` (single lowercase token — failed the name/code guard); (2)
**markup-only** strings like `&lt; %s` / `&nbsp;<br>` ("lt"/"nbsp" inside the entity looked like a
word); (3) a q2_k_xl **2-bit hallucination** (Korean `U+B461`). Three fixes in `sm2_translate.py`:
(a) `validate()` now accepts no-Hebrew for a single-token **handle** (camelCase / has-digit /
len≥11); (b) `validate()` strips **html entities + tags** (`&[..];`, `<..>`) before the
real-word check so markup-only reads as empty → accepted; (c) NEW `park_failures()` — a persistent
**3-strike** counter (`sm2_translate_strikes.json`): any key that fails every attempt in a pass
strikes, and at 3 joins `sm2_translate_skip.json` so the queue can never loop on it again (the
build's Arabic/English fallback covers it). Verified: done resumed climbing 12603→12619+ (~390/hr),
WD2 unharmed. **Lesson (universal): a translator's `validate()` reject MUST be paired with a
strike/park, or any permanently-unfixable entry loops the queue forever and silently stalls the run.**
**Realistic throughput: dialogue ~12 s/entry; most subtitle keys are short single-`<ts>`
lines (token-budget packing → median ~13/batch, ~21 s/entry), only ~2% are huge multi-`<ts>`
scenes that go solo (~minutes each). Estimated full 41 k run ≈ 1.5-2 weeks.** A quant that FITS 16 GB VRAM
(full-GPU) would be ~5-15× faster — a quality/speed call for the user, not done unasked.

### Translator config (tuned for the slow model, `sm2_translate.py`)
- **Serial** `WORKERS=1`, `TIMEOUT=900`. **Shortened system prompt** (~400 vs ~1000 tok —
  the prompt is re-prefilled every batch; this was the dominant cost). All strict rules kept.
- **Type-aware batching**: dialogue `BATCH_DIAL=10` (short, amortizes prefill); **subtitles
  packed by ESTIMATED token budget** (`SUB_TOKEN_BUDGET=340`), NOT by count — because ONE
  subtitle key can be a whole multi-`<ts>` scene (hundreds of tokens). A huge scene lands in
  its own batch; `max_tokens` is sized per batch from the estimate (`est_out_tokens`, cap 1200).
  (Fixed-count subtitle batches truncated → only 1/4 emitted. Token-budget packing fixes it.)
- **Resilience**: `translate_batch_robust` retries the missing subset once, then a singleton
  fallback for stubborn long entries; misses stay queued (no entry lost). `flush_outputs` is
  **atomic** (temp+os.replace) so a watchdog kill never corrupts the JSON. `validate()` now
  ACCEPTS a no-Hebrew result when the source is a name/code ("Miles?", "F.E.A.S.T.") — avoids
  perpetual false-skip + wasted retries. **Skip-list** `sm2_translate_skip.json` (QA-parked
  keys) is excluded from the queue.

### Self-healing supervisor — `sm2_watchdog.py` (RUN THIS, it owns the stack)
Single thing to launch; brings up + babysits the whole run unattended for the multi-week haul.
**Launch under BASE python (not the venv stub — the venv `python.exe` is a redirector that
double-spawns and breaks the singleton):**
`Start-Process "C:\Users\...\Python313\python.exe" -ArgumentList '-u','sm2_watchdog.py' -WorkingDirectory <work> -WindowStyle Hidden`
- **LM monitor**: if gemma drops out of `lms ps`, auto-reloads it (attrib -R + `--parallel 1`)
  and restarts the translator to re-queue outage-skipped batches.
- **Translator/pusher**: launched detached + tracked by Popen handle (`.poll()` liveness, no
  fragile cmdline scan); relaunched on death; **hang-kick** if `done` is frozen > 1500 s
  (kill translator → reload LM → probe → relaunch).
- **Hourly structural QA** (`run_qa`/`qa_entry`): re-checks lines translated since the last tick
  for `<ts>`/`&rlm;`/`[TOKEN]`+`{VALUE}` placeholders/foreign-script/niqqud/untranslated-leak.
  Bad lines are REMOVED (atomic) so the translator re-does them; a key failing 3× is parked to
  the skip-list. Verified offline: all bad flagged, all good pass. State: `sm2_watchdog_state.json`
  + `sm2_watchdog_seen.json`. Logs: `c:\tmp\sm2_watchdog.log`.
- Singleton-guarded, crash-protected (loop never dies). Children are detached → survive a
  watchdog restart; a fresh watchdog clears orphans + relaunches.

### The 10-hour stall — TWO bugs found + fixed (2026-06-16) — do NOT regress
The run froze at exactly done=207 for ~10 h (12 watchdog stalls, all "reloading LM", zero
progress). Two independent bugs, both now fixed:
1. **Reload-while-busy + `unload MODEL` + a crash.** The watchdog reloaded the LM *while the
   hung translator still held the connection*, used `lms unload MODEL` (can't cleanly unload a
   busy/hung model), AND `reload_lm` threw every time (`r.stdout + r.stderr` when stdout was
   None → `NoneType + str`). So the hung runtime was never actually cleared. **Fix:** recovery
   now **kills the translator FIRST**, then `lms unload --all` → clear ReadOnly → load → an
   end-to-end **`lm_responsive()` probe** (a tiny request — `lms ps` says "loaded" even when
   hung; only a real generation proves health). A hung LM shows `STATUS=GENERATING` for many
   minutes with zero output — that's the signature.
2. **cp1255 stdout crash (the silent killer).** The watchdog launched the translator with
   Windows' default **cp1255** stdout; the translator's `[SKIP] … → …` line contains `→`
   (U+2192), which cp1255 can't encode → **`UnicodeEncodeError` killed the translator** the
   moment any batch had a skipped entry. On a *working* LM this fires immediately (the hung LM
   had masked it). **Fix:** every script does `sys.stdout.reconfigure(encoding="utf-8",
   errors="replace")` at startup AND the watchdog launches children with
   `env PYTHONIOENCODING=utf-8`. Belt-and-suspenders — never print-crash again.
Also: the translator now **flushes after every batch attempt** (done advances promptly →
stall window tightened to 1500 s), `validate()` accepts no-Hebrew when there's **no real
lowercase word** (codes/quantities like `5x[CURRENCY]`, `F.E.A.S.T.` pass through, not wasted
on retries), and the serial loop replaced the ThreadPoolExecutor. Verified: done 207→215+ once
both fixes landed. **If progress freezes again: check `lms ps` STATUS (GENERATING+frozen=hung)
and grep the translator log for `UnicodeEncodeError`.**

**Two MORE bugs found while it ran slow (2026-06-17) — fixed:** (3) the hourly QA's
"untranslated" check **falsely flagged character-NAME entries** (`BIO_HARRY_TITLE`="Harry",
"Lizard", "JJJ", "May" — names correctly kept Latin) → removed them → **killed the translator
every hour** to rewrite output → re-translated → re-flagged → infinite churn (throughput
~53/h instead of ~200/h). Fix: `qa_entry`'s untranslated check now uses the SAME name/code
guard as `validate()` (is-namey OR no real lowercase word). The skip-list had filled with ~31
false-parked names/codes — cleared it + reset strikes. (4) `sm2_watchdog.py` used `urllib` in
`lm_responsive()` without importing it → the post-reload probe always threw `name 'urllib' is
not defined`; the reload still ran (so recovery worked) but was unverified — added
`import urllib.request, urllib.error`. After both: clean batches of 10/10, ~200 dialogue
entries/h, QA quiet. **Lesson: any QA "untranslated/leak" check MUST share the translator's
name/code passthrough rule, or it churns on every proper-noun entry.**

### Progress on the site — `sm2_progress.py`
Standalone 60 s loop → upserts the `spiderman2` `progress_snapshots` row via
`POST /api/admin/progress` (`MONITOR_TOKEN` from root `.env`), `phase=translation`,
`processed=done`, `total=41324`, `meta.alive=true`, ai_model `gemma-4-31b-it`. The homepage
`pickActiveSnapshot` surfaces it (CP2077 snapshots are >2 h stale → filtered). The watchdog
keeps it alive. `python sm2_translate.py --status` for a CLI count.

**After translation completes** — rebuild + publish:
⚠️ **Run the WHOLE chain under the REPO `.venv` python** (`.venv\Scripts\python.exe`), NOT base
Python313 — base lacks `fontTools` (step 94) + `python-bidi` (step 91), and step 91 WITHOUT bidi
silently MANGLES entries (e.g. `&nbsp;`→`bsp;`). ⚠️ **Step `15_build_stage.py` is MANDATORY and was
missing from this list** — it converts the patched+fixed `arabic_patched_hebrew_menu.localization`
into `hebrew_main_menu_test.stage` (asset `BE55D94F171BF8DE` = localization_all). Step 80 PACKS that
stage but does NOT rebuild it; **skip 15 and step 80 ships a STALE localization stage** → the new
translations never reach the game (menus look right from a prior build, but the freshly-translated
subtitles render as the English fill-in). Hit + fixed 2026-06-20 (the whole 22,883-subtitle bake was
invisible in-game until 15 was run). Verify the modular actually grew + contains the new Hebrew
(`zipfile` grep a known new string) before deploying.
```
cd games/spiderman2/work   # use ..\..\.venv\Scripts\python.exe for every step
python 98_anchor_subtitle_punct.py  # RTL punct anchor: per-<ts> trailing &rlm; on subtitles_he/dialogue_he (idempotent; BEFORE 10)
python 10_build_patched_localization.py
python 91_match_arabic_structure.py
python 94_fix_font_controls.py
python 95_fix_percent_and_punct.py
python 96_fix_span_punct_numbers.py
python 97_fix_boxglyphs_and_numspans.py
python 15_build_stage.py            # ← MANDATORY: patched .localization → hebrew_main_menu_test.stage
# bump BUILD_VERSION in 80_build_css_rtl_mod.py (e.g. "19")
python 80_build_css_rtl_mod.py      # packs the stage from 15 + CSS into hebrew_full.modular
# deploy hebrew_full.modular to all 3 Mods Library locations + clear Overstrike Cache.json/Suits Cache.json
# in Overstrike: re-Apply (mod must show the new vN); then launch with TextLanguage=Arabic
# pack + publish as v1.0.0-beta.3
```

### SM2 full run COMPLETE + beta.3 PUBLISHED (2026-06-21)

After the user's in-game review of the 22,883-subtitle build ("שמות עדיין באנגלית; חלק מהסימנים
בצד הלא־נכון") the last polish landed and beta.3 shipped:

- **791 `NAME_SUBTITLE_*` speaker labels Hebraized** (240 unique — Sandman→סנדמן, Wraith→רייט',
  Dr. Connors→ד"ר קונורס, Civilian→אזרח…) via a deterministic name-map written into
  `dialogue_he.json` (loaded LAST → wins). **A Hebrew speaker label is what fixes the RTL colon
  side** (same rule as CP2077 pk=48683: a bare speaker-NAME entry MUST be Hebrew, NOT Latin V —
  the "V is Latin" rule is for V *inside prose* only).
- **36-key `sm2_translate_skip.json` tail closed:** **9 SFX captions** done deterministically
  (`CCAP_GEN_PETER*` gasps→מתנשף/growls→נוהם/laughs→צוחק/roars→שואג… — tooling, like CP2077
  vocalizations) + **12 real dialogue lines** DELEGATED to a Google/Antigravity agent (per
  [[delegate-all-translation]]) through `work/gemini_tail_input.json` (the `@@TSn@@` quote-free
  flow) → merged with **`work/tail_put.py`** (reattach real `<ts>` tags + structural validate →
  +10 `subtitles_he`, +2 `dialogue_he`). The remaining **16 keys correctly stay Latin** (markup
  `&nbsp;`/`&gt; %s`, social handles `purplepowah`, `TBR_*` dev codes) — NOT defects.
- **Rebuilt 10→91→94→95→96→97→15→80** under `.venv` (step 10 ~64 min; step 15 mandatory) →
  `hebrew_full.modular` 2,524,711 B; zipfile-grep confirmed names+SFX+dialogue inside → deployed
  to all 4 targets (3 Mods Libraries + bundled `translation_manager/assets/spiderman2/`).
- **Published `1.0.0-beta.3`** (same pattern as beta.2 — keep the FULL `v1.0.0-beta.1` tag as
  `releases/latest`, CLOBBER its assets; do NOT mint a beta.3 tag): `pack_and_release.py
  1.0.0-beta.3 --pack-only` (zip 3,243,271 B, sha `b1872de416c3b8c66205c113a6878ad4f6b5c50eda892d03d097d3ba481dbf45`)
  → `gh release upload v1.0.0-beta.1 --clobber manifest.json spiderman2_hebrew_ui.zip` →
  `publish_version.py spiderman2 1.0.0-beta.3 --stage beta --sha … --size … --archive-url
  …/v1.0.0-beta.1/…zip --apply`. **Verified consistent across all 4 surfaces** (Worker
  `/spiderman2-hebrew/manifest` / Supabase `games` / `mod_version_history` is_current /
  `download_url` HEAD 200 — same version+sha+size). 3 news suggestions pushed to admin.
- User just **re-Applies in Overstrike** (mod shows v19) to see it; the colon + names render
  correctly. Memory [[sm2-translation-run]].

### RTL sentence-final punctuation anchored (`?`/`!`/`.` flip) → beta.4 (2026-06-23)

User report: sentence-ending punctuation (esp. the **question mark `?`**) rendered on the
RIGHT (visual start) instead of the LEFT (RTL end). **Root cause (proven from the game's
own Arabic):** Hebrew uses the NEUTRAL `?` (U+003F); Arabic uses the STRONG-RTL `؟` (U+061F).
The engine anchors neutral terminal punctuation with a trailing `&rlm;` — measured over the
shipped Arabic: `.`=18,600 anchored, `!`=8,255, `،`=1,717, `--`=932, but **`؟`≈0** (it
needs none). The Gemini pass followed the Arabic per-key `rlm` flag, so it left Hebrew
`?`-endings UNanchored → they flipped. Fixes:
- **`universal/rtl_anchor.py`** (shared, self-tested) — `anchor_value(v)` adds a trailing
  `&rlm;` per `<ts>` segment whose visible text ends with neutral terminal punct
  (`. ! ? … : ; ,` or a `--`/dash run), idempotent, skips `<span>` (menu) values; `strip_rlm`.
- **`games/spiderman2/work/98_anchor_subtitle_punct.py`** — bakes it into `subtitles_he.json`
  + `dialogue_he.json` (backup `.bak_punct`). Applied: **19,049 entries anchored**
  (16,254 subtitles + 2,795 dialogue), verified **0 entries where non-`&rlm;` content changed**
  (only `&rlm;` added). Added to the build chain BEFORE step 10 (10 reads those files).
- **`universal/qa_review.py` hardened** so the resumable QA loop can never break the anchoring:
  new config `anchor_rtl_punct:true` (set in the SM2 `qa_review_config.json`) → `get` shows the
  agent CLEAN Hebrew (`strip_rlm`), `put` **re-anchors** the agent's fix (`anchor_value`) before
  validate+save. Verified end-to-end (display clean, `…?`→`…?&rlm;` on put).
- Rebuilt 98→10→…→15→80 (BUILD_VERSION **20**) → deploy 4 targets → publish **beta.4**.

### Leading-opener quote/paren anchor → beta.5 + names-translation tooling (2026-06-25)

Two user reports: (1) a sentence-initial **opening quote/paren** (`"`/`(`) flipped to the
visual LEFT and looked like a "stray extra quote"; (2) many **character names left in
English** in the prose — wants consistent canonical Hebrew + nicknames, saved to a registry.

- **Special-char fix (mine, deterministic, beta.5):** root-caused with **python-bidi (UBA
  simulation)** — under the LTR container base a segment-initial neutral opener resolves LTR
  → flips left; a **leading `&rlm;` before the opener** pulls it back to the RTL right
  (UBA-verified on the exact screenshot line + edge cases). Extended `universal/rtl_anchor.py`
  `anchor_value` to anchor BOTH ends per `<ts>` segment (leading opener `"“«(‘` — `[` excluded
  to avoid `[TOKEN]`/`[sound-cue]` brackets — + trailing punct). Mid-sentence quotes need no
  fix (verified). `qa_review.py`'s `anchor_rtl_punct` re-anchor covers it. Built 98→…→80
  (BUILD_VERSION **21**), modular has 127 anchored opening quotes + 381 opening parens.
  Published **beta.5** (sha `3d804a08…`, 4-surface consistent). **Insight:** Hebraizing the
  names ALSO cleans the bidi (fewer LTR islands) → the two fixes reinforce.
- **Names tooling (research DELEGATED to a Google agent per [[delegate-all-translation]]; PENDING):**
  scope = **7,989 prose entries** with a Latin token, **308 distinct** (Pete 557, Harry 730,
  Miles 588, Spider-Man 1222…). Built: candidate extraction + context; **`names_research.json`**
  (registry skeleton, 88 seeded canonical Hebrew + 214 blank for the agent); **`names_apply.py`**
  (SAFE deterministic applier — word-boundary, protects `<ts>`/`[TOKEN]`/`{VALUE}`, longest-first,
  drops the Hebrew-prefix maqaf before an inserted name `ו-Miles→ומיילס`; 6,951 entries change
  with the 88 seeds alone); **`NAMES_RESEARCH_HANDOFF.md`** + paste-ready agent instruction
  (research canonical Hebrew from Wikipedia, nicknames Pete→פיט, SKIP non-names, consistency).
  **NEXT:** user runs the Google agent to fill `names_research.json` → Claude runs
  `names_apply.py` → rebake → **beta.6**. Memory [[sm2-translation-run]], [[qa-review-handoff]].
- **Names filled by the Google agent + applied (2026-06-25, LOCAL build only — user said "don't
  publish until complete"):** agent filled 308/308 (247 Hebrew + 61 SKIP). Independently verified
  (per the GoWR lesson — never trust the agent's own check): 0 no-Hebrew/Latin/niqqud, person+place
  names canonical + CONSISTENT (Pete/פיט, Spider-Man/ספיידרמן, Watson/ווטסון), seeds preserved.
  Caught + fixed: `Web-Shooters→"יורי קורים"` (ambiguous with Yuri) → `משגרי קורים`. **KEY finding:
  the candidate list also caught COMMON-NOUN/ABILITY tokens embedded in compound proper names —
  replacing them standalone CORRUPTS the name** (`Time Twister→"זמן Twister"`, `Music Man→"מוזיקה
  Man"`, `Bird`[=Charlie Parker]→`ציפור`, `Right Field Rick→"Right שדה ריק"`). Fix: `names_apply.py`
  has a **`HOLD` set of 58 common-noun/ability/geographic-part tokens** that are NOT applied
  standalone (proper nouns stay applied). Result: **189 tokens applied, 7,019 entries changed, 0
  structural mismatches** over 41,309 (ts/token/spec preserved). Person names clean
  (`Aaron Davis→אהרון דייוויס`, `ו-Pete?→ופיט?`, `Dr. Connors→ד"ר קונורס` — title-period dropped);
  proper-noun-in-compound = acceptable partial (`Venom Smash→ונום Smash`, `Brooklyn Bridge→ברוקלין
  Bridge`). Rebuilt BUILD_VERSION **22**, deployed LOCAL.

### Names canon-VERIFIED vs Hebrew Wikipedia + place-compound phrases → beta.6 PUBLISHED (2026-06-25)

The agent-filled names were re-verified against authoritative sources (the user asked "did you
really check these are the real Hebrew names?"). A 6-agent web-research Workflow (serial, rate-limit-safe;
each agent did 6–20 WebSearch/WebFetch on he.wikipedia.org) audited the 53 canon-sensitive names:
**32 match, 9 acceptable-variant, 10 MISMATCH, 2 uncertain**. Key finding: the fill agent
**over-transliterated** — Hebrew Marvel canon *translates* some villains per each character's
established Hebrew name (NOT my inconsistency). Fixed all 10 in `names_research.json`:
`Lizard→הלטאה`, `Scorpion→העקרב`, `Vulture→הנשר`, `Hammerhead→ראש פטיש` (⚠️ canon but reads
literal — easily revertable), `Tombstone→טומסטון`, `Wraith→ווירת'`, `Raft→הרפסודה`,
`Felicia→פלישיה`, `Sandman→סאנדמן`, `Chinatown→צ'יינהטאון`, `Ganke→גנקי`. The 2 uncertain
(`Roxxon`, `Ravencroft`) have NO Hebrew source → kept transliteration (don't guess).
- **Place-compound gap CLOSED** — added a **`PHRASE_MAP` pre-pass to `names_apply.py`** (38 multi-word
  names, longest-first, runs BEFORE the single-token pass): `Black Cat→החתולה השחורה`,
  `Mr. Negative→מיסטר נגטיב`, `Financial District→הרובע הפיננסי`, `Coney Island→קוני איילנד`,
  `Central Park→סנטרל פארק`, `Times Square→כיכר טיימס`, `Brooklyn Bridge→גשר ברוקלין`,
  `Oscorp Tower→מגדל אוסקורפ`, `Upper East/West Side`, `Brooklyn Visions Academy→אקדמיית ברוקלין ויז'נס`,
  etc. — kills the Hebrew+English hybrids ("קוני Island"). **Gameplay/ability compounds** (Web Wings,
  Symbiote Surge, Hunter Base…) left English by design (separate editorial pass; the `HOLD` set still
  protects bare tokens). Re-applied from the clean `.bak_names2` baseline (not the names-applied spine —
  English tokens must still be present): **7,090 entries changed, 0 structural mismatches / 41,309, 0
  niqqud, 0 foreign**.
- Rebuilt BUILD_VERSION **23** (step 10 ran ~93 min under machine load) → deployed to all 5 LOCAL
  targets → **PUBLISHED `1.0.0-beta.6`** (same pattern: `pack_and_release.py 1.0.0-beta.6 --pack-only`
  → `gh release upload v1.0.0-beta.1 --clobber manifest.json spiderman2_hebrew_ui.zip` →
  `publish_version.py spiderman2 1.0.0-beta.6 --stage beta --sha ca1d3995… --size 3246959 --apply`).
  Verified 4-surface consistent: Worker `/spiderman2-hebrew/manifest` = `1.0.0-beta.6` sha `ca1d3995…`,
  GitHub download 302→asset, Supabase games + mod_version_history synced. 2 news drafts pushed
  (canonical names + RTL punctuation). **Verification artifact:** the 6-agent audit result is in the
  workflow task output (10 mismatch rows with he.wikipedia URLs). Memory [[sm2-translation-run]].


## SM2 Hebrew QA — v18 SHIPPED + published as beta.2 (2026-06-16)

**313 translation fixes** applied to the SM2 Hebrew mod via exhaustive multi-agent LQA (126 chunks × ~52 entries each = all 6,536 translated keys reviewed). Pipeline: deterministic scan → multi-agent review → structural guard → apply → rebuild → publish.

- **6 niqqud violations** stripped (COMM_NAME_WRAI, TRICK_LEFT_DOWN, HUD_ENM_HEALTHBAR_WRAITH, HELP/TUT_WRAITH_TAKEDOWN, ITEM_PHOTO_BIKEACCIDENT_DESC).
- **277 AI-flagged fixes** applied from 104 reviewed chunks (guard blocked 6 structurally-dangerous fixes — correct). Key fixes: drone→רחפן consistency, Venom→ונום (was "ארסי"), Octuple→מתומן (was "משומן"), Distract Police→הסח דעת המשטרה, Squint→מפזל, knocks back→הודף.
- **36 more fixes** from the final 22 chunks: Hunter Drones=רחפני הצייד, Fidelity mode=נאמנות חזותית, subtitle settings terminology (כתוביות/גודל/צבע/רקע/דובר), Off with markers=כבוי עם סמנים, Friendly Neighborhood=שכונה ידידותית.
- Build chain: 10→91→94→95→96→97→80 (BUILD_VERSION="18"). Deployed to all 3 locations (Game Lab Mods Library, Downloads Overstrike Mods Library, `translation_manager/assets/spiderman2/`). Overstrike Cache.json + Suits Cache.json cleared.
- **Published**: GitHub `v1.0.0-beta.1` release asset clobbered (3.2MB zip, sha256 `06ee0afe…`). Supabase updated to `v1.0.0-beta.2` beta via `publish_version.py`. Worker serves latest via `releases/latest`.
- **Structural guard** (`qa_v17_apply.py`): checks [TOKEN] sets, span/br/rlm/nbsp counts, printf spec multisets — 0 structural regressions possible.


## SM2 Hebrew RTL/font/percent/QA — v17 SHIPPED + published (2026-06-15)

A long deep-fix session on the **on-screen rendering** of the SM2 Hebrew mod
(menus + subtitles + descriptions). The translation data was already good; the
defects were all RTL/bidi, font-glyph, and printf-percent rendering bugs plus a
final exhaustive translation QA pass. End state: **mod build `v17`**, deployed
locally AND published to GitHub — the website download serves it.

### The rendering engine — cohtml (Coherent GameFace)
- **cohtml ignores CSS `direction`/`dir`.** It honors **Unicode bidi CONTROL
  chars** only. The RTL base comes from the UI **container**, not the content.
  See memory [[cohtml-rtl-bidi]].
- **THE tofu-box root cause (font, not data).** cohtml draws a stray bidi-control
  char using the **active font's glyph**. The **Heebo** subset shipped a VISIBLE
  4-contour glyph for **U+200F (RLM)/U+200E (LRM)** (advance 0 but real contours
  → a visible mark/symbol at the end of lines) and **lacked U+202B/U+202C
  entirely** (→ `.notdef` box). The game's native Arabic font (AzbukaPro) keeps
  these as **empty zero-width** glyphs. → Fix = **empty Heebo's U+200F/U+200E
  glyphs** + keep Arabic-matched `&rlm;` anchors (never use RLE/PDF U+202B/U+202C).
- **Arabic is the ground truth.** The shipped `arabic.json` uses **zero RLE/PDF**;
  it relies on natural container RTL + strategic `&rlm;` (e.g. trailing after a
  period, before certain spans). Our HE markup skeleton matches the AR skeleton
  ~99.98%, key-by-key.
- **printf vs display percent (per-key).** The engine **printf-formats SOME**
  strings (value labels: `SETTING_GAMESPEED_100`="100%%", `UI_PERCENT`="%d%%",
  perk descs with "%%110") and **displays OTHERS raw**. printf strings need the
  literal `%` **doubled** (`%%`); display strings need a **single** `%`. The
  Arabic encodes this per-key: **if `arabic.json[key]` contains `%%` → it is a
  printf string.** Collapsing `%%`→`%` on a printf key produces in-game garbage
  ("100□יל" — the engine consumes the lone `%` as a format spec and shifts bytes).

### Build chain (all under `games/spiderman2/work/`, run in order)
1. **`10_build_patched_localization.py`** — the spine builder. Extract Arabic
   slot variant_18 → fill untranslated from English base (variant_00) → apply
   Hebrew `menus*_he.json`+`settings_he.json` patches → **FINAL Arabic-gated
   percent + box-glyph normalize pass** (runs AFTER the Hebrew patches — earlier
   bug: it ran before and only fixed the English base). The gate:
   `_double_pct(s)` if `'%%' in arabic[key]` else `s.replace('%%','%')`; `_BOX`
   maps `؟→?`, `،→,`, drops `U+FFFC`. Serialize → `.localization`.
2. **`91_match_arabic_structure.py`** — transplants Arabic's exact `&rlm;` anchor
   positions onto the Hebrew prose, **drops RLE/PDF**, and **PRESERVES Hebrew
   spacing** (`OURS.sub('', h)` keeps spaces; only grafts AR_LEAD/AR_TAIL `&rlm;`).
   (Earlier bug: it copied Arabic's spacing and corrupted Hebrew ל/ב/מ prefixes.)
3. **`94_fix_font_controls.py`** — empties Heebo's U+200F/U+200E glyphs
   (numberOfContours=0, width 0) in Heebo-Regular/Medium/Bold/Black.ttf (backs up
   to `.bak94`). `71_build` embeds the patched TTF as-is.
4. **`95`/`96`/`97`/`98`** — surgical Hebrew fixers (percent+trailing-`&rlm;`;
   subtitle trailing-punct-to-span-START Arabic-style "!אני בדרך"; box-glyph +
   number-span match; **`98_apply_qa_fixes.py`** applies the QA workflow's
   verified fixes with a `[TOKEN]`/`<span>`-loss safety guard).
5. **`80_build_css_rtl_mod.py`** — `BUILD_VERSION = "17"` → builds the combined
   `hebrew_full.modular`, info.json name `"Hebrew Translation v17 (menu + RTL CSS)"`.
   **Bump `BUILD_VERSION` every rebuild** so Overstrike's mod list shows the new
   build. The in-game text carries NO version stamp (per user) — version lives
   ONLY in the Overstrike mod name.

### 🔴🔴 Overstrike's "'toc' has changed — update toc.BAK?" is a BACKUP-POISONING PROMPT (2026-07-27)
**Two appliers own the same `toc`** — Overstrike (GUI, baseline `toc.BAK`) and this project's own
native applier `spiderman2_mod.py` (writes `d/mods/tm_he_*` + backs up `toc.tm_he_backup`). Whenever
the launcher applied last, Overstrike opens with *"It seems your 'toc' has changed! Do you want to
update 'toc.BAK' with it?"* — **and clicking "Yes" writes the MODDED toc over the only vanilla
backup, permanently.** Both offered answers were wrong here:
| answer | effect |
|---|---|
| **Yes** | `toc.BAK` ← the launcher-modded toc ⇒ vanilla lost forever |
| **No** | keeps a `toc.BAK` from **before the game update** ⇒ Overstrike rebuilds on a 1.130 index over 1.131 data |
**Decide from the BYTES, never from the dialog**: a modded toc still contains its archive-name
strings — `open("toc","rb").read().count(b"tm_he")` was **23** on the live toc and **0** on both
backups, which named the culprit in one line. Sizes + mtimes then pinned which backup is the CURRENT
vanilla (`toc.tm_he_backup` 51,309,060 @ the game-update timestamp = true 1.131; `toc.BAK`
51,306,504 @ Jan-2025 = stale 1.130).
**The fix is neither button — close the dialog and repair the baseline:** keep the old vanilla under
a new name (`toc.BAK.v1130`), copy the TRUE current vanilla over BOTH `toc` and `toc.BAK`, and park
the other applier's `d/mods/tm_he_*` + `.tm_he_manifest.json` (moving the manifest also makes
`spiderman2_mod.is_applied` correctly report False). With `toc == toc.BAK` the prompt cannot fire.
**UNIVERSAL: when two independent appliers back up the same file, each one's "has it changed?" check
sees the OTHER's output as the user's own edit — so any prompt offering to refresh a pristine backup
must be answered from file evidence, and a game update makes an existing backup STALE even when it
is genuinely unmodded** ([[game-update-makes-backups-stale]]).

### Deploy gotcha — TWO Mods Libraries → CONSOLIDATED (2026-07-27)
Overstrike scans the `Mods Library/` folder **next to its own exe**, and the machine used to
have two (a `Downloads` extraction + the game folder's). That ambiguity is gone: **Overstrike
now lives IN the game folder** (`Game Lab\Marvel's Spider-Man 2\`, upgraded in place to
**1.7.4.0**), so its library IS `…\Marvel's Spider-Man 2\Mods Library\` and the deploy has
**3** targets, not 4 (that library + `translation_manager/assets/spiderman2/` + the launcher
cache `~/.translation_manager/mod_cache/spiderman2/`). The Downloads staging copies were
removed; rollback = `_overstrike_backup_1.7.3/` in the game folder (+ the installer zip).
The active profile is `Profiles/02.json` (`"path"` → the game folder, all 3 mods enabled) —
read it to confirm which install Overstrike really drives instead of guessing.
After any rebuild: run the deploy, delete `Cache.json` + `"Suits Cache.json"`, re-Apply.
⚠️ **An Overstrike UPGRADE must never touch `Profiles/` or `Mods Library/`** — copy only the
7 shipped files (`Overstrike.exe`, `Check for updates.exe`, `scripts_proxy.dll`,
`libdeflate.dll`, + the 3 docs); a fresh extract ships an EMPTY `Profiles/`, so replacing the
whole folder would wipe the game path and the enabled-mods list.

### Translation QA (this session)
**100 corrections applied**: 77 from a multi-agent adversarial-verify Workflow
(review→verify pipeline) via `98_apply_qa_fixes.py` (token-safe) + 23 Talon-faction
fixes (`מלתעה`/fang → `טלון`; unified "drone" → `רחפן`). The remaining
`english_in_hebrew` items are intentional brand/acronym pass-throughs.

### Publish status (content-verified)
- GitHub release on `hebrew-translation-hub/spiderman2-hebrew-mods`, tag **`v1.0.0-beta.1`**
  (FULL release so `releases/latest` resolves; semver beta scheme). The repo was
  made **public** so the website download works.
- The release asset (`spiderman2_hebrew_ui.zip`, served by the website's
  `releases/latest/download/` URL) was **byte-content-verified == local v17**:
  contains `"Hebrew Translation v17"`, the game-speed `%%` fix (`100%%` present,
  GAMESPEED single-`%` NOT broken), and the translation fixes (`בית הקברות`).
- **Caveat — version LABEL is separate.** The website's DISPLAYED version (Supabase
  `games` row, e.g. "בטא — ממשק") is a different field from the downloadable file's
  internal `v17` build number; the download is current even if the label reads
  older. To bump the shown label/changelog: PATCH `games?id=eq.spiderman2` +
  `mod_version_history` (service key in `website/.env`) — see the CP2077 sync rule.

### 🔴🔴 SM2 PC-settings pages are LTR-BASE — root-caused + fixed with an RLE embedding (2026-07-26)

User report on v2.629: in the PC display/graphics settings, **mixed Hebrew+Latin lines came out
in reverse word order** (stored `טכנולוגיית NVIDIA Reflex לתגובה מהירה` → shown
`לתגובה מהירה NVIDIA Reflex טכנולוגיית`) and **sentence-final periods sat on the wrong side**.
Root-caused by reading the vanilla UI JS (asset `B40AFA7568AA4412`, extracted from the pristine
`toc.tm_he_backup`), and the answer is in Insomniac's own code:

- Under `langIsRightToLeft` the game sets **ONLY** `--languageNormalAlignment` /
  `--languageOppositeAlignment` (text **ALIGNMENT**) and a `cohinline` attribute on two CSS
  classes. **It NEVER sets `direction` or `dir` anywhere in the document.** Their own comment:
  *"TODO: These css classes may not catch everything, do we need a specific class to query?"*
- ⇒ the PC-settings pages keep an **LTR paragraph base**, and the UBA lays `H1 <latin> H2` out
  left-to-right as `H1|latin|H2` — which a Hebrew reader scanning right-to-left sees as
  `H2 latin H1`. A sentence-final `.` is a NEUTRAL and resolves to the LTR end = the wrong side.
- **The `setAttribute('dir','rtl')` in `css_rtl_patches.json` was a NO-OP** — per this project's
  own §8a finding, **cohtml ignores CSS `direction`/`dir` and honours ONLY Unicode bidi controls.**

**THE FIX (root, two layers) — force an RTL base with an EMBEDDING:**
1. **`94_fix_font_controls.py`** now **ADDS** `U+202A–202E` (LRE/RLE/PDF/LRO/RLO) to all four
   Heebo TTFs as **empty, zero-width, cmap-mapped** glyphs — the same treatment RLM/LRM already
   got. This **lifts the long-standing RLE/PDF ban**: they were forbidden only because Heebo had
   no glyph for them and drew `.notdef` boxes. Backup is now non-clobbering, and the script
   **asserts** every control ends up `contours=0, width=0` (or exits). The font ships in the
   SEPARATE `hebrew_font_v7.modular` → **`71_build_heebo_font_mod.py` must be re-run and the font
   mod re-applied**, or the controls render as boxes.
2. **`10_build_patched_localization.py`** wraps each line in **RLE…PDF** for the cohtml PC
   families (`PCDISPLAYSETTINGS_` / `PCGRAPHICSSETTINGS_` / `PCWARNING_` / `PC_`, minus the two
   pre-launch NATIVE popups) — **269 strings**. Text stays in clean **LOGICAL** order.

**Why the embedding beats reordering the text** (the alternative I prototyped and rejected):
a run-order reversal has to guess how the UBA groups runs, and it **breaks `60 FPS` → `FPS 60`**
(adjacent Latin+digit runs separated by a space must stay one LTR unit), plus every `{TOKEN}`
becomes a hazard. The embedding changes **zero** words — verified offline: strip the two controls
and the string is **byte-identical** to the input. It is idempotent, and it wraps each
`<br>`-separated segment on its own (an embedding must not span a line break).

**⚠️ The one-build lag that made this hard to see:** steps 91/94/95/96/97 edit the JSON/TTFs and
run *after* step 10, so their effect only lands on the **NEXT** build. Never judge a fix by the
build that introduced it.

**⚠️ Two of my own hacks were the cause of a regression here and were REMOVED:** a `NATIVE_LTR`
dict that reordered a few labels Latin-first (correct for the pre-launch native dialog, **wrong**
for the in-game menu, which shares the same keys) and a broad `_NATIVE_PREFIXES` `&rlm;` strip
that deleted the anchor from **56 in-game strings** — that strip is exactly what put the
sentence-final periods on the wrong side. Only the two explicit native-popup keys are stripped
now (those widgets render HTML entities literally, so `&rlm;` would show as `.rlm;`).
The surviving `&rlm;` anchors are kept as a harmless fallback: inside an RTL embedding they are
a no-op, but if the embedding ever fails they still pin the trailing punctuation.

**UNIVERSAL:** when a bidi engine ignores CSS, read the vendor's own RTL code path before
theorising — the bug is usually that it sets *alignment* and never *direction*. And prefer an
**embedding** (which forces the base and preserves logical order) over any hand-rolled visual
reordering, which silently corrupts number+unit pairs and tokens. See [[force-rtl-base-rle]].

**🔴🔴 THE TEXT MOD AND THE FONT MOD ARE NOW COUPLED — ship them together or the UI breaks.**
The RLE-wrapped text is only invisible because `hebrew_font_v7.modular` carries the new empty
`U+202B/202C` glyphs. **`hebrew_full.modular` (new) + `hebrew_font_v7.modular` (old) = a visible
box before and after EVERY PC-settings string.** Right after the rebuild the new font existed in
only 2 of 6 locations — the stale ones included **`translation_manager/assets/spiderman2/`** (the
asset the LAUNCHER installs) and `~/.translation_manager/mod_cache/spiderman2/`. **Every deploy
must now sync BOTH modulars to all targets** (`C:\tmp\sm2_deploy_v25.sh`).
Size is the quick tell — new font `717,172 B` vs old `716,532 B`.
**UNIVERSAL: the moment a text build starts depending on a glyph, the font stops being an
independent artifact — treat the pair as one release unit and verify both versions at every
deploy target before shipping.**

### 🔴 CLIPPED LABELS — measure the RENDERED WIDTH, and take the budget from the widest English (v26, 2026-07-27)
With the order fixed, the next report was *"הכתב נחתך כי הוא ארוך מדי"*. **Character count is the
wrong instrument**: `PCDISPLAYSETTINGS_FSRFRAMEGEN` was 31 chars vs the English 34 — *shorter* — and
still clipped, while `NVIDIAREFLEX` at 37 vs 25 chars was **1.39× the English WIDTH**. Measure the
real thing: after the font swap **both scripts render in Heebo**, so summing `hmtx` advances over
the string in `extracted/_heebo/Heebo-Regular.ttf` gives a directly comparable em width for EN and HE.
- **The budget is the widest ENGLISH string the control already ships** — that is what the designer
  sized it for. Derived from the data: label surface **12.4em** (`Dynamic Resolution Scaling`),
  `_UPPERCASE` surface **16.1em** (`RAY-TRACED AMBIENT OCCLUSION`). Ranking every Hebrew label by
  absolute width against that budget found exactly **2 over** out of 94 — no guessing which to touch.
- **When the ENGLISH itself is over-wide, faithfulness is not the goal.** `FSR {FSR_VERSION} Frame
  Generation` is **17.2em — the widest string in the entire surface** and it clips in vanilla too.
- **🔑 `{FSR_VERSION}` is a DEAD TOKEN in this build — remove it.** It appears **nowhere** in
  `Spider-Man2.exe`, `cohtml.WindowsDesktop.dll` or `RenoirCore.WindowsDesktop.dll`, and it rendered
  literally **before** the RLE build (so the embedding is not the cause). Dropping it fixed the braces
  AND the width in one edit: **15.0em → 7.8em**, matching its DLSS sibling (`DLSS יצירת פריימים`
  8.4em). Also cleaned the two untranslated siblings that fall back to English and would show braces
  in the upscaling dropdown (`PCDISPLAYSETTINGS_FSR` → `FSR`, `_FSRAA` → `FSR AA`).
- Reflex: `טכנולוגיית NVIDIA Reflex לתגובה מהירה` (16.7em) → **`NVIDIA Reflex השהיה נמוכה` (12.0em)** —
  same noun-pile as the English, just under its 12.1em, and `השהיה` already matches the term the
  description uses for *latency*.
- **⚠️ Apply a value fix to EVERY file that holds the key, never just the merge winner.** These keys
  live in 2-3 spine files each (`settings_he` / `menus9_he` / `menus12_he` / `dialogue_he`) and the
  LAST file wins — a one-file edit is silently overridden. `_UPPERCASE` is **stored explicitly** in
  `dialogue_he.json` here, so it needs its own edit (uppercase Latin is wider: 12.7em vs 12.0em).
- **⚠️ Verify a grep's METHODOLOGY before trusting its negative.** `d/userinterface` returned 0 for
  `FSR_VERSION` — but also 0 for `DLSS`/`NVIDIA`/`PCDISPLAYSETTINGS` while finding `function` ×487,
  i.e. the settings JS is compressed and the scan was **inconclusive**. The decisive evidence was
  behavioural (literal braces predate the RLE build), not the grep.
**UNIVERSAL: for any fixed-width UI control, the translation budget is the rendered width of the
longest string the vendor already ships in that control — compute it from the font, rank every
candidate against it, and fix only what is over. A char-count check both misses real clipping and
flags strings that are fine.**

### Hard-won rules (do not regress)
- A **standalone speaker-NAME** entry must stay native Hebrew so RTL colon renders
  correctly; "protagonist name is Latin V" applies ONLY to V **inside prose**
  (same rule as CP2077 pk=48683).
- **Never** introduce RLE/PDF (U+202B/U+202C) — Heebo lacks them → box. Use only
  `&rlm;` matched to Arabic positions, with the emptied U+200F/U+200E font glyphs.
- The percent gate is **Arabic-driven, per-key** — do NOT blanket-collapse or
  blanket-double `%`.
- Run `94_fix_font_controls.py` after any font re-extract; the empty-glyph patch
  is the linchpin of the whole RTL fix.


