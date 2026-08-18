## 🖼️ Game-card cover images stuck black + library page frozen — the growing catalog exposed a latent skeleton-shimmer perf issue (2026-08-14, LOCAL build DEV_BUILD 238, BUILD_ID `20260813215433`, NOT published)

User report right after the four-game catalog growth above (screenshot): most game cards in
"משחקים" → "מותקנים ללא תרגום" / "לא נמצאו במחשב" rendered as **blank/near-black boxes with no
cover art**, and the page felt **stuck — couldn't scroll**
("רוב הפעמיים הוא לא טוען את התמונות ואיא אפשר לגלול שהוא תקוע ככה").

- **Ruled out first, by direct code read (no fix needed — each was already correct):**
  the documented [[cached-image-onload-race]] fix was already present verbatim in BOTH
  `GameCard.tsx` and `SmartImage.tsx` (a `useEffect` checking `el.complete && el.naturalWidth>0`
  synchronously after mount/src-change — a cache-HIT can never strand the fade-in). The GSAP
  `useFlipGrid` animation only fires on explicit `[sortMode,viewMode,cardSize,listCols]` user
  actions, never on `games` array updates. `LibraryView`'s scroll container
  (`h-full overflow-y-auto`) and the app shell's flex/`overflow-hidden` chain are CSS-spec-sound.
  No global wheel/scroll-blocking handler exists in `spatialNav.ts`/`ripple.ts`. `usePersisted`/
  `cardSize.ts` have no degenerate-value or re-render-loop bug. `tailwind.config.js`'s `fade-in`
  keyframe is one-shot, not `infinite`. `getModUpdates()` in `App.tsx` is async/non-blocking and
  hard-capped.
- **🔴 THE MECHANISM (converged from this project's own documented perf history, not newly
  discovered): `data-backdrop="glass"` is the DEFAULT on this strong-tier host**
  (`themePrefs.autoBackdrop() = _weakHost() ? "none" : "glass"`), meaning `main.glass` runs an
  ACTIVE `backdrop-filter: blur(18px)` over the whole content pane — and under this launcher's
  standing `--disable-gpu-compositing` Chromium flag every `backdrop-filter` is **CPU-rasterized
  per paint** (already the documented root cause of an earlier FPS regression in this file).
  `.skeleton::after`'s shimmer (`transform: translateX`) ran `infinite` — and with a **46-game
  catalog** (the four new games added this same session), a slow/stuck cover fetch could leave
  DOZENS of these repainting forever, simultaneously, inside the blurred region — plausibly
  enough sustained CPU/paint pressure to both (a) keep the near-black skeleton visually "stuck"
  and (b) make scrolling feel frozen. This scales DIRECTLY with catalog size, which is exactly
  why it surfaced now and not before.
- **Fix — two safe, symptom-targeted changes, zero regression risk on normal fast loads
  (both only ever engage once a load is already slow/stuck):**
  1. **`GameCard.tsx` + `SmartImage.tsx`** — a new `useEffect` per component: if neither
     `onLoad` nor `onError` has fired within **12 seconds**, force `setImgError(true)` (falls
     back to the card's own themed gradient background instead of shimmering forever).
  2. **`index.css` `.skeleton::after`** — `animation: skeleton-sweep 1.4s ease-in-out infinite`
     → **`… 5`** (bounded to 5 cycles, ~7s). With no `animation-fill-mode`, the element settles
     at its off-screen `translateX(-100%)` transform after the 5th cycle — a static box, zero
     ongoing repaint — instead of animating for however long a slow/stuck fetch actually takes.
- **Verified:** `npx tsc -b` clean (no TS errors). Full local build+install:
  `& '.\build_exe.bat'` (BUILD_ID `20260813212621`→**`20260813215433`**, DEV_BUILD 237→**238**,
  `=== BUILD SUCCESS ===`, dist exe mtime confirmed fresh) → ISCC (`Successful compile`, only the
  2 pre-existing benign warnings) → `Output\TranslationManager-Setup-1.2.0.exe` (fresh mtime) →
  launched via `Start-Process` for the user's UAC/click-through. **Not yet confirmed by the user
  whether this resolves the reported symptom** — awaiting their re-test on the new install.
  **NOT published** — local build only, per the standing rule; ship to other users only on an
  explicit "פרסם".
- **Separate, unrelated, low-priority item noticed while reading the real launcher log**
  (`C:\Users\Nehoray_Cohen\.translation_manager\launcher.log` — NOT the sandboxed
  `$env:USERPROFILE` path per [[env-redirection-real-home]]): a benign warning fires on EVERY
  boot across many recent builds —
  `translation_manager.game_language: FOLDERID_Profile lookup failed - argument 1: TypeError:
  expected LP__GUID instance instead of pointer to GUID` (a ctypes signature bug, unrelated to
  this fix). Flagged, not investigated/fixed this session.


## 🔁 "תרגומים מובילים" (Featured row) visibly re-populated on every catalog refresh — root cause + debounce fix (2026-08-14, LOCAL build DEV_BUILD 239, BUILD_ID `20260813224113`, NOT published)

Follow-up user report, same session as the black-cover fix above: on the home screen the
**"תרגומים מובילים"** row (`HomeView.tsx`) shows only PART of its cards at first, then
"updates" — and this recurs every time the catalog changes ("בהתחלה רואים רק חלק מהכרטסיות
שבתרגומים המובילים ואז הוא מתעדכן. תתקן את זה שלא יחזור על עצמו כל פעם שמשתנה משהו חדש").

- **🔑 ROOT CAUSE — this is the SWR (stale-while-revalidate) catalog cache working exactly as
  designed, but with no UI-side settling.** `main_eel._load_catalog()` calls `swr_cache.swr
  ("games", _fetch_catalog_live_first, ttl=30)` (`main_eel.py:465`). On a warm boot the on-disk
  `~/.translation_manager/cache.json` entry from the LAST session is almost always older than
  the 30 s TTL (the app isn't kept running for 30 s between closes), so `get_all_games()` returns
  that **stale** snapshot INSTANTLY (by design — this is what makes the app open fast) and, in
  the same call, fires a background live re-fetch (`_maybe_refresh_bg` → `_bg_worker`,
  `swr_cache.py:233-313`). If the live catalog genuinely differs from the stale snapshot (exactly
  the case right after this session's 4-new-games work — new `featured` flags / new games / a
  changed `sortOrder`), `_bg_worker` pushes the corrected array via `cache_refreshed("games", …)`
  → the frontend's SWR handler (`App.tsx:453-474`) does a plain `setGames(fresh)`.
  `HomeView.tsx` recomputes `featured = games.filter(g => g.featured).sort(...)` **inline on
  every render**, so the moment that push lands the row's composition (which ids, in what order)
  can jump straight from the stale set to the corrected one — read as "shows part, then
  suddenly more cards appear." Because this SWR correction fires on **every boot** where the
  live catalog has moved on since the cached snapshot (not a one-off), the visible pop recurs
  "every time something new changes," exactly as reported.
- **Why the individual card images don't also flicker (ruled out as a contributing cause):**
  the [[cached-image-onload-race]] fix in `GameCard`/`SmartImage` keys its `useEffect` on the
  derived cover-URL **string**, not the `game` object identity, so a card whose cover string is
  unchanged keeps its `imgLoaded` state across an SWR push with zero visual reset — confirmed by
  reading both components again this round. The reflow the user saw is specifically the ROW'S
  **composition/order** changing (cards being added/reordered), not individual images reloading.
- **Fix — `HomeView.tsx`, a settle debounce scoped to the featured composition only, zero added
  latency on a normal boot:** the FIRST render of the featured list still paints immediately
  (a plain `useState(featuredNow)` initializer — no delay, no regression vs. before). A `useRef`
  tracks the last-shown composition's signature (`featured.map(g=>g.id).join(",")`); a
  `useEffect` keyed on that signature only fires when it actually changes on a LATER render, and
  defers applying the new composition by **500 ms** (clearing/rescheduling on each further
  change, so a burst of several quick SWR pushes collapses into one final settled swap instead
  of several visible flickers). Both consumers of the row (`FeaturedCarousel` and the horizontal
  card list) read the debounced state, so the fix covers both surfaces in one place.
- **Verified:** `npx tsc -b` clean (no TS errors). Full local build+install:
  `& '.\build_exe.bat'` (BUILD_ID `20260813215433`→**`20260813224113`**, DEV_BUILD 238→**239**,
  `=== BUILD SUCCESS ===`, dist exe mtime confirmed fresh) → ISCC (`Successful compile`, only the
  2 pre-existing benign warnings) → `Output\TranslationManager-Setup-1.2.0.exe` (fresh mtime,
  01:49) → launched via `Start-Process` for the user's UAC/click-through. **Not yet confirmed by
  the user** whether the row now settles cleanly on the new install.
  **NOT published** — local build only, per the standing rule; ship to other users only on an
  explicit "פרסם".
- **Deliberately NOT changed:** the SWR cache-first/background-revalidate architecture itself
  (`swr_cache.py`) — it's used app-wide and is what makes the app open instantly; slowing/blocking
  the FIRST catalog fetch to avoid ever showing a stale snapshot would trade this cosmetic issue
  for a real, felt boot-speed regression on every single launch. The stats row
  (`בקטלוג`/`זמינים`/`בקרוב`/`מותקנים במחשב`) was left un-debounced — those are plain numbers, a
  value flipping isn't visually disruptive the way a card grid reflowing is, so it wasn't in
  scope for this fix.


## 🩺 Crash-report triage → three real bugs, one of them the FPS complaint (2026-08-13, LOCAL build `20260813174402`)

Seven reports from the admin panel, and reading them as CLASSES (not as seven incidents) is what
made them tractable: 2 × `launch_error/no_exe`, 3 × `self_healed` on `plugins.state`, 2 ×
`off_thread_timeout: get_mod_updates did not return within 180.0s`. Two user reviews landed
mid-session and turned out to be the SAME root cause as one of them.

- **🔴🔴 THE 180 s TIMEOUT WAS A QUEUE WAIT, NOT A SLOW CALL — and the code it blamed was already
  correct.** `get_mod_updates` measured **10.8 s** here, both slow calls were already `_bounded(8 s)`,
  and the between-item budget is 30 s — so the function could not produce 180 s. The clock belongs to
  `_run_off_thread`, which **starts counting when it SUBMITS to `QThreadPool.globalInstance()`**,
  and every one of the **15 fire-and-forget install/scan jobs runs on that same global pool** (a
  Witcher 3 install holds a thread for ~6 minutes, `scan_deep` for minutes, `clear_*_cache` 300 s).
  The pool is sized to the CORE COUNT, so on a 4-core laptop two installs plus a scan **saturate it
  and an advisory read waits out its entire budget without ever running.** Fix: `_slot_pool()` (12
  threads, short slot-blocking calls) is now separate from `_job_pool()` (3 threads, the long jobs).
  Proven both ways in one offscreen test: with 6 heavy jobs queued, a slot call returns in **0.03 s**
  under the new shape and reproduces the exact reported `TimeoutError` under the old one.
  **UNIVERSAL: a timeout on a pooled dispatch measures QUEUE + EXECUTION. If the same pool carries
  minute-long jobs, a short call can fail having done nothing — and every instinct will send you to
  profile the innocent function.** The timeout message now says which it was
  (`queued 180s, never started - slot pool starved` vs `started after 0.4s, still running`), so the
  next report diagnoses itself.

- **🔴 "דרך התוכנה ה-FPS נמוך, דרך המשגר של המשחק חלק" — a user's own A/B, and we were the variable.**
  `launch_game` spawned the exe and then did **nothing**: we stayed a VISIBLE Chromium window
  compositing on the same GPU the game needs, polled at full cadence, held a few hundred MB of
  working set, and ran at the same priority as the game. Steam/Epic get out of the way; we did not.
  `_yield_to_game(proc)` now (1) hides the window to tray via a `@Slot` on the shell — the only
  thing that actually stops QtWebEngine painting AND removes an always-on-top surface that can knock
  a game out of exclusive fullscreen, (2) drops OUR priority to BELOW_NORMAL (we are I/O-bound, so
  it costs nothing), (3) `perf_manager.set_game_running(True)` → **every background poller ×6** plus
  a forced memory trim. A daemon watcher restores all three when the game exits. Measured end-to-end:
  priority `0x20 → 0x4000 → 0x20`, poll multiplier `6.00 → 36.00 → 6.00`, hide fired, restore
  automatic. The game is spawned with an explicit `NORMAL_PRIORITY_CLASS` so it can never inherit
  our lowered class on a later launch.
  ⚠️ **`set_game_running` exists because the CPU heuristic is a LAGGING signal** — it only reacts
  once the machine is already pegged, i.e. after the user has felt the stutter.
  ⚠️ **The ctypes handle trap bit again, and would have been silent:** `GetCurrentProcess()` must be
  declared `restype=c_void_p` or the 64-bit pseudo-handle is truncated and `SetPriorityClass` fails
  **inside the `except`** — the priority drop would simply never have happened. Same bug that made
  `EmptyWorkingSet` a no-op for months. It surfaced only because the TEST hit it first.

- **`no_exe` — the launcher ignored the exe the user had picked BY HAND.** The ladder is now:
  `paths.get_exe` (an explicit user choice outranks every guess) → `cfg.validation_file` →
  `game_detector.find_exe` (the game's REAL exe names across the known `bin/` layouts, better than
  "largest .exe", which picks a crash handler) → the old heuristic. Verified 26/26 detected games
  resolve here. And the dead-end message was split: a MISSING folder (moved / drive unplugged) now
  says exactly that, because it is the only one the user can act on — the reporter clicked twice
  three minutes apart and gave up.

- **3 of the 7 reports were a mechanism WORKING.** `plugins.state recovered after 1 retry (locked)`
  is an AV/indexer holding a small JSON for a few ms; the retry is the design. Reporting it at the
  same severity as a real failure is how a genuine one gets buried. A one-retry `locked` recovery no
  longer reports; anything slower, or any other kind (corruption/disk/memory), still does.


## 🔴🔴 Permanent boot crash after a SignalRGB mod install — a `SystemExit` from downloaded code that EVERY `except Exception` missed (2026-08-01, LOCAL build `20260801175140`, NOT published)

User: "after installing the SignalRGB mod the launcher crashes forever — and it doesn't even send a
crash report to the admin site." Root-caused from the live `launcher.log`: the app was alive on the
SignalRGB panel (`owns_game(signalrgb) → True` ×4), then from the next boot it **crash-looped** —
every cycle reached `catalog poller started` + gpu-probe, then died **mid-enrichment with ZERO
`owns_game`/card-render calls after it** (a healthy boot continues to `owns_game`). No traceback, no
crash report, and — the decisive clue — **no Windows Application-Error event 1000**.

- **🔴🔴 THE ROOT CAUSE — a `raise SystemExit` in downloaded in-process code.** Reproduced by running
  the three enrichment calls in isolated subprocesses with the real user profile: `signalrgb_mod.
  status()` → `_exe_is_hebrew()` → the DOWNLOADED package's `patch_exe.find_slot()` does
  **`raise SystemExit('no Arabic/Hebrew .qm slot found in the exe')`**. `SystemExit` is a
  **`BaseException`, NOT an `Exception`**, so the `except Exception:` in `_exe_is_hebrew`, in
  `status()`, and in the `_mod_state` SignalRGB branch **all missed it** — and the interpreter treats
  `SystemExit` as a *clean exit*: it does **not** call `sys.excepthook`, so the crash_reporter never
  fires, nothing is logged, and Windows logs no Application-Error event. The process just vanishes and
  relaunches. `find_slot` aborts because the SignalRGB app **auto-updated `app-2.5.74` → `app-2.5.75`**
  (the detector shows the live path), moving the `.qm` qrc slot the mod was built for.
  **The author KNEW install.py raises SystemExit** — `enable()`/`disable()` explicitly
  `except SystemExit`. They just MISSED the READ/reconcile path (`status()` → `find_slot`), guarding
  it only with `except Exception`.
- **✅ FIX — three launcher-side layers (no mod re-publish needed; the LAUNCHER runs the downloaded
  code):** (1) `signalrgb_mod._exe_is_hebrew()` → **`except BaseException`** (the actual leak point;
  reconcile-against-the-exe is advisory → fall back to the recorded state, never die); (2) the
  `_mod_state` SignalRGB branch → `except BaseException`; (3) **THE SYSTEMIC NET — `_enrich_catalog`
  now guards EACH row with `except BaseException`, logs it, REPORTS it to the admin site
  (`_event("enrich_failed", …)`), and shows the bare row.** So one bad applier can never again
  silently kill boot or abort the whole catalog, and — answering the user's second complaint — it is
  never silent again. `srgb.status()` now returns `{cached, enabled:false}` cleanly; a re-install on
  2.5.75 returns `enable()`'s clean SystemExit-caught error instead of crashing.
- **🔴 UNIVERSAL:** any launcher guard around code that may run **downloaded / applier / CLI-style
  code** (SignalRGB + Borderless Gaming run downloaded `install.py`/`patch_exe` in-process) MUST catch
  **`BaseException`, not `Exception`** — a `raise SystemExit` / `sys.exit()` inside a library function
  is a landmine that kills a long-running host with **no diagnostics**. And a boot enrichment/fan-out
  loop must **degrade-and-report per item**, never let one item's failure of ANY class abort the sweep.
  **Recognise the signature instantly: permanent boot crash-loop + no crash report + no Application-
  Error event + the log ends mid-boot = a `SystemExit`/`os._exit` escaping an `except Exception`, NOT
  a native access violation.** [[systemexit-escapes-except-exception]]
- **⚠️ SEPARATE follow-up (a MOD concern, not the crash):** the SignalRGB Hebrew mod is now broken on
  app **2.5.75** (the `.qm` slot moved) — it needs re-deriving for the new exe layout; until then it
  shows DISABLED/not-installed. The package's `patch_exe.find_slot` should also change its
  `raise SystemExit` → a catchable exception on the next SignalRGB publish (cosmetic now the launcher
  is immune). Left the downloaded-package source untouched (changing it needs a re-publish + re-test,
  zero benefit now that all three launcher layers catch it).


## Launcher field-error fixes + EXE-path picker (2026-07-31, LOCAL build `20260731013613`+, NOT published)

Two field-error reports + a UX request, all built+installed LOCALLY (Program Files), NOT published.
- **Detection is by FOLDER, not by EXE** — `game_detector` matches a folder NAME under known roots
  (Steam/Ubisoft/Epic/… registries give the folder too); the EXE is only a **fingerprint fallback**
  (`match_by_executable`) when the folder name doesn't match. `_install_path` therefore always returns
  a game-ROOT folder, and every applier + `_deploy_root` writes into it.
- **🔑 Settings path field is now EXE-centric, but the backend still stores the FOLDER.** The field
  shows/accepts a full EXE path and a "בחר קובץ (EXE)…" button opens a native `QFileDialog`
  (`bridge.pick_exe` Slot + `@eel.expose pick_exe` fallback; `api.pickExe`). On save, `set_custom_path`
  detects a `.exe` and stores the ROOT (`game_detector.root_from_exe`) + remembers the exact exe for
  display (`paths.get_exe/set_exe` → `custom_exes.json`, a separate store so the root schema is
  untouched). `_enrich_game_row` emits `exe_path` = the picked exe OR `find_exe(gid, folder)`. **Zero
  applier risk** — the stored root is unchanged, and appliers validate their target (a wrong root
  fails with a clear message, never corruption).
  - **🔴 THE DISCRIMINATOR for root-from-exe is the FOLDER-NAME PATTERN, not `match_by_executable`.**
    `match_by_executable` can't tell `<root>` from `<root>\bin\x64` (both "contain" the exe via its
    `sub=""` branch), so it would resolve a `bin/x64` exe to the wrong root. `root_from_exe` walks UP
    from the exe's folder and returns the first ancestor whose NAME matches this game's detect pattern
    (or a `GameConfig.validation_file` exists under it), else the exe's own folder. **Round-trip
    verified 8/8 on real installs**, incl. the subdir case `WATCH_DOGS2\bin\WatchDogs2.exe` → root
    `WATCH_DOGS2`. Memory [[launcher-install-error-diagnosability]].
- **`get_mod_updates` 180s timeout (warn)** — one item's native `is_applied()` content-hash of a
  multi-GB game file ran unbounded (the 30s budget is only checked BETWEEN items). Fixed with
  `_bounded(fn, 8s)` per item: the hash finishes in the background (warms its memo → next poll fast)
  while the sweep returns quickly. `fetch_manifest` was already 10s-capped.
- **`install_error: שגיאה בהתקנה: [WinError 2]` (error)** — leaked a raw English Windows string with
  no game id. Fixed: W3+GTAV `apply()` catch `OSError` → an actionable Hebrew message ("קובץ שנדרש
  לא נמצא / אין גישה אליו — אמת קבצי המשחק, סגור את המשחק, ונסה שוב"); the `install_error` event now
  tags the game (`_CUR_INSTALL_GAME`). Diagnostic: a no-path `[WinError 2]` = a subprocess/low-level
  missing file (a normal file op prints `[Errno 2] … : '<path>'` WITH the path).

---


## Launcher `auth_me` crash fix — LOCAL build (2026-07-09, NOT published)

Old admin-panel crash (build `20260705144705`): `TimeoutError: _run_off_thread: auth_me did
not return within 30.0s`. Root cause: `auth/manager.py` `me()` chains up to THREE sequential
HTTPS calls on token expiry (15+8+8 ≈ 31s worst case), which exceeds the 30s off-thread guard
in `qt_shell/bridge.py` on a slow network → the `TimeoutError` escaped the `auth_me` slot and
crashed the app. **Two-part fix (build-installed locally per [[local-install-launcher-builds]],
NOT published — no "פרסם"):**
- `qt_shell/bridge.py auth_me`: bumped `_run_off_thread` timeout 30→**45s** AND wrapped it so it
  **never crashes** — on any timeout/exception it logs a warning and returns the cached identity
  (`self._b.auth_cached_user()`), so a slow network degrades gracefully instead of crashing/
  signing out.
- `auth/manager.py`: new **`cached_user()`** = last-known signed-in identity from the on-disk
  `~/.translation_manager/user_cache.json` (network-free, GUI-thread safe). Re-exported in
  `auth/__init__.py` (`from .manager import … cached_user` + `__all__`). `main_eel.py`: new
  `@eel.expose auth_cached_user()` RPC → the bridge fallback path.
- Built via `build_exe.bat` (BUILD_ID `20260709194431`, DEV_BUILD 48, dist exe 9,154,907 B) →
  ISCC → installed locally. All 4 files py_compile-clean. Version stays 1.0.2 (channel beta).

---


## 📊 The progress bar promised work that wasn't happening — gate it on the state that MEANS it (2026-08-16)

User, with two panels side by side: Skyrim at **99.7 %** under a **"בעבודה"** chip, and Crimson
Desert at 66.5 % under **"בתהליך תרגום"** — *"תסיר שלא יהיה בכלל רק למשחק שהוא על סטטוס של 'תהליך
תרגום' ולא משהו אחר"*.

- **ROOT CAUSE — a helper whose name is broader than the decision it was making.** The bar was gated
  on `isInFlight()`, i.e. the SET `{in-progress, extracting, translating, packing, finalizing, qa}`.
  That set exists for a genuinely different question ("is this game anywhere in the pipeline?"), and
  it was answering "should we draw a live progress bar?". So a game parked at 99.7 % under a generic
  "בעבודה" advertised a bar that had not moved in weeks — the UI claimed live work where there was none.
- **Fix: a second, deliberately NARROWER predicate** — `showsTranslationProgress(a) => a ===
  "translating"` (`lib/types.ts`), used for BOTH the render gate and the `useLiveGameProgress`
  fetch-enable (no point polling `/api/progress` for a game that will never render it). `isInFlight`
  is left intact for other callers, with its comment corrected so it no longer claims to gate the
  progress UI. **UNIVERSAL: when a boolean helper is reused for a second decision, check that its
  NAME still describes that decision — the cheapest way a UI starts asserting something false is a
  predicate that is 80 % right.**
- **Verified by EXECUTING the predicate, not by matching a string:** the smoke test parses the
  `Availability` union and the function body out of the real source, builds the function, and runs it
  over all 11 states — exactly one passes (`translating`), and each of the other 10 is asserted
  individually. It also pins the two Hebrew chips (`translating`→"בתהליך תרגום",
  `in-progress`→"בעבודה") so a future label edit can't silently re-open the gap, and asserts the
  panel still has exactly **2** `<LiquidWave>` blocks — the install/download bar must not be caught
  by this change. 27/27, `tsc -b` clean, both earlier suites still green.
- **Same round, the activation note: one stray arrow.** `NATIVE_DL_API.hogwarts.note` read
  `הגדרות ← שפת טקסט (Text Language) → בחרו English` — a `→` among `←`, while all four sibling notes
  use `←` throughout. In an RTL breadcrumb the arrow must point the way you read, and an arrow is a
  bidi NEUTRAL, so it renders as authored rather than being mirrored into place. Fixed to `←`; a
  before/after render confirmed it ([[close-the-loop-before-tuning]]). ⚠️ The WD2 reminder's
  `Settings → Written Language` is CORRECT and must stay `→` — that arrow sits between two Latin runs
  inside an LTR island. **The arrow follows the direction of the RUN it lives in, not the paragraph.**
  The note itself stays — it is the only place that tells the user to switch Text Language to English,
  without which an installed translation looks like it did nothing.


## 🖼️ "לפעמים אין תמונות" — the empty black card was a FINISHED animation, not a missing one (2026-08-16, source-only)

User report on the library grid (screenshot): many cards render as black boxes with only the title.
The ask was "an animation everywhere a picture should be, until it shows". The mechanism already
existed — it had simply **stopped**.

- **🔴 ROOT CAUSE — the animation was bounded SHORTER than the state it decorates.**
  `.skeleton::after` ran `skeleton-sweep 1.4s × 5` = **7 s**, then parked at `translateX(100%)`
  (off-screen, no fill-mode) leaving the base `rgba(255,255,255,0.05)` — which over this app's
  near-black shell IS an empty box. But the loading STATE lives up to **12 s** (the stuck-load
  timeout in `GameCard`/`SmartImage` forces the error fallback). So every slow cover spent ~5 s
  looking broken, and then fell back to a themed gradient that is *also* near-black for every theme
  (`#0a0a14 → #101830` by default, and the darkest is `#050807`). Two different states, one identical
  black rectangle.
- **The fix is to bind the animation to the STATE'S OWN MAXIMUM LIFETIME instead of an arbitrary
  number**: `2.2s × 6 = 13.2 s > 12 s`. Still a finite count (never `infinite` — the documented
  46-card CPU-raster problem is about an unbounded sweep inside a `backdrop-filter` region), but now
  it cannot stop before the thing it represents does. It costs nothing in the common case: a cover
  that lands in <1 s unmounts the element, so the extra iterations are only ever paid when a load is
  genuinely slow — exactly when the affordance is needed. The smoke test asserts the inequality
  against the timeout it reads out of the components, so the two can never drift apart again.
- **A placeholder must look DELIBERATE at every frame, including its resting one.** The base gained a
  soft tint layer (`--skeleton-tint`, neutral default) and the sweep a themeable band
  (`--skeleton-sheen`); `GameCard` feeds both from the game's own accent. The **failed-cover**
  fallback got the same treatment — an accent bloom over the themed gradient — because after 12 s
  that is what every stuck card becomes, and it was the *same* black box.
- **The list rows had the same hole from the other direction:** `SmartImage` hides a broken `<img>`
  and there was nothing behind it. Tinting the **slot** (the `w-12 h-16` container) rather than the
  image covers both states in one line, and the skeleton inherits `--skeleton-*` from it for free.
- **🔴 A REAL BUG FOUND NEXT DOOR: `html.anims-low .skeleton { animation: none }` stopped nothing** —
  the sweep lives on `.skeleton::after`, so the "reduced animation" level never actually disabled it.
  Fixed to target the pseudo-element. (`prefers-reduced-motion` had it right all along.)
- **Verified by LOOKING at it** ([[close-the-loop-before-tuning]]): a standalone page rendered in
  headless Chrome shows loading / parked / no-cover / the OLD look side by side — the old parked and
  old fallback are visibly grey-black, the new ones read as per-game art. Plus a 21-check regression
  suite over the REAL files, `tsc -b` clean, all seven earlier suites still green.
  ⚠️ The comment-vs-code artifact bit a third time: my own comment saying *"never `infinite`"* failed
  the negative assertion looking for `infinite`. Strip comments before asserting absence.


## 🔴🔴 …AND THAT SAFETY NET BECAME THE BUG — a timeout must never destroy what it guards (2026-08-16)

The very next launch, the user recorded it: after the splash the home **"תרגומים מובילים"** cards were
blank, and **only leaving the menu and coming back** filled them in. That "a remount fixes it" signature
is the [[cached-image-onload-race]] tell — but the cache fix was present and correct. The 12 s stuck-load
timer added above was the culprit, and it is a **regression I introduced**.

- **THE CHAIN.** The card mounts → its cover is `loading="lazy"` and the featured row is **below the
  fold**, so the fetch never starts → the timer nevertheless fires 12 s after **MOUNT** → it set
  `imgError` → and the `<img>` was rendered `{!imgError && (<img …>)}`, i.e. **removed from the DOM**.
  An element that is not in the DOM can never load, so the card was dead until a remount rebuilt it.
- **🔴 THE TIMER MEASURED THE WRONG INTERVAL.** It was written to catch *"a hung request"*, but it
  counts from mount, and a lazy/off-screen image has not made a request at all. The budget can be fully
  spent **before the fetch begins** — so the grace period is effectively zero for anything below the fold.
  **Any deadline on an operation must start when the operation starts.**
- **🔴 AND IT WAS DESTRUCTIVE, WHICH TURNED A GLITCH INTO A DEAD END.** A fallback is supposed to be what
  you show *while* you wait, not a decision to stop waiting. Fix: split the two states — `imgError` means
  *the load genuinely failed*, the new `settled` means *the placeholder stopped shimmering*. `settled`
  only swaps the skeleton for the themed gradient; it never hides or unmounts the image, so a cover that
  arrives at t=20 s still fades in. **Now that the timer cannot break anything, firing early is harmless.**
- `SmartImage` had the same defect in a quieter form: it kept the `<img>` mounted but keyed opacity on
  `loaded && !err`, so once the timer set `err` a later successful load could never become visible.
  Opacity is now keyed on `loaded` alone, and `onLoad` clears the error latch in both components.
- **The home row no longer relies on lazy at all.** `size="lg"` is used by exactly one caller (the
  featured row), those ≤8 covers are precisely what the splash preloader already warms, and the row is
  below the fold — so lazy there only delays an image we already hold. `loading={size === "lg" ? "eager"
  : "lazy"}`; the ~46-card library grid keeps lazy.
- **🔑 PROVEN IN A REAL BROWSER, not by reasoning** — the launcher-designer preview mounts the REAL `App`
  behind a mock eel, so Playwright can replay the user's exact sequence. Two runs: (1) open, sit still
  15 s, then scroll → the `<img>`s are all still present, the shimmer has settled, covers load and reach
  opacity 1; (2) **hold every image response for 14 s** (past the timer) → at 13 s the placeholder has
  settled with **0 loaded** yet **2/2 `<img>` alive**, and at 20 s the late covers decode and paint.
  Run (2) is the one that would have failed on the old code, and it is the regression test worth keeping
  (`launcher-designer/_dom_covers.cjs`, `_dom_late.cjs` — ⚠️ they must LIVE in `launcher-designer/`,
  because node resolves `playwright-core` from the script's directory, not the cwd).
- **Reading the recording is what aimed this** ([[read-the-recording-frame-by-frame]]): a contact sheet
  located the moment, and a 1.7× crop showed the cards were a *flat* themed gradient with no shimmer —
  the settled/error look, not a still-loading one — while the library view a second later was perfect.
  ⚠️ I then tried to separate "skeleton parked" from "error gradient" by measuring luminance across
  frames and it was **inconclusive** (the user was scrolling, so the patch moved). **When two candidate
  mechanisms share one fix, stop measuring and fix the class** — both were real, and both are now closed.
- 4 assertions in the previous round's suite failed afterwards. They were **stale expectations**, not
  regressions: they matched `setImgError(true)` inside the timer, which is exactly what the fix removes.
  Re-derived against the current design ([[recheck-exclusions-against-what-was-approved]]) — never
  deleted. **152 checks green across 4 suites**, `tsc -b` clean.

### Round 18 — the PROMPT is the product: full-screen capture, window-switch awareness, read-the-screen, web grounding (2026-08-16, source-only)

Every earlier round was about the WINDOW. The user's ask here was about the ANSWER: capture the
whole screen (not a window), notice when they alt-tab and change subject, actually READ what is
written on screen (quest, objectives, dialogue, HUD), and search the web about that quest so the
answer is the real one. Plus "ועוד שיפורים שאפשר להכניס".

- **🔴 Capture the MONITOR, not the window.** `_monitor_rect()`
  (`MonitorFromWindow(MONITOR_DEFAULTTONEAREST)` + `GetMonitorInfoW`, `rcMonitor` not `rcWork`)
  feeds `ImageGrab.grab(bbox=…, all_screens=True)`. A window crop hides exactly what the answer
  needs — the HUD, minimap, quest tracker and prompts live at the SCREEN edges, half of them
  outside a windowed game's client area — and it makes the capture behave identically whether the
  game is windowed, borderless or maximised. Pillow subtracts the virtual-screen offset itself, so
  a monitor left of the primary (negative coords) works. Falls back to the window bbox, then the
  whole virtual desktop.
- **Fidelity follows the new job.** The feature is now READING small type, and that is the first
  thing a hard downscale plus JPEG ringing destroys: **1280→1536 px, q72→q85**, and
  **temperature 0.4→0.25** (transcribing a screen is factual, not creative). `max_tokens`
  900→**1400** and the timeout 45→**75 s**, because a truncated answer loses the STEPS — the part
  the user acts on. Key verification keeps its own **30 s** budget: it runs while they wait.
- **`detect_context()` replaces "what game is this?" with "what is the user looking at?"** —
  `{title, exe, catalog_id, app, is_game, display}`. It matches our catalog on the title **and on
  the EXE**, because a game in exclusive fullscreen usually has a useless title while its exe never
  lies; and a `_KNOWN_APPS` table names a browser/Discord/Steam/the launcher **as an app**, so the
  answer adapts instead of inventing a quest. `detect_game_name()` stays as a wrapper.
- **The window-switch cue is what makes it change subject.** `cfg["last_game"]`/`last_at` are
  already persisted by both call sites, so no new state: the prompt carries *"last time (N minutes
  ago) the screen showed X — if it changed, refer only to what is shown now."* **It requires the
  timestamp** (`bool(last_at) and mins <= 120`): the cue's whole value is recency, and a
  `last_game` with no `last_at` could be days old, which is worse than saying nothing.
- **🔴🔴 GROUNDING WAS SILENTLY OFF FOR A WHOLE MODEL FAMILY.** The tool field is `google_search` on
  Gemini 2.x and **`google_search_retrieval` on 1.5** — a single attempt meant a 1.5-class model
  fell straight through to "no tool" and the answer was a plausible guess with no way to tell.
  Now it is a chain (`google_search` → `google_search_retrieval` → none), and it **only retries a
  400/403/404** — a bad key or a spent quota would otherwise fail identically three times and just
  slow the error down. The prompt states honestly whether search exists (`can_search` is Gemini-only
  today) and the answer ends with a **🔎 מקור** line, so the user can tell a searched answer from a
  remembered one.
- **🔴 OUR OWN PANEL IS IN THE SCREENSHOT.** `_start_analysis()` calls `show_animated()` (it holds
  the "analysing" state) *before* `analyze()` runs on the worker thread — so with step 2 telling the
  model to read every word on screen, it would dutifully report our own UI as part of the game.
  Fixed by `_overlay_is_visible()` (reads the existing `_runtime_status` under the existing lock)
  → one prompt line describing the panel and telling it to ignore it, emitted **only when the panel
  is really up** so we never send it hunting for something that isn't there. Hiding the window
  instead would need a GUI-thread round-trip from a worker thread plus a compositor wait — all risk,
  no gain.
- **Output format grew to seven sections** (`🎮 מה על המסך · 📖 כתוב על המסך · 📍 המצב · 🎯 המטרה ·
  📋 שלבים · 💡 טיפ · 🔎 מקור`). ⚠️ `_HEADER_MARKS` in the runtime **must** list every one of them —
  a marker missing there renders as ordinary body text, so the two files are a contract.
- **Verified:** `py_compile` clean; a new 83-check suite (`smoke_prompt.py`) covering the capture
  path, context detection (game / browser / title-less fullscreen / nothing), every instruction the
  user asked for, the per-call context lines, `analyze()` wiring against a stubbed provider, and the
  grounding chain — plus all six earlier suites still green (**317 checks total**).
  ⚠️ Two of the new assertions failed first: one was the documented comment-vs-code artifact (the
  comment explaining `1536 (was 1280)` contains `1280`), the other was a REAL behaviour question
  that the code lost — a `last_at` of 0 emitting a cue — and the fix belonged in the code.
- **No build.** The user runs `dev_overlay.py`.

### Round 17 — 🔴🔴 `reposition()` was using the PREVIOUS size, so every open/close mis-docked (2026-08-16, source-only)

A fourth recording and a precise report: docked RIGHT it opens **off-screen to the right**, closing
makes **the tab run away**, same on the bottom, and long text should **grow the window** instead of
scrolling. Rounds 14 and 16 had both aimed at this and missed, because both reasoned about
*animation* when the defect was *arithmetic*.

**🔴🔴 THE ROOT CAUSE — a layout change does not reach the WINDOW until the next layout pass, so
every position was computed from the size the window had a moment ago.** `_reflow()` called
`_view.setFixedSize(w,h)` + `adjustSize()`, then `reposition()` read `self.width()` — still the OLD
value. Measured, not inferred (`scratchpad/probe_anchor.py` prints the real geometry):

| action | size reposition SAW | result |
|---|---|---|
| expand on a right dock | 40 (the tab) | `x = right-50`, then it grew to 470 ⇒ **430px off-screen** |
| collapse on a right dock | 470 (the panel) | `x = right-480`, then it shrank ⇒ **the tab 430px inland** |

The probe made it unmistakable: every printed rect was the one the PREVIOUS step should have had.

**THE FIX — two halves, both needed.** (1) `_reflow()` now calls `layout().activate()` on the chain,
so `self.width()` is truthful immediately; (2) position and size are applied in **ONE**
`setGeometry(x, y, w, h)` (`_apply_geometry`), computed from `self._size` — the size we INTEND —
so there is never a frame where the new size sits at the old position. `_target_pos()` is now a pure
function of (w, h), which is what makes it testable.

**🔑 And the snap-vs-glide decision moved INTO `_reflow(animate=…)`, where `animate` is a REQUEST,
not a command:** a glide is allowed only if the size did not change. Rounds 14 and 16 each had to
get that right at every call site (and each time a new caller appeared it was wrong again); now one
place decides, and `reposition()` keeps an independent guard that downgrades an animated call to a
snap if it would also resize. **UNIVERSAL: when a rule must hold at N call sites, move the rule
below them — a flag every caller has to pass correctly is a bug waiting for the next caller.**

**📏 Long text now GROWS the window** (`_on_content_height` ← the page's own measurement), capped at
86 % of the screen and always symmetric around the dock anchor, so the rail never moves. Verified
end-to-end against the REAL page, not just the Python half (`scratchpad/probe_grow_live.py`):
51 lines → **156 → 670px** (the cap; it wants 1015), on-screen, centred — and **back to 156** when a
short answer follows.

**🔴 THE SECOND BUG, which only the live probe could show: a scroll box can never ask to be
SMALLER.** The first formula was `winH - body.clientHeight + body.scrollHeight`, and
`scrollHeight >= clientHeight` **by definition** — so once grown, "needed" always equalled the
current height and the panel stayed huge after a two-line answer (measured: 670 reported as needed
for two lines). The text now lives in an inner block whose height is pure content, in both
directions. **UNIVERSAL: to auto-size a container to its content, measure a child that is sized BY
the content — never the scroll box itself, which is sized by the container.**

**🔴 `QRect.right()`/`bottom()` are INCLUSIVE** (`x + w - 1`), so `geo.right() - w - MARGIN` left an
**11px** gap against the left/top's 10. Fixed with `+ 1`; the suite asserts all four margins.

- ⚠️ **Three suites had assertions that spied on `reposition(animated=…)`** — legitimate before the
  rule moved, meaningless after (a snap no longer calls `reposition` at all). Re-derived to assert
  the OUTCOME (the window lands at the computed target in one frame), which is stronger: it also
  covers the resize, which a spy on the position never did.
- ⚠️ **A negative assertion must read CODE, not prose** — `"body.scrollHeight" not in js` failed on
  the COMMENT explaining why that formula is wrong. Strip comments first (the round-12 CSS lesson,
  in JS).
- **Verified:** `py_compile` + `node --check` clean; **234 checks green across six suites**
  (12: 20 · 13: 35 · 14: 37 · 15: 29 · 16: 35 · 17: 78) plus two live probes. **No build** — the
  user runs `dev_overlay.py`.

### Round 16 — the rail now runs ALONG whichever edge it docks to (2026-08-16, source-only)

Third recording + three asks. The recording confirmed 15b landed: the rail mirrors to the RIGHT on
a right dock, and a pixel scan across the panel edge shows **no hairline** — the DWM border fix
holds. What was left is that the rail was still a VERTICAL column on a top/bottom dock, i.e. the
✕ / arrow / ↻ sat on the *side* of a panel hugging the *top* of the screen.

**The rail is now an axis, not a side.** `.edge-top { flex-direction: column }` /
`.edge-bottom { column-reverse }` put the sidebar on the docked edge (column order is literal —
`dir` only affects the inline axis), and the sidebar itself flips to `flex-direction: row` with a
fixed `height` instead of a fixed `width`. The grab pill transposes with it (22×44 → 44×20), and
`setEdge` now toggles **all four** classes — including `.edge-left`, which needs no rule (it IS the
base layout) but is toggled anyway so the state is inspectable and a future rule cannot silently
miss it. That is exactly the bug `.edge-right` had for five rounds.

**A collapsed tab has to transpose too, and CSS cannot do that — the WINDOW is sized in Python.**
`_reflow()` now returns `(_PILL_H, _PILL_W)` on a top/bottom dock, so the tab is wide-and-short
there instead of tall-and-thin. The collapsed rail gets its own 3-class rule so it beats both the
generic collapsed rule and the horizontal-rail rule.

**🔴 A "did the size change?" check must NOT measure the window.** Crossing between a vertical and
a horizontal edge while collapsed is a SHAPE change, so per round 14 it must snap rather than
glide. The obvious implementation — snapshot `self.size()`, `_reflow()`, compare — **always reports
"unchanged"**: right after `adjustSize()` the top-level still holds the old size (it trails its
child view by an event-loop turn, the same lag the round-15 suite had to `settle()` around). The
fix is to derive the fact from the EDGES (`(old in horiz) != (new in horiz)`), which is
deterministic and needs no event loop. **UNIVERSAL: never measure a Qt widget's geometry in the
same turn you changed it — compute the intent instead.** The round-16 suite caught this as a real
FAIL, not as a test artifact.

**The "טקסט ארוך" demo is now ~50 lines of real paragraphs** (the ripperdoc cyberware screen,
explained properly). A three-line answer proves nothing about the scroll area, the wrap, or how the
panel reads when the model actually explains something.

- **Verified: 156 checks green across five suites** (12: 20, 13: 35, 14: 37, 15: 29, 16: 35).
  `py_compile` + `node --check` clean. Two round-15 assertions were STALE and re-derived, not
  deleted: one matched the old `_arrow()` expression verbatim, and one asserted a tall collapsed tab
  while the preceding loop had left the panel on a *bottom* dock — where wide is now correct.
- **No build** — the user runs `dev_overlay.py`.

### Round 15b — the frame was WINDOWS', the rail never had a rule, and the snap was aspect-ratio biased (2026-08-16, source-only)

A second recording (cropped tight on the panel — much better) plus two screenshots, after 15a shipped.

**🔴🔴 THE "THIN FRAME" SURVIVED REMOVING EVERY CSS RIM BECAUSE IT WAS NEVER CSS — Windows 11 draws
a 1px border on every window, frameless and layered included.** Settled by MEASURING a pixel row
across the panel edge instead of looking: interior `lum=181`, desktop outside `lum=110`, and
**exactly one pixel at the window boundary reading `lum=246`**. A single bright hairline precisely at
the boundary cannot be an inset box-shadow (that would sit inside the radius and span more than one
pixel). Fix: `DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR=34, DWMWA_COLOR_NONE=0xFFFFFFFE)`.
**UNIVERSAL: on a frameless Windows 11 window, removing every CSS border still leaves the DWM border
— and a one-pixel scan across the edge tells you which one you are looking at in seconds.**

**🔴🔴 `.edge-right` HAD BEEN TOGGLED SINCE ROUND 10 WITH NO CSS RULE ANYWHERE.** `setEdge` faithfully
did `classList.toggle('edge-right', …)` and the stylesheet never mentioned it, so `flex-direction:
row-reverse` pinned the rail to the LEFT forever and a right-docked panel opened AWAY from its own
edge (`"החלון נפתח לצד השני ... והוא לא מתהפך אוטומטי"`). Added `.overlay-window.edge-right
{ flex-direction: row; }` plus a mirrored content padding. Note `_arrow()` already computed
`contentOnRight = (_edge !== 'right')` — the JS had assumed the mirror all along, so the arrow was
pointing correctly for a layout that never happened.
**UNIVERSAL: a class that is toggled but never styled is invisible to every test that greps for the
toggle. Assert that each state class HAS a rule, not just that something sets it.**

**🔴 THE SNAP WAS DECIDED BY THE SCREEN'S ASPECT RATIO, not by where the user dropped it.**
`_snap_to_nearest_edge` compared RAW pixel distances, and on 1920×1030 the vertical half-span is 515
while the horizontal is 960 — so anything in the middle band is "nearer" to top/bottom no matter
what. Measured on the real geometry: a drop at 86 % width / 22 % height picked **top**; at 12 % width
/ 80 % height picked **bottom**. Exactly `"אם אני קרוב ללמטה או ללמעלה אז הוא ננעל על הלמעלה או למטה
ולא במקום שבחרתי"`. Fix: divide each distance by that axis's half-span, so it is a fraction of how
far it COULD be. After: those two cases pick **right** and **left**, and a genuine top/bottom drop
still snaps top/bottom (4 of 8 test cases changed).
**UNIVERSAL: any "nearest edge/corner" comparison on a non-square area must normalise per axis, or
the aspect ratio silently makes the decision for you.**

- ⚠️ **The first version of that proof was a measurement artifact — the offscreen screen is 800×800,
  SQUARE, so normalising changed nothing and the test reported "0/6 changed".** Re-ran it against the
  real 1920×1030 geometry to get the 4/8. **A fix that must depend on aspect ratio cannot be
  validated on a square test surface.** (Fifth artifact of this kind in the session; the pattern is
  always "my harness cannot express the failing condition".)
- ⚠️ **The offscreen top-level window trails its child view by an EXTRA event-loop turn** (measured:
  view 470→40 immediately, window still 470 after one `processEvents`, correct on the second). Pump
  until settled, never once.
- **Verified: 121 checks green across four suites** (12: 20, 13: 35, 14: 37, 15: 29).
  `py_compile` + `node --check` clean. **No build** — the user runs `dev_overlay.py`.

### Round 15 — a 33s SCREEN RECORDING found five bugs at once; and the build step is retired (2026-08-16, source-only, NO build)

**⚙️ NEW STANDING RULE (user): stop building. Iterate with `.venv\Scripts\python.exe dev_overlay.py`,
which the USER runs.** That is exactly what `dev_overlay.py` was built for in round 9 (a ~2 s
edit→see loop instead of ~10 min build+ISCC+install). Every change below is source-only.

**🔑 THE INSTRUMENT THAT BEAT EVERY PREVIOUS ROUND: a screen recording, read as frames.** The user
sent a 33 s MP4. `ffmpeg -vf fps=1.33` → 44 PNGs → a 6×8 contact sheet to find the interesting
moments → crop+zoom (`crop=W:H:X:Y,scale=iw*5:ih*5:flags=neighbor`) on the panel. **A 5× zoom on the
collapsed pill showed the defect immediately** — something a full-screen frame at 1916×1030 hides
completely. This replaces "the user describes it and I guess" with reading the pixels, and it found
**five** distinct bugs in one pass where the previous rounds fixed one or two per launch.
**UNIVERSAL: ask for a recording, extract frames, and ZOOM — a bug at 22 px is invisible at 1:1.**

**🔴🔴 CSS SPECIFICITY SILENTLY UNDID THE COLLAPSED STATE.** `.overlay-window.tint` (2 classes) BEATS
a bare `.collapsed` (1 class), so in the new default tint mode collapsing did NOT clear the fill or
the rim — the lone pill sat inside a visible frame (`"מסגרת דקה מרובעת ... על המלבן שהוא סגור"`).
The Python side was correct the whole time (`_apply_accent` switched the blur off); the CSS quietly
put the surface back. Fixed by promoting every rule to `.overlay-window.collapsed` AND placing the
block after `.tint` — **both are needed; either alone still loses.**
**UNIVERSAL: when you add a MODE class to a base element, every state class that must override it
needs at least the same class count and a later position — a state rule written before the mode
existed is silently dead.**

**🔴 THE DRAG FLICKER WAS MINE, from hardcoding a state at a call site.** `_on_drag_start` forced
`ACCENT_ENABLE_BLURBEHIND` and `_on_drag_finish` forced `ACCENT_ENABLE_ACRYLICBLURBEHIND`, both
ignoring the surface mode — so dragging in **tint** mode turned the blur ON and left it on acrylic:
clear → blurred → dark, exactly `"בגרירה יש רעשים בין רקע שקוף לרקע שחור"`. `_apply_glass` had the
same problem at first show. Fixed by making `_apply_accent(dragging=None)` **the single place** that
decides the state (collapsed / surface / dragging), with `_apply_glass` now only *probing* whether
the API works and leaving the window on `ACCENT_DISABLED`. Asserted in the suite: **exactly one
`_set_accent(int(self.winId()))` call in the whole file.**
**UNIVERSAL: a state that depends on 3 inputs must be computed in ONE function; every hardcoded
value at a call site is a mode you forgot to handle, and it surfaces as flicker.**

**🔴 "difficulty dragging" = a 320 ms LONG-PRESS on a 22×48 pill** — a tiny target *and* a
deliberate wait. Replaced with a **4 px movement threshold** (standard hysteresis, per the
apple-design skill): the drag starts the instant the pointer actually travels, a press that does not
travel is still a click, and there is nothing to wait for or learn. **The whole panel is now a drag
surface** (`.icon-btn, .drag-pill, .body` opt out via `closest()`), so the target went from 22 px to
470 px. **UNIVERSAL: prefer a movement threshold over a press TIMER — a timer makes the user wait to
find out whether the app understood them.**

- **The thin frame in the OPEN state too.** `inset 0 0 0 1px rgba(255,255,255,.10)` is literally a
  1 px outline drawn around the panel, and on a colourless surface it was the most visible thing on
  it. Removed from both modes; depth now comes only from a lit top edge + a soft bottom shade, which
  imply a light source instead of outlining a box.
- **The pill read as an unstyled light-grey OVAL** (`rgba(255,255,255,.30)` gradient + `.34` border +
  a bright inset highlight) — the loudest element on a panel whose whole point is restraint. Dropped
  to `.085` flat with no border, brightening on hover; the collapsed state gets its own darker,
  shadowed treatment since there it is the only thing left.
- **Four more stale assertions re-derived, not deleted** (round 12 ×1, round 13 ×3) — all were
  literal string matches against the previous CSS text (`".collapsed              { background:"`),
  so they failed on correct output and would have passed on wrong output. Now parsed and
  selector-agnostic. ⚠️ One of my own replacements was itself wrong: `\.collapsed\s*\{` also matches
  *inside* `.overlay-window.collapsed`, so the "out-specifies" check compared the wrong offset.
  **92 checks green across the three suites.**
- **Verified:** `py_compile` + `node --check` clean (⚠️ extract the page JS to a REAL file — native
  node cannot open a `<(…)` process-substitution fd). **No build** — the user runs `dev_overlay.py`.

### Round 14 — the surface is now a SETTING (blurred glass vs clear-and-darkened), + the expand-direction bug (2026-08-16, LOCAL build `20260816012427` DEV 252, NOT published)

User: **"שקוף וקצת מושחר זה אפשרי?"**, then mid-turn **"באג - שהחלון בצד ימין הוא נפתח לצד ימין
ולא הפוך"** (with a screenshot of the collapsed rail docked at the right edge).

- **"Transparent + slightly darkened" is not only possible, it is the CHEAPER mode — and the proof
  was already in our own code.** In the collapsed state we deliberately set `ACCENT_DISABLED` and
  expect only the pill to be visible ⇒ *"no blur + a layered window = genuinely transparent"* was
  already established here. So the two looks are one flag apart: `ACCENT_ENABLE_ACRYLICBLURBEHIND`
  (frosted, the game blurs) vs `ACCENT_DISABLED` (clear, the game stays SHARP behind a darker
  see-through panel, and the compositor re-samples nothing while a game runs).
- **🔑 I MADE IT A SETTING INSTEAD OF GUESSING.** Two messages earlier the ask was *blurrier*;
  now it was *transparent and dark*. Those are opposite materials, both defensible, and the right
  answer is a preference — not another round of me picking one. `SURFACE_OPTIONS` = `tint`
  (default) / `glass`, normalized by `_normalize_surface()`, surfaced through `get_state`
  (`surface` + `surfaceOptions`) and a `set_surface` action, and rendered by ONE declarative
  `select` node in the plugin manifest — **zero new frontend code**, exactly as the plugin
  architecture intends.
- **The two modes are not the same fill at two opacities.** `tint` needs a HEAVIER fill (0.62 vs
  the glass mode's 0.20): with no blurred acrylic layer underneath, legibility has to come from the
  page. It also drops the frosted top highlight, which only reads correctly on frost. Measured in
  the suite: `tint` alpha > `glass` alpha, and `tint` still < 0.85 so it never becomes an opaque box.
- **Accent policy is now derived, not hardcoded:** `_apply_accent()` = blur ON only when
  `not collapsed and surface == "glass"`. This keeps the round-12 rule (Windows blurs the whole
  window RECT, so a lone pill must not sit in a blurred rectangle) and adds the new one in the same
  place, instead of scattering `_set_accent` calls.
- **`refresh_surface()` is a deliberate NO-OP.** It is called from a QThreadPool worker, and the
  controller's own 600 ms GUI-thread poll already re-reads config every tick — so the new look
  lands within ~0.6 s with **no cross-thread plumbing to get wrong**. Named and documented rather
  than deleted, so the call site's intent is obvious.

**🔴🔴 THE REPORTED BUG — a SIZE change must re-dock in the SAME FRAME; only a POSITION change may
glide.** `_toggle_collapsed()`/`expand()` did `_reflow()` (which resizes instantly, because the root
layout is `QLayout.SetFixedSize`) and then `reposition(animated=True)`. Qt resizes around the
window's **TOP-LEFT**, so a panel docked on the RIGHT first grows **rightward, off-screen**, and the
220 ms glide then slides it back — which is *exactly* "it opens to the right instead of the other
way". Fix: `reposition(animated=False)` on both size paths. Measured: with the panel docked right at
`x=319 w=470`, after a collapse the window sits at `x=749 w=40`; on re-expand the width returns to
470 **while x is still 749**, i.e. 431 px past the screen edge until the glide finishes.
**UNIVERSAL: animate POSITION, never the position correction that follows a SIZE change — the user
reads the intermediate frames as the direction the window opened.**

**🔴🔴 …AND MY FIRST TEST FOR IT PASSED ON THE BROKEN CODE — a measurement artifact, the third this
session.** Asserting the on-screen rect after a collapse/expand cycle was green for *both* versions,
because (a) the offscreen platform DEFERS resizes and (b) `reposition` short-circuits to an instant
move when `not isVisible()`. Showing the window was not enough either. What actually discriminates:
force the window 430 px off-target and call `reposition` both ways — `animated=True` leaves it
**430 px off on the frame the user sees**, `animated=False` snaps to 0 px — then spy on the method
to prove each path picks the right mode (collapse/expand → `False`, edge change/drag release →
`True`). **A green assertion that never exercised the failing path is not evidence; make the test
prove the two candidate behaviours DIFFER before trusting that it caught anything.**

- **The arrow could get stuck on its hardcoded glyph.** `_arrow()` only ran when Python pushed
  `setEdge`/`setCollapsed`, while the markup ships a literal `&#9654;` (▶) — so a missed call left
  it pointing the wrong way with nothing to correct it. It now runs once at page init.
- **Two round-12 assertions were STALE, not regressions** — round 13 replaced the flat `.16` veil
  with the GlassSurface gradient and *deliberately added* a CSS `border-radius` to match
  `SetWindowRgn`. Re-derived them against the current design (fill must stay see-through; the CSS
  radius must EQUAL `_CARD_RADIUS`, or the window clip and the page rounding disagree at the
  corners) instead of leaving two permanent red marks. **A suite that still encodes the previous
  design fails on correct output — and would pass on wrong output.**
- **Verified:** `py_compile` clean; page JS `node --check` clean (⚠️ extract it to a REAL file —
  native node cannot open a `<(…)` process-substitution fd, the same class as `/dev/stdin`);
  **91 checks green across all three suites** (round 12 20/20 after the re-derivation, round 13
  34/34, round 14 37/37).
- **Honest caveat, unchanged:** the OS compositor's real behaviour over a running game cannot be
  produced in this environment — only the user's screen settles which of the two surfaces they
  prefer. **Still NOT published — LOCAL install only; say "פרסם" to ship.**

### Round 13 — the GlassSurface look (minus the one part that is impossible), + six real position/drag/stability bugs (2026-08-16, LOCAL, NOT published)

User: **"אני רוצה כזה https://reactbits.dev/components/glass-surface אבל קצת מטושטשת"** and
**"ותקן הרבה באגים של המיקום, הזזה, יציבות החלון ועוד"**.

- **🔴🔴 THE REFRACTION HALF OF GlassSurface IS IMPOSSIBLE HERE, and it is worth knowing why.**
  React Bits' GlassSurface is `backdrop-filter: url(#feTurbulence+feDisplacementMap)` — it refracts
  **the page content behind the element**. Our overlay is a transparent window floating over a
  GAME, and **`backdrop-filter` cannot see past its own window**: the backdrop root is the page,
  and the page is empty behind the card. The proof is that Electron has a long-standing
  [feature request](https://github.com/electron/electron/issues/30412) asking for exactly this
  (backdrop-filter against a transparent window, to recreate acrylic) — it does not exist. The blur
  of the game can ONLY come from the OS compositor, which is what round 12 wired up.
  ⇒ **Never add an SVG displacement filter to this overlay** — it would refract nothing and, under
  this launcher's `--disable-gpu-compositing`, cost a CPU rasterization every paint *while a game
  is running*. (The `liquid-glass` skill's launcher caveat, taken to its conclusion.)
- **What IS shippable, and is what actually makes a surface read as glass:** a frosted body
  gradient, a **specular rim** (`inset 0 0 0 1px`), a **lit top edge**, a soft **bottom inner
  shade**, a static **grain** layer (`feTurbulence` as a data-URI background, `mix-blend-mode:
  overlay`, `opacity .035` — no animation), and real rounded corners.
- **🔑 "קצת מטושטשת" has exactly ONE lever: the acrylic TINT alpha.** Windows does not expose the
  acrylic blur RADIUS through `SetWindowCompositionAttribute`, so "blurrier" is expressed as a
  heavier neutral tint over the already-blurred backdrop: `_ACCENT_TINT` `0x2A → 0x3E`. The page's
  own veil is kept light (`rgba(18,18,21,.20)`) so the two never stack into a dark card.
- **🔴 Rounded corners needed a WINDOW REGION, not CSS.** Windows applies the acrylic to the whole
  window **rectangle**, so a CSS `border-radius` rounds only what we paint and leaves the blurred
  surface square behind it — the "weird square edges" from round 10. `_round_window()`
  (`CreateRoundRectRgn` + `SetWindowRgn`) clips the window itself; re-applied from `resizeEvent`
  and `_reflow`, because a stale region from the previous size crops the new content. The CSS radii
  and `_CARD_RADIUS`/`_PILL_RADIUS` must stay equal (asserted in the suite).
  ⚠️ `SetWindowRgn` **takes ownership** of the region — never `DeleteObject` it yourself.

**The six bugs — all were live in the shipped build:**
1. **Multi-monitor: docking always used `primaryScreen()`.** Dropping the panel on monitor 2 yanked
   it back to monitor 1 on release, on any re-dock, and on every show. Now `_screen_for_point()`
   (`QApplication.screenAt`, primary as fallback) picks the monitor the panel is actually on.
2. **Dragging was unbounded** — the window could be pushed entirely off every screen and lost (the
   hotkey would "work" while nothing appeared). `_clamp_on_screen()` clamps against the **union of
   all screens**, keeping 24 px reachable.
3. **🔴🔴 A drag whose `mouseup` never arrived chased the cursor FOREVER.** The page reports
   `dragEnd` from its own `mouseup`, which is lost if the page reloads mid-drag, the hotkey hides
   the window, or the game grabs the pointer — and the 16 ms timer then kept moving the window with
   no way to stop it. `_drag_tick` now self-finishes when the primary button is no longer held.
   **🔑 The guard must read GLOBAL key state, not `QApplication.mouseButtons()`** — Qt only knows
   about events it received, and this window is `WA_ShowWithoutActivating` while a game may hold the
   pointer, so a Qt-based guard would cut a LEGITIMATE drag short. Uses `GetAsyncKeyState` (the same
   call the hotkey capture already trusts), honouring a swapped-button mouse, and **fails OPEN**
   (returns "held") if the probe throws — never strand a drag.
4. **Two animations fighting over `pos`** — the 280 ms show-slide and the 220 ms snap-glide could
   run together (e.g. a dock change right after a show), which reads as stutter or a wrong landing.
   `_stop_pos_anims()` guarantees a single owner, and the non-animated path stops pending glides too
   (a queued glide would otherwise silently undo a `move()`).
5. **`reposition()` during a drag fought the drag** — now inert while `_dragging`.
6. **A game going fullscreen CHANGES SCREEN GEOMETRY**, and the overlay is shown precisely then, so
   it kept the old resolution's coordinates and could sit half (or entirely) off-screen. Re-docks on
   `screenAdded`/`screenRemoved`/`primaryScreenChanged`/`geometryChanged`/`availableGeometryChanged`,
   debounced 350 ms so a burst costs one move.

- **⚠️ THE SUITE FAILED TWICE AND BOTH WERE THE HARNESS — but the failure was itself the evidence.**
  `_on_drag_start()` followed by `pump()` let the 16 ms tick fire, and with no button held in a
  headless run the new guard correctly self-finished — so "drag armed" and "reposition is inert
  during a drag" both failed *because the fix works*. Assert BEFORE pumping. Same family as the
  round-12 artifacts: **a red result needs the same scrutiny as a green one.**
- **Verified: 34/34 offscreen** (`scratchpad/smoke_round13.py`) — the glass signature, matching
  radii, the heavier neutral tint, clamping at both extremes, the stuck-drag guard using global key
  state, single-animation ownership, drag/reposition exclusion, the screen-change timer, plus the
  round-12 regressions (layered, `windowOpacity` 1.0, docking, collapse/expand, page setters).
- ⚠️ Unchanged caveat: DWM blur cannot be produced headlessly. **NOT published — LOCAL only.**

### Round 12 — 🔴🔴 the black background was a MISMATCHED transparency recipe, and `set_edge` never moved the window (2026-08-16, LOCAL, NOT published)

Round 11 shipped and the user reported, with a screenshot: **"הרקע הוא שחור ולא מטושטש"** and
**"וגם יש בעיות לגבי המעברים בלי שמאל וימין במיקום וגם למעלה ולמטה"**. Both were real, and the
first one is the most transferable finding in this whole 12-round effort.

- **🔴🔴 THE ROOT CAUSE — ON WINDOWS THERE ARE TWO BLUR RECIPES AND EACH HAS TWO HALVES; WE HAD ONE
  HALF OF EACH.** They are not interchangeable:
  | recipe | window must be | API |
  |---|---|---|
  | Mica / Acrylic backdrop | **NOT** layered (no `WA_TranslucentBackground`) | `DwmSetWindowAttribute` + `DWMWA_SYSTEMBACKDROP_TYPE` |
  | Acrylic blur-behind | **layered**, real per-pixel alpha (`WA_TranslucentBackground`) | `SetWindowCompositionAttribute` + `ACCENT_ENABLE_ACRYLICBLURBEHIND` |
  Round 7 correctly established that `WA_TranslucentBackground` forces `WS_EX_LAYERED` and that a
  layered window cannot compose with `DWMWA_SYSTEMBACKDROP_TYPE` — **and then drew the wrong
  conclusion**: it dropped `WA_TranslucentBackground` and kept the DWM backdrop call. But a Qt
  window that is not `WA_TranslucentBackground` has an **OPAQUE client area**, and a
  `QWebEngineView` paints **solid black** wherever the page is transparent. Hence a perfectly
  reported "success" from every DWM call and a **black rectangle** on screen. Round 4 had made the
  mirror-image mistake — calling the *acrylic* API on the *non*-transparent window — and concluded
  "the API does nothing". **Fix: commit fully to the layered recipe** — `WA_TranslucentBackground`
  back on the top-level window, and `_set_accent()` (`SetWindowCompositionAttribute`,
  `ACCENT_ENABLE_ACRYLICBLURBEHIND`, with `ACCENT_ENABLE_BLURBEHIND` as the fallback on builds that
  refuse it). `windowOpacity` is still never touched — every fade lives in the page's CSS, so the
  round-7 guarantee holds **by construction**.
- **The CSS veil had to come DOWN, not up.** Acrylic carries its own dark tint (`_ACCENT_TINT`
  alpha 0x2A ≈ 16 %); stacking the page's 30 % on top of that is a dark card again, not glass.
  Veil `rgba(16,16,18,.30)` → **`.16`**. Legibility still comes from `text-shadow`, and the tint is
  neutral by construction (`r == g == b`, asserted in the smoke test) so it can never read as a
  coloured panel.
- **🔴 Windows blurs the whole window RECT, not the pixels you paint — so the COLLAPSED state must
  turn the accent OFF.** Left on, the lone 24×48 pill would sit inside a blurred 40×64 rectangle,
  which is exactly the "big frame" collapsing exists to remove. `_reflow()` now sets
  `ACCENT_DISABLED` when collapsed and re-arms acrylic when expanded; with the window layered, the
  transparent area is then genuinely see-through and only the pill remains.
- **Acrylic re-samples what is behind the window on every move → laggy dragging** (documented
  Windows 11 behaviour). `_on_drag_start` downgrades to plain `BLURBEHIND` and `_on_drag_finish`
  restores acrylic — visually indistinguishable for the fraction of a second a drag lasts.
- **🔴 THE SECOND BUG, and it was a one-liner: `set_edge()` called `_reflow()` and never moved the
  window.** The rail flipped to the correct side and the panel stayed exactly where it was, so
  every left/right and top/bottom transition looked broken. It only ever appeared to work because
  `_toggle_collapsed()` happens to call `reposition()` right afterwards. `set_edge()` now calls
  `reposition(animated=True)` itself; `expand()` got the same treatment (its size changes, so the
  edge-anchored position must be recomputed).
- **⚠️ MY OWN TEST LIED TWICE, in the two documented ways.** (a) The "no CSS border-radius" check
  matched the **comment** that mentions `border-radius`, not a rule — strip comments before
  asserting on CSS. (b) The first `set_edge("right")` **early-returns** when nothing changed, so
  the panel sat at `(0,0)` and the edge matrix "passed" while proving nothing about docking; the
  harness had also skipped the `reposition()` that **every production show path does first** (three
  call sites). Fixed by repositioning before showing and asserting the right edge lands at
  `screen.right − w − margin`. **A green suite that never exercised the real call order is not
  evidence** — same family as the round-9 measurement artifacts.
- **Verified: 20/20 offscreen** (`scratchpad/smoke_round12.py`) — layered + frameless, neutral
  tint, veil `.16`, docked right at `x=319 = 799−470−10`, all four edges distinct
  (`left 10 · right 319 · top 10 · bottom 633`), collapse `470×156 ↔ 40×64`, `windowOpacity`
  exactly `1.0` through a full drag, all five page setters defined. `py_compile` clean, page JS
  `node --check` clean.
- **⚠️ Unchanged honest caveat: DWM's real blur cannot be produced in this environment.** The
  recipe is now internally consistent and every measurable property checks out, but only the
  user's own screen settles whether it finally reads as frosted glass. **NOT published — LOCAL
  install only; say "פרסם" to ship.**

### Round 11 — colourless glass, smaller type, a real drag fix, and collapse-to-just-the-pill (2026-08-16, LOCAL, NOT published)

User feedback on the round-10 build, with a screenshot: **"אני רוצה חלון צף בלי צבע בכלל אלא רק רקע
מטושטש וכיתב · הטקסט גדול מדי · החלונית קופצת והכי באגים של שליטה בחלון והמיקום שלה · בהסתרה הוא
צריך להשאיר רק את המלבן עם החץ"**. Four items, three of them CSS and one a genuine bug.

- **🔴🔴 THE DRAG BUG — a page's `mousemove` is the WRONG source for a window move, twice over.**
  The page was sending `e.screenX/screenY` to Python on every mousemove. Two independent defects:
  (a) those are **CSS pixels**, which disagree with Qt's device-independent coordinates on a scaled
  display, so the window **drifts away from the cursor** as you drag; (b) `mousemove` stops firing
  the instant the pointer **outruns the moving window**, so a fast drag freezes until the cursor
  catches up — the reported "קופצת". **Fix: the page reports only `dragStart`/`dragEnd`; Python
  polls `QCursor.pos()` on a 16 ms `QTimer`.** Scale-independent, never loses the pointer, and one
  source of truth. `dragMove` is kept as an explicit no-op so a stale cached page can't error.
  **UNIVERSAL: when a web page drives a NATIVE window's position, take the coordinates from the
  windowing system, not from the DOM event.**
- **🔴 The second half of "jumping": releasing a drag TELEPORTED the window to the snapped edge**
  (and so did collapsing). `reposition(animated=True)` now glides with the spring curve over
  220 ms, and grabbing the pill mid-glide **stops the animation first** so the two can't fight.
  Verified with a real-cursor test: the window tracks a 60,40 px cursor move exactly 1:1, the
  release starts an animation instead of moving, and a re-grab cancels it.
- **Colourless by construction.** The card's `rgba(25,20,45,.65)` purple-navy became a **neutral
  `rgba(16,16,18,.30)`** (r≈g≈b — no hue at all), the rail lost its own dark fill and separator
  line, the CSS `border-radius`/`border`/`box-shadow` were dropped in favour of **DWM's own rounded
  window + Acrylic + shadow**, and the answer's section heads went from cyan to plain **bold
  white**. Legibility over pure blur now comes from `text-shadow`, not from a background fill —
  that is what lets the panel be colourless at all. `_answer_html` emits **classes only, never
  inline colour**.
  ⚠️ Dropping the CSS radius is deliberate: a rounded card inside a *rectangular* acrylic surface is
  exactly what produces the "weird square edges" — the window must be the rounded surface.
- **Type scaled down** 26/15/17px → **13/11.5/10px**, rail 70→52, pill 32×65→24×48, panel
  586×236 → **470×156**. Also killed the visible scrollbar thumb (`::-webkit-scrollbar{display:none}`)
  — on a colourless panel it read as a stray floating bar, which is exactly what the screenshot showed.
- **Collapse now shrinks the WINDOW to the pill alone** (`_PILL_W/H = 40×64`): `.collapsed` sets the
  card background to transparent and hides `.content` **and** the ✕/↻ buttons, so there is no frame
  left to see. Only possible because the window itself resizes, not just the page.
- **Verified by measurement, not by eye** (the round-9 discipline): a DOM probe confirmed all **8**
  arrow cases (4 edges × collapsed/expanded), `collapsed` → ✕ `display:none` + background
  `rgba(0,0,0,0)` + content `none`, expanded background `rgba(16,16,18,0.3)`, and font sizes
  13/11.5/10px. The 25-check panel smoke test and the 6-check drag test both ALL_OK.

### Round 10 — the overlay became an HTML/CSS page; hand-painting it was the wrong MEDIUM (2026-08-16, LOCAL build `20260815230758`, DEV 248, NOT published)

Round 9 fixed the loop and shipped a measurably better panel. The user still said **"זה עדיין נראה
גרוע"**, rejected a 9-slice image-asset proposal too (**"גם לא"**), and then supplied **complete
HTML + CSS** for exactly the window they want. That settles it: after ten rounds, the problem was
never the values — **QPainter was the wrong tool for a glassmorphism panel.** CSS gives real
`border-radius`, `box-shadow`, `backdrop-filter` and layered translucency for free, and the design
becomes a stylesheet the user can hand over directly instead of paint code I have to interpret.

- **The split: Python keeps the WINDOW, the page owns the LOOK.** `_OverlayPanel` is now a
  frameless `QWidget` holding one `QWebEngineView` on `copilot_overlay.html`; every proven
  behaviour — edge docking, `_snap_to_nearest_edge`, `_persist_position`, long-press-drag, the
  spring slide-in, the hotkey — is untouched. The page reports intent over a `QWebChannel` object
  named `overlay` (`close/refresh/toggleCollapse/dragStart/dragMove(x,y)/dragEnd`) and Python
  drives content back with `runJavaScript("window.setTitle/setBody/setHint/setEdge/setCollapsed/
  setShown/setDimmed(...)")`. **Deleted ~430 lines of paint code** (`_GlassCard`'s panel role,
  `_HandleTab`, `_BevelButton`, `_wrap_rtl`/`_title_html`/`_format_answer`/`_format_error`,
  `_glass_shadow`, the body-height animator). `_GlassCard` survives only for the hotkey-capture
  dialog.
- **🔴🔴 THE BUG THE RENDER-AND-LOOK LOOP CAUGHT, and it would have shipped a permanently blank
  overlay: `new QWebChannel(qt.webChannelTransport, …)` sat at the TOP of the page's IIFE.** When
  the transport isn't ready it throws `ReferenceError: qt is not defined` — which kills the rest of
  the IIFE, so **every `window.set*` setter below it is never defined**, `setShown` never runs, the
  card stays in its initial `gone` (opacity 0) state, and the user gets a correctly-sized window
  rendering nothing, with no error they can see. Fix: **define the setters FIRST, then wrap the
  channel handshake in its own try/catch** — a dead bridge now costs two dead buttons instead of
  the whole panel. **UNIVERSAL: in a page whose rendering API is called from the host, never let
  the host-bridge handshake run before the rendering API is defined — one throw takes down
  everything after it in the same scope.**
- **🔴 Same class, one level up: the page starts `gone` so the first `show_animated()` FADES in —
  which means any plain `.show()` would leave it invisible.** All four production call sites use
  `show_animated()`, but `showEvent` now also calls `setShown(true)`, so no future path can
  reintroduce it.
- **🔴 A `QGraphicsOpacityEffect` is now forbidden on this window** — it renders its whole subtree
  into an offscreen pixmap and a `QWebEngineView` draws through a separate compositor, so the panel
  can come out blank. All fades moved into CSS (`.gone`/`.dimmed` + a `.2s` opacity transition);
  `hide_animated` lets that transition play then hides the window on a 210 ms timer. The round-7
  `WS_EX_LAYERED` guarantee is now true **by construction** — nothing touches `windowOpacity` at
  all (still regression-tested: it reads exactly 1.0 through a full drag).
- **🔴🔴 TWO CAPTURE METHODS THAT SILENTLY LIE ABOUT A WEB VIEW — both cost a round:**
  `QWidget.grab()` on a `QWebEngineView` returns **fully transparent** (measured rgba 0,0,0,0
  everywhere) because the page never reaches the widget's backing store; and
  `QScreen.grabWindow(0)` over a translucent frameless Qt window under DWM returns what is
  *behind* it plus a dark wash, not the panel. **What works: paint the demo backdrop INSIDE the
  page (one opaque window, no cross-window alpha) and grab that window** — the card's own
  translucency still reads correctly because it composites against that backdrop in-page.
  **And when pixels are ambiguous, ask the DOM instead**: a `getBoundingClientRect`/`Range` probe
  reported the card as 550×202 at (18,17), radius 18px, sidebar 71px, setters `function/function`
  — data, not squinting. That probe is also what proved the try/catch fix.
- **⚠️ My own screenshot reading was WRONG once and the measurement corrected it.** The numbered
  steps looked like the "1." had landed on the LEFT (wrong for RTL). A `Range` rect settled it:
  number at x 531-542, first Hebrew word at 492-527 ⇒ **the number is rightmost, correct**. Same
  lesson as [[hebrew-screenshot-transcription-trap]] — measure, don't eyeball.
- **Sizing is fixed, not content-driven**: `_PANEL_W/H = 586×236`, `_RAIL_W = 106` (the panel plus
  the 18px body padding the CSS `box-shadow` needs). Collapsing hides `.content` and resizes the
  window; `QLayout.SetFixedSize` keeps the window tracking it. The long AI answer scrolls inside
  `.body` with a slim custom scrollbar instead of growing the window.
- **The arrow is computed from BOTH dock side and state** (`contentOnRight = edge !== 'right'`), so
  it always points the way the panel will move — outward to reveal, back toward its edge to tuck
  away. Verified on all four edges.
- **`copilot_overlay.html` ships fine**: it rides the spec's `('translation_manager',
  'translation_manager')` datas entry, `_keep()` doesn't filter `.html`, and it was confirmed
  present in `dist/.../qt_shell/` after the build. Resolution mirrors `_brand_icon_path` —
  `_MEIPASS` first, then `__file__` — rather than trusting `__file__` in a frozen build.
- **Verified:** `py_compile` clean, page JS `node --check` clean, and a 25-check end-to-end smoke
  test against the REAL panel (load, queued-JS flush, title/body/hint delivery, expand/collapse
  window widths 586↔106, all 4 edges, bridge→Python callbacks, drag dim/undim with
  `windowOpacity == 1.0` throughout, error summary+detail, loading state, hide/show) — ALL_OK.
  Built + installed LOCALLY. **NOT published.**
- **⚠️ Honest caveat, unchanged from every round:** DWM Acrylic's real blur over a running game
  cannot be produced in this environment. `backdrop-filter` blurs only what is behind the element
  *within the page*, so the desktop blur must come from the OS — only the user's own screen
  settles whether it now reads as genuine frosted glass.

### Round 9 — "תמיד אני מקבל תוצאות גרועים": the LOOP was the bug, and closing it found three real defects in one sitting (2026-08-16, LOCAL build `20260815221533`, DEV 247)

Eight rounds of "make it premium" had produced eight rejections. The user finally asked the right
question — *how do we solve this, I always get bad results* — and the answer was not a colour value.

- **🔴🔴 THE ACTUAL ROOT CAUSE: a blind 10-minute loop with a 1-bit feedback channel.** Each round
  was: write paint code → assert pixels offscreen → composite over SYNTHETIC bokeh → build+install
  (~10 min) → user says "bad". I had **never once looked at the panel**, and "bad" carries no
  information about *which* of a dozen simultaneous choices was wrong. No design converges on that.
  **Two fixes, and they are the transferable part of this round:**
  1. **`dev_overlay.py` (repo root, NEW)** — runs ONLY the overlay, on the real desktop, with real
     DWM Acrylic. No launcher build, no installer, no UAC. A parent process watches the source and
     restarts the child on any edit, so **a paint tweak is on the user's screen in ~2s instead of
     ~10min**; a small always-on-top control window cycles every state (4 dock edges, collapse,
     loading / short / long / error) so no state needs a code change to inspect.
     Run: `.venv\Scripts\python.exe dev_overlay.py`.
  2. **RENDER THE WIDGET AND READ THE PNG.** `preview_bezel.py` grabs the real card, composites it
     over synthetic bokeh, saves a PNG — and I open it with the Read tool. That is the capability I
     had been failing to use: **I can see images.** Every defect below was found by looking, not by
     reasoning, and each was fixed and re-checked in seconds.
- **🔴🔴 DEFECT 1 — the "glass" was tinted METAL, opaque (measured alpha 255).** The shell was
  filled opaque across the whole card and the low-alpha tint laid ON TOP of it. **A pane must be a
  genuine HOLE**: compute the pane path first, fill the metal as `shell.subtracted(pane)`, then tint
  the hole. Alpha 255 → 89 (34 % opaque), bokeh visibly through it.
  **UNIVERSAL: painting a translucent colour over an opaque fill never produces transparency, only a
  tint — the surface underneath has to be cut away.**
- **🔴🔴 DEFECT 2 — the card's own DROP SHADOW was veiling the glass by +45 alpha.** Once the pane is
  a hole, the surrounding opaque metal's `QGraphicsDropShadowEffect` spills **INWARD** through it.
  Isolated by measuring with and without the effect: **median pane alpha 134 → 89**. And CLAUDE.md
  had already recorded that this shadow draws *nothing* outward (with `SetFixedSize` the window is
  exactly the card's size, so it is fully clipped) — so it cost a render pass, produced zero visible
  separation, and was single-handedly making the glass ~18 % more opaque, which is **the user's #1
  recurring complaint across four rounds**. Removed from both the overlay card and the capture
  dialog; the bright 1px rim pen is what lifts the panel off the background.
  **UNIVERSAL: a drop shadow on a surface that contains a transparent CUT-OUT bleeds into the
  cut-out. If a panel is meant to be see-through, measure its alpha with the effect disabled before
  trusting any other opacity tuning.**
- **🔴 DEFECT 3 — a "thin 3 % bright edge" was half the visible frame.** The metal gradient runs over
  the whole card height (~196 px) but the metal is only *visible* in a ~15 px band at top/bottom, so
  a 3 % stop ≈ 6 px ≈ 40 % of the frame there — which is why it read as chrome rather than graphite,
  in both this round and round 8. Fix: the gradient body is now uniformly dark and **every bright
  edge is a 1px PEN**. **UNIVERSAL: a gradient stop is a fraction of the whole geometry, not of the
  part you can see — for a frame, edge highlights belong in pens, never in stops.**
- **`✕` / `↻` rendered as TOFU BOXES** in the preview — a font glyph for U+2715/U+21BB is not
  guaranteed in whatever face Qt resolves. Redrawn as **geometry** (two capped strokes; an open ring
  + arrowhead), which also keeps the stroke thin and even instead of inheriting a bold font's weight.
  Same reasoning as the sapphire's arrow. **UNIVERSAL: any glyph outside basic Latin that the design
  depends on should be drawn, not typed.**
- **Brushed grain is what makes metal read as metal** — `_brush()` draws ~150 precomputed hairlines
  (deterministic, so the grain is stable across repaints rather than shimmering) clipped to the metal
  path. A gradient alone can only ever be smooth plastic; this directly answers "לא צבעים רגילים".
- **Reference-matching changes:** chamfered/octagonal → **rounded** corners everywhere (radius 22);
  the sapphire is a true **ellipse** with a radial crown core + off-centre glint + bottom bounce
  (a flat top-to-bottom ramp reads as coloured plastic); the ✕/↻ are **engraved** into the faceplate
  (a dark incision + a bright lip) with no chrome of their own; title text cream-gold `#f2e6cb` at
  13.5px, hint `#ccd3e6`. The three now-dead helpers (`_chamfer_path`, `_chamfer_points`,
  `_asymmetric_rounded_path`) and the `_big_side` state were deleted rather than left to confuse a
  future round.
- **⚠️ THREE MORE TEST-ARTIFACT FAILURES, all of the same family as round 8's** — each looked like a
  code bug and was the measurement being wrong: the ring-scan `skip=32` was tuned for the octagon and
  clipped away **both** bands the check existed to find (rounded corners need only ~10); the stone
  sample took the geometric centre, which is **exactly where the white arrow is drawn**; and the pane
  sample hit text + its legibility shadow. The checks were also encoding the OLD design — "the ring
  is a wide gradient" stopped being true the moment banding moved into pens, so it now measures a
  gentle gradient **plus** grain (a horizontal scan — the grain runs vertically) and the pane is
  measured with the text widgets hidden. **UNIVERSAL: when a redesign lands, re-derive what each
  assertion is actually claiming — a suite that encodes the previous design fails on correct output
  and, worse, passes on incorrect output.**
- **Verified:** 30/30 pixel checks pass · `py_compile` clean · long-answer and collapsed states
  rendered and eyeballed (panel grows 196→279 with the pane in register; collapsed is a 74px milled
  strip with the stone still grabbable) · the round-7 `WS_EX_LAYERED` guarantee regression-tested
  (`windowOpacity` stays exactly 1.0 through drag and both animations).
- **Honest caveat, unchanged:** DWM Acrylic's real blur cannot be produced in this environment, so
  only the user's screen settles the final look — but that is now a 2-second check via
  `dev_overlay.py` instead of a 10-minute build. **Still NOT published — LOCAL install only.**


## Launcher UX fixes (2026-06-09)

Four launcher fixes shipped together (same re-release as the language switcher):

- **Full drive scan no longer freezes the UI.** `scan_deep` (and `scan_quick`)
  ran synchronously on the Qt GUI thread in `qt_shell/bridge.py`, so
  `game_detector.deep_scan_drives`'s minutes-long filesystem walk locked the
  whole launcher. Both slots now go through the existing `_run_off_thread`
  (scan_deep timeout 900s, scan_quick 120s) — the GUI keeps pumping events and
  the awaiting JS still gets the real result.
- **Tray LEFT-click opens the window.** `qt_shell/tray.py` `_on_activated` only
  handled `DoubleClick`; now handles `Trigger` (single left-click) too →
  `show_and_activate()`. Right-click still shows the context menu.
- **Desktop shortcut / second launch now focuses the existing window.** Root
  cause: `MainWindow.show_and_activate` was a plain method, so the
  single-instance listener's `QMetaObject.invokeMethod(window,
  "show_and_activate", …)` (a by-NAME meta-invoke) silently no-op'd — the tray
  menu worked because it calls the method directly. Fix: decorate it `@Slot()`.
  Also added `_force_foreground()` (ctypes `ShowWindow(SW_RESTORE)` +
  `SetForegroundWindow`) and, in `single_instance.signal_show()`, an
  `AllowSetForegroundWindow(ASFW_ANY)` from the relaunching process so the
  running instance is permitted past Windows focus-stealing prevention.
- **Per-game current language shown.** `_enrich_game_row` (main_eel) now adds
  `currentLanguage` (interface + subtitles) via `game_language.get_state` — a
  no-op for unsupported titles, a ~1-5ms read for spiderman2 / cyberpunk.
  `Game.currentLanguage` added to `types.ts`; `GameDetailPanel` shows a "שפה: …"
  chip in the header and "ממשק/כתוביות כעת: …" in the language switch.


