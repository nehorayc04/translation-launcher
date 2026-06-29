# Translation Launcher

A Windows desktop launcher for Hebrew game-translation mods. Built with
**Eel** (Python ↔ Chromium bridge), a React + Vite frontend, and packaged
as a standalone installer via PyInstaller + Inno Setup.

The launcher fetches a games catalog from the public translation hub
API, displays available titles, downloads the matching translation
archive, and copies it into the game's mod folder.

---

## 🎛 orchestration/ — the control plane (READ FIRST, 2026-06-29)

A top-level management layer above every game + every profile, so the solo dev
(Nahorai) drives the whole multi-agent operation from ONE place instead of
hand-writing instructions to each agent in each profile. Full docs:
`orchestration/README.md`. **The operating charter is `orchestration/DOCTRINE.md`
(READ FIRST) — finish to the end, full power on hard problems, cut fast on dead-ends/
trivia, no weak shortcuts, double-check everything (never trust an agent's "done"),
elite model per role.** Decisions (user, AskUserQuestion):

- **Brain = a single MAX Claude Code session.** It holds all state, generates all
  agent instructions, routes tasks. PRO + Google/Antigravity agents only execute.
- **Delivery = one-liner file pointer.** The brain writes the full instruction to a
  repo file; the user pastes ONE line per agent (`קרא <file> ובצע`). Requires the
  same repo folder open in each Antigravity profile.
- **Roles:** MAX = orchestrate + heavy launcher/site work · PRO = overflow when MAX
  quota hits (via `orchestration/HANDOFF.md`) · 3-5 Google agents = parallel
  translate/QA (interchangeable slots, `N` per task).
- **Full-auto with 3 hard gates.** Auto without asking: instruction generation,
  output merge + structural QA, shared-rule updates, board refresh. **Requires
  explicit user OK:** (1) publishing a mod (GitHub/Worker/site), (2) shipping the
  launcher (rebuild + `publish_release`), (3) deleting/overwriting real game files.
- **Initiative = propose + wait.** Each session, read the board and propose the best
  next step; wait for approval before acting.
- **Command vocabulary** (`orchestration/COMMANDS.md`): `מצב/status`,
  `תרגם/translate <game> <N>`, `בקר/qa <game> <N>`, `מזג/merge <game>`,
  `בנה/build`, `פרסם/publish` 🔒, `שגר לאנצ'ר` 🔒, `כלל/rule "<text>"`,
  `חדש/new <game>`, `המשך/continue` (PRO).
- **Files:** `MISSION.md` (the board the user opens — auto-generated, never edit by
  hand) · `state.json` (source of truth) · `RULES.md` (shared cross-game rules +
  per-game pointers + a changelog; a new universal rule is appended here AND applied
  to future handoffs) · `HANDOFF.md` (MAX→PRO handoff) · `orchestrate.py`
  (`board`/`status`/`set`/`dispatch`/`clear-dispatch`). Regenerate the board:
  `python orchestration/orchestrate.py board`.

When the user gives a short command in any MAX/PRO session in this repo, treat it as
an orchestration command, act per the gates above, then `orchestrate.py board`.

---

## Repository layout (post-2026-05-27 reorg)

The root holds only the launcher build + game data; everything else
lives under `games/<game>/`, `universal/`, or `_archive/`.

| Path | Purpose |
|---|---|
| `main_eel.py` / `main_qt.py` | Launcher entry points (Eel and Qt). |
| `translation_manager/` | Python application package — UI views, asset/download logic, game detection, theme, paths, SWR cache, Steam mod lifecycle. |
| `frontend/` | React + Vite UI rendered inside the Eel window. Build output is bundled into the executable. |
| `build_assets/` | Installer artwork (icon, wizard BMPs, store screenshots) used by Inno Setup + PyInstaller. |
| `build_exe.bat` | One-shot build script: builds the frontend, runs PyInstaller, then Inno Setup. |
| `installer.iss` | Inno Setup script. |
| `TranslationManager.spec` / `TranslationManager_qt.spec` | PyInstaller specs — declare hidden imports, data files, icon, console behaviour. |
| `publish_release.py` / `monitor_push.py` | Launcher-release publisher + universal live-progress push library. |
| `games.json` / `news.json` / `updates.json` | Public launcher catalog data (snapshot for offline use; the live source is the Worker). |
| `Cyberpunk 2077/` | The staging copy of the game the user actually plays + the mod-deploy target (`archive/pc/mod/`). |
| `תרגום_משחקים/` | The CP2077 translation source data (1.4 GB — `source/resources/localization_translated.json` is the spine). |
| `games/cyberpunk2077/` | Every CP2077-specific Python script, batch file, state JSON, and the GitHub release zip. |
| `games/steam/` | The Steam UI translator + its `steam_hebrew_output/` + the Cloudflare Worker source + the GitHub release zip. |
| `universal/` | Game-agnostic infra: cross-validation audit (`continuous_audit_loop.py` + `get_next_audit_batch.py` + `filter_existing_flags.py` + sidecars), the `progress_monitor/` package, and the `visual_bridge/` Visual LQA capture backbone. Sidecars (`cross_audit_*.json`, `audit.lock`) live alongside the scripts here. |
| `website/` | The public translation-hub site (Vite + React + Tailwind + Supabase + Vercel functions) — **its own git repo**, pushed to `github.com/nehorayc04/A-translation-hub`. The outer repo ignores it (`/.gitignore`); to commit/push site changes, `cd website` and use git there. Old chat sessions for this project moved with the folder — see "Claude Code sessions" below. |
| `_archive/{logs,backups,old_reports,scratch,images,shortcuts,obsolete_artifacts}/` | Inert/historical files. Nothing in the active pipeline reads these. |
| `winget-manifest/` | Winget package manifest for the launcher. |
| `Output/` / `dist/` / `build/` | PyInstaller + Inno Setup output (gitignored). |

### Adding a new game

The project is structured so a future game gets its own subtree without
touching anything else:

1. Create `games/<gamename>/` and drop its translator scripts +
   resource pulls there.
2. If it needs the universal cross-validation audit, write a thin
   adapter for `universal/get_next_audit_batch.py` (read its data,
   yield rows) and a thin `universal/progress_monitor/adapters/<gamename>.py`
   for the live-progress TUI.
3. Add the launcher card in `frontend/src/views/AppsView.tsx` /
   `GamesView.tsx` and the lifecycle module in
   `translation_manager/<gamename>_mod.py`.
4. Publish the mod archive through `publish_release.py` (launcher) or
   a `games/<gamename>/pack_and_release.py` (per-game).

The universal audit's data path is computed as `HERE/../תרגום_משחקים/...`
in `get_next_audit_batch.py` — for a different game it would be
`HERE/../games/<gamename>/data/...` or similar.

### Claude Code sessions

Claude Code stores per-project chat history in
`C:\Users\nc528\.claude\projects\<encoded-cwd>\`. The encoding maps
each non-alphanumeric char to `-` (case-preserved). When the website
project was moved into `website/` on 2026-05-27 the old chat folder
`c--Users-nc528--------------------------\` was renamed to
`c--Users-nc528-----------------------website\` so the two prior
sessions (13 MB) auto-load when you open Claude Code in `website/`.

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

## Dev setup

Prerequisites: **Python 3.11+**, **Node 20+**, **Windows 10/11**.

```bash
# Python deps (run from the repo root)
python -m venv .venv
.venv\Scripts\activate
pip install -r translation_manager/requirements.txt

# Frontend deps
cd frontend
npm install
```

---

## Running locally

```bash
# Terminal 1 — frontend dev server (HMR)
cd frontend
npm run dev

# Terminal 2 — Eel host (Python)
python main_eel.py
```

For a one-shot production-mode launch (frontend already built into
`frontend/dist/`):

```bash
cd frontend && npm run build && cd ..
python main_eel.py
```

---

## Building the installer

`build_exe.bat` is the canonical end-to-end build:

1. `npm run build` inside `frontend/` — produces `frontend/dist/`.
2. `pyinstaller TranslationManager.spec` — bundles Python + frontend
   into `dist/TranslationManager/`.
3. Inno Setup compiles the installer into `Output/TranslationManager-Setup-<version>.exe`.

Latest signed builds: see
[Releases](https://github.com/nehorayc04/translation-launcher/releases).

### Re-release rule — build-id (in-app self-update)

The launcher version stays **v1.1.0** and is re-released in place. The
in-app self-updater therefore can't tell two builds apart by version, so
it compares a **build-id**: `build_exe.bat` bakes a fresh UTC timestamp
into `translation_manager/_build_info.py` (gitignored) on every build,
and `get_launcher_update_info` offers an update when the release feed's
build-id differs from the running build's.

**Every re-release MUST**, with the same build-id throughout:

1. Run `build_exe.bat` (bakes a new `BUILD_ID` into `_build_info.py`).
2. Compile `installer.iss`, replace the GitHub `v1.1.0` release asset
   in place (`gh release upload v1.1.0 --clobber`).
3. PATCH the `launcher_releases` row (id 14) with the new `sha256`,
   `size_bytes` **and `build_id`** — the build-id must equal the value
   in `_build_info.py`. Confirm the row stays `is_current = true`
   (the public `/api/launcher` returns 204 if no row is current).

If the baked `BUILD_ID` and the DB `build_id` ever diverge, every
launcher shows a perpetual false "update available".

The installer force-closes a running launcher before the file copy
(`installer.iss` `[Code]` `KillRunningLauncher` — poll-kill + settle +
file-lock probe) and relaunches it non-elevated (`[Run]`
`runasoriginaluser`); this covers both a manual install-over-old and
the in-app self-update.

> ⚠️ **`build_exe.bat` MUST stay CRLF.** It is a Windows batch file —
> cmd.exe needs CRLF line endings. If an editor / `git autocrlf` rewrites
> it to LF, cmd silently mis-parses it (REM comments run as commands,
> `'… is not recognized'`, `was unexpected at this time`) and the script
> never actually builds. The danger is a SILENT stale ship: a wrapper that
> only checks `test -f dist/.../TranslationManager.exe` then proceeds to
> Inno Setup + `publish_release.py` will package and publish the PREVIOUS
> build (old `_build_info.py` ⇒ old BUILD_ID), so the DB build-id equals
> what users already run and the self-updater never fires. **Always verify
> after a build:** `_build_info.py` BUILD_ID is a fresh timestamp AND the
> `dist` exe mtime is "now" before compiling/publishing. Fix endings with
> a byte-level LF→CRLF rewrite (no BOM). Hit + fixed 2026-06-14.

### CP2077 mod v1.0.2 published + launcher v1.1.0 re-release (2026-06-14)

Shipped the QA'd CP2077 base-game mod and propagated the version-compare fix.

- **Mod published — `v1.0.2`** on `nehorayc04/cp2077-hebrew-mods` via
  `pack_cp2077_mod.py 1.0.2` (full release, NOT prerelease, so the Worker's
  `releases/latest` resolves it). The Worker now serves
  `/cp2077-hebrew/manifest` → `version:"1.0.2"`, sha256
  `8b91b55e4e9a9acb2db532d256d07ce9821a75b3b64fe816701a62129a2da55a`
  (92.3 MB zip — all 3 archives, ~206 verified semantic fixes baked in).
  **`pack_cp2077_mod.py` `MOD_DIR` was repointed** to
  `Game Lab/Cyberpunk 2077/archive/pc/mod` (where the bake scripts deploy —
  the old `Cyberpunk 2077/…` path was empty).
- **Version-scheme conflict + fix (`_parse_version`).** The mod scheme moved
  from dates (`2026.05.22`) to semver (`1.0.x`), but the Worker was serving
  `2026.05.22` and the launcher compares numerically: `(1,0,2) < (2026,5,22)`,
  so `1.0.2` read as OLDER → no update ever offered. **Fixed `_parse_version`
  in `main_eel.py`**: any date-scheme version (major ≥ 2000) is ranked BELOW
  every semver via a leading `0`/`1` scheme tag → `1.0.2 > 2026.05.22` now
  True. (The Qt build uses this — `main_qt.py` imports `main_eel`; the bridge
  routes `check_game_mod_update`/`get_mod_updates` there.) The fix only
  reaches installed launchers via a launcher self-update, hence:
- **Launcher re-released in place as `v1.1.0`** (build-id self-update).
  `build_exe.bat` (fresh BUILD_ID `20260613211237`) → `ISCC installer.iss`
  → `publish_release.py 1.1.0` (clobber GitHub asset + Supabase
  `launcher_releases` insert/flip is_current). Verified end-to-end:
  `/api/launcher` → `version 1.1.0`, `buildId 20260613211237` (== baked
  `_build_info.py`, no divergence), sha256 `78f88a00…`. **First attempt
  silently shipped the June-10 stale build** (the LF bug above) — caught by
  the BUILD_ID check (`20260609231927`), fixed, rebuilt, re-published.
- **The public website shows the mod version from a SEPARATE source** — the
  Supabase `games` table (`version` + `download_url` columns, edited via the
  admin GamesTab), NOT the Worker manifest or the GitHub release. Publishing
  the mod does NOT touch it, so the site kept showing `v1.0.1`. On every mod
  release also PATCH `games?id=eq.cyberpunk` (service key from `website/.env`):
  bump `version` → `v1.0.2` and repoint `download_url` to the new release zip
  (`…/releases/download/v1.0.2/cyberpunk_hebrew_translation.zip`). The launcher
  reads the Worker manifest; the website reads the `games` table — keep both in
  sync. (Done 2026-06-14.)

### Security + bug audit and fixes (2026-06-14)

A 10-auditor adversarially-verified security/bug audit of the launcher + website
(full report: `SECURITY_AUDIT_2026-06-14.md`). 23 confirmed findings (1 "critical"
= **by design, not a bug**: the mod archive is intentionally free to download
manually; payment buys the launcher's auto-install/update convenience, so the
public Worker archive route is expected). Real fixes shipped:

- **Launcher self-update hardening** (`main_eel.py` `_run_launcher_update`):
  SHA-256 is now **mandatory** (no feed hash → abort, never run an unverified
  installer) and the download URL must be **HTTPS on an allowlisted host**
  (`_is_trusted_update_url` → github/githubusercontent/hebrew-translation-hub).
  Closes a MITM/redirect→RCE path on the unsigned installer. (Authenticode
  signing still TODO — needs a cert.)
- **Launcher GUI-freeze bug** (`qt_shell/bridge.py` `get_game_language`): now
  wrapped in `_run_off_thread` — it could do a blocking ~2.5 s `auth_owns_game`
  HTTPS call on the GUI thread for a paid title.
- **Launcher cache race** (`swr_cache.py` `_build_snapshot`): iterate
  `_mem.copy()` (atomic under the GIL) instead of the live dict — kills the
  "dictionary changed size during iteration" persist crash under the Qt poller.
- **Website PayPal capture** (`api/paypal.ts`): a COMPLETED capture with a
  missing amount/currency is now REJECTED (was `if (cap.amountValue && …)` →
  silently skipped the verification); `!cap.amountValue || mismatch` → 402.
- **Website rate-limit IP** (`api/_lib/rate.ts` `clientIp`): trust only the
  edge-set `x-vercel-forwarded-for` / `x-real-ip`, else the RIGHTMOST XFF hop —
  the leftmost `x-forwarded-for` was client-spoofable to dodge every bucket.

Both shipped: launcher v1.1.0 re-release (BUILD_ID 20260613233048) +
`vercel --prod` website deploy. Remaining lower items (loopback OAuth port,
zip-bomb size cap, admin-upload content-type, public-insert global cap) are
documented in the report for later.

### Build E (2026-05-23, BUILD_ID 20260523200531)

Two root-cause fixes shipped after a deep audit triggered by an
"install stuck at 0%" + "personal area empty" report:

- **`get_purchases` SQL** — the query asked for `user_purchases.created_at`,
  which does not exist (real columns are `purchased_at` + `completed_at`).
  Every personal-area call returned HTTP 400 `42703` so the UI silently
  rendered "0 purchases". Fixed in `translation_manager/auth/manager.py`
  via a PostgREST column alias `created_at:purchased_at` so the JS
  shape stays identical to `MyPurchase.created_at`.
- **`certifi` missing from the bundle on disk** — `TranslationManager.spec`
  now lists `requests/urllib3/idna/charset_normalizer/certifi` in
  `hiddenimports` AND adds `datas += collect_data_files('certifi')`
  so `_internal/certifi/cacert.pem` is always present. The user's
  Build D install was wrecked by **IObit Uninstaller** — it selectively
  deleted files (including `cacert.pem`) and renamed others with an
  `_IObitDel.<ext>` suffix while the launcher was running; the launcher
  then booted (Python stayed in PYZ) but every HTTPS call died with
  `OSError: Could not find a suitable TLS CA certificate bundle`. The
  explicit spec entry makes the data file impossible to miss — but the
  user-facing rule is **uninstall via Windows Settings → Apps, not via
  IObit/third-party uninstallers**, which is the only thing that
  reliably keeps a half-deleted install off disk.

---

## Frontend build flags

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with HMR on `localhost:5173`. |
| `npm run build` | Type-checks + emits production bundle to `frontend/dist/`. |
| `npm run preview` | Serves the built bundle to validate before bundling. |

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

## In-game language switcher (2026-06-09)

A per-game **3-way text-language switch** in the launcher's `GameDetailPanel`
sidebar (shown only for supported titles): **אוטומטי / עברית / אנגלית** + a
**"שחזר לשפה שלפני המוד"** link. Flips the game's *own* text-language setting
so the user picks Hebrew (the Arabic locale slot) or English without editing
the registry / a settings file by hand.

- **`translation_manager/game_language.py`** (NEW) — generic, config-driven.
  `LANG_CONFIGS` declares each game's mechanism:
  - `kind="registry"` — a HKCU DWORD. **spiderman2**: `HKCU\Software\Insomniac
    Games\Marvel's Spider-Man 2` → `TextLanguage` (0=English, 18=Arabic), plus
    `englishVO=1` pinned on every write (keep English voice).
  - `kind="cp2077"` — delegates to `cp2077_language.py` (UserSettings.json
    Text+Subtitles; en-us / ar-ar), reusing its robust schema walker.
  - Modes: `auto` (installed→Hebrew, else original/English), `hebrew`,
    `english`. The **pre-mod language is captured on the FIRST write** and
    persisted to `~/.translation_manager/game_langs.json` so
    `restore_original()` is always exact. Never raises; winreg is
    lazy-imported + `sys.platform`-guarded.
- **`cp2077_language.py`** — added `current_text_language()` +
  `set_text_language(locale)` (the 3-way needs an explicit "force English" and
  a live-state read; `enable_arabic_slot`/`restore_language` remain the
  auto-flip pair the mod lifecycle drives — left untouched).
- **RPCs** (`main_eel.py`, additive — CP2077 mod-lifecycle hooks unchanged):
  `get_game_language` / `set_game_language(mode)` / `restore_game_language`.
  `_lang_mod_installed(game_id)` resolves `auto`: launcher-tracked mods
  (CP2077) → real install state; games with no launcher-managed mod
  (spiderman2 via Overstrike) → `None`, which `auto` reads as Hebrew.
- Bridge slots in `qt_shell/bridge.py`; `eel.ts` `GameLanguageState` type +
  `getGameLanguage`/`setGameLanguage`/`restoreGameLanguage`.
- Verified on a throwaway HKCU key: hebrew→18, english→0, auto resolves off
  install state, restore returns the captured pre-mod value, englishVO pinned.
  **Reaches installed users only after a launcher rebuild + re-release.**

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

## Unified version-management system (2026-06-14)

SemVer + pre-release stages (alpha → beta → rc → stable) across the WHOLE
platform (both mods + the launcher), one publish flow, one admin dashboard.

- **Canonical comparator — keep 4 surfaces in lockstep:**
  `website/src/lib/version.ts`, `frontend/src/lib/version.ts`,
  `main_eel.py:_parse_version`, `universal/versioning.py`. Tuple key
  `(scheme, major, minor, patch, stage_rank, pre)` — `scheme` 0=legacy date
  (`2026.05.22`, below all semver)/1=semver; `stage_rank`
  alpha0/beta1/rc2/stable3 (a pre-release ranks below its stable). Verified
  identical Python↔JS. `formatVersion` → `vX.Y.Z[-beta.N]`; a value with NO
  digit ("—"/"-") passes through (never `v-`).
- **DB (`website/supabase/versioning_migration.sql`, applied):** `games`
  +`release_stage`+`changelog`+`locked_fields`(jsonb override locks); new
  `mod_version_history` (public timeline, one `is_current`/game); `launcher_
  releases`+`channel`. **DDL access**: `SUPABASE_DB_URL` (Session-pooler URI)
  in `website/.env` (gitignored) → `python c:/tmp/run_migration.py <sql>`.
- **Website (LIVE):** `StageBadge` on cards+detail; `VersionTimeline` via
  `GET /api/games?action=history&game=<id>`; admin **"גרסאות" tab**
  (`VersionsTab`): state+drift-heal+locks+rollback+changelog+launcher-channel.
  Admin actions on `/api/games?action=`: version-state/mod-set/rollback/
  history-set/launcher-channel/drift-heal. `MANIFEST_URLS` → drift vs Worker.
- **Launcher download page:** `/api/launcher` returns `channel`; dev/canary
  show ONLY in a login-gated "גרסאות מפתחים" area (main → "בפיתוח"), beta=
  public+label, stable=main. Current launcher (id=30 v1.1.0) = channel=dev +
  is_current → "dev-only, no public stable" (the user's intent).
- **Publish pipeline:** `universal/publish_version.py <game> <ver> --stage <s>
  [--changelog --sha --size --archive-url]` — DRY-RUN preview (transition,
  locks, pre-checks: newer/not-dup/sha/link-200) then `--apply` writes games +
  `mod_version_history` via the DB. Claude runs it on "publish X stage Y".
- **SM2 now ships via GitHub Release like CP2077** (new versions w/o a launcher
  rebuild). Release **v1.0.0-beta.1** on `nehorayc04/spiderman2-hebrew-mods`
  (FULL release so `releases/latest` resolves; manifest carries the beta tag).
  Worker slug `spiderman2-hebrew` added to `games/steam/steam_mod_worker/src/
  index.js` (**redeploy: `cd games/steam/steam_mod_worker && npx wrangler
  deploy`** — needs the user's Cloudflare token). `_run_sm2_install` downloads
  via `mod_source.fetch_and_extract(slug='spiderman2-hebrew')` → cache +
  `state.json`; **bundled `.modular` stays as offline fallback**. Re-pack
  future SM2 from the BUNDLED files. `check_spiderman2_update` RPC.
- **Launcher beta channel + auto-update (`launcher_prefs`):** `mod_beta_channel`
  + `mod_beta_overrides{game_id:bool}` + `mod_auto_update`. `_offer_update()`
  gates ALL update checks — a pre-release is offered only if opted in (per-mod
  override wins). Settings "עדכוני תרגומים" toggles. RPCs get/set_update_prefs
  + set_mod_beta_override (+ bridge + eel.ts).
- **ALL launcher code is compile-verified (py_compile + tsc); ships in the NEXT
  rebuild** (`build_exe.bat` — user runs). Until then SM2 applies from bundle.
- **Follow-ups:** silent auto-update stores the pref only (no auto-apply
  wiring — currently notify); channel-label display + per-mod beta-override UI
  in GameDetailPanel not yet added. Two user commands: Worker redeploy +
  launcher rebuild.

### Launcher version reset to clean SemVer + channel (2026-06-14)

The launcher version was reset from `1.1.0` to a clean **`1.0.0`** carrying the
maturity in a SEPARATE `channel` column (`dev`), the way Chrome / VS Code do it
— the stored SemVer is pure, and the **display joins them → `v1.0.0-dev`**.
Rationale: the old `v1.1.0` read like a shipped stable when there is no public
stable, and stale end-user release notes ("פתח בתוכנה") showed under a
non-existent stable version. Do NOT bake the channel into `LAUNCHER_VERSION` —
the version comparator treats that string as pure semver.

- **Version touchpoints all → `1.0.0`:** `main_eel.py:LAUNCHER_VERSION`,
  `installer.iss #define AppVersion`, `translation_manager/__init__.py
  __version__`, `frontend/package.json` (+ lock), `frontend/src/App.tsx
  APP_VERSION` (`v1.0.0`). `LAUNCHER_CHANNEL` stays `"dev"`. The installer
  asset filename is channel-free (`TranslationManager-Setup-1.0.0.exe`).
- **Display joins version+channel** (NOT stored joined). `website/src/pages/
  DownloadsPage.tsx`: `channelSuffix = channel && channel!=='stable' ?
  '-'+channel : ''` → `dispVersion = v{version}{suffix}` used in the hero label,
  main button, bottom CTA, and the dev-builds section (`v1.0.0-dev`). The
  launcher's own Settings already shows `{version}` + a channel chip.
- **RELEASE NOTES gated off for dev** — the main-column notes block now renders
  only when `!isDevChannel` (a dev build has no public "current version"); any
  notes move into the gated developer-builds section instead.
- **`publish_release.py` is channel-aware:** `publish_release.py <ver> [channel]`
  (default `stable`). Non-stable → GitHub `prerelease=True` and tag
  `v<ver>-<channel>` (so a future stable `v<ver>` never collides); the inserted
  `launcher_releases` row now carries `channel`. Default `notes=""` (the stale
  hardcoded feature text was removed).
- **Self-update safe across the "downgrade":** installed `1.1.0` dev users still
  get offered `1.0.0-dev` because `get_launcher_update_info` OR's a build-id
  mismatch with `_version_is_newer` (new BUILD_ID ⇒ `build_differs=True`), so the
  numeric downgrade doesn't suppress the update.
- **Shipped (2026-06-14):** website `vercel --prod` (LIVE on
  hebrew-translation-hub.com) + launcher rebuilt (BUILD_ID `20260614054514`) →
  ISCC → `publish_release.py 1.0.0 dev` → GitHub release `v1.0.0-dev`
  (prerelease) + Supabase row id=32. Verified `/api/launcher` → version `1.0.0`,
  channel `dev`, buildId `20260614054514` (== baked, no divergence), notes empty,
  sha256 `b32b6185…`.

### Opus QA run + CP2077 v1.0.0-beta.3 published (2026-06-15)

Autonomous multi-agent **Opus 4.8** LQA review of the CP2077 Hebrew translation
(workflow: 20 review agents + 20 independent adversarial-verify agents per
600-line batch, ~3.5M tokens/batch). **9,280 onscreens_final lines reviewed,
1,275 fixes applied + deployed** (mistranslations, broken Hebrew+Latin translits,
foreign-script leaks — German `Schnürsenkel`, Vietnamese `mũi`, Polish — grammar,
gibberish). Report: `games/cyberpunk2077/OPUS_QA_REVIEW_REPORT_2026-06-15.md`.
Reusable loop tooling under `games/cyberpunk2077/qa_review_*.py` +
`c:\tmp\opus_qa_workflow.js`; state in `universal/opus_qa_checkpoint.json` (9,280)
+ `opus_qa_fixes.applied.jsonl` (1,275). 5h session limits hit ~5× and cleared on
retry; **short-save** (`qa_review_commit_completed.py` commits only completed
chunks) meant 0 lines lost.

**HOW TO RESUME the Opus QA loop (from checkpoint 9,280; needs Ultracode/Workflow).**
One cycle = 600 lines, ~3.5M tokens. Repeat back-to-back until the goal/limit:
```
# 1. prep (clears stale fixes_). EN source = $TEMP/en_onscreens_full/text/*.json.json
#    (re-extract via WolvenKit `extract lang_en_text.archive -w "*onscreens*"` +
#     `convert serialize` into that dir if it's missing after a temp wipe).
python games/cyberpunk2077/qa_review_extract.py 600 /tmp/opus_qa_batch.json
python games/cyberpunk2077/qa_review_chunk.py   /tmp/opus_qa_batch.json /tmp/opus_qa_chunks 30
# 2. review + adversarial verify (20 review agents -> 20 independent verify agents):
Workflow({scriptPath: "c:\\tmp\\opus_qa_workflow.js"})   # N=20 + chunkDir hardcoded in the script
# 3. on completion: merge, SHORT-SAVE commit (only completed chunks), apply, bake+deploy:
python games/cyberpunk2077/qa_review_finish.py           C:\Users\Nehoray_Cohen\AppData\Local\Temp\opus_qa_chunks /tmp/opus_qa_batch.json
python games/cyberpunk2077/qa_review_commit_completed.py C:\Users\Nehoray_Cohen\AppData\Local\Temp\opus_qa_chunks
python games/cyberpunk2077/qa_review_apply.py            # QA-lock+backup+atomic, mirrors onscreens.json, prunes to 3 backups
python games/cyberpunk2077/rebuild_onscreens_and_pack.py # ~76s, game must be CLOSED
```
Key invariants: the chunk dir MUST be the absolute `…AppData\Local\Temp\opus_qa_chunks`
(agents Read it; MSYS rewrites `/tmp` only for argv, not inside scripts). Reviewers
return `{pk,sec,new,reason}` — NOT `old`; `qa_review_finish.py` reconstructs `old`
byte-exact from the batch (preserves the leading control byte), and
`qa_review_apply.py` is a no-op for any fix whose `old` ≠ current spine value and
rejects a `new` that fails `mk.parse_slots` — so the loop is safe to re-run. On a 5h
session-limit the workflow returns `keptTotal 0` + session-limit failures: just retry
it; it succeeds once the limit actually resets (an immediate retry that fast-fails in
~22 s = still active → retry every ~10-15 min; do NOT precompute the reset time).
After onscreens_final (~70k) finish, sweep onscreens.json, then quest subtitles (EN
source there = the entry's `secondaryKey`, a different extract). Full context +
recurring-fix glossary (headband=סרט ראש, bandana=בנדנה, steel-toes=נעלי בטיחות,
Shard=שארד, Cyberware=סייברוור, melee=קרב מגע, V stays Latin in prose but a bare
speaker-name entry "וי" must stay): memory [[opus-weekly-qa-run]].

**Published `1.0.0-beta.3`** with all 1,275 fixes — same proven pattern as beta.2
(keep the GitHub `v1.0.2` release as `releases/latest`, **clobber its assets**;
do NOT mint a `v1.0.0-beta.3` tag — semver-wise `1.0.2 > 1.0.0-beta.3` so GitHub
would keep v1.0.2 as latest and the Worker would serve stale): `pack_cp2077_mod.py
1.0.0-beta.3 --pack-only` → `gh release upload v1.0.2 --clobber manifest.json
cyberpunk_hebrew_translation.zip` (92.3 MB, sha
`8f49e121238b759395e0ab8499b09a3de76dfe14ea2c66bfb34a3d5895f8d8bf`). Worker
`/cp2077-hebrew/manifest` now serves `1.0.0-beta.3`. Website synced via
`publish_version.py cyberpunk 1.0.0-beta.3 --stage beta --sha … --size … --archive-url
…/v1.0.2/…zip --apply` (games row + `mod_version_history`; `games.download_url`
already points at the v1.0.2 zip, now updated content — left as-is). 3 Claude news
suggestions dropped for admin approval ([[claude-news-suggestions]]).

### Badge dedup + CP2077→beta + admin history edit/delete (2026-06-14)

Follow-up polish for cross-surface version consistency (website ↔ launcher).

- **One beta badge, not two.** The website's `GameDetailModal` rendered BOTH the
  brown version-driven `StageBadge` (from `release_stage`/version) AND the
  theme-colored `StatusBadge` (from `games.status`) → two "בטא" pills in two
  colors. Removed `StatusBadge` from the modal (kept the brown `StageBadge`,
  which auto-resolves for every game). The launcher already showed only
  `StageBadge`, so both surfaces are now consistent: a single brown maturity
  pill, version-driven.
- **CP2077 relabeled `1.0.2` → `1.0.0-beta.2`** (a version-SCHEME change, same
  content — presents CP2077 as a beta like SM2). Updated in THREE places so the
  launcher (reads `games` via `_shape_supabase_game`) and the website show the
  same thing AND the admin drift check stays clean: (1) Supabase `games.version`
  + `release_stage=beta`; (2) the `mod_version_history` current row; (3) the
  GitHub release `v1.0.2` **manifest.json** `version` field (the only asset
  re-uploaded — same 92 MB zip + sha256, so installed users are unaffected). The
  Worker serves `/cp2077-hebrew/manifest` → `1.0.0-beta.2`. `games.download_url`
  still points at the `v1.0.2` release asset (content identical) — left as-is.
- **Admin VersionsTab — history is now editable + deletable.** New API actions on
  `/api/games`: `history-delete {gameId,version}` (refuses the is_current row so
  the games row is never orphaned) and an EXTENDED `history-set` that now edits a
  row's `newVersion` + `stage` + `changelog` (not just changelog), mirroring onto
  the games row when editing the current version (respects per-field locks). UI:
  a `HistoryRow` component per timeline entry with an inline editor (version /
  stage / changelog) + ערוך / חזור לכאן / מחק; the history `<details>` now shows
  at `>= 1` rows (was `> 1`).
- **Removed the lonely `·` dot** in the game detail modal — the `· {versionLabel}`
  span rendered a bare middot when `version_label` is empty (all games). Now
  rendered only when `versionLabel` is non-empty.
- **Fixed reversed parens** in the launcher beta toggle (`GameDetailPanel`
  `ModBetaToggle`): `)מההגדרות(` → `(מההגדרות)` (logical parens, matching every
  other Hebrew parenthetical in the app — the reversed literal showed backwards).
- **Shipped:** website `vercel --prod` (LIVE) + launcher rebuilt (BUILD_ID
  `20260614071049`) → ISCC → `publish_release.py 1.0.0 dev` → GitHub `v1.0.0-dev`
  + Supabase row id=33. Verified `/api/launcher` buildId == baked. Note: the
  badge/dot fixes reach a browser on next load (new hashed chunks); the parens
  fix reaches installed launchers via the dev self-update.

### Claude news-suggestions category + stronger stage badge (2026-06-14)

- **Claude writes news suggestions on every change.** The admin "הצעות AI" tab
  (`NewsDraftsTab.tsx`) now filters drafts by `source` into **Claude** /
  **Gemini** / **all** (default Claude). `news_drafts.source` already existed
  (Gemini = `'ai'`); Claude items use `source='claude'`. New helper
  **`universal/claude_suggest.py`** inserts them (reads `website/.env` service
  key → POST `news_drafts`, `source='claude'`, accepts `--json <file>` / stdin
  JSON array / single `--title`). Approve/reject is the existing flow (approve →
  promoted to the public `news` feed). STANDING RULE (memory
  [[claude-news-suggestions]]): after ANY site/launcher change, also drop 2-4
  user-facing Hebrew suggestions describing the current state — the user decides
  what publishes. Nothing auto-publishes. Seeded 4 on 2026-06-14.
- **STANDING RULE — periodic news suggestions (user request 2026-06-16).** Beyond
  the per-change rule above, **every so often** when there IS something worth
  announcing (a shipped mod/launcher version, a new game added, a notable fix,
  a milestone), proactively push 2-4 Hebrew `news_drafts` via
  `universal/claude_suggest.py` (`source='claude'`) for the admin to approve —
  do NOT wait to be asked. If there's nothing new/interesting, skip (don't
  manufacture filler). The user reviews + decides what publishes; nothing
  auto-publishes.
- **Stronger stage badge.** `STAGE_BADGE` (BOTH `website/src/lib/version.ts` +
  `frontend/src/lib/version.ts`, kept in lockstep) fill `0.14 → 0.30`, border
  `0.5 → 0.8`, brighter fg — the brown beta pill (and alpha/rc) is now far less
  transparent on cards / modal / launcher panel. Reaches the launcher via the
  rebuild below.

### Version state + cross-surface sync — continuation reference (2026-06-15)

**Current snapshot.** CP2077 mod **`1.0.0-beta.3`** (beta, sha `8f49e121…`,
92,324,322 B) · SM2 mod **`1.0.0-beta.1`** (beta) · launcher **`1.0.0` channel
`dev`** (BUILD_ID `20260614175504`, GitHub release `v1.0.0-dev`, Supabase
`launcher_releases` id=34, is_current). All verified consistent 2026-06-15.

**A mod version lives in 4 surfaces that MUST agree.** Website + launcher both
*display* the Supabase `games` row; the launcher's install/update reads the
Worker manifest:
1. **Supabase `games`** — `version` + `release_stage` → website + launcher
   card/panel (launcher via `main_eel._shape_supabase_game`).
2. **Supabase `mod_version_history`** — one `is_current` row → public timeline +
   admin VersionsTab.
3. **GitHub release `manifest.json` asset** → what the Worker `/<slug>/manifest`
   serves → the launcher's install + update-check source of truth.
4. **GitHub release zip asset** (`/<slug>/archive`) — the bytes; `manifest.sha256`
   must equal it.

**CP2077 publish keeps `releases/latest` stable:** the tag stays **`v1.0.2`** (a
FULL release); each build CLOBBERS its assets (`gh release upload v1.0.2
--clobber manifest.json cyberpunk_hebrew_translation.zip`) — NEVER mint a
`v1.0.0-beta.N` tag (semver `1.0.2 > 1.0.0-beta.N`, so GitHub would keep v1.0.2
as latest and the Worker would serve stale). So `games.download_url` correctly
stays `…/v1.0.2/…zip` even when the manifest version is a beta. Sync the website
with `universal/publish_version.py cyberpunk <ver> --stage beta --sha … --size …
--archive-url …/v1.0.2/…zip --apply` (writes `games` + `mod_version_history`),
and edit the release's `manifest.json` `version` field (a tiny asset — not the
92 MB zip; the Worker reads it). For a pure RELABEL with no content change, also
fine to PATCH `games` + `mod_version_history` directly (PostgREST, service key in
`website/.env`) and re-upload only `manifest.json`.

**Consistency check (run on any "is everything OK?" / after a publish):** assert
version + sha256 + stage all equal across the Worker `/cp2077-hebrew/manifest`,
`games?id=eq.cyberpunk`, the `mod_version_history` is_current row, and that the
Worker `/archive` + `games.download_url` both HEAD 200 with the same byte size —
and that `games.version == manifest.version` (no drift). The admin VersionsTab
also surfaces drift with a one-click heal.

**The 2 user-run commands that DON'T self-propagate** (everything else is live
via DB/Worker): a launcher **rebuild** (`build_exe.bat` → ISCC →
`publish_release.py 1.0.0 dev`) to ship launcher-frontend/Python changes to
installed apps; and a **Worker redeploy** (`cd games/steam/steam_mod_worker &&
npx wrangler deploy`, needs the user's Cloudflare token) only when the Worker
`src/index.js` itself changes (e.g. a new mod slug). Website code changes go live
via `vercel --prod` (run from `website/`).

## Community translation system — crowdsourced EN→He lines (STAGE 3 LIVE 2026-06-18)

A platform feature so users don't translate every game alone: the team builds the
per-game **skeleton** (Arabic-slot RTL + font + repack + deploy — the existing
`games/<game>/FEASIBILITY.md`/`PIPELINE.md`), and the only remaining heavy work —
translating the lines — is **crowdsourced**. Logged-in users claim a batch, translate
EN→He, submit back; an **auto structural-QA gate** rejects bad ones; the admin (user)
reviews + approves; approved Hebrew exports back into the existing apply/bake/deploy
keyed by the exact spine key. Works for BOTH untranslated games (fresh) AND
already-translated games (`current_he` set → contributors propose IMPROVEMENTS).

**User decisions (2026-06-18):** input model = **both** (in-site editor primary +
file download/upload for power users); approval = **admin approves everything** for
the MVP (trust-levels later); scope = **all games**, including already-translated.

**Stage 1 — DB schema (DONE + LIVE + verified).**
`website/supabase/community_translation_migration.sql` (applied via
`python c:/tmp/run_ct_migration.py`, the SUPABASE_DB_URL psycopg2 method). Two tables +
2 views, RLS like `reviews`/`votes`:
- `translation_strings` — source-of-truth lines per game: `game_id`(FK), `string_key`
  (EXACT spine pk/stringId — export maps back on it), `source_en`, `current_he`
  (''=untranslated, non-empty=improve mode), `context`, `char_limit`, `section`,
  `order_index`, `status`(open/translated/approved), soft claim (`claimed_by`,
  `claim_expires_at`), `approved_text`. unique(game_id,string_key). **Public read**;
  writes service-role only.
- `translation_submissions` — `string_id`(FK), `game_id`, `user_id`, `hebrew_text`,
  `author_name`(denormalized like reviews), `status`(pending/approved/rejected/
  superseded), `reviewer_note`, `auto_qa`(jsonb), review fields. unique(string_id,
  user_id) — a user revises via upsert, others add their own. **Self-read only**;
  writes service-role only.
- Views: `translation_progress` (per-game counts) + `translation_contributors`
  (leaderboard, aggregate only — author_name not email). **Grant the views to
  service_role too** (RLS bypass ≠ view grant — first apply missed it → 403; fixed).
- Claims are a SOFT lock; expired claims are treated as free LAZILY by the API (no cron).

**Stage 2 — pipeline bridge (DONE + round-trip verified).**
`universal/community_translate.py` (urllib only, reads `website/.env` service key) —
game-agnostic. Contract = a NORMALIZED strings file (JSON array of
`{string_key, source_en, current_he?, context?, section?, char_limit?, order_index?}`);
each game makes it with a tiny adapter over its existing extractor. Commands:
`import <game_id> <strings.json>` (bulk upsert on game_id+string_key, chunks of 500,
merge-duplicates so a re-extract refreshes the pool without losing claims/approvals),
`export <game_id> [--out]` (approved rows → `{string_key: approved_text}` JSON for the
apply script), `stats <game_id>`. Verified: import 2 → stats (total/had_existing/
untranslated_open correct) → export → cleanup, all good.

**Stage 3 — web layer (LIVE 2026-06-18).** Deployed `vercel --prod` (dpl_FV2oBxbb…).
- `website/api/translate.ts` — full endpoint: GET list/stats/download/admin-queue/my-submissions, POST submit+upload (auto-QA gate inline), PATCH approve/reject/edit. Rate-limited (60 submissions/min/user). Service-role bypasses RLS; admin actions via `requireAdmin`.
- `website/src/pages/TranslatePage.tsx` — public `/translate` route (login-gated), game selector, batch-size 10/25/50, row-by-row table (EN | HE textarea | actions, RTL via `dir="rtl"`), status colors, inline QA errors, file download (fetch+blob) + upload (CSV/JSON parser).
- `website/src/components/admin/TranslationsTab.tsx` — admin review queue under "תרגומים" tab in AdminLayout "אתר" group: game+status filter, per-card approve/edit/reject with inline edit+note.
- `website/src/pages/ProfilePage.tsx` — "התרגומים שלי" tab added (🌐 icon): loads `/api/translate?action=my-submissions`, shows status-colored rows (pending/approved/rejected).
- `website/src/components/Navbar.tsx` — "תרגמו איתנו" link added after "משחקים".
- `website/src/App.tsx` — lazy `/translate` route behind ProtectedRoute.
- `api/software.ts` DELETED (dormant, was the 12th→13th function on Hobby plan); ProgressTab made resilient to 404.
- **Auto-QA gate** (server-side, shares Playbook §7 name/code rule): niqqud, foreign script, placeholder multisets [UPPER]/{VALUE}, not-identical-to-source, must-have-Hebrew (unless name/code).
- **Next**: per-game adapter to import strings (`universal/community_translate.py import <game> <strings.json>`), then contributors can start. Start with WD2 or GoWR EN source.
- 4 news suggestions pushed to admin queue (`universal/claude_suggest.py`).

The auto-QA gate MUST reuse the translator's name/code passthrough rule (Playbook §7) —
accept no-Hebrew when the source is a name/code — or it churns on proper nouns.

### Stage 3 UX polish (2026-06-18) — covers, background, hidden reference, token-free editing

Four fixes to `TranslatePage.tsx` after the user reviewed the live page (all
deployed `vercel --prod`, aliased to hebrew-translation-hub.com):
- **Game-card covers were empty boxes.** `/api/games` shapes the cover field as
  **`cover`** (see `api/games.ts` `shape()` → `cover: row.cover_url`), but the
  page read `g.coverUrl || g.cover_url` (neither exists). Fixed → `resolveCoverUrl(g.cover, g.id)`
  (the canonical `src/lib/coverUrl.ts` helper: absolute / public / bucket / `<id>.jpg`
  fallback). The 4 games hold full `…/covers/<id>.webp` URLs.
- **Site starfield/video background was blocked** by a `bg-zinc-950/80` blanket on
  the content wrapper → removed it (cards keep their own translucent bg, so the
  background shows through the gaps). Hero is `bg-black/60 backdrop-blur-sm`.
- **`current_he` hidden from contributors** (admin-only reference): stripped from
  the `/api/translate` GET list response (`safeStrings` omit) AND not rendered in
  `StringCard`. Still in the DB + admin-queue join + download endpoint.
- **Contributors translate token-FREE.** Measured the real string pool (4,000
  sampled): **~84% clean** (no tokens), ~7% boundary-only, ~9% inline
  (cyberpunk 99.9% clean; SM2 the outlier at 59.5% clean / 19.5% inline `%d`).
  So `TranslatePage` now decomposes each `source_en` via `analyzeSource()` into
  **prefix / core / suffix + inlineTokens** (PRESERVE_RE = tags, `&ent;`,
  `[[cue]]`, `[TOKEN]`/`[LF]`/`[style]`, `{val}`, `%d`-specs, `\n\t`):
  - **Boundary tokens** (start/end + adjacent ws) are PEELED off — the editor
    shows only the clean `core`; on submit `reconstructFull` re-attaches
    `prefix+editable+suffix` (the FULL structured string is what's stored/exported
    keyed by `string_key`). A saved submission is peeled back via `stripToEditable`
    on reload. Round-trip + `prefix+core+suffix===src` verified 0-fail over all 4,000.
  - **Inline tokens** can't be auto-placed (Hebrew reorders) → shown as amber
    chips in the source + a **one-click "+ %d" palette** under the textarea that
    inserts the exact token at the caret (contributor never types the code); a
    multiset `missingInline` check colors un-placed chips amber.
  - The standalone explanatory legend banner was removed (noise for the 84% clean).
  This mirrors Playbook §3/§7 token rules on the contributor side — the server
  auto-QA still validates placeholder multisets, so a missing inline token is
  rejected regardless.

### Stage 3 — clean fragments + repair guard-dogs (2026-06-18)

User feedback: a row showed a stray leading `". Be"`, and the request was to
NEVER tell a contributor "what you wrote is an error" — instead repair it.

- **Clean-fragment display.** Game dialogue is split into fragments, so a
  `source_en` can start with `". "` / `"... "` / a space after a `<ts>` timing
  tag. `analyzeSource()` now also peels leading/trailing **whitespace** and a
  leading **fragment marker** (`/^(?:[.,;…]+\s+|[.…]{2,})/`) into prefix/suffix
  (re-attached on submit). Dropped "dirty cores" 63→11 over 4,000 (the rest are
  `!OBSOLETE` dev-codes + `'Scuse`-style word-attached apostrophes, correctly
  left). `prefix+core+suffix===src` and the strip/reconstruct round-trip stay
  0-fail.
- **TWO repair guard-dogs replace hard rejection** (the user's "כלבי שמירה"):
  - **Guard dog #1 — server, deterministic (`api/translate.ts`).** Submit/upload
    no longer 422-reject on QA failure. `cleanHe()` strips niqqud + zero-width
    (NOT trimmed — boundary prefix/suffix must survive); the row is ACCEPTED as
    `pending` with `auto_qa = {ok, flags, needs_repair, niqqud_fixed, repaired}`.
    The ONLY hard stop is a truly-empty cell. Submit returns `needsRepair` →
    the UI shows a sky-blue "נשלח! נסדר את הניסוח והמבנה אוטומטית" note (not a red
    error). Upload reports `accepted`/`flagged`/`skipped` (no `rejected`).
  - **Guard dog #2 — local LM watchdog (`universal/community_qa_watchdog.py`,
    NEW).** Pulls `status=pending & auto_qa->>needs_repair=true` submissions
    (joins `translation_strings(source_en)`), rewrites each via LM Studio
    (gemma-4, env `CT_QA_MODEL`/`CT_QA_LM_URL`) into a valid structured Hebrew
    line, **deterministically re-validates** (`validate()` MIRRORS the server
    autoQa — niqqud/foreign/placeholder-multiset/has-Hebrew-or-name, unit-tested
    9/9), then PATCHes `hebrew_text` + `auto_qa{repaired:true,needs_repair:false}`
    back as `pending` for admin approval. Strike/park at 3 fails
    (`repair_strikes` → `unrepairable`). Trio discipline: UTF-8 stdout, singleton
    lock, crash-proof loop, `--once`/`--status`/`--game`/`--limit`. **It is LOW
    priority on the SHARED LM** — if the model is unresponsive it WAITS (does NOT
    reload, which would disrupt a running SM2/WD2 translator) unless `--manage-lm`.
  - `auto_qa` jsonb shape extended (no migration — jsonb). Admin still approves
    everything; the guard-dogs just make sure what reaches the admin is clean.
  Run it (when contributions exist + LM loaded): `python
  universal/community_qa_watchdog.py` (loop) or `--once`. `--status` = flagged count.

### Stage 3 — collaborative + versioned (public attribution + history) (2026-06-18)

The contributor flow became a transparent wiki-style model (user decision via
AskUserQuestion: **edits are admin-gated**, NOT auto-publish). All `vercel --prod`.

- **Translations are PUBLIC + attributed (reverses the 2026-06-18 "hide current_he").**
  The GET list now returns, per string: `currentText` (`approved_text` > `current_he`
  seed > ''), `currentAuthor` ({name, avatar} of the approved submission's author —
  **never email**), `hasHistory`, `status`. `current_he` is no longer stripped.
- **`StringCard` has VIEW / EDIT / HISTORY states.** A string with a live translation
  opens read-only (current text + `Avatar`+name + "✏ שנה" + "🕘 היסטוריה"); "שנה"
  pre-fills the editor via `stripToEditable(currentText)` → submit = a pending
  PROPOSAL (admin approves → new current, old → history). Untranslated rows open
  straight into the editor. Button flips to "↑ שלח הצעת שינוי" when a current exists.
- **Public per-string history** — `GET /api/translate?action=history&string=<id>` →
  `{sourceEn, seedHe, versions[]}`; each version = {hebrewText, status, author
  {name,avatar}, createdAt, reviewedBy, note}. Lazy on expand; shows the team seed
  (`seedHe`) as the "before" baseline. Uses `fetchAuthors()` (service-role read of
  `profiles` for name+avatar, bypassing self-read RLS; email only derives a fallback
  handle, never returned).
- **Show-everything filter** — list no longer excludes approved. New `filter` param:
  `all` (default) / `open` (`current_he=''` AND not approved = genuinely untranslated)
  / `translated` (`or(current_he.neq.,status.eq.approved)` = has a seed OR approved).
  3-way toggle (`הכל/לתרגום/מתורגמות`) reloads on click. NOTE: seeded strings keep
  `status='open'` (approval is a community state), so "translated" keys off `current_he`
  non-empty, NOT `status=approved`. (cyberpunk: 44,482 translated / 148 open.)
- **Privacy (stated to user):** name + avatar are public; **email is NOT** exposed
  publicly — admin-only via the admin-queue. Avatars from `profiles.avatar_url`
  (Google `picture`); `Avatar` falls back to an initial bubble.
- No DB migration (the `translation_submissions` chain — approved→superseded as new
  ones land — IS the history; `profiles` already has `avatar_url`). Admin approve/
  edit/reject (PATCH) unchanged — the gate that promotes a proposal to current.

### WD2 community pool — corrupt source_en re-aligned to game truth (2026-06-18)

A contributor flagged a `/translate` WD2 card showing "Take" → "זום". Root cause was
NOT the translation: `games/watchdogs2/work/build_ct_strings.py` joined `source_en`
from `extract/ui_strings_english.txt` (a **misaligned/garbled** English extraction)
while `current_he` came from the checkpoint `C:/tmp/wd2_ui_he.json` (keyed by the
game's real oasis ids). The two English id-mappings disagreed — **21,601 of 29,521
WD2 rows (73%) had wrong/scrambled `source_en`** (e.g. id 4567 = "Take" in the bad
file but "ZOOM" in the game; weapon descriptions were word-salad). The game's own
`main_english.loc` (decode: `tools/loctool/loctool.exe <loc>` → `.loc.txt`) is the
authoritative English and agreed with the Hebrew per id.
- **Fix:** bulk-upserted (`on_conflict=game_id,string_key`, merge-duplicates → only
  `source_en` written, `current_he`/status untouched) every WD2 row's `source_en` to
  `main_english.loc[id]`. Verified **0 mismatches** across all 29,521 rows; the flagged
  card now reads "ZOOM" = זום, the real "Take" ids (293453/316477) = "קח". No website
  deploy needed (reads the DB live).
- Also **rewrote `extract/ui_strings_english.txt` clean** from `main_english.loc` so a
  future `build_ct_strings.py` + re-import reproduces correct data.
- **LESSON (memory [[community-translation-model]]):** when seeding a community pool,
  `source_en` and `current_he` MUST come from the SAME id-mapping (the game's
  authoritative loc), never two independent extractions — or every row is silently
  mis-paired. Extract char note: decode in Node (`Buffer.toString`) or Python with the
  RIGHT encoding; a wrong `errors="replace"` turned `–`/`•` into `�` on 2 rows (fixed).

## Per-game mod updates (2026-06-09)

The launcher now detects when an INSTALLED translation mod has a newer version
on the server and offers a one-click update — in the game's own panel AND on
the Downloads/Updates screen.

- **Backend** (`main_eel.py`, additive): `check_game_mod_update(game_id)` (a
  single game) and `get_mod_updates()` (all installed download-distributed
  mods). Both fetch ONLY the manifest via `mod_source.fetch_manifest(slug)`
  (no archive) and compare with `_version_is_newer` against the installed
  `state.json` version. Kept OUT of `get_game_mod_state` (which stays instant);
  the Qt bridge runs both through `_run_off_thread` so the network call never
  freezes the UI.
- **GameDetailPanel**: a network update-check runs when a download mod is
  installed; an **"⬆ עדכן תרגום → <ver>"** button (accent) appears in the
  installed action row when `updateAvailable`, plus an "⬆ עדכון זמין" header
  chip. The update reuses `downloadAndInstallGameMod` — `download_and_cache`
  wipes the cache first, so it pulls the fresh version.
- **DownloadsView**: a new **"עדכוני תרגום למשחקים"** section (green) lists each
  installed mod with `vInstalled → vLatest` + an "עדכן" button (per-row progress
  via the shared `mod_install_progress` channel). It replaces the
  "אין עדכונים זמינים כרגע" empty state when mod updates exist.
- `eel.ts`: `GameModUpdate` + `ModUpdate` types, `checkGameModUpdate` /
  `getModUpdates`. Dormant until an installed mod's server version is newer.

## Spider-Man 2 through the launcher — BLOCKED on Overstrike (2026-06-09)

Investigated wiring SM2 into the launcher like CP2077. **Not feasible as a
drop-in:** the SM2 Hebrew mod ships as two `.modular` files
(`hebrew_full.modular` ~2.5 MB + `hebrew_font_v7.modular` ~716 KB) that are
applied ONLY by **Overstrike** (a 3rd-party .NET GUI mod manager, no CLI) into
a separate "Mods Library" folder — NOT copied into the game folder like
CP2077's `archive/pc/mod/`. dat1lib (`games/spiderman2/tools/ALERT`) can
read/write DAT1 but has no end-user apply path. No Cloudflare Worker is deployed
for SM2 yet (the `nehorayc04/spiderman2-hebrew-mods` repo + `pack_and_release.py`
exist but no release pushed). The in-game language switch (Arabic-slot
TextLanguage DWORD) already works via `game_language.LANG_CONFIGS['spiderman2']`.
Realistic paths (pending user choice): (a) guided semi-auto — launcher
downloads + drops `.modular` into Mods Library, bundles/opens Overstrike, sets
the language, user clicks Apply once; (b) re-implement Overstrike's
toc-rewrite/DAT1 injection in Python (large, fragile to game patches); (c) keep
SM2 as a manual website download + the existing language switch.

## Launcher: WD2 install + AC Shadows detect + auth-resilience + no-silent-update (2026-06-21)

Four launcher fixes from a user report (all compile-verified — `py_compile` + `tsc -b`
+ `vite build` all clean; WD2 byte-logic round-trip-tested). **Reach installed users only
after a launcher rebuild** (`build_exe.bat` → ISCC → `publish_release.py 1.0.0 dev`).

- **Watch Dogs 2 now installs through the launcher** (was unsupported). New native
  applier `translation_manager/watchdogs2_mod.py` reproduces the proven
  `games/watchdogs2/work/wd2_archive.py` **FAT5 fat-redirect** in shipping-grade form:
  for each of 3 bundled files (`main_arabic.loc` + Hebrew font `.ffd`/`.xbt`) it appends
  the bytes to every archive's `.dat` (common/patch/patch2) and rewrites the `.fat` entry
  (stored, unc=0); fully reversible (per-`.fat` backup + `.dat` origsize, restore+truncate).
  **Backups live OUTSIDE the game** (`~/.translation_manager/mod_cache/watchdogs2/backup/`)
  + a `wd2_he_applied.json` marker = `is_applied`. Payloads BUNDLED under
  `translation_manager/assets/watchdogs2/` (ride the `('translation_manager',…)` spec
  datas entry — no spec change), `_WD2_BUNDLED_VERSION="1.0.0-beta.2"`. RPCs in main_eel
  (`get_watchdogs2_mod_state`/`install_watchdogs2_mod`/`remove_watchdogs2_mod` +
  `_run_wd2_install`), `_mod_state`/`_enrich_game_row` WD2 branches, bridge slots, eel.ts
  `WatchDogs2State`+3 calls, and a dedicated `isWd2` branch in `GameDetailPanel` (install/
  remove + progress + an in-game "Written Language = Arabic, launch with -eac_launcher"
  caveat). Activation stays in-game (Arabic slot) — the launcher never touches a game
  setting. Round-trip test (synthetic FAT5): apply redirects+appends, read-back matches,
  revert byte-identical, re-apply works. **In-game render is the user's to confirm** (the
  applier is byte-faithful to the proven dev script). NOTE: updates ship a new launcher
  build (bundled). A future Worker-download path (slug `watchdogs2-hebrew`, already in
  `index.js` but undeployed) would allow versioned updates without a rebuild.
- **Assassin's Creed Shadows is now FOUND.** The detector had no AC Shadows pattern, so the
  card (fetched live from the hub, id **`ac-shadows`**) never resolved an install path.
  Added `game_detector._PATTERNS["ac-shadows"]=["assassinscreedshadows"]` +
  `_EXE_PATTERNS["ac-shadows"]=["ACShadows.exe","ACShadows_Plus.exe"]` (key matches the
  Supabase `games.id` so `detected_cached()["ac-shadows"]` lines up) + a `games_catalog`
  entry for offline parity. Exact-match means no "…Shadows"→"Assassin's Creed" false
  positive. (No install flow — AC Shadows is still feasibility-stage; this only makes the
  launcher detect/show the installed game.)
- **"Logged out after a while" FIXED** (`auth/manager.py`). Root cause: `me()` called
  `store.clear()` on ANY `AuthError` — including a transient network blip while the access
  token was expired, OR a refresh-token race under Supabase rotation — permanently wiping
  the session. Fix: new **`AuthNetworkError(AuthError)`** for transient failures
  (network/timeout/5xx/429) raised by `_refresh`/`_fetch_user`; `me()` now **keeps the
  session + returns the cached identity** on transient errors and **only signs out on a
  definitive revoke** (401/403/invalid-refresh). Added a **`_refresh_lock`** + reload-after-
  acquire (`_refresh_locked`, used by me/owns_game/_authed_token/get_votes) so two concurrent
  refreshes can't burn a rotated token → false logout. Added an on-disk **profile cache**
  (`~/.translation_manager/user_cache.json`, seeded on login/signin/signup, cleared on
  logout) so the offline/transient fallback returns a full identity (name+avatar).
- **Silent auto-update REMOVED; replaced with notifications.** Dropped the
  `mod_auto_update` pref (`launcher_prefs`), its RPC plumbing (`get/set_update_prefs` no
  longer carry `autoUpdate`; bridge `set_update_prefs` is 1-arg), the Settings "עדכון
  אוטומטי שקט" toggle, and the App.tsx silent-install effect. Now on boot the app checks
  for available mod updates (CP2077-style + SM2) and, if any, shows **(1) an in-app toast**
  AND **(2) a native Windows notification** — new `notify_os` RPC → bridge `notify_os` Slot
  → `os_notification` Signal → `Tray.showMessage` (wired in main_qt). Nothing installs on
  its own; the user clicks "update" in the game card / Downloads screen.
- **SHIPPED 2026-06-21:** `build_exe.bat` (BUILD_ID `20260620230751`, dev_build 2) → ISCC
  → `publish_release.py 1.0.0 dev` → GitHub release `v1.0.0-dev` (prerelease, asset
  clobbered) + Supabase `launcher_releases` id=39 (is_current). Verified `/api/launcher` →
  version 1.0.0, channel dev, buildId `20260620230751` (== baked, no divergence), sha256
  `3f66cf23…`, size 247,847,353 B. WD2 assets confirmed bundled in the dist
  (`_internal/translation_manager/assets/watchdogs2/`). Installed dev launchers get the
  self-update on next check (build-id differs from the prior `20260616003325`).
  ⚠️ Note: `build_exe.bat` must be run via the PowerShell call operator (`& '.\build_exe.bat'`)
  — `cmd /c build_exe.bat` and Git-Bash `cmd //c` both fail "not recognized" on this machine
  even from the correct cwd.

## Single-session-per-account + Anno 1800 on /translate (2026-06-22)

Two shipped changes.

- **One launcher install per account (single-session).** A user can no longer be
  signed in on two machines at once — a fresh sign-in **displaces** the previous
  install, which signs itself out within ~60 s and explains why. Mechanism
  (poll-based, deliberately NO server session-revoke):
  - **DB:** `profiles` gained `active_device text` + `active_device_at timestamptz`
    (migration `profiles_active_device_single_session`). The existing
    `profiles self read/update` RLS (`auth.uid() = id`) already covers them — no
    policy change. The launcher writes via its own user bearer token.
  - **`auth/manager.py`:** a stable per-install **device-id**
    (`~/.translation_manager/device_id`, uuid4, survives sign-out/in). On every
    successful sign-in (`login`/`signin_with_password`/`signup_with_password` →
    `_register_active_session`) it PATCHes `profiles.active_device = <device_id>`.
    `me()`, AFTER a 200 from `/auth/v1/user`, calls `_device_owner_status` (GET
    `profiles.active_device`): `mine` (==ours, or **NULL→claim it** so a
    pre-feature/already-signed-in user is grandfathered) → stay; `taken` (≠ ours)
    → **definitive sign-out** + drop a one-shot marker
    (`~/.translation_manager/session_takeover.flag`); **`unknown`** (any read
    error / non-200 / no row) → KEEP the session (a transient network error must
    NEVER sign out — same posture as the AuthNetworkError fix). `logout()` clears
    the marker (a deliberate sign-out is not a takeover).
  - **Why no `/auth/v1/logout?scope=others`:** on an older GoTrue an unrecognised
    `scope` can fall back to `global` and revoke the just-created session too —
    re-introducing the exact false-logout bug. The active_device claim + the
    client poll enforce single-session safely without touching the server session
    table. (If ever wanted as defense-in-depth, first verify this project's GoTrue
    honours `others`.)
  - **RPC/UI:** `auth_consume_takeover` RPC (main_eel + bridge `@Slot(result=bool)`),
    `eel.ts authConsumeTakeover`. `useLauncherAuth` now **polls `me()` every 60 s**
    (so a displaced install disconnects on its own) and, on a signed-in→signed-out
    transition, calls `authConsumeTakeover()`; if true it dispatches a window
    `"auth-takeover"` event (App.tsx → top-center toast) + a native Windows
    notification (`api.notifyOs`). The poll only clears the ownership cache when the
    identity actually changes (cheap). Offline-unit-tested: device-id stable,
    marker one-shot, null→claim+mine, same→mine, different→taken, error/empty→unknown
    (no signout), claim PATCH url+payload. **Reaches installed users via the dev
    self-update below.**
- **Anno 1800 uploaded to the community `/translate` pool.** Imported **56,087**
  strings (all already Hebrew → improve-mode; the 2,595 skip-only data-binding/number
  records were excluded — they stay as-is) via
  `universal/community_translate.py import anno1800 <strings>` built from
  `games/anno1800/agent_handoff/{to_translate,hebrew,skip}.json`. The `anno1800`
  `games` row already existed (status `locked`, `show_on_website=true`), so no FK
  issue. Verified live: `/api/translate?action=games` → anno1800 total 56,087 /
  open 0, and anno1800 is in `/api/games`. DB-only — no site deploy needed
  (`/translate` reads the DB live).
- **SHIPPED 2026-06-22:** `build_exe.bat` (BUILD_ID `20260622173127`, dev_build 3)
  → ISCC (`...AppData\Local\Programs\Inno Setup 6\ISCC.exe` — NOT Program Files on
  this machine) → `publish_release.py 1.0.0 dev` → GitHub `v1.0.0-dev` (asset
  clobbered) + Supabase `launcher_releases` id=40 (is_current). Verified
  `/api/launcher` → version 1.0.0, channel dev, buildId `20260622173127` (== baked,
  no divergence), sha `77e6ce3c…`, size 247,859,256 B.

## Anno 1800 purchasable (₪53) + installable in the launcher (2026-06-23)

Made the Anno 1800 Hebrew mod a **paid download-mod** (₪53 / 5300 agorot) installable
through the launcher — reusing the existing generic paid-mod machinery (buy button +
`owns_game` DRM gate + install/update + website Buy) with **no new RPCs and no new
GameDetailPanel branch**. The one twist: Anno is a **loose-file mod** that deploys into
`%Documents%\Anno 1800\mods\` (NOT the game folder; the zip already nests
`zzz_hebrew_translation/` at top level).

- **The seam — `_deploy_root(game_id)` (main_eel.py).** A game whose `GameConfig` has the
  new `documents_subdir` (Anno = `r"Anno 1800\mods"`) deploys to `_documents_dir()/sub`;
  every other game returns `_install_path` **byte-identical** (CP2077 untouched).
  `_documents_dir()` resolves the real Documents known-folder (HKCU `…\Shell Folders\Personal`
  via winreg, OneDrive-safe; falls back to `~/Documents`). `_deploy_root` is threaded into the
  FILE-TARGET sites only — `_mod_state` (`detect_state`), `get_game_mod_state`/`check_game_mod_update`/
  `get_mod_updates` (`status`), `_run_game_mod_install` + `set_game_mod_installed` (`install`/`disable`,
  with a `mkdir(parents,exist_ok)` of the deploy root for documents mods), `clear_game_mod_cache`.
  The DRM gate + `base is None` "game detected" check + `hasPath` stay on `_install_path`.
- **`config.py`:** new `GameConfig.documents_subdir` field + an Anno entry (`mod_slug="anno1800-hebrew"`,
  `mod_files=[r"zzz_hebrew_translation\modinfo.json"]` = installed-detection sentinel, common_paths +
  `validation_file=r"Bin\Win64\Anno1800.exe"`). `game_mod.py` unchanged (already takes an arbitrary root).
- **Activation (auto + note).** Post-install hook `_anno1800_set_language_english()` edits
  `%Documents%\Anno 1800\config\engine.ini` (`"TextLanguage":"English"` regex, leaves AudioLanguage)
  — called from `_run_game_mod_install`/`set_game_mod_installed` for `_ANNO_ID`. `GameDetailPanel`'s
  download-mod branch shows a Hebrew note for `game.id==="anno1800"`: the user toggles the language
  once in-game for the full atlas re-bake.
- **Worker:** the slug `anno1800-hebrew` was in `index.js` but **not deployed** (404). Ran
  `npx wrangler deploy` (wrangler was already authed) → `/anno1800-hebrew/manifest` now 200
  (version 1.0.0-beta.1, sha `2fd7ee0d…`), `/archive` 200. The launcher downloads via the Worker,
  so this was a hard prerequisite.
- **Supabase `games` row** brought from `locked`/free to a live paid beta (it had drifted — the
  `mod_version_history` current row was already correct `1.0.0-beta.1`): `price_cents=5300`,
  `availability='available'`, `status='beta'`, `release_stage='beta'`, `version='1.0.0-beta.1'`,
  `download_url`→the release zip, `show_on_*=true`. The website Buy button + the launcher
  "רכישה — 53 ₪" both render now; after a PayPal purchase → `user_purchases` completed →
  `owns_game('anno1800')` → install unlocks. (CP2077 model: the raw GitHub zip stays publicly
  downloadable; payment buys launcher auto-install convenience.)
- **SHIPPED 2026-06-23:** `build_exe.bat` (BUILD_ID `20260623003946`, dev_build 4) → ISCC →
  `publish_release.py 1.0.0 dev` → GitHub `v1.0.0-dev` (asset clobbered) + Supabase
  `launcher_releases` id=41 (is_current). Verified `/api/launcher` buildId `20260623003946`
  (== baked), sha `62e8884a…`, size 247,885,615 B; `/api/games` anno1800 priceCents 5300.

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

## Watch Dogs 2 Hebrew — full toolchain built + proven in-game (2026-06-17)

Feasibility was answered **GO** and the **entire tooling is built and validated end-to-end**:
Hebrew text + injected Hebrew font glyphs render correctly **RTL in-game** (proven with test
markers; Latin stays pixel-perfect/vanilla). The ONLY remaining step is the actual EN→Hebrew
translation of the 48,138 lines (NOT done, by user request). Full recipe + format notes:
**`games/watchdogs2/PIPELINE.md`**; deep dive in `games/watchdogs2/FEASIBILITY.md`; memory
[[wd2-feasibility-go]].

- **Engine/format:** Ubisoft Disrupt, FAT5 v11 archives (`.fat`+`.dat`). The Arabic-slot
  hijack works: user sets Settings → Written Language → **Arabic** (`TextLanguage2=22`) and
  the engine renders RTL. Subtitle/narrative text = `languages\main_arabic.loc` (format `SL`,
  custom Huffman). `oasisstrings.rml` is NOT read at runtime; the **main menu/frontend is
  english-locked** (minor limitation). Font = `ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd`
  + atlas `..._1.xbt` (TBX header + DXT5 DDS 1024×2048).
- **Tools (`games/watchdogs2/`):** `work/wd2_loc.py` (.loc **encoder/repacker** — 100%
  round-trip incl. Hebrew; the hard novel part), `tools/loctool/loctool.exe` (.loc decoder,
  C# port of ahmet-celik), `work/wd2_archive.py` (extract/deploy/**revert** via fat-redirect;
  backups in `F:\WD2_lang_backup`), `work/wd2_font.py` (Hebrew font-atlas generator → .fnt+.xbt;
  keeps every original glyph+metric, adds Hebrew px=40 in a taller 1024×2304 atlas),
  `tools/ffdconverter/` (FFDConverter `-v WD2`, .ffd↔.fnt). Also `tools/Gibbed.Disrupt/`
  (Unpack/Pack/ConvertXml, LZ4LW decompress).
- **Deploy = fat-redirect** (append stored file to `.dat` + rewrite the 20-byte `.fat` entry;
  v11 stored ⇒ UncompressedSize=0). Run with EAC off: `WatchDogs2.exe -eac_launcher` (offline).
- **Hard-won fixes:** subtable block-offsets are relative to the SUBTABLE START (incl. the
  offset-array); Pillow's DDS header writes a wrong dwPitchOrLinearSize/mipcount → splice the
  ORIGINAL DDS header + our DXT5 body; glyphs are white-RGB + alpha=coverage; the original
  atlas is full → use a taller atlas. A proof `main_arabic.loc` + Hebrew font are currently
  DEPLOYED to the live install (revert: `python work/wd2_archive.py revert "<path>"`).
- **To finish (when asked):** translate `en.loc.txt` EN→Hebrew with the SM2 LM trio pattern
  (§ Universal Playbook below) → `wd2_loc.py encode` → deploy. Then publish like SM2/CP2077.

### WD2 INTERFACE translation — ✅ COMPLETE + DEPLOYED 100% (2026-06-19)

**DONE:** the full WD2 UI is Hebrew and LIVE in-game — **19,419 translated + 96 left-Latin
(handles/codes/place names) = 19,515/19,515, 0 missing, QA-clean.** The local-LM run reached
~95%; the **final ~338 tail was finished by an external Google/Antigravity agent** via the
self-contained handoff at `games/watchdogs2/agent_handoff/` (`INSTRUCTIONS.md` + `to_translate.json`
+ `hebrew.json` + `get_batch`/`loop_split`/`loop_merge`/`qa_scan` + `skip.json` for untranslatable
handles). The agent translated itself (no model), looped to "All done!", parked untranslatables to
`skip.json`. Deployed: `wd2_ui_merge.py agent_handoff/hebrew.json` (visual) → `wd2_loc.py encode`
→ `wd2_archive.py deploy` (3 archives).

**PUBLISHED `v1.0.0-beta.1` (UI-only beta, like SM2) — 2026-06-19.** GitHub repo
`nehorayc04/watchdogs2-hebrew-mods`, FULL release `v1.0.0-beta.1` (so `releases/latest`
resolves) with `manifest.json` + `watchdogs2_hebrew_ui.zip` (1.46 MB, sha
`79345481ffb0d6415b63c0b0757e63eedbffa9c63febd28ede6b43c960bea625`). Zip bundles the deployed
`main_arabic.loc` + Hebrew font + a self-contained `install.py` (auto-finds the game,
fat-redirect, `--revert`) + `wd2_archive.py` + Hebrew readme. Packer:
`games/watchdogs2/pack_and_release.py` (sources in `release_files/`). Supabase synced via
`publish_version.py watchdogs2 1.0.0-beta.1 --stage beta --apply` + a PATCH setting
`games.status=beta` + `download_url`→the release zip. Worker slug `watchdogs2-hebrew` added to
`games/steam/steam_mod_worker/src/index.js` — **needs `npx wrangler deploy` (user's Cloudflare
token)**; NOT required for the website Download button (download_url points straight at GitHub).
3 news suggestions pushed.

**UI lines ALSO uploaded to the community `/translate` pool** — `community_translate.py import
watchdogs2` set `current_he` for 19,419 ids (source_en preserved from the realigned pool); live.

**Remaining: spoken subtitle lines — NOW RUNNING (2026-06-19).** The original in-progress notes follow.

### WD2 full-corpus linguistic QA (4 parallel Google agents) → beta.3 PUBLISHED (2026-06-27)

A complete EN-vs-HE proofreading pass over **all 39,500 translated lines** (UI+subtitles) by
parallel no-history Google/Antigravity agents, then build+publish. **100% reviewed · 9,487
corrections applied.** Tooling: `games/watchdogs2/agent_handoff_qa/` (`build_corpus.py` →
`corpus.json {id:{en,he,src,flags}}`; `prep_agents.py N` splits the REMAINING into disjoint
`agent_K/` folders each with a full `INSTRUCTIONS.md`; per-folder `qa_get_batch.py`/`qa_merge.py`;
`apply_corrections.py` writes fixes back to `agent_handoff/hebrew.json` (ui) + `agent_handoff_subs/
hebrew.json` (sub)). Round flow: user says "N agents", Claude runs `prep_agents.py N` + pastes N
SHORT pointer blocks (each → its `agent_K/INSTRUCTIONS.md`); progress accumulates across rounds via
`progress_reviewed.json`/`progress_corrections.json`. Mid-progress "build without publish" =
apply→`wd2_sub_merge`(enum-driven visual/logical)→`wd2_loc.py encode`→`wd2_archive.py deploy`
(game CLOSED, **venv python** for the bidi `visual()`); `wd2_archive.py revert` undoes it.
- **⚠️ Anti-cheat = attestation-by-enumeration** (`qa_merge.py`, 2026-06-26). Agents kept writing
  an `auto_qa.py` that dumped `{}` to bulk-mark the tail "reviewed" without reading. Fix: a line is
  marked reviewed ONLY if the agent gives it an entry in `qa_fixes.json` — a correction OR literal
  `"OK"`. Empty/partial `{}` advances NOTHING (same batch returns forever) → can't fake `QA done!`.
  Salvage when an agent cheats: keep its `corrections.json`, reset `qa_reviewed.json` to the
  corrected pks only. `prep_agents.py` got a resilient `_force_rmtree` (AV/indexer lock retries).
- **Targeted transfer** when an agent is quota-blocked: harvest all folders to progress, move the
  blocked agent's un-reviewed ids into a free agent's `corpus.json`, retire the blocked one (shrink
  its corpus to done → resuming = `QA done!`, no collision). Used twice (agent_2→4, agent_2→1).
- **Published `1.0.0-beta.3`** (same pattern as beta.2 — keep the FULL `v1.0.0-beta.1` tag as
  releases/latest, CLOBBER its assets; do NOT mint a beta.3 tag): updated `release_files/`
  (new `main_arabic.loc` + **font v8**) → `pack_and_release.py 1.0.0-beta.3 --pack-only` (zip
  1,360,186 B, sha `7bc3fa81e072be33158ea6cf2c9792eb5e319e53bd2f6a499f56a6813e3d02a3`) →
  `gh release upload v1.0.0-beta.1 --clobber manifest.json watchdogs2_hebrew_ui.zip` →
  `publish_version.py watchdogs2 1.0.0-beta.3 --stage beta --sha … --size 1360186 --archive-url
  …/v1.0.0-beta.1/…zip --apply`. Structural verify (`wd2_full_qa_scan.py`) on the built corpus =
  0 FOREIGN, 0 NIQQUD, 1 benign `\n`-reflow TOKEN_MISMATCH; MISORIENTED/PLACENAME/ICON/ENGLISH_LEAK
  are pre-existing by-design categories. GitHub manifest + Supabase games + mod_version_history all
  beta.3; public download HEAD 200 (1,360,186 B). 3 news drafts pushed.
- **⚠️ GOTCHA — WD2 has TWO full releases (`v1.0.0-beta.1` AND `v1.0.0-beta.2`), so GitHub's
  `releases/latest` = `v1.0.0-beta.2`** (higher semver, both non-prerelease). The Worker
  (`steam_mod_worker/src/index.js`) reads `releases/latest`, so **the clobber MUST target
  `v1.0.0-beta.2`, NOT beta.1** (the documented "keep beta.1 as latest" rule was already broken
  when a beta.2 tag got minted). First publish this round clobbered beta.1 → Worker stayed stale;
  re-clobbering `v1.0.0-beta.2` (`gh release upload v1.0.0-beta.2 --clobber manifest.json
  watchdogs2_hebrew_ui.zip`) fixed it → Worker `/watchdogs2-hebrew/manifest` = beta.3 + `/archive`
  HEAD 200. **`npx wrangler deploy` did NOT help** (the Worker reads live; the issue was the wrong
  release). For future WD2 publishes: clobber `v1.0.0-beta.2` (and beta.1 too for safety), then
  verify `gh api repos/nehorayc04/watchdogs2-hebrew-mods/releases/latest` resolves to beta.2 with
  the new manifest. `games.download_url` points at the beta.1 asset (also clobbered to beta.3, so
  identical bytes — fine). Memory [[parallel-agent-qa-protocol]], [[delegate-all-translation]].

### WD2 SPOKEN subtitles + dialogue — ✅ COMPLETE + PUBLISHED beta.2 (2026-06-20)

The spoken subtitles/dialogue are DONE and shipped. The local LM ran to ~69%, then the
remaining lines + a full 3-agent QA pass (review→fix EN vs HE, the `agent_handoff_subs/`
`qa_get_batch`/`qa_merge` loop — the GOOGLE agents do the translating/fixing, NOT Claude;
see [[delegate-all-translation]]) brought ALL 21,678 lines to QA-clean. Claude verified
(0 real token mismatches, 0 foreign/niqqud, full coverage), built (`wd2_sub_merge` UI-visual +
subs-LOGICAL → `wd2_loc.py encode` → `wd2_archive.py deploy` to common/patch/patch2), and
published **`v1.0.0-beta.2`** (GitHub `nehorayc04/watchdogs2-hebrew-mods`, sha `fae97e28…`,
1,364,965 B, releases/latest; Supabase games + mod_version_history + download_url → beta.2;
scope now `full`). The 6 residual "הזאמור" garbles were then fixed by a user-authorized
one-time DETERMINISTIC regex `הזאמור[סת]?`→`לעזאזל` (0 residual), rebuilt + deployed, and the
SAME `v1.0.0-beta.2` re-published (GitHub assets CLOBBERED, new sha `1f074e7e…`, 1,364,940 B;
Supabase history sha/size synced). Worker slug still needs `wrangler deploy` (not blocking).
Memory [[wd2-subtitle-run]], [[delegate-all-translation]].

### WD2 SPOKEN subtitles + dialogue — unattended weekend run STARTED (2026-06-19)

User reversed the "everything EXCEPT the lines" scope: run the local LM
(`gemma-4-31b-it@q2_k_xl`) all of Shabbat (~24h) translating **everything that
remains**, with the full heavy protections + comprehensive watchdog. UI is 100% done,
so the model is dedicated SOLO to this. Memory [[wd2-subtitle-run]].

- **Queue = 21,938** (`work/wd2_sub_build_queue.py`) from the **CLEAN oasis XML**
  (`extract/en_oasis/.../oasisstrings_converted.xml`) — NOT `main_english.loc.txt`
  (GARBLED for barks). 16,357 soundbinary subtitles + 5,581 translatable named;
  excludes pure-name enums + already-done UI + skip. Ordered **short-real-first** (the
  fast bulk first; long mixed-language narratives last). EN = oasis `value` (clean UTF-8).
- **Trio (`work/`):** `wd2_sub_translate.py` (serial, token-budget batching, narrative
  prompt, `validate()` + 3-strike park + atomic; state `C:/tmp/wd2_sub_he.json` logical
  Hebrew), `wd2_sub_watchdog.py` (**RUN THIS** — owns LM+translator+QA; **adds SM2-grade
  LM management** the UI watchdog lacked, now SM2 isn't sharing the slot: monitor
  `lms ps`, recover drop/hang via kill-translator-FIRST→`unload --all`→reload→probe→
  relaunch; hourly QA; auto-deploy every 500 when game CLOSED), `wd2_sub_merge.py`.
- **⚠️ bidi: subtitles stored LOGICAL** (the Disrupt engine bidi-reorders the Arabic
  narrative slot — FEASIBILITY's positive determination), the **OPPOSITE of UI/menu**
  (VISUAL, non-bidi). `wd2_sub_merge.py` applies `visual()` to UI ids but stores subtitle
  ids logical, converting the oasis literal `\n` → the skeleton `[LF]` marker; deploy
  combines UI (ui_all+ui_he+agent_handoff/hebrew.json) + subtitles.
- **LM = SOLO** `--parallel 1 --context-length 8192` (q2_k_xl 13.11 GiB, fits VRAM).
  Reload: `attrib -R %USERPROFILE%\.lmstudio\.internal /S /D` then `lms load
  gemma-4-31b-it@q2_k_xl -y --gpu max --context-length 8192 --parallel 1`.
- **Launch** (BASE python, hidden, PYTHONIOENCODING=utf-8): `Start-Process
  ...Python313\python.exe -ArgumentList '-u','work\wd2_sub_watchdog.py' -WorkingDirectory
  <games/watchdogs2> -WindowStyle Hidden`. **Status:** `python work/wd2_sub_translate.py
  --status` · `tail C:/tmp/wd2_sub_watchdog.log`. **Resume after reboot** = relaunch the
  watchdog (resumable/idempotent/singleton). Verified end-to-end: clean natural Hebrew,
  `\n` preserved, validate blocks Thai/Arabic leaks, merge stores subs logical + UI
  visual. **When the queue drains** → final deploy → publish a new beta (GitHub clobber +
  Supabase) like the UI.

Translating the game **UI/interface** (NOT the spoken subtitle lines — those stay English by
the user's standing rule "everything EXCEPT the lines"). Runs unattended on the local LM in
parallel with the SM2 run; auto-deploys into the live game. Memory [[wd2-ui-translation]];
full method in `games/watchdogs2/PIPELINE.md` (§ "UI translation").

**THE KEY DISCOVERY — where the UI text lives.** The full string table is `main_english.loc`
(48,138). The oasis XML (`extract/en_oasis/languages/english/oasisstrings_converted.xml`) keys
every string by `LineId` and tags it with an **`enum`**. **The `enum` is the ONLY reliable
UI/audio discriminator** — the XML section names (`CinemaSubtitles`/`BarkSubtitles`) are
USELESS (real UI like "Brightness" sits inside them):
- audio subtitle ⇒ `enum="soundbinary\N.bnk"`
- UI / everything else ⇒ a **symbolic name** (`enum="Brightness"`, `"Quality Main Menu"`,
  `"InventoryWheel_ammo"`, `"actNavigate"`).
An earlier pass wrongly took the **4,032 "not-in-oasis"** ids as the UI pool — that pool is
mostly leaked cutscene dialogue (only 1,602 of it was UI). The real UI is the NAMED oasis set.

**Full text breakdown (48,138 total):**
| Category | Count | Translated? |
|---|---:|---|
| audio subtitles (`soundbinary` enum) | 16,537 | ❌ the spoken lines — excluded by request |
| dialogue (not-in-oasis pool) | 4,032 | ❌ mostly cutscene/phone dialogue (1,602 of it WAS UI → done earlier) |
| NAMED (UI + content) | 27,573 | partial → |
| ⮡ **UI queue (translating now)** | **17,913** | 🔄 ~63%+ (`C:/tmp/wd2_ui_he.json`) |
| ⮡ excluded content (names/media/phone/email/paint codes) | 9,660 | ❌ stays Latin / near "lines" |
→ **Total UI being Hebrew = 19,515** (17,913 NAMED queue + 1,602 earlier `wd2_ui_all.json`).

**Renderer is NON-BIDI** (frontend + settings + HUD all draw glyphs in storage order) →
Hebrew MUST be stored **VISUAL (pre-reversed per line)** via `work/wd2_ui_merge.py:visual()`
(reverses each Hebrew run + the run order; keeps Latin / `[TOKEN]` / `{VALUE}` / `%spec` /
`[CR]`/`[LF]` intact). Logical storage → mirror text in-game (the "עברית ראי" bug, seen 2026-06-18
after a parallel session removed the `visual()` call — RESTORED). Latin proof: the main menu
(visual) renders correct; a logical-stored settings string rendered mirror.

**Tools (`games/watchdogs2/work/`):**
- `wd2_ui_translate.py` — the translator. Same model `gemma-4-31b-it@q2_k_xl` at
  `localhost:1234` (SHARES the serial `--parallel 1` slot with the SM2 run — requests
  interleave, so it runs alongside SM2 at ~9 str/min combined). Serial, `BATCH=14`, short
  strict UI prompt, **placeholder-multiset validate**, atomic resumable output. Queue =
  `C:/tmp/wd2_ui_queue.json` [{id,enum,en}], ordered **real-words-first** (untranslatable
  ordinals st/nd/rd/th, single chars, no-letter codes pre-skipped to `C:/tmp/wd2_ui_skip.json`).
- `wd2_ui_watchdog.py` — **RUN THIS** (the supervisor). Owns the translator via Popen
  (relaunch on death + hang-kick if `done` frozen >1800s); **auto-deploys every 400 new
  strings whenever WatchDogs2.exe is CLOSED** (combine `wd2_ui_all.json`+`wd2_ui_he.json` →
  `wd2_ui_merge.py` visual → `wd2_loc.py encode C:/tmp/ar.loc … main_arabic_he.loc` →
  `wd2_archive.py deploy "languages\main_arabic.loc"`); hourly structural QA (below).
  **Launch under BASE python** (`…\Python313\python.exe`, NOT the venv stub) hidden, with
  `PYTHONIOENCODING=utf-8`. Resume after reboot = just relaunch it (resumable, idempotent).

**Two-layer translation PROTECTION (the user's "כלבי שמירה" — same as SM2/CP2077):**
- **Layer 1 — `validate()` at WRITE time** (per line, fail → re-queued, never written):
  Hebrew+Latin only · no foreign script · no niqqud · **placeholder multiset identical**
  (`[TOKEN]`,`[CSS_…]`,`{VALUE}`,`%d/%s/%ls/%%`,`&#xA;`/`&amp;`) · **model-refusal / "here is the
  translation" leak** rejected (`REFUSAL` regex) · **length anomaly** (HE > 2.4×EN+40 = rambling)
  · **name/code passthrough** (accept no-Hebrew when source is a proper-noun ≤4 words OR has no
  real lowercase word — else "Marcus"/"DedSec" churn forever; the SM2 lesson).
- **Layer 2 — hourly QA in the watchdog** (`qa_entry`/`run_qa`, ONE source of truth — reuses
  Layer-1's `T.REFUSAL`/`T.placeholders`/etc.): re-checks new lines; **removes** defects so they
  re-translate; parks a key failing 3× to `wd2_ui_skip.json`. Self-test passed; live it has
  caught Thai-script + refusal leaks with **0 false flags** so far.

**State / artifact files (all `C:/tmp/`):** `wd2_ui_queue.json` (17,913 queue) ·
`wd2_ui_he.json` (resumable output {id: hebrew_LOGICAL}) · `wd2_ui_all.json` (1,602 earlier UI) ·
`wd2_ui_skip.json` (parked/untranslatable) · `wd2_ui_qa_seen.json` · `wd2_ui_watchdog_state.json`
(`last_deploy`, `strikes`) · `ar.loc` (encode base) · `main_arabic.loc.txt` (AR skeleton =
English, since WD2 ships no Arabic) · `main_arabic_he.loc` (deployed build) · logs
`wd2_ui_translate.log` / `wd2_ui_watchdog.log`. Deploy target = `languages\main_arabic.loc`
across common/patch/patch2 (backups `F:\WD2_lang_backup`); activation = in-game Written
Language = Arabic, launch `WatchDogs2.exe -eac_launcher`.

**Status check anytime:** `python work/wd2_ui_translate.py --status` (count) ·
`tail C:/tmp/wd2_ui_watchdog.log` (supervisor actions). **When the queue drains** → the watchdog
does a final deploy; then publish like SM2/CP2077 (GitHub release + Worker slug + Supabase
`games` row + `mod_version_history`). The spoken-subtitle lines remain a separate future task.

## God of War: Ragnarök Hebrew — foundation built, feasibility GO (2026-06-17)

New game scaffolded at `games/godofwar_ragnarok/` (FEASIBILITY.md / RECON.md /
PIPELINE.md + `work/` trio). **Read side proven end-to-end; nothing in the game
folder modified yet.** Two engineering gates remain before a full run.

- **Format (fully cracked):** localization = `exec/wad/pc_le/r_lang_<loc>.wad` =
  **LZ4 frame** (magic `04 22 4D 18`, Python `lz4.frame` round-trips, ~2.3×) →
  inner **WAD** with `WTOC` table-of-contents @0 → **`MSGS_TXT`** section holding
  newline-delimited records `*<numeric_id>*\n<value>\n`, **UTF-8**, ids identical
  across locales. So Hebrew (UTF-8) stores byte-for-byte like the Arabic slot.
- **Arabic-slot hijack applies cleanly** (playbook §0): Arabic is an OFFICIAL full
  locale (`r_lang_ar.wad` present; `21 ar ARABIC` in `exec/languages/LANGS_GOWR09000.txt`;
  `"ar"` in `boot-options.json`) → the engine's RTL/bidi is dev-tested. Mechanism =
  edit `r_lang_ar.wad`, drop in `pc_le/`, set in-game language=العربية — identical
  to the existing Nexus lang-mods (Indonesian/Vietnamese) and CP2077/SM2/WD2.
  Community packer exists: **"God of War Localization Tool" by Delutto** (fallback).
- **`work/gowr_wad.py`** — read-only WAD reader: `decompress` / `extract` (→`{id:str}`)
  / `stats`. Verified on both reference WADs (EN `Vanir Summon` ↔ AR `استدعاء فانير`
  under `*372*`). Corpus dumped: `work/english.json` (53,199) + `work/arabic.json`
  (49,199). **Translatable scope = 48,886** shared EN∩AR ids (EN value = source →
  Hebrew → AR-slot id). Preserve tokens verbatim: `[[S:CHAR:vo_…]]` voice cues, `\n`,
  `[style=Highlight]`/`[/style]`, `[i]`/`[/i]`, `%d`, `[Icons:…]`. Lengths median 83 /
  max 2,279 chars → token-budget batching.
- **Trio templates laid** (adapted to this format, compile-clean, ready for gate-1):
  `work/gowr_translate.py` (EN→He, serial gemma-4, token-budget batches, validate(),
  atomic flush, seed GoW glossary), `work/gowr_watchdog.py` (self-healing supervisor —
  kill-client→`unload --all`→probe→relaunch; UTF-8 children), `work/gowr_progress.py`
  (60 s push to `/api/admin/progress`, `gameId="godofwar_ragnarok"`).
- **Install:** `Game Lab/God of War - Ragnarok/` (FitGirl repack, app v01.01 — the
  staging/test copy; ignore the `C:\Games` one). Reference WADs + decompressed `.bin`
  + corpus JSONs are gitignored (copyrighted/derived); only our code+docs are tracked.
- **Open gates (see FEASIBILITY.md):** (1) **re-pack round-trip** — rebuild the inner
  WAD `WTOC` offsets for a resized `MSGS_TXT` + re-LZ4 (or use Delutto), prove a
  test-string shows in-game; (2) **Hebrew font glyphs** — the Arabic font (`copperplate_*`/
  `godofwar_*` resources) almost certainly lacks Hebrew letters → inject like SM2/WD2.
  Translation can run in parallel with solving repack; only DEPLOY is gated. Backup
  `r_lang_ar.wad.he_backup` before any game-file write.

### BOTH gates SOLVED — Hebrew renders readable RTL in-game (2026-06-18)

The two open gates (repack + Hebrew font) are **closed and user-confirmed in-game**:
the menus render readable, correctly-ordered Hebrew (titles, settings rows, calibration
screens, the long data-collection paragraph). This is the hard, novel engineering done.

- **🟢 GATE 1 — WAD repack (`work/gowr_wad.py`).** Two breakthroughs:
  1. **LZ4 `compression_level=0`** is BYTE-IDENTICAL to the game's packer
     (`pack({})` reproduces the original WAD, MD5 `10963861a94343cf72d4a4174fd59e2b`).
     The engine **REJECTS level-9 frames** (valid LZ4, different 64 KB-block layout) →
     blank text + crash. So `pack()` MUST use `lz4.frame.compress(..., block_linked=False,
     content_checksum=True, store_size=True, compression_level=0)`.
  2. **Constant-size MSGS_TXT pad (delta=0).** Growing `MSGS_TXT` shifts the downstream
     streams (font atlas / SMF) → font corruption → all text blank. Hebrew is MORE compact
     than Arabic (≈ -30 KB), so `pack_blob()` pads MSGS back to the EXACT original byte
     size with trailing `\x00` (and re-appends the original single `\x00` terminator —
     dropping it caused a delta=-1 corruption). With delta=0 the WTOC header stream-0 size
     (+0x14), entry-31 size (+0x04) and SMF entries 43-46 (+0x78) updates are all no-ops →
     nothing downstream moves → bulletproof. (If a build ever can't fit, those four fields
     ARE patched by the same code, but stay in delta=0 for safety.)
- **🟢 GATE 2 — Hebrew font injection (`work/gowr_font.py` `inject_hebrew`).** Atlas =
  `copperplate_ar` (entry 41, BC4 1024×1024); glyph table = `SMF_1` (entry 43, 0x70 header
  + 28-byte records sorted by codepoint + ~27 KB kerning tail). Record layout: +0 cp(u16),
  +12 atlasX×8, +14 atlasY×8, +16 height×8, +18 y_off(**signed** i16), +20 bearingX×8,
  +22 width×8, +24 advance×8. The breakthroughs:
  1. **OFF-BY-ONE codepoint mapping (the root cause of the early garble).** The format
     stores, in record(cp=X), the glyph OUTLINE for codepoint **X+1** (verified: record
     'A'=0x41 holds the 'B' outline). The engine renders codepoint C by exact-matching a
     record cp==C, then drawing the **previous** record's glyph. So Hebrew letter L needs
     (a) glyph(L) written into the record at **cp=L-1**, AND (b) a record AT cp==L to be
     the match-anchor. → write 27 records at cp=0x5cf..0x5e9 holding א..ת, PLUS a **28th
     blank anchor record at cp=0x5EA** so ת (the highest cp) gets an exact match (without
     it, "הגדרות"→"הגדרו", "התחבר"→"החבר" — the last letter dropped). Diagnosed
     definitively via `work/diag_latin.py` (inject LATIN markers into the Hebrew slots →
     read which letters appear in-game → revealed the -1 shift with zero font ambiguity).
  2. **Union-extent fixed cell** (kills clipping + stray dots). Render all 27 glyphs on a
     tall canvas at one fixed baseline, take the UNION ink extent across all of them as the
     cell height (so ל's ascender isn't clipped), clear+mark each atlas box fully dirty
     (removes speckle), align the cell baseline to the **Latin baseline (row 37)** via the
     signed `y_off` → Hebrew sits at the same size/position as English.
  3. **Font = David Regular** (`C:\Windows\Fonts\david.ttf`) — the user's stated
     light/airy preference; `pick_font()` prefers it. A GoW-themed Hebrew font does NOT
     exist (the game's Latin `copperplate`/`godofwar` fonts carry **zero** Hebrew glyphs —
     that is exactly why we inject). `inject_hebrew(blob, font, letter_h=34, ...)`,
     length-preserving (no stream shift).
- **`work/build_wad.py`** — the end-to-end builder: reads `hebrew.json`, `W.pack` (level-0
  + delta-0), injects the font, deploys to the Game Lab `r_lang_ar.wad`. Activation: in-game
  Settings → Text Language = **العربية** (Arabic slot). Offline verifiers (iterate WITHOUT
  burning an in-game test): `c:\tmp\gowr_verify2.py` (faithful engine model — sort by cp,
  render C via exact-match-then-previous-glyph) + `gowr_ingame_sim.py`.
- **⚠️ ENGINE-NATIVE limits (NOT mod-fixable — same for the official Arabic build).** Verified
  by dumping EN/AR/HE for the visible menu strings: **Arabic uses ZERO bidi control chars**
  (no RLM/RLE/LRM), spaces + translations are correct in our `hebrew.json`, and we match the
  Arabic byte-structure exactly. So the remaining cosmetic items the screenshot analysis
  raised are the engine's per-widget layout for the Arabic locale, identical in the shipped
  Arabic game, and CANNOT be changed via a localization WAD: (a) some description/explanation
  panels render **LTR / left-aligned**; (b) bullet markers sit on the LTR side; (c) the
  nav-hint icons (ESC/ENTER/H/«) sit on the LTR side of their label. These are the
  Arabic-slot-hijack tradeoff (cf. WD2's english-locked frontend), not data defects. Adding
  RLM marks where Arabic doesn't is risky (tofu) and unproven on this engine — deferred as an
  optional future experiment, not chased blind.
- **Translation status: 100% COMPLETE (2026-06-19)** — 48,885 / 48,886 translatable strings in
  Hebrew (the 1 untranslated = id 62333 = `\x{A0}`, a non-breaking-space code, not translatable).
  `hebrew.json` = 49,387 keys. Done via the `work/` trio (gemma-4) + a parallel Gemma/Antigravity
  agent looping 500-string batches (`get_batch.py`→split→translate→`loop_merge.py`).
- **⚠️ POST-TRANSLATION QA FIX (2026-06-19) — the agent's "100% clean" claim was WRONG.** A full
  token-integrity sweep found **560 structural mismatches** the agent's merge let through (a prior
  local-loop merge had a looser check): (a) **377 `\n`→real-newline conversions** + 17 nl-count
  diffs (the `\\n`/`\n` confusion — fixed deterministically by `c:\tmp\gowr_detfix.py`: protect the
  cue-separator newline, convert in-prose real newlines back to literal `\\n`); (b) **150 entries in
  ONE corrupted batch (ids ~119833-120767, Vanaheim Wisp dialogue) where the Hebrew belonged to a
  NEIGHBORING line** (wrong `[[S:...]]` cue proved it) — these + 16 tag-variant entries (196 total)
  were **RE-TRANSLATED by Claude** from the correct EN (`c:\tmp\gowr_apply_fixed.py`, token-validated
  before apply); (c) 2 niqqud stripped. Re-verify: **0 token mismatches, 0 niqqud, 100% coverage.**
  Backups: `hebrew.json.bak.detfix.*` + `.bak.claudefix.*`. LESSON: always run a full
  `TOK.findall(en)==TOK.findall(he)` sweep over the whole spine after a bulk agent run — do not
  trust the agent's own merge-time check; a wrong `[[S:]]` cue is the signal of a misaligned batch.
- **⚠️ BUILD CROSSED INTO delta>0 (first time, 2026-06-19) — NEEDS IN-GAME VERIFICATION.** All
  earlier proven-in-game builds (≤72%) were **delta=0** (Hebrew fit inside the Arabic byte budget,
  padded). At 100% the Hebrew MSGS_TXT is **+303,526 B larger than Arabic**, so `pack_blob` now
  takes the **delta>0 path**: it grows stream-0, patches the WTOC stream-0 size (+0x14), MSGS entry
  size (+0x04) and SMF entry offsets (43-46, +0x78); the atlas is in **stream-1** which shifts
  automatically (its base derives from stream-0 size, internal offset unchanged). Offline-verified
  coherent (MSGS parses 49,199 entries, Hebrew matches spine, font present), but whether the engine
  derives stream bases from WTOC sizes is **UNPROVEN** — the user must launch + confirm menu text +
  font still render (revert = copy `r_lang_ar.wad.he_backup`). Deployed to BOTH Game Lab AND
  `C:\Games\God of War - Ragnarok` (the play install). Community pool `/translate` (`gowragnarok`)
  refreshed to 48,886 (0 open).
- **Next when in-game confirmed:** publish like SM2/CP2077 (GitHub release repo + Worker slug +
  Supabase `games` row + `mod_version_history`).
- **Font polish (2026-06-18, after in-game review):** `inject_hebrew` calibrated past the
  first readable build — (a) **vertical**: `y_off = cell_h - baseline_in_cell` (engine is
  baseline-anchored: `bitmap_bottom = line_baseline + y_off`, native caps use y_off=0; the
  earlier `37 - baseline_in_cell` put Hebrew ~16 px too high); (b) **soft engraved look**:
  native copperplate glyphs peak at alpha ~180 (NOT 255) and are dominated by a mid-range
  glow (~84-100% box fill) — so render supersampled + add a `GaussianBlur` GLOW
  (`max(sharp, glow*1.4)`, peak clamped to 180) to reproduce the per-letter shadow the user
  asked for; the old hard `a[a<28]=0`/max-255 looked flat + "מקוטע". `:`/`.`/`,` stay native
  baseline glyphs (also used inside `[Icons:…]` tokens — not safe to move). `build_wad.py`
  reads `hebrew.json` each build, so font + translation co-ship.

## Assassin's Creed Shadows Hebrew — groundwork laid, GO-WITH-CAVEATS (2026-06-17)

Feasibility researched + the project skeleton built. Verdict **🟡 GO-WITH-CAVEATS,
"prove-before-invest"**: 4 of 5 pipeline pillars are SOLVED and locally verified;
the project is gated on ONE hard dependency — there is **no free/open/scriptable
forge REPACKER for the 2025 `scimitar` v42 generation**. A *manual* one-off Hebrew
mod is likely achievable; the *automated launcher pipeline* (usual end goal) is
blocked until an open repacker exists. Full writeups: `games/acshadows/FEASIBILITY.md`
/ `PIPELINE.md` / `RECON.md`; memory [[acs-feasibility-go-with-caveats]].

- **Install:** `C:\Games\Assassin's Creed Shadows`, Ubisoft **Anvil**, ~142 GB,
  **99 `.forge` archives ALL version `scimitar` v42** (`b"scimitar\x00"` + `uint32
  LE 0x2A` @ offset 9 — verified via `games/acshadows/tools/acs_forge_probe.py
  survey`). Forge inner blocks are **Oodle-Kraken** compressed (lead `0x8C`); the
  game ships **NO `oo2core` DLL** (a repacker must supply one from another title).
  `dstorage.dll` present (DirectStorage/GDeflate streaming).
- **🟢 SOLVED — FONT (the big de-risk):** `resources/AvenirNextWorld-Regular.ttf`
  already carries **52 Hebrew glyphs (real outlines, not `.notdef`)** + 104 Arabic +
  133 Arabic presentation forms. The shipped UI font renders Hebrew AND does Arabic
  shaping/RTL — **no font work at all** (unlike Heebo/SM2, atlas/WD2, CR2W/CP2077).
- **🟢 SOLVED — Oasis loc system:** `VoiceAnimDataByOasisID` + `Dialogue*` in the
  Anvil type table. Text = per-language binary **`LocalizationPackage_<Lang>.data`**
  INSIDE the forge, keyed by numeric Oasis hashes (one file per language) — WD2's
  oasisstrings family. Lives in `DataPC_boot.forge` (20.7 GB) + its patch forges, NOT
  the per-language SOUND forges (audio only: bra/eng/fre/ger/ita/jap/spa, no Arabic VO).
- **🟢 SOLVED — language select = trivial INI edit:** `Documents\…\ACShadows.ini`
  `[Language] Text=/Subtitles=` use plain codes (`en-US`); flip to `ar-AE`. The 23-byte
  root `localization.lang` (`b"LANG…"`) is just a pointer stamp.
- **🟢 SOLVED — deploy/Denuvo:** Denuvo protects the EXE, not asset forges — many
  Nexus retexture/outfit forge mods load fine; no EAC. Deploy = repack-and-replace
  **`DataPC_boot_patch_01.forge`** (the slot the live modding scene + Mod Manager
  v1.0.4 use — NOT `patch_02`, which is the game's own TU forge) + back up vanilla;
  re-apply after each game update (Ubisoft Connect "verify" reverts it).
- **🔴 THE GATE:** the only v42 extract+REPACK tool is **AnvilToolkit's
  donation/Discord-gated AC Shadows BETA** (public release stops at Mirage 2023). Its
  ability to repack a v42 `LocalizationPackage` into a forge that LOADS is unproven by
  any artifact, **no AC Shadows text mod exists in ANY language** (only retextures),
  reimport must preserve the `.header` sidecar or the game crashes, and a Discord-gated
  closed binary **cannot be bundled into the launcher**.
- **✅ STAGE 0 PART A — PASSED in-game (2026-06-17, user-confirmed).** Set
  `Text/Subtitles=ar-AE` via `acs_set_language.py --arabic` + launched the VANILLA
  game → the first-run setup screen rendered **fully Arabic, correct engine-native
  RTL** (`لغة النص=العربية`, `لغة الصوت=English`). **The Arabic RTL text slot is REAL
  and selectable on this SKU** — the research dispute (Game8 omitted Arabic) is
  resolved GREEN. Font + Arabic-slot + locale + oasis + deploy are now ALL proven;
  **exactly one gate remains** (the v42 repacker).
- **NEXT — Part B (the only remaining gate, needs external tools):** acquire the
  ATK beta + an `oo2core` DLL, extract the Arabic `LocalizationPackage`, repack it
  UNCHANGED into `patch_01`, deploy → does it boot showing vanilla Arabic? This
  zero-translation identity round-trip proves the repack+Oodle+`.header`+integrity+load
  chain before any translation. `tools/acs_capture.py` (built) grabs the game window
  for in-game verification (works — not exclusive-fullscreen).
- **Skeleton built:** `games/acshadows/` — `tools/acs_forge_probe.py` (read-only
  inspector, working), `tools/acs_set_language.py` (ini flip + backup, working),
  `tools/acs_capture.py` (window grab), `work/acs_{translate,watchdog,progress}.py`
  (SM2 LM trio copied as TEMPLATES), `extract/` (empty).
- **✅ READ-SIDE TOOLING BUILT + format largely cracked (2026-06-17, pure-RE "way 1"):**
  - **Oodle SOLVED** — `tools/acs_oodle.py` wraps `oo2core_9_win64.dll` (borrowed from
    `C:\Games\Battlefield 6`; game ships none) via ctypes: compress+decompress
    round-trip identical, our Kraken output lead byte = `0x8C` = forge blocks. **The
    Oodle wall is gone — we can decode AND re-encode** (key for building our own
    repacker; only DLL *redistribution* is gated, not local calls).
  - **v42 forge TOC reader VERIFIED** — `tools/acs_forge.py` (list/raw/verify/extract/
    decode-stats). Index: `u64 ptr@off13` → `u32 count@idx+0x0C`, `u32 array@idx+0x28`;
    24-byte records `{u64 offset,u32 ts,u32 flags,u32 size,u32 nameHash}`. Cumulative
    invariant `off[n+1]==off[n]+size[n]` holds **100%** incl. **DataPC_boot.forge
    (129,843/129,843, 20 GB)** + shared_00 (35,076/35,076).
  - **Resource sub-container cracked for simple resources** — chunk header 0x1F bytes:
    `magic 0x57FBAA33 · 0x1004FA99 · … · u32 uncompSize@+0x13 · u32 compSize@+0x17 ·
    u32 cksum@+0x1B · payload@+0x1F` (Oodle or stored). **98/103 AnimusRoom resources
    decode.** READ proven end-to-end (TOC→chunk→Oodle→bytes).
  - **✅ READ PATH COMPLETE — real dialogue text read (pure RE "way 1", no gated tool).**
    LARGE multi-block resources (the loc package = boot.forge idx 36626, nameHash
    `0xa5b3bea0`, base+patch dup) use **256 KB blocks** preceded by a `{count,blockSize}`
    header + a comp-size table + small variable inter-block headers. A robust walk
    (binary-search each block's comp length + forward-scan past headers) decoded **all
    134 blocks → 35.1 MB, whole resource**. Translatable text is **UTF-16LE keyed by
    Oasis IDs** (`0xAC4BDB1D…`); recovered real lines verbatim ("Don't be mad.", "Can you
    play something, Naoe? Please?", etc.). So TOC→resource→multi-block Oodle→UTF-16
    dialogue all works in home-built Python.
  - **✅ WRITE FORMAT CRACKED + CODEC ROUND-TRIPS (2026-06-17).** Decompiled the FREE
    public **AnvilToolkit v1.3.4** with `ilspycmd` (same method as AC2; user downloaded
    the binary, no donation) → exact `CompressedFileData` spec (full writeup
    `games/acshadows/FORMAT.md`): `u64 Magic 0x1004FA9957FBAA33` + `CompressionInfo[7]`
    (i16 ver=3, u8 algo=8=Oodle, OodleVersions[Shadows]=9 → oo2core_9) + `i32 blockCount`
    + BlockInfoData `{i32 uncomp, i32 comp}×N` + CompressedData `{u32 adler, comp bytes}×N`.
    **THE CHECKSUM is LZO Adler-32 = `zlib.adler32(data, 0)`** (start value 0) — a plain
    data checksum, NOT anti-tamper — **verified byte-for-byte on multiple blocks**. So a
    home-built Python repacker is fully viable (this was the make-or-break unknown).
    `tools/acs_cfd.py` = decode+encode; **round-trip on the 56.3 MB loc resource = 2/2
    CFDs reproduce identically**. The entire read+write engineering is now proven offline.
    Decompiled ATK source kept at `c:\tmp\atk_src\`.
  - **REMAINING to in-game Hebrew:** (a) locate the Arabic-slot UI resource (the
    setup-screen strings — 36626 is English quest dialogue; the visible menu Arabic is a
    different, not-yet-located resource); (b) parse the Oasis id↔UTF-16 record layout to
    edit a string; (c) inject Hebrew → re-encode CFD → same-size in-place patch (delta-0,
    forge TOC unchanged) → deploy to `patch_01` (backup vanilla); (d) user launches +
    verifies Hebrew RTL. Denuvo protects the exe not asset forges (texture mods load), so
    the repack-loads risk is low. Then the standard translate→publish pipeline.

### Loc format RESOLVED + 15,997 English lines uploaded to /translate (2026-06-20)

The "fragment LocalizationPackage" theory (§4b of an earlier FORMAT.md) was **empirically
WRONG for Shadows**: the ATK `LocalizationPackage` class hash `0x6E37B1AF` (1849465967) is
**ABSENT** from every shipped forge (full-decompress scans: top-50 largest + all 25k of the
100KB–5MB band + the entire 129,844-resource boot.forge → zero hits). AC Shadows stores text
as **literal UTF-16LE**, two kinds:
- **Oasis line records (the translatable dialogue):**
  `[lineID u64][0xFADE9F44 u32][00][convID u64][0000][charLen u32][UTF-16LE]`. `0xFADE9F44`
  (`44 9F DE FA`) = the localized-string field tag; the u64 **before** it = the unique Oasis
  line-ID (cross-language key); `charLen` = UTF-16 unit count. Tool: **`tools/acs_oasis.py`**
  (`scan`/`dump`/`extract`). Distributed (no master table; densest resource = 84 lines).
- **Bare UI strings:** `[u32 charLen][UTF-16LE]`, no inline id (settings/menu, e.g. idx 40549
  — the proof-of-load path). Not yet pool-uploadable (needs a `resourceHash:index` key).

**Extracted + uploaded** (user request "upload all English lines like the other games"):
boot **14,084** + patch_01 **10,979** + patch_02 **7,921** = **16,725 unique lineIDs** →
merged/normalized (`tools/acs_build_ct.py`, drop 728 markup-only) → **15,997 rows** →
`universal/community_translate.py import ac-shadows` (game id is **`ac-shadows`** with a
hyphen; the games row already existed). Verified live on `/translate`: `untranslated_open =
15,997`. The per-language SOUND forges and the `*_dlc.forge` (Vault/Rift/CrystalCave/WhiteRoom)
have **0** oasis records. English is clean (no Arabic/JP leakage; markup like `[beat]`,
`[[grunts]]`, `[style=…]` preserved). Files: `c:/tmp/acs_en_{boot,patch01,patch02}.json` →
`c:/tmp/acs_ct_strings.json`.

**Still open (deploy-side gate, unchanged):** the dialogue resources carry the ENGLISH text
inline; whether the Arabic copy of each lineID sits in the SAME resource (so Hebrew can be
written keyed by lineID) or a separate package is **not yet confirmed** → the Hebrew
write-back path is unproven. The bare-UI same-size in-place repack (`acs_repack.py` on idx
40549) is still the only demonstrated write. Memory [[acs-feasibility-go-with-caveats]].

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

## Anno 1800 Hebrew — groundwork DONE + PROVEN in-game, GO (2026-06-21)

New game scaffolded at `games/anno1800/` (FEASIBILITY.md / RECON.md / PIPELINE.md
+ `work/`). Multi-agent adversarially-verified Phase-1 groundwork, then **both gates
CLOSED by an in-game proof (user-confirmed)**: deploy is the EASIEST in the project
(loose-file mod, no repack, no anti-cheat, keep user locale), Hebrew renders cleanly
in the injected font, and the native HUD is **NON-bidi → store VISUAL** (proven).
Ready for Phase 2 (translation). Memory [[anno1800-groundwork-go]].

- **✅ PROVEN in-game 2026-06-21 (user-confirmed):** a diagnostic mod in
  `Documents\Anno 1800\mods\zzz_hebrew_proof\` flipped main-menu labels. Result: the
  injected **Frank Ruehl font renders Hebrew perfectly** (no tofu), and an A/B on
  working menu GUIDs (New Game 154000 / Options 154002 / Credits 10438) showed
  **VISUAL-stored Hebrew reads correctly while LOGICAL reads reversed** → Anno's
  native HUD does **NOT** do bidi (WD2-menu/AC2 class). So `build_mod.py` defaults to
  **VISUAL** (`visual_line()` = WD2's proven `_visual_line`: Hebrew runs reversed,
  whitespace its own run, Latin/digit/[TOKEN]/%-spec runs intact, run order flipped,
  per line). The translator stores LOGICAL; `visual()` is applied only at build.
- **mod.io mods backed up for fast test launches:** the 189 subscribed mods (~14 GB)
  at `C:\Users\Public\mod.io\4169\mods\` were moved (instant same-drive rename) to
  `…\mods_DISABLED_hebrew_test\` (restore note `RESTORE_MODS_README.txt`; subscriptions
  in `metadata\state.json` untouched). Restore = rename back (game closed). The Hebrew
  mod itself lives in `Documents\Anno 1800\mods\`, loaded fast on its own.

- **Engine/format:** Ubisoft Mainz "Anno" engine; archives = **RDA "Resource File
  V2.2"** (`maindata/data0.rda`..`data33.rda` + per-lang `en_us0/de_de0/fr_fr0/
  ru_ru0.rda`). Format fully cracked; pure-Python READ-ONLY reader **built+proven**
  at `work/rda_reader.py` (seek-only block-chain, zlib-deflate, never loads a multi-
  GB file). Layout: header 0x318 (firstBlockOffset u64 @0x310), 32-byte BlockInfo
  chain at block tails, 560-byte DirEntry (UTF-16LE name[520]+offset+csz+usz+ts+unk).
- **Text spine:** `data0.rda` → **`data/config/gui/texts_english.xml`** (NOT
  en_us0.rda — that's Wwise audio). 12 LTR sibling `texts_<lang>.xml`. Schema UTF-8/
  CRLF: `<TextExport><Texts><Text><GUID>n</GUID><Text>s</Text></Text>…`. **28,165 EN
  records** (measured); numeric `<GUID>` SHARED across all languages = the id-mapping.
  25,167 genuinely localized vs DE; ~4% carry inline markup/placeholders. Scope ~28k
  base, ~1.5–2× with full DLC. UI/content-dominant (buildings/goods/quests/expeditions/
  newspaper/encyclopedia), thin spoken-subtitle tail. Extracted to `extract/`.
- **NO Arabic slot** (declared locales all LTR) → **AC2-class LTR-slot hijack**: ship
  Hebrew inside `texts_english.xml`; user keeps in-game Language=English. `engine.ini`
  `"TextLanguage"`/`"AudioLanguage"` are SEPARATE keys → English VO preserved free.
- **UI engine split (key finding):** the **main HUD is the engine's NATIVE GUI**
  (XML/binary layouts; `data/ui/*.dds` art; rendered with loose `data/fonts/*.ttf`).
  **CEF/Chromium 108.4.13** (`libcef.dll`) drives ONLY the stats/chart/debug web
  panels (d3/nvd3/jquery under `data/config/http`) — those get free ICU bidi; the
  **native HUD is NON-bidi (PROVEN in-game)** → store Hebrew **VISUAL**
  (`build_mod.py` default; `--logical` only for re-testing). Translator output stays
  logical; `visual()` applied only at build.
- **Font:** **NO shipped UI font has Hebrew** (cmap-verified all 15 `data/fonts/*.ttf`
  = Latin+Cyrillic; Meta/Kelvinch/Heuristica/Roboto + CJK). But they're plain loose
  TTFs → injection is LOW complexity (no CR2W-embed / DDS-atlas): `work/anno_font.py`
  ADDS the U+0590–05FF block from a Hebrew source (default Windows `frank.ttf` = Frank
  Ruehl serif, Belle-Époque-fitting; David alt) into each Anno TTF via fontTools
  (DecomposingRecordingPen + TransformPen scale to target upem; preserves the Anno
  font name/Latin/Cyrillic — only Hebrew added), shipped as loose-file `data/fonts/`
  overrides. **Verified offline:** injected metaoffcpro/kelvinch = Hebrew 27/27 +
  Latin 26/26 kept.
- **Deploy = loose-file mod, NO .rda repack.** Mod loading is **built into the game**
  (xforce/anno1800-mod-loader integrated; standalone repo archived) — no DLL to
  install. Drop `mods/<name>/` into **`Documents\Anno 1800\mods\`** (preferred — takes
  precedence, immune to Ubisoft Connect "Verify files", no admin) or `<install>/mods/`.
  Mod = `modinfo.json` + `data/config/gui/texts_english.xml` (ModOps patch: `<ModOp
  Type="add" Path="/TextExport/Texts"><Text><GUID/><Text/></Text>` — adding for an
  existing base GUID overrides it) + `data/fonts/<injected TTFs>` (+ optional scoped
  CSS for the CEF panels). **No anti-cheat** (no EAC/BattlEye). Activation: in-game
  Language=English, restart. Removal = delete folder. RdaConsole/RDAExplorer exist but
  only for one-time READ — we have our own reader, repack never needed.
- **Detection:** `game_detector` ALREADY has `anno1800` patterns + `Anno1800.exe`
  (key == proposed Supabase `games.id` `anno1800`). Single Steam install.
- **work/ tooling:** `rda_reader.py` (reader, proven) · `anno_font.py` (Hebrew TTF
  injection, proven) · `make_proof.py` (builds the proof mod) · `build_mod.py` (full
  mod assembler from `hebrew.json` {guid:he}, `--visual` flag) · `anno1800_{translate,
  watchdog,progress}.py` (SM2-trio adaptation). Precedent: Ukrainian (Nexus 539, RU-slot)
  / Czech (310) / Russian (136) full loose-file translation mods prove the mechanism;
  NO RTL precedent anywhere.
- **Phase 2 (translation) — AGENT HANDOFF BUILT (2026-06-21, user chose the agent path
  over the local-LM trio):** `games/anno1800/agent_handoff/` is the self-contained
  package for a fresh Google/Antigravity agent (per [[delegate-all-translation]] — Claude
  built tooling+glossary+instructions, never translates). Contents: `INSTRUCTIONS.md`
  (filled Hebrew handoff: Belle-Époque register, LOGICAL storage, Anno token rules,
  locked glossary) · `to_translate.json` {guid:en} (28,165) · `skip.json` (718 pure
  data-binding/number records pre-seeded) → **27,447 real translatable** · `hebrew.json`
  ({} output) · helpers `get_batch`/`loop_split`/`loop_merge`/`qa_scan` + `_tokens.py`
  (the KEY Anno bit: a **nesting-aware** token extractor for `<br/>` + nested `[...]`
  data-binds like `[AssetData([RefGuid] Text)]` — preserved verbatim, multiset-validated).
  Loop tooling end-to-end tested (valid merges atomic, dropped-token flagged). The agent
  self-translates in a `get_batch→split→translate→merge` loop to "All done!", writing
  LOGICAL Hebrew. **After the agent finishes:** Claude runs `python work/build_mod.py`
  (VISUAL by default + font inject → `Documents\Anno 1800\mods\zzz_hebrew_translation\`)
  → in-game Language=English → publish like SM2/CP2077 (GitHub `anno1800-hebrew-mods` +
  Worker slug `anno1800-hebrew` + Supabase `games` + `mod_version_history`). (The
  SM2-style local-LM trio `work/anno1800_{translate,watchdog,progress}.py` remains as an
  alternative haul path.)
- **TRANSLATION COMPLETE + MOD BUILT + DEPLOYED (2026-06-21).** Five sequential
  Google/Antigravity agents (no shared history; each handed a fresh self-contained
  resume instruction) ran the loop to "All done!": **27,300 translated + 865 skip =
  28,165 (100% coverage)**. Claude verified independently (GoWR lesson — never trust the
  agent's own merge check): full-spine sweep = **0 token mismatch / 0 foreign / 0 niqqud
  / 0 empty**; 29 internal asset-ID passthroughs (`small_feedback_ship01`,
  `MovieCapture_…`) moved to skip. Built via `work/build_mod.py` → VISUAL + 11
  Hebrew-injected fonts → `Documents\Anno 1800\mods\zzz_hebrew_translation\` (proof mod
  removed). **Two `visual_line` bugs found + fixed by the deployed-XML token sweep (would
  have shipped 1,069 broken binds):** (1) Anno `[...]` data-binds contain SPACES → must
  be **protected as atomic LTR placeholders** before the run-reversal (not split at
  spaces); (2) `<br/>` is a **line break** → split on it like `\n` and visual each segment
  independently (else line order swaps); also top-level non-overlapping tokenizer so a
  `%i` nested inside a `[...]` bind isn't double-extracted. Deployed XML re-verified: 0
  mismatches. **PENDING: user in-game verification** (Language=English, restart) → then
  publish (GitHub `anno1800-hebrew-mods` + Worker slug `anno1800-hebrew` + Supabase
  `games`/`mod_version_history`). The 189 mod.io mods stay disabled until the user restores.

### Anno 1800 — PUBLISHED v1.0.0-beta.1 + the cold-boot verdict (2026-06-22)

**SHIPPED.** Full Hebrew UI mod published. GitHub `nehorayc04/anno1800-hebrew-mods` FULL
release `v1.0.0-beta.1` (releases/latest) — `anno1800_hebrew.zip` (23,113,143 B, sha
`2fd7ee0da670a2487ff8876fc9596f5ce9a993aa33f384376372ab0fd67c8c0a`) + manifest.json. Packer
`games/anno1800/pack_and_release.py` zips the deployed loose-file folder `zzz_hebrew_translation`
(+ a Hebrew readme documenting both activation paths). Supabase synced: `publish_version.py
anno1800 1.0.0-beta.1 --stage beta --sha … --size 23113143 --archive-url …/v1.0.0-beta.1/anno1800_hebrew.zip
--apply` (games.version+release_stage + mod_version_history is_current) PLUS a direct UPDATE
`games.status='beta'` + `download_url`→the zip (publish_version leaves status/download_url alone).
Worker slug `anno1800-hebrew` added to `games/steam/steam_mod_worker/src/index.js` — **needs
`npx wrangler deploy` (user's CF token); NOT needed for the website Download button** (download_url
→ GitHub directly). All 4 surfaces sha-consistent. 4 news drafts pushed.

**THE COLD-BOOT VERDICT (triple-verified, do NOT re-investigate).** The user wanted "English
setting + full Hebrew at cold-boot + NO language switch." **Proven IMPOSSIBLE** by 3 parallel
deep-scan agents: the font-atlas glyph BREADTH at cold-boot is decided by the active language's
CLASS inside the **PROTECTED/packed `Anno1800.exe`** (320 MB writable `.text1`, entry in `.xtls`,
~12 KB `.reloc`), not in any editable data. CJK language (Korean/JP/CN/TW) → engine forces a
BROAD/dynamic atlas that preloads Hebrew; English/LTR → NARROW static atlas, omits Hebrew. **No
data lever exists** — PHXLF per-language records are byte-identical CJK-vs-English except name+font
GUID; the PHXFT KIND flag is per-FONT and flipping it 0→1 already gave "????" AND is logically
refuted (Korean→Meta(flag0) STILL boots broad → breadth follows LANGUAGE, not font); properties.xml
`<Languages>` has only audio/locale fields; no charset/glyph-preload config anywhere. Static exe
patch ~10% (packed) → dead. The only two physically-possible end states: **(A) Korean slot** = full
Hebrew cold-boot, no switch, but menu label "한국어" + live CEF web panels (mod.io browser, news
ticker) show Korean; **(B) English slot** = English menu + English web content, full Hebrew only
AFTER one in-game language toggle/launch (a live re-init fires the broad dynamic re-bake). Live
web/news content follows TextLanguage and CANNOT be decoupled by a mod.

**User chose (B) — English + one toggle/launch.** `engine.ini` TextLanguage="English",
AudioLanguage="English". The shipped mod fills ALL 5 slots (chinese/taiwanese/japanese/korean/
english) with the Hebrew + 2,595 English-fallback GUIDs → 100% coverage (no "????" untranslated
leak on any slot), so a downloader can use EITHER path (readme documents both). `build_phxlf`
(Korean→Meta) kept (harmless on English; gives narrow Latin if toggling via Korean). Rebuilt +
verified 2026-06-22: 56,400 Hebrew + 2,595 EN-fallback = 58,995 GUID overrides, **0 real token
mismatches** (23 flagged are correct `SublineText="…"` attr translations — Enbesa/Kashta DLC
sublines; stored LOGICAL inside the atomic tag → may render mirror in that DLC, ~0.04%, minor
follow-up), 16 Hebrew-injected fonts, 4 PHXLF. **Follow-ups:** user confirms (B) in-game (launch
English → toggle language once → full Hebrew); `npx wrangler deploy` for the slug; restore the 189
mod.io mods when done testing (rename `C:\Users\Public\mod.io\4169\mods_DISABLED_hebrew_test\` →
`…\mods\`, game closed). Memory [[anno1800-groundwork-go]].

## Grand Theft Auto V (Legacy) Hebrew — FULL translation SHIPPED + OpenIV-free launcher install PROVEN (2026-06-26)

Full Hebrew for GTA V Legacy (`F:\Games\Grand Theft Auto V Legacy`), deployed via the
OpenIV **mods** folder (real game-file edits trip `ERR_GEN_INVALID` anti-tamper — mods/
is the only safe path). Memory [[gtav-groundwork-go]] + [[parallel-agent-translation-handoff]].

### Engine / format (cracked)
- **Text = GXT2** files inside RPF7 archives. `magic 0x52504637` (reads "7FPR"/"2TXG"),
  UTF-8 NUL-terminated, **joaat(label)** keys, entries sorted ascending. **NEVER dedup** —
  the loader derives each string's length from `offset[i+1]-offset[i]` (contiguous in hash
  order); a shared offset → garbage length → `ERR_MEM_EMBEDDEDALLOC_ALLOC`. Codec:
  `games/gtav/work/gtav_gxt2.py` (`read_gxt2`/`write_gxt2`/`visual_line`, self-tested).
- **No Arabic locale** (all shipped locales LTR) → AC2/Anno-class: **hijack the English
  (American) slot + store Hebrew VISUAL** (pre-reversed; engine does no bidi for an LTR
  locale). `visual_line` reverses each Hebrew run, flips run order, keeps Latin/digits/
  `~tokens~`/`<tags>` forward, handles the maqaf boundary, splits on `~n~`/newlines so a
  multi-line paragraph keeps line order. User sets in-game Settings → Language = **American**.
- **Text layers (load order, from OpenIV.log):** `update2:/x64/data/lang/american_rel.rpf`
  = the REAL base table (69,209 keys) → `update:/x64/patch/.../american_rel.rpf` = patch
  delta (351). The x64b base (23,136) is SHADOWED. We write the full Hebrew into **update2's
  american_rel** (loads once as base → no story-load hang) — mods-redirectable → no anti-tamper.
- **Fonts** already render Hebrew once injected: `font_lib_efigs.gfx`/`_pc.gfx` (Scaleform UI)
  + `font_lib_web.gfx` (in-game browser). `work/font_add_hebrew.py` adds 27 glyphs
  (U+05D0–05EA) to every DefineCompactedFont face (FFdec swf2xml→inject→xml2swf).

### Full translation — COMPLETE (91,480 strings, 100% of the dialogue/subtitle pool)
- **Scope:** 610 `american_rel.rpf` gxt2 = 278,749 entries / 197,223 unique. Reused 49,521 UI
  translations (exact-EN match) + skipped ~51,835 codes/labels → **91,551 NEW** mission/dialogue
  strings. Done by sequential Google/Antigravity (Gemini) agents ([[delegate-all-translation]]).
- **Continuous-loop handoff (`games/gtav/agent_handoff_full/`)** — the per-file chunk flow made
  agents stop+report; switched to the proven `get_batch.py`/`merge_batch.py` loop
  ([[parallel-agent-translation-handoff]]): `get_batch.py` writes the next ~1500 untranslated to
  `current_batch.json`; agent fills Hebrew in place; `merge_batch.py` validates+merges to
  `hebrew.json`; repeat until "All done!". Bigger batch = fewer tool-calls/line → agent covers
  more before its per-turn cap. **Parallel-safe mode** `get_batch.py <slot> <nslots>` partitions
  by **stable `md5(en)%nslots`** → N agents never collide; each merges to its own
  `hebrew_<slot>.json`. The build reads `hebrew.json` + every `hebrew_*.json`.
- **⚠️ Anti-cheat gate (critical):** an agent faked "All done!" by filling hard keys with the
  English original (`{k:k}`). Caught by a post-sweep (re-queued 1,492 prose entries) +
  `merge_batch.py` now **REJECTS no-Hebrew on real prose** (≥2 lowercase words; names/codes/labels
  may stay English). Always independently sweep `hebrew.json` for no-Hebrew-prose after any "done"
  claim — never trust the agent's own completion (GoWR lesson). Verified final: 0 faked prose.
- **User-directed text fixes (2026-06-26):** `EXIT`→**"צא"** (80 exit-family entries; contextual
  "Exit to Roof"=יציאה לגג left — grammatically a noun there) + unified "Story Mode"
  **"מצב סיפור"→"מצב עלילה"** everywhere (0 old left, matches the dialogue usage). Applied to
  `reuse_he.json` (backup `.bak_exitstory`) → rebuilt → republished.

### Build + publish
- **`work/build_full_gxt2.py [--oiv]`** — reads `reuse_he.json`+`hebrew.json`, `strip_gloss`
  (drops agent-added Latin "(English)" glosses, 22.5k) + `visual_line` all 610 gxt2 (round-trip-
  guarded; 165,093 Hebrew / 278,749, rest = intentional English codes/names), writes a **token-
  deviation report** (47 unique, all benign `~s~` color-reset; 0 dropped content placeholders),
  and assembles `gtav_hebrew_FULLTEXT.oiv` + `gtav_restore_FULLTEXT.oiv` (all 610 → update2's
  american_rel + 3 Hebrew fonts; restore = **byte-exact vanilla, FILE-LEVEL `<add>` so other
  users' mods in the same RPF are untouched** — the user's explicit requirement; never deletes an
  archive). OIVs copied to the game folder for testing.
- **Published `pack_and_release.py`** → GitHub `nehorayc04/gtav-hebrew-mods` release
  **v1.0.0-beta.2** (scope=full) = `gtav_hebrew.zip` (sha `b5dfaeed…`, 11,705,868 B, both OIVs +
  Hebrew readme + manifest). Supabase `games`(version/download_url/changelog) + `mod_version_history`
  current → 1.0.0-beta.2; website shows GTA V as a free UI/full beta (download_url → GitHub
  directly, **no Worker slug needed**). show_on_launcher=false (needs OpenIV — until the writer
  below ships). Re-release = re-pack + `gh release upload v1.0.0-beta.2 --clobber` + PATCH Supabase
  sha/size.

### OpenIV-free launcher auto-install — `tools/rpf7_writer.py` BUILT + PROVEN
Goal: the launcher installs the mod itself, exactly like OpenIV (read-modify-write the mods-folder
RPF), **without OpenIV and without harming other mods in the same RPF**. Two parts:
1. **The loader** — `dinput8.dll` proxy + an ASI loader (`OpenIV.asi` / open-source Ultimate ASI
   Loader) makes the game read `mods\update\update2.rpf` instead of the real one. The launcher
   BUNDLES these (no OpenIV). Already present in the user's game folder.
2. **The writer** — `games/gtav/tools/rpf7_writer.py` (pure Python, OPEN RPF7 read-modify-write).
   **Format cracked from the LIVE archive:** file entry = u64[`NameOffset`(0:16) | `FileSize`-
   compressed(16:40, 24-bit) | `OffsetBlocks`(40:64, 24-bit)] + u32 `FileUncompressedSize` + u32
   flags; **`FileSize==0` ⇒ stored RAW, real length in `FileUncompressedSize`** (why the >16-bit-
   addressable nested `american_rel.rpf` first read as 0); **compression = RAW DEFLATE
   `zlib wbits=-15`** — `deflate()` @level 9 reproduces OpenIV's stored `global.gxt2`
   **BYTE-IDENTICAL** (1,813,502 comp / 4,878,946 raw). `serialize_open_rpf` re-assigns entry
   indices by BFS (each dir's children contiguous) + 512-aligns data. **PROVEN end-to-end** on the
   real 463 MB `mods\update\update2.rpf`: parsed root (2185 entries) → nested `american_rel.rpf`
   (csize=0 raw, 610 gxt2) → replaced 1 gxt2 (deflate) → re-serialized → **all 609 OTHER files
   byte-exact, 0 mismatch = the "don't harm other mods" guarantee proven**. (The live nested
   `global.gxt2` already inflates to our Hebrew — the user's OpenIV install IS the latest build.)
- **The HARD/uncertain part (format + other-mod preservation) is DONE.** Remaining = assembly:
  (1) `install_gtav_mod.py` — apply all 610 gxt2 + fonts via read-modify-write to
  `mods\update2.rpf`/`update.rpf` (re-embed the nested american_rel RAW, re-serialize the 463 MB
  parent — same proven code path); (2) bundle the ASI loader; (3) in-game test of a writer-produced
  archive (user's to confirm); (4) launcher RPC + GTA card/UI.
- **⛔ Bootstrap gap (honest):** a 100%-clean install (no `mods` folder) needs the folder created
  from the **NG-encrypted** vanilla — Legacy-2025 rotated the NG keys (uncrackable, only OpenIV
  has them; `0/101` keys + `0/272` tables found in `GTA5.exe` while `PC_AES_KEY_HASH` matched,
  proving the search works). So read-modify-write (Path A) only serves users who already have a
  mods folder. For clean installs → a from-scratch OPEN **DLC pack** the writer builds (small RPF,
  no vanilla needed, doesn't touch update2) — earlier DLC attempt story-hung; needs the load-order/
  metadata right. NG decrypt is needed ONLY to read MORE vanilla strings (the 89 DLC packs) — NOT
  for deploy.

### Launcher install — easiest-path UX DESIGN (2026-06-26, user spec) — two scenarios

The user wants the **easiest possible** in-launcher install with the user's existing mods NEVER
harmed. Mapped to what the cracked tooling can actually do:

- **Scenario A — user already mods GTA (a `mods\` folder exists + a loader is connected).** This is
  the PROVEN, fully-deliverable path. Detection signals (in the detected game root): `mods\` dir
  present (`mods\update\update2.rpf`, `mods\update\update.rpf`) AND the ASI loader wired
  (`dinput8.dll` proxy in the game root). The launcher **read-modify-writes** the user's existing
  `mods\update\update2.rpf` (swap the nested `american_rel.rpf` gxt2 → Hebrew) + `mods\update\
  update.rpf` (Hebrew fonts) via `rpf7_writer.py` — **every OTHER file/mod in those RPFs stays
  byte-exact** (proven). **No OpenIV needed for this** (the launcher does the RPF surgery itself;
  bundle the loader so even a "mods folder exists but `dinput8.dll` absent" sub-case can be
  *connected* by the launcher dropping the bundled `dinput8.dll`+Ultimate-ASI-Loader). Message:
  "המערכת נבנית מבלי לפגוע במודים שכבר התקנת — נוגעים רק בקבצי התרגום." → **after the initial
  mods-folder setup, OpenIV is never needed again.**
- **Scenario C — 100% clean install (no `mods\` folder, no OpenIV).** The user's "Option 2" (launcher
  creates `mods\` + copies ~X GB so it's self-contained, no OpenIV) is **BLOCKED**, and the message
  must say so honestly: GTA Legacy-2025 **rotated the NG encryption keys**, so the launcher cannot
  read/decrypt the vanilla `update2.rpf` to build an OPEN `mods\update\update2.rpf` from scratch
  (only OpenIV holds the keys). So a clean install needs **OpenIV ONCE** to create the mods-folder
  override (its "copy to mods folder" / decrypt step); thereafter the launcher takes over forever
  (Scenario A). The bundled ASI loader removes OpenIV from the *loading* path, but NOT from the
  one-time *creation* of the decrypted mods RPF. (The only no-OpenIV-ever route is the unsolved
  from-scratch OPEN **DLC pack** — story-hung; a future task.) Short message: "אין תיקיית mods —
  ל-GTA המעודכן צריך את OpenIV פעם אחת ליצירת תיקיית המודים (בגלל הצפנת המשחק); אחר כך התוכנה מנהלת
  הכול לבד."

**Pre-install BACKUP (user requirement).** Before any RPF write, copy the touched archives
(`mods\update\update2.rpf` + `mods\update\update.rpf` — they may hold the user's OTHER mods) to
`~/.translation_manager/mod_backups/gtav/<timestamp>/`, then build the new RPF in a temp file and
`os.replace` it in (atomic — a failed build never corrupts the live RPF). **Remove/restore** =
copy the backup back (instant, current). State + version tracked in
`~/.translation_manager/mod_cache/gtav/state.json`. This guarantees the user's edits are always
recoverable.

**Launcher SETTING (user requirement).** A per-launcher toggle (in `launcher_prefs` +
SettingsView) — "GTA V: השתמש בתיקיית ה-mods שלי (OpenIV מחובר)" — lets the user force Scenario-A
behavior (edit my existing mods folder) vs the self-contained mode, instead of relying only on
auto-detection.

**Wiring (native-applier pattern, like SM2/WD2/Anno):** `translation_manager/gtav_mod.py` (NEW —
wraps `rpf7_writer.py`: detect scenario, backup, apply all 610 gxt2 + 3 fonts, revert) + bundled
payloads/loader under `translation_manager/assets/gtav/` (rides the existing
`('translation_manager','translation_manager')` spec datas entry — no spec change) + RPC trio
`get/install/remove_gtav_mod` (+ `_run_gtav_install`) in `main_eel.py` + bridge slots + `eel.ts`
`GtavState`/calls + an `isGtav` branch in `GameDetailPanel` (scenario message + install/remove +
progress) + the prefs toggle. GTA `games` row → `show_on_launcher=true` once shipped.

**ENGINE BUILT + PROVEN (2026-06-26) — `games/gtav/work/install_gtav_mod.py`.** The end-to-end
OpenIV-free apply/revert is done and offline-verified against the user's LIVE mods folder: it
read-modify-writes `mods\update\update2.rpf` (swap all **610 Hebrew gxt2** in the nested
`american_rel.rpf`) + `mods\update\update.rpf` (swap the **3 Hebrew Scaleform fonts** in the nested
`scaleform_generic.rpf`/`scaleform_platform_pc.rpf`), preserving **every other file byte-exact**
(`--test` verifier: update2 610 gxt2 in + all others exact; update.rpf 3 fonts in + all others
exact). Backup-before-write (the 2 RPFs → `~/.translation_manager/mod_backups/gtav/`) + build-in-temp
+ `os.replace` atomic + `revert()` restores. Preserves per-file storage mode; nested rpfs re-embedded
raw. `--test` (non-destructive) / `--apply` / `--revert` / `--status`.
- **⚠️ CRITICAL `rpf7_writer.py` FIX (2026-06-26): resource files were being CORRUPTED.** The file
  entry's data offset is **23 bits**, and **bit 63 is a RESOURCE flag** (`.ymt`/`.ydr`/… ,
  `flags=0x20000000`) — the writer read it as a 24-bit offset, so every resource file got an offset
  +0x800000 blocks too high → **empty data → 88 corrupted files in update.rpf** (update2 has no
  resource files, which is why it round-tripped perfectly and masked the bug). Fix: parse
  `offblocks=(packed>>40)&0x7FFFFF` + `_res=(packed>>63)&1`; serialize repacks with the 23-bit mask
  + `(_res<<63)`. Backward-compatible (binary files have bit 63 = 0). After the fix: update.rpf
  round-trips **0 mismatches** (1,082 files), writer self-test ALL PASS. **Lesson: any RPF7
  read-modify-write MUST preserve the resource flag, or it silently bricks every resource file.**
- **LAUNCHER INTEGRATION SHIPPED (2026-06-26, dev_build 5, BUILD_ID `20260626150937`, release
  id=42).** GTA V is now a one-click install in the launcher:
  - `translation_manager/gtav_mod.py` (wraps the engine) + `translation_manager/gtav_rpf7.py`
    (vendored FIXED writer) + bundled `assets/gtav/gtav_he_payload.zip` (610 gxt2 + 3 fonts, 6 MB —
    rides the existing spec datas entry, no spec change). Verified the launcher applier reproduces
    the proven result (610 gxt2 + 3 fonts, all other files byte-exact) reading payloads from the zip.
  - `main_eel`: `_GTAV_ID` + RPC trio `get_gtav_mod_state`/`install_gtav_mod`/`remove_gtav_mod`
    (+ `_run_gtav_install`/`_run_gtav_remove` background workers — both heavy multi-GB, progress-
    streamed) + `_mod_state`/`_enrich_game_row` GTA branches. Bridge slots (install/remove on the
    QThreadPool). `eel.ts` `GtavState` + 3 calls. `GameDetailPanel` `isGtav` branch keyed on
    `scenario`: **ready** (mods+loader → install/remove) / **mods_no_loader** (install + loader
    warn) / **clean** (no install — a GUIDED "OpenIV once" message + an openiv.com link) /
    **no_game**. Installed-note: "won't harm other mods + set in-game Language = American".
  - **PAID — ₪53 (2026-06-26).** GTA is a paid mod (`games.price_cents=5300`, availability
    available, status beta, show_on_launcher+show_on_website true). The website BuyButton is
    data-driven (`showOnLauncher && priceCents>0` → PayPal → `user_purchases` → `owns_game`). The
    LAUNCHER native applier was gated to match the download-mod DRM: `get_gtav_mod_state` returns
    `owned`(=`auth_owns_game` for price>0)+`priceCents`; `install_gtav_mod`+`_run_gtav_install` block
    when not owned; the `isGtav` UI shows "רכישה — 53 ₪" (reuses `handlePurchase`/`openPurchasePage`
    + the burst poller, now GTA-aware) when unowned and the install button only when owned (in the
    `clean` scenario the buy button + OpenIV guidance show together). The GitHub OIV zip stays
    publicly downloadable (CP2077 model: payment buys launcher convenience). Re-published the mod
    (`gh release upload v1.0.0-beta.2 --clobber`, FULL release, current sha `b5dfaeed…`).
  - **SHIPPED 2026-06-26 (dev_build 6, BUILD_ID `20260626154958`, release id=43):** rebuilt → ISCC →
    publish. Verified `/api/launcher` buildId == baked; `/api/games` gtav priceCents 5300.
  - **SURGICAL REMOVE (2026-06-26, dev_build 7, BUILD_ID `20260626162111`, release id=44).** "הסרת
    התרגום" no longer restores the (possibly STALE) install-time full backup — which would wipe any
    mod the user added AFTER installing. Instead it **swaps the 610 gxt2 + 3 fonts back to VANILLA
    English/original-fonts IN PLACE** (the same read-modify-write as install, with a 2nd bundled
    `gtav_vanilla_payload.zip` = 610 vanilla gxt2 + 3 vanilla fonts), so every OTHER file — including
    the user's newer mods — is preserved byte-exact. Verified offline against the live RPFs (610→vanilla,
    `global.gxt2`==vanilla payload, all others byte-exact). `gtav_mod.revert()` is now the surgical
    swap; the old full-backup restore is a SEPARATE explicitly-warned action `restore_gtav_backup`
    (RPC + bridge slot + `restoreGtavBackup` + a small "שחזור גיבוי מלא (לפני ההתקנה) ⚠" link in the
    GTA panel, shown only when a backup exists) — "⚠ discards changes since install". `get_gtav_mod_state`
    gained `vanillaAvailable` + `backupAvailable`. The install-time backup is still taken (safety +
    the separate restore), just not used by the normal remove.
  - **NOT done (deferred, low value):** an explicit Settings toggle to FORCE OpenIV-connected mode —
    the `scenario` auto-detection (mods folder + `dinput8.dll`) already drives the right path. The
    OIV loader (`OpenIV.asi`) is NOT bundled (OpenIV's closed component) — clean installs stay
    GUIDED; the launcher only does the RPF surgery once an OPEN `mods\` folder exists.
  - **User's to confirm in-game:** the launcher-produced archives boot + render Hebrew (the engine
    is byte-faithful to the user's already-working OIV install; revert restores the pristine backup).
  Memory [[gtav-groundwork-go]].

### DLC-pack route — researched, does NOT escape the clean-install wall (2026-06-26)

Investigated whether the from-scratch OPEN **DLC pack** (`work/build_dlc_oiv.py` +
`release/gtav_hebrew_DLC.oiv` — a `dlcpacks:/hebrew/` with `setup2.xml`/`content.xml`/
`dlctext.meta`+`hasGlobalTextFile` auto-loading `americandlc.rpf\global.gxt2`) can give a CLEAN
install Hebrew WITHOUT OpenIV. **Conclusion: NO — same NG-key wall.** Two facts settle it:
- ✅ **`rpf7_writer.serialize_open_rpf` CAN build an RPF from scratch** (its `__main__` self-test
  builds a tree from nothing → serialize → re-parse identical). So the launcher *can* build the
  `dlc.rpf` (setup2/content/dlctext + nested `americandlc.rpf\global.gxt2`) with no vanilla, no
  OpenIV.
- ⛔ **But a DLC MUST be registered in `dlclist.xml`, which lives inside `update.rpf`**
  (community-confirmed: every dlclist tool edits `update.rpf` *or* `mods\update\update.rpf`; there
  is NO registration-free path for an asset/text DLC). A clean install's `update.rpf` is
  **NG-encrypted** → the launcher can't edit it → can't register the DLC. So the DLC route ALSO
  needs OpenIV (or an already-OPEN `mods\update\update.rpf`) once. **It does not solve Option 2.**
- **Where the DLC route IS useful:** for a **Scenario-A** user (already has `mods\update\update.rpf`
  OPEN), the launcher can build `dlc.rpf` + edit the mods-side `dlclist.xml` with `rpf7_writer` —
  a **cleaner** deploy than the 463 MB `update2` rewrite (small RPF, Rockstar's own pattern, never
  touches `update2`/base text). Gated only on the **story-mode-hang** fix, which needs in-game
  iteration (the prior `build_dlc_oiv.py` "research-backed fix" — `setup2.xml` shows `order=100`
  though its docstring says 255; suspected load-order/`COMPAT_PACK` issue — was never confirmed to
  boot). **Verdict: the clean-install-no-OpenIV goal is fundamentally blocked by GTA's 2025 NG-key
  rotation (registration always touches an encrypted RPF); only the cleaner Scenario-A deploy is on
  the table, and it's in-game-test-gated.**

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

## 8. RTL / font gotchas (cohtml / Coherent GameFace engines, e.g. SM2)
- cohtml **ignores CSS `direction`/`dir`** — honors only Unicode **bidi control chars**. Base RTL
  comes from the UI container; use **`&rlm;` anchors matched to the Arabic** positions.
- **NEVER use RLE/PDF (U+202B/U+202C)** if the shipped font lacks those glyphs → tofu box. If the
  font renders U+200F/U+200E (RLM/LRM) as visible marks, **empty those glyphs** in the TTF. The
  game's native Arabic font keeps them zero-width — match that.

## 9. Per-game add checklist
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

---

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

### Deploy gotcha — TWO Mods Libraries
Overstrike scans a `Mods Library/` folder. The machine had **two**: a `Downloads`
one and **`Game Lab/Marvel's Spider-Man 2/Mods Library/`** (the one the game
actually used, had a stale June-5 mod). After a rebuild, deploy `hebrew_full.modular`
to **both** and clear Overstrike's `Cache.json` + `"Suits Cache.json"` so it re-applies.
Find the live one with `find … -name hebrew_full.modular`.

### Translation QA (this session)
**100 corrections applied**: 77 from a multi-agent adversarial-verify Workflow
(review→verify pipeline) via `98_apply_qa_fixes.py` (token-safe) + 23 Talon-faction
fixes (`מלתעה`/fang → `טלון`; unified "drone" → `רחפן`). The remaining
`english_in_hebrew` items are intentional brand/acronym pass-throughs.

### Publish status (content-verified)
- GitHub release on `nehorayc04/spiderman2-hebrew-mods`, tag **`v1.0.0-beta.1`**
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

## License

See repository for license terms.

---

# Cyberpunk 2077 Hebrew Translation Pipeline

A second project sharing this directory — the standalone scripts that
extract, translate, and repack Cyberpunk 2077's onscreen text into
Hebrew. Not part of the launcher; runs locally against LM Studio.

## Current Status (2026-05-18)

**Onscreens translation — COMPLETE.** All 23,792 pending fields translated
via LM Studio (Gemma-2-27B), merged into `localization_translated.json`,
packed, and deployed.

### Deployed mod

| Property | Value |
|---|---|
| Path | `Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive` |
| Size | 9,216,000 bytes (9.2 MB) |
| MD5 | `91cf8c40302f645dbd265062a8aa0879` |
| Deployed | 2026-05-18 18:36:16 |

### Coverage in this build

| Section | Matched primary keys | femaleVariant updated | maleVariant updated |
|---|---|---|---|
| `onscreens.json` | 60,296 | 59,942 | 126 |
| `onscreens_final.json` | 60,296 | 59,944 | 126 |

→ ~120,138 Hebrew strings live via the Arabic-slot pipeline (up from the
~89k baseline on 2026-05-10).

### Activation

User must set Cyberpunk 2077 → Settings → Language → Interface = **العربية**
(Arabic), then restart the game. The Hebrew text routes through CDPR's
tested RTL/bidi pipeline (see "Arabic-slot approach" in earlier history
notes — putting Hebrew CR2W in `en-us/` crashes the engine).

## Working pipeline (replay any time)

End-to-end is `translate_queue_fast.py` → `fill_translations_from_queue.py
lm_output.json --rebuild`, which chains `rebuild_onscreens_and_pack.py`
through 7 steps:

1. Extract pristine Arabic CR2W skeleton from `lang_ar_text.archive`
2. Serialize CR2W → text JSON (WolvenKit `convert serialize`)
3. Apply Hebrew via `cp2077_apply_translations_to_wkit_json.py`
4. Deserialize text JSON → CR2W
5. Place CR2W into `<project>/source/archive/base/localization/ar-ar/onscreens/`
6. Pack with WolvenKit → `archive.archive`
7. Deploy → `<game>/archive/pc/mod/z_hebrew_translation.archive`

Total runtime: ~1.6 min (94s) on this machine.

**Precondition:** Cyberpunk 2077 must be closed (deploy target is overwritten).

## Throughput tuning (translate_queue_fast.py)

Patches applied 2026-05-17 — reduced error/translation ratio from 22%
to 0.1% over a full 23k-item run:

| Setting | Before | After |
|---|---|---|
| `DYN_MAX_WORDS` | 150 | 100 |
| `LONG_ITEM_CHAR_THRESHOLD` | (none) | 200 — items > 200 chars bypass batching, go straight to single-mode |
| Batch retries on 400 | 2 attempts × 2s sleep | 0 — instant fallback to per-item single-mode |
| `translate_one` retries on context-size | 3 × 2s sleep | 0 — `_is_context_error()` short-circuits the loop |

Sustained throughput on LM Studio (Gemma-2-27B, AMD RX 9070, 4 parallel
workers): **~13 items/min**. Total run for 23,792 items: ~31 hours.

The bottleneck is LM Studio inference, not Python. Process consumed
228 CPU-seconds in 16.5 hours of runtime — it's >99% idle waiting on
HTTP responses.

## Monitor stack

- `cp2077_monitor.bat` → `python -m progress_monitor --adapter cp2077 --tui`
- Adapter: `progress_monitor/adapters/cp2077.py` — parses the translator's
  log file directly, builds 3-stage snapshot (extraction / translation / packaging)
- Core: `progress_monitor/core.py` — pushes to website API every 15 min,
  refreshes TUI every 1.5s
- Bidi handling: `tui.py` `_LEGACY_CONSOLE` detection. On user's cmd.exe,
  `fix_rtl()` reverses Hebrew runs (their terminal doesn't run the bidi
  algorithm). Modern terminals (Windows Terminal, ConEmu, VS Code term)
  set env vars we sniff and skip the reversal.

### Cleanup-mode remap (2026-05-18)

When `translate_cleanup_all.py` runs (sub-thousand sweep against the
already-translated bulk), the adapter detects the `"Global queue:"` /
`"cleanup mode"` log markers and remaps the subset onto the global
scope before pushing/displaying:

- Constant: `CLEANUP_GLOBAL_TOTAL = 23792` in `cp2077.py`
- baseline    = CLEANUP_GLOBAL_TOTAL − cleanup_subset_size
- processed   = baseline + items_fixed_in_this_run
- total       = CLEANUP_GLOBAL_TOTAL

Without this remap the website progress bar snapped to "417/950" for
the cleanup-only subset, looking like project regression instead of
a 98% bulk + final-polish run. The TUI's stage-2 detail row shows both
numbers: "סה\"כ גלובלי: 23,792" + "תוקן עד כה: 23,259 (מהם 417 בריצה הזו)".

**Note:** changes to `cp2077.py` require a TUI restart — Python caches
the module on import. For an immediate one-shot push after editing:
`python -m progress_monitor --adapter cp2077 --once --no-tui`

## Key files

| File | Purpose |
|---|---|
| `translate_queue_fast.py` | Main translator — LM Studio queue runner with dynamic batching |
| `fix_missing_translations.log` | Monitor-watched log (DO NOT rename — adapter regex depends on it) |
| `lm_output.json` | Per-section output dict (`{section: [{primaryKey, femaleVariant, maleVariant}, ...]}`) |
| `missing_translations_queue.json` | Input queue (deduped pending items) |
| `fill_translations_from_queue.py` | Merges `lm_output.json` → `localization_translated.json`. With `--rebuild` chains the full pack+deploy |
| `rebuild_onscreens_and_pack.py` | 7-step WolvenKit chain (extract → serialize → apply → deserialize → place → pack → deploy) |
| `rebuild_subtitles_and_pack.py` | Surgical subtitle re-bake — reuses `cp2077_subtitle_batch.py`'s phase fns, re-bakes only the patched subtitle files (driven by `patch_615_report.json`), then pack+deploy |
| `cp2077_apply_translations_to_wkit_json.py` | Step 3 — applies Hebrew by primaryKey lookup |
| `patch_615_flagged.py` | Dynamic audit-driven cleanup — scans for foreign-script contamination (reuses `audit_translations.detect_scripts`, no 500-cap), re-translates from `localization_export.json`, writes `patch_615_report.json` |
| `cp2077_orchestrator.py` | Unattended final-pipeline driver — monitors subtitle batch → fresh audit → suspend rival LM clients (ctypes `NtSuspendProcess`) → `patch_615_flagged.py` → re-pack both. `--dry-run` supported |
| `progress_monitor/` | Universal monitor package (adapter-driven) |
| `cp2077_status_report.py` | Read-only completeness audit — categorizes every entry in `localization_translated.json` + `dlc_ep1_text.json` (UI / Story / NPCs / Devices / Items / RPG / Subtitles), classifies each as Hebrew / English / Arabic / blank / N-A, writes `cp2077_translation_status_report.txt`. English source: `localization_export.json` for onscreens (pk-matched), the subtitle `secondaryKey` for subtitles. DLC translation status via global stringId cross-check |
| `cp2077_consolidate_dlc.py` | One-time builder of `dlc_ep1_text.json` — consolidates the Phantom Liberty (ep1) localization that was extracted+serialized from `ep1/lang_en_text.archive`. Docstring carries the WolvenKit extract/serialize prereq commands |
| `dlc_ep1_text.json` | `source/resources/` — consolidated Phantom Liberty English text (716 sections: 2 onscreens + 714 subtitle files, 47,905 entries). Static game data; read by `cp2077_status_report.py` |
| `cp2077_qa_defects.py` | Shared 4-class defect detector (foreign-script / English-leak / missing / structural). `scan_all()` is the single source of truth for the QA sweep + watchdog; reuses `audit_translations.detect_scripts`, `cp2077_status_report.classify`, `cp2077_markup_translate.parse_slots`. Also holds the `qa.lock` write-coordination helpers |
| `cp2077_qa_sweep.py` | One-shot QA pass — audit→fix→re-audit loop (cap 5 + no-progress break). Re-translates flagged entries (plain via `patch_615_flagged.translate_clean`, markup via the slot model), gates each fix through `value_is_clean`, writes `qa_sweep_report.json` |
| `cp2077_qa_watchdog.py` | Persistent "castle guard" — every ~20 min re-audits + auto-fixes the JSON (never bakes/deploys). Writes `~/.translation_manager/cp2077_qa_status.json`; parks entries failing 3+ ticks in `qa_watchdog_giveup.json`. Run via `cp2077_qa_watchdog.bat` (auto-restart loop) |
| `cp2077_post_pipeline.py` | Master automation — finish translation → QA sweep → bake subtitles → bake onscreens+deploy → status report → launch watchdog. `--dry-run` / `--skip-qa` / `--full-subs` |

## QA / backup / watchdog automation (2026-05-20)

The post-translation pipeline is now fully automatic. `cp2077_post_pipeline.py`
chains: finish translation (`translate_cleanup_all.py --no-rebuild`) → QA sweep
→ bake subtitles → bake onscreens + deploy → status report → launch the QA
watchdog. Base game ONLY — the Phantom Liberty DLC is excluded everywhere.

- **QA sweep** scans EVERY line for foreign-script contamination, untranslated
  English mid-Hebrew, missing/blank, and broken markup; re-translates the
  flagged ones; loops audit→fix→re-audit until clean. Detection lives in
  `cp2077_qa_defects.py` so the sweep + watchdog flag identically.
- **English-leak heuristic** is "smart": a 2+ word run is flagged only when it
  carries a lowercase common English word (real prose); brand / product names
  ("Nokota Manufacturing", "Street Queen") are not flagged. Tuning against live
  data dropped false positives 1,874 → 175.
- **Backup-on-deploy**: `rebuild_onscreens_and_pack.py` (`step7_deploy`) and
  `cp2077_subtitle_batch.py` (`phase3_pack_deploy`) copy the current
  `z_hebrew_translation.archive` into
  `Cyberpunk 2077\archive\pc\mod_backups\<timestamp>\` before overwriting it
  (only that one archive — the menu/startup mods are untouched).
- **QA watchdog** runs forever; the monitor adapter surfaces it as a 4th stage
  "שלב 4 — בקרת איכות" from the `cp2077_qa_status.json` sidecar (a running TUI
  must be restarted once to pick up the adapter change).
- **markup translator fix**: `cp2077_markup_translate.py` now finalizes /
  logs / checkpoints each entry as it completes (was: silent until 100%), so
  the monitor tracks it live and a crash is resumable via `markup_done.json`.

## Phase 1 COMPLETE — base game deployed (2026-05-21)

Phase 1 (base-game completion + QA + deploy) finished and deployed.

- **Base game — 99.7%** (145,152 / 146,232 translatable lines in Hebrew; only
  390 untranslated — the irreducible damaged/truncated-source tail).
- Translated this session: 3,136 markup entries (`cp2077_markup_translate.py`)
  + 660 clean lines (`translate_cleanup_all.py`).
- **QA**: foreign-script contamination 287/290 stripped; English-word leaks
  141/161 fixed (20 borderline residual in `qa_sweep_report.json`).
- **Deployed**: `Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive`
  (9,170,944 bytes, 2026-05-21 09:48) — 702 re-baked subtitle CR2W + both
  onscreens CR2W. Old archives backed up under `archive\pc\mod_backups\<ts>\`.
- Phantom Liberty DLC untouched (38.8%) — separate task.

### Static mods merged into one archive (2026-05-21)

The two static mods — `z_hebrew_menu_name_patch.archive` (Settings>Language
label override, 18 locales) and `z_hebrew_startup_fix.archive` (Arabic intro
video swap) — were merged into a single **`z_hebrew_static.archive`** (~81 MB,
37 files: 36 onscreens CR2W + 1 bk2). Their game paths are disjoint, so the
merge is lossless — `merge_static_archives.py` extracts both, re-packs once,
backs the originals up to `mod_backups/static_merge_<ts>/`, and removes them.
The mod folder now holds exactly two archives: `z_hebrew_static.archive`
(static, rebuilt only when a build script reruns) + `z_hebrew_translation.archive`
(the live, re-baked translation mod — the only one backed up on every deploy).

### QA tooling — fixes made this session

- `cp2077_qa_defects.py` detector had false positives, all fixed: classify
  mis-flagged translated `<kiroshi>` entries (Hebrew lives in the tag attrs),
  naive `<`/`>` bracket counting, dev-junk (`IGNORE, TO BE DELETED`), and
  truncated-tag attribute leaks. Detection is now slot-aware.
- The english-leak fixer is 2-stage: whole-line re-fix (hallucination-guarded
  — rejects a result that drops <60% of the original Hebrew words), then a
  surgical fallback that translates each leaked fragment WITH the full line as
  context and substitutes it in place (surrounding Hebrew stays byte-identical).
- Foreign-script cleanup = direct `strip_foreign()` (deterministic; no LM).
- `cp2077_qa_sweep.py` gained `--only <kinds>`; `qa.atomic_write_json` retries
  through transient Windows file locks (`os.replace` WinError 5).
- `cp2077_status_report.classify` HEB check now reads the raw value, not the
  tag-stripped core — so translated `<kiroshi>`/`<mothertongue>` entries count
  correctly (this is why base-game jumped 98.0% → 99.7% on the same data).
- `bake_monitor_bridge.py` (NEW) — mirrors `rebuild_subtitles.log` progress
  into `subtitle_batch.log` in the adapter's format, so `cp2077_monitor.py`
  (and the website/launcher) track a `rebuild_subtitles_and_pack.py` bake live.

## Base-game polish + publish (2026-05-22)

Autonomous run after the user reported in-game blanks. A full 4-class
`cp2077_qa_defects.scan_all()` found 221 defects; addressed as follows:

- **QA sweep** (`cp2077_qa_sweep.py`) — 11 genuine fixes (real text + laughs).
- **Vocalizations** — `cp2077_fix_vocalizations.py` (NEW): the LM cannot
  "translate" interjections, so a deterministic 14-form map transliterates
  `Hmm…/Haha./Heh…` → `המממ…/חה חה./חה…`. **70 entries** fixed, no LM.
- **Markup translator** — 5 more `<kiroshi>` TR slots translated.
- **Corrupted markup** — `cp2077_fix_corrupted_markup.py` (NEW): repairs
  entries whose `<kiroshi>`/`<mothertongue>` tag was destroyed by an old
  non-markup-aware pass (`<kiroshi`→`קירושי`, foreign `o=` translated,
  structure collapsed). Rebuilds femaleVariant from the English skeleton in
  `secondaryKey`; falls back to the clean English skeleton when the LM result
  is not clean. **11 garbage entries** restored to valid markup.
- The remaining ~140 residual are correctly left: codes / serials / acronyms
  (`NC484…`, `VSync`, `ISO 100`, `8ug8ear`), CDPR dev-junk (`[db_db]…`,
  `chickentest`), and the truncated-source tail the markup parser rejects.

**Status after the run — base game 99.8%** (145,221 / 146,232 lines; 322
untranslated = the irreducible code/acronym/damaged tail). Re-baked 66
subtitle sections + both onscreens, backed up + deployed
`z_hebrew_translation.archive`.

**Published** `pack_cp2077_mod.py 2026.05.21.1` — GitHub release
`v2026.05.21.1` on `nehorayc04/cp2077-hebrew-mods` (zip + manifest, sha256
`ebbc63d2…`). Verified: the release is `latest`, the Cloudflare Worker
`/cp2077-hebrew/manifest` serves version `2026.05.21.1`.

The **QA watchdog** is running (`cp2077_qa_watchdog.py`, 1200 s patrol).
A boot-persistent Scheduled Task could not be registered (needs elevation) —
to make it survive reboots, run as admin: Task Scheduler → "At log on" →
`cp2077_qa_watchdog.bat` (the .bat documents this).

### Known issue — 273 dropped markup wrappers (future task)

`is_markup(secondaryKey) and not is_markup(femaleVariant)` finds **284**
entries where an old translation pass dropped the `<kiroshi>`/`<mothertongue>`
wrapper. **11 were garbage** (fixed above). The other **273 are type-A**: a
fluent Hebrew sentence with merely the foreign-audio wrapper gone — they read
correctly in-game (not broken sentences), just lack the Kiroshi/mothertongue
styling. Deferred — re-wrapping 273 means re-translating + re-baking 273
sections; worth its own dedicated pass, not a rushed addition.

### Out of scope — the user's two screenshots

- Journal **"Phantom Liberty"** blank — DLC content (`ep1/` / `Story-ep1-*`),
  not in the base-game pipeline → Phase 2.
- Empty **Contacts list** — no base-translation-data cause (0 structural
  defects; contact-name strings are translated). Needs in-game diagnosis
  (test with the mod disabled).

## Deep English-tail audit + manual hand-fixes (2026-05-23)

End-to-end forensic re-audit covering source JSON, **the baked archive
itself**, and the game folder. Two new artefacts shipped:

- `cp2077_deep_english_audit.py` — 5-layer auditor. Layer 1 reuses
  `cp2077_qa_defects.scan_all()` for source defects; Layer 2 is new — it
  extracts `z_hebrew_translation.archive` + `z_hebrew_static.archive` via
  WolvenKit, serializes every CR2W (~3,085 files), and diffs source vs.
  baked per `(section, primaryKey)`. Layer 3 catches dropped markup
  wrappers (`is_markup(secondaryKey) && !is_markup(femaleVariant)`). Layer
  4 is a defensive walk of small text files in the game folder. Layer 5
  categorises every finding into 12 buckets A..L. Cached extracts /
  serializations cut subsequent runs from ~3 h to ~30 s. Reports:
  `cp2077_deep_english_audit.txt` (human) + `.json` (machine).
- `apply_deep_audit_translations.py` + `apply_leak_fixes.py` — one-shot
  hand patches (no LM), back the spine file up and write atomically.

**Key plumbing fixes for the auditor:**
- Subtitle CR2W keys entries by `stringId`, onscreens by `primaryKey` —
  `_index_by_pk()` accepts both.
- Static archive (`z_hebrew_static.archive`) covers 18 locales (NOT ar-ar —
  that's the main mod). Verification targets the specific menu-label entry
  (pk=49601 / sk endswith `UI-Settings-Language-Arabic`) and asserts its
  femaleVariant ∈ {Hebrew, עברית, Ivrit}. The earlier "any Hebrew char in
  the file" heuristic was a false positive — the patch deliberately writes
  the Latin word "Hebrew" everywhere for cross-locale discoverability.
- `Story-ep1-…` / `…_EP1_…` entries leaked into the base source from older
  passes — they're DLC content and the base archive's Arabic skeleton has
  no slot for them. Filtered out of bake-drift; routed to category K
  (`translated_but_not_in_base_bake`) as informational.

**Findings + actions (base-game audit, JSON-only — no re-bake yet):**

| Bucket | Count | Verdict |
|---|---:|---|
| A. fixable_missing | **5 → 0** | All 5 hand-translated (see `apply_deep_audit_translations.py`) — tutorial text (Hazards/Focus), GPS shard title, `[Say nothing]` dialogue option. Source for pk=77919/87898 was truncated in `localization_export.json`; the FULL text came from a live extract of `lang_en_text.archive` (434 / 563 chars). |
| B. fixable_english_leak | **17 → 4** | 13 hand-fixed; 4 kept (intentional brand names — `"Drugs are bad"` website, `Us Cracks`/`Off the Leash` band+song, three song titles in `mq023_03_street_vendor.json`). Bonus: 4 Thai `เรื่อง:` (subject) labels in two emails fixed to `נושא:` — that's why H dropped 2→0 with no separate pass. |
| C. foreign_voiceset | 3 | `<kiroshi l="rus/jpn/mex"…>` content — by design. |
| D. code_or_acronym | 82 | HDR10, ISO 100, NC484, Mk.31, mmHg — by design. |
| E. dev_junk | 30 | `[db_db]…`, `chickentest`, `IGNORE` — CDPR dev refs. |
| F. dropped_markup_wrapper | 276 | Type-A: Hebrew is intact, only the `<kiroshi>` wrapper was lost. Deferred (cosmetic — no in-game English). |
| G. bake_drift | **5** | Real drift — the 5 manual A-translations are in the source JSON but the baked archive still has the OLD English/Arabic text. Cleared by re-bake. |
| H. foreign_script | **2 → 0** | The two Thai-script leaks were inside the entries hand-fixed in B; resolved as a side-effect. |
| I. loose_game_text | 0 | Clean. |
| J. structural_markup | 0 | Clean. |
| K. translated_but_not_in_base_bake | 1,305 | DLC overflow — base source JSON has Hebrew for these ep1 / Q307 / Barghest pks but the base game's Arabic skeleton has no slot for them. Will ship via the (separate) DLC archive — not a base-game drift. |
| L. orphan_or_other | 0 | Clean. |

**Re-bake required to make the 18 hand-fixes visible in-game.** Affected
sections (6 total):
- `onscreens/onscreens.json` (entries: 6269, 11534, 77919, 87898, 95358)
- `onscreens/onscreens_final.json` (6269, 11521, 11534, 82710, 83878,
  84326, 86817, 87898 (mirror via single pack), 95358)
- `subtitles/quest/mq028/mq028_02_park.json` (1975…)
- `subtitles/quest/q103/q103_07_ghost_town_drive.json` (1665…)
- `subtitles/open_world/voicesets/gang_scv_m_11_rus_40_mt.json` (1898…)
- `subtitles/open_world/voicesets/gang_vdb_f_03_car_30_mt.json` (1949…)

Two backups of the spine file:
`localization_translated.json.bak.deep_audit_a.20260523_132934` (pre-A)
and `…bak.deep_audit_b.20260523_140906` (pre-B). Both can be reverted
file-copy.

## Phantom Liberty DLC translation — SHIPPED v2026.05.24 (2026-05-24)

**Status: SHIPPED.** Full Phase 2 — Phantom Liberty Hebrew translation deployed
as a separate `z_hebrew_dlc.archive` (2.7 MB) sitting alongside the existing
base + static mods.

### Timeline (2026-05-23 → 2026-05-24)

| Stage | Duration | Result |
|---|---|---|
| Translation (`cp2077_dlc_translate.py` via supervisor) | 21.3 h | 30,104 → 325 untranslated (99.3% Hebrew) |
| QA fix (`cp2077_dlc_qa_fix.py`) | ~3 h | 941 / 1,063 defects fixed (88%) — 122 LM-unfixable tail accepted |
| Bake (`rebuild_dlc_and_pack.py`) | 4.0 h | 715 / 716 CR2W baked (1 had no Hebrew), 47,435 fv + 47,434 mv applied, 0 failures |
| Publish | ~1 min | GitHub release v2026.05.24 + Cloudflare Worker auto-served |

### Final deployment

| Mod archive | Size | Coverage |
|---|---:|---|
| `z_hebrew_translation.archive` | 9.2 MB | base-game (99.8 %) |
| `z_hebrew_static.archive` | 81 MB | Settings>Language label + Arabic intro video (18 locales) |
| **`z_hebrew_dlc.archive` (NEW)** | **2.7 MB** | **Phantom Liberty (99.3 %)** |

GitHub: https://github.com/nehorayc04/cp2077-hebrew-mods/releases/tag/v2026.05.24
SHA-256 of `cyberpunk_hebrew_translation.zip` (92.7 MB):
`15e7b3688495cb67c66bb1ba777019619402d9a22d97bbe2af9964049bac5636`

### Key tooling built this session

- `cp2077_dlc_qa_fix.py` (NEW) — targeted DLC defect fixer with 4 kinds:
  GARBLED (auto-pad Hebrew↔Latin script seams — deterministic, instant),
  UNTRANSLATED (LM retry strict→lenient), DOUBLE_LANG (surgical English-run
  re-translation with context splice), LENGTH_ANOMALY (LM re-translate).
  **Process order matters**: sort defects so GARBLED runs first — otherwise
  slow LM calls block the worker pool and instant fixes wait for hours.
- `_dlc_audit_scout.py` (NEW) — pre-fix defect inventory. Distinguishes
  real defects from heuristic noise (e.g. translated brand names like
  `BARGHEST → ברגסט` are CORRECT and must not be flagged).
- `auto_pad_script_seams()` — deterministic single-space insertion at every
  Hebrew↔Latin abut outside tags. Turned 651 GARBLED entries (like
  `'וreed'`) into clean `'ו reed'` in seconds, no LM calls.

### Known issues to file separately

- `cp2077_status_report.py` still calculates DLC coverage as 38.8 % via
  cross-reference with base `localization_translated.json` — it never
  loads `dlc_ep1_translated.json` directly. The real archive carries
  99.3 % Hebrew (verified by direct walk of the source JSON). Needs a
  small refactor to detect and load the DLC spine file.
- LM Studio runtime still hangs occasionally into `GENERATING` state with
  zero output for tens of minutes — same root cause as the 2026-05-23 hang.
  Recovery: `lms unload --all && lms load gemma-2-27b-it -y --gpu max
  --context-length 8192 --parallel 4`. Already documented in the LM
  Studio hang-recovery section above.
- 122 DLC entries remain LM-unfixable (long messy English, mixed-case
  identifiers, rare Unicode). They are flagged in `dlc_qa_fix_report.json`
  and can be hand-fixed later if specific ones surface in-game.

---

## In-game defects polish + subtitle re-bake (2026-05-24)

After v1.0.1 shipped, a 10-minute play-test surfaced three deterministic defect
patterns (screenshots): Spanish "cuerpo a cuerpo" leaking from English "melee"
tooltips; the protagonist's name `V` transliterated to `וי` in subtitles + UI;
Creole `kamyonèt` left untranslated mid-Hebrew Voodoo-Boys dialogue. Per the
standing rule **"the protagonist's name is always `V` in Latin"** all three are
search-and-replace — no LM needed.

`fix_ingame_defects.py` (NEW) — read-only deterministic pass over the spine JSONs:

| Pattern | EN match | HE replacement | Base hits | DLC hits |
|---|---|---|---:|---:|
| Spanish melee leak | `\bcuerpo[- ]a[- ]cuerpo\b` (case-insens.) | `פנים אל פנים` | **74** | 0 |
| V → V (Latin) | standalone Hebrew `וי` between word boundaries, when EN source has standalone `V` AND no negative context (`VIP`, `AV`, `V8`, `V/T`, `V-for-Victory`, `VTOL`, `VHS`, `VPN`, `V12`) | `V` | **220** | **209** |
| Creole truck word | `\bkamyon(?:èt|et)?\b` | `קמיון` / `קמיונט` (preserves Voodoo-Boys flavor; clean RTL flow) | **10** | 0 |

**Total: 513 spine edits**, atomic-written via `tqf._atomic_write_json`.

Two sequential bakes from the patched spines:

1. **Onscreens** (`rebuild_onscreens_and_pack.py`) — 67s, completed 20:06:54.
   Archive size unchanged (9,170,944 bytes — character-level swaps stay
   inside the CR2W slot).
2. **Subtitles** (`rebuild_subtitles_and_pack.py --sections-file
   affected_base_subtitle_sections.txt`, 571 sections containing V/kamyon
   hits) — **3 h 45 m wall (13,522 s)**, completed 23:52:29.
   fv=34,760 · mv=34,693 applied, **571/571 OK, zero failures**. Old archive
   backed up to `mod_backups/20260524_235229/` before overwrite.

Same `z_hebrew_translation.archive` (9,170,944 bytes) redeployed at
2026-05-24 23:52:29 — base game now ships all 530 in-game defect fixes.

**DLC re-bake** (222 V→V DLC entries patched in `dlc_ep1_translated.json`) —
**DEFERRED**. The DLC bake is ~4 h and the in-game DLC impact is limited; the
fixes will ride with the next DLC release cycle, not as a hotfix.

**v1.0.2 publish status: NOT SHIPPED.** Per user instruction, the release tag +
GitHub upload + Cloudflare manifest update will only run when the user
explicitly authorizes (`"publish 1.0.2"`). Until then the corrected archive is
local-only on the user's machine.

---

## Cross-validation audit infrastructure (2026-05-24)

Goal: independent LQA review of the shipped Hebrew translation — surface
stylistic literalisms, missed Cyberpunk register, and hidden truncations —
**without ever modifying the source JSONs**. The polished v1.0.1 spines are
sacred to this pipeline.

Three scripts, all in the project root:

| File | Role |
|---|---|
| `cross_model_watchdog.py` | Original LM Studio + Llama 3.1 8B watchdog at `http://10.0.0.5:1234`. Replaced after the 8B judge produced ~100% false positives on Hebrew parentheticals etc. Prompt was tightened mid-iteration to 4 mechanical defect categories (truncation / corruption / missing / structural); kept as a fallback. |
| `get_next_audit_batch.py` | Read-only batch fetcher + flag-logger + dashboard renderer. Subcommands: `next [--size N]`, `flag --file <json>`, `dashboard`. Flat row index across base+DLC (~238,556 rows total). Writes only the sidecars below. |
| `continuous_audit_loop.py` | Autonomous LM Studio judge driver (`qwen2.5-32b-instruct` @ `http://10.0.0.5:1234`, 90 s timeout). Subprocess-wraps `get_next_audit_batch.py`, judges each row, persists flags. Built to grind unattended for hours. |

**Sidecar state files** (all in project root, never source paths):

| File | Purpose |
|---|---|
| `cross_audit_checkpoint.json` | `{last_index, processed, flagged, base_done, dlc_done, ...}` |
| `cross_audit_flags.json` | JSONL append-only (one record per line, O(1) append regardless of size — filename keeps `.json` extension per spec) |
| `cross_audit_dashboard.md` | Overwritten with each new batch — live progress + last-5 flags table |
| `cross_audit_batch.json` | Transient: last batch payload between fetch and judge |

**Safety & Autonomy protocol** baked into `continuous_audit_loop.py`:

| Rule | Implementation |
|---|---|
| READ-ONLY source | `PROTECTED_FILES` frozenset of the 4 source JSONs (base/DLC × translated/English). `_safe_write_check()` runs before every write. Violation → `_critical_safety_stop()` writes `CRITICAL_SAFETY_STOP` marker to stderr + exits code 99. |
| Connection self-heal | LM Studio unreachable (preflight, judge call, or subprocess fetch) → 30 s pause, **infinite retry** until response. |
| Bad-response self-heal | Empty / malformed / non-connection error → 30 s pause, up to 3 retries, then skip row. |
| Batch crash recovery | Uncaught exception in row loop → flush partial flags, 30 s pause, restart same in-memory batch from row 0, up to `MAX_BATCH_RESTARTS` (5). Then move on. |
| 4xx client error | Log + skip row (retrying a malformed call doesn't help). |
| Ctrl+C | `_sleep_interruptible` checks `_STOP` every 1 s, so SIGINT exits within ~1 s instead of waiting out a 30 s backoff. |

**Tightened judge prompt (`JUDGE_SYSTEM`):** Lead LQA Editor, three axes
(naturalness / Cyberpunk register / integrity), explicit anti-flag whitelist
(single-word translations, transliterations, parentheticals like
`מיכל דלק (מתפוצץ)`, V kept as Latin). `BE CONCISE — default PASS, only flag
real bugs or stilted phrasing.` Output strictly one of `PASS` or
`FAIL: <critique>; SUGGEST: <better Hebrew>`.

**First batch (Claude-as-judge, 2026-05-24 22:01)** — 10 rows from
`onscreens/onscreens.json` (pk 40–53), 3 stylistic flags:
- pk 49 `BREAKING NEWS → חדשות חמות!` → suggest `מבזק!` (native Israeli ticker)
- pk 50 `Cyberpsycho on rampage! → סייברפסיכו בטירוף!` → suggest `סייברפסיכו משתולל!` (verb-match for "rampage")
- pk 52 `Politician killed by frenzied mob! → ...המון משוגע!` → suggest `...המון מתפרע!` (idiomatic mob descriptor), or active voice `המון פרוע רצח פוליטיקאי!`

**Permission change**: `permissions.defaultMode = "bypassPermissions"` written
to `.claude/settings.local.json` (project-only scope). Existing 50+ `allow`
rules preserved verbatim. Takes effect on next Claude Code launch.

### Audit watchdog false-kills — ROOT-CAUSED + FIXED (2026-06-11)

The audit had been getting killed by its own hang-watchdog **2-6×/hour for
12+ hours** (`audit_watchdog.log`: "HANG DETECTED — checkpoint age > threshold").
A warm LM-Studio reload did NOT fix it (reboot either). A 7-agent adversarial
workflow + direct latency measurement found the **real** root cause, deeper than
"LM is slow":

- **Measured throughput**: qwen2.5-32b on the RX 9070 spills to RAM
  (`DEVICE=Local`) → **~2.46 gen tok/s + ~35 prefill tok/s**. So `max_tokens=300`
  alone is up to ~122 s of generation, and the largest real audit rows
  (max **~3,400 prompt tokens** — a few dozen untranslated DLC onscreens entries
  like pk=85427) add ~97 s of prefill.
- **The actual kill mechanism**: the watchdog keys off
  `cross_audit_checkpoint.json` **mtime**, which `get_next_audit_batch.py` only
  rewrites at batch FETCH / flag-FLUSH — and `flush_flags()` returns early on a
  zero-flag (all-PASS) batch. So **~53 % of batches never refreshed the mtime
  mid-flight**; the watchdog measured *whole-batch wall-time*, not a true hang,
  and killed slow-but-healthy batches with zero stuck rows. The long-FAIL-critique
  timeouts were a *secondary* contributor.

**Fix package (all verified end-to-end, zero kills after restart):**
1. **Per-row mtime heartbeat** — `heartbeat_checkpoint()` (`os.utime(CHECKPOINT_FILE)`)
   called after every judged row in the loop (`continuous_audit_loop.py` ~line 745).
   THE fix: decouples "slow" from "hung" — a genuinely stuck `judge_row()` blocks
   the heartbeat too, so a *true* 900 s stall still trips the watchdog while a slow
   batch keeps the mtime fresh. mtime-only (content/`last_index` still advances per
   batch, so restart-resume is unchanged). Verified: mtime advanced +53 s mid-batch
   while `last_index` held.
2. `max_tokens` **300 → 160** (line ~558) — caps worst gen ~122 s → ~65 s.
   Truncation-safe: the PASS/FAIL verdict is the FIRST token and `critic_feedback`
   is stored as an opaque string (nothing splits on `FAIL:`/`SUGGEST:`), so a
   chopped critique never misclassifies a row — only cosmetically shortens the
   suggestion on <1 % of flags.
3. `REQUEST_TIMEOUT` **90 → 180 s** (line 125) — lets the largest legit rows
   (~162 s = 97 s prefill + 65 s gen) COMPLETE on the first attempt instead of
   timing out → 3 wasted retries. Measured: a full 160-token row = ~82 s.
4. `MAX_BAD_RESPONSE_RETRIES` **3 → 2**, `RETRY_SLEEP` **30 → 15 s** (lines 126-129)
   — caps a truly-stuck row at 180+15+180 = 375 s (< 900 s) instead of 510 s+.
5. `--batch-size` **20 → 8** (`start_audit.bat`) — content checkpoint advances
   ~2.5× more often (smoother website push, less re-work on a true-hang restart).
6. **LM Studio reloaded `--parallel 4 → 1`** — the audit is 100 % serial, so 4
   slots wasted KV cache AND split context to 8192/4 = **2048 per slot**, too small
   for the >2048-token rows (they'd truncate/error). `parallel 1` gives each serial
   request the full 8192 ctx + all compute. **After any reboot, reload with:**
   `lms load qwen2.5-32b-instruct -y --gpu max --context-length 8192 --parallel 1`.
7. `AUDIT_HANG_SECONDS=900` in `start_audit.bat` (kept) — now coherent with the
   above; was the earlier (insufficient-alone) attempt.

**Data → website is healthy**: `monitor_supervisor.bat` runs
`progress_monitor --adapter audit`, pushing `phase=qa processed/total` every 60 s
to `https://hebrew-translation-hub.com/api/admin/progress` (verified live, no HTTP
errors). Checkpoint at handoff: **processed 118,456 / 238,556 (base only), 8,314
flagged**.

### Local-32B audit quality MEASURED — it is poor (2026-06-11)

Blind calibration: Opus 4.8 (via the Claude Code subscription) re-judged 1,000
rows qwen had already rated (400 of its FAILs + 600 of its PASSes), stratified +
weighted to the population. Result — the local qwen-32B audit is **low quality,
not just slow**: **precision ~32 %** (≈68 % of its ~8,600 flags are noise) and
**recall ~23 %** (it misses ~3 of every 4 real defects). Estimated **~12,000 real
defects** in the corpus; qwen surfaced ~2,700 (buried under ~5,800 false flags)
and **missed ~9,200** (incl. ~5,800 OBJECTIVE integrity bugs — foreign-script like
Vietnamese `bất tử`, `V's Apartment`→`דירת ו`, German garbage, truncations — that
it passed). A cheap-screener cascade is therefore **empirically unsafe** (a 23 %-
recall screen never escalates the misses). The genuine quality floor for nuanced
Hebrew LQA is **Claude Sonnet 4.6** (Haiku 4.5 / Gemini Flash over-flag, repeating
the documented Llama-3.1-8B disaster); cheapest full-corpus path = Sonnet 4.6 via
the **Batches API ≈ $145**, async, same-day. (Gemini free-tier rotation does NOT
help — limits are per-PROJECT, not per-key.)

**Audit STOPPED 2026-06-11** and the flag set cleaned **deterministically (no AI,
token-cheap)** after the subscription session limit was hit. Two reusable scripts
added under `universal/`:
- **`classify_flags.py`** — NO-AI false-positive filter over `cross_audit_flags.json`:
  KEEP only on an objective machine-detectable defect (foreign script / control
  char / placeholder-or-tag present in EN but missing from HE); else DROP. The 760
  Opus verdicts already produced (`c:\tmp\flag_cleanup_verdicts.json`, keyed by flag
  line index) override the rule. Output: **`cross_audit_flags_clean.json` (512 real
  defects: 354 Opus + 158 rule)**, `cross_audit_flags_dropped.json` (8,156 noise),
  `needs_ai_review.jsonl` (5,275 prose flags for a later subjective AI pass).
- **`smart_filter_queue.py`** — NO-AI source pre-filter (reuses
  `get_next_audit_batch.build_corpus`): skips rows that need no AI (file-paths/IDs,
  bare code-tags, numbers/symbols-only, EN==HE proper nouns) and writes the rest to
  **`ai_work_queue.jsonl`**. Run: 238,556 → skipped 26,703 → **211,853 queued**.

### NO-AI deterministic defect sweep + fix (2026-06-11)

Going deeper without AI, two more scripts under `games/cyberpunk2077/`:
- **`deep_scan_deterministic.py`** — full-corpus deterministic scan reusing the
  project's tested `cp2077_qa_defects.scan_all` (slot-aware 4-class: foreign /
  english_leak / missing / structural, incl. niqqud via `detect_scripts`) PLUS an
  inline V→וי detector. Found **503 real defects with zero AI** (qwen had missed
  many): foreign 84 · v_transliteration 78 · english_leak 52 · missing 289
  (base 188 / DLC 315) → `universal/deterministic_defects.jsonl`.
- **`apply_deterministic_fixes.py`** — surgically fixes ONLY the deterministically
  fixable kinds: `foreign`→`strip_foreign()`, `v_transliteration`→replace standalone
  `וי` with Latin `V`. Acquires the project QA lock, **backs up each spine file**
  (`*.bak.detfix.<ts>`), atomic-writes, then re-verifies. Run: **135 fixes applied**
  (57 foreign-strip + 78 V→V), **VERIFY 0 residual**. The 27 unfixed "foreign" were
  chars INSIDE tags (legit game data — correctly untouched). `missing` (289) +
  `english_leak` (52) are left for the AI pass (they need translation, not cleanup).
  Spine backups: `localization_translated.json.bak.detfix.20260611_155400` (+ DLC).

### Subtitle speaker-label colon — player name MUST stay "וי" (2026-06-11)

In-game RTL bug: the subtitle **speaker label** (engine renders `[name]:[line]`) put
the colon on the WRONG side for the player — `V:` rendered broken — while Hebrew NPC
names (`שוטר NCPD:`) rendered correctly. Root cause + fix, after a long trace:
- The dialogue string carries **no speaker** (engine prepends it). The speaker name
  resolves from the **player base character record**, NOT the menu/FPP displayName.
  The decisive entry is **`onscreens.json` pk=48683**, secondaryKey
  `Story-base-characters-entities-player-player_base_rec…_displayName`. (Dead ends with
  NO effect: pk=6820 `player_menu_fpp` displayName, pk=6821 empty-sk, and invisible
  bidi marks RLM U+200F / RLE U+202B — the engine ignores marks; only a real Hebrew
  name flips the colon to the correct RTL side.)
- **`apply_deterministic_fixes.py`'s V→וי pass had changed pk 48683 "וי"→"V"**, which
  broke the colon (the old working mod had "וי"). Reverting pk 48683 to **"וי"** + an
  onscreens re-bake FIXED it (user-confirmed in-game).
- **GUARD added** to `apply_deterministic_fixes.py`: the V→וי pass now SKIPS any entry
  whose whole value is exactly "וי" (a bare speaker/character NAME) — only substring
  "וי" inside real dialogue becomes "V". **Do NOT remove this guard.** Rule refinement:
  "protagonist name is Latin V" applies to V **inside dialogue/prose**, NOT to a
  standalone speaker-NAME entry (there "וי" is required for correct RTL colon).
- **Follow-up (not done):** the EP1/DLC player display-names `onscreens.json` pk=92467
  & 92468 (`…player_{ma,wa}_tpp_ep1…_displayName`) hold the GARBLED value `"48683VVVV"`
  — Phantom Liberty player speaker labels will be broken until set to "וי" + re-baked.

WolvenKit CLI 8.17.4 was (re)installed this session to
`…AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe` (lost in a PC reset) —
`WolvenKit.Console-8.17.4.zip` from GitHub releases; .NET 7/8 present. The bake scripts'
`APPLY_SCRIPT` path was also fixed (post-reorg it pointed at the repo root instead of
`games/cyberpunk2077/`).

### ROOT CAUSE of all blank UI lines — Arabic maleVariant (2026-06-11)

The in-game "blank rows" (quest objectives rendering `.( )`, input-hint action
labels, etc.) were NOT missing translations and NOT fonts (both theories
disproven by direct evidence): **the player is male V → the engine resolves
`maleVariant`; our spine fills only `femaleVariant`, so ~7,400 onscreens
entries kept the Arabic skeleton's `maleVariant`; the Heebo fonts carry no
Arabic glyphs → only ASCII (parens/dots) rendered.** Decisive proof: baked
pk=39166 ("Talk to Jackie.") had fv=`דבר עם ג'קי.` mv=`تحدث إلى (جاكي).` —
the on-screen "( )" was literally the Arabic parens.

- **Fix:** `cp2077_apply_translations_to_wkit_json.py` now backfills
  `maleVariant = femaleVariant` when our translation lacks mv and the
  skeleton mv is non-empty. mv-updated jumped 126 → **7,471** on the next
  bake. The subtitle (`cp2077_subtitle_batch.py` L228-233) and DLC
  (`rebuild_dlc_and_pack.py` L152-156) appliers ALREADY had this backfill —
  onscreens was the only broken path. Do not remove it from any of the three.
- Also fixed in the spine the same evening: melee "פנים אל פנים"→"קרב מגע"
  (75 melee-context entries; user request), "Dodge/Dash"→"חמק/זנק" (was
  "חמק/קו" — "Dash" mistranslated as the punctuation dash), lottery
  "Body-count Lottery"→"הגרלת ספירת הגופות" + `"Vigilante"` quotes removed
  (base 17 + DLC 6), subtitle "punching bag"→"שק אגרוף" (q001+mq025,
  user-confirmed in-game).
- ~75 onscreens entries still carry Arabic femaleVariant = the untranslated
  tail (no Hebrew in spine) — queue to the local model later.
- **DLC archive (May 24) still lacks:** the lottery fixes, the pk 92467/92468
  `48683VVVV` repair, the DLC-side spine updates — needs a DLC re-bake (~4h).

### Overnight autonomous polish + final defect sweep (2026-06-13)

A fully-autonomous local-model (gemma-4-31b-it, loaded ALONE `--parallel 1`)
finishing run, then a deterministic verification sweep — base game brought to a
clean floor and re-deployed. All passes use the standard backup + QA-lock +
atomic-write spine discipline; every bake re-deploys
`z_hebrew_translation.archive`.

- **Arabic tail (`tail_translate.py`, NEW)** — the ~75 onscreens entries with an
  empty `femaleVariant` in the spine (so the Arabic skeleton showed in-game).
  gemma-4 translated 69/75 (gate: has Hebrew, tags preserved, no Arabic/niqqud);
  written to both `onscreens.json` + `onscreens_final.json`, onscreens re-baked.
- **Mixed-script corrective round (`corrective_fix.py`, NEW)** — Claude
  personally re-reviewed gemma's earlier "ok" verdicts on 189 Hebrew+Latin
  glued tokens and CONFIRMED the over-judging: ~half were genuinely-broken
  half-transliterations (גילherme, לQuadra, מטלFX, מילוGost). A DIRECTIVE prompt
  (force ONE script: person→Hebrew translit, brand→full English w/ maqaf,
  scream→all Hebrew) + a hard **seam gate** (`[א-ת][A-Za-z]|[A-Za-z][א-ת]`
  rejects any still-glued result) fixed **173/189**; 131 touched subtitle
  sections + onscreens re-baked.
- **Comprehensive anomaly scanners (NEW, reusable, game-agnostic-ish):**
  - `scan_word_anomalies.py` — per-word illogical-token detector across the
    whole corpus (mixed_script / hebrew_digit / single Hebrew|Latin letter /
    punct-in-word / niqqud / repeated / control / double-space / **hebrew_too_long**
    (≥22-letter run) / **long_latin_run** (5+ word Latin inside Hebrew)). Strips
    tags/`{ph}`/literal `\n` first; one ordered review file + JSONL.
  - `scan_language_report.py` — full-corpus English/foreign scan (unicodedata
    FOREIGN class catches ALL non-Latin/non-Hebrew letters): english_in_hebrew /
    english_only / foreign_script / corrupt_midword.
  - `glossary_consistency.py` — 52 named terms, reports those with >1 Hebrew
    rendering (`unify_glossary.py` already renamed 1,342 base + 379 DLC; 19 of 52
    still have context-dependent variants).
- **Final cleanup (`final_cleanup.py`, NEW)** — root-cause-aware: re-translates a
  foreign-leftover **only when the ENGLISH SOURCE is plain English** (`en_is_plain`,
  ≥85% Latin) — so it NEVER touches the intentional foreign-flavor gang dialogue
  (Valentinos Spanish / Voodoo Boys Creole, where the EN source is itself foreign).
  Fixed 11 of the residual seams+leaks.
- **Deterministic brand fix (`det_brand_fix.py`, NEW — no LM)** — the 5 stubborn
  UI brand names gemma kept gluing, mapped to their correct English form:
  מטלFX→**MetalFX**, קריסטלCoat™→**CrystalCoat™**, דוםלuncher→**Doomlauncher**,
  4XדרYves→**4xDRIVE**, EZאסטייטס→**EZ Estates**, plus subtitle ירו בbastards→
  **ירו בממזרים**. Whole-value substring map, instant, re-baked.

**Final verified state (re-scan after all passes, 238,556 rows):**
`mixed_script_word` 16→**0**, `corrupt_midword` 4→**0** — every broken
Hebrew↔Latin seam ELIMINATED. The remaining categories are all
**intentional-by-design, NOT defects**: `single_hebrew_letter` 2,518 (Hebrew
prefixes ו/ב/ל/ה before an icon/tag), `single_latin_letter` 1,157 (X/M button
labels, initials), `english_in_hebrew` ~11k (brand/vehicle/weapon/acronym
passthrough — the documented tuned-heuristic policy), `long_latin_run` 113 +
`english_only` 21 + `foreign_script` 15 (low-visibility foreign-flavor voiceset
/ gang lines + correct English brand names — left on purpose). Deployed:
`z_hebrew_translation.archive` 8,716,288 B + `z_hebrew_dlc.archive` 2.69 MB +
`z_hebrew_static.archive` 81 MB. Website QA bar tracked the whole run
(`chain_progress.py`, wall-time-weighted % to `/api/admin/progress`).

---

## Phantom Liberty DLC translation — IN PROGRESS (2026-05-22)

Full Phase 2 — the entire Phantom Liberty DLC to Hebrew, same Arabic-slot
trick, shipped as a separate `z_hebrew_dlc.archive`.

Base fixes shipped first (release **v2026.05.22**): save-screen playtime units
`UI-Labels-Units-Hours/Minutes` reverted `ה/מ` → `H/M` (`cp2077_fix_units.py`);
"Time Remaining" `rămaining` Latin-extended contamination fixed.

DLC pipeline — new files:
- `cp2077_dlc_build.py` — builds `dlc_ep1_translated.json` from
  `dlc_ep1_text.json`; pre-fills 8,233 entries reusable from the base
  translation by exact English match. LM workload: **40,531** new entries.
- `cp2077_dlc_translate.py` — DLC translator; reuses `translate_queue_fast`'s
  LM core (plain) + `cp2077_markup_translate`'s slot model (markup).
  `dlc_ep1_translated.json` IS the resumable state. **Running since
  2026-05-22 05:30 — ~50h** (40,212 plain + 301 markup). NOTE: it imports
  both tqf and mk, which each swap `sys.stdout`; `_KEEP_STREAMS` pins the
  orphaned wrappers so the shared buffer is never closed mid-run.
- `rebuild_dlc_and_pack.py` — DLC bake: extract `ep1/lang_ar_text.archive` →
  serialize → apply Hebrew (onscreens by `primaryKey`, subtitles by
  `stringId`) → deserialize → place at `ep1/localization/ar-ar/...` → pack →
  `z_hebrew_dlc.archive` → deploy. Verified: compiles, extract OK (717
  files), `section_to_relpath` mapping confirmed.

Section-key → CR2W path: `ep1/<rest>` → `ep1/localization/ar-ar/<rest>`.
DLC onscreens entries key on `primaryKey`; subtitle entries on `stringId`.

Remaining after translation completes: DLC QA sweep → `rebuild_dlc_and_pack.py`
→ deploy → `pack_cp2077_mod.py` (add `z_hebrew_dlc.archive` to `_MOD_FILES`)
→ status report → relaunch QA watchdog.

- `cp2077_dlc_run.py` (NEW) — crash-resilient supervisor: re-launches
  `cp2077_dlc_translate.py` after any abnormal exit (a one-off exit 127 was
  seen). Stops when the translator exits 0 (collected work done) or makes no
  progress. Run this, not the translator directly.

**LM Studio "0 GPUs detected" / "No runtimes found" after update (2026-06-07):**
machine is the Ryzen 5 5600X + **AMD RX 9070 (RDNA4, gfx1201)**. After an
in-place LM Studio 0.4.16 update the GUI Hardware panel showed `0 GPUs
detected`, VRAM 0, and `lms runtime ls` → `No runtimes found` even though the
backend folders were all on disk. Root cause: the previously-selected runtime
was **ROCm**, whose survey fails on RDNA4 Windows (`No hip devices found!`), AND
the 0.4.x decoupled-runtime/engine-index was left unregistered. Key facts:
- For RX 9070 / RDNA4 use **Vulkan**, NOT ROCm — ROCm "No hip devices found" on
  RDNA4 Windows; `vulkaninfo` sees the card fine. Vulkan survey then reports the
  9070 with ~15.92 GiB VRAM.
- `lms` CLI is only an RPC client to the LM Studio daemon. `lms runtime get`
  downloads to disk but only the **running GUI** finalizes/registers the pack —
  so a CLI-only download leaves `lms runtime select` failing with "No installed
  runtime extensions found matching". Don't fix this from the CLI alone.
- The "Enable LM Studio Engine Protocol" Developer toggle is a buggy beta in
  0.4.14–0.4.16 — keep it OFF.
- **Fix that worked (user, 2026-06-07):** back up models + saved profiles, wipe
  the `~/.lmstudio` runtime/config folders, relaunch the GUI so it rebuilds a
  clean engine index, restore the backups. Lighter fallback: quit, delete only
  `~/.lmstudio/.internal/internal-engine-index.json` (derived cache, rebuilt on
  next launch), relaunch. After the reset Vulkan was auto-selected and the GPU
  detected. Do NOT force-kill the GUI from a shell and try to relaunch it —
  agent shells can't launch the GUI into the user's desktop session.

**LM Studio hang recovery (seen 2026-05-23):** after the user updated LM Studio
mid-run, the engine settled into a `GENERATING` state that produced zero
output for tens of minutes (a 60 s curl to `/v1/chat/completions` for "Hello"
returned nothing). The fix: `lms unload --all && lms load gemma-2-27b-it -y
--gpu max --context-length 2048 --parallel 4` — a clean unload+reload clears
the stuck runtime. Sanity test post-reload with a 30 s curl; healthy is
~1.5 s for a short prompt, ~9 s for a 50-token reply.

**LM Studio context-per-slot — the real bottleneck (2026-05-23):** LM Studio
divides `--context-length` per parallel slot. With `--ctx 2048 --parallel 4`
each slot gets ~512 tokens, and a 12-item batch needs ~1,200 tokens
(SYSTEM_PROMPT ~430 + header ~25 + 12 items ~300 + `MAX_TOKENS=512`). Serial
batches still succeed (one slot uses the full 2048), but concurrent batches
all fail with `400 — Context size has been exceeded` and fall back to
single-mode → throughput collapses to ~0.3 entries/min.

**The fix:** `lms load gemma-2-27b-it -y --gpu max --context-length 8192
--parallel 4` — Gemma-2's native context. Each slot gets 2,048 tokens,
batches fit comfortably, all 4 workers run in parallel without errors.
Measured 2026-05-23 with `_lm_client_test.py` (the SDK-path verifier that
imports `translate_queue_fast` and runs its real `translate_batch` 4 ways):
serial 194.8 s, concurrent 117.2 s, **speedup 1.66×, 24.6 items/min**, zero
context errors. The earlier `_lm_parallel_test.py` urllib test reported
2.51× — that was misleading because its prompts were tiny (50 input + 120
output ≈ 170 tokens per slot, well under the 512 budget); use
`_lm_client_test.py` for any future tuning since it exercises the real
translator's prompt sizes.

If `lms ps` ever shows `DEVICE: Local` plus partial GPU offload (i.e. some
layers on CPU), drop to `--context-length 4096 --parallel 4` and set
`MAX_TOKENS = 256` in `translate_queue_fast.py` — see the plan file
`C:\Users\nc528\.claude\plans\hashed-meandering-stearns.md` for the full
fallback ladder.

- `cp2077_dlc_translate.py` markup pass parallelized to 4 workers; both tqf
  and mk swap `sys.stdout` at import → `_KEEP_STREAMS` pins the orphaned
  wrappers so the shared buffer is never closed mid-run.
- Monitor fix — `progress_monitor/adapters/cp2077.py`: the cleanup-mode remap
  (caps the total at 23,792) now triggers ONLY on the literal `cleanup mode`
  marker, not the generic `Global queue:` line — otherwise the DLC's ~40k
  queue was falsely capped. `cp2077_monitor.bat` now shows the DLC translation
  live (stage 2: processed / ~40,116).

## Translation status snapshot (2026-05-20)

`cp2077_status_report.py` baseline:

- **Base game — 97.5%** (141,343 / 144,996 translatable lines in Hebrew;
  3,653 remain). Onscreens 99%+ in every category. The remaining base gap is
  mostly subtitles: Open World **92.1%** (2,132 lines, concentrated in
  `open_world/voicesets/` — foreign-language gang `<kiroshi>` audio cues) and
  Quests 98.3% (765 lines). Zero Arabic-skeleton contamination.
- **Phantom Liberty DLC — 38.2% headline, but misleading.** The DLC ships in a
  separate `ep1/` archive not in the pipeline. DLC onscreens (97.6%) + overlay
  subtitles (97.8%) are "covered" only because they re-use base stringIds that
  are already translated. The **genuinely-new DLC dialogue** (subtitles
  quest 16,945 + open_world 5,904 + media 260) is **~0.7% translated —
  ~22,673 lines pending**, all in `ep1/subtitles/quest/q3xx/`.
- **Grand total base+DLC — 85.4%** (155,579 / 182,242). 26,663 lines remain,
  86% of which is untranslated Phantom Liberty dialogue.

Re-run `cp2077_status_report.py` any time for a fresh count — never re-pack blind.
Reports: `cp2077_translation_status_report.txt` (English) +
`דוח מצב תרגום Cyberpunk 2077 (בסיס + DLC).txt` (Hebrew).

## Prompt hardening (2026-05-18)

Both `translate_queue_fast.py` and `translate_cleanup_all.py` now use a
unified, stricter `SYSTEM_PROMPT`:

- "Professional Cyberpunk 2077 localizer" preamble with Night City tone
- Hard rule: Hebrew + English alphabets only (explicit list of banned
  scripts: Cyrillic, Arabic, Thai, Greek, CJK, Hangul, …)
- Hard rule: NEVER use Niqqud vowel-points
- Tag preservation extended (`<Rich color="...">`, `{VALUE,...}`)
- Glossary extended: Shard → שארד, Edgerunner → אדג'ראנר

The cleanup script also pre-filters items leading with control bytes
0x01–0x05 followed by Rich-text/JSON markers (CR2W framework
placeholders) — `_looks_like_framework_placeholder()`. These can't be
translated cleanly and used to flood the SKIP feed.

## Quality audit (2026-05-18, post-bulk)

`audit_translations.py` scans `localization_translated.json` for
foreign-script contamination in narrative Hebrew. Strips passthrough
tags first (`<kiroshi l="jpn" o="..."/>`, `<Rich color="...">`,
`{VALUE,...}`) so legitimate game-data text inside markup doesn't
count as a bad translation.

Results across 220,485 variants (3,085 sections):

| Stat | Value |
|---|---|
| With Hebrew chars | 214,615 |
| Real foreign-script leaks | **615 (0.28%)** |
| Top scripts | Hangul 268 · Greek 101 · Cyrillic 88 · Katakana 78 · Devanagari 35 · Arabic 31 · Hiragana 20 · Han CJK 8 · Thai 4 · Armenian 3 |
| Niqqud violations | 0 |

Report file: `audit_translations_report.txt` (per-script samples, capped
at 500 per script). These entries can be purged + retranslated via the
cleanup script once the user decides.

## Final-pipeline orchestrator (2026-05-20)

`cp2077_orchestrator.py` automates the post-subtitle-batch stages, unattended:

0. Admin check (`ctypes ... IsUserAnAdmin`) — warns if not elevated.
1. Polls every 60 s until `cp2077_subtitle_batch.py` exits; aborts if the
   process vanishes below 95 % (crash guard).
2. Re-runs `audit_translations.py` for a fresh count. If 0 flagged → stops.
   Else: auto-detects rival LM Studio clients (`steam_translator.py`,
   `translate_queue_fast.py`, `translate_cleanup_all.py`), **suspends** them
   via `ntdll.NtSuspendProcess` (ctypes — no psutil), runs
   `patch_615_flagged.py`, **resumes** them in a `finally` block.
3. If `patch_615` fixed > 0 entries → runs `rebuild_subtitles_and_pack.py`
   then `rebuild_onscreens_and_pack.py`.

Key correction vs. the original ask: suspending a translator client frees
LM Studio's **inference queue**, NOT VRAM (LM Studio holds the model). The
"615" in `patch_615_flagged.py` is historical — the script patches whatever
the *current* audit flags (the original 615 was already purged; audit is
currently 0-flagged).

Verified 2026-05-20: all 3 scripts `py_compile` clean; `patch_615 --dry-run`
→ 0 flagged; orchestrator `--dry-run` → detects the running batch + stage
flow; ctypes suspend/resume smoke test PASSED.

## ⚠ DEPLOY TARGET — critical (resolved 2026-05-20)

**The game the user launches/tests is the project's own staging copy:**
`C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077`
**NOT** `C:\Games\Cyberpunk 2077` (a separate install the user never plays).

All deploy scripts (`cp2077_subtitle_batch.py`, `rebuild_onscreens_and_pack.py`,
`rebuild_subtitles_and_pack.py`, `fix_*`) must have `GAME` pointed at the
staging path. A 2026-05-19 "forensic" note wrongly concluded `C:\Games` was
the real install and repointed two scripts there — so every re-pack landed in
a folder the user doesn't play, and the user kept loading a stale archive.
This is what made subtitles appear "blank" — the staging archive predated the
subtitle translation. **Never repoint deploy at `C:\Games` again.**

## Subtitle "blank" saga — RESOLVED (2026-05-20)

Symptom: in-game subtitles rendered blank / "only special characters" while
menus showed Hebrew. After an exhaustive hunt (verified: data 95 % Hebrew,
fonts md5-identical Heebo, archive structurally identical to pristine,
subtitle widget uses `raj` font that IS swapped) the cause was **purely the
deploy-folder mistake above** — not data, not fonts, not the override
mechanism. Copying the current archive into the staging mod folder → subtitles
render in Hebrew, bottom + above-NPC.

New cleanup tooling:
- `build_subtitle_cleanup_queue.py` — scans `localization_translated.json`
  subtitle sections, queues every untranslated line (multi-word English +
  empty; skips single-word proper nouns) → `cleanup_queue.json` +
  `subtitle_cleanup_sections.txt`. Last build: 3,246 entries / 537 sections.
- `rebuild_subtitles_and_pack.py` — gained `--sections-file` (read the section
  list from a file; avoids the Windows CLI-length limit for ~hundreds).
- `cleanup_subtitles.bat` — one-shot: `translate_cleanup_all.py --no-rebuild`
  → `rebuild_subtitles_and_pack.py --sections-file subtitle_cleanup_sections.txt`.
  ~6.5 h run (translate + re-bake + deploy).

## Open / optional

- [ ] Run `cp2077_post_pipeline.py` once the markup translation finishes — it
      finishes the clean lines, runs the QA sweep, bakes + backs-up + deploys,
      refreshes the report, and launches the QA watchdog. Supersedes the manual
      `cleanup_subtitles.bat` + `cp2077_orchestrator.py` flow for base-game work.
- [ ] (optional) Add `cp2077_qa_watchdog.bat` to Task Scheduler ("At log on")
      so the QA guard survives reboots.
- [ ] Handle Phantom Liberty DLC text in `archive/pc/ep1/lang_ar_text.archive`
      — separate task, NOT part of the base-game pipeline.

---

# Steam Hebrew Localizer (Side Project)

Hijacks Steam's Arabic-locale slot to ship Hebrew UI in the desktop client +
Big Picture, using the same RTL/bidi pipeline trick as the CP2077 project.

## Current Status (2026-05-20)

**FULL RUN COMPLETE.** All 8 Steam UI files translated to Hebrew and
validated. `python steam_translator.py all` finished cleanly (exit 0).

### Final output (`steam_hebrew_output/`)

| File | Size | Slot | Keys | Hebrew |
|---|--:|---|--:|--:|
| `steamui_arabic-json.js` | 952 KB | (none — by filename) | 9,424 | 9,104 |
| `shared_arabic-json.js` | 315 KB | arabic | 3,964 | 3,822 |
| `friendsui_arabic-json.js` | 88 KB | arabic | 1,210 | 1,199 |
| `steampops_arabic-json.js` | 11 KB | arabic | 174 | 159 |
| `vgui_arabic.txt` | 10.8 KB | Arabic | 208 | 206 |
| `overlay_arabic.txt` | 20 KB | Arabic | 236 | 220 |
| `platform_arabic.txt` | 4.7 KB | Arabic | 59 | 56 |
| `trackerui_arabic.txt` | 57 KB | Arabic | 671 | 643 |

- **15,946 strings total · 98.03% Hebrew coverage.** The 309 "eng-only"
  entries are brand names / acronyms / FPS values (MMO, RPG, DLC,
  "60 FPS", "ROG Ally", "Steam", …) — intentional pass-throughs.
- Failure tally over the whole run: 34 timeouts · 12 fallbacks · 6
  single-fail (0.04%, kept English original).
- `steamui` carries no `language` key (true of the English source too) —
  Steam matches that bundle by filename. The other 3 JSON bundles + all
  4 VDF files have the locale slot hijacked to Arabic.
- QA: `python verify_steam_all.py` → "slot check: ALL OK".

### Throughput tuning — RESOLVED

The translator's speed problem went through three configs:

| Config | Result |
|---|---|
| `NUM_WORKERS=4`, `BATCH_SIZE=30` | LM Studio saturated — constant 240s `Read timed out`, cascading retries, ~16 strings/min decaying to ~3/min |
| `NUM_WORKERS=2`, `BATCH_SIZE=30` | Fewer timeouts but still ~5.7/min — 30-string batches still too slow per call |
| **`NUM_WORKERS=2`, `BATCH_SIZE=20`** | **~18-20 strings/min, near-zero timeouts** — final/correct setting |

Root cause: a 30-string batch generates enough output tokens that a
27B model on one GPU often exceeds the 240s read timeout; the retry
cascade then destroys throughput. A 20-string batch finishes well
inside the window. **Keep `BATCH_SIZE=20`.**

LM Studio also drifts slower over a long session (16+ h) — a "warm
reboot" (eject + reload the model in the LM Studio UI) restores speed.

### Checkpoint / resume (added 2026-05-20)

`steam_translator.py` now writes a sidecar `<output>.partial.json`
(`{key: hebrew}`) atomically after every batch. On restart it loads the
checkpoint and skips already-translated keys — any kill/crash loses at
most one batch. The checkpoint is deleted once the file completes.
Helpers: `checkpoint_path_for()`, `load_checkpoint()`, `save_checkpoint()`.

### VDF Language-slot bug (fixed 2026-05-20)

`translate_vdf` originally only processed lines inside the `"Tokens"`
block, but the `"Language"` key is a SIBLING of `"Tokens"` (sits before
it) — so the English→Arabic slot hijack never ran on VDF files. Fixed by
moving the `key.lower() == "language"` check ahead of the `in_tokens`
gate. The 4 VDF files already produced were patched in place by
`fix_vdf_language_slot.py` (no re-translation needed).

## Key files

| File | Purpose |
|---|---|
| `steam_translator.py` | Standalone translator — modern JSON bundle parser + legacy VDF parser, hijacks `language` field to `"arabic"`, outputs to `steam_hebrew_output/` |
| `verify_steam_output.py` | QA on translated JSON bundle (Hebrew %, placeholder preservation) |
| `verify_steam_vdf.py` | QA on translated VDF file (encoding round-trip, Language slot, placeholder count vs source) |
| `translation_manager/steam_apply.py` | `find_steam_install()` (registry probe → fallback) + `apply()` (backup-then-copy from `steam_hebrew_output/` into live Steam dirs) |
| `translation_manager/steam_mod.py` | Local lifecycle — cache + enable/disable toggle + clear_cache. Sits above `steam_apply`. |
| `translation_manager/mod_source.py` | GitHub-proxy fetch+verify+extract (written, not yet wired — Step 2 below). |

## Launcher integration (wired & live)

- **Sidebar** groups Games + Apps under a "ספרייה" header (`NavGroupRow` + `NavRow`).
- **AppsView** — Steam card with the full **Install / Enable / Disable**
  state machine (`SteamCardCta`) + a phase-aware progress bar fed by
  `mod_install_progress` events.
- **SettingsView** — "מטמון תרגומים" section with a **Clear Cache** button
  → `ClearCacheConfirm` modal (mirrors `LogoutConfirm`).
- **main_eel.py** exposes `apply_steam_translation`, `get_steam_mod_state`,
  `set_steam_mod_enabled`, `clear_steam_mod_cache`.
- **eel.ts** — `applySteamTranslation` / `getSteamModState` /
  `setSteamModEnabled` / `clearSteamModCache` + `onModProgress` subscriber.
- **eel-bindings.js** — static `mod_install_progress` registration
  (`window.__eelModHandlers`) — the bundler can't safely call `eel.expose`.

### Local lifecycle (steam_mod.py) — implemented 2026-05-20

- **Cache:** `~/.translation_manager/mod_cache/steam/` holds the extracted
  Hebrew tree + `state.json` (`{version, cached_at, enabled, installed_files}`).
  `apply_steam_translation()` is cache-first — only populates the cache on a
  miss, then `enable()`s.
- **Backup scheme — `<name>.orig`** (NOT timestamped `.bak`): the genuine
  Steam file is captured ONCE, the first time we overwrite it, and never
  touched again. A timestamped scheme can't toggle — a 2nd apply would back
  up our OWN Hebrew file. `enable()` = cache → Steam (+ make `.orig` once);
  `disable()` = `.orig` → Steam, or delete the file if no `.orig` (it was
  purely ours, e.g. a new `resource/*_arabic.txt`).
- **Partial-failure safety:** `disable()` only touches files in
  `state["installed_files"]` — the exact set the last `enable()` wrote — so a
  half-finished enable can't make disable delete an untouched Steam original.
- **`clear_cache()`** reverts Steam (restores `.orig`), deletes the `.orig`
  backups, then removes the cache — leaving the machine pristine.

**Cache source — STEP 2 LIVE (2026-05-20):** `apply_steam_translation()`
fetches from the private GitHub repo via the Cloudflare Worker proxy
(`mod_source.fetch_and_extract()` → download → SHA-256 verify → extract),
populates the cache, then `enable()`s. The temp dir is `shutil.rmtree`'d
in a `finally`. On a cache hit it skips straight to `enable()`.

Verified end-to-end 2026-05-20:
- `test_steam_lifecycle.py` — 22/22 (install → enable → disable →
  re-enable → clear_cache), self-restoring.
- Live worker fetch — `fetch_and_extract()` pulled v2026.05.20, SHA-256
  verified, 8 files extracted, temp cleaned. Phases download/verify/
  extract all fired.
Finding: Steam ships Arabic versions of only the 4 JSON bundles; the 4 VDF
`*_arabic.txt` files are purely ours (no `.orig`, deleted on disable).

End-to-end flow: launcher → תוכנות → "התקן" (download+enable) → restart Steam
with Interface=العربية. Thereafter the button toggles Enable/Disable with no
re-download; Settings → "נקה מטמון" wipes it.

## GitHub distribution (Phase 2 — 2026-05-20)

Private repo **`nehorayc04/steam-hebrew-mods`** is the source of truth.
Payload ships in Releases, never in the repo tree.

- **`pack_and_release.py`** — zips the 8 files from `steam_hebrew_output/`
  (internal layout mirrors Steam's tree), SHA-256s it, writes
  `manifest.json` (`{archive_name, sha256, version}`), and
  `gh release create`s it. Artifacts land in `./release/`.
  First release: **`v2026.05.20`** — `steam_hebrew_translation.zip`
  (300,996 bytes, sha256 `98a0c65f4186…`) + `manifest.json`.
- **`steam_mod_worker/`** — Cloudflare Worker proxy, **deployed & live**
  at `https://steam-hebrew-mods.nc52885.workers.dev`. `src/index.js` holds
  the GitHub PAT as the `GITHUB_TOKEN` secret (never shipped); routes
  `/steam-hebrew/manifest` + `/steam-hebrew/archive`. Redeploy after
  edits: `wrangler deploy` (the secret persists).
- `mod_source.py` `PROXY_BASE` defaults to
  `https://steam-hebrew-mods.nc52885.workers.dev` — verify after deploy.

## File-format gotchas (discovered the hard way)

1. **Modern bundles** are `JSON.parse('…')` inside a webpack chunk. Single-
   quoted JS string with `\'` and `\\` escapes wrapping a JSON payload.
   Round-trip needs proper JS-string decode/encode (NOT `unicode_escape`).

2. **Legacy VDF files are UTF-8 with BOM**, not UTF-16 LE as the older
   Steam docs imply. All four (`vgui_english.txt`, `overlay_english.txt`,
   `platform_english.txt`, `friends/trackerui_english.txt`) are UTF-8 BOM
   as of 2026. `translate_vdf` now sniffs both BOMs (`\xff\xfe` and
   `\xef\xbb\xbf`) and round-trips in the source's own encoding.

3. **`shared_dummy: "dont translate"`** — Steam's own meta-placeholder that
   instructs translators to leave it alone. Our system prompt + skip-rules
   correctly preserved it on the steampops test (the AI followed the
   instruction in-band).

4. **U+2028 / U+2029** must be escaped to ` / ` when re-
   embedding in a JS source string literal — raw bytes would break the
   surrounding `'…'` literal. Easy to miss because they look like ordinary
   spaces in editor display.

## Steam install detection

`steam_apply.find_steam_install()` probes in order:
1. `HKCU\Software\Valve\Steam` → `SteamPath`
2. `HKLM\SOFTWARE\WOW6432Node\Valve\Steam` → `InstallPath`
3. Default `C:\Program Files (x86)\Steam`

Validates each candidate by checking `<dir>/steamui/` exists. Verified
working on this machine — returns `c:\program files (x86)\steam`.

## Verification on the steampops test (already passed)

| Metric | Value |
|---|---|
| Total keys | 174 |
| `language` slot | `"arabic"` ✓ |
| Translated to Hebrew | 172 / 173 (99.4%) |
| Preserved as-is | `shared_dummy: "dont translate"` (intentional) |
| Output | `steam_hebrew_output/steamui/localization/steampops_arabic-json.js` (11,220 bytes) |
| Runtime | 1335s (~22 min) sequential, BATCH_SIZE=12 |

## Open tasks (Steam project)

- [x] ~~Tune concurrency~~ — settled on `NUM_WORKERS=2`, `BATCH_SIZE=20` (2026-05-20)
- [x] ~~Complete full `steam_translator.py all` run~~ — done, 8 files, 15,946 strings (2026-05-20)
- [ ] Manual end-to-end: close Steam → click "התקן" → restart Steam with Interface=العربية → verify Hebrew UI
- [ ] Bundle `steam_hebrew_output/` alongside the launcher in `build_exe.bat` (PyInstaller / Inno Setup) so installed users get pre-compiled translations without running the translator themselves
- [ ] Handle Steam-running case: detect `steam.exe` and either auto-kill (UAC) or block with a clear error before attempting to copy
- [ ] (Optional) Add an "Uninstall" action in AppsView that restores `*.bak.<timestamp>` files
- [ ] (Optional) Log the failing input string in the per-item fallback handler so the 6 single-fail entries can be pinpointed for a cleanup pass

## Technical decisions (Steam project)

- **Arabic-slot hijack** rather than adding a new `hebrew` slot — Steam has
  no `hebrew` locale; the Arabic slot also gets us built-in RTL/bidi
  handling for free.
- **Backup-then-overwrite** with timestamped `.bak.<YYYYMMDD_HHMMSS>` files
  in the same directory — single-file restore, no separate backup tree.
- **OpResult-shaped return** from `apply_steam_translation()` so we don't
  need a new TS type; reuses the existing `OpResult` interface.
- **Source dir detection via `sys.frozen`** — works for both dev runs
  (`steam_hebrew_output/` next to `main_eel.py`) and PyInstaller bundles
  (`steam_hebrew_output/` next to the exe). Bundling step itself still TODO.
- **No new chrome for the install toast** — reuses App.tsx's existing top-
  center `reportStatus` plumbing; AppsView accepts it as a prop.
- **System prompt strictness** copied from CP2077: Hebrew + ASCII only,
  no Niqqud, preserve every placeholder/tag, brand names stay English.
  Validation showed only 1 untranslated string out of 173 — the one Steam
  itself flagged with "dont translate".
