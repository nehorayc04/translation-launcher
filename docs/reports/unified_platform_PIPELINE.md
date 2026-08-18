# Unified Platform (Track B) — PIPELINE

The durable, checkable task list. Facts in `unified_platform_RECON.md`; go/no-go reasoning in
`unified_platform_FEASIBILITY.md`. Every task here is local-build-and-install ONLY
(`launcher-build` skill: `& '.\build_exe.bat'` → ISCC → install locally) — **nothing is published
to real users until the human says "פרסם"**, verbatim. Log every shipped chunk to
`LOCAL_CHANGELOG.md` under Translation Manager (`local-changelog` skill).

## Standing constraints (repeat of the plan's, kept here for a quick re-check per task)

- Base 1 (`games/*/fleet|work|extract`, Fleet orchestration, `/translate`, community-compute) is
  never touched by any task below.
- Every new backend capability needs BOTH RPC halves: `main_eel.py` `@eel.expose` AND
  `translation_manager/qt_shell/bridge.py` `@Slot`.
- `py_compile` every touched backend `.py`; `npx tsc -b` the frontend — BEFORE every build.
- Legal/ToS checklist (feasibility doc) applies to C1-C6.

---

## Stage 0 — WebView2-vs-Qt glass POC

- [ ] Confirm `dotnet --version` reports a .NET 8 SDK.
- [ ] `dotnet new wpf -n GlassPocHost` in a throwaway `stage0_poc_webview2/` dir — **untracked, not
      wired into `TranslationManager_qt.spec`**.
- [ ] `dotnet add package Microsoft.Web.WebView2`.
- [ ] `MainWindow.xaml`: one `<wv2:WebView2 x:Name="wv"/>` filling the window, no custom chrome.
- [ ] Navigate to the UNMODIFIED frontend — Vite dev server (`npm run dev`, port 5173) or
      `npm run build` → `frontend/dist/index.html` (works under `file://`, confirmed by
      `vite.config.ts`'s `base: './'`).
- [ ] No mock backend needed to start — `detectTransport()` resolves `null` gracefully. Add a mock
      `window.bridge` only if a specific screen is found to hard-block.
- [ ] Open WebView2 DevTools (`wv.CoreWebView2.OpenDevToolsWindow()`), confirm the `[gpu-probe]`
      console line, record a Performance-panel trace on a glass-heavy screen (`GameDetailPanel`, the
      settings rail).
- [ ] **Repeat the identical measurement on the current, already-installed Qt build**, SAME machine.
- [ ] **Repeat both on at least one weak/older GPU machine** — this is the comparison that actually
      matters (see feasibility doc's pass/fail bar).
- [ ] Record the result (pass/fail per the feasibility bar) — feeds the Stage-4 go/no-go alongside
      the human operator's (A) audience confirmation. Delete the throwaway project once measured;
      no packaging/IPC/install work under this stage.

## Stage 1-3 — ordered tasks

### ✅ C0 — "ביג-לאנץ", a SEPARATE console shell — DONE 2026-08-16

> **⚠️ C0 was originally written as "flip `BIG_PICTURE_ENABLED` to true". That reading was WRONG.**
> The flag flip shipped (`20260816040719`) and the human corrected it: *remove the old fullscreen
> overlay entirely and build a "ביג-לאנץ" — a console shell **exactly like Winhanced**, **separate**
> from the current launcher.* The old overlay was a carousel bolted onto the desktop shell; the
> blueprint's category-10 row asks for a real 10ft UI. The steps below are what actually shipped.

**Remove the old one**
- [x] Deleted `frontend/src/components/BigPictureMode.tsx`.
- [x] Stripped every reference from `App.tsx` + `HomeView.tsx` — verified 0 matches for
      `BigPicture|bigPicture|BIG_PICTURE|onBigPicture` across the whole frontend.
- [x] **Finding:** `App.tsx` listened for a `toggle-bigpicture` event **nothing ever dispatched**
      (`spatialNav.ts` maps Start(9)→`nav-settings`, Guide(16)→`nav-sidebar`). The old mode had NO
      controller entry — the plan's "controller Start flips it" was never true.

**Build the new one** (`frontend/src/biglaunch/`, 5 files, ~45 KB)
- [x] `bigLaunch.css` — self-contained 10ft design system. NO large always-on `backdrop-filter`
      (documented CPU-raster FPS killer here); exactly ONE blurred element (a static hero `<img>`);
      transitions on `transform`/`opacity` only; FOCUS (not hover) is the primary state.
- [x] `BigTile.tsx` — focusable tile; `onFocus` drives the hero, `onMouseEnter` forces focus so
      mouse and controller agree; a status dot (פעיל / מותקן-כבוי / זמין להתקנה).
- [x] `BigLaunchApp.tsx` — shell root: hero + tabs (בית / ספרייה), rows (המשחקים שלך · מוכן בעברית ·
      זמין לתרגום בלחיצה · תרגומים מובילים · כל הקטלוג), library filters, clock, hint bar,
      focus-parking after every screen change, Esc→`nav-back` bridge.
- [x] `BigGameHub.tsx` — per-game screen: hero art + logo + chips + ▶ הפעלה + translation action.
- [x] `BigQuickMenu.tsx` — Winhanced-style Power/Command menu (מצב שולחן עבודה · הגדרות · רענון ·
      סגירה · יציאה), opened by **Guide (16)** or ☰, closed with B.

**Wire the switch**
- [x] `main.tsx` routes on the URL fragment — `#big` → `<BigLaunchApp/>`, else `<App/>` (the same
      channel `main_qt.py` already uses for `#game=<id>` deep links). The two never mount together.
- [x] `main_qt.py --big` → `setFragment("big")` + `main_eel.set_big_launch_requested(True)` +
      `window.set_big_launch(True)` BEFORE the first show (never flashes as a window first). A deep
      link WINS over `--big`.
- [x] 3 RPCs, **both halves each** (`main_eel.py` + `bridge.py` + `eel.ts`): `set_big_launch`,
      `big_launch_requested`, `app_quit`. `MainWindow.set_big_launch` saves/restores geometry +
      maximized state and hides/shows the custom title bar. **`app_quit` routes to
      `request_real_exit()`, NOT `window_close()`** — the latter honours the close-behavior pref
      and usually hides to the tray, which from a full-screen console reads as "the app vanished".
- [x] `installer.iss` — a dedicated **"ביג-לאנץ"** Start-menu shortcut (`--big`, same AUMID) + an
      optional desktop one behind a new `biglaunchicon` task.
- [x] Desktop home's old "🖥 מצב מסך-מלא" button replaced with **"🎮 ביג-לאנץ"** → `setBigLaunch(true)`
      → `#big` → reload.

**Scope decision (deliberate, surfaced in the UI)**
- [x] The console drives the SIMPLE generic path (`modSlug` + owned → `downloadAndInstallGameMod`).
      The 8 native appliers (`modSlug === ""`) keep their multi-branch flow/DRM/activation note in
      the desktop panel and get an explicit **"🖥 פתח בשולחן עבודה"** handoff instead of a fake button.

**Round 2 — "exactly like it, not just similar" (BUILD_ID `20260816135837`, DEV 258)**

> The human escalated twice: *"שיהיה ממש דומה לwinhanced"* → *"שיהיה בדיוק כמוהו ולא רק דומה"*.
> A similar-LOOKING shell was not the ask, so the layout was recovered from their own markup.

- [x] **Decoded 113 compiled-XAML files' string tables** with the project's existing
      `games/winhanced/work/xbf.py` (`parse(path).strings` → type/property/`x:Name`/literals in
      markup order ⇒ the element tree). No binary asset copied; everything re-implemented in our
      own CSS/SVG. *(A 10-agent Workflow was tried first: 3.3M subagent tokens, all session-limited,
      `(no spec produced)`. Check for an existing reader before fanning out agents at a binary.)*
- [x] Sources used: `MainWindow.xbf` (BumperPillNavigation + GlowUnderline · PinnedSecondaryNavHost
      with LT/RT + sort + range counter · GlassRailHost/HomeGameInfoPanel · RecentGames repeater ·
      NavFooterGrid · BackgroundImageA/B + BloomCanvas + AcrylicVeil) · `Views/GameDetailsPanel.xbf`
      (hero + Diagonal/Top/Bottom scrims + ActionDock: SplitButton + DockCards + DownloadProgressBar)
      · `Dialogs/PowerMenuDialog.xbf` (icon + SemiBold title + subtitle rows, divider, Desktop Mode,
      Quit) · `Controls/GlassPillIndicator.xbf` (pill order) · `Resources/DesignSystem.xbf` (Inter
      weights, 12–24 sizes, 2/6/12/20 spacing, SystemAccentColor, the Glass*/Acrylic* brushes,
      CardFocusGlow, the corner-radius + text-style sets).
- [x] `bigLaunch.css` rewritten on those tokens; `BigTile.tsx` rebuilt to their card anatomy
      (ShadowHost > FocusableCardButton > CardChrome + TintOverlay + CardSpecularRim + BoxArtImage +
      GlassSourceBadge + FocusGlowBorder + FocusScaleTransform).
- [x] New `BigGlyph.tsx` (controller glyphs DRAWN, not their PNGs — so they re-colour with the
      theme) + `BigStatusPill.tsx` (GlassPillIndicator, restricted to search/downloads/power/clock;
      Volume/Bluetooth/Network/Battery are hardware surfaces we refuse to fake).
- [x] **Rendered the built shell headlessly behind a mock `window.bridge` and READ the PNGs** —
      which found 3 real defects that code review had not: the status pill covering the LB glyph
      (fixed by centering the bumper group, which is also what they do), a failed cover leaving a
      blank card (added the `onError` → title-plate fallback), and an unreadable translucent power
      dialog (a modal is a solid layer over a dim scrim).
- [x] ⚠️ One screenshot-derived "bug" was **my misreading**: the library grid was already correct
      RTL — verified by checking the card ORDER, not the picture. Comment corrected in place.

**Verify + ship**
- [x] `npx tsc -b` clean · `py_compile` clean (`main_eel.py`, `main_qt.py`, `bridge.py`,
      `main_window.py`).
- [x] Local build BUILD_ID `20260816044752` (DEV 257) — BUILD_ID **and** dist-exe mtime both
      confirmed fresh before ISCC → `Output\TranslationManager-Setup-1.2.0.exe` (143,100,265 B),
      launched via `Start-Process` for the human's UAC.
- [x] `LOCAL_CHANGELOG.md` entry with the BUILD_ID.
- [ ] **Human step, not automatable from here**: launch the new **"ביג-לאנץ"** shortcut AND the home
      button; check tile focus/scroll with arrows + a controller, the game hub, the quick menu
      (Guide), and the return-to-desktop path; eyeball the console for errors on the running app.

### C1 — Discord Rich Presence

- [ ] Add `pypresence` to `requirements.txt`.
- [ ] New `translation_manager/discord_presence.py` — defensive style matching `perf_manager.py`
      (a closed/absent Discord client must never crash or block the launcher; wrap every call).
- [ ] `set_discord_presence` / `clear_discord_presence` — `@eel.expose` in `main_eel.py` AND
      `@Slot` mirror in `bridge.py`.
- [ ] Wire into the existing game-launch path (set on launch, clear on exit/close).
- [ ] New `discord_rpc_enabled` pref in `launcher_prefs.py` (default **True**, opt-out — same
      pattern as `crash_reporting`).
- [ ] Toggle in `SettingsView.tsx`.
- [ ] Register a free Discord "Application ID" (NOT the gated Partner SDK) — human operator step.
- [ ] Test via BOTH the Eel dev path (`python main_eel.py`) AND the packaged Qt build.

### C2 — Cross-store library badge (surface-only, Phase 1)

- [ ] `main_eel.py`: attach `source_launcher` to the already-fetched game payload (data
      `game_detector.py` already resolves — just not surfaced today).
- [ ] `frontend/src/lib/types.ts`: `Game.sourceLauncher?: string`.
- [ ] Small badge in `LibraryView.tsx` / `AppsView.tsx` cards.
- [ ] **Explicitly do NOT** build full per-store enumeration in this pass — that's Phase 2, deferred
      until C3/C4 exist to give newly-discovered titles art + price instead of a blank card.

### C3 — Cover/hero art (SteamGridDB + IGDB)

- [ ] Establish the API-key storage convention: git-ignored `.env`/local-JSON (NOT `keyring`/
      `auth/storage.py` — wrong tool, see feasibility doc).
- [ ] New `translation_manager/art_fetch.py` (reuses the existing `requests` dep).
- [ ] Local cache under `~/.translation_manager/`, atomic-write + `.bak` via the `resilience.py`
      pattern (matching how `detected_games.json` is already persisted).
- [ ] First slice: cataloged titles only, one cover + one hero per title, cached.
- [ ] Degrade to the current bundled static art on ANY failure (missing key, network error, rate
      limit) — zero regression risk.
- [ ] Register free SteamGridDB + IGDB keys — human operator step.

### C4 — Price comparison in ₪ (Steam Store API + IsThereAnyDeal)

- [ ] New `translation_manager/price_lookup.py`.
- [ ] Steam's `appdetails` endpoint — keyless, use directly.
- [ ] IsThereAnyDeal — needs a free key via C3's now-established `.env` convention.
- [ ] Badge in `GameDetailPanel.tsx` / cards.
- [ ] Cataloged games only, TTL-cached, ₪ throughout (not $ — Hebrew-speaking audience, per the
      research docs' own correction).

### C5 — Smart Launch Watcher (our own implementation of the idea)

- [ ] New `translation_manager/launch_watcher.py` — `ctypes` `SetWinEventHook`, extending
      `perf_manager.py`'s existing low-level Win32 interop style.
- [ ] Auto-dismiss known UAC/EULA/anti-cheat-installer dialogs, matched by window title/class
      against a small JSON pattern list (own data, never Winhanced's).
- [ ] New `smart_launch_watcher_enabled` pref, default **False** (opt-in — higher blast-radius than
      C1-C4, see feasibility doc).
- [ ] Wire to the tracked-game-launch event.

### C6 — Sunshine/mDNS discovery → Moonlight handoff

- [ ] Add `zeroconf` to `requirements.txt`.
- [ ] New `translation_manager/sunshine_discovery.py` — browse for a self-hosted Sunshine mDNS
      record, `subprocess`-launch Moonlight if already installed.
- [ ] Launcher-only — no streaming code of our own.
- [ ] Lowest priority; do last.

## Verification, every task

- Local build via the `launcher-build` skill; confirm BUILD_ID freshness (`_build_info.py` timestamp
  + dist exe mtime, per the skill's own "classic failure = stale ship" warning) BEFORE ISCC.
- Test each new RPC through BOTH transports (Eel dev + packaged Qt) — the 1:1 mirror contract means
  a capability can silently work in one and not the other.
- `LOCAL_CHANGELOG.md` entry per shipped chunk, per the `local-changelog` skill.
- **Never publish** — the launcher stays local-only for this entire initiative until an explicit
  "פרסם".
