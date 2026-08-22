## 📘 "הפלטפורמה המאוחדת" — Winhanced × TranslationManager, PDF עיצוב חזותי מלא (2026-07-30/31, שני PDF בשורש הפרויקט)

תרגום מסמך ה-blueprint המקורי (`translation_manager_winhanced_master_blueprint2.md` — 10 קטגוריות
+ 8 דיאגרמות mermaid) לכדי **PDF מעוצב אמיתי**: רקע כהה, טקסט לבן/צבעוני, וכל דיאגרמת mermaid
הוחלפה במנוע flowchart/sequence-diagram **תוצרת-בית** (RTL מלא, בלי mermaid בכלל כלל) שמצייר עם
SVG מחושב (קשתות/חצים בטריגונומטריה, לא path-data ידני).

- **הצינור:** Python בונה HTML+CSS טהור (`build.py`/`build_unified.py`) → Chrome headless מרנדר
  ל-PDF → `PyMuPDF` (`fitz`) מרנדר כל עמוד ל-PNG ב-150dpi לבדיקה ויזואלית (`Read` tool על כל
  עמוד בפועל — לא הנחות). עמוד = `<div class="sheet">` בגודל A4 קבוע (`break-after:page`), לא
  pagination אוטומטי של הדפדפן — כך כל "תרחיש" יוצא באותו גודל בדיוק, בלי חיתוכים.
- **מנוע דיאגרמות עצמאי** (מחליף mermaid לגמרי): `node()`/`flow_row()`/`flow_col()`/`branch()`/
  `merge_up()`/`sequence()`. RTL אמיתי — עמודות ה-sequence-diagram ממוספרות הפוך
  (`col_of[aid] = n - i`) כך שהישות הראשונה שמוצהרת יושבת הכי ימין (סדר קריאה עברי טבעי); הודעת-
  עצמי (self-message loop) מצוירת עם סוגר-לולאה ייעודי.
- **עמוד השער** — שני אייקוני מותג עגולים (מעובדים ב-PIL: supersample ×4, מסכת אליפסה,
  GaussianBlur על השוליים, downscale) מ-`AppIcon.jpg` (Winhanced) ומ-`לוגו לאייקון\
  1784219013286_1784219075576.png` (TranslationManager), מחוברים בסמל sync מחושב (`sync_mark()`)
  — מבטא מיזוג שני המוצרים עם כל היתרונות של שניהם ביחד.
- **תיקון "דק מדי" (האחרון, ממש לפני כתיבת התיעוד הזה):** דיווח המשתמש שהטקסט/קווים/חצים דקים
  מדי ונבלעים ברקע הכחול עם הרשת. תוקן שיטתית בקובץ ה-CSS: כל stroke-width/border-width הוכפל
  בערך (למשל `.arrow-line` 1.4→2.2, `.node` border .75px→1.2px, `.branch-stem`/`.merge-*` 1px→
  1.8px + צבע מ-`--cyan-line` החלש ל-`--cyan-soft` החזק), וכל טוקן צבע ב-`:root` הואר (`--ink`
  #e9eff8→#f4f8fd, `--ink-dim` #9fb2ca→#bcd0e8, `--cyan-soft` אלפא .55→.85 וכו'), בעוד שקיפות
  רשת הרקע צומצמה כדי שתפסיק להתחרות. תוקן גם overflow שנוצר בעמוד טבלת ההשוואה הסוגרת (padding
  תאים + margin/padding של תיבת ה-callout צומצמו).
- **באגים נוספים שנמצאו+תוקנו בדרך:** double-escaping של HTML entities (מחרוזות מקור שכבר
  הכילו ישויות בשם/מספר, וה-`html.escape()` עיוות אותן — תוקן ע"י המרה ל-Unicode ליטרלי ישירות
  ב-Python) · אימוג'י שגוי (🚫 במקום 🚁 בתרחיש 4) · גרש לטיני שגוי במקום גרש עברי אמיתי (U+05F3)
  · תיבות "חלולות" ענקיות בדיאגרמות (נגרם מ-`flex:1` שמותח `.diagram-panel` — תוקן להסרת flex:1
  וגודל אינטרינזי) · שרשראות 4-nodes שנשברו לצורת "S" מבלבלת (קטגוריות 2,4 + קטגוריה 6) — תוקן
  במעבר מ-`flow_row()` ל-`flow_col()` · קו-מחיקה על תווית self-message loop (תוקן ע"י הרחבת
  `.seq-self` והורדת קו הלולאה) · sequence-diagrams קצרים שנדבקו לראש העמוד עם ריק גדול למטה
  (תוקן ע"י `align-items:center` + `row_h` בסיסי 15→19).
- **שני קבצי PDF קיימים כרגע בשורש הפרויקט — שניהם עדכניים, לא סותרים:**
  | קובץ | עמודים | גודל | תאריך | מקור |
  |---|---|---|---|---|
  | `translation_manager & winhanced.pdf` | 19 | 4,330,418 B | 2026-07-30 20:18 | `build.py`→`blueprint.html`/`.pdf` — רינדור 1:1 של ה-markdown המקורי (10 קטגוריות + 8 תרחישים) |
  | **`unified_platform_visual_scenarios.pdf`** | **25** | **4,850,828 B** | **2026-07-31 06:18** | `build_unified.py`→`unified.html`, נבנה ע"י `make_pdf.py` דרך CDP `Page.printToPDF` (לא ה-flag `--print-to-pdf` הרגיל — יציב יותר לזמן טעינת הפונטים) |
  השני הוא **REV. 02** — הרחבה/ארגון-מחדש אמיתי, לא רק תיקון עיצובי: יורש את כל תיקוני העובי/
  בהירות שלמעלה (נבנה אחריהם), אבל מארגן מחדש ל-**8 "קטגוריה"** + חלק תרחישים ייעודי שגדל
  **מ-8 ל-13 תרחישים**. חותמת השער: **"VISUAL MASTER PLAN · REV. 02"**, ופס הסטטוס בתחתית השער
  קורא במפורש **"תכנון · לא לביצוע"** — כלומר זהו מסמך חזון/הצעה, לא הוראת בנייה.
- **מפת 25 העמודים של `unified_platform_visual_scenarios.pdf`:** שער (00) → אינדקס (01) →
  קטגוריות 01–05 (02–06) → מפריד "13 תרחישים חזותיים" (07) → 13 עמודי תרחיש (08–20): 🛒 גילוי←
  מחיר←קנייה←הופעה בספרייה · 🌐 תרגום בלחיצה אחת (המנוע שלך) · 🎮 Handheld במצב בקר עם תרגום ·
  👁 תרגום-מסך חי תוך-משחק (ניסיוני) · 🚁 סנכרון צי (Fleet) ↔ אתר /translate · 🧩 התקנת מוד +
  בדיקת קונפליקטים · 🧠 כניסה למשחק ← השהיית UI ל-Tray · ☁️ סנכרון ענן PC↔Handheld · 🤖 אימות
  אוטונומי ברקע (dxcam) · ⚡ פרופיל TDP חכם (Handheld) · 🎁 התראת משחק-חינם (בטוח ל-ToS) · 🕹
  ניווט מלא בבקר (Console Mode, דיאגרמת flow לא sequence) · 🟣 נוכחות Discord+חברים — קטגוריה
  07 (21) → קטגוריה 08 סיכום מנהלים (22) → טבלת השוואה מרכזית 1/2 ו-2/2 (23–24, Winhanced מול
  "שלך"/TranslationManager, כולל 4 יכולות חדשות שאף בסיס לא נותן היום: OCR חי, זיכרון-תרגום
  קהילתי, פרופיל TDP+שפה כפולה, סנכרון PC↔Handheld).
- **תיקיית עבודה:** `scratchpad/blueprint_pdf/` — `build.py` (19-עמוד), `build_unified.py`
  (25-עמוד, ~32KB), `make_pdf.py` (רינדור ה-PDF הסופי דרך CDP), `capture_check.py` (בדיקת
  screenshot מהירה של 3 עמודים דרך CDP), `unified.html`/`blueprint.html` (HTML שנוצר), `fonts/`
  (Heebo Regular/Medium/Bold/Black, SuezOne, Consolas+Bold), `icon_winhanced.png`/
  `icon_translationmanager.png` (תגי המותג העגולים 600×600), `preview/`+`preview_unified/`
  (צילומי QA ב-150dpi), `chrome_profile2/` (פרופיל Chrome מבודד לרינדור — `chrome_profile`
  המקורי ננעל ע"י נעילות קובץ פתוחות של Chrome ונזנח לטובת השם החדש).
- **מצב:** שני ה-PDF תקינים ומאומתים ויזואלית (כל 25 העמודים של הגרסה המאוחדת נבדקו). אין
  overflow, אין תיבות ריקות, טקסט/קווים קריאים על רקע הרשת הכחולה. `unified_platform_visual_
  scenarios.pdf` הוא הגרסה השלמה/העדכנית ביותר ומיועד כמסמך ההתייחסות הראשי מכאן והלאה;
  `translation_manager & winhanced.pdf` נשאר כרפרנס לרינדור המקורי 1:1 של ה-markdown.
- **פתוח:** אין משימה תלויה כרגע — ממתין להנחיה נוספת של המשתמש (עריכות תוכן/עיצוב נוספות אם
  ירצה).
- **החלטות טכניות:** mermaid הוחלף לגמרי במנוע ציור עצמאי כדי לשלוט לגמרי ב-RTL, בגודל-עמוד
  קבוע, ובעקביות חזותית בין "תרחישים" — פתרון מוכן-מראש היה בולם את כל שלוש הדרישות בו-זמנית.
  `Page.printToPDF` דרך Chrome DevTools Protocol (במקום ה-CLI flag `--print-to-pdf`) נבחר לבנייה
  הסופית של `unified_platform_visual_scenarios.pdf` כי הוא מאפשר `time.sleep()` מבוקר לפני
  ההדפסה, כדי לוודא שהפונטים המוטמעים (`@font-face` מקומי) נטענו במלואם — מונע טקסט שנופל
  לפונט חלופי, שקורה לפעמים עם ה-CLI flag. שני קבצי ה-PDF (19-עמוד + 25-עמוד) נשמרים בו-זמנית
  בשורש הפרויקט במקום דריסה — כל אחד נבנה מסקריפט שונה (`build.py` מול `build_unified.py`)
  ומשקף שלב שונה בהתפתחות התוכן; לא נמחק אף אחד מהם עד הנחיה מפורשת.


## 🧭 "הפלטפורמה המאוחדת" — readiness assessment + TWO real sub-projects, not one (2026-08-16)

Continuing from the PDF-design work above: the underlying proposal is a real, actively-researched
initiative to merge TranslationManager with feature ideas from a genuine third-party closed-source
Windows app called **Winhanced** (a Handheld-gaming "shell," v0.9.9.3 Beta, installed at
`C:\Program Files\Winhanced`) — NOT the user's own product. **Two SEPARATE tracks exist under this
umbrella and must never be conflated** (the user asked "is everything ready to start developing" —
this section is the answer, verified against the real repo, not just against the planning docs).

### Track A — Hebrew-localize Winhanced itself (`games/winhanced/`) — the hard gate is already CLOSED

Same class of project as every other closed-app/game translation in this repo (WD2/SM2/AC2/etc.) —
patch a third-party binary's OWN shipped resource files with a local Hebrew translation, no
redistribution of their assets. This sub-project was ALREADY underway (dated ~2026-07-26/27, before
the platform-merge planning docs) and had never been logged here until now:
- Container = compiled binary XAML (`.xbf`) + `Winhanced.pri` (Package Resource Index). Both are
  READ **and WRITE** (`games/winhanced/work/xbf.py`, `pri_xbf.py`), the `.pri` written delta-0.
- `deploy.py` follows this project's own hard-won safety discipline exactly: backs up every file to
  `games/winhanced/backup/` BEFORE the first write (never overwrites an existing backup, so a 2nd
  deploy can't capture our own patch); the manifest stores BOTH the pristine sha256 AND the deployed
  sha256, so `--revert` REFUSES to restore over a file the vendor has since updated (a Winhanced
  auto-update would otherwise silently downgrade — [[game-update-makes-backups-stale]]); everything
  writes to a temp file + `os.replace`.
- **3-round proof methodology, the exact "menu-proof" pattern used on every other target.** Round 1
  (naive single-token replacement) **hung the app on load** — in compiled XAML a bare token is just
  as likely to be an `x:Name`/`VisualState`/resource key as a visible label, and renaming one breaks
  the parse ([[translate-labels-never-values]], the same class as every combobox-value trap in this
  file). Round 2 restricted to multi-word prose only → worked. Round 3 tested which SINGLE tokens
  are safe by checking whether they're visibly rendered on screen (`Play`/`Search`/`Close`/`Select`
  found on the bottom action bar) — [[pin-proof-strings-to-seen-rows]].
- `games/winhanced/backup/manifest.json` shows **`deployed_sha256 != original_sha256` on 3 files**
  (`MainWindow.xbf`, `Views/GameOptions/ArtworkBrowserPage.xbf`, `Views/StreamingLaunchOverlay.xbf`)
  — **a proof build has already been deployed onto the LIVE installed Winhanced.exe.**
- Corpus: `extract/ui_text.txt` = **772 lines** of real UI text (software-scale — comparable to
  VirtualDJ/SignalRGB, not a AAA game corpus); `extract/ambiguous_tokens.txt` (170 KB) classifies
  every string as identifier/URI/schema/color/numeric/dotted-path/geometry vs. real prose
  (`work/scope.py`), the same "records / per-file uniques / GLOBAL uniques, separate identifiers
  from real text" discipline documented in §17 of this file for every other corpus-scoping pass.
- **What's genuinely missing:** no `RECON.md`/`FEASIBILITY.md`/`PIPELINE.md` exist for this target
  (every other target in this repo has all three — this write-up is the first documentation of it
  at all). The actual content-translation pass has NOT started — only ~13 proof strings exist
  (`proof_he.json`/`proof_tokens.json`), not the 772-line corpus. **⇒ the multi-week hard part
  (cracking the closed container format) is done; what's left is ordinary translation work**
  (delegate per [[delegate-all-translation]] once proper groundwork docs exist for it).
- Legally distinct from Track B: locally patching Winhanced's own shipped resource files is the
  same category as every other closed-game/app mod in this project (a local patch, never
  redistributing their assets) — Track B below must never copy their UI/code/assets this way.

### Track B — the "unified platform" architectural merger (the PDF cluster) — planning DONE, development NOT yet greenlit

`unified_platform_visual_scenarios.pdf`/`.md` (built above, self-labeled **"תכנון · לא לביצוע"** —
planning, not execution) proposes merging TranslationManager with feature IDEAS borrowed from
Winhanced (unified cross-store library, console/Big-Picture mode, TDP control, Discord presence,
live-OCR screen translation, cloud sync, etc.). Its companion, **`unified_platform_grounded_plan.md`**
(same day, same authorship), is an explicit self-correcting engineering audit that "unifies and
REPLACES" 5 earlier, more hyped docs (`winhanced_report.md`, `translation_manager_vs_winhanced_
architecture_report.md`, the two `*_master_blueprint*.md` files, `winhanced_servers_report.md`) —
and it already functions as most of the readiness assessment on its own. Read in full 2026-08-16,
then EVERY concrete codebase claim in it was VERIFIED against the real repo, not trusted blind:

| Claim in `unified_platform_grounded_plan.md` | Verified against the repo |
|---|---|
| "Console-Mode/Big-Picture is already ~80% built, just behind a flag" | ✅ `frontend/src/App.tsx:44` `const BIG_PICTURE_ENABLED = false`; `lib/spatialNav.ts` (17,337 B), `lib/gamepadMap.ts` (6,220 B), `components/BigPictureMode.tsx` (8,955 B) all exist and are substantial — matches the "Launcher design — WAVES 2+3" history documented elsewhere in this file |
| "`perf_manager` already has RAM-trim (`EmptyWorkingSet`)" | ✅ `translation_manager/perf_manager.py` — real ctypes psapi binding (`restype`/`argtypes` declared), called from `trim_memory()` |
| "`game_detector` already covers more than Steam" | ✅ real Ubisoft Connect (registry), Epic Games (Manifests `*.item` JSON), GOG Galaxy (registry), Xbox/MS Store (XboxGames folder) detection, plus `detect_via_launchers()` + common-path fallback lists |
| "Qt WebEngine's `--disable-gpu-compositing` is why glass/`backdrop-filter` had to be dropped" | 🔴 **STALE — corrected 2026-08-16.** `main_qt.py` (~lines 89-183) defaults GPU compositing **ON** (`--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy --enable-accelerated-2d-canvas`); `--disable-gpu-compositing` only fires on an explicit user opt-out (`launcher_prefs.json`'s `disable_gpu_compositing`, the "האצת חומרה" Settings toggle), a detected prior boot-crash safe-mode, or an external `QTWEBENGINE_CHROMIUM_FLAGS` override. A working weak-hardware auto-degrade ALREADY exists too (`gpuInfo.ts`'s `UNMASKED_RENDERER` sniff → `themePrefs._weakHost()` → `autoBackdrop()` falls back to `data-backdrop="none"`). The documented 2026-06-28 FPS-fix history (below) is accurate as HISTORY — that was the state of the flag on that date — but is no longer the CURRENT default. See `unified_platform_RECON.md` for the full correction; it reframes Stage 0's question from "can Python+Web render glass at all" (already yes, on decent hardware) to "does WebView2 raise the floor on weak/GPU-blocklisted hardware specifically." |

**§ The document's own explicit verdict — NOT ready to build the native host ("Base 2"/Stage 4)
yet.** Three decisions/steps remain open, none of which I can make for the user:
1. **Audience** — Handheld owners (ROG Ally/Legion Go/Steam-Deck-on-Windows, where TDP/fan control
   is central) vs. Desktop-Hebrew-first (the product's actual current identity — a Hebrew
   game-translation hub; TDP/fans are nearly worthless off an AMD-APU handheld). Reorders ~70% of
   the roadmap's priority order by itself.
2. **Base-2 technology** — a thin native host (.NET **or** Tauri/Rust) whose only jobs are: host
   the EXISTING, UNCHANGED React frontend inside a GPU-accelerated WebView2 control (fixes the
   glass/FPS problem Qt can't); native hardware/controller/overlay access; a lightweight resident
   tray daemon. Python stays the untouched "moat" (translation engine, every `games/*` injection,
   the Fleet, `/translate`, community-compute), running as an IPC sidecar (named-pipe/socket/stdio
   JSON-RPC — not shared memory). **Explicitly REJECTS rewriting the UI in WinUI 3** (throws away
   the whole frontend/RTL/launcher-designer investment for no real gain — the "Living Glass" look
   is reproducible in plain CSS; the snippet is already in `translation_manager_vs_winhanced_
   architecture_report.md`).
3. **A Stage-0 proof-of-concept** — actually build + MEASURE whether hosting the current React UI
   inside GPU-accelerated WebView2 raises the reliability floor on WEAK/GPU-blocklisted hardware
   specifically (the corrected framing above — Qt already renders real glass on decent hardware, so
   the open question narrowed). Not yet built, not yet measured.

**§ Status (2026-08-16) — the narrative became an executable plan, approved, and Stage-1 has
started shipping.** `EnterPlanMode`/`ExitPlanMode` was used to turn the above into a concrete,
staged plan (`C:\Users\Nehoray_Cohen\.claude\plans\snoopy-exploring-balloon.md`) — user-approved.
Three new companion docs now exist alongside the two above: **`unified_platform_RECON.md`**
(verified-claims table, incl. the GPU-compositing correction), **`unified_platform_FEASIBILITY.md`**
(the (A)/(B) reasoning + per-item C0-C6 go/no-go), **`unified_platform_PIPELINE.md`** (the checkable
task list). Audience default settled as **Desktop-Hebrew-first** (reversible, stated not asked —
`game_detector.py` has zero handheld-specific detection, zero TDP code, and the whole product is
Hebrew-RTL AAA-PC-title localization). Standing constraints for the whole initiative: Base 1 (every
`games/*` pipeline, Fleet, `/translate`, community-compute) stays untouched; every change is a
LOCAL build/install only, published to nobody until an explicit "פרסם"; PawnIO/RyzenAdj/TDP work is
fully out of scope; every new backend capability needs both RPC halves (`main_eel.py` `@eel.expose`
+ `bridge.py` `@Slot`).
- **🔴 C0 as written ("flip `BIG_PICTURE_ENABLED` to true") WAS THE WRONG READING — SUPERSEDED by
  "ביג-לאנץ" (2026-08-16, BUILD_ID `20260816044752`, DEV 257).** I shipped the flag flip
  (`20260816040719`) and the user corrected it verbatim: *"לא הבנת אותי נכון. אני לא רוצה את המסך
  מלא שהיה פעם ושסתרתי אותו. אלא **להסיר את הישן** ותצור «ביג-לאנץ» **בדיוק כמו winhanced** — משהו
  **נפרד** מהלאנצר שיש עכשיו."* The old overlay was a thin cinematic carousel bolted onto the
  desktop shell; what the blueprint's category-10 comparison row actually asks for is a **10ft
  console UI** — a separate experience, the way Winhanced ships a Console mode beside its Desktop
  mode. **`components/BigPictureMode.tsx` DELETED** and every reference stripped from `App.tsx` +
  `HomeView.tsx` (verified: 0 matches for `BigPicture|bigPicture|BIG_PICTURE|onBigPicture` in the
  whole frontend).
  - **⚠️ Found while removing it: the old Big Picture had NO controller entry at all.** `App.tsx`
    listened for a `toggle-bigpicture` event that **nothing in the codebase ever dispatched** —
    `spatialNav.ts` maps Start(9)→`nav-settings` and Guide(16)→`nav-sidebar`, and there is no
    `toggle-bigpicture` emitter anywhere. So the plan's "controller Start flips it" was never true,
    and the flag flip had only ever exposed a mouse button. **A dead event listener reads exactly
    like a wired feature — grep for the DISPATCH, not just the listener, before believing a
    binding exists.**
  - **What "separate" means here, decided from Winhanced's own shape** (`games/winhanced/extract/
    ui_text.txt` — its Power Options carry "Desktop Mode" / "Switch to Windows desktop", and it has
    a "Desktop mode launch at startup" setting): Winhanced is ONE app with two experiences, not two
    processes. So: **separate React root** (`frontend/src/biglaunch/`, 5 files), **separate CSS**
    (`bigLaunch.css`, self-contained, not Tailwind), **separate window state** (borderless
    fullscreen), **its own shortcut** — and the two shells never mount together.
  - **🔑 THE SWITCH IS THE URL FRAGMENT — the channel `main_qt.py` ALREADY uses.** Deep links
    already do `initial_url.setFragment(f"game={id}")` and `App.tsx` already reads
    `/[#&?]game=…/` from `window.location.hash`. So `#big` → `<BigLaunchApp/>`, anything else →
    `<App/>` (`main.tsx`), and a shortcut running `TranslationManager.exe --big` lands there with
    zero new plumbing. A deep link WINS over `--big` (an explicit `hebrewhub://game/<id>` click
    opens that game's desktop page rather than being hijacked into the console).
  - **The nav engine is REUSED, not rewritten.** `spatialNav.ts` was read in full and confirmed
    fully DOM-generic (nearest-focusable-by-direction scoring on rectangle GAP, typematic repeat,
    stick hysteresis, right-stick scroll, `body.using-spatial-nav` focus ring, and it only polls
    the gamepad while a pad is connected). Big Launch calls `initSpatialNav()` and listens to the
    same `nav-back`/`nav-sidebar`/`nav-settings` events — so controller behaviour CANNOT drift
    between the two shells. **Guide (button 16, already bound to `sidebar`) opens the quick menu**
    inside Big Launch — matching Winhanced's "remap a hardware key to the Gamebar" idea with **no
    new binding**. B is contextual and, at the root, opens the quick menu (console convention).
  - **Backend: 3 new RPCs, both halves each** (`set_big_launch` · `big_launch_requested` ·
    `app_quit` in `main_eel.py` + `bridge.py` + `eel.ts`). `main_window.set_big_launch(on)` saves
    `_pre_big_maximized`/`_pre_big_geometry`, hides the custom title bar and `showFullScreen()`s;
    leaving restores geometry + maximized state + the title bar. **`app_quit` deliberately does NOT
    call `window_close()`** — that honours the close-behavior pref and usually just hides to the
    tray, which from a full-screen console reads as "the app vanished"; it routes to
    `request_real_exit()`, the same path the tray's own Quit uses.
  - **🔑 HONEST SCOPE, surfaced in the UI instead of faked:** the console drives the SIMPLE generic
    translation path (`modSlug` + owned → `downloadAndInstallGameMod`). The 8 NATIVE appliers
    (SM2/WD2/GTAV/GoWR/W3/HL/PT/SignalRGB — `modSlug === ""`) each carry their own multi-branch
    flow, DRM gate and activation note in the desktop panel; re-implementing them here would
    duplicate that surface and drift. Those games get an explicit **"🖥 פתח בשולחן עבודה"** handoff
    button + an explanatory line, not a pretend button.
  - **Perf rules baked into the new CSS** (this project's own): NO large always-on
    `backdrop-filter` (the documented CPU-raster FPS killer under this launcher's Chromium) — flat
    rgba fills + static gradients instead; **exactly one** blurred element (a static hero `<img>`
    that never animates); every transition on `transform`/`opacity` only; FOCUS (not hover) is the
    primary state, and `onMouseEnter` forces focus so mouse and controller always agree.
  - **Verified:** `npx tsc -b` clean · `py_compile` clean on `main_eel.py`/`main_qt.py`/`bridge.py`/
    `main_window.py` · BUILD_ID + dist-exe mtime both confirmed fresh before ISCC ·
    `Output\TranslationManager-Setup-1.2.0.exe` (143,100,265 B) launched via `Start-Process` for
    the user's UAC. **NOT published** — say "פרסם" to ship it. **Still open (needs a human at the
    machine): the controller/keyboard smoke test of the real console shell** — entry from the home
    button AND from the new `--big` shortcut, tile focus/scroll, the game hub, the quick menu, and
    the return-to-desktop path.
  - **🔑🔑 REBUILT 1:1 ON THE REAL WINHANCED (2026-08-16, BUILD_ID `20260816135837`, DEV 258) —
    the user escalated twice: "שיהיה ממש דומה לwinhanced" → "שיהיה בדיוק כמוהו ולא רק דומה".**
    A "similar-looking" console shell was not the ask; the layout had to BE theirs. **The method
    that made that possible without copying a single asset: decode their compiled XAML's STRING
    TABLE.** `games/winhanced/work/xbf.py`'s `parse(path).strings` returns every type name,
    property name, `x:Name` and literal roughly in markup order — enough to reconstruct the element
    tree of all 113 `.xbf` files. That recovered, verbatim: `MainWindow.xbf`'s
    `BumperPillNavigation` (LB ‹ pills › RB, `GlowUnderline` on the active tab) ·
    `PinnedSecondaryNavHost` (LT ‹ filter chips › sort ▾ + range counter › RT) · the
    `GlassRailHost`/`HomeGameInfoPanel` beside a horizontal `RecentGames` ItemsRepeater ·
    `NavFooterGrid` (the controller hint bar) · the crossfading `BackgroundImageA/B` +
    `BloomCanvas` + `AcrylicVeil` stack; `Views/GameDetailsPanel.xbf`'s hero + Diagonal/Top/Bottom
    scrims + `ActionDock` (SplitButton + DockCard stats + DownloadProgressBar);
    `Dialogs/PowerMenuDialog.xbf`'s exact row set (icon + SemiBold title + subtitle, divider,
    "Desktop Mode — Switch to Windows desktop", "Quit"); `Controls/GlassPillIndicator.xbf`'s pill
    order; and `Resources/DesignSystem.xbf`'s tokens (Inter Light/Medium/SemiBold, sizes
    12/14/16/18/20/22/24, spacing 2/6/12/20, `SystemAccentColor`, the Glass*/Acrylic* brush family,
    `CardFocusGlowBrush`, `GameCardCornerRadius`, `GlassPillCornerRadius`, H1/H2/H3 + Body1/Body2 +
    Subtext styles). The card is rebuilt to their own anatomy — `ShadowHost > FocusableCardButton >
    CardChrome + TintOverlay + CardSpecularRim + BoxArtImage + GlassSourceBadge + FocusGlowBorder +
    FocusScaleTransform` with `FocusStates` Unfocused/Focused/PointerFocused.
    **UNIVERSAL: to match a closed app's UI exactly and legally, decode its compiled-markup STRING
    TABLE to recover the element tree + design tokens, then RE-IMPLEMENT in your own CSS/SVG.
    Layout/IA is observable design; the binary assets are the thing you must never copy** (their
    controller glyphs ship as PNGs — ours are drawn in `BigGlyph.tsx`, which also lets them
    re-colour with the theme).
    - **⚠️ The 10-agent Workflow spent 3.3M subagent tokens and returned `(no spec produced)`** —
      every agent hit the session limit. The XBF decode did the same job myself, faster and free.
      **Before fanning out agents at a closed binary, check whether the project already owns a
      reader for its format** (`xbf.py` existed from Track A all along).
    - **🔴 RENDERING THE SHELL FOUND 3 REAL BUGS THAT READING THE CODE DID NOT**
      ([[close-the-loop-before-tuning]]): the built app was loaded in headless Chrome behind a mock
      `window.bridge` (the Qt slot shape is `fn(...args, cb)`, so a mock is ~30 lines) and the PNGs
      were read. (1) The `GlassPillIndicator` floats at the top inline-start and **covered the LB
      glyph** — fixed by centering the bumper group so the glyphs hug the pills, which is also what
      Winhanced actually does. (2) A cover that FAILS to load left a **totally blank card with a
      broken-image glyph** — `BigTile` had no `onError`; now it falls back to the title plate
      (same family as [[cached-image-onload-race]]). (3) The power dialog was translucent over box
      art and **unreadable** — a modal is a SOLID layer over a dim scrim, never glass on glass.
    - **⚠️ AND ONE "BUG" I DIAGNOSED FROM THE SCREENSHOT WAS WRONG.** I read the library grid as
      laying out LTR and "fixed" it; checking the actual card ORDER right-to-left proved it was
      correct all along (Hebrew captions under Latin box art make an RTL grid look LTR). The
      `direction: rtl` I added is a harmless explicit no-op and its comment now says so.
      **Read the ORDER, not the picture** — [[hebrew-screenshot-transcription-trap]], one level up
      from text to layout.
  - **🔑🔑🔑 REBUILT ON A NEW BASE — TWO EXECUTABLES, THE STEAM SHAPE (2026-08-17, BUILD_ID
    `20260816225005`, DEV 261).** The user asked for the same design but **"גם אם זה בסיס אחר"** and
    **"שיהיה כמו סטים וביג סטים שיש לכל אחד EXE שונה"** — an explicit authorisation to change the
    stack. So the console shell left the React/WebView surface entirely and became **`biglaunch/` —
    a WPF (.NET 8) app publishing its own `BigLaunch.exe`**, with its own shortcut, its own
    `AppUserModelID` (`HebrewTranslationHub.BigLaunch`, matching `installer.iss` so Windows gives it
    a **separate taskbar button** — the visible difference between "two programs" and "one program
    twice"), and its own DWM Acrylic window. The launcher keeps `TranslationManager.exe`. Neither
    embeds the other.
    - **The handoff is two-way and already had one half.** BigLaunch → launcher existed
      (`Catalog.OpenDesktop(gameId)` spawning `TranslationManager.exe hebrewhub://game/<id>`, which
      `main_qt.py` already parses). The missing direction is `big_launch_available` / `open_big_launch`
      in `main_eel.py` **plus the mirrored `@Slot`s in `bridge.py`** (the 1:1 RPC contract — a
      capability with only one half silently works in one build and does nothing in the other).
      `enterBigLaunch()` prefers the native EXE and **falls back to the old in-process React console**
      for a launcher installed before the shell shipped, so the button is never dead.
    - ⚠️ **The console deliberately OUTLIVES the launcher that started it** (`DETACHED_PROCESS |
      CREATE_NEW_PROCESS_GROUP`) — which means it holds its own file lock, so `installer.iss`'s
      `KillLauncherProcesses` had to learn to `taskkill /IM BigLaunch.exe` too, or the copy fails on
      a file whose parent process is already gone.
    - **Winhanced's signature capability, ported: live telemetry** (`Services/Telemetry.cs`) in the
      status pill — CPU + RAM by the SAME pure P/Invoke this project's own `perf_manager.py` uses
      (`GetSystemTimes` deltas, `GlobalMemoryStatusEx`), 2 s cadence, tinting warm ≥75 % and
      destructive ≥90 %. ⚠️ **kernel time INCLUDES idle**, so busy = `1 - dIdle/(dKernel+dUser)`, and
      the first sample has no delta. GPU is the one signal Windows exposes ONLY through
      `PerformanceCounterCategory("GPU Engine")` (`engtype_3D` instances) — so it is strictly
      best-effort and **one failure disables it permanently for the session**: a machine without that
      counter will never grow one, and retrying every tick burns CPU to report CPU.
    - **A real settings page replaced a dead tab** — Winhanced's own card pattern ("מה מקבלים /
      מה המחיר"): system state, library state, art-cache maintenance, the desktop handoff, about.
      `NavField()` generalises the controller model so the SAME geometric navigation drives both the
      tile grid and the settings buttons.
    - **🔴🔴 THE CAPTURE INSTRUMENT WAS LYING, NOT THE APP.** Every screenshot came back MIRRORED,
      which reads exactly like a broken RTL layout. Cause: WPF sets **`WS_EX_LAYOUTRTL` (0x00400000)**
      for `FlowDirection=RightToLeft`, and GDI then mirrors all drawing through that window's DC — so
      `PrintWindow` renders mirrored while the on-screen window is perfect. **`SetLayout(memDC,
      LAYOUT_LTR)` does NOT fix it** (PrintWindow re-applies the window's own layout); the fix is to
      mirror the bitmap in software, gated on the ex-style bit. `C:\tmp\cap_window.py` now detects and
      un-mirrors automatically. **I did not "fix" the app** — the un-mirrored image proved it had been
      correct all along, and the same discipline then stopped me twice more (the tile grid and the
      stats pill both READ as LTR-ordered and both were verified correct by checking ORDER, not the
      picture).
    - **Craft defects only rendering could find**, each fixed: the stats pill inherited
      `HintGlyph`'s `Width="26"` and rendered as an empty circle; a growing readout (46 % → 100 %)
      **reflowed the CENTERED tab strip and made a tab click miss** (fixed with per-readout
      `MinWidth`); WPF's default dotted focus rectangle drew on top of our own focus plate (all five
      button styles now set `FocusVisualStyle="{x:Null}"`); filter chips stayed visible on a tab that
      cannot use them; and **`HorizontalAlignment="Right"` put the settings cards on the visual LEFT**
      — alignment is in LAYOUT space, which RTL mirrors. Emoji were replaced by **Segoe Fluent Icons /
      Segoe MDL2** (Winhanced's own declared icon font), and `GlyphClear` moved E894→E74D because
      MDL2's "Clear" is an ✕ indistinguishable from the close glyph beside it.
    - **🔑 THE THIRD SOURCE — Steam Big Picture, MEASURED from the installed client, not recalled.**
      The user asked to scan the installed Steam too and merge its advantages. Steam's own gamepad UI
      ships as ordinary CSS, so the design system is readable directly out of
      `steamui/css/chunk~2dcc5aaf7.css` — no decompilation, no assets copied. Recovered verbatim:
      the palette (`#0e141b` ground · `#23262e` surface · `#3d4450` raised · `#67707b`/`#8b929a`/
      `#b8bcbf`/`#dcdedf` text ramp · `#1a9fff` accent · `#de3618` destructive · `#ffd55f` warm),
      **`--gamepad-page-content-max-width: 1100px`**, the house easing
      `cubic-bezier(0.17, 0.45, 0.14, 0.83)`, and — the important one — **the `gpfocus` model**:
      focus INVERTS to white-on-black, kills the outline, and paints a `::after` plate BEHIND the
      element at 120 % × 132 %, which is why a focused Steam tile reads at couch distance where a
      border would not. That plate-behind-the-element idea is what the tile/settings focus here is
      built on. **UNIVERSAL: a closed app whose UI is a web view has its entire design system sitting
      in plain CSS — read the stylesheet before assuming you need to reverse a binary** (the
      counterpart to decoding Winhanced's compiled-XAML string table for the same purpose).
    - **🔴 A DISCONNECTED RDP SESSION BREAKS BOTH ELEVATION AND GUI VERIFICATION — and it looks like
      two unrelated bugs.** Two `Start-Process -Verb RunAs` installs returned *"The operation was
      canceled by the user"* within seconds, and a synthetic click on the settings tab silently
      missed. Neither is a code fault: **`GetForegroundWindow()` returned 0**, i.e. there is no
      interactive desktop, so the UAC consent prompt is auto-cancelled and synthetic input lands
      nowhere. The tell that named it: `tasklist` showed the session as **`RDP-Tcp#1`**. Diagnose
      with `GetForegroundWindow()` + the UAC policy keys (`EnableLUA`,
      `ConsentPromptBehaviorAdmin`, `PromptOnSecureDesktop`) before suspecting the installer.
      **UNIVERSAL: when an elevation prompt is refused instantly and repeatedly, check whether a
      desktop exists at all — and STOP GUI-driving, because every click after that is landing
      somewhere you cannot see.**
    - **The same disconnected session exposed a real hardening**: the window opened at its restore
      size (1600×900 at 130,130) instead of maximized, because WPF could not resolve a work area.
      `WindowState="Maximized"` in XAML is normally sufficient, so `OnLoaded` now RE-ASSERTS it — a
      no-op when it already won, and a 10ft shell whose first frame is windowed is simply wrong.
    - **Still open:** a controller smoke test and the in-app settings-button click-through (both
      need a live, connected session). **LOCAL ONLY — not published.**
  - **🔑🔑🔑🔑 REBUILT FROM THE PLANNING REPORT — the APPLICATION layer replaced, the primitives
    kept (2026-08-17, BUILD_ID `20260817002453`, DEV 263).** The user supplied
    `C:\Users\Nehoray_Cohen\Downloads\deep_analysis_report.md` (590 lines: a 5-part study of
    Winhanced + Steam Big Picture, ending in a feature map of 18 Winhanced must-haves + 14 Steam
    must-haves + 10 combined-design directives) and asked to restart Big Launch FROM it, realizing
    the whole vision, **plus a hard new constraint**: *"הביג-לאנץ יהיה נפרד מהלאנצ'ר הרגיל ולא יהיה
    מצב שאני לוחץ על כפתור מסויים והוא יחזור … החזרה והמעבר בינהם זה רק על ידי כפתור אחד שנמצא
    בהגדרות"* — one, and only one, way back.
    - **What was KEPT vs REBUILT is the whole judgement call.** The measured primitives
      (`Design/Tokens.xaml` = the Steam palette + `ContentMaxWidth 1100` + the house easing +
      Winhanced's type/spacing; `Design/Controls.xaml` = the merged focus model, Steam's plate
      BEHIND the card *and* Winhanced's accent glow, on Steam's own overshoot curve;
      `Interop/{Backdrop,Gamepad,Focus}.cs`; `Services/{Catalog,Telemetry}.cs`) are the expensive,
      already-verified part — rewriting them would have been pure regression risk. The
      APPLICATION layer on top of them was replaced wholesale. **A rebuild request is not a
      permission to discard measurements.**
    - **NINE new services, each an idea from the report re-implemented rather than copied**
      (the legal map forbids Winhanced's assets/logic, never its ideas):
      `LibraryScanner.cs` (the report's #1 item on BOTH lists — a hand-written Valve-KeyValues
      parser over `libraryfolders.vdf` + `appmanifest_*.acf`, plus Epic `.item` manifests, GOG and
      Ubisoft registry (both views), Xbox/EA folder roots and emulator ROM folders; enriched with
      the Hebrew catalog by install path or normalized title) · `AppSettings.cs` (per-game profiles
      = our OWN local "smart profile", set by this user on this machine) · `Sfx.cs` (10 cues
      **synthesized** as PCM at startup — Winhanced's 7 `.wav` files are assets and are off-limits)
      · `Sessions.cs` (Quick Resume via `NtSuspendProcess`/`NtResumeProcess` + a memory guard) ·
      `LaunchWatcher.cs` (our own 18 rules + `SetWinEventHook`) · `Storage.cs` · `Streaming.cs` ·
      `Capture.cs` · `DiscordRpc.cs` (the free `\\.\pipe\discord-ipc-N` path, never the gated
      Partner SDK).
    - **🔑 FULL ARTWORK WITH ZERO API KEYS — the find that made the report's art requirement
      free.** Steam already keeps `appcache/librarycache/<appid>/{library_600x900.jpg,
      library_hero.jpg, library_hero_blur.jpg, logo.png, header.jpg}` on disk. Reading the user's
      OWN cache gives box art, hero, blurred hero and logo per title, offline, with no SteamGridDB/
      IGDB key and no network call. **Before planning an art-fetch service, check whether the store
      client already cached the art locally.**
    - **🔴 THE SEPARATION RULE HAD TO BE ENFORCED STRUCTURALLY, NOT BY INTENT.** A first pass left
      FOUR routes back to the desktop launcher (Settings, plus a "פתח בלאנצ׳ר" CTA on the blade, a
      "ניהול התרגום" row, and a hub-update row in Downloads). All three extra routes were removed
      and replaced with a non-clickable `InfoRow` that REPORTS the translation state and says where
      it is managed. Verified the only way that can hold: **`grep -n "HandOff(\|OpenDesktop("` in
      `MainWindow.xaml.cs` returns exactly ONE call site** (the Settings row) plus the definition.
      Root `B`/Escape opens the quick menu instead of leaving. **UNIVERSAL: "only one way out" is a
      claim you must be able to GREP, not a rule you follow while editing — every convenience
      shortcut you add later is a second door.**
    - **The in-process React console was DELETED** (`frontend/src/biglaunch/`, its `#big` fragment
      route in `main.tsx`, and the `setBigLaunch(true)` fallback in `App.tsx`). It existed as a
      fallback for a launcher installed before the native shell shipped — but the installer now
      always ships `BigLaunch.exe`, two consoles inevitably drift, and the second one carried its
      own exit. A missing EXE now reports "התקן מחדש" instead of opening a different-looking
      screen. `Toggle`'s knob is mirrored deliberately (RTL: "on" = `HorizontalAlignment.Left`).
    - **⚠️ Build traps hit, both one-liners:** a XAML `<!-- ---------- header ---------- -->`
      separator is **invalid XML** (`MC3000: An XML comment cannot contain '--'`); and a
      `private void Activate()` on a `Window` silently hides `Window.Activate()` (CS0108) — renamed
      `ActivateFocused()`, since ours is about the focused ELEMENT, not the window.
    - **Verified:** `dotnet build -c Release` 0 warnings 0 errors · `dotnet publish` →
      `dist_biglaunch/BigLaunch.exe` **1,724,673 B** · `npx tsc -b` clean · `py_compile` clean on
      `main_eel.py`/`bridge.py`/`main_window.py` · BUILD_ID + both exe mtimes confirmed fresh before
      ISCC · `Output\TranslationManager-Setup-1.2.0.exe` **141,990,432 B** (BigLaunch.exe confirmed
      compressed into it) launched for the user's UAC.
    - **🔴 HONEST SCOPE — what the report asks for that is NOT physically reachable here**, stated
      rather than quietly dropped: **Dynamic TDP and Fan Control** (a signed ring-0 driver —
      PawnIO/RyzenAdj — explicitly out of scope for this project), **every Steam-ACCOUNT feature**
      (achievements, cloud saves, Workshop, friends, QR login — they need Steam's authenticated
      APIs, not a local file), **in-game overlay injection** and **game recording** (both mean
      injecting into another process), **VR**, **Lottie animations**, **ComputeSharp D2D1 pixel
      shaders**, and **Motiva Sans** (Valve's licensed font — Heebo is used instead, since Inter
      has no Hebrew at all). Everything else on both must-have lists is implemented.
    - **Still open (needs a human at the machine):** the controller smoke test of the rebuilt
      shell — entry from the launcher's home button AND from the `BigLaunch.exe` shortcut, tile
      focus/scroll, the blade, the quick menu, and the single Settings handoff. **LOCAL ONLY —
      not published.**
- **C1-C6 (Discord Rich Presence · cross-store badge · cover/hero art · price-in-₪ · Smart Launch
  Watcher · Sunshine/mDNS discovery) — queued, not started**, per the ordering + go/no-go detail in
  `unified_platform_PIPELINE.md`/`FEASIBILITY.md`. C3 (cover art) is the first to need a genuinely
  new project convention — no 3rd-party API key is stored anywhere in this codebase today; the plan
  calls for a git-ignored `.env`/local-JSON (the `website/.env` pattern), explicitly NOT the
  `keyring`-based `auth/storage.py` session-encryption mechanism (wrong tool — these are shared
  app-level public keys, not per-user secrets).
- **Stage 0 (the WebView2 POC) — not yet started.** Scaffold decided: WPF + `Microsoft.Web.
  WebView2` (not Tauri — on Windows, Tauri's `wry` backend IS a WebView2 wrapper, so a raw WPF host
  answers the identical question with far less toolchain). See `unified_platform_PIPELINE.md`'s
  Stage-0 checklist for the exact steps and the corrected pass/fail bar.

**§ What's already safe to build with ZERO new decisions (Stages 1-3, pure Python+Web, no second
base at all):** unified cross-store library (extend the already-partial `game_detector`) · price
comparison in ₪ (Steam Store API — public, no key — + IsThereAnyDeal; **not** scraping) · cover/
hero art (SteamGridDB + IGDB, free) · **turning ON Console-Mode/Big-Picture** (one flag + polish —
highest ROI, nearly free) · Smart Launch Watcher (Win32 WinEvent hooks blocking UAC/EULA/AntiCheat
popups — copy the IDEA, Winhanced's own implementation is closed) · Discord Rich Presence via
`pypresence` (free, **not** the closed Discord Partner SDK Winhanced uses) · detecting a self-hosted
Sunshine server via Zeroconf/mDNS + launching Moonlight (don't build streaming — just act as a
launcher for it).

**§ Legal/ToS map — from `winhanced_servers_report.md` (read in full), the single most load-bearing
fact-check for feasibility.** Winhanced's own servers split cleanly into 3 tiers: 🔒 **private/
closed** (update/OTA, the community "Smart Profiles" performance-profile backend, their internal
store-price-engine logic, their account/auth, their news feed) — cannot access, cannot replicate,
cannot self-host; 🌍 **public 3rd-party APIs Winhanced merely consumes** — SteamKit2 (open-source,
a full Steam client lib), Steam Web/Store API, IGDB API, SteamGridDB API, Discord RPC/IPC (free —
**not** their gated Partner SDK), the Fronkon Games Steam dataset (MIT-licensed, the literal seed
of their 167 MB `store_seed.db`, on HuggingFace/Kaggle), ES-DE emulator-detection rules (open,
GitLab) — all directly usable by us too, with zero relation to Winhanced; 🏠 **local tools
Winhanced merely orchestrates, self-hostable independently** — Sunshine+Moonlight (GPLv3, and
Winhanced auto-discovers a self-hosted Sunshine via mDNS, so it would detect ours too), RyzenAdj
(LGPL, TDP — Winhanced even ships ready-to-run `readjustService.ps1`/`readjust.py`/`pmtable-
example.py` directly on disk), LibreHardwareMonitor (MPL-2.0), PawnIO (GPL-2.0 kernel driver), RTSS
(freeware overlay), Chiaki (AGPLv3, PS Remote Play). **Explicitly forbidden to reproduce:**
Winhanced's own UI/compiled-XAML/"Living Glass" assets, the community Smart-Profiles dataset, the
actual implementation code behind Smart Launch Watcher (only its JSON config SHAPE is visible, not
the logic), their internal recommendation engine. Auto-claiming free games across storefronts =
account-ban risk (recommend notification-only, never auto-claim); an OCR/live-translation overlay
injected over an anti-cheat-protected (EAC/BattlEye) game = ban risk (ship only on non-anti-cheat
titles, labeled experimental — this is a genuinely separate research track from today's high-
quality OFFLINE baked-in translation, not a replacement for it).

**§ Realistic metrics correcting the earlier hyped docs (grounded plan §8).** Production already
runs Qt WebEngine + QWebChannel, not Eel/WebSockets (dev-only); "<20 MB RAM in-game", "0% FPS drop
during OCR overlay", and "100 GB mod injection in 3 seconds" are all fantasy figures — this file's
OWN documented mod-install times run seconds-to-**minutes** depending on the mod (Witcher 3 ~6 min);
target ₪, not $, throughout (Hebrew-speaking audience); the ONE metric worth actually chasing is
"does GPU-accelerated WebView2 give real smooth `backdrop-filter`" — answerable only by the Stage-0
POC above.

**Status (2026-08-16): research/planning complete and internally consistent — every checkable claim
verified true against the live repo. Development on Track B has NOT started; Track A's container
crack is done but its translation pass is at ~2% (13/772).** Next, per the user's explicit ask to
turn this into an actual plan: draft a concrete, staged implementation plan for Track B (gated on
the user picking an audience + a Base-2 tech, presented via Claude Code's plan mode for explicit
approval before any code changes — per this file's own standing rule "before large/destructive
changes, ask first"); separately, write proper `RECON.md`/`FEASIBILITY.md`/`PIPELINE.md` for Track A
so its translation phase follows this project's standard groundwork process.


## 🔌 THE `--shell` BRIDGE — the last 4 launcher-parity gaps closed in Big Launch (2026-08-18, LOCAL, NOT published)

The user stopped the design loop and scoped the finish: *"תעצור את הלולאה ותבנה את מה שנשאר"* —
the ~12 report items that are physically out of reach (TDP/fans, everything Steam-ACCOUNT, overlay
injection, recording, HowLongToBeat, RetroAchievements, 5-store price compare, back-paddle remapping)
are **explicitly NOT to be built** (*"אלה לא ייבנו — הם מתועדים ככאלה"*), and the **4 gaps vs the
desktop launcher** are: beta opt-in per mod · sign-in/personal-area/purchases · plugins · self-update.

**🔑 THE ARCHITECTURAL CALL: extend the EXISTING headless bridge, never re-implement in C#.**
`ModBridge` already drives the launcher as `TranslationManager.exe --mod install --game X` → one JSON
object per line on stdout. So `main_qt.py` gained a sibling verb group **`--shell
{all,account,plugins,beta,update}`** (`_shell_cli`, ~110 lines, runs BEFORE the single-instance guard
like `_mod_cli`) + **`biglaunch/Services/ShellBridge.cs`**. The account one is not a preference, it is
a **requirement**: the signed-in token lives in `session.enc`, encrypted with a key in the Windows
credential store and reachable only through the launcher's own auth stack — a C# copy would be a
second implementation of the crypto AND a second place a token can leak. The other three are the same
argument one notch weaker (the beta override outranks the global switch; the plugin host must be told
to re-read its state; editing their JSON from another process works until one of those rules changes).

- **🔴 A CAPABILITY PROBE IS PER-CAPABILITY, NOT PER-BRIDGE — and getting this wrong breaks the
  product's one hard rule.** `ModBridge.Available()` is NOT transferable to `--shell`: every launcher
  built before today has `--mod` and not `--shell`, and **an unknown switch does not error — `main_qt`
  falls through and OPENS THE DESKTOP WINDOW**, which is exactly the "only one way back" rule Big
  Launch is built around. So `ShellBridge` carries its own probe + its own on-disk stamp, and the
  `ct.Register(() => p.Kill(true))` in the runner is what makes that probe safe on an old build.
  **UNIVERSAL: when you add a second verb group to an existing CLI, the consumer needs its own
  capability probe — a switch the target does not know usually falls through to its normal startup
  rather than failing.**
- **🔴 ONLY PERSIST A *POSITIVE* PROBE.** A capability check can fail for reasons unrelated to the
  capability — an antivirus scanning a freshly-installed exe on its first run is the obvious one, and
  it happens exactly once, at exactly the moment the probe first runs. Persisting that "no" (keyed on
  the exe's identity) disables the feature until the file changes, i.e. forever. A "no" is simply
  re-asked next session; the cost is one short-lived process. Measured probe cost: **1.2 s**.
- **🔴 A SETTER MUST RETURN THE STATE, NOT `{ok}`.** `set_plugin_enabled` returned `{"ok": true}`
  while the console needed the list back — so the C# read it as a failure and toasted an error over a
  write that had SUCCEEDED. `set_mod_beta_override` already returned `get_update_prefs()`; following
  that existing convention is the fix. It matters beyond shape: **enabling a plugin can also INSTALL
  it**, so the answer can differ from the request in more than one field. The error path now also
  translates the launcher's own reason (`not-entitled` → "נדרשת רכישה…") instead of a generic failure.
- **🔴 ONE CALL, NOT FOUR (`--shell all`).** The expensive part is not the work, it is the PROCESS:
  every invocation imports the launcher's whole backend, so asking four questions separately paid that
  four times and left the console showing "טוען" for most of a minute. Each section is still
  independent — one that raises comes back `null` instead of taking the other three down.
- **🔴 A LATE ASYNC RE-RENDER STEALS THE USER'S PLACE.** These cards INSERT rows above existing ones,
  so a refresh that lands mid-scroll shifts every focus index and the ring jumps somewhere arbitrary.
  The refresh is gated on `AtPageEntry()` — focus still on the page's first row; a user who already
  started moving keeps their position and sees the values next time Settings opens. The read is also
  started at STARTUP (not on opening Settings), so it is normally there before the page is reached.
- **🔴 "בדוק שוב" MUST RESET THE PROBE.** The whole reason the console reports an available update is
  that the user goes and installs it — and the very next thing they do is come back and press refresh.
  A probe cached for the process lifetime answers from before the update and calls the NEW launcher too
  old, at the exact moment the feature should start working (`ShellBridge.Reset()`).
- **Purchases: only `status == "completed"` counts.** A pending or refunded row listed as owned is the
  app making a claim about the user's money the server would not back. A row with no status is kept —
  that is a shape question, not a refund.

**What is deliberately READ-ONLY, with the reason stated in the UI rather than quietly omitted:**
- **Sign-in.** OAuth needs a browser and a keyboard; a password over a CLI argument would be visible
  in the process command line to anything on the machine. The console SHOWS who is signed in and what
  they own, and the not-signed-in row says where to sign in. Gap #2 is therefore closed for *personal
  area + purchases* and **deliberately not for the act of signing in** — stated, not glossed.
- **Self-update.** Two independent hard blocks, not caution: the launcher's installer **kills
  `BigLaunch.exe` on purpose** (`installer.iss` `taskkill /IM BigLaunch.exe` — it must, to replace a
  file in the same folder the console holds open), and it asks for **UAC, which lives on the secure
  desktop where a controller cannot reach**. A button here would end the process mid-press and strand
  the user at a prompt they cannot answer. `start_launcher_update()` also spawns a **gevent greenlet**,
  which never runs in a CLI process that exits immediately. So it reports, and the one handoff acts.
- **Plugins: toggle only, never install** — acquisition stays where price, permissions and the full
  description can be shown. All 3 installed plugins (save-backup, game-copilot, community-compute) list.

**Verified against the BUILT exe** (not the source tree): `all` returns all four sections · `account`
returns identity + purchases · `plugins` set returns the full 3-plugin list · `beta` global toggle
round-trips `true→false→true` · per-game override cycles `{} → {gtav:true} → {gtav:false} → {}` — every
test restored the user's state exactly. `py_compile` clean; `dotnet build` 0 warnings 0 errors;
installer **142,340,040 B**, only the 2 known benign warnings.

- **⚠️ `dotnet publish` SKIPS THE COPY WHEN THE DESTINATION IS NEWER — including a CORRUPT one.** A
  killed ISCC left a partial **316,416-byte** `BigLaunch.exe` (should be 2,142,465); the next publish
  reported success and did not overwrite it, because it compares timestamps, not contents. **Verify the
  artifact's SIZE, not the build's exit code** — `rm` the destination to force a real write. Same family
  as [[never-background-build-exe-race]].
- **⚠️ "THE FILE EXISTS AND IS RECENT" IS NOT "THE BUILD FINISHED".** ISCC writes its installer
  incrementally: an `-newermt` check fired on a mid-write **83 MB** file that grew to 99 MB and finally
  **142 MB**. Wait for the PROCESS to exit, never for the artifact to appear.
- **🔴🔴 AN ELEVATED TARGET BLOCKS GUI DRIVING EVEN WITH A LIVE DESKTOP — and `SendInput` LIES about
  it.** The installer runs elevated, and the app it launches inherits that, so the console on screen
  was **high-integrity while my shell was medium**. UIPI then discards every synthetic keystroke —
  but `SendInput` still **returns 1 with `GetLastError()==0`**, because it injects into the system
  queue successfully and the message is dropped later, at the integrity boundary. Four Tab presses
  and an Escape did nothing, with no error anywhere, which reads exactly like "my key binding is
  broken" and sends you to debug a handler that was never reached.
  **The decisive probe is `PostMessage(hwnd, WM_KEYDOWN, …)` → returns 0 with `GetLastError()==5`
  (ACCESS_DENIED)** — that is the integrity boundary answering directly. Two corroborating tells,
  both cheap: `Get-CimInstance Win32_Process` shows an **empty `ExecutablePath`**, and
  `taskkill /F` answers **"Access is denied"**.
  ⚠️ **This is NOT the documented disconnected-RDP case** — `GetForegroundWindow()` returned the real
  window here, so the "is there a desktop at all?" check passes and tells you nothing. Different
  cause, identical symptom, different probe.
  ⚠️ And the elevated instance ALSO holds the single-instance mutex, so a newly-built copy exits
  quietly on launch (correct behaviour) — meaning **the window you are looking at is the OLD build**
  ([[stale-elevated-instance-fakes-no-change]]). Closing it needs elevation, i.e. the user.
  **UNIVERSAL: before driving any GUI synthetically, prove the target is reachable — `SendInput`
  succeeding is not evidence, and an elevated target makes both the input AND the "did my build
  land" question unanswerable from a normal shell.**
- ⚠️ **A defensive fix is not a diagnosis.** `new Mutex(...)` throwing `UnauthorizedAccessException`
  on a higher-integrity owner is real and worth catching (the desktop launcher hit exactly that) —
  but measuring it here returned **183 ALREADY_EXISTS, not 5**, so the catch never fired and did not
  explain the vanished process. Shipped as declared defence with the measurement written next to it,
  rather than as the answer. **Measure which failure mode you actually have before crediting a fix.**


## 🔬 Winhanced — full reverse-engineering study (2026-08-16, read-only; `winhanced_deep_analysis.md`)

The user asked for an exhaustive 5-part engineering study of Winhanced (architecture · features ·
UI/UX · safety · replication blueprint). Delivered as **`winhanced_deep_analysis.md`** (repo root).
**Nothing was installed, run, or modified** — including the 0.9.9.7 installer the user supplied.

- **🔴🔴 THE PRODUCT IS PROTECTED BY A JIT-HOOK PROTECTOR — and knowing exactly what that destroys
  is the whole game.** Namespace `Xy9Ac91TTPsPd5mC4M`, bootstrap `CIbUAhPuLA8nvrkWee.ExGYDduSGq()`
  in every static ctor, 6 obfuscated `libclrjit` P/Invokes, `NoInlining` on every member. Present
  in **all four** managed assemblies (`Winhanced.dll`, `.Shared.dll`, `DynamicTDP.dll`,
  `HardwareControl.dll`) and in **both** 0.9.9.3 and 0.9.9.7.
  **SURVIVES (citable):** namespaces · type names · hierarchy · interfaces · method names +
  full signatures · property names · **enum names AND values** · **attribute arguments**
  (`DllImport("user32.dll")`, `ComImport`, `Guid("…")`, `MarshalAs`) · `const` values.
  **DESTROYED:** every method body (→ `return null;`) and **every in-method string literal**.
  Measured, not assumed (`C:\tmp\probe_strings.py`, 27 probes × 2 encodings × 2 versions):
  `SOFTWARE\Microsoft\Windows`=0 · `Win32_VideoController`=0 · `powercfg`=0 · `schtasks`=0.
  ⇒ **Exact registry paths / WMI queries / PowerShell command lines are NOT statically
  recoverable** — say so instead of inventing them. **UNIVERSAL: measure the protector's boundary
  with a probe-string count BEFORE promising any answer that depends on string literals; a
  decompile that looks readable (real type names) can still have 100% of its bodies encrypted.**
- **🔑🔑 THE HIGHEST-VALUE ARTIFACT WAS A `.xml` SITTING BESIDE THE DLL.** `whservice/DynamicTDP.xml`
  (16 KB) is the assembly's **XML documentation file** — a full `<summary>` for every type and
  member, i.e. the algorithm in the author's own words, **completely unprotected** (a protector
  encrypts IL, never the doc file the compiler emits next to it). It handed over: RTSS frametime is
  the sole target authority while CPU/GPU pressure is a **veto that never raises power**; GPU is the
  primary signal above 25% with aggregate CPU as fallback and max-core CPU **diagnostic only**; a
  recent-median GPU window so "one isolated peak cannot create a hidden floor"; a latch because
  "sampler updates do not arrive atomically"; **fail-OPEN when telemetry is missing "so telemetry
  cannot become a hidden floor"**; a 250 ms / 1,024-entry allocation-free rolling window; a write
  pump that "never cancels or overlaps" an active transaction; epoch+revision+lease transaction
  identity; a universal **500 ms** settle floor. **UNIVERSAL: before decompiling a protected
  assembly, `ls` its directory for a same-named `.xml` — it can be worth more than the decompile.**
- **🔑 AN INSTALLER IS A PRISTINE COPY — use it when the live install carries your own patches.**
  The installed 0.9.9.3 has our Track-A Hebrew proof in 4 files (`MainWindow.xbf` decoded with our
  own `שחק`/`חיפוש` in it, which I initially mistook for the vendor's strings). The 782 MB
  `Winhanced-Installer-0.9.9.7.exe` is an **NSIS PE + appended ZIP** → `7z x` extracts it read-only,
  giving both a clean corpus and a 4-versions-newer diff. **Never analyse a target you have already
  modified without diffing against the pristine source.**
- **⚠️ TWO ARCHITECTURAL FACTS THAT KILL THE "IT MUST BE INJECTING" ASSUMPTION** (both matter for
  our own launcher's overlay ambitions): (1) **`CustomCapability.SCCD` declares
  `Microsoft.appCategory.gamingHome_8wekyb3d8bbwe`** — the official Windows capability that lets an
  app register as a gaming-home Shell (what the Xbox full-screen experience uses); `Winhanced.
  Identity.msix`+`.cer` is the **sparse/identity package** that gives a Win32 app the package
  identity required to claim it. (2) **The HUD is an official Xbox Game Bar widget** —
  `AppxManifest.xml` declares `uap3:AppExtension Name="microsoft.gameBarUIExtension"`,
  `GameBarWidget Type="Standard"`, 460×625, publisher `CN=Joseph Rizzo`. And
  `WinhancedOverlayBridge.dll` lives in `Assets/RTSS/` beside `.ovl` files that are plain INI
  declaring `Provider=AIDA` / `ID=WINHANCED_OVERLAY_MODE` ⇒ it publishes to RTSS over the
  **AIDA64-compatible shared-memory** contract. **There is no process injection and there are no
  hooks anywhere in the product** — three independent proofs.
- **The hardware layer is the real product** (`Winhanced.HardwareControl.Backends`, ~95 types, all
  names survive): AMD **PawnIO** + **SMU PM-table** · Intel **MSR/RAPL** · ASUS **ACPI/ATK + DSTS +
  SMU** · Lenovo **GameZone WMI + EC** · MSI **WMI/ACPI**, unified by
  `HardwareTdpRoute {GenericAmdPawnIo, AsusAtkAcpi, AsusGz302Wmi, MsiClawWmi, LenovoWmi,
  LenovoSmuPawnIo, AsusAllySmuPawnIo, GenericIntelMsrPawnIo}`. **The safety discipline is what is
  worth copying:** `DeviceIdentityConfidence {Unknown, HintOnly, Family, Model, Variant, Ambiguous}`
  gates every write, and the result is verified in four grades
  (`TdpWriteVerification {Rejected, BackendAccepted, RegisterVerified, ResponseValidated}`) plus a
  `PackagePowerAgreementPolicy` that compares **measured** package power against the request.
  ⚠️ **No System-Restore-point or registry-backup mechanism was found anywhere** — stated as an
  absence of evidence, not as a claim that none exists.
- **UI/effects, from the XBF string tables:** `Views/Diagnostics/GlassLabPage.xbf` is an internal
  **"Glass Lab — shader pipeline diagnostic"** with `BaselineCanvas`/`ShaderCanvas`/`RimShaderCanvas`/
  `MinimalRimCanvas` over `Microsoft.Graphics.Canvas.UI.Xaml` ⇒ the "Living Glass" is **Win2D
  `CanvasControl` + ComputeSharp D2D1 pixel shaders**, with a dedicated **rim** shader. Design tokens
  (`Resources/DesignSystem.xbf`, 75): **Inter** Light/Medium/SemiBold at 2/6/12/14/16/18/20/22/24,
  Segoe MDL2 + Segoe Fluent icons, `AcrylicBrush` (Tint/TintLuminosity/AlwaysUseFallback),
  explicit Light/Dark brush pairs, `SystemAccentColor`. **The UX pattern worth stealing:** every
  toggle card in `PerformanceSettingsPage` carries **"What you get: / Trade-off: / Alternative:"**
  plus a demo video — it states the COST of each change, which is what separates a credible system
  tool from an "optimizer".
- **⚠️ A 14-agent Workflow spent 8,985,002 subagent tokens and returned `{"reports":[]}`** — every
  agent hit the session limit. Doing the extraction personally took one pass. Same lesson as the
  AC Unity round: **the project already owned the reader** (`games/winhanced/work/xbf.py` from
  Track A decoded all 113+99 XBF).
- **Status: research only.** No project code changed; Track A (the Winhanced Hebrew localization,
  ~2% translated) is untouched and still needs its `RECON/FEASIBILITY/PIPELINE.md`.



## 2026-08-19 — Big Launch is now a Windows "home app" (מצב XBOX)

The ask: Big Launch should appear in **הגדרות ‹ משחקים ‹ מצב XBOX ‹ "בחר אפליקציית בית"**, where
Windows previously offered only `ללא / XBOX / Winhanced`. **Big Launch alone** - the regular
launcher was registered too in the first pass and then deliberately removed: a home app is what the
full-screen experience boots INTO and drives with a pad, and a mouse-first window is the wrong thing
to offer there.

**The mechanism** (found by inspecting how the one working third-party entry is registered — the
sparse package's manifest, which is public metadata, not its code):

- The picker lists exactly the packages holding the custom capability
  `Microsoft.appCategory.gamingHome_8wekyb3d8bbwe`. Verified as a set: `Microsoft.GamingApp`,
  `Winhanced`, and now Big Launch — nothing else on the machine has it.
- An unpackaged Win32 exe can join that set through a **sparse (external-location) package**: a
  manifest + tile art + `uap10:AllowExternalContent`, `-ExternalLocation` pointing at the real
  install folder. No code is packaged and no file moves.
- The app must be **mediumIL**. FSE activates the home app through package identity and cannot
  elevate — `requireAdministrator` fails to launch and the home app silently does nothing.
  `BigLaunch.exe` is `asInvoker`, so it is pointed at
  directly (Winhanced needed a `WinhancedFseBridge.exe` shim for exactly this reason).

**Four traps, each of which cost a failed registration or a wrong-looking entry:**

1. **The SCCD is read from the EXTERNAL LOCATION, not from the manifest folder.** The deployment
   log names the pattern outright — `CC file pattern C:\...\*.sccd` — while the PowerShell error is
   only "The system cannot find the file specified" with no file named. `Get-AppPackageLog
   -ActivityID <id>` is what turns that into a one-line diagnosis.
2. **The descriptor must be plain.** An SCCD with a leading XML comment fails with `0x8007007A`
   ("data area too small"). The accepted file is 408 bytes, CRLF, no comments.
3. **The tile art is read from the external location too.** Registered without an `Assets\` folder
   in the install dir, the picker draws the generic placeholder even though the package folder holds
   the logos. Proven in both directions on one variable: rename the folder away and re-register ->
   placeholder; put it back and re-register -> our logo.
4. **A re-register does NOT relocate the package.** Registering the same identity from a new folder
   reports success and leaves `InstallLocation` on the old one — so a first run from the source tree
   quietly keeps the entry tied to the source tree. Only `Remove-AppxPackage` then register moves
   it. `register.ps1` now detects this and removes first.

**What shipped:** `tools/msix/biglaunch/` (manifest + tile art + dev SCCD) and
`tools/msix/register.ps1`; `installer.iss` copies them to `{app}\msix`, drops the SCCD in `{app}` and
the tile art in `{app}\Assets`, registers on install (`runasoriginaluser` — packages register per
user) and unregisters on uninstall.

**The distribution caveat:** the SCCD is the development form (`AllowAny` + catalog `FFFF`), which
Windows honours only on a developer-unlocked machine (`AllowDevelopmentWithoutDevLicense=1`, true
here). Shipping the home-app entry to ordinary users needs a Microsoft-issued SCCD bound to our own
publisher certificate. Registration is best-effort and swallows its own errors, so a machine that
cannot have it simply installs without it.

**Verified:** the entry appears in the picker with the real Big Launch logo, and activates through
package identity (`shell:appsFolder\<PFN>!App` starts the real exe — the same path FSE uses);
registration lives entirely under `C:\Program Files\Translation Manager\msix`, so the repo can move.

**Watch this:** selecting a newly registered home app is not the only thing that changed — after the
registration, **"היכנס למצב XBOX בעת ההפעלה" came back ON** (it was off before), i.e. the machine
would boot into the shell. Nothing in our code touches that toggle; Windows appears to arm it when a
home app is chosen. Check it after any registration round.

## 2026-08-19 — glass, motion, and the core the shell was burning

**What was asked:** make every floating surface look like the reference's frosted glass, smooth
every transition, give the audio/Bluetooth panels the reference's full option set, and make the
size sliders look like the volume slider (with a knob).

**Glass is a RELATIONSHIP, not a fill.** A translucent panel over a sharp screen is a dirty window;
what makes the reference read as glass is that the shell BEHIND it is blurred and pushed back. So
`Frost()`/`UpdateFrost()` (`MainWindow.Glass.cs`) blurs `Chrome` (and `Blade`, when something opens
over it) while any overlay is up, and the panel fills in `Tokens.xaml` (`GlassPanel`, `GlassEdge`)
stay genuinely translucent instead of creeping toward opaque every time something is hard to read.
The blade's action list was an explicitly opaque plate for exactly that reason — with the frost
behind it, it became glass too.

- Frost is hooked to the HOSTS' `IsVisibleChanged`, not to the thirteen call sites that open
  something. `UpdateFrost()` derives the answer from what is visible, because the layers stack (a
  confirmation over the blade over the shell) and a boolean gets the two-deep case wrong.
- The blur effect is **removed** on close, never left at radius 0 — a zero-radius effect still taxes
  the layer every frame.

**Motion:** one house curve (`KeySplineEase` over the measured `EaseDecel`/`EaseStandard` splines),
arriving soft and leaving brisk; panels now materialise (scale 0.96→1 + rise + fade) instead of
appearing.

**🔴🔴 THE REAL FIND — the shell idled at ~104% of one core doing nothing.** Measured, then
bisected: with every animation disabled it was still ~85%, which ruled out the visuals. The cause
was `Interop/Gamepad.cs` polling **all four XInput slots plus four winmm joystick ids, 60 times a
second**, with a comment claiming it "costs nothing when no pad is attached" — the early-out is the
RESULT of the query, not a way to avoid it, and querying an empty slot goes to the device layer.
Now: a full sweep twice a second, and once a slot answers that one slot is read at the full 16ms.
**104% → 26%.** Capping the ambient bloom's animations (`DesiredFrameRate` 20 for the drift, 10 for
the hue walk — a 22-second colour cycle does not need 60 samples a second) and caching the blurred
background layers took the animated state to ~33%.

**Audio panel: the options were not missing, they were failing silently.** `AudioMixer.OutputDevices()`
and `Sessions()` returned empty because `new MMDeviceEnumerator()` threw
`InvalidCastException: Unable to cast object of type 'MMDeviceEnumerator' to type 'MMDeviceEnumerator'`
— **two `[ComImport]` types with the same CLSID/IID in one assembly** (Volume.cs and AudioMixer.cs
each carried their own private copy, deliberately, "so the vtable sits beside the code that calls
it"). The runtime binds one COM identity to whichever it sees first; the loser dies. Now declared
once in `Interop/CoreAudio.cs`. What found it was not more reading — it was `AudioMixer.LastError`
plus an empty-state row that says WHY a section is empty, i.e. giving the failure a place to appear.

**Also:** output device is now one row that opens a picker (a machine with four outputs used to push
the mixer off the panel); Bluetooth opens with a state card and its search button becomes
"עצירת החיפוש" while scanning (with a generation counter so the late result is discarded); device
names, SSIDs and percentages are LRM-fenced (they rendered as `%30` and `(Speakers (V18`).

**Home screen (same day, separate ask):** one screenful, no scrolling — the "שוחקו לאחרונה" shelf
plus four destination tiles stretched into the remaining height. The "הספרייה שלך" and "זמין בעברית"
shelves are gone; two of the four tiles open the same lists.

## 2026-08-19 (later) — "the floating windows are not stable at all"

Read off a 66-second screen recording, frame by frame (contact sheet → dense sheet around each
transition → full-res frames). Four separate faults were doing it:

1. **The panel jumped across the screen on its own.** `AnchorToChip` re-measured the header chip on
   EVERY refresh — and the header redraws itself every two seconds for the live CPU/RAM readout,
   which replaces the chip element. The panel then held an element that was no longer in the tree,
   `IsVisible` came back false, and the catch-all fallback parked it in the opposite corner: open it
   on the left, touch nothing, and two seconds later it had moved. **The position is now computed
   once at open and frozen until close** — a better fallback would not have fixed it, because the
   panel must not move at all while it is up.
2. **Every arrow press rebuilt the whole card**, so holding a direction made the window pulse
   (entrance animation replayed) and shift (re-anchor). A level change is not structural, so the row
   now writes its new value into the controls it already owns; only a mute (glyph + title) redraws.
   A refresh no longer replays the entrance animation either.
3. **The per-app list re-ordered itself** between refreshes — Windows returns sessions in
   enumeration order — so the row being aimed at moved out from under the cursor. Sorted by name.
4. **The knob was clipped into a half-circle at 0% and 100%**, exactly the two values people sit at,
   and the value bubble was hung on a negative margin outside the row where the focus ring sliced it.
   Both now live inside the row (half-knob inset, and the track's top inset is the bubble's room).

Verified by measuring frame-to-frame diffs while holding a direction: the changed region stays
inside the slider strip (y 157..209), i.e. the card itself does not move.

**Elastic slider** (asked for alongside, after reactbits' ElasticSlider): the fill is now an
animatable attached property (`FracProperty`) whose callback writes the two star column widths — a
`GridLength` cannot be animated, which is why a value change used to jump. Steps settle with a light
`BackEase` overshoot, the track thickens and the knob grows while the row is in use, and a press that
cannot move the value (right at 100%) stretches the track from the opposite end and springs back
instead of doing nothing.

**App icons** in the per-app mixer: `Interop/AppIcons.cs` resolves each session's process path with
`QueryFullProcessImageName` (NOT `Process.MainModule`, which throws for any process this one cannot
open for VM read — i.e. most of them) and extracts the shell icon, cached by path, `DestroyIcon`'d
after conversion because `CreateBitmapSourceFromHIcon` copies the pixels but does not own the handle.

## 2026-08-19 (evening) — the batch read off screenshots

**Sliders.** Pinned LTR to cure "the right arrow moves the handle left", then un-pinned when the
answer came back: in a Hebrew UI the bar belongs right-to-left with everything else, and it was the
ARROWS that were wrong. They are mirrored now — a direction key promises a DIRECTION, not an
arithmetic sign, which is what Windows does for its own mirrored sliders. Also: press-and-drag with
the mouse (a slider you cannot hold is the one thing every other volume control allows); mute moved
off the row and onto the speaker mark, because reaching for the track used to silence the thing you
were setting; the pad keeps A on the row.

**The knob was sliced in half at 0% and 100%** — the two values people actually sit at. It hung half
its width past the boundary between the filled and empty columns, and at either end that boundary IS
the track's edge, so half of it was arranged outside the cell. Widening the inset did nothing
(the overhang is measured from the CELL). Fixed by giving the knob **its own fixed middle column**:
`[filled*][knob px][empty*]`, so it is never outside anything. The value bubble rides the same
column — inside a `Canvas`, because a child of a 20px cell is MEASURED against 20px and the read-out
came out squeezed to a sliver.

**🔴 The pale blurred screen before the opening film was not a splash.** `Backdrop.Apply` makes the
WPF composition target transparent so DWM's acrylic can show — and between that call and this
window's first painted frame, what shows through is the blurred DESKTOP. Deferring the backdrop
request to `ContextIdle` (after layout and the first render) fixes it. Verified by watching the
first second of startup: the first frame is now `mean = 0.0`, i.e. pure black.

**"There is a delay switching menus"** — measured before changing anything: building a screen costs
**0–12ms** (205ms once, the first home render). So the entire wait was the transition I had
lengthened to 260ms earlier the same day. Back to 170ms with the opacity leading at 110ms. Smooth is
not the same as slow.

**"זמין להתקנה" was a lie for anything still in production.** The catalog has always carried
`availability`; nothing read it. A mod that is not `available` now states its stage (בתהליך תרגום,
בבקרת איכות, בקרוב) and links to the site instead of offering a download that does not exist. The
tile badges follow the same rule.

**Missing covers** (Ubisoft titles with no Steam cache and no hub entry): the tile now falls back to
the game's own executable icon — not box art, but local, instant, and the mark the user already
associates with the game. `GameIconPath` picks the biggest .exe in the install root, skipping
installers/crash handlers.

**Home screen:** more covers in the shelf, the four destinations back to a strip (stretching them
into the lower half made four shortcuts dwarf the library), and a "מה חדש" row underneath — wide,
short cards carrying the linked game's artwork blurred behind the text, cached so the blur is
rasterised once rather than per frame of a scrolling strip.

## 2026-08-20 — the tuned sizes became 100%

The four multipliers the user had dialled in (tiles 120%, header 130%, text 120%, hints 125%) are
now the code's own baseline (`MainWindow.Sizes.GroupBase`), so "רגיל" opens at the size the shell was
actually tuned to on a television and every percentage above it is genuinely larger. Existing
settings files are rebased exactly once (`AppSettings.SizeBaseline`): the multipliers that PRODUCED
that look are reset to 1.0, so nobody's screen moves on the day it shipped.

**What that broke, and why the fix took six rounds:** at the bigger baseline the home screen no
longer fit, and the "מה חדש" band came out sliced. Three separate causes, each hidden behind the
next:

1. **A star row inside a ScrollViewer is not a share of the frame.** The page host measures its
   child against infinite height, so `Height=Star` resolves to the content's own height and the last
   band simply lands below the fold. Same family as the horizontal shelf, where
   `HorizontalAlignment` could not work until the holder was given a real width.
2. **The footer legend is drawn OVER the page, not beside it** (deliberately — it must stay above
   every layer), so the host's height includes the strip the footer covers. A page that trusts that
   number puts its last band underneath it. The band was never short; it was hidden.
3. **Auto rows take what they want.** Even with the height right, the two rows above claimed the
   remainder. All three bands now get explicit measured heights, and the covers - the only elastic
   band - shrink until everything fits.

**🔴 And the reason several "verified" rounds were worthless:** the elevated mirror that copies the
build into Program Files exited on its own 8-hour deadline, while the cycle script's freshness check
compared file SIZE - and consecutive builds of the same code are usually the same size. It kept
printing `mirrored=True` against a stale exe. Now it compares `LastWriteTimeUtc` and says so out
loud when it falls back to the dev copy.

## 2026-08-21 — mining Winhanced's 22-version changelog

The user supplied `WINHANCED_VERSION_REPORT.md` (their public release notes for 22 versions) and
asked what we can learn. The boundary held throughout: their notes tell us WHAT KIND of thing breaks
in a shell like this and WHAT users needed; every fix below is our own code.

**The pattern their bug list keeps landing on — and we had the same shape:**

1. **A failed enumeration adopted as truth.** They shipped "a failed or interrupted sync can no
   longer delete, hide, empty or duplicate your games" TWICE in one month, plus "a failed scan can
   no longer change install status" and "playtime no longer resets to zero after a failed fetch".
   Ours: `ReloadLibraryAsync` assigned the scan result straight over the library, and EVERY failure
   path returned an empty list — one locked registry key and the library was gone until the next
   good scan. Now `LibraryScanner.LastScanComplete` reports completeness, a complete scan is adopted
   whole, and a partial one is unioned with what it could not look at (and says so).
2. **Watching the wrong process.** Their "a game reported as closed seconds after launching" and
   "detection through nested launchers". Ours was worse: for a `steam://` launch `Process.Start`
   returns null, so `Alive` was false on the first 2-second tick — every store-launched title
   "closed" immediately, banked no playtime, and could not be suspended. Sessions now adopt the real
   process from under the game's install folder and get a 90-second appearance window.
3. **The shell hiding the thing that is blocking it.** Their "Steam pop-ups that block a launch now
   surface instead of the app looking stuck". Ours is a maximised borderless window: if the game has
   not appeared after 8s AND we are still the foreground window, we minimise and say why. And when a
   game exits we come back (`RestoreShell`), instead of leaving the user on the desktop.
4. **Focus that forgets where you were.** Their "Back returned to the first tile instead of the game
   you came from". Ours did exactly that — `_focusTag` only matched string tags and a tile's Tag is
   the game object. Added `_focusGameKey`.
5. **Re-decoding art on every render.** Their "covers are cached and no longer re-decoded when
   scrolling back" and "faster library load". Ours had no image cache at all: every screen build
   re-read and re-decoded every cover. Measured after the fix: a home rebuild went from 250-400ms to
   5-16ms.
6. **Settings that do not always save.** Their "fixed settings that sometimes did not save". Our
   `SaveThrottled` DROPPED a write inside its window rather than deferring it - the last press of a
   drag is exactly the call with nothing after it. Now the burst still coalesces and a trailing write
   always lands.
7. **A pointer parked on a 10ft screen.** They fixed cursor hiding twice. We never had it: the
   pointer now hides on pad input and returns on a real mouse move (with a 3px threshold, because
   WPF raises MouseMove for a pointer that has not moved when the visual under it changes).

**Checked and already right:** playtime is forward-only; hide-not-delete with a restore screen;
scroll resets on filter change; a clean close takes 283ms (they had a 10-second shutdown freeze);
rapid Back hammering does not crash; `SaveThrottled` on exit is covered by `OnClosing`.

**Not for us:** everything TDP/fan-curve/RGB/handheld-hardware, emulator and ROM libraries, console
Remote Play, the store/wishlist/price-comparison stack. Different product, different catalog.

**🔴 A note on instruments:** late in the night every screenshot came back black or uniform grey and
it read exactly like "the shell renders nothing". The app was fine - the display had powered down
(and the primary adapter is a Parsec virtual display), so PrintWindow and BitBlt were handing back
placeholder surfaces. `std == 0` across a whole screen is not a UI state. Verified instead through
the app's own trace log (build times, row heights), `errors.log` and a stress pass.

### What the 15-agent mining run found on top of that

372 changelog items → 372 generalized lessons → each checked against our source by six mappers →
139 claims → three skeptics refuted 35 → **111 survived**. Two of the refutations were the workflow
catching up with fixes made the same night (the session lifecycle and the blade focus), which is a
fair check on the method. Acted on immediately:

- **🔴 The pad drove the shell while a game was in front.** `OnPad` never asked whether the shell was
  active, so during a game the stick walked an invisible focus ring and A activated whatever it was
  sitting on. Now deaf while a session runs and we are not in front — deliberately NOT a bare
  `!IsActive`, because Windows hands activation away for reasons (a toast, an installer) that would
  otherwise strand someone holding a controller.
- **"שוחקו לאחרונה" was not sorted by recency** — it took the first N of the LIBRARY order
  (installed-first, favourites floated) and called them recent.
- **Prices lost their agorot**: `PriceCents / 100` is integer division, so 5350 displayed as "53 ₪"
  on the one screen that quotes a price. One formatting helper now, so no call site can round again.
- **"Clear the image cache" cleared a folder nothing writes to** — `Catalog.ArtDir` versus the
  `%LocalAppData%\BigLaunch\art` that `ArtCache` actually mirrors into. It always reported 0 files
  while the real cache grew without bound.
- **The purchase page opened behind a maximised borderless window** — the same lesson `HandOff`
  already carried; both blade routes minimise now.
- **The system panels had no controller route at all.** Volume, network and Bluetooth live behind
  header chips that are deliberately outside the focus map, and nothing else opened them: with a pad,
  on a couch, there was no way to reach the Wi-Fi list — the exact situation the Bluetooth panel's own
  comment gives as its reason to exist. Three rows in the quick menu.
- **Art arriving in the background stole the focus ring** every 450ms while the user was browsing.
- **Per-tile shadows**: measured 2969ms → 2438ms of CPU for the same scroll, an 18% tax for an effect
  that is invisible on a bright cover. A hairline rim was tried as a middle ground and measured
  2812ms — a border is another draw per tile — so the card carries nothing at rest, which is what
  both reference shells do.

Still on the list from that run (not done tonight): a `_modBusy` guard and a timeout/cancel for mod
installs; dedupe folding Manual/Emulator entries into a store record by install directory; the
library filter not persisting; "not installed" shown while a game is merely updating; a Discord RPC
supervisor; `_sessions.ReleaseAll()` before sleep/shutdown; and a real re-arm on resume.

## 2026-08-21 (afternoon) — closing the deferred list ("מה נשאר בשביל 100%")

The user asked what was still open **from rounds where I had stopped short** — items that were
documented and skipped rather than hard. Everything below was implemented and verified in one pass.
All LOCAL. Nothing published.

### The mod-install path was the worst of them

`RunMod` had three separate holes, and they compound:

1. **No busy guard.** The row stays clickable behind the progress card and the pad auto-repeats, so a
   double-press started a SECOND headless applier on the same game folder. The second one can back up
   a half-patched archive as if it were the original — which is how a "revert" restores a broken game.
   The guard is on the worker (`_modBusy`), not on the row, because the blade and the quick menu both
   reach the same call.
2. **No way out.** `_dialogBack` was `() => { }` on purpose (an interrupted patch is dangerous), but
   "you may not leave" was implemented as "there is no exit at all": a worker that hung left a frozen
   progress bar with every button dead. B now CANCELS through a `CancellationTokenSource`, which kills
   the worker so the launcher's own journal can roll back, and the card carries the same action as a
   real button.
3. **🔴 A redirected stderr that nobody read.** `RedirectStandardError = true` and not one read: the
   child blocks the moment it writes past the ~4 KB pipe buffer, which is exactly what a Python
   traceback does. **The one case that most needed an error message was the one case that froze.**
   It is drained on its own task now, the tail is kept, and a worker that exits without printing its
   `{"ok": …}` verdict reports the last stderr line or its exit code instead of a bare "הפעולה נכשלה".

Plus a stall watchdog: **4 minutes of SILENCE**, not a total deadline — a 4 GB install on a slow disk
legitimately takes many minutes, and a deadline measured from the start would kill the one install
that needed the time. What is never legitimate is emitting nothing while the worker reports a phase
line per step.

### The mapping screen made every other screen lie

Every `SetHints` call names a literal button — `("A", "בחירה")` — which was true right up until the
controller-mapping screen let someone move "בחירה" onto Y. From then on the footer promised A on every
screen while A did nothing. The tokens are now read as the DEFAULT binding they were written against,
resolved back to a `ShellAction`, and drawn as whatever button currently carries it (`LiveToken`).
The keyboard prompts go through `KeyFor` for the same reason. `HintAction` was also a second,
hand-copied implementation of five commands that had already drifted from `InvokeAction`; it now
routes through it.

### Everything else on the list

| What | Why it was wrong |
|---|---|
| "לא מותקן" on a game that is patching | Stores clear the installed bit while an update downloads, so a library turns into a wall of "not installed" the morning after a patch day — and the row underneath offers to install it AGAIN. `UpdatePending` was already read off the manifest; it never reached the screen. |
| Two badges clipped at the tile edge | A content-sized `StackPanel` aligned to the edge grows past the cover and gets clipped. A `WrapPanel` stretched to the cover width has a real boundary to wrap against. |
| The footer said "N מושהים" | It counted `Sessions.Count` — **every** session — and labelled it "suspended". A game that was merely running was reported as parked, on the one line whose whole justification is that it can never be wrong. Running and suspended are counted separately now. |
| Floating cards at 1280×720 | Widths were hardcoded (940/900/760…) against a 2560px window; the confirm row of a destructive dialog could sit off-screen. `CardWidth(want)` keeps the number as the INTENT and gives the viewport the final say. |
| B on the size sliders | The sliders REPLACE the settings rows in place (deliberately — you must see the shell resize while dragging), so the shell did not know it was a level deeper and B threw the user out to Home. |
| The library filter | The sort was remembered and the filter was not. Restored on load only if it still names a live collection, so a deleted one cannot come back as a permanently empty library. |
| Manual + store duplicates | The install-dir comparison was verbatim, so one trailing backslash made two games. Normalised through `Path.GetFullPath`; the store record wins the merge (it has the launch URI) but a manually-typed NAME is kept. |
| Discord connected once, at boot | Order of launch decided whether the feature existed at all: a shell that starts with Windows, before Discord finishes loading, had no rich presence for the whole session. Backed-off retry (15s → 5min), reset on success, re-armed the moment the toggle is switched on. |
| The first frame | An empty library and an unfinished scan looked identical, and only one of them is bad news. Home is now drawn BEFORE the store sweep with placeholder tiles ("סורק את הספרייה…") in the row's real shape. |
| GPU % on a laptop | Summing every "GPU Engine" instance adds an idle iGPU to a busy dGPU and calls the total "the GPU" — unstable, because Windows moves work between them. Grouped by adapter LUID, busiest one wins. And the counters are rebuilt after a resume: their instances are keyed by process and adapter, both gone after a sleep, and five throws in a row used to latch "this machine has no GPU counter" for the session. |
| Sleep / shutdown | A suspended game is frozen and **this process is the only thing that can un-freeze it**. Sleep is where that stops being safe (the resume may kill us), and `SessionEnding` — log off, shut down — never ran `OnClosing` at all, so preferences changed since the last throttled save were simply lost. |

### 🔴 An environment trap that cost the build loop

`dotnet publish` started failing with "the process cannot access the file" on its own output. The
Restart Manager named the holder: **Google Drive**, which syncs `Projects\` and holds a 150 MB
single-file exe open for as long as its upload takes. The build output moved to `C:\tmp\bl_dist`
(`bl_cycle.ps1`, and the elevated mirror's `-Source`) — no lock, and no 150 MB uploaded per build.
⚠️ The mirror needs ONE elevation to be restarted against the new path; until it is, the copy in
`C:\Program Files\Translation Manager\` is whatever it last mirrored.
