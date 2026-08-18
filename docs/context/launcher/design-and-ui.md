## Persistent toast + 4-level anim/glass + Ubisoft-name DB + env-redirect root-cause + cached-image race (2026-07-17, LOCAL builds up to `20260717164418`, NOT published)

A long multi-request UX + correctness round. All built+installed LOCALLY (per
[[local-install-launcher-builds]]); website still serves 1.0.2; NOT published.

- **🔴 THE unifying dev-env ROOT CAUSE — Antigravity redirects `USERPROFILE`/`APPDATA`/`LOCALAPPDATA`.**
  When the launcher is started from the Antigravity IDE it inherits a redirected home
  (`AntigravityProfiles\translation-profile3`), so `Path.home()` / `expandvars('%USERPROFILE%')` /
  browser-profile resolution all point at an EMPTY sandbox profile. This ONE artifact explained THREE
  separate user reports: (a) wrong save-backup default path, (b) generic (non-Ubisoft) save detection
  finding NOTHING (Ubisoft worked only because its path uses `%PROGRAMFILES(X86)%`, which is NOT
  redirected), (c) the "isolated browser" (a launched browser reads its user-data from the redirected
  empty `%LOCALAPPDATA%\Google\Chrome\User Data` → makes a fresh isolated profile). **FIX for a/b:**
  `save_backup._real_home()` = `SHGetKnownFolderPath(FOLDERID_Profile)` (reads the token/registry, NOT
  env → returns the REAL `C:\Users\<user>`); `_env()` / `_expandvars_real()` remap USERPROFILE/
  LOCALAPPDATA/APPDATA → `_real_home()`; `_save_roots()`/`_expand`/`_expand_all` route through it;
  `_BACKUP_ROOT_DEFAULT = _real_home()/".translation_manager"/"save_backups"`. **The browser case is
  dev-ONLY** (a real end-user has no redirection → their default browser opens their real profile) →
  left un-fixed on purpose (spawning the browser with a scrubbed env would touch the real-user "open
  website" path for a cosmetic dev-only issue). **UNIVERSAL LESSON: for any user-home / user-profile
  lookup that must be correct even when launched from a redirected sandbox, use
  `SHGetKnownFolderPath(FOLDERID_Profile)`, never `Path.home()`/`%USERPROFILE%`.**
  [[env-redirection-real-home]]
- **🔴 Cached-image race → "covers vanish after a drive scan" (also menu switch / software tab).**
  Rebuilding the list re-renders cards with the SAME already-cached cover URL; a fresh `<img>` whose
  src is cached can be `complete` BEFORE React attaches `onLoad` → `onLoad` never fires → the cover
  sits at `opacity-0` until the whole view is remounted (leave+return "fixes" it). **FIX** in BOTH
  `GameCard.tsx` and `SmartImage.tsx`: an effect keyed on the src that checks
  `el.complete && el.naturalWidth > 0` → `setLoaded(true)` SYNCHRONOUSLY (and `naturalWidth===0` →
  error) instead of waiting for an event that won't come. **UNIVERSAL: any fade-in `<img>` gated on
  `onLoad` MUST also handle the cached-complete case, or a cache HIT strands it invisible.**
- **Persistent Windows notifications (Action Center history), not a flash.** `QSystemTrayIcon.showMessage`
  is a balloon that vanishes and is NEVER kept in Windows notification history. `app_icon.show_toast(title,
  body)` fires a real **WinRT ToastNotification** via a hidden `powershell.exe -EncodedCommand` (base64
  UTF-16LE; values passed as `TM_TOAST_*` env vars to avoid quoting), tied to our AUMID
  `HebrewTranslationHub.TranslationManager`; `register_toast_identity()` writes the winreg
  `DisplayName`="מנהל התרגומים" + `IconUri`; `main_qt` sets `SetCurrentProcessExplicitAppUserModelID` at
  boot and `_show_os_toast` prefers `show_toast` (balloon fallback). Verified it stays in Action Center.
  A tray-minimized webview keeps polling, so background notifs still fire. [[windows-toast-persistence]]
- **App icon stuck on the OLD 5g gradient.** An orphaned persisted `5g-square-round` value survived the
  brand-badge switch. `app_icon._migrate(variant)` maps every legacy `5c/5e/5g-*` id → `brand`/`brand-square`;
  `current()` runs it. Also verified NO personal name anywhere in shipped software (publisher = the brand).
- **4-level animation + glass segmented controls (big UX round).** Replaced the anim on/off toggle with
  **מלאה / רגילה / מופחתת / כבויה** (`themePrefs.AnimLevel`: `data-anim=high|normal|low|off` +
  `.reduce-anims`(off)/`.anims-low`(low); "מופחת" snaps transitions instant via
  `html.anims-low .nav-slide,.seg-thumb{transition:none}`). New **`SegmentedControl.tsx`** = a sliding-thumb
  radiogroup applied to EVERY 2+-option toggle (anim level, sidebar mode, icon shape, in-game language switch,
  library/apps toolbars). Hard-won details: cyan accent not `var(--accent)` yellow; **position via
  `el.offsetLeft/offsetWidth`, NOT `getBoundingClientRect`** (the view-transition `scale(0.976)` skewed the
  rect → "drifts left"); **ResizeObserver created ONCE + a `slidingUntil` ref that RETARGETS mid-slide**
  (re-creating it per value change / firing immediately killed the slide); glass sheen ONLY on the active
  travelling thumb (`data-anim=high`), never on hover; curve `cubic-bezier(.34,1.35,.5,1)` matched to
  `.nav-slide` so the picker motion == the menu-transition motion; no per-option frame — glass only under the
  focused/travelling indicator. The travelling menu pill (`.nav-slide-glass`, sidebar + settings tabs) keeps
  a rounded glowing edge-bar (`w-[3px]`, boxShadow cyan, `z-10` so the sheen doesn't wash it) — glow ONLY on
  the moving indicator, no sharp edges.
- **Machine auto-degrade correctness.** `gpuInfo.ts` software-detection is a POSITIVE regex match only (an
  unknown renderer is NOT treated as software → don't force the dark/no-glass look on a fine GPU);
  `themePrefs.shouldAutoReduce()` = `_weakHost()` (software-GPU OR tier=="low") OR prefers-reduced-motion,
  but `autoBackdrop()` is keyed on `_weakHost()` ONLY (reduced-motion must not kill the frosted glass — that
  regression made "windows dark not glass"). `initThemePrefs` runs `detectGpu()` FIRST.
- **Save-backup polish (plugin engine, cloud-editable).** "שנה מיקום" opens a REAL native folder dialog
  (`main_eel.pick_folder` → `set_native_pick_folder` → `bridge.pick_folder_blocking(title,start)`: a Signal
  hops worker→GUI thread for `QFileDialog`, an Event returns the path); added a **"איפוס לברירת מחדל"**
  button (`engine.reset_destination`, `visibleWhen:"destinationIsCustom"`). **Heavy-backup guard**:
  `folder_size(path)` (os.scandir, cap 300K files, `truncated` flag) + `HEAVY_BYTES=500MB`; `add_ubi_game`
  returns a `confirm` string (size) when heavy unless `confirmed`, and `add_ubi_account`/"הוסף הכל" list
  which games are heavy with sizes. The renderer handles a `confirm` result via `window.confirm` → re-calls
  with `confirmed:true`. (Anno 1800 autosaves ≈ 31GB is the motivating case.)
- **Ubisoft game NAME from the numeric folder ID.** `savegames\<account-uuid>\<numeric-id>` — the numeric
  folder IS the Ubisoft product ID, but the local Ubisoft `configurations` cache does NOT carry the ID inside
  its YAML → a static shipped DB is required. Built `translation_manager/assets/ubisoft_games.json` (~522KB,
  **12,984 games**) by MERGING two complementary public lists (`iArtorias/ubisoft_game_ids` `ID, Name` +
  `Haoose/UPLAY_GAME_ID` `ID - Name`); `save_backup.ubisoft_game_name(number)` resolves it, falls back to the
  bare number when absent (e.g. `61402`, a Dec-2025 title genuinely in NEITHER public list — refused to
  guess). Ships via the spec `('translation_manager','translation_manager')` datas entry.
- **GoWR install showed success but "not installed".** Backend is CORRECT (`get_gowr_mod_state` →
  `installed:True`, `is_applied` = backup exists + live WAD sha == recorded sha; install runs on a
  **QThreadPool** worker in the bridge, NOT the dead-under-Qt `gevent.spawn`). It was a UI timing race (worker
  writes `state.json` then fires `done`; a slow disk reads the old file). **FIX:** the `done` tick now does
  `refreshAll()` + `window.setTimeout(refreshAll, 1500)` → converges.
- **Removed the misleading "מוכן להתקנה" badge from all cards.** `modStateLabel("NOT_INSTALLED")` = "מוכן
  להתקנה" showed even on coming-soon games whose mod doesn't exist. The 3 card sites (GameCard / AppsView /
  LibraryView) now compute `modBadge = game.has_mod_support && game.mod_state !== "NOT_INSTALLED" ? … : null`
  (ACTIVE/DISABLED chips stay).
- **Anonymous op-failure reporting (the "why wasn't the language-switch error reported" ask).**
  `main_eel._report_op_failure(op, game_id, res)` reports a handled `{ok:False}` failure to the admin site
  anonymously (skips benign `not-purchased` etc.), wired into `set_game_language`/`restore_game_language`.
  `cp2077_language._read_json_ex` now distinguishes `settings-file-missing`/`-locked`(3 retries)/`-unreadable`
  so the surfaced error is real, not a silent swallow.
- **Reading LIVE Windows files:** MSYS `stat`/`tail` LIED about `launcher.log` (stale 898KB/10:36 vs the true
  24KB/16:29) — use PowerShell (`Get-Item`/`Get-Content -Tail`) for any live Windows file, never the Bash
  coreutils here. [[read-live-windows-files-powershell]]


## New "TM" icon set (5g-circle-round) everywhere + SWITCHABLE app icon in Settings (2026-07-16, LOCAL build `20260716095125`, website DEPLOYED)

The user supplied a finished icon set at `לוגו לאייקון\assets\final\` = **12 SVG variants**: 3 letterform
STYLES (`5c`=filled white T/arrow · `5e`=outlined · `5g`=gradient-M) × 2 SHAPES (circle / rounded-square)
× 2 M-corner treatments (`חד`=sharp / `מעוגל`=round), on a blue→pink (`#3d6bff`→`#e0345e`) gradient. The
website + splash + sidebar + build-default all use **`5g-circle-round`** (the user's pick); the app icon
(taskbar/window/tray/shortcut) is **user-switchable in Settings**.

- **Rasterizer = `PySide6.QtSvg.QSvgRenderer` offscreen (NO new deps).** `scratchpad/svg_raster.py` renders
  any SVG→QImage at any size; `scratchpad/gen_all_assets.py` is the master generator (WEBP+ICO via PIL,
  which IS in the `.venv`; cairosvg/svglib are NOT). Re-run it to regenerate everything. Multi-size ICO =
  manual PNG-in-ICO (`struct.pack`, per-size crisp render at 16/24/32/48/64/128/256).
- **Website (DEPLOYED `vercel --prod`, verified live):** FIRST set to `5g-circle-round.svg`, then
  **SUPERSEDED same day (2026-07-16) by the user's new chrome-badge PNG**
  `לוגו לאייקון\assets\final\חדש\1784215694284_1784216000125.png` (2896² RGBA, transparent, a 3D
  chrome "TM/HTH" monogram in a neon purple/blue ring) — applied to the WEBSITE ONLY ("על כל מקום חוץ
  מהתוכנה" = the launcher stays 5g). Regenerated the PNG set from it (favicon-32/64, apple-touch-180,
  icon-128 png+webp, icon-192/512) via PIL LANCZOS; **REMOVED `icon.svg`** + the `image/svg+xml` favicon
  link (the new icon is raster, not vector); `Navbar.tsx` brand `<img src>` → `/icon-128.webp`. Verified
  live: favicon/apple-touch bytes == local, `/icon.svg` → 404, 0 svg links in index.
- **Splash + sidebar** (`frontend/public/app-logo.svg` = copy of the default SVG): `SplashScreen.tsx` +
  `Sidebar.tsx` `<img src>` `./app-icon.png` → `./app-logo.svg` (keeps the neon glow `drop-shadow` +
  `float-soft` gentle bob).
- **🔑 SWITCHABLE app icon (the new feature).** Settings → מראה → "אייקון התוכנה": a **shape** segmented
  toggle (עיגול / ריבוע מעוגל) + a **style** thumbnail grid (6 = 5c/5e/5g × sharp/round for the current
  shape). Applies **LIVE, no restart** to the app/window/**taskbar**/tray, AND repoints the Start-menu/
  Desktop/pinned-taskbar **shortcuts** at the chosen `.ico`. **The raw `.exe` file icon in Explorer stays
  the build default** (baked into the PE; can't change at runtime) - documented in the UI copy.
  - **`translation_manager/app_icon.py` (NEW)** - the 12-variant table (id=`<style>-<shape>-<corner>`,
    default `5g-circle-round`), `ico_path()` (resolves `translation_manager/assets/app_icons/<id>.ico` via
    `_MEIPASS`/dev), `qicon()`, `apply_live(window,tray)` (QApplication+window `setWindowIcon` + tray
    `setIcon`), `repoint_shortcuts()` (hidden PowerShell WScript.Shell over Desktop/Programs/QuickLaunch
    `*.lnk` matching our exe → `IconLocation`; a distinct per-variant filename busts Explorer's icon
    cache; frozen-only, no-op in dev), `options()`, `set_variant()`. Pure stdlib + lazy PySide6; never
    raises.
  - **Assets bundled** under `translation_manager/assets/app_icons/*.ico` (rides the spec's
    `('translation_manager','translation_manager')` datas entry; `_keep()` keeps `.ico`) + thumbnails
    `frontend/public/app_icons/<id>.png` (webview picker). Build-default `build_assets/app.ico` +
    `app_512.png` + wizard-small/preview-small regenerated from `5g-circle-round` (exe icon = spec
    `icon=['build_assets\\app.ico']`).
  - **Wiring:** `launcher_prefs.get/set_app_icon` (key `app_icon`, default `5g-circle-round`). `main_eel`
    `get_app_icon()`/`set_app_icon()` (eel path = persist+repoint). **`bridge.py`** slots `get_app_icon`/
    `set_app_icon` (the REAL Qt path → `set_variant(variant, self._window, self._tray)` = live) + a new
    `set_tray(tray)`. `main_qt` after building window+tray: `bridge.set_tray(tray)` + `app_icon.apply_live(
    current(), window, tray)` at boot (before show → taskbar right from frame 1). `eel.ts`
    `getAppIcon`/`setAppIcon` + `types.ts` `AppIconOption`/`AppIconState`.
- Built via `& '.\build_exe.bat'` (BUILD_ID `20260716095125`, exe 9,208,884 B) → ISCC →
  `Output\TranslationManager-Setup-1.0.2.exe` (185 MB, smaller - the icon assets are tiny) → installed
  LOCALLY. `py_compile` (main_eel/main_qt/app_icon/launcher_prefs/bridge) + `tsc`+`vite build` clean.
  Version stays 1.0.2 beta; **NOT published** (no "פרסם").

**FOLLOW-UP same session (2026-07-16, LOCAL build `20260716212715`) - chrome-badge logo INTO the app +
website icon swaps:** the user then supplied a finished **3D chrome "HTH" monogram** set (in
`לוגו לאייקון\assets\final\חדש\`): a CIRCLE badge (`1784219013286_1784219075576.png`) and a ROUNDED-SQUARE
badge (`1784218957330_1784219130200.png`). Applied:
- **Website (DEPLOYED, verified):** favicon/PWA/apple-touch/navbar → first `1784219013286` (circle), then
  the user swapped the site to `1784219013286` again (both site rounds verified live: favicon/apple-touch
  bytes == local). `icon.svg` was removed earlier this session (the new icons are raster PNGs).
- **App (the user: "תכניס את זה גם תוכנה"):** the CIRCLE badge became the app BRAND icon everywhere -
  splash + sidebar (`frontend/public/app-logo.png`, `<img>` `.svg`→`.png`; app-logo.svg deleted), the
  exe icon (`build_assets/app.ico` regenerated from the circle), AND a NEW **`"brand"` variant** in
  `app_icon.py` (`VARIANTS["brand"]=("brand","circle","round")`) with **`DEFAULT="brand"`** +
  `launcher_prefs._APP_ICON_DEFAULT="brand"` → boot `apply_live` shows the chrome circle on window/taskbar/
  tray. The 12 style variants (5c/5e/5g) stay switchable; the Settings picker gained a "מותג (ברירת מחדל)"
  card at the top (selectable) with a `style`-fallback so the grid still works when brand is active.
  `translation_manager/assets/app_icons/brand.ico` + `frontend/public/app_icons/brand.png` generated from
  the circle (PIL-only `scratchpad/gen_brand_app.py`, source is PNG so no Qt).
- **Installer SMALL wizard image** (`WizardSmallImageFile`, top-left of inner pages) → the ROUNDED-SQUARE
  badge; the user asked for it **"בלי המסגרת, רק הלוגו והרקע שלו"** → the badge FILLS a square frame with
  the transparent corners flattened on **WHITE** (matches modern-Inno's white header strip, so no dark box)
  - NOT the old dark 450×171 landscape canvas. **`WizardImageFile` (the TALL banner) left AS-IS** per the
    user. `build_assets/{wizard-small.bmp,preview_small.png}` = 256² badge-on-white.
  - Built `20260716212715` → ISCC → installed LOCALLY. Version stays 1.0.2 beta; **NOT published**.

---


## New HTH logo everywhere + launcher UX batch + admin fixes (2026-07-15, LOCAL build `20260715173410`, website NOT deployed)

Multi-request round. **Launcher built+installed LOCALLY (round-icon build); website admin fixes are
code-complete + `tsc`/`vite build` clean but NEED the user's `vercel --prod` + one SQL migration.**

- **🎨 NEW BRANDING - the neon "HTH" (Hebrew Translation Hub) monogram.** Canonical source `icon.jpg`
  (`ImageFile.LOAD_TRUNCATED_IMAGES=True` - the source jpgs are missing their last bytes). Two icons:
  the FAVICON/website/wizard-small use `icon.jpg`; the **APP icon (exe/window/tray) + sidebar avatar
  use `icon2.jpg`** (a zoomed/bigger crop, more legible small) rendered with a **CIRCULAR mask
  (transparent corners = round frame)** per the user. Regenerated via `scratchpad/gen_icons.py` +
  inline scripts: `build_assets/app.ico` (multi-size ICO, circular), `app_512.png`,
  `frontend/public/{icon.png,app-icon.png,app.ico}`, and the website favicons
  (`website/public/{favicon-32,favicon-64,icon-128.png/.webp,icon-192,icon-512,apple-touch-icon}`).
  **Installer wizard art:** `wizard-large.bmp`+`preview_large.png` = the full portrait banner
  `image_1784130557271.jpg` (HTH + "מרכז התרגום העברי / HEBREW TRANSLATION HUB" + neon modules,
  cover-cropped 164:314 at 3x for crispness); `wizard-small.bmp`+`preview_small.png` = the icon on dark.
  Dropped `WizardImageAlphaFormat=defined` (BMPs are now 24-bit opaque). `scratchpad/gen_wizard.py`.
- **Launcher UX (all shipped in the LOCAL build):** (a) **removed the brown "בטא" StageBadge from the
  library/software CARDS** (`GameCard.tsx`) - it stays only in the detail panel. (b) **Plugin settings
  collapse chevron** (`PluginsSettings.tsx`) - an icon-only up/down chevron below each plugin's action
  button (left-aligned, `dir=ltr`) that shows/hides ALL that plugin's settings; **the body stays
  MOUNTED and is hidden via CSS** so toggling does NOT re-fetch the plugin UI (no "טוען הגדרות…" flash),
  and it applies to EVERY installed+enabled plugin incl. future cloud plugins (the map renders it per
  `p`). (c) **Titlebar click-stick fix** (`TitleBar.tsx`) - the window MOVE now starts only after the
  pointer moves >4px (threshold), so a plain click / the two stationary presses of a double-click-to-
  maximize never enter Windows' modal `startSystemMove` loop that was swallowing clicks. (d) **Taskbar
  toggle-minimize** (`main_window.py` `toggle_visibility` + `main_qt.py` `_bring_to_front`) - a bare
  single-instance relaunch (clicking the pinned taskbar icon) now TOGGLES: a foreground window
  minimizes, a hidden/behind one comes forward (a deep-link still always shows). (e) **59 MB junk MP4
  removed** from `translation_manager/` (it shipped in every installer because the whole dir is bundled);
  added a video-extension guard to `TranslationManager_qt.spec` `_keep()` so a stray media file can never
  pad the installer again. The other large bundled files are legit mod payloads.
- **Website admin (code-complete, `tsc`+`vite build` clean, GATED on the user's `vercel --prod`):**
  - **Plugin icon picker** (`PluginsTab.tsx`) - a categorized emoji library (מומלצים/שמירה/ענן/אבטחה/
    משחקים/כלים/ממשק/כללי) + a live preview chip; the launcher renders `plugin.icon` as TEXT so an emoji
    works end-to-end with no rebuild/webfont. (A full Flaticon-SVG library like `icon-manager.html` would
    need the LAUNCHER to render non-emoji plugin icons - a separate build - so the emoji library is the
    deployable answer.)
  - **🔴 2FA-users analytics FIXED** (`api/paypal.ts handleAdminUsers`) - `auth.admin.listUsers()` does
    NOT populate each user's `factors`, so `mfaEnrolled` was ALWAYS false (every user showed "-").
    Now fetches verified factors per user via `auth.admin.mfa.listFactors({userId})` with bounded
    concurrency (chunks of 10) and builds a set → `mfaEnrolled` is correct.
  - **Payment-only flag** (`games.payment_only`, migration `website/supabase/games_payment_only_migration.sql`
    - **the user must run it**) - the opposite of a free manual-only title: hides the free manual-download
    column in `TwoButtonCta` (`GameDetailModal.tsx`, reused by the game + software detail pages) and offers
    ONLY the paid launcher install. Wired through `api/games.ts` (WRITABLE + DbGame + shape `paymentOnly` +
    toRow), the `Game` type, and an admin checkbox in BOTH `GamesTab` + `SoftwareTab`.
  - **AI news suggestions upgraded** (`api/news.ts` `suggest`) - Gemini now gets REAL current facts
    (recent `mod_version_history` + changelog, the live `launcher_releases` notes, active
    `translation_progress`, the full catalog) instead of just titles, so it describes what actually
    happened; **IRON RULE enforced server-side**: any suggestion without a substantive `detail` (≥15
    chars) is dropped - never a title without content.
- **🗂 ADMIN REORG DONE (`AdminLayout.tsx` + new `ByOptionTab.tsx`), user chose "do it all":**
  - **4 game/software tabs → 2.** The old `games-website`/`games-launcher`/`software-website`/
    `software-launcher` (all the SAME `GamesTab` with `scope`+`kind` props) collapsed into ONE **"משחקים"**
    (`GamesTab kind="games"`) + ONE **"תוכנות"** (`GamesTab kind="software"`); scope defaults to `all` so
    `GamesTab`'s EXISTING internal אתר/לאנצ׳ר pill strip is the platform filter within the one tab. (The
    separate `SoftwareTab.tsx` was already DEAD - not imported by the nav - left in place, harmless.)
  - **New "לפי אפשרות" tab (`ByOptionTab.tsx`)** - a cross-cutting view: each OPTION (featured / מוצג
    באתר / מוצג בלאנצ׳ר / תשלום בלבד / הערת-ממשק / בתשלום / תוכנה) is a COLLAPSIBLE sub-menu listing every
    game/software that carries it, with an inline "כבה" toggle that PATCHes just that flag (optimistic +
    rollback), so a setting can be managed across the whole catalog from one place. Read-only facets
    (price, is-software) just list.
  - **Sub-menus everywhere + no duplicate menus.** `TabDef` gained an optional `group`; `groupTabs()`
    buckets an env's tabs into labelled sub-menu blocks rendered in BOTH the sidebar (uppercase header /
    a divider when icon-collapsed) and the top tab-row. `manage` grouped into **קטלוג** (games/software/
    by-option/versions) · **הפצה ותוספים** (launcher/plugins/progress) · **קהילה ונתונים** (users/
    analytics/votes/purchases/crashes); `content` into **תוכן ציבורי** + **AI ותרגום**. Fixed the
    `system` tab's duplicate 🧩 icon → 🖥️. `readTab`/`lastTabByEnv` defaults → `games`. `tsc`+`vite build`
    clean (AdminLayout chunk 222→227 KB).
- **✅ SHIPPED (2026-07-15):** website DEPLOYED `vercel --prod` (auto-aliased hebrew-translation-hub.com,
  `dpl_7sbtHYzA…`, verified live: `/api/games` now returns `paymentOnly`); the `payment_only` DDL
  migration RAN in production (column exists, boolean). Launcher built+installed LOCALLY (BUILD_ID
  `20260715173410`), NOT published.
- **🔑 RUNNING DDL MIGRATIONS FROM THIS ENV (reusable) — the direct Postgres ports (5432 session +
  6543 transaction pooler) are BLOCKED here (connection timeout), so `psycopg2`/`SUPABASE_DB_URL` can't
  run a migration. Instead use the Supabase MANAGEMENT API over HTTPS (443, open):**
  `POST https://api.supabase.com/v1/projects/<ref>/database/query` with `Authorization: Bearer <sbp_
  PAT>` + body `{"query": "<SQL>"}` runs arbitrary DDL (returns 201). **CRITICAL: Cloudflare bot-blocks
  the default `Python-urllib` User-Agent with a 403 "error code: 1010" (looks like a token/permission
  error but is NOT — it 403s even with NO auth). Set a real browser `User-Agent`
  (`Mozilla/5.0 … Chrome/… Safari/537.36`) and it goes through.** Needs a Supabase PERSONAL ACCESS TOKEN
  (`sbp_…`, full-access; the service-role key can't do DDL) — not in `.env` by default; the user adds
  `SUPABASE_ACCESS_TOKEN=sbp_…`. Reusable runner: `scratchpad/run_migration_mgmt.py`. Project ref =
  `mfudkftrluabqlrpkvtj` (from `SUPABASE_URL`). This supersedes the older "Postgres ports blocked → user
  must run migrations by hand" note.

---


## Restart-relaunch fix + text-size 50-150% + 70 icons applied + categorized icon-manager (2026-07-14, LOCAL build `20260714003914`, NOT published)

Multi-request round (all built+installed LOCALLY per [[local-install-launcher-builds]], NOT published).

- **🔴 "הפעל מחדש מכבה ולא מחזירה" ROOT-CAUSED + fixed (`qt_shell/bridge.py restart_app`).** The
  previous windowless relaunch used a **detached PowerShell** `Start-Process` — it consistently KILLED
  the app but never RELAUNCHED it (the older `cmd`/`ping` helper DID relaunch, just showed a black
  window). A console-less `-WindowStyle Hidden` detached PowerShell can fail to init and/or be
  killed-with-us by a kill-on-close **job object**, so `Start-Process` never ran. **Fix = a VBScript
  run by `wscript.exe //B //Nologo` (genuinely windowless — no console EVER, survives our death):** it
  polls (cheap WMI `Win32_Process` query, 500ms) until OUR pid dies → the single-instance named-mutex is
  released → then `WScript.Shell.Run(exe,1,false)` launches the new instance and self-deletes the .vbs.
  Spawned with `CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB` (0x01000000), with a
  fallback to plain detached if the job forbids breakaway (`OSError`). The single-instance guard is a
  Win32 named mutex (auto-released on process death), so a fresh instance acquires it cleanly once we're
  gone. [[qtwebengine-ui-gotchas]] [[run-hidden-no-popups]]
- **Text-size range 80-120% → 50%-150% in 5% steps** (`lib/themePrefs.ts` `TEXT_MIN=8, TEXT_MAX=24`,
  step 0.8px = 5%; 16px=100% default; 21 marks 50,55,…,150). `SettingsView` slider `min={8} max={24}`
  + a live **`{Math.round(px/16*100)}%` badge** next to the "גודל הטקסט" title. The controller L1/R1
  nudge reads `el.min/max/step` from the DOM, so it auto-adapts (no change).
- **🎨 70 chosen Flaticon UICONS applied to the launcher** (from the user's `icon-changes (4).json` =
  7 nav/tab REPLACE + 63 button/header/badge ADD). Pipeline: `C:/tmp/extract_uicons.py` decodes the
  UICONS "Regular Rounded" **woff2** (needs `brotli`; `fontTools` `SVGPathPen`+`BoundsPen`+`TransformPen`
  fit each glyph to a 0 0 24 24 box, filled `currentColor`, Y-flipped) → **`frontend/src/components/
  UiIcons.tsx`** (70 exported components, `{width,height,className,style}`). The **7 existing** replaced
  in-place (NavIcons `HomeIcon`/`DownloadsIcon`, Sidebar `AppsIcon`/`PluginsIcon`, SettingsView
  `IconAppearance`/`IconPrivacy`/`IconPaths` — swapped stroke SVG → filled UICONS path, same
  currentColor coloring). The **63 optional** inserted before their Hebrew labels across **17 files** by
  a **per-file Workflow** (one agent per file, no file conflicts; each reads `C:/tmp/icon_worklist.json`,
  inserts the icon as the FIRST child = leading/right side in RTL, sizes by kind button 15/header 17/
  badge 12/empty 26, `shrink-0 opacity-90`, currentColor). **63/63 placed, 0 skipped, `tsc -b` clean.**
  ⚠️ Workflow `args` object didn't bind (ran 0 agents) → hardcoded the file list in the script and re-ran.
- **🗂 icon-manager.html regenerated (`build_icon_manager.py`) — categorized + applied-state + controllers.**
  (a) Reflects the APPLIED picks: it reads `applied_icon_changes.json` (= the user's picks) and shows each
  picked glyph as the slot's CURRENT icon (`<i class="fi-rr-NAME">`) so re-picking exports only the delta.
  (b) The 3,933 font icons are now bucketed into **23 categories** (categorize-by-keyword) with a
  category-chip row + search-within-category. (c) A curated **offline gaming/controller library** (12
  hand-authored `currentColor` SVGs — Xbox / PlayStation / Switch Joy-Con / Steam-Deck / D-pad / analog
  stick / arcade / PS ✕◯□△ face-buttons / bumper / gaming-headset) sits in a "בקרים ומשחק" category
  alongside the 51 font gaming glyphs (gamepad/console-controller/joystick/vr/dice/chess/trophy). Library
  entries are mixed font-`<i>` + inline-SVG; assigning either works, SVGs export as `svg-upload`. JS
  `node --check` clean. (The user asked for Xbox/PS4/PS5 controllers "of all kinds" → the curated set +
  the font's `console-controller`/`gamepad`/`joystick`.)
- Built via `build_exe.bat` (BUILD_ID `20260714003914`, dev_build 87, exe 9,237,945 B) → ISCC →
  `Output\TranslationManager-Setup-1.0.2.exe` (243,778,297 B) → installed LOCALLY. Version stays 1.0.2
  beta; NOT published (no "פרסם").
- **Follow-up round (2026-07-14, NOT BUILT YET — user said "אל תבנה עדיין"):** applied `icon-changes (2).json`
  (merged into `applied_icon_changes.json` → 76 picks; re-ran `extract_uicons.py` → UiIcons.tsx from the merged
  set): SettingsView `IconController`→gamepad + `IconPrivacy`→fingerprint-verified; TitleBar window controls
  `IcoMin/IcoMax/IcoClose`→UICONS minus/square/cross; PersonalAreaView library headers get `IconOptHdrMyGames`
  (gamepad) / `IconOptHdrMySoftware` (box-open) by kind; `opt-btn-logout`→arrow-right-to-bracket +
  `opt-badge-plugin-active`→rotate-square auto-updated via the regenerated UiIcons. **Text-size range TIGHTENED
  50%-150% → 75%-125%** (`themePrefs.ts` `TEXT_MIN=12, TEXT_MAX=20`) — 50/150 broke animations+buttons and things
  escaped; 100% default + 5% grid + % badge kept. **icon-manager.html: added a "🚫 ללא אייקון" (remove) option**
  (assign `{type:'none'}` → export `action:'remove', iconType:'none'`) + **grew the curated gaming set 12→20
  controllers** (Xbox/Xbox-Series/PlayStation/PS5/Switch-Pro/Joy-Con/Steam-Deck/retro/arcade/racing-wheel/flight-
  stick/VR/mobile-clip/D-pad/analog/PS-face-buttons/bumper/headset) on a WIDE 0 0 36 24 canvas + `.li svg`
  renders bigger aspect-preserved (max 30×26, no squish). **"Some icons not in place" ROOT-CAUSED + fixed:** the
  63-icon workflow iconed only the `gm.modSlug` branch of GameDetailPanel's action buttons, so native-applier game
  types (SM2/WD2/GoWR/GTA + the legacy remove) rendered the SAME buttons WITHOUT icons → inconsistent per game.
  Added the matching icons (purchase/already-paid/install/remove) to ALL those mutually-exclusive branches (no
  runtime duplication). `tsc -b` clean. **Build pending the user's go-ahead.**
- **Round 2 BUILT + installed LOCALLY (2026-07-14, BUILD_ID `20260714113944`, NOT published) — Witcher 3 launcher
  pipeline READY + controller ARTWORK + `icon-changes (3).json`:**
  - **🔴 W3 launcher applier ROOT-CAUSED + rewritten (the mod was about to publish BROKEN).** `witcher3_mod.py` was a
    stale placeholder that copied a `Mods\modHebrew` overlay, but the REAL published mod (GitHub
    `hebrew-translation-hub/witcher3-hebrew-mods` `v1.0.0-beta.1`, `witcher3_hebrew.zip` 3,839,030 B, sha `54c5fddb…`) is a
    **direct base-game patch driven by its own `install.py` + `lib/`** doing 5 mechanisms: 34 `ar.w3strings` →
    `content\`, Hebrew glyph inject into `r4gui.bundle`, subtitle+in-video-USM patch of `movies.bundle`, rename the
    language selector "Arabic"→"Hebrew" across every `*.w3strings`, and a `texture.cache` banner byte-swap; every touched
    file backed up `<f>.he_backup`. **Fix: the launcher now RUNS THE MOD'S OWN install.py IN-PROCESS** (importlib load;
    `lib/` = pure stdlib struct/re) so it deploys EXACTLY what the author shipped + inherits its revert; a cache-free
    `_glob_restore` fallback restores all `.he_backup` even if the mod cache was cleared. `is_applied` = `content\
    content0\ar.w3strings.he_backup` exists. `main_eel` `_w3_download_payload` pick rewritten to find the install.py mod
    root (not `modHebrew`) + cache it at `_w3_mod_root_cache()`; `remove_witcher3_mod` passes it to revert; activation
    msg + the GameDetailPanel `NATIVE_DL_API.witcher3` note → "Options → Language → Text = Hebrew" (the selector now
    literally says Hebrew). **Offline-verified**: applier loads install.py, `install_text` patches 34/34 + backs up,
    `is_applied` True, `_glob_restore` → all-vanilla + is_applied False. `witcher3-hebrew` slug ADDED to the Worker
    `steam_mod_worker/src/index.js` (code only, NOT deployed). GitHub release confirmed a FULL release resolvable via
    `releases/latest`, manifest `version 1.0.0-beta.1` + `sha256 54c5fddb…` MATCHES the zip. **PUBLISH-GATED (nothing
    public done):** at "פרסם" run `cd games/steam/steam_mod_worker && npx wrangler deploy` + `publish_version.py witcher3
    1.0.0-beta.1 --stage beta --sha 54c5fddb935bdb4b4ecbc1d197f4f7fb3b14679784c37e36b79d9b5f8370c04f --size 3839030
    --archive-url https://github.com/hebrew-translation-hub/witcher3-hebrew-mods/releases/download/v1.0.0-beta.1/witcher3_hebrew.zip
    --apply` (flips the coming-soon `games` row → available; the panel is gated on `availability==="available"` so it
    shows "בקרוב" until then). Free mod (no DRM gate).
  - **🎮 Controllers = the user's own PNG artwork** (`build_assets/controllers/{ps5,ps4,xbox}.png`, embedded as data
    URIs in `frontend/src/lib/controllerIcons.ts`): PS5=`gamepad_8940967` (DualSense), PS4=`video-console_7837237`
    (DualShock), Xbox=`xbox_14087662`. Drawn as **CSS masks** (`backgroundColor:currentColor`) since the PNGs are solid
    black — so each pad keeps its accent color (PS blue / Xbox green); an `<img>` would be black-on-black. `ControllerSettings.tsx`
    `TYPE_ICON` maps ps5/ps4/xbox to the mask icons (the inline SVGs removed); icon-manager splits the combined
    "PlayStation (DualSense/DualShock)" target into separate PS5 + PS4 slots showing the real artwork.
  - **`icon-changes (3).json`:** `pad-generic` (שלט כללי) → the user's uploaded ✕◯□△ SVG (`ControllerSettings` GamepadIcon);
    `opt-badge-plugin-active` (פעיל) → **removed** (the new "🚫 ללא אייקון" export worked). **Icon sizes enlarged app-wide**
    (user "תגדיל את האייקונים"): sidebar nav 20→25px, Settings tabs 18→20px, all 78 button/header/badge/empty icons bumped.
  - Built via `build_exe.bat` (BUILD_ID `20260714113944`, exe 9,240,223 B) → ISCC → `Output\TranslationManager-Setup-1.0.2.exe`
    (243,837,616 B) → installed LOCALLY (UAC). Version stays 1.0.2 beta; NOT published.

---


## Notifications-pop + frameless frosted title bar + sidebar-icon px pin + admin crash-copy (2026-07-13, LOCAL build `20260713205203`, NOT published; website DEPLOYED)

Rapid multi-request UX round. **Launcher built+installed LOCALLY (per [[local-install-launcher-builds]]),
NOT published; website admin change DEPLOYED live (`vercel --prod` → 409 "already current" = live).**

- **🔔 New-notification POP as a dedicated glass card (`components/NotifToast.tsx`, NEW).** The pop fired
  but reused the generic gray `reportStatus` toast — not the transparent card the user asked for. NotifToast
  = top-right stacked glass cards (transparent → LESS transparent on hover, `whitespace-pre-line` line
  breaks, slide-in/out, auto-dismiss 8s paused-on-hover, click → open URL/game, dismiss ×). NO backdrop-filter
  (QtWebEngine progressive-blur bug). `App.tsx` renders `<NotifToast/>` + the `notif-pop` handler now only
  fires `api.notifyOs` (the card is the visual). **Firing fixed + testable:** `notifications.ts` — versioned
  seen-keys (`seen2`/`seeninit2`) = one-time reset so a pre-existing test notif can pop; single-path rule
  "pop the ≤2 newest UNREAD+unseen" (no more first-launch swallow); `pushNotif` pops unconditionally
  (mute-respecting); + a **window-focus refresh** (throttled 8s) so an admin-added notification pops within
  ~1s of returning to the app instead of the 5-min poll. `firePop` still no-ops when muted (red dot only).
- **🔴 RED bell dot** (shown even muted) + **mute button glyph is state-driven** (`NotificationsBell.tsx`):
  not-muted → gray **sound-waves** (VolumeGlyph); muted → gold **speaker-x** (MuteGlyph).
- **Notif panel = ONE frosted surface, clip-path entrance (no blur delay).** The old "3-stages / gets milkier"
  bug = animating a transform/opacity UNDER the backdrop-filter → QtWebEngine re-composites the blur
  progressively. Fix: the panel stays `opacity:1` + NO transform; the open/close is a **clip-path wipe** (a
  nub near the bell → full), so `backdrop-filter: blur(9px)` is stable from frame 1. Corner radius **24px** (==
  the home/games `.glass` panel). Cards get `backdrop-filter: blur(6px)` + higher bg opacity = "a bit more
  blurred than the window". Notif links open a **URL via `api.openExternal`** or a **game id via
  `deep-link-game`** (was game-only → a URL never opened); same fix in NotifToast.
- **Sidebar icons pinned to FIXED px** (`Sidebar.tsx`) — `w-12/w-10/w-9` (rem) SCALED with the text-size
  setting and overflowed their 48px slots ("the icon escapes"). Brand avatar→48px, profile avatars→40/36px
  (+ inner UserIcon/badge/lock to `w-[Npx]`), settings gear box→36px. Nav-row icons were already px
  (`<Icon width={20}/>`) so untouched. **Rule: fixed-slot sidebar chrome must use px, not rem, or the
  text-size feature breaks it.**
- **Featured carousel** (`HomeView.tsx`): descender letters (g/y/p) were clipped by `line-clamp-2` +
  `leading-none` → `leading-[1.14] pb-[0.12em]`. `App.tsx` now re-pulls the catalog on window-focus (throttled
  45s) so admin FEATURED changes appear without a manual refresh (the list is derived live from `games`).
- **🪟 Frameless custom title bar → DEFAULT ON + redesigned** (user turned it on, then asked for changes).
  `launcher_prefs.get_custom_titlebar()` default **False→True** (still reversible via Settings + tray).
  `TitleBar.tsx`: **frosted glass** (`backdrop-filter: blur(14px)` + translucent, always-mounted so no
  entrance ramp); window-control glyphs **recolor + glow on hover with NO square hover box** (X→red,
  min→cyan glow, max→yellow glow); **app icon + title text removed** (empty drag region). `main_window.py`:
  **DWM rounded corners** on Win11 via `DwmSetWindowAttribute(DWMWA_WINDOW_CORNER_PREFERENCE=33,
  DWMWCP_ROUND=2)` in a one-shot `showEvent` (the compositor clips the whole surface incl. web content → no
  CSS rounding needed; best-effort, no-op off-Win11). **⚠️ frameless is Qt-level + can't be verified from the
  build env — user confirms drag/resize/close/round in-game; a broken frameless window is undoable from the
  tray.**
- **🌐 Admin site — crash panel COPY buttons (`website/src/components/admin/CrashReportsTab.tsx`, DEPLOYED).**
  Per-report **"📋 העתק"** (copies ALL fields + Traceback + Log tail + Extra as one paste-ready block via
  `navigator.clipboard` + a hidden-textarea fallback) shown on every row without expanding, plus a per-Block
  copy button (Traceback/Log/Extra). `tsc`+`vite build` clean; `vercel --prod` promoted (409=live).

---


## Launcher Designer — "edit the REAL app" visual designer (2026-06-28)

`launcher-designer/` — a SEPARATE Vite+React+TS app (not bundled into the launcher) for
visually redesigning the launcher UI. **Pivoted from a Craft.js from-scratch block editor to
an "edit the real app" inspector** after user feedback that block-replicas didn't look like
the real software. The user explicitly chose this (AskUserQuestion): "התוכנה האמיתית + עריכת
כל אלמנט". Run: `cd launcher-designer && npm install && npm run dev` → http://localhost:5180
(run with NO trailing args — a pasted `→ http://localhost:PORT` annotation becomes vite's
`root` arg → blank/wrong-port). Full docs: `launcher-designer/README.md`. Verified end-to-end
in headless Chrome (playwright-core + the system Chrome `executablePath`; the
`npx playwright install chromium` download times out here — use the installed browser).

- **The preview = the REAL app, 1:1.** `preview.html` + `src/preview/main.tsx` mount the actual
  `@fe/App` (`@fe` → `../frontend/src`) with the real `@fe/index.css`. A Vite plugin
  `designer-mock-eel` (`vite.config.ts`) swaps ANY import resolving to the launcher's eel
  backend (`lib/eel`) for `src/mock/eel.ts` — a full mock of eel's 7 exports (`api`, `jsLog`,
  `isReady`, `onModProgress`, `onLauncherUpdateProgress`, `onCatalogRefreshComplete`,
  `safeReportCrash`) returning sample games/news/user/prefs. So the real App + all views +
  hooks render with believable data and NO Qt/Eel runtime. (Multi-page build: index.html =
  inspector, preview.html = real app.) Headless-verified: real sidebar + Hero + stat cards +
  game cards with real cover art, 0 pageerrors.
- **The inspector (`src/App.tsx`).** An `<iframe src="/preview.html">` (same-origin → full
  access) + a properties panel. "בחירה" ON → hovering the iframe highlights elements, clicking
  selects one (capture-phase listener on the iframe document `preventDefault`s so the app's own
  click doesn't fire). The panel edits the selected element: background/color/font/padding/
  margin/border/radius/width/height/opacity/text-align, **free move** (transform translate),
  **text**, and **hide**. To change screen: turn בחירה OFF, click the real sidebar in the
  preview, turn בחירה back ON.
- **Override model (`src/inspector/overrides.ts`).** Each edit is stored keyed by a STABLE
  selector (`cssPath` = an `:nth-child` path anchored at `#root`). `buildCss` → one stylesheet
  (`sel{prop:val!important}`, `display:none` for hidden); injected as `<style id="design-
  overrides">` into the iframe (survives React re-renders). Text = best-effort DOM pass. Export
  → `design-overrides.json`; persisted to localStorage.
- **The design BECOMES the real launcher.** `frontend/src/designer/applyOverrides.ts`
  (`initDesignOverrides`/`applyDesignOverrides`) — framework-free, mirrors `buildCss`; injects
  the SAME `<style>` + a MutationObserver-backed text pass. Wired into `frontend/src/main.tsx`
  (`initDesignOverrides()` before `createRoot`), reading `frontend/src/designer/design-overrides.json`
  (default **`{}`** ⇒ guaranteed no-op, shipping launcher byte-identical). To apply a design:
  replace that JSON with the designer's export + rebuild the launcher (`build_exe.bat`).
- **Headless E2E proof:** clicked the real Hero primary button → panel selected it (selector
  `#root > … > main…`); set background → the real element went brand-yellow→green live + the
  `<style>` was injected. Both apps build green; `frontend` tsc clean.
- **Limitations (stated to user):** it's RESTYLE-the-existing-UI (per-element CSS/text/hide/
  nudge), not drag-new-components-from-scratch. Text/hide are best-effort. The obsolete Craft
  approach files (`blocks.tsx`/`launcherBlocks.tsx`/`RenderNode.tsx`/`renderDesign.tsx`/
  `sample-design.json`) were DELETED in the pivot; `@craftjs/core` stays in package.json,
  unused.


## GameDetailPanel "page-2" cinematic layout (2026-06-28)

The game-detail screen (`frontend/src/views/GameDetailPanel.tsx`) was re-laid-out from the
old 3-column grid (`[380px_1fr_300px]` = cover-right · info-center · settings-sidebar) to the
**page-2 design the user drew in PowerPoint** (`עריכת תוכנה.pdf`):
- **Top row** `grid-cols-[minmax(220px,260px)_1fr_320px]` (RTL → right·center·left):
  **actions stacked top-RIGHT** (▶ הפעל + the per-game install/remove/buy branch), **title +
  status badges + tagline + description + progress + contextual notes in the CENTER**, **large
  cover on the LEFT**.
- **Bottom**: a **full-width COLLAPSIBLE "הגדרות" drawer** (`settingsOpen` state, default open,
  ▲/▼ toggle) holding everything that used to be the right sidebar, in 3 sub-columns
  (RTL right→left): install-path + שמור/נקה + פתח תיקייה + the language switch · the beta opt-in
  + ניקוי מטמון התרגום · the stats block (זמינות/גרסה/התקנה/תמיכת מוד/סטטוס מוד).
- **ALL logic preserved byte-for-byte** — every branch (CP2077 `gm.modSlug` download mod, SM2,
  WD2, GTA, Anno note, legacy enable/disable), purchase + burst-poller, language switch, beta
  toggle, progress streams. Only JSX layout moved: the action branch was extracted to an
  `actionButtons` fragment and the settings to a `settingsBody` fragment; badges flipped
  `justify-end`→`justify-start` (sit under the LTR title). `tsc` + `vite build` clean.
- **Verified in the designer (headless Chrome, real App 1:1):** detail panel renders with 0
  pageerrors — cover-left, title+badges-center, actions-right, drawer-bottom; the ▲/▼ collapse
  works. This IS the designer's purpose: a structural region-move like this is done in code
  (per-element CSS overrides can't reflow whole sections), then the designer fine-tunes each
  element on top of the new layout.


## Launcher DESIGN questionnaire (2026-06-28)

A separate 104-question RTL-Hebrew design questionnaire for the LAUNCHER (distinct from the
admin/site one). Goal captured from the user: top-tier, smoothest/fastest/most-convenient,
"beyond Steam Big Picture". Built like the admin questionnaire:
- **Generator:** `_faq_build_launcher/build_launcher_questionnaire.py` reads every `*.json`
  category there → emits the self-contained `שאלון-עיצוב-התוכנה.html` at the repo root (the
  admin `שאלון-התאמה-אישית.html` from `_faq_build/` is UNTOUCHED). Rebuild:
  `python _faq_build_launcher/build_launcher_questionnaire.py`.
- **11 categories** (`01_overall`…`11_extra`): overall look/vibe, sidebar+nav, home/hero,
  game cards, detail panel, buttons/colors, typography, motion/background, secondary screens,
  UX/behavior (incl. a Big-Picture + full keyboard/controller-nav question), and a window/
  details/inspiration extra. Schema per Q: `{q,help,multi,allowFree,options:[{label,desc}]}`.
- **Keyboard control (user-requested):** options show number badges; **1–9 select**,
  **←/↓/Space/Enter advance**, **→/↑/Backspace go back**, guarded so it never hijacks the
  free-text box (Esc blurs it) or double-fires on a focused button. A `⌨` hint line shows the
  keys per question. Wizard one-Q-at-a-time + side category list + autosave to localStorage +
  save/load JSON + copy-text summary (same engine as the admin one).
- Headless-verified: 104 side rows, pressing "3" selects option 3 (counter→1/104), arrows
  navigate, 0 pageerrors. The user fills it → exports → I implement the design from the answers.


## Premium UI overhaul — WeMod/Steam-grade (2026-06-28)

User feedback: the launcher looked "too simple and basic" → wanted WeMod/Steam-level polish.
A cohesive visual upgrade across the launcher's face (home/library/cards/sidebar/detail), all
verified headless in the designer (real App 1:1) + `tsc`/`vite build` clean.

- **Design tokens.** `frontend/tailwind.config.js` gained keyframes/animations: `rise`,
  `shimmer`, `sheen`, `float`, `gradient-pan`, `glow-pulse`. `frontend/src/index.css` gained a
  "premium UI kit": `.text-gradient` (brand gradient heading/number text), `.sheen-layer`
  (moving light sweep on `.group:hover` — used on primary buttons), `.grid-texture` (masked
  accent grid for hero/banners), `.lift` (hover translateY + shadow), `.stagger` (staggered
  child entrance), `.scroll-x` (hidden-scrollbar horizontal scroller). **Self-contained
  `@keyframes rise`+`sheen` are declared in index.css** (don't depend on Tailwind emitting
  them — `sheen` has no `animate-sheen` utility usage, and `.stagger`'s `opacity:0` would hide
  content if the keyframe were missing).
- **`launcher-designer/tailwind.config.js` MUST mirror** the frontend keyframes/animations (it
  processes `@fe/index.css` for the preview) — updated in lockstep. If they drift, `.stagger`
  elements render invisible (opacity:0, no keyframe) in the designer preview only.
- **`HomeView.tsx` — clean premium BRAND hero** (no featured game). NOTE: a first pass put a
  cinematic featured-game spotlight (blurred game backdrop + tilted cover-art card) in the hero;
  the user rejected it — the blurred backdrop "looked cut off" (קטוע) and they wanted the home
  top WITHOUT the recommended game. Current hero = centered brand pitch: gradient title, eyebrow,
  pitch, a sheen "▸ עיין בספרייה" primary CTA + site link, over a `grid-texture` + ambient
  brand glows (no game art, no backdrop image). Stat cards got icons (inline SVG), accent glow
  corners, gradient numbers, `.lift`. The "תרגומים מובילים" featured ROW (lower down) stays.
- **`GameCard.tsx`** — per-game **accent glow** + accent ring on hover (`hover` state →
  boxShadow `${accent}80`), cover zoom, a centered "▸ פתח" reveal pill, an accent wash, and a
  pulsing green "active mod" dot. `.lift` for the smooth rise.
- **`LibraryView.tsx`** — gradient title + count subtitle, sheen on the scan button, section
  headers with accent count-pills + glowing bars + gradient dividers, `animate-rise`.
- **`Sidebar.tsx`** — active nav row gets an accent glow on the indicator bar + a soft accent
  wash. `DownloadsView`/`SettingsView` h1 → `.text-gradient` for cross-screen consistency.
- All dynamic colors are inline styles (per-game accent) — the lint "no inline styles"
  warnings are expected/unavoidable for that.


## Launcher design questionnaire → implementation WAVE 1 (2026-06-28)

The user filled the 104-question launcher design questionnaire (`עיצוב-התוכנה-בחירות.json`,
104/104). Decoded against `_faq_build_launcher/*.json` (the answer file is mojibake when
viewed raw but UTF-8-clean on disk; `scratchpad/decode_answers.py` cross-joins answers↔options
into a readable brief). The active (non-"current") directives drive a multi-wave premium
overhaul. **WAVE 1 SHIPPED** (BUILD_ID `20260628014118`, dev_build 11, `launcher_releases`
id=48, `/api/launcher` buildId == baked, verified). All frontend, headless-verified in the
designer (real App 1:1, 0 code pageerrors — the lone console 404 is an external cover image).

- **Per-game accent paints the whole app** (brief 01-Q10 / 08-Q3). New
  `frontend/src/lib/useAccent.tsx` (`AccentProvider`/`useAccent`/`useSetAccent`) sets a
  `--accent` CSS var on `:root`; App renders a fixed `.accent-bg` layer (index.css, two
  drifting blurred blobs, z:1 between the video and the z:10 shell). `GameDetailPanel` calls
  `useSetAccent(accentFor(theme_key))` → background tints to the open game's color, restores
  the neutral `#00ffe0` default on close. Verified: opening Cyberpunk flips `--accent`→`#fff700`.
- **Global click ripple** (06-Q6). `frontend/src/lib/ripple.ts` `initRipple()` — ONE
  capture-phase `pointerdown` listener spawns a `.ripple-ink` span in any `<button>` (skips
  `disabled` / `data-noripple`), forces `position:relative`+`overflow:hidden` if needed. Wired
  once in App via `useEffect(() => initRipple(), [])`. Non-invasive (no per-button edits).
- **Animated hero + rotating recommended carousel** (03-Q2, 03-Q9, 08-Q1). Reconciles the
  earlier "remove the cut-off spotlight" with the questionnaire's "yes, a rotating carousel":
  the clean brand hero stays (03-Q1) + gets a subtle `.aurora` drifting layer; a NEW
  `FeaturedCarousel` (in HomeView) sits below it — a CONTAINED, well-masked spotlight (cover
  fills the LTR/left side, mask-fades into the glass; title+tagline+▸פתח on the RTL/right;
  auto-advance 6 s, pause-on-hover, arrows + dots). Not full-bleed → never looks cut off.
- **GameCard green border for active** (04-Q5): `ring-2` green + green glow when
  `mod_state==="ACTIVE"` (hover still wins with the accent ring).
- **Library grid/list toggle + sort** (04-Q7, 04-Q9): a toolbar with grid/list view buttons
  and a state/name/version sort. Default = grouped-by-state sections (unchanged). New `GameRow`
  compact list item. `sort==="state"`→grouped; else a flat sorted block in the chosen view.
- **Premium CSS kit** (index.css): `@keyframes aurora-drift/aurora-pan/ripple-out/
  skeleton-sweep`; `.accent-bg`, `.aurora`, `.ripple-ink`, `.skeleton`; scrollbar now
  **hidden-until-hover** (transparent thumb, fades in on `*:hover`) per 11-Q6;
  `prefers-reduced-motion` kills the looping ambient/skeleton anims. These are plain CSS in
  index.css (NOT Tailwind utilities) → ship regardless; no tailwind.config change needed.
- **REMAINING WAVES (queued, from the same brief):** Wave 2 (frontend) = collapsible sidebar
  (02-Q2) + stronger active glow + monochrome→color icons (02-Q3/Q6), Settings side-tabs
  (09-Q3), detail-panel redesign + **version history like the website** + **wide background
  banner + logo (Steam-style)** (05-Q1 free, 11-Q12 — needs new image fields/fallback to
  blurred cover), changelog "what's new" modal (11-Q10), friendly empty states (09-Q7),
  skeleton loaders in data spots (06-Q8). Wave 3 (heavy/structural) = **Big Picture full-screen
  mode** + **full keyboard nav** + **controller support** in a console-familiar layout (10-Q2/
  Q3/Q4, 11-Q16 free), user theming controls (10-Q8 / 01-Q11), launch splash (08-Q7),
  onboarding tour (11-Q8), optional sounds w/ toggle (11-Q3), generous tooltips (11-Q7),
  frameless custom titlebar (11-Q1), parallax (08-Q5). Tone = professional/clean (11-Q14);
  agent may decide small things, consult on big (10-Q10).


## Launcher design — WAVES 2 + 3 (2026-06-28)

User decided (AskUserQuestion): banner = **hybrid** (blurred-cover default now +
optional `bannerUrl`/`logoUrl` override later), work order = **"הכול ואז שיגור אחד"**
(build all of Waves 2+3, ONE ship). **SHIPPED** (BUILD_ID `20260628022701`, dev_build
12, `launcher_releases` id=49, `/api/launcher` buildId == baked, verified). Every piece
headless-verified in the launcher-designer (real App 1:1; 0 code pageerrors) + `tsc -b`
clean. All frontend except where noted.

- **Collapsible sidebar** (`Sidebar.tsx`): persisted `localStorage.sidebarCollapsed`,
  width 230↔72, chevron collapses / the brand avatar expands; collapsed = icon-only nav +
  icon-only auth/settings; stronger active glow; monochrome icons that colorize on hover
  via `group-hover:[color:var(--ic)]`. Verified 230→72→230.
- **Settings → side-tabs** (`SettingsView.tsx`): RTL side tab-list (כללי / מראה / עדכונים /
  פרטיות / נתיבים) + content pane. ALL existing toggles/sections preserved, just reorganized.
- **Theming (`lib/themePrefs.ts` + Appearance tab)**: animations on/off (`html.reduce-anims`
  kills transitions/anims), density comfortable/compact (`html[data-density=compact]` → 14.5px
  rem base), neutral ambient accent swatches (drives `useAccent` default; live-applies), and
  optional UI sounds. `initThemePrefs()` applies anims+density before React mounts (App).
- **Detail panel** (`GameDetailPanel.tsx`): a **cinematic Steam-style hero banner** (`bannerUrl`
  override → else blurred/zoomed cover, accent scrim, back button overlaid, `logoUrl` → else the
  English title as the logo); the info column H1 became the **Hebrew** title (complementary, not
  a dup); a **"✨ מה חדש"** button → `ChangelogModal` (bulletizes `game.changelog`); a
  **`VersionHistory`** section that fetches the hub's public `GET /api/games?action=history&game=<id>`
  (fields `version/stage/changelog/publishedAt/isCurrent`) and renders a timeline — renders
  nothing on offline/empty. `Game` gained optional `bannerUrl`/`logoUrl` (types.ts).
- **Empty states + skeletons**: `EmptyState.tsx` (icon bubble + CTA) used in the library empty
  branch; `GameCard` shows a `.skeleton` shimmer until the cover image loads.
- **Per-game accent + ambient background** (Wave-1 carryover): `useAccent` now defaults to the
  themePrefs neutral accent; `setAccent(null)` re-reads it live.
- **Launch splash** (`SplashScreen.tsx`): branded animated boot overlay (~2 s, fades), skipped
  instantly when animations are off. Shown once on boot (App `splashDone`).
- **Onboarding tour** (`OnboardingTour.tsx`): first-run animated 4-step modal carousel
  (localStorage `onboardingDone`), shown after the splash; skippable; keyboard-navigable.
- **Console-style keyboard + controller nav** (`lib/spatialNav.ts`): ONE document handler —
  arrow keys move focus to the nearest focusable in that direction (only `preventDefault`s when
  it actually moves, so scrolling still works), Backspace → `nav-back`; a `requestAnimationFrame`
  Gamepad loop maps D-pad/left-stick → directional moves, A→click, B→`nav-back`, Start→
  `toggle-bigpicture`. Strong `:focus-visible` ring (index.css, accent-colored). App listens to
  `nav-back` (contextual back: close game → else home; ignored while Big Picture is open).
- **Big Picture mode** (`BigPictureMode.tsx`): full-screen console-familiar overlay — cinematic
  backdrop + big centered spotlight (cover + Hebrew title + ▸פתח) + a bottom cover strip; ←/→
  (or D-pad/stick/wheel) change selection, Enter/A opens (exits BP + opens detail), Esc/B exits.
  Owns the keyboard via capture-phase + `stopImmediatePropagation` so global nav doesn't double-
  fire. Toggled from a Home hero "🖥 מצב מסך-מלא" button or the controller Start (App owns the
  `toggle-bigpicture` state). Verified open→navigate→Esc-close, 0 errors.
- **Optional UI sounds** (`lib/sound.ts`): synthesized Web-Audio click on button press, gated by
  the themePrefs `themeSounds` (default OFF). `playClick/playSuccess/playError` available.
- **DEFERRED (deliberately, NOT shipped): the frameless custom titlebar (11-Q1).** It's
  Qt-coupled (`main_window.py` FramelessWindowHint + startSystemMove/startSystemResize + a
  JS↔Python min/max/close bridge) and **cannot be verified from this environment** (the designer
  is a browser, not Qt), and a wrong frameless setup can break window drag/resize/close. Per the
  user's own "consult on big" (10-Q10) + their high stability priority, it's left as a separate
  step to implement WITH the user available to confirm the live window. Everything else from the
  104-answer brief is in.


## Launcher polish — stability + server banners/logos + Big Picture fix (2026-06-28)

Follow-up after the Waves-1/2/3 ship. User report: "the new app moves really slowly and is
unstable", + 3 asks (server-served banner/logo images, pinned settings drawer, a Big-Picture
bug). SHIPPED (BUILD_ID `20260628032218`, dev_build 13, `launcher_releases` id=50,
`/api/launcher` buildId == baked, verified). All headless-verified in the launcher-designer
(real App 1:1, system Chrome via `playwright-core`) — **0 code pageerrors**.

- **PERF/STABILITY regression FIXED (the #1 complaint).** The Wave-1 premium kit added
  continuously-animating GPU-expensive layers that janked Qt WebEngine (Chromium):
  - `index.css` `.accent-bg` was two **`filter: blur(90px)` 46rem blobs animated infinitely**
    (`aurora-drift`) sitting BEHIND the main `.glass` panel's `backdrop-filter: blur(28px)` →
    Chromium re-rasterized a huge blurred surface every frame, then re-blurred it for the
    backdrop. Made them **STATIC soft radial-gradients** (no `filter`, no animation, no
    `will-change`) — a `radial-gradient(...transparent 70%)` already looks like a soft blob for
    free. Same for `.aurora` (dropped `blur(20px)` + `aurora-pan`). Removed `will-change:
    transform` from `.lift` (was forcing a compositor layer per card).
  - `lib/spatialNav.ts` ran a **permanent `requestAnimationFrame` gamepad poll** (60fps) even
    with NO controller connected → constant CPU tax. Now the poll **only runs while a pad is
    connected** (`gamepadconnected`/`gamepaddisconnected` start/stop; checks already-connected at
    init). This is the general lesson: never leave an idle rAF loop running.
- **Per-game banner + logo images, served from the SERVER (not bundled — keeps the install
  small).** Source art `Downloads\…\תיקיה חדשה (4)` (per game: `<Name>.png/jpg` = wide
  background, `<Name>-.png` = transparent logo). `scratchpad/upload_banners.py` mapped each file
  to a `games.id` by normalized `title_en`, compressed (banners → webp ≤1600px q82, logos → png
  ≤360px keeping alpha), and uploaded to the public `covers` bucket under `banners/<id>.webp` +
  `logos/<id>.png` (25 games, 50 images, ~7 MB, 0 unmatched). New DB columns
  `games.banner_url` + `games.logo_url` (migration via psycopg2 `SUPABASE_DB_URL`). Wired
  through BOTH shapes: website `api/games.ts` (`DbGame`/`shape→bannerUrl,logoUrl`/`toRow`/
  `WRITABLE_GAME_COLUMNS`) and the launcher `main_eel.py:_shape_supabase_game` (the launcher REST
  uses `select=*` so the columns flow once mapped). `GameDetailPanel` already consumed
  `game.bannerUrl`/`game.logoUrl` (Steam-style hero) with a blurred-cover/title fallback when
  absent. Website redeployed (`vercel --prod`); `/api/games` now returns `bannerUrl`/`logoUrl`.
  Covers were already server-side, so total launcher install size is UNCHANGED.
- **Settings drawer PINNED to the panel bottom** (`GameDetailPanel.tsx`). The "הגדרות"
  collapsible drawer used to live inside the scroll area → it scrolled away. The panel root is
  now a flex column: a `flex-1 min-h-0 overflow-y-auto` content area (hero + info + version
  history) + a `shrink-0` drawer pinned at the bottom; the drawer body is `max-h-[46vh]
  overflow-y-auto` so a tall settings grid never overflows. Headless-proven PINNED (drawer Y
  unchanged after scrolling content to the bottom).
- **Big Picture bug FIXED** (`App.tsx`). Opening a game from Big Picture used to
  `setBigPicture(false)` → it dropped to the windowed detail. Now BP **stays full-screen**: BP's
  `onOpenGame` just `setSelected(g)`; while `bigPicture && selected` the detail renders as a
  full-screen `z-[180]` overlay (back → `setSelected(null)` returns to the cover grid, BP stays
  on); the main-area branch is gated `!bigPicture && selected` so there's no double-mount; the
  `nav-back` handler routes BP-detail → grid; exiting BP clears `selected`. Headless-proven
  (detail renders inside the z-180 overlay after Enter in BP).


