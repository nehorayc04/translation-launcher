# Unified Platform (Track B) — RECON

Companion to `unified_platform_grounded_plan.md` / `unified_platform_visual_scenarios.md`. This is
the **verified-claims** doc — every line below was checked against the live repo (Grep/Read), not
assumed from the original research PDFs. Where a research doc's premise turned out stale, the
correction is called out explicitly. See `unified_platform_FEASIBILITY.md` for the go/no-go
reasoning and `unified_platform_PIPELINE.md` for the task list this feeds.

Track A (`games/winhanced/`, the separate Hebrew-localization-of-Winhanced-itself sub-project) has
its own RECON/FEASIBILITY/PIPELINE triad, not covered here — see CLAUDE.md's "Track A" section.

## 🔴 Correction — GPU compositing in the Qt build is NOT what the research docs assumed

`translation_manager_vs_winhanced_architecture_report.md` and (implicitly) `unified_platform_
grounded_plan.md` both frame "Python + Web" as inherently CPU-rendered / heavier-footprint than a
native WinUI3 host, and the project's own CLAUDE.md at one point repeated "Qt runs
`--disable-gpu-compositing`, glass had to be ripped out" as a settled fact. **That premise is stale.**

Verified directly (`main_qt.py`, ~lines 89-183):
- GPU compositing is **ON by default**. The launch flags include `--ignore-gpu-blocklist
  --enable-gpu-rasterization --enable-zero-copy --enable-accelerated-2d-canvas`.
- `--disable-gpu-compositing` (CPU fallback) only fires on:
  1. An explicit user opt-out — `launcher_prefs.json`'s `disable_gpu_compositing` key, surfaced as
     the "האצת חומרה" (hardware acceleration) toggle in Settings.
  2. A detected prior boot-crash — `_safe_mode = _last_boot_failed()`.
  3. A pre-set `QTWEBENGINE_CHROMIUM_FLAGS` env var (external override).
- The code comment at that site explains WHY the opt-out exists: hardware accel can rarely flicker
  when another GPU-heavy workload (e.g. a local LLM inference process) is saturating the same card —
  this is a real, occasionally-hit failure mode, not a theoretical one, hence the toggle exists and
  persists per-user rather than being removed.

A second, independent piece already exists and works: a **weak-hardware auto-degrade system**.
- `frontend/src/lib/gpuInfo.ts` (line ~39): regex `swiftshader|software|microsoft basic|llvmpipe|
  mesa offscreen|generic` matched against `UNMASKED_RENDERER_WEBGL` — detects a software/blocklisted
  renderer.
- `frontend/src/lib/themePrefs.ts`: `_weakHost()` (line ~89) consumes that signal; `autoBackdrop()`
  (line ~160-161) returns `_weakHost() ? "none" : "glass"` — i.e. the app already ships its own
  runtime decision between full glass and a flat fallback, keyed on the actual detected renderer.
- `frontend/src/main.tsx` already logs a `[gpu-probe] accelerated=... renderer="..."` console line
  on every boot (via `logGpuOnce()`) — free diagnostic, reusable by any future host comparison.

**What this means for Stage 0 (the WebView2 POC):** the original framing — "prove glass can render
at all in a Python+Web launcher" — is already answered YES on suitable hardware, by the current Qt
build. The real, still-open question is narrower and more useful: **does a WebView2 host raise the
reliability FLOOR on weak/GPU-blocklisted hardware, where Qt's current path already falls back to
flat/no-blur?** That reframing is what `unified_platform_PIPELINE.md`'s Stage-0 steps are scoped to
measure — not "can it glass," but "is the floor higher."

## Frontend/backend contract facts

- **`main_eel.py` ↔ `translation_manager/qt_shell/bridge.py` is a mandatory 1:1 mirror.** Every
  `@eel.expose` function in `main_eel.py` needs a matching `@Slot` in `bridge.py` — the file's own
  header self-describes as "mirrored 1:1 from main_eel.py." Two build transports exist (Eel dev /
  packaged Qt); a capability implemented in only one half works in dev and silently does nothing in
  the shipped app (or vice versa). Every Stage-1-3 backend addition (Discord RPC, art fetch, price
  lookup, launch-watcher toggle, mDNS discovery) needs both halves.
- **`frontend/src/lib/eel.ts`'s `detectTransport()`** polls for `window.bridge`/`window.eel` for
  ~600ms, then resolves `null` if neither shows up. A bare WebView2 shell with no Python backend
  attached does NOT hang — the frontend renders its real chrome (sidebar, glass panels, an
  empty-catalog state) with no backend at all. Relevant for keeping the Stage-0 POC minimal: no mock
  `window.bridge` is needed to start, only if a specific screen is later found to hard-block.
- **`vite.config.ts`'s `base: './'`**, per its own comment, means `frontend/dist/index.html` (the
  production build output) already works navigated to directly under `file://`, not only under an
  HTTP dev server — the Stage-0 POC can point WebView2 at either the Vite dev server (fastest
  iteration) or the built `dist/` (closer to shipped reality).

## `game_detector.py` — real coverage, and its real limit

Confirmed substantial, working detection logic for: Steam (registry + library VDF parsing),
Ubisoft Connect (registry), Epic Games (`Manifests/*.item` JSON), GOG Galaxy (registry), Xbox/
Microsoft Store (the `XboxGames` folder). A `detect_via_launchers()` dispatcher plus common-
install-path fallback lists round it out.

**The real limit, and why it shapes the C2 scoping in the pipeline doc:** these are catalog-ID
*matchers* — "does game X (a title our own catalog already knows about) exist under this
launcher's known install locations" — not full library *enumerators* — "list every game the user
owns under launcher Y, including titles our catalog has never heard of." Full enumeration per
store (parsing Steam's `libraryfolders.vdf` + every `appmanifest_*.acf`, Epic's full manifest set,
etc., then reconciling against — or creating provisional entries for — the existing games catalog)
is real, separate, larger work. It is explicitly deferred to a later Phase 2, after C3 (cover art)
and C4 (price lookup) exist to serve the newly-discovered titles something better than a blank card.

## Existing defensive-coding patterns new Stage-1-3 modules should follow

- **`translation_manager/perf_manager.py`**: a real, working `ctypes`-based `EmptyWorkingSet` call
  (psapi), with `restype`/`argtypes` explicitly declared before use. Cited as the house style for
  any new low-level Win32 interop (e.g. C5's `SetWinEventHook` launch-watcher).
- **`translation_manager/resilience.py`**: the established atomic-write + `.bak` self-heal pattern.
  `game_detector.py` already uses it to persist `detected_games.json`; any new local cache (C3's
  cover-art cache) should reuse it rather than inventing a new persistence scheme.
- **`translation_manager/launcher_prefs.py`**: the established home for new boolean feature toggles.
  Existing model to copy: the `crash_reporting` flag (default True, opt-out). New toggles planned:
  `discord_rpc_enabled` (default True, opt-out, C1) and `smart_launch_watcher_enabled` (default
  False, opt-in, C5 — higher blast-radius since it manipulates other processes' windows).

## API-key storage — a gap, and the convention to fill it

Confirmed: **no third-party API key is stored anywhere in the codebase today.** Nothing for
SteamGridDB, IGDB, Discord Application ID, or IsThereAnyDeal exists yet. The existing `keyring`-
based `auth/storage.py` session-encryption pattern is the WRONG tool for these — it exists for
per-user secrets (auth tokens), while these are app-level *public* keys shared across every install.
The `website/.env`-style git-ignored local file convention is the right fit and will be established
for the first time by C3 (cover art) — see the pipeline doc.

## Dependency delta — what's genuinely new vs already available

| Dependency | Status | Needed by |
|---|---|---|
| `requests` | Already in `requirements.txt`, used throughout | C3, C4 |
| `pypresence` | **New** — not present today | C1 (Discord Rich Presence) |
| `zeroconf` | **New** — not present today | C6 (Sunshine mDNS discovery) |
| `ctypes` (stdlib) | Already used extensively (`perf_manager.py`) | C5 (`SetWinEventHook`) |

## Legal/ToS map (from `winhanced_servers_report.md`, unchanged, re-stated here for reference)

- **🔒 Never touch/replicate**: Winhanced's own update/OTA channel, Smart-Profiles community
  backend, internal price-engine, account/auth, news feed.
- **🌍 Freely usable, public 3rd-party APIs Winhanced merely consumes**: SteamKit2, Steam Web/Store
  API, IGDB, SteamGridDB, Discord RPC (the free tier — NOT the gated Partner SDK), the MIT-licensed
  Fronkon Games Steam dataset, ES-DE emulator rules.
- **🏠 Independently self-hostable local tools Winhanced merely orchestrates**: Sunshine+Moonlight
  via Zeroconf/mDNS auto-discovery, RyzenAdj, LibreHardwareMonitor, PawnIO (flagged HIGH crash/
  signing risk — out of scope for this whole plan), RTSS, Chiaki.
- **Forbidden regardless of tier**: Winhanced's own compiled UI/XAML assets, its Smart-Profiles
  dataset, its actual Smart-Launch-Watcher *implementation* (only the on-disk JSON config SHAPE and
  the general idea are inspectable — never its code).
- **Standing rules, no exceptions**: never auto-claim a free game (ban risk — notification/link-out
  only, if ever built); OCR live-translation overlay (a Stage-5, far-future idea) only ever on
  non-anti-cheat titles.
