## Cloud plugin engine (SAFE declarative) + universal save-backup + UI polish (2026-07-15, LOCAL build `20260714234303` dev_build 115, NOT published)

Continuation of the icon marathon, then a big architectural addition: a **cloud plugin
engine** so a NEW plugin (or an update to an existing one) installs from the cloud with
**NO app rebuild**. Design doc: `CLOUD_PLUGIN_HOST.md`. All LOCAL build+install only.

- **UI tweaks (shipped in this build):** (a) `icon-changes (7).json` = the AuthModal
  **brand-lock** SVG updated to a thinner double-line lock+key (svg-upload → inlined in
  `AuthModal.tsx`, merged into `applied_icon_changes.json`, icon-manager regenerated).
  (b) **Game/software detail gap** tightened: `GameDetailPanel.tsx` top-row grid actions
  column `minmax(...,240px)`→`minmax(160px,190px)` so it hugs the `max-w-[190px]` buttons
  (both games + software use the SAME panel). (c) **Plugin toggle button** (`PluginsSettings.tsx`):
  enabled state now shows a DISTINCT icon (`IconOptBtnDisableTranslation`, minus-hexagon) +
  the label **"כבה"→"השבת"** (download icon stays for "הורדה"). (d) **"הוסף הכל"** button at
  the top of the save-backup auto-detect list (`addAll` batches all detected in ONE `save`,
  dedup by source - a loop of `addEntry` would read a stale `cfg` from the closure).
- **🧠 THE cloud plugin engine (user asked: "release a new plugin without rebuilding the
  app"). Security fork surfaced + user chose the SAFE path (they work in cybersecurity):**
  the existing `plugins/__init__.py` explicitly forbids downloaded-and-executed code (it
  would reverse the signed-installer / SHA-verified posture). So instead of a Python-code
  loader, built a **safe declarative engine** - the launcher ships ONE generic renderer +
  audited primitives; a plugin is DECLARATIVE data (a `ui` manifest + actions that map to
  bundled primitives), never code.
  - **`translation_manager/plugins/engine.py` (NEW)** - `run_action(pid, action, args)`
    dispatches an action NAME to an AUDITED primitive wrapping `save_backup.py`+`registry`+
    `host`: detect / add_detected / **add_all** / add_manual / remove_entry /
    set_entry_enabled / set_schedule / set_field(keep,destination) / backup_now / restore /
    pick_folder / open_folder. `get_state(pid)` returns the dict the UI binds to (entitled,
    schedule+scheduleOptions, keep, entries, backups[+canRestore/whenDisplay], detected).
    `configure(detect_fn, pick_folder_fn, open_folder_fn)` injected from main_eel (like
    `registry.configure`). Mutating actions require an installed plugin (install is the
    entitlement gate). Unit + integration tested (isolated temp state - never touches the
    real `state.json`).
  - **Generic RPCs (STABLE, no per-plugin rebuild):** `main_eel.py` `plugin_ui(pid)` →
    `{ui, state, meta}` + `plugin_action(pid, action, args)` → `{ok, state?, status?}`; both
    off-thread bridge slots in `qt_shell/bridge.py`; `eel.ts` `pluginUi`/`pluginAction` +
    `PluginUiNode`/`PluginUiResult`/`PluginActionResult` types. `_plugins()` now also calls
    `engine.configure(...)`.
  - **Declarative `ui` manifest** for save-backup lives in `registry.py` (`_SAVE_BACKUP_UI`,
    5 nodes: schedule+keep grid, backed-up section w/ detect+backup-now header actions +
    entries list, detected box w/ הוסף+הוסף-הכל, manual-add box, history box w/ restore).
    Node types: grid2/section/box/row/text/input/button/list/field. **🔑 `available()` now
    MERGES the bundled entry over the cloud catalog** (`{**bundled, **cloud_non_none}`) - so
    a metadata-only cloud row (the live `site_config.plugins` has NO ui) still inherits the
    bundled `ui`+`capabilities` (the panel renders), while a cloud row MAY ship its OWN `ui`
    to change the UI with no rebuild. Without this the cloud catalog silently hid the ui.
  - **`GenericPluginRenderer.tsx` (NEW)** - walks the manifest, draws with the design system
    + `UiIcons` (icon by NAME map), `{{field}}` interpolation, `visibleWhen`/`disabledWhen`
    truthiness (NO eval), local input state (bind `local.X`), `then.setLocalFrom`/`clearLocal`,
    `args` `{$bind}` for arrays. `PluginsSettings.tsx` `DeclarativePluginBody` fetches
    `pluginUi` → renders the generic renderer when `ui` present, else falls back to the
    built-in `SaveBackupPanel` (kept for safety). Result: save-backup's UI (labels/buttons/
    icons/layout) is now cloud-editable; today's 3 tweaks become cloud data.
  - **Cloud infra GATED on "פרסם"** (do NOT deploy): the `ui`+`capabilities` go in the admin
    `site_config.data.plugins` (public GET already wired). A genuinely NEW primitive (rare)
    is the only thing still needing a small reviewed code change.
- **🔧 save-backup UX fixes (same build, user-reported, engine-side so they land via the
  generic renderer):** (1) **Unified list** - `engine._last_detected[pid]` caches the last
  scan; `get_state` FILTERS out candidates whose folder is already tracked, so "נמצאו
  אוטומטית" shows only NOT-yet-added saves - pressing "הוסף" moves an item into the backed-up
  list (הסר) instead of leaving a duplicate; "הוסף הכל" empties the found list; re-detect /
  manual-add only add what's missing. (2) **Ubisoft `.tmp.driveupload` bug** - the
  `savegames\*` wildcard matched a Google-Drive temp DOT-folder (and `cache`) instead of the
  real account folder; `save_backup._expand_all` now skips `.`-prefixed + `_JUNK_NAMES`
  folders → the real `savegames\<account-uuid>` is detected. (3) **"תיקיית הגיבויים" button**
  (new `open_backup_folder` action + manifest header button) opens the backup destination
  root (`~/.translation_manager/save_backups`, organised `<label>/<date>`). All 3
  engine-tested (isolated temp state).
- **🌍 UNIVERSAL save-backup (user: "back up ALL games, even non-cataloged; Ubisoft per
  account with an expandable tree; editable usernames") - separate follow-up build below.**
  - `save_backup.detect_ubisoft_accounts()` - an ACCOUNT = a **UUID-named** folder under
    `savegames\`, found at depth 1 OR one level inside a user-made container (e.g. the user's
    `עוד משתמשים` folder held 4 more account UUIDs); each account's numeric-id subfolders = its
    games (INCLUDING games the launcher doesn't know). `detect_generic_saves()` - sweeps the
    GAME-dedicated roots (`Saved Games`, `Documents\My Games` = surface every subfolder;
    `LocalLow` = mixed → `_NONGAME_VENDORS` blocklist [AMD/Adobe/Microsoft/UnrealEngine/…] +
    save-likeness score) so any non-cataloged game is offered. **Real-machine: 5 accounts /
    27 Ubisoft games + 28 flat games (Far Cry/Watch Dogs/Division/TLOU/…).** ⚠️ the earlier
    `savegames\*` bug (matched `.tmp.driveupload`) is why the dot-folder skip in `_expand_all`
    + `_clean_children` matters.
  - `engine.py`: `get_state` adds `ubisoftAccounts` (per account: editable `label` from
    `cfg["ubi_account_labels"]`, games with an `added` flag, `addedCount`/`allAdded`); `detect`
    runs catalog + Ubisoft tree + generic (Ubisoft account folders excluded from the flat list -
    the tree covers them per-game). Actions `add_ubi_game` / `add_ubi_account` (Ubisoft entries
    carry `ubi_account`+`ubi_number`) / `rename_account` (relabels the account AND its already-
    added games) / `rename_entry` (any entry). All engine-tested on real data.
  - **Renderer:** new `ubitree` node (collapsible accounts, editable username via a pencil→inline
    input→`rename_account`, per-account "הוסף חשבון" + per-game "הוסף"/✓נוסף) + inline rename on
    the main entries list (`item.editableAction:"rename_entry"`). Manifest: `ubitree` node after
    the detected box + `editableAction` on entries.
- **🔧 More save-backup + UI polish (same build, user-reported):** (a) **Change backup
  location** - `engine.pick_destination` action (native folder picker → `cfg.destination`) +
  a "מיקום הגיבוי" box in the manifest (shows the path ltr + "שנה מיקום"). (b) **Disk-full
  handling** - `save_backup.backup_entry` PRE-FLIGHT `shutil.disk_usage` check (source size +
  50 MB margin) → returns `error:"diskfull"` instead of a failed partial copy; a mid-copy
  failure cleans the partial folder + re-checks; `engine.backup_now` surfaces "אין מקום פנוי
  בכונן היעד". The game's SOURCE saves are read-only in a backup → a full disk can NEVER
  corrupt them. (c) **Unlimited backups** - `keep=0` = keep everything (`_rotate` already
  honors `keep<=0`; fixed the `config.get("keep") or 10` bug that turned 0 into 10);
  `set_field` clamps `max(0,…)`; the manifest field is min 0 / max 9999, label "(0 = ללא
  הגבלה)". (d) **News header** got the glowing accent bar (`bg-brand-yellow shadow-…`) it was
  missing vs "תרגומים מובילים"; the plugins-view h1 icon → `IconNavPlugins` (apps-add,
  3-squares+plus) to match the sidebar (was `IconOptHdrPlugins` = 4-squares apps). (e)
  **Persisted sort/view** - `lib/usePersisted.ts` (localStorage) so the grid/list + sort choice
  in LibraryView + AppsView survives leaving/returning (was a plain useState that reset on
  remount); keys `lib*`/`apps*`.
- **🌊 Smooth mod-install animation for ALL mods (`lib/useSmoothProgress.ts`).** The shared
  `GameDetailPanel` install bar (CP2077/SM2/WD2/GTA/GoWR/W3/HL/PT/VDJ) pinned the `LiquidWave`
  to 100 during `apply`/`verify` with a numberless "מתקין…", so a long stage looked frozen
  (worst on the multi-stage W3 applier that runs the mod's own install.py as ONE blocking
  call). `useSmoothProgress(target, active)` = a rAF trickle that eases the shown fill toward
  the real pct and, while a stage sits, keeps creeping (decelerating, capped ~96) then snaps to
  100 - so it always FLOWS; the bar + "מתקין… N%" label read the smooth value. Applies to every
  mod via the shared block.
- **⚠️ W3 mod↔app contract (user heads-up "the Witcher 3 mod will change - verify mod↔app
  consistency"):** `witcher3_mod.py` runs the mod's OWN `install.py` in-process, so a changed
  W3 mod MUST keep: (1) zip layout = a mod root with `install.py`+`lib/`+`data/`
  (`_mod_root` rglob); (2) `install.py` exposes `install(root)`/`revert(root)`; (3) backs up
  as `<file>.he_backup` + specifically `content/content0/ar.w3strings.he_backup` (the launcher
  `is_applied` marker); (4) revert globs `content/content*`, `dlc/*/content`, `content0/bundles`,
  `.../epilepsy`; (5) publish-time 4-surface version sync (Worker `witcher3-hebrew` + GitHub
  zip/sha + Supabase `games`+`mod_version_history`). W3 is currently publish-gated (nothing
  live). Re-verify when the new mod zip exists.
- **⚠️ Shell-cwd-leak gotcha:** a `Bash` `cd .../plugins` leaked into the `PowerShell` tool's
  cwd (they share the session cwd), so a relative `Output\...exe` install path resolved under
  `translation_manager\plugins` and failed. **Use ABSOLUTE paths for build/ISCC/install.**
- Built via `build_exe.bat` (BUILD_ID `20260714224416`, dev_build 109, exe 9,254,105 B) →
  ISCC → `Output\TranslationManager-Setup-1.0.2.exe` → installed LOCALLY. Version stays 1.0.2
  beta; NOT published.
- **🔁 CROSS-GAME CONSISTENCY audit + fixes (2026-07-15, LOCAL build `20260715003432`, NOT
  published).** User: "שלכל משחק אפשרי שיהיה עיקבי - החלפת שפה, ניקוי מטמון, וכל דבר שלא עיקבי
  בין משחקים ותוכנות" (+ a follow-up: remove the clipped green lock badge on the signed-out
  sidebar avatar).
  - **🔑 Witcher 3 language switch — the `ini` mechanism (NEW `game_language` kind).** The 3-way
    switch (אוטומטי/עברית/אנגלית) only rendered for `LANG_CONFIGS` members = {spiderman2 (registry),
    cyberpunk (cp2077), virtualdj (xmltag)}, so W3 (a native applier) had NO switch while CP2077
    did — the exact inconsistency the user screenshotted. **The plumbing already existed**
    (`main_eel` install calls `set_mode(_W3_ID,"hebrew",installed=True)` and remove calls
    `"english"`) but was a documented **no-op until a LANG_CONFIGS entry exists**. Added
    `kind:"ini"` = surgical edit of ONE key under ONE `[SECTION]` of a plain INI + a `witcher3`
    entry (`docsub=("The Witcher 3","user.settings")`, section `Localization`, key `TextLanguage`,
    codes `{english:"EN", hebrew:"AR"}` — the mod ships Hebrew in the **AR slot** and renames the
    in-game selector to "Hebrew"; **VoiceLanguage is never touched** so English voice stays).
    Safety: line-based **section-scoped** replace (a `TextLanguage` under a DIFFERENT section is
    NOT touched), preserves the key's exact spelling/spacing + the file's CRLF, **one-time
    `.tm-lang-backup`**, atomic temp+os.replace, and **never ADDS lines — a missing section/key
    returns `language-key-not-found` (no-op) rather than risk corruption**; missing file →
    `settings-file-missing` (the game writes it on first run). `_documents_dir()` resolves the real
    Documents known-folder via HKCU `Shell Folders\Personal` + `expandvars` (OneDrive-redirect
    aware). **Verified against a synthetic user.settings**: read EN → write AR → CRLF preserved,
    VoiceLanguage untouched, a `[Rendering] TextLanguage` decoy untouched, backup created, line
    count unchanged, missing key → clean no-op. Live `get_state("witcher3")` → `kind:"ini",
    current:"hebrew", currentCode:"AR"` (reads the real file). **W3 is the ONLY remaining game with
    a safely-editable text-language store** — GoWR/HL/PT keep it in a BINARY save (`userpreferences`
    / engine save → documented as too risky), GTAV/WD2 have no simple store, and Anno already
    auto-sets its own `engine.ini` at install (JSON-ish `"TextLanguage":"X"`, not `Key=Value`, so
    the `ini` kind does NOT fit it) — so "every POSSIBLE game" is now covered. `is_supported` is
    consumed dynamically everywhere (`main_eel:792` `_enrich_game_row`), so nothing hardcodes the
    old 3-game set.
  - **🔑 `clear_native_mod_cache` — clear-cache for EVERY applier.** "ניקוי מטמון התרגום" only
    rendered for download mods (`gm.modSlug` = CP2077/Anno); the 8 native appliers had none. New
    generic RPC + bridge slot (**`_run_off_thread` 300s** — a W3/GTAV revert is heavy and would
    freeze the GUI) + `eel.ts clearNativeModCache` + the button now renders on `nativeInstalled`
    (SM2/WD2/GTAV/GoWR/HL/W3/PT/VirtualDJ), picking the handler by `gm?.modSlug`.
    **⚠️ THE safety rule: the revert BACKUP lives INSIDE `_native_cache_dir` (WD2), so clear-cache
    MUST revert FIRST and only wipe if the mod is no longer installed** — a naive "wipe the cache"
    would destroy the backup and strand the mod un-revertable. Implementation: read state → if
    `installed`, call the applier's own `remove_*` → **if the revert fails (e.g. the game is
    running) return the error and DO NOT wipe** → only then `shutil.rmtree(_native_cache_dir)`.
    VirtualDJ routes to its existing `clear_virtualdj_mod_cache`. (SM2's backup is in the GAME
    folder and GTAV's in `mod_backups/gtav`, so wiping `mod_cache/<id>` is harmless for them.)
  - **Sidebar signed-out avatar**: removed the tiny lock badge (`absolute -bottom-0.5 -left-0.5`)
    that was clipped by the button's own `rounded-full overflow-hidden` — the person icon +
    gradient remain (the expanded "התחברות/הרשמה" button keeps its LockIcon).
  - **Audited, no bug found (verified, left alone):** `useSmoothProgress` (rAF cleanup + resets
    between installs via the `active` false-branch), `usePersisted`, `GenericPluginRenderer` state
    flow (`data.state` is a STABLE ref per `plugin.id`, so the `useEffect([initialState])` re-seed
    can NOT clobber an action's result on an ordinary re-render), `save_backup._rotate` (`keep<=0`
    → early-return = UNLIMITED) + `keep = config.get("keep")` (the `or 10` bug stays fixed) +
    disk-full pre-flight/mid-copy re-check, ambient `--accent2` (`.accent-bg::after` →
    `var(--accent2, var(--accent))`), keep-field `min:0/max:9999`.
  - **⚠️ BUILD GOTCHA RE-CONFIRMED (cost a silent stale ship this session):** `cmd.exe /c
    build_exe.bat` **silently does nothing** (exit 0, empty output, BUILD_ID unchanged, stale dist
    exe) — it MUST run via the PowerShell call operator **`& '.\build_exe.bat'`**. Caught only by
    checking that `_build_info.py` BUILD_ID is FRESH **and** the dist exe mtime is "now" before
    ISCC/publish (exactly the check CLAUDE.md prescribes). ISCC needs its absolute path
    (`…AppData\Local\Programs\Inno Setup 6\ISCC.exe`).
  - `py_compile` (main_eel/bridge/game_language) + `tsc -b` clean. Built BUILD_ID `20260715003432`
    → ISCC → installed LOCALLY. Version stays 1.0.2 beta; **NOT published**.
- **🔎 500-scenario multi-agent AUDIT + fixes + catalog/grid UX (2026-07-15, LOCAL, NOT published).**
  User asked for a >500-scenario bug audit "and fix confirmed ones". Ran a **16-dimension × 32+ scenario
  Workflow** (450 scenarios traced) with an adversarial skeptic per finding. **⚠️ the run HIT THE WEEKLY
  USAGE LIMIT partway** (12 of 67 agents done; most `verify:*` agents errored) → I VERIFIED every raw
  candidate myself against the code (per [[delegate-all-translation]]'s "never trust an agent's done")
  and fixed the confirmed ones. Confirmed + fixed:
  - **Save-backup "גבה עכשיו" reported SUCCESS on total failure** (`host.py run_now` hardcoded `ok:True`
    after collecting `errors`; `engine.backup_now` only special-cased `diskfull`) → a failed backup
    (source gone / drive offline / permission denied) showed the benign "אין שינוי חדש לגבות" = a
    data-loss illusion on the ONE feature meant to protect saves. Fix: `run_now` → `ok = not errors`;
    `backup_now` surfaces the failed folders as an error toast. (A forced run can't legit-return 0 with
    no errors - `force=True` skips the unchanged-skip - so 0-copied ⇒ every entry failed.)
  - **`on_launch` ("בהפעלת משחק") never backed up manual/generic/Ubisoft saves** - `on_game_launch`
    filtered `_run_save_backup` by the launched game's catalog id, but those entries carry game_id
    `manual`/`generic`/`ubi_*` → never matched → silently never backed up (the bulk of the universal
    feature). Fix: drop the game_id filter for the event (the schedule + entries are GLOBAL); backup_entry
    still fingerprint-skips unchanged, so no dup work.
  - **SWR background push injected `isSoftware` rows into the GAMES library** - `_load_catalog` filters
    software (flag + soft_ids) but the SWR push path (`_enrich_catalog(data)`) did NOT → "רענן מהשרת"
    made VirtualDJ appear as a game (and double-counted the new "בקטלוג" total). Fix: extracted
    `_games_only()` and applied it on BOTH the read path AND the push.
  - **`clear_native_mod_cache` (my new code) trusted an ASYNC remove** - `remove_gtav_mod` is the ONE
    native remove that runs on a worker (`gevent.spawn` → `{ok:True, started:True}` instantly), so the
    `ok` check passed while the revert was still running. Fix: re-read the REAL state after the revert
    and refuse to wipe if still installed (generic over sync + async removes; never strands the backup).
  - **Qt bridge auth CRASHES (the auth_me crash class, unfixed for siblings):** (a) `auth_get_my_purchases`
    fallback was `[]` but the RPC returns a DICT `{rows,reason,detail}` → a slow-network timeout handed the
    Personal Area a list → `.rows` undefined → app crash → fixed to a dict fallback + 45s. (b)
    `auth_signin_password`/`auth_signup_password`/`auth_verify_mfa` used plain `_run_off_thread` (30s,
    RAISES TimeoutError out of the slot = crash) → switched to `_safe_off_thread` 45s + a graceful
    "החיבור איטי - נסה שוב" fallback.
  - **Software could not be BOUGHT from the launcher** - `open_purchase_page` opened `/games/<id>` for
    every id, but software lives at `/software/<id>` (games route redirects to the grid) → VirtualDJ's
    ₪15 was unbuyable. Fix: route by `_load_software()` membership.
  - **`game_mod`**: `clear_cache` swallowed a locked-file unlink error then reported `ok:True` ("cache
    cleared" while the mod is still active in-game) → now returns a failure naming the stuck file;
    `disable` lacked the `expected_files` fallback its sibling `clear_cache` has (an old-build install
    with a wiped cache → nothing removed but "disabled" reported) → added the fallback (caller passes
    `cfg.mod_files`).
  - **`GenericPluginRenderer` (my new code):** a cancelled folder picker (`then.setLocalFrom` with "")
    wiped the manually-typed path → only overwrite on a non-empty return; clearing the "כמה גיבויים
    לשמור" number field to retype persisted `keep=0` (=UNLIMITED, rotation off) → ignore an empty/NaN
    field, commit only a real number.
  - **GoWR + Plague-Tale backup POISONING on a mod UPDATE (data loss)** - the "game-patched → refresh the
    vanilla backup" heuristic (`live != new-heb AND live != vanilla-backup`) can't tell "our OLD Hebrew"
    from "a fresh game-patched vanilla" by sha alone, so a v1→v2 update overwrote the vanilla backup with
    the OLD Hebrew build → "הסרת התרגום" could never restore vanilla. Fix: thread the PREVIOUSLY-applied
    Hebrew sha(s) from `state.json` into `apply()` (GoWR = the single `sha`; PT now stores ALL applied
    file `shas`) and exclude them from the refresh. (PT is publish-gated so its case is latent; fixed
    anyway.) **Universal rule: a "refresh the vanilla backup on game-update" heuristic MUST know the set
    of previously-applied mod shas, or a mod update poisons the backup.**
  - **NOT fixed (verified real but lower-priority / needs judgement, left for the user to prioritise):**
    background scheduled backup writes back a stale cfg (read-modify-write race, no lock) → can drop
    entries added mid-copy; two save entries with the SAME label share one backup folder (restore could
    target the wrong game); OneDrive-redirected Documents may miss some generic sweep roots; a transient
    keyring READ error minting a new Fernet key over the old (session loss); the Settings "נתיבים
    מותאמים אישית" listing auto-detected games with a no-op "נקה". These are catalogued from the audit
    journal for a follow-up pass.
  - **UI (user, same round):** (a) home stat card → counts **games + software** together, label
    "משחקים בקטלוג"→**"בקטלוג"** (HomeView gets `software` from App). (b) **Grid card SIZES** (small/
    medium/large) - `GameCard` gained a `fluid` size (fills the grid cell; `lg`/`md` stay fixed for the
    home scroller) + `lib/cardSize.ts` `gridCols()` = `auto-fill minmax(<size>,1fr)` so the COLUMN COUNT
    follows the window width (≈3 large / 4 medium / 5-6 small, more when wider), in BOTH games + software.
    (c) Toolbar order SWAPPED: the grid/list toggle (2 choices) is on the RIGHT, the density picker (3
    choices) on the LEFT. (d) **List view density** - new `ListLayoutPicker` (1/2/3 game-rows per line)
    shown in list view; rows render in a responsive grid (`listGridCls`). All persisted per view
    (`libCardSize`/`libListCols`/`appsCardSize`/`appsListCols`).
  - **🌐 Website (separate repo, needs `vercel --prod` by the user):** the announcement banner
    (`SiteBanner`, `fixed top-0`) covered the hero title - page content flowed under it because only the
    navbar offset by `--banner-h`. Fix: `App.tsx` wraps the routes in a `paddingTop: var(--banner-h,0px)`
    div (no-op when no banner). Website `tsc` clean.
  - `py_compile` (all touched backend) + `tsc -b` clean. Built + installed LOCALLY; version stays 1.0.2
    beta; **NOT published**.

---


