## 3,000-scenario machine-performance + general audit → 21 fixes (2026-07-17, LOCAL build `20260717103356`, NOT published)

User asked for 500 scenarios on **the user's own machine performance and how the app responds**, then
+500 perf/+500 general, then +2,000 general — each time "rank critical→weak BEFORE fixing", then
"תקן הכל". Audit journals: `scratchpad/{perf_audit,perf_audit_r2,general_audit_2000}.md`. **THE
THEME: `perf_manager` adapted the PYTHON background work beautifully, but the USER-FELT render
(animations/blur) was fixed at FULL and nothing auto-degraded on a weak machine.** All 21 fixed +
verified (py_compile + `tsc -b` clean; behaviour proven by running it, not assumed):

- **🔴 `set_hidden()` was DEAD CODE → the entire tray-RAM feature was OFF.** Defined at
  `perf_manager.py:204`, called by NOBODY. So `state` never became "hidden" (backoff capped at
  "background" 3× instead of 8×) and `is_dormant()` stayed False → **`trim_memory()` NEVER fired
  while sitting in the tray** - holding ~150-300 MB of Chromium behind a running game, the exact
  scenario the module exists for. Now called from `main_window` `closeEvent`(hide) /
  `show_and_activate`(show) / `changeEvent`(minimise) via `_report_hidden()`. **Also fixed
  `set_hidden` not invalidating the 2s sense cache** (the new state took up to 2s to be observed -
  i.e. the very tick that should back off still used the old state). VERIFIED: visible 180s/not-
  dormant → tray **480s + dormant + trim issued** → restore 180s.
- **🔴 `launcher.log` had NO rotation** (`basicConfig(filename=…, filemode="a")`, no
  `RotatingFileHandler` anywhere) → unbounded growth for the life of an install. Now 2 MB × 3.
- **🔴 `crash_reporter._log_tail()` read the ENTIRE log into RAM** (`read_text().splitlines()`) to
  keep 50 lines - **while the app is crashing, often from memory pressure**: the reporter could
  amplify the crash it reports. Now seeks the last 64 KB. **Testing it surfaced a 2nd, pre-existing
  bug: `[:2000]` truncated from the FRONT, discarding the newest lines = the ones right before the
  crash** → `[-2000:]`. VERIFIED: 21.9 MB log → 2000 chars in 0.73s, keeps the last line.
- **🔴 `closeEvent`'s error fallback was the DESTRUCTIVE branch** - `except → pref=None` fell
  through to the real-exit path, so a transient prefs read failure (an AV lock on
  launcher_prefs.json) turned a click on X into "kill the app" (taking any in-flight download with
  it) - while minimise is the DEFAULT. Now defaults to `"minimize"`.
- **🔴 GPU SAFE MODE (self-healing white screen).** We force `--ignore-gpu-blocklist` +
  `--enable-gpu-rasterization` for everyone; on a broken/ancient/VM/RDP GPU that can kill the GPU
  process every launch → a permanently WHITE window, and the user can't reach Settings to turn
  accel off *because the settings are inside the window that won't render*. Now a
  `boot_incomplete.flag` sentinel is dropped before the window is built and cleared on
  `loadFinished(ok)`; a boot that never painted makes the NEXT launch fall back to CPU
  compositing automatically. Self-healing both ways.
- **🔴 swr background refresh was DEAD under Qt + leaked `_inflight` FOREVER.**
  `_maybe_refresh_bg` did `gevent.spawn`, but no gevent hub is pumped under the Qt build → the
  greenlet never ran → `_bg_worker`'s `finally` never popped `_inflight[key]` → that key could
  never refresh again for the process lifetime (the `except→Thread` fallback never fired because
  `import gevent` succeeds). Now transport-aware `_use_gevent()` (`PySide6 in sys.modules` → real
  thread), same pattern as `loopback.py`.
- **🔴 AUTO-DEGRADE on a weak machine (the "never smooth" root).** `gpuInfo` already DETECTED
  software rendering (SwiftShader) and merely logged it; `themePrefs` read only localStorage, so a
  low-end/software-rendered host ran the FULL animation + `backdrop-filter: blur(18px)` load by
  default. Now `shouldAutoReduce()` = software-GPU **or** `tier=="low"` (new `get_machine_profile`
  bridge slot → `perf_manager.hardware()`) **or** the OS `prefers-reduced-motion` (was ignored
  outright); it drives BOTH `getAnims()` and a new `autoBackdrop()` → `data-backdrop="none"` (the
  solid look, zero per-paint blur - `reduce-anims` never covered backdrop-filter). An EXPLICIT user
  choice always wins.
- **`scan_deep`/`scan_quick` → `_safe_off_thread`** (were `_run_off_thread`): a slow HDD with many
  drives can exceed 900s → the raising @Slot does NOT reject the JS promise → "סורק…" spun forever.
- **`_cpu_percent()` returned 0.0 on its FIRST call** (needs 2 samples) → the first
  `poll_multiplier()` ran at full cadence and the first `should_defer_heavy()` said False, exactly
  during boot/game-load. Now primed at import. VERIFIED: first read 79.8% instead of a fake 0.0.
- **Battery awareness (new):** `_on_battery()` via `GetSystemPowerStatus` → `poll_multiplier` ×2
  (active) / ×3 (background) on DC. We sensed CPU but never power state.
- **QtWebEngine HTTP cache capped** at 96 MB (`setHttpCacheMaximumSize`; was Qt's unbounded default).
- **swr**: compact JSON (`separators`, was `indent=2` = ~30-40% inflation rewritten every tick);
  negative-age guard (a backward clock jump made entries look eternally fresh → never refreshed);
  `_persist_now` catches broad exceptions (was OSError-only → a `json.dumps` TypeError silently
  killed persistence for the session); **`progress_keys()` capped at 8 MRU** (was unbounded - every
  game card ever opened added a permanent per-tick HTTP request).
- **`single_instance`**: mutex/`OpenEventW` failures now LOG (both were silent - a fail-open guard
  that lets two launchers write the same state, and a shortcut click that does nothing).
- **deeplink `read_pending`**: ignores a >60s-old pending file (debris from a handoff whose signal
  never landed made a LATER launch jump to a stale game card).
- **NOT fixed (deliberate, reported):** low-RAM boot pre-flight (can't meaningfully refuse to
  boot); freezing frontend animations when the MACHINE is pegged (Chromium already throttles a
  backgrounded window); `should_defer_heavy` before a heavy mod apply (user-initiated); the poller
  re-tuning only at tick boundaries (inherent to QTimer); trim→soft-fault lag (inherent tradeoff).

A Windows desktop launcher for Hebrew game-translation mods. Built with
**Eel** (Python ↔ Chromium bridge), a React + Vite frontend, and packaged
as a standalone installer via PyInstaller + Inno Setup.

The launcher fetches a games catalog from the public translation hub
API, displays available titles, downloads the matching translation
archive, and copies it into the game's mod folder.


## 700-scenario multi-agent audit + fixes → bumped to v1.1.0 (2026-07-17, LOCAL build `20260716231731`, NOT published)

User asked to "run agents with 700 new scenarios (expected + unexpected) and find any bug/error/
malfunction or convenience add." Ran **11 background sonnet agents** (~70 scenarios each = 700+),
each tracing one dimension against the REAL code + returning provable file:line findings; then I
**verified every candidate myself (Opus) before fixing** (agent LQA false-positive rate is high - the
prior 500-run lesson). Candidate journal: `scratchpad/audit_findings.md`. **15 confirmed bugs fixed**
(py_compile + `tsc -b` clean; built + installed LOCALLY; NOT published):
- **[CRITICAL data-integrity] WD2 wrote the game's own `.fat` archive INDEX non-atomically**
  (`watchdogs2_mod.py` `_deploy_one` + `_revert_one`) → a crash/AV-lock mid-write can make the game
  fail to load the whole archive. Added `_atomic_write_bytes` (temp+fsync+os.replace) for both writes.
- **[DRM hole, offline] `games_catalog.CatalogGame` had NO price field** → a paid download-mod (Anno/
  GTAV ₪53) resolved to price 0 = FREE on the cold bundled-catalog fallback (Supabase down). Added
  `price_cents` (Anno/GTAV=5300) + `_game_price_cents` now reads `priceCents` OR `price_cents`.
- **[freeze/crash class, confirmed by 3 agents] 8 `bridge.py` @Slots ran SYNC on the GUI thread** →
  froze the window up to ~8s or crashed the @Slot on a `TimeoutError`. Off-threaded: `set_game_language`
  / `restore_game_language` (→ `_safe_off_thread`+fallback), `set_game_mod_installed` / `clear_game_mod_cache`
  (→ `_run_off_thread` 300s), `get_live_progress`, `download_and_install_game_mod` pre-flight owns-check,
  `auth_owns_game` + `auth_get_access_token` (→ `_safe_off_thread` fail-closed/None, no more @Slot-raise crash).
- **GTAV "clear cache" never worked in the Qt build** - `clear_native_mod_cache` routed GTAV through the
  eel wrapper `remove_gtav_mod` (a `gevent.spawn` the Qt build never pumps) → forever "ההסרה רצה ברקע".
  Routed to the SYNC `_run_gtav_remove` (clear_native is already off-thread). (`main_eel.py`)
- **`clear_game_mod_cache` wiped the local cache/state even when the game-folder revert failed** (game
  running) - now REVERT-FIRST: bail before the `rmtree` when a file is stuck. (`game_mod.py`)
- **`_lang_mod_installed` returned None for SM2/W3** → "auto" language forced the Arabic slot even when
  the mod was NOT installed (showed untranslated base Arabic). Special-cased `_SM2_ID`/`_W3_ID` → `_mod_state`.
- **Auth "silent sign-out on a transient error" class (3 fixes, some were CLAUDE.md known-open):**
  `_claim_device_if_free` returned False on BOTH a lost race AND a network blip → false "signed in
  elsewhere". Now tri-state (`bool|None`; blip → 'unknown', never signs out). `storage._load_or_create_key`
  minted a NEW Fernet key on a transient keyring READ error → clobbered the real key → permanent sign-out;
  now it propagates instead, and `TokenStore.load` distinguishes transient (keyring/OS → keep session) from
  genuine corruption (InvalidToken/JSON → clear). `_store_token_from_response` swallows a post-refresh
  `store.save` RuntimeError (the token is already rotated server-side → a raise = permanent invalid_grant
  sign-out).
- **App-icon picker:** false success toast (didn't check `r.ok`), wrong fallback variant (`5g-circle-round`
  → `brand`), and a **PowerShell single-quote injection** in `repoint_shortcuts` (a path with `'` truncated
  the command) - now `'`→`''` escaped. `get_custom_titlebar` exception fallback False → True (real default).
- **Notif:** the mod-update notice fired the native OS toast TWICE and the 2nd bypassed mute - removed the
  redundant direct `api.notifyOs` (the `pushNotif`→`notif-pop` path already toasts, mute-respecting).
- **SmartImage + GameCard latched at opacity-0 forever** if a cover failed then a valid URL arrived for the
  same id - reset load/err on `[src]`/`[coverSrc]` change.
- **Self-update check showed a FALSE "✓ up to date" on a timeout** - the `get_launcher_update_info` slot
  fallback now carries an `error` (not None) so the panel shows "בדוק שוב".
- **`show_on_launcher` "hide from launcher" worked for software but never for GAMES** - mapped it in
  `_shape_supabase_game` + filtered in `_games_only` (bundled/None = shown).
- **GTAV install had no `is_writable` pre-flight** (unlike the other 6) → failed after minutes of multi-GB
  work with a raw error. Added the probe + Hebrew message. Fixed a stale "צפיפות" settings header/onboarding
  copy (density control no longer exists).
- **Deferred + reported to the user (verified real but bigger/riskier/judgement):** `update_download_progress`
  + `cache_refreshed` push channels unwired in Qt (S1/S2); `mod_install_progress` carries no game_id (cross-
  game bleed, confirmed x2); save-backup "change backup location" + manual browse are DEAD in Qt (pick_folder_fn
  → a stub, not the QFileDialog bridge); spatial-nav dead-ends at the fold of a long list; 2FA fails OPEN on a
  factor-check blip (security judgement); first-run close-modal never fires in Qt; restart_app has no WSH-blocked
  fallback; perf `set_hidden()` is dead code; swr `cache.json` bypasses resilience.

**Follow-up user requests (same session, all LOCAL):** (a) **App-icon picker simplified** - removed the
6-thumbnail STYLE grid (5c/5e/5g) + the brand card; the picker is now just **circle / rounded-square**, both
showing the **new chrome "HTH" brand badges** (added `brand-square` variant + `brand-square.ico`/`.png`
generated from `לוגו לאייקון/assets/final/חדש/1784218957330_1784219130200.png`; `app_icon.VARIANTS` gained
`"brand-square":("brand","square","round")`; picker `brandForShape(sh)` → `brand`/`brand-square`). The old
5g gradient-M variants stay in VARIANTS (valid) but are no longer offered in the UI. (b) **"המשך ריצה ברקע
בלחיצה על X" is now ON by default** - `launcher_prefs.get_close_behavior()` default None→**"minimize"** (X
keeps the app in the tray, no first-run prompt; `main_qt` binds it as the closeEvent `prefs_getter`).
- **Version bump 1.0.2 → 1.1.0 (MINOR).** User: "we changed the software 90 degrees - big difference from the
  site's 1.0.2." Correct SemVer call = MINOR (new backward-compatible features + many fixes; NOT MAJOR - nothing
  breaks compatibility, self-updates cleanly). Bumped all 5 touchpoints (`main_eel.LAUNCHER_VERSION`,
  `installer.iss` AppVersion, `translation_manager/__init__.__version__`, `frontend/package.json`,
  `App.tsx APP_VERSION`); channel stays `beta`. (`package-lock.json` project version was already stale at 1.0.0,
  not in the display chain - left.) Built BUILD_ID `20260716231731` → `Output/TranslationManager-Setup-1.1.0.exe`
  → installed LOCALLY. **NOT published** - the SITE still serves 1.0.2 until an explicit "פרסם".

---


## Security audit + hardening — website + launcher (2026-07-01)

A rigorous 5-surface security audit (auth/2FA, purchases/PayPal/DRM, data-exposure/RLS/
admin/injection, launcher, secrets) via parallel adversarial subagents, then **every real
finding independently re-verified against the code by the main session** (never trusted an
agent's verdict). **Verdict: NO critical/high account-takeover or payment-forgery holes.** The
two user-priority areas are solid: PayPal money path (amount+currency verified server-side vs
the capture, replay blocked by unique index, IDOR blocked by RLS + service-role-only writes,
`owns_game` server-verified fail-closed) and 2FA (admin TOTP enforced **server-side** in
`api/_lib/auth.ts`, `aal1` rejected with ZERO data before the code; regular users are
single-factor by design). Real cluster was privacy/hardening. **Shipped (deployed +
verified):**

- **M1 — public `user_id` (auth UUID) exposure CLOSED (two layers).** `reviews`/`votes`/
  `review_replies` + the `translation_contributors` view leaked the raw auth UUID to the anon
  key (direct PostgREST) AND the reviews API returned it in JSON. Fix: (a) **code** —
  `reviewsHandler.ts` `shape`/`shapeReply` now emit `isMine` (computed server-side from a
  soft-resolved viewer token via `resolveViewerId`), never the UUID; `userId` kept ONLY on the
  admin `all=1` path. Authed GETs bypass the CDN (Vercel doesn't shared-cache Authorization'd
  requests) + `Vary: Authorization` + `private, no-store`, so `isMine` never leaks across
  viewers. Frontend (`useReviews`/`ReviewSection`/`ReviewReplies`/`ReviewsPage`) switched
  `userId`→`isMine` and now sends the token on the reviews GET. (b) **DB** (migration
  `website/supabase/security_hardening_2026-07-01.sql`) — `revoke select … from anon,
  authenticated` on the 3 tables (reads flow through the service-role API; frontend never reads
  them directly) + recreated `translation_contributors` WITHOUT `user_id`. Verified live: API
  returns `isMine` (no `userId`), anon PostgREST = "permission denied", site still 200.
- **M2 — password change now requires re-auth** (`ProfilePage.tsx`): email accounts must enter
  the current password (verified via `signInWithPassword`) before `updateUser({password})`, so
  an open/hijacked session can't silently reset it. OAuth-only accounts (adding a first
  password) are exempt.
- **L2 — the `launcher_installs` boot-ping is now rate-limited** per IP (`launcher.ts`,
  fail-open telemetry) so nobody can loop random `?device=` to inflate the count / bloat the
  table.
- **L3 — admin MFA check now FAILS CLOSED** (`api/_lib/auth.ts`): if `listFactors` errors or
  throws, return a retryable `503` instead of silently granting admin without the second factor.
- **L4 — rate-limiter can FAIL CLOSED** (`api/_lib/rate.ts` new `{failClosed}` opt), applied to
  the abuse-sensitive writes (review post/reply + translate submit) so a limiter-RPC outage
  can't open an unbounded write flood. Reads/telemetry stay fail-open.
- **L5 — signup no longer confirms email existence** (`AuthContext.tsx`): conditional phrasing
  ("if you already have an account…") kills the enumeration oracle.
- **L7 — public image buckets are content-type-locked** (`covers`, `launcher-screenshots` →
  image mimes only) so a compromised admin can't host HTML/JS on the project CDN.
- **L6 — launcher `MOD_PROXY_BASE` is HTTPS+host-pinned** (`translation_manager/mod_source.py`,
  same posture as the self-updater's URL allowlist) so a hostile env var can't redirect
  integrity-checked mod downloads to an attacker origin. **Ships to installed users on the next
  launcher rebuild** (code-only until then; high attacker bar — needs env control).
- **M3/M4 — Supabase-dashboard items** (can't be done from code): `website/
  SECURITY_SUPABASE_SETTINGS.md` documents them — GoTrue login/MFA/OTP rate-limits + optional
  CAPTCHA (login/MFA bypass the app's limiter → only GoTrue defends them), leaked-password
  protection, refresh-token rotation. **M4:** the platform default that auto-grants `anon`
  SELECT to every FUTURE table is owned by `supabase_admin` (postgres can't alter it — standard
  Supabase design; RLS is the net). **Verified: 100% of anon-readable public tables have RLS
  enabled** — the systemic risk is covered as long as every new table enables RLS.

**Controls confirmed CORRECT (not changed):** no service-role/secret in any client bundle or the
launcher binary (only the public anon key ships; Worker uses `env.GITHUB_TOKEN`), no
`dangerouslySetInnerHTML`/XSS, strong CSP+HSTS, rate-limit IP un-spoofable, SSRF hardened,
self-update SHA-256 mandatory + host allowlist, launcher creds encrypted (keyring+Fernet),
zip-slip guarded, no committed `.env`. Memory [[hub-security-hardening]].

---


## Resilience audit (1,082 scenarios) + crash/freeze fixes (2026-07-01)

A full crash/freeze audit: 15 parallel agents catalogued **1,082 scenarios** (common→rare, per
subsystem) with code-grounded ✅/⚠️/❌ verdicts → root **`RESILIENCE_SCROLL.md`**. Every ❌ was
re-verified against the code (never trusted an agent verdict). Verdict: **~95% resilient** — the
site is wrapped in `safe()` (throw→clean 500) + `ErrorBoundary` + `lazyWithRetry`; the launcher in
a `main_eel`/RPC catch-all + fallbacks + atomic writes. Fixes shipped this pass (all py_compile +
`tsc` clean; **launcher reaches users only on the NEXT rebuild**, website on `vercel --prod`,
worker on `wrangler deploy`):

- **THE Google-login FREEZE (user-reported) — root-caused + fixed.** `auth/loopback.py`
  `LoopbackListener` was built ENTIRELY on gevent (`gevent.event.Event`/`gevent.spawn`/
  `gevent.sleep`). Correct for the Eel build (one hub) but BROKEN for the shipped **Qt build**:
  `login()` runs on a real OS thread and `abort()` is called CROSS-THREAD from the GUI thread; a
  gevent Event is bound to the WORKER thread's hub, so `.set()` from the GUI thread never wakes the
  waiter, and `loop.run_callback` cross-thread (libev — NOT thread-safe) HANGS the GUI thread →
  "בטל וחזור" dead + "העתק קישור" dead + app freezes after a few seconds. **Fix: rewrote
  `LoopbackListener` with native `threading` only** (Thread + Event) — genuine threads under Qt
  (a cross-thread `.set()` wakes `await_code` instantly), transparently cooperative greenlets under
  Eel's `monkey.patch_all()`. `manager.py` now needs no gevent hub at all. Memory
  [[loopback-gevent-qt-freeze]].
- **Launcher white-screen / boot / wedge guards:** `DownloadsView` `(item.size_mb ?? 0).toFixed`
  (a missing field white-screened the WHOLE app via the single ErrorBoundary); `eel.ts call()`
  **timeout** (a slot that throws before invoking its QWebChannel callback no longer wedges the
  Promise forever — generous per-name ceilings: auth_login 240s / scan_deep 960s / default 120s);
  `CloseBehaviorModal` **catch** (an early-boot bridge failure no longer traps the full-screen
  overlay); `useLauncherAuth` **login-flash epoch-guard** (a poll's `authMe()===null` mid-sign-in
  can't clobber the fresh user — the reported flash); `profile.py` off-the-record fallback
  (unwritable storage roots no longer crash boot before the window exists); `main_window` dark page
  background (a dropped GPU frame paints `#050510`, not black — the "black bars"); `swr_cache`
  `list()` snapshots (no "dict changed size"); `paths.py` isinstance guards; `bridge`
  `auth_signup_password` off-thread; WD2 `_revert_one` keeps its backups on a failed truncate
  (revert was becoming a permanent no-op + an ever-growing `.dat`).
- **Website (`vercel --prod`):** `GameCard`/`GameDetailModal` `themes[key] ?? themes.default` (an
  admin-added game with an unknown themeKey no longer white-screens the grid/modal); `translate.ts`
  upsert now checks `error` (no false `{ok:true}` on a DB failure); `paypal.ts` create/capture now
  rate-limited (fail-open — never blocks a real buyer); `TranslationsTab` loadQueue catch;
  `ProgressTab` progress fetch fail-soft (a progress blip no longer blanks the games catalog).
  **Worker (`wrangler deploy`):** `steam_mod_worker/src/index.js` guards `JSON.parse` of the GitHub
  releases + `manifest.json` bodies (malformed → clean 502, not an uncaught SyntaxError).
- **Install-count telemetry VERIFIED working** (`launcher_installs`): a live manual ping to
  `/api/launcher?device=…` → HTTP 200 → row logged (device/version/channel/os) → cleaned. The count
  is currently **0** only because no installed client has yet booted a build carrying `_ping_install`
  (shipped 2026-06-30 PM); it fills in as users self-update. Count active installs:
  `select count(*) from launcher_installs where last_seen > now() - interval '30 days'`.

**Second-pass deep bug-hunt (same day) — 7 more real bugs (find→adversarial-verify workflow) fixed,
incl. a REGRESSION in the loopback fix above:**
- **loopback REGRESSION** — the "native threading" rewrite above was right for the SHIPPED Qt build
  but REINTRODUCED the freeze for the **Eel dev build** (`python main_eel.py`): `main_eel` patches
  socket/ssl/select but NOT threading, so a native `Event.wait()` pins the single gevent hub. Fix:
  `LoopbackListener` is now **transport-aware** — `_use_gevent = _gevent_patched() and not
  _under_qt()` (`'PySide6' in sys.modules`) → Qt=native, Eel=gevent. The `not _under_qt()` gate
  guarantees the shipped build always stays native. [[loopback-gevent-qt-freeze]].
- **`translate.ts` admin approve/edit** were 3 sequential UNCHECKED writes → a partial DB failure
  could mark a submission approved but leave `translation_strings.approved_text` unset (drops the
  line from export). Now the two export-critical writes run first + error-checked → 500 on failure.
- **`translate.ts` bulk upload** now dedups upserts by `string_id` — one duplicate `stringKey` in
  the file used to make Postgres reject the WHOLE batch ("cannot affect row a second time" → 500).
- **`GameDetailPanel`** now has `key={selected.id}` in App.tsx (both mounts) → switching games while
  the panel is open resets state (`pathInput` was showing the PREVIOUS game's install path).
- **WD2 `apply()`** aborts if the pre-apply `revert()` FAILS (game open) instead of appending on top
  → no more ever-growing, un-revertable `.dat`.
- **`ProgressTab`** `/api/games` fetch now rejects on `!r.ok` (a 500 returns valid JSON `{error}`
  that would otherwise become a non-array `g` → `games.map` crash).
- **single-session TOCTOU** — `_device_owner_status` now uses `_claim_device_if_free` (conditional
  `active_device=is.null` CAS) and reports 'taken' if it lost the race, instead of blindly claiming.
All py_compile + `tsc` clean. Security dim didn't run (agent session-limit) → manual spot-check
(Worker slug→fixed `REPOS` map = no SSRF; self-update HTTPS+host-allowlist; new edits injection-safe)
+ the 2026-07-01 hardening audit. **Shipped as v1.0.1-beta** (bumped 1.0.0→1.0.1; channel stays
beta — a real bug-fix release users can see; the launcher self-updates via build-id regardless).

**Post-ship (same day) — 3 more user-reported bugs in the shipped 1.0.1, fixed + re-released 1.0.1
in place (new BUILD_ID `20260701214259`, `launcher_releases` id=59, sha `5d3e94a3…`):**
- **2FA verify was DEAD** (`unexpected: module 'translation_manager.auth' has no attribute
  'verify_mfa'`). `manager.py` defines `verify_mfa`/`cancel_mfa`/`mfa_pending`/`consume_takeover`
  but `auth/__init__.py` never re-exported them, so `_auth.verify_mfa(code)` from `main_eel` raised
  `AttributeError` → the correct TOTP code was rejected. (`consume_takeover` was ALSO unexported →
  the single-session takeover notice never fired.) Fix: add all four to the package
  `from .manager import (...)` + `__all__`. **Lesson: every new `manager.py` function called as
  `_auth.<name>` MUST be added to `auth/__init__.py` — the package re-export is the attribute
  surface, and the miss fails silently through main_eel's `except Exception` catch-alls.**
- **"copy link" silently no-op'd** — QtWebEngine BLOCKS JS clipboard access by default, so both
  `navigator.clipboard.writeText` and `execCommand('copy')` failed. Fix: `profile.py` sets
  `QWebEngineSettings.JavascriptCanAccessClipboard` + `JavascriptCanPaste` = True.
- **Backdrop click during a Google wait didn't ABORT the login** — it called `onClose()` (hides the
  modal) but left the loopback listener running ("returns to the app but it's still in progress").
  Fix: `AuthModal` backdrop `onMouseDown` calls `cancelGoogle()` (→ `auth_abort_login`) when
  `googleBusy`, else `onClose()`. (The "בטל וחזור" button was already wired correctly; the
  transport-aware loopback fix makes it responsive again.)
Verified: `_auth.verify_mfa` etc. importable, `QWebEngineSettings.JavascriptCanAccessClipboard`
exists, tsc/py_compile clean. Re-published in place (`publish_release.py` clobbers the existing
`v1.0.1-beta` asset + inserts a fresh is_current row); winget sha refreshed. Users self-update.

**FINAL loopback fix (2026-07-02, BUILD_ID `20260701225640`, dev_build 27, `launcher_releases`
id=61, sha `f48b081c…`, 240,672,382 B).** The "transport-aware" loopback above was STILL wrong: on
Qt, `login()` runs on a FRESH native OS thread per attempt and `main_eel` monkey-patches socket
process-wide, so the gevent-greenlet serve loop ran on the 2nd native thread's fragile throwaway
hub → **browser opened the 1st time but NOT the 2nd** (+ cross-thread gevent `.set()` → freeze +
`crypto_generatorandom()` crash). Rewrote `LoopbackListener` **gevent-INDEPENDENT**: serve loop = a
plain daemon `threading.Thread` doing blocking `accept()` on an **UNPATCHED** socket
(`_ReuseHTTPServer` rebuilds `self.socket` from `gevent.monkey.get_original('socket','socket')` with
`bind_and_activate=False`); `abort()`+callback set **plain `threading.Event`s** (thread-safe cross-
thread in both builds); `await_code()` polls them with a cooperative sleep (`gevent.sleep` under Eel
where login is a greenlet, `time.sleep` under Qt) — the ONLY per-build branch. Smoke-tested
`c:\tmp\loopback_test2.py` (patched sockets + fake PySide6 + native threads): 8/8 — callback
captured AND cross-thread abort 'cancelled' in ~0.35s on EVERY sequential attempt (no "works once").
Also `AuthModal.copyAuthorizeUrl` now fetches the URL via `api.authGetAuthorizeUrl()` if the
prefetch hasn't landed (the native-clipboard slot has no user-gesture constraint), so copy works
even independent of the browser-open path. Memory [[loopback-gevent-qt-freeze]].

**Google-login copy + "slow 2nd browser" RESOLVED + PUBLISHED v1.0.1-beta (2026-07-02, BUILD_ID
`20260702005524`, dev_build 32, `launcher_releases` id=62, sha `3ce96b43…`, 240,662,820 B).** After
the loopback fix landed, two user reports remained: "browser opens but slow the 2nd time (after
cancel)" and "copy-link doesn't work". **Diagnosed from real ms-timestamp breadcrumbs** in
`~/.translation_manager/auth_debug.log` (added `_debug_step` at login-start + build_id + bind +
"opening browser NOW" + `os.startfile` return) — PROVED login()→browser-open is **60 ms** (zero
code delay; the "slow 2nd time" is the external browser's COLD-START because the user closed it
after cancelling — not fixable in our code). The copy bug's smoking gun was one log line
`js_console: copyAuthorizeUrl: src=fetch urlLen=0` → `auth_get_authorize_url` returned EMPTY because
the user clicked copy right when login **timed out (180 s) and cleared `_last_authorize_url` in the
`finally`**. Fixes shipped: (1) **auto-copy the authorize URL to the clipboard the instant login
starts** (`manager._clipboard_set`, raw Win32 ctypes with an `OpenClipboard` retry — Qt holds the
clipboard transiently; roundtrip-verified) so the URL is on the clipboard while the listener is
alive, no dependency on the button/prefetch/timeout; overlay text tells the user "הקישור כבר הועתק
ללוח — הדבק (Ctrl+V)"; (2) **login timeout 180 s → 300 s** across all 4 layers (manager
`login(timeout=300)`, Qt slot safety `320_000`, eel greenlet `320.0`, eel.ts `auth_login 340_000`)
so a slow user's listener stays alive; (3) **robust browser opener** `_open_browser` (os.startfile →
webbrowser → ShellExecuteW, each logged); (4) **persistent prefetch** (poll `auth_get_authorize_url`
every 300 ms the whole time the overlay is open, not just 1 s); (5) **2FA stale-error clear** — a
"הקישור לא זמין" from an early copy click LINGERED onto the 2FA screen (the overlay hides the error
box, so it only becomes visible after login completes) → clear error+info on 2FA-screen entry, and
the copy button now flashes "✓ copied" (auto-copy already did it) instead of a red error. The
BRIDGE `copy_to_clipboard` slot (Qt path) now logs win32/qt result — note it calls
`_win_set_clipboard` DIRECTLY, so logging in the EEL `copy_to_clipboard` never fires under Qt (that
misled diagnosis once). User confirmed "עובד". Standing rule saved [[local-install-launcher-builds]]:
launcher changes now auto build+ISCC+RUN the installer locally; publish only on "פרסם". 2 news
drafts pushed. Memory [[loopback-gevent-qt-freeze]].

---


## Launcher FPS — POLISH PASS 3 (the REAL fix) + mod-update clickable + website thread/guest-view (2026-06-29 PM)

User: published the launcher, STILL not smooth "even with animations off"; + remove "כמו Steam"
text; + a mod-update bug ("notification but no button to update"); + show installed version; +
2 website features (reply thread, guest-viewable /translate).

- **FPS — evidence-based root cause (after 2 failed guesses).** A research+audit Workflow
  (`diagnose-launcher-fps`) proved: removing `backdrop-filter` from `.glass` (Pass 2) was
  NECESSARY-BUT-NOT-SUFFICIENT — the real always-on cost is **component-level `backdrop-blur-*`
  everywhere**: ~2-3 per GameCard (`lib/theme.ts` availability+mod badges + version chip) ×N
  cards, re-rasterized every scroll frame, and **`html.reduce-anims` does NOT touch
  backdrop-filter** so they survived "animations off" (the exact symptom). Removed ALL: theme.ts
  badges→`bg-black/90`, GameCard chip, GameDetailPanel back-btn/chip + the near-fullscreen
  `blur-xl` no-banner hero, HomeView carousel arrows + the corner-glow `blur-2xl`→radial-gradient,
  AppsView, SoftwareDetailPanel, PersonalAreaView; de-layered GameCard (dropped
  `will-change-transform`+`translateZ(0)`). main_qt flags → `--ignore-gpu-blocklist
  --enable-gpu-rasterization --enable-zero-copy --enable-accelerated-2d-canvas` (GPU default-ON).
  **STOP-GUESSING DIAGNOSTIC:** `frontend/src/lib/gpuInfo.ts` (WebGL UNMASKED_RENDERER) shown in
  **Settings → ביצועים** ("מצב עיבוד גרפי": green=GPU+renderer / red="עיבוד תוכנה") + logged
  `[gpu-probe]` to launcher.log → tells us definitively if QtWebEngine is on the GPU vs SwiftShader
  software fallback (if software → release-build/ANGLE issue, NOT CSS). Removed the "כמו Steam" text.
- **Mod-update "no button" FIXED** (workflow `map-mod-update-flow`): the boot toast was
  non-actionable AND native-applier mods (SM2/WD2/GTAV) had NO update button at all (only CP2077/
  Anno download-mods did). Now: clickable boot banner → routes to the game/Downloads;
  `check_game_mod_update`/`get_mod_updates` cover native (SM2 vs GitHub manifest, WD2/GTAV vs
  bundled version, `kind:"native"`); GameDetailPanel SM2/WD2/GTAV branches get the "⬆ עדכן תרגום"
  button + chip; DownloadsView `updateMod` dispatches by `kind` to the right install RPC.
- **Installed version shown**: GameDetailPanel stats now show "גרסה זמינה" vs **"גרסה מותקנת"**
  (from state.json), highlighted amber + "⬆ קיים עדכון חדש יותר" when older.
- **SHIPPED 2026-06-29 PM** (BUILD_ID `20260629042940`, dev_build 16, `launcher_releases` id=53,
  `/api/launcher` buildId==baked ✓, sha `1511afd7…`, 259,589,816 B). Installed dev launchers get
  it via self-update. **User must still open Settings → ביצועים and report the GPU line** so we
  confirm whether the FPS fix landed (GPU active) or QtWebEngine is on software (then a Qt-side
  release-build/ANGLE fix is needed, not CSS).
- **Website (SHIPPED + verified live, `vercel --prod`):** review reply THREAD (table
  `review_replies`, any user replies, admin badged "מנהל"+logo) + `/translate` public-to-view
  (guests read-only, actions gated). Detail in `website/CLAUDE.md`.


## Launcher FPS deep-fix + right-rail settings + carousel banners + Website review replies (2026-06-29)

User report: "still always low FPS, never smooth" + 4 launcher asks + 1 website ask.
**Launcher SHIPPED** (BUILD_ID `20260629022411`, dev_build 14, `launcher_releases` id=51,
`/api/launcher` buildId == baked, verified). All 5 launcher fixes headless-verified in the
launcher-designer (real App 1:1) — 0 code pageerrors. **Website code+migration DONE but the
`vercel --prod` DEPLOY is BLOCKED** (see below).

- **THE real FPS root cause (the prior 2026-06-28 perf pass wasn't enough):** `main_qt.py`
  launches Chromium with **`--disable-gpu-compositing`**, so EVERY `backdrop-filter: blur()` and
  every `filter: blur()` is rasterized **on the CPU each paint**. The near-fullscreen `.glass`
  main panel was re-blurring the background continuously → permanently low FPS. Fix
  (`index.css`): **dropped `backdrop-filter` from `.glass`/`.glass-strong`/`.glass-soft`** →
  solid translucent dark fills (`rgba(12,12,26,0.82)` etc.) — visually a dark frosted panel, ZERO
  per-paint blur. Also replaced the HomeView hero's 3 animated `blur-3xl` + `animate-glow-pulse`
  blobs with a STATIC radial-gradient. Headless-verified `getComputedStyle('.glass').backdropFilter
  === "none"`. (The poster bg still shows through panel gaps/rounded corners.) **Lesson: under
  `--disable-gpu-compositing`, blur is a CPU killer — never ship animated/large blur; the website's
  VideoBackground is already a static poster, so blur was the only continuous cost left.**
- **Settings → fixed RIGHT-side collapsible rail** (`GameDetailPanel.tsx`, reverses the
  2026-06-28 bottom-pin per new user request). Detail root is now a `flex` row (RTL → rail on the
  RIGHT): a `w-[330px]` `glass` `<aside>` (own scroll) with a hide button → collapses to a thin
  `w-11` ⚙ bar; the main content is `flex-1 overflow-y-auto`. `settingsBody` flattened from a
  3-col grid to a single vertical stack. Headless-proven `onRight=true (x=1093,w=330)` + collapse.
- **Home carousel uses the wide per-game BANNER** (`HomeView.tsx` FeaturedCarousel) instead of the
  cropped vertical cover — `g.bannerUrl` full-bleed + `g.logoUrl` + scrim (falls back to the masked
  cover when a game has no banner). Uses the banners uploaded 2026-06-28.
- **Big Picture HIDDEN for now** (`App.tsx` `const BIG_PICTURE_ENABLED = false`) — gates the home
  button (`onBigPicture` undefined), the Start-controller `toggle-bigpicture` effect, and the
  overlay render. Trivially re-enableable (flip the flag). Headless-verified button count 0.
- **Home news/updates → latest 10 only** (`NewsSection.tsx` `slice(0,10)`).
- **Website — reply to user reviews, admin reply badged "מנהל" + site logo** (code + DB done;
  deploy pending). Migration: `reviews.admin_reply` + `admin_reply_at` (psycopg2 SUPABASE_DB_URL).
  `api/_lib/reviewsHandler.ts`: `DbReview`+`shape→adminReply/adminReplyAt` + a PATCH **`reply`
  verb** (admin-only, empty clears). `src/lib/useReviews.ts`: `Review` fields + a standalone
  `submitReviewReply(id,text,token)`. New `src/components/ReviewAdminReply.tsx`: everyone SEES the
  reply (logo `/icon-128.webp` + "מנהל" badge + "צוות התרגום"); an admin (`useAuth().isAdmin`) sees
  inline **"↩ השב כמנהל"** / ערוך / מחק — wired into BOTH `ReviewSection` (per-game) and
  `ReviewsPage` (`/reviews` browse). `tsc` + `vite build` clean.
- **⚠️ WEBSITE DEPLOY BLOCKED — vercel auth in the isolated Antigravity profile.** `vercel --prod`
  failed `Error: The specified token is not valid`; `vercel whoami` HANGS. Root cause: this MAX
  session runs under `AntigravityProfiles\translation-profile2` which **redirects HOME/APPDATA/
  LOCALAPPDATA**, so the vercel CLI can't find its global auth (no `com.vercel.cli/auth.json` under
  the real home either; no `VERCEL_TOKEN` in `website/.env`). Same redirection also broke
  `$env:LOCALAPPDATA\…\ISCC.exe` → **use the explicit ISCC path
  `C:\Users\Nehoray_Cohen\AppData\Local\Programs\Inno Setup 6\ISCC.exe`** (the launcher publish
  uses GitHub+Supabase keys from `website/.env`, so it was unaffected). **To finish the website:**
  `cd website && vercel login` (interactive) then `vercel --prod`, OR pass `vercel --prod
  --token <TOKEN>`. The DB migration is already live, so once deployed the reply feature works
  immediately (`/api/reviews` will then return `adminReply`/`adminReplyAt`).

---


## Universality audit + fixes (2026-06-09)

A multi-agent portability audit (baked dev-paths, Windows version/arch,
locale/encoding, permissions/registry, bundled deps) with adversarial
verification. Most flagged risks were **verified as non-issues**: Win7/8/8.1
are already blocked by `MinVersion`; `certifi` is bundled and `requests`'
default `verify=True` uses it (no OS cert-store dependency); non-ASCII Windows
usernames are fully supported (pathlib + `utf-8`/`utf-8-sig` everywhere, wide
Win32 APIs); offline first-launch falls back to the bundled `_bundled_games()`
catalog (the Qt build never calls the Eel offline dialog); the language
registry-write error is already surfaced via `GameDetailPanel` `langErr`; and
single-instance mutex/event names are already per-session-isolated by Windows
(no `Global\` prefix → Local namespace). Three real fixes shipped:

- **`installer.iss` `MinVersion` 10.0 → 10.0.17763** (Windows 10 1809) — the
  floor for Qt6/QtWebEngine. Below it the bundled Chromium fails with a cryptic
  DLL error; now the installer refuses with a clean message. 1809 is long EOL
  so no real user is excluded.
- **Pre-flight writability probe** — `game_mod.is_writable(game_root)` (a
  non-destructive `NamedTemporaryFile` probe). `main_eel._run_game_mod_install`
  checks it BEFORE the (large) download, so a non-elevated user targeting a
  game under `C:\Program Files` gets an immediate "run as admin / move the game"
  message instead of downloading hundreds of MB and only then failing the copy.
- **`game_mod.disable()` correctness** — only marks `installed=False` when every
  file actually deleted. Previously a locked file (game running) broke the loop
  but state still flipped to "disabled", so the UI lied while the mod stayed on
  disk. Now it stays "active" on partial failure and a retry re-attempts.

Noted but NOT fixed (needs a paid asset / decision, not code): the installer +
exe are **not Authenticode-signed** → SmartScreen "Unknown publisher" on first
download (one-click "Run anyway"; reputation self-heals). A code-signing cert
(~$100-500/yr) removes it.


