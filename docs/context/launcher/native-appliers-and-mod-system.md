## ZERO bundled mods (100% server-first) + installer slimmed 186→134 MB + W3 readiness audit (2026-07-19, LOCAL build `20260718214326`, NOT published)

User is about to publish the launcher + the Witcher 3 mod together and asked three things: is W3
really ready, is EVERY mod served from the server (not baked into the installer), and are there
files in the installer that do not belong. All three answered end-to-end; the launcher was rebuilt
+ installed LOCALLY four times this round. **Nothing published, website untouched.**

- **🔴 THE STANDING RULE THIS ROUND ESTABLISHES: no mod payload ships inside the installer.**
  Every translation is downloaded from the Worker on first install and then KEPT IN THE LAUNCHER
  CACHE (`~/.translation_manager/mod_cache/<id>/`); a machine with no/weak internet uses the
  OFFLINE PACKAGE (`tools/build_offline_bundle.py`) instead of a stale copy baked into the exe.
  The 4 bundled payloads (`assets/{gtav,spiderman2,watchdogs2,godofwar_ragnarok}` ≈ 22 MB) are
  dropped by `_keep()` in `TranslationManager_qt.spec` (`any(f"assets/{g}/" in dest …)`;
  `app_icons` + `ubisoft_games.json` are NOT mods and stay).
- **🔴 THE BUG THAT REMOVAL EXPOSES (would have shipped a dead Install button):** three RPCs
  pre-checked the BUNDLE before starting the worker (`install_spiderman2_mod` `_sm2_payload_files()`,
  `install_watchdogs2_mod` `_wd2_payload_map()`, `install_gowr_mod` `_gowr_payload()`) and returned
  "קבצי המוד אינם זמינים בגרסה זו" - so with no bundle the click would fail INSTANTLY, before any
  download. All three deleted. Same class: the `available` flag in `get_{watchdogs2,gowr,gtav}
  _mod_state` MEANT "a bundled copy exists" → now hard `True` (the mod is downloadable; a network
  failure is reported by the install, never by hiding the action). **UNIVERSAL: when a payload moves
  from bundled to downloaded, every "is it available" check must flip from *is it on disk* to *can
  it be fetched*, or the feature silently disappears from the UI.**
- **GTA V was the last bundled-ONLY mod → now server-first like the rest.** `gtav_mod` gained
  `set_payload_dir()` (a downloaded dir WINS over the bundle; `_asset()` checks it first);
  `main_eel` gained `_GTAV_SLUG="gtav-hebrew"`, `_gtav_payload_dir()`, `_gtav_use_cached_payload()`
  and `_gtav_download_payload()` (one archive carrying BOTH `gtav_he_payload.zip` +
  `gtav_vanilla_payload.zip`, so the surgical revert writes back the vanilla files the install came
  from); install records the server version via `_native_write_state`; `get_gtav_mod_state` points
  the resolver at the cache first; the update check moved to `_native_latest_version(_GTAV_SLUG…)`.
  **`games/gtav/pack_and_release.py` now emits TWO assets** - `gtav_hebrew.zip` (website/OpenIV,
  linked by `games.download_url`) and `gtav_launcher_payload.zip` (the Worker/launcher) - with
  `manifest.archive_name` pointing at the LAUNCHER one, because the Worker exists to serve the app.
  Without that split a future re-pack would silently feed the OIV zip to the launcher.
  Built + offline-verified: archive → `pick()` → 610 gxt2 + 3 fonts in each payload, Hebrew ≠
  vanilla, bundle-fallback still resolves. `gtav` added to the offline builder's `NATIVE_SLUGS`.
- **Installer 186.0 → 134.3 MB, dist 613 → 489.6 MB.** Beyond the 22 MB of mods: `numpy` +
  OpenBLAS (**27 MB**, pulled in ONLY by `PIL._typing`'s `try: import numpy.typing` - nothing in
  the app touches numpy), 51 of 53 `qtwebengine_locales/*.pak` (**42 MB**; kept `en-US` + `he`,
  Chromium falls back to en-US), `qtwebengine_devtools_resources.pak` (**11 MB**), every
  `*.debug.pak`/`*.debug.bin` (**5 MB**), and `tkinter`/tcl/tk (**9 MB**, only the Eel-path
  `_show_no_internet_dialog`). **DO NOT drop Qt6Quick/Qt6Qml/qml (~55 MB): in Qt 6 QWebEngineView
  is backed by a QQuickWidget, so removing them breaks the webview.** Verified after install: the
  window painted (boot sentinel cleared), GPU accelerated.
- **🔴 Inno leaves orphans + an unbounded uninstall log (both found by measuring the INSTALLED
  dir, not the dist).** (a) Inno only adds/overwrites, so the ~100 MB we stopped shipping stayed
  behind: a 511 MB program measured **1,036 MB** after an in-place update → `[InstallDelete]` now
  wipes `{app}\_internal` wholesale (safe: the writable cache is `{app}\data`, user state is
  `%USERPROFILE%\.translation_manager`), which also subsumes the hashed-asset rule. (b)
  `unins000.dat` had grown to **161 MB** because Inno APPENDS every install's records →
  `UninstallLogMode=overwrite`. ⚠️ `UninstallLogMode=new` is the WRONG fix (tested): it writes
  `unins001/002/…`, a fresh uninstaller PAIR per install, and leaves the huge legacy log behind.
- **Witcher 3 readiness: code ✅, two PUBLISH steps still open.** Verified: the applier's
  `_mod_root` expectation matches the shipped zip EXACTLY (root `install.py` + `lib/` + `data/`,
  and `lib/` holds precisely the 4 modules `_LIB_MODULES` pops); `install.py` loads through the
  launcher's own importlib path and exposes `install()`/`revert()`; the GitHub release
  `v1.0.0-beta.1` is a FULL release whose zip (3,842,202 B, sha `38d7db64…`) MATCHES its manifest
  (**the sha documented earlier in this file was stale - the mod was re-uploaded**); the mod is
  backup-poisoning-safe (`backup()` never overwrites an existing `.he_backup`, `_vanilla_bytes()`
  always repacks from vanilla → re-install/update is idempotent); detector pattern, `_W3_ID`,
  `game_language` `kind:"ini"`, state + revert are all wired. **BLOCKERS:** the Worker slug
  `witcher3-hebrew` 404s (present in `src/index.js`, never deployed) and the Supabase row is
  `coming-soon/locked` while the panel is `gated:true` → the card shows "בקרוב" with no install
  button. Added `gtav-hebrew` to the Worker map in the same edit, so ONE deploy covers both.
- **GTA V is HIDDEN from the launcher ON PURPOSE** (user, 2026-07-19): `games.show_on_launcher=false`
  and nobody has bought it, so at publish time do NOT deploy its Worker slug and do NOT upload
  `gtav_launcher_payload.zip`. The server-first code stays in place, dormant, ready to switch on by
  flipping the flag + running the two commands. (`witcher3` is ALSO `show_on_launcher=false` - that
  one IS an oversight: the site row says available/beta, so the game is published on the website but
  invisible in the launcher until the flag flips.)
- **THE IN-APP CHANGELOG IS A SEPARATE, LONGER TEXT from the website's.** In-app =
  `frontend/src/lib/changelog.ts` (Settings → "יומן שינויים", bundled so it renders offline and
  covers the installed build even before a public release); website = the `launcher_releases.notes`
  row, one short paragraph. The 1.1.0 in-app entry was rewritten + approved by the user on
  2026-07-19: headline + 4 groups (משחקים ותרגומים 2 · תכונות חדשות 8 · שיפורים 8 · יציבות ואבטחה 10).
  Note the user deliberately DROPPED the "נסגרה פרצה שאיפשרה להתקין תרגום בתשלום ללא רכישה" line -
  do not re-add it. When bumping the version, prepend a new entry and keep older ones verbatim.
- **🔴🔴 THE BLOCKER THAT WOULD HAVE SHIPPED BROKEN: the W3 release manifest used `archive`
  instead of `archive_name`.** Deploying the Worker exposed it instantly: `/witcher3-hebrew/archive`
  answered **502 "release has no asset 'undefined'"** (the Worker looks the asset up by
  `manifest.archive_name`) AND `mod_source.fetch_manifest` REJECTS a manifest without that key
  ("manifest missing 'archive_name'") - so the install was dead in BOTH layers, silently, for a mod
  that was already published on the website. Root cause: `games/witcher3/pack_release.py` is the ONE
  packer that wrote `archive`; **every other game's packer writes `archive_name`** (audited all 9).
  Fixed in three places: (1) the Worker now normalizes `archive_name ||= archive` right after
  parsing, so no packer's wording can ever take a published mod offline again; (2) the packer writes
  BOTH spellings; (3) the live release's `manifest.json` was re-uploaded corrected (the zip is
  untouched - same sha). **UNIVERSAL: `manifest.archive_name` is a hard contract shared by the
  Worker and `mod_source`; verify a NEW game's slug with a real `/manifest` + `/archive` request
  before trusting it, never by reading the packer.** All 8 published slugs re-verified: manifest
  parses + `/archive` HTTP 200.
- **Witcher 3 is now LIVE end-to-end in the launcher** (verified against the real install, not by
  inspection): Worker deployed · `games.show_on_launcher` flipped true · the launcher's catalog
  carries the row (`availability=available` = the install-button gate) · `fetch_manifest` →
  download → SHA-256 verify → extract → the `_w3_download_payload` `pick()` finds the mod root →
  `witcher3_mod._load_installer` loads it → `validate_game(D:\Games\The Witcher 3 - Complete
  Edition)` returns ok · payload complete (35 w3strings + 72 subtitle files + the Hebrew fonts).
  ⚠️ A freshly-flipped flag reaches a running launcher only after the SWR catalog refresh (the
  first read returned the stale cached list) - a cold start or "רענן מהשרת" shows it immediately.
- **⚠️ wrangler auth is invisible from an Antigravity profile** ([[env-redirection-real-home]]):
  `wrangler whoami` says "not authenticated" because the redirected `%APPDATA%` hides
  `…\AppData\Roaming\xdg.config\.wrangler\config\default.toml`. Fix: set
  `$env:APPDATA = 'C:\Users\Nehoray_Cohen\AppData\Roaming'` for the wrangler command. No re-login.
- **✅ THE 1.0.2 → 1.1.0 UPGRADE WAS REHEARSED ON REAL 1.0.2 HARDWARE** (MAIN-LAPTOP, reachable at
  `Nehoray_Cohen@10.0.0.49:22` with `~/.ssh/id_ed25519` - the same host as the NIM fleet laptop
  stream). It ran the PUBLISHED build `20260705144705` installed **per-user** in
  `%LOCALAPPDATA%\Programs\Translation Manager` (NOT Program Files - `PrivilegesRequiredOverrides
  Allowed=dialog` lets a user pick that). scp'd the installer, ran it `/VERYSILENT`, verified:
  740.9 MB → **568.4 MB**, build → `20260718221736`, `unins000.dat` 2.6 MB → **1.01 MB**, it
  UPDATED IN PLACE (no duplicate machine-wide install), every orphan class gone (numpy, tcl/tk,
  devtools pak, all 4 mod payloads), locales 2, **js bundles 1**, Qt6Quick + app_icons kept, ALL
  user state intact (`session.enc`, `launcher_prefs.json`, `user_cache.json`, `detected_games.json`,
  `device_id`, `cache.json`), the installer relaunched the app, and the webview PAINTED (boot
  sentinel absent, gpu-probe accelerated on Intel UHD / tier "balanced"). **The upgrade path is
  proven end-to-end on a second machine with different hardware.**
  ⚠️ Two notes for a remote/silent run: the installer elevates (`PrivilegesRequired=admin`), so
  over SSH the UAC prompt is invisible and `Start-Process -Wait` looks hung - the install DOES
  complete, just verify after instead of waiting; and MSYS `/tmp` is invisible to Windows Python,
  so stage the remote PowerShell in the scratchpad and send it `-EncodedCommand` (UTF-16LE base64).
- **⚠️ PRE-PUBLISH SIDE EFFECT: any machine already on a 1.1.0 build is offered "1.0.2" as an
  update** until 1.1.0 is published. `get_launcher_update_info` ORs `_version_is_newer` with a bare
  `build_differs` inequality, which is DELIBERATE (it is what let the documented 1.1.0 → 1.0.0
  version reset reach installed users) - so do NOT "fix" it into a strict newer-only check. Just
  don't accept the update prompt on a test machine before publishing; publishing 1.1.0 clears it.
- **🔴🔴 ONE ROOT CAUSE BEHIND THREE USER-VISIBLE BUGS: an ELEVATED instance defeats the
  single-instance mutex, and TWO instances silently break localStorage.** Reported from the laptop
  after the upgrade: (a) the onboarding tour + the welcome notification replay on EVERY quit-and-
  reopen, (b) two `TranslationManager.exe` processes, (c) "I never saw the window, only a Windows
  notification". Measured, not guessed: pid A **elevated=YES** (relaunched by the installer), pid B
  **elevated=no** (the user's own launch), both alive, both `MainWindowHandle=0`. `CreateMutexW`
  from the elevated process gets a default DACL that mandatory-integrity DENIES to a medium-IL
  process, so the second launch fails with **ERROR_ACCESS_DENIED (5), NOT ERROR_ALREADY_EXISTS
  (183)** - and `acquire()` failed OPEN on any non-183 error. Both instances then opened the SAME
  QtWebEngine profile; the second could not take the Local Storage **leveldb LOCK**, so its
  localStorage degraded to IN-MEMORY. Proof: `onboardingDone` / `pth.notif.seen2` were ABSENT from
  the on-disk leveldb on the laptop while PRESENT on this machine, and the leveldb had not been
  written since 7/14. **FIX:** `single_instance.acquire()` treats ACCESS_DENIED as "another
  instance owns it" (exit, don't duplicate) and records `elevated_owner()`; `main_qt` then shows a
  native MessageBox (Qt is not up yet) telling the user to quit the elevated copy from the tray,
  because that owner's show-event is unreachable for the same reason and the launch would otherwise
  vanish silently. **VERIFIED IN THE FIELD on the laptop: with an elevated instance running, a
  second normal launch left the count at 1 (it used to become 2).**
  ⚠️ The elevated relaunch itself is an artifact of running Setup from an ALREADY-elevated context
  (my SSH `-Verb RunAs`): Inno's `runasoriginaluser` has no non-elevated parent to drop back to. A
  user double-clicking, and the in-app self-updater (which spawns Setup non-elevated → UAC →
  runasoriginaluser), both land correctly. **UNIVERSAL: a Win32 single-instance guard MUST treat
  ERROR_ACCESS_DENIED as "already running"; failing open there is how you get two processes
  fighting over one Chromium profile.**
- **Avatar had no failure fallback (separate real bug, fixed).** `Sidebar.tsx` + `PersonalAreaView.tsx`
  rendered the REMOTE Google avatar with the initials bubble as the fallback for a MISSING url only -
  so an image that fails to LOAD (offline, blocked CDN, rate limit) left an empty circle. Both now
  track `avatarBroken` via `onError` and reset it when the url changes. Same class as the
  [[cached-image-onload-race]] cover bug: *having a src is not the same as having a picture*.
- **NOT a regression: "GPU acceleration was off by default" on the laptop.** `disable_gpu_compositing`
  defaults to **False** (accelerated); that machine's `launcher_prefs.json` carried `true` from
  BEFORE the upgrade, i.e. a stored per-machine choice. The GPU safe-mode sentinel never writes the
  pref (it only adds a runtime Chromium flag), so nothing in 1.1.0 turned it off.
- **🔴🔴 "No module named 'potato_bundle'" - the W3 install worked in DEV and died in the SHIPPED
  build (fixed, build `20260719010830`).** `witcher3_mod` deliberately runs the MOD'S OWN
  `install.py` in-process, and that file resolves its own location like a standalone tool:
  `def _base(): return sys._MEIPASS if getattr(sys,"frozen",False) else dirname(__file__)`, then
  `HERE=_base(); sys.path.insert(0, HERE+"/lib"); import potato_bundle` and `DATA=HERE+"/data"`.
  Inside OUR frozen launcher `sys.frozen` is True and `sys._MEIPASS` is the LAUNCHER's bundle -
  so `HERE` pointed at the launcher, `lib/` was not there, and `DATA` (which all five install
  phases read) would have been wrong too. A dev run resolves `__file__` and passes, which is
  exactly why my earlier end-to-end test (80 s, byte-identical re-install) did NOT catch it.
  **FIX in `_load_installer`:** (1) pre-seed the mod's `lib/*.py` into `sys.modules` from THIS
  extracted root - in dependency order, `w3strings_patch` imports `w3strings` - so the imports
  resolve no matter what `HERE` computes; (2) after `exec_module`, pin `mod.HERE` / `mod.DATA` to
  the mod root (they are plain globals read at CALL time, so patching post-import is what actually
  decides where the payload is read from). Deliberately does NOT touch `sys.frozen`/`sys._MEIPASS` -
  they are process-global and other threads resolve bundled assets through them. Verified by
  SIMULATING the frozen env (`sys.frozen=True`, `_MEIPASS`=an empty dir): old code →
  `ModuleNotFoundError: No module named 'potato_bundle'` (the user's exact error), new code → loads,
  `DATA` reads the real 34-entry payload, `validate_game` ok. **UNIVERSAL: whenever the launcher
  executes a mod's OWN installer in-process, that installer's `sys.frozen`/`_MEIPASS` path guess
  belongs to OUR exe, not to it - always pin its root explicitly, and TEST with frozen simulated,
  because a dev run cannot reproduce it.**
- **🔴🔴 DRM HOLE: a PAID mod installed for an account that never bought it - because the Qt bridge
  starts the WORKER directly, bypassing every RPC-level gate (fixed, build `20260719013835`).**
  Found by the user ("my account did not buy it and it still installed"). Two compounding causes:
  (1) W3/Hogwarts/Plague-Tale shipped as FREE titles, so **no purchase check was ever written** in
  either their RPC or their worker - and price is ADMIN-EDITABLE, so when the Witcher 3 went
  `price_cents` 0 → 5300 mid-life the mod stayed wide open; (2) even where the RPC DID check
  (`download_and_install_game_mod`), `qt_shell/bridge.py` calls
  `QThreadPool.start(_run_game_mod_install)` / `_run_w3_install` / `_run_sm2_install` /
  `_run_gowr_install` **directly**, so on the SHIPPED build the RPC gate is not on the path at all.
  Audit of all 9 install paths: 3 had NO gate anywhere, 3 more (GoWR/SM2/WD2) were latent holes
  waiting for a price change, 1 (the generic download mod) was RPC-only; only GTA V and VirtualDJ
  were correct. **FIX: `if _game_price_cents(gid) > 0 and not auth_owns_game(gid)` in EVERY worker
  AND every RPC** - a no-op for a genuinely free mod (`price <= 0`), evaluated against the LIVE
  catalog price so a later price change is enforced without a rebuild. **UNIVERSAL: in this app a
  check that lives only in an `@eel.expose` RPC is NOT a gate - the Qt bridge is the real entry
  point and calls workers directly. Gate in the worker, always, even when the title is free today.**
- **🔴🔴 THE SAME DRM HOLE HAD A SECOND HALF, IN THE UI: a paid native title showed "✓ נרכש"
  and NO buy button (fixed, build `20260719015757`).** Reported by the user right after the
  worker-gate ship: the Witcher 3 panel rendered the green "✓ נרכש" chip and went straight to
  "התקנת תרגום" on an account that never bought it. Two independent causes, both in the state
  layer, not the gate: (1) **every native applier's state RPC omitted `owned` + `priceCents`
  entirely** (`get_{witcher3,hogwarts,plaguetale,gowr,watchdogs2,spiderman2}_mod_state`) - and the
  panel draws the buy button from `priceCents > 0 && !owned`, so with the keys absent it read
  "free + owned" and the button could not exist; (2) `get_game_mod_state`'s **slug-less branch**
  (which is exactly the native-applier case, and still feeds the header chips) returned a
  **hardcoded `"owned": True`**, which is what painted the false chip. Fix: one shared
  `_owned_fields(game_id)` → `{priceCents, owned}` (live catalog price; `price <= 0` short-circuits
  to owned=True with no network call) spread into all six native state RPCs and into the slug-less
  branch. `SpiderMan2State` / `WatchDogs2State` gained the two optional keys (`GowrState`, which
  W3/HL/PT/GoWR share, already had them), and the SM2 + WD2 CTA branches gained the same buy block
  the `isGowr` branch has. **This ALSO restores `locked`** (`titlePrice > 0 && !titleOwned`), which
  hides the language switch / beta opt-in / cache wipe on an unpurchased paid title - it had been
  dead for every native game because `owned` was always True.
  **🔑 THE FINDING THAT MAKES THIS NOT-HYPOTHETICAL: Watch Dogs 2 and Spider-Man 2 are ALSO
  `price_cents=5300`.** The notes above (and the code comments) called them free because they were
  free when first published; the live catalog says otherwise. **7 of 42 titles are paid** - gtav /
  cyberpunk / anno1800 / watchdogs2 / witcher3 / spiderman2 at ₪53, virtualdj at ₪15 - so the SM2
  and WD2 buy gates close a live bypass, not a future one. Verified against the live catalog:
  witcher3/watchdogs2/spiderman2 → `price=5300 owned=False`, hogwarts/plague-tale/gowragnarok →
  `price=0 owned=True` (no network). **UNIVERSAL: a DRM gate needs BOTH halves - the worker check
  (so it cannot be done) and truthful `owned`/`priceCents` in the state RPC (so the UI offers the
  purchase instead of an error). Never assume a title's price from a code comment; read the live
  catalog - `price_cents` is admin-editable and these three changed after launch.**
- **🔴 GoWR "removal succeeded" but stayed מותקן - the zero-bundled-mods change broke its
  installed-MARKER (fixed, build `20260719023042`).** The removal genuinely WORKED (verified on the
  real machine: `state.json` `{}`, and the live `r_lang_ar.wad` is byte-identical to the backup =
  the original is restored) - only the marker lied, so the panel stayed "תרגום מותקן" and
  clear-cache refused with "ההסרה רצה ברקע". Root cause: `gowr_mod.is_applied`'s no-sha fallback was
  a bare **"a backup exists + the WAD exists"**, and `revert()` deliberately KEEPS the backup → True
  forever. It only surfaced now because the sha came from `state.get("sha") or _gowr_bundled_sha()`:
  the state is cleared by revert, and **`_gowr_bundled_sha()` is None since the bundled payload was
  dropped**, so the content check that used to save it no longer ran. Fix: the no-sha path now
  compares the live WAD against the BACKUP (different = ours is in place, identical = reverted), and
  `revert()` DROPS the backup after a successful restore (the live file IS the original; keeping it
  is what made the marker sticky, and it would also read as "applied" after a later game update).
  Re-install re-takes the backup from the restored file - round-trip tested. **UNIVERSAL: an
  installed-marker must be evidence the mod IS IN PLACE (content), never "a backup was taken once";
  and re-audit every marker when a payload moves bundled → downloaded, because a bundled-file sha is
  exactly the kind of silent input that disappears** ([[no-bundled-mods-server-first]]).
- **🔴 An unowned account could not REMOVE an already-installed paid mod (fixed).** Reported after
  switching to an account with no purchases: Anno 1800 and CP2077 offered only "רכישה" - the mod
  stayed applied to the game with no way out. The download-mod branch gated its remove button on
  `gm.owned && gm.installed`, and the (new) native buy branches were gated on `!installed`. Now, in
  ALL branches: **buy** = `price > 0 && !owned`, **install** = `owned && !installed`, **remove** =
  `installed` (never gated on ownership); the UPDATE button stays owner-only. Same reasoning applied
  to "ניקוי מטמון התרגום", which had `!locked` on it - it is a REMOVAL action and its condition
  already requires something installed/cached. **UNIVERSAL: a DRM gate restricts ACQUIRING, never
  UNDOING - anything already written to the user's disk must always be removable.**
- **Purchase CTA is one fixed colour now.** It took the per-game accent on native appliers and
  `bg-brand-yellow` on download mods, so on a yellow-accented title (Anno / CP2077) it came out the
  same yellow as "הפעל" - two identical buttons - while every other game showed cyan. All six buy
  buttons now share one `BUY_BTN` constant (sky), distinct from the yellow primary.
- **🔴 The panel assembled itself in THREE visible stages (fixed).** Opening a game showed the
  basics, then the action buttons + language switch, then the version history dropped in. Two causes:
  (a) every region rendered the moment its OWN fetch landed; (b) **`auth.owns_game` is an UNCACHED
  HTTPS round-trip and the ownership work above asked for it TWICE per open** (`get_game_mod_state`
  for the header chips + the game's own native state RPC), so a paid title blocked on two sequential
  network calls. Fixes: **`_owns_ui(game_id)`** memoizes the READ path - positive 600s (a purchase
  does not expire), negative **1.5s** (short enough that the 3s post-purchase burst poller still
  flips the CTA), cleared alongside `_owned_confirmed` on every sign-in/out; **install gates keep
  calling `auth_owns_game` directly so no gate is ever decided by a cached value**. And a single
  `hydrated` flag (all LOCAL bridge state settled, 2.5s safety deadline) now gates the actions +
  language switch + beta/cache controls so they paint together behind one skeleton; the version
  history is REMOTE, so it keeps its own reserved skeleton and a `done` flag to tell "still fetching"
  from "this title has no timeline". **UNIVERSAL: before optimising perceived load, count the
  NETWORK calls a screen makes - a DRM/ownership check added to a state RPC is easy to add twice.**
- **The W3 progress bar "stuck at 96%" was a 6-minute install with no feedback (fixed).**
  `witcher3_mod.apply` sent 55% and then nothing until done, so `useSmoothProgress` crept to its
  ~96% cap and sat there - indistinguishable from a hang, and a user who kills it there leaves the
  game mid-write. The install really does take minutes (it rewrites the 2.5 GB `movies.bundle` and
  touches the 8.4 GB `texture.cache`; sampling caught `movies.bundle` at 0 bytes mid-rebuild, with
  the 2.5 GB `.he_backup` intact the whole time). install.py already narrates itself through a
  `log` callback ("1/5 …" … "5/5 …"), so `apply()` now passes one that maps the phase to
  **55 → 63 → 71 → 79 → 87 → 95** with Hebrew labels, and phase 3 says outright that it takes a few
  minutes. **UNIVERSAL: any single blocking call that can run for minutes must be given a progress
  channel - if the applier exposes a log hook, bridge it; a frozen bar reads as a crash.**
- **💰 STANDING RULE (user, 2026-07-19): every mod released through the launcher is ₪53** -
  `games.price_cents = 5300`, set **as part of publishing**, next to `show_on_launcher` /
  `availability` / `mod_version_history`. God of War Ragnarök shipped `available` with
  `price_cents = 0` and was therefore installable by anyone: the gate was working correctly, the
  PRICE was the hole. No rebuild is needed (`_game_price_cents` reads the live catalog). Audit =
  released rows (`availability='available'`) whose `price_cents != 5300`; currently 7/7 game mods
  comply. Deliberate exception: **VirtualDJ ₪15** (software, not a game mod). hogwarts /
  plague-tale-requiem are not released yet - price them the moment they go available.
  [[mod-price-53-default]]
- **Publish commands (run only on an explicit "פרסם"; GTA lines intentionally omitted):**
  1. `cd games/steam/steam_mod_worker && npx wrangler deploy` (serves `witcher3-hebrew`; the
     `gtav-hebrew` entry rides along in the map but stays unused while GTA is hidden).
  2. PATCH `games?id=eq.witcher3` → `show_on_launcher=true` (the site row is already
     available/beta/1.0.0-beta.1; without this flag the game never reaches the launcher catalog).
  3. The launcher itself: `build_exe.bat` → ISCC → `publish_release.py 1.1.0 beta`, then write the
     SHORT website paragraph into `launcher_releases.notes` (the long text lives in-app).


## OFFLINE PACKAGE (build-on-demand bundle) + boot-lag root-cause (2026-07-18, LOCAL build `20260718175424`, NOT published, website untouched)

User asked for an offline install path for a machine with NO internet, then refined it into the
right design: **not** a static fat installer (which would need rebuilding+republishing on every mod
release), but an **online BUILDER run on demand** - tick the games you want, it pulls the CURRENT
versions, and writes a package you carry to the offline machine. Built end-to-end, LOCAL only.

- **🔑 THE DIVISION OF RESPONSIBILITY (the user's own correction, and it is the right one):** the
  installer/package **NEVER writes into a game folder**. It only pre-seeds the **cache**, i.e. makes
  the DOWNLOAD step unnecessary; the launcher's own applier still does backup → apply → state →
  revert. A mod must always be written by the code that knows how to revert it.
- **`translation_manager/offline_bundle.py` (NEW)** - reads the store
  (`~/.translation_manager/offline_bundle`): `manifest.json` + `mods/<gid>/<archive>.zip` (the EXACT
  Worker archive) + `images/<bucket-rel>` + `catalog.json`. API: `verify()` (SHA-256 gate),
  `extract()` (returns `(dir, version)` - the SAME contract as `mod_source.fetch_and_extract`, so
  every per-game `pick()` works unchanged), `images_payload()`, `catalog_games/config()`,
  `offline_update()`. **SECURITY: the SHA is re-verified at USE time, not just at build time** - a
  store tampered with in transit is refused, never applied (self-tested incl. the tamper case).
- **`tools/build_offline_bundle.py` (NEW, run ONLINE)** - interactive checklist (or `--all` /
  `--games a,b` / `--zip`), fetches `/api/games` + `/api/config` + `/api/launcher`, downloads each
  selected mod through the **same SHA-verified Worker path** the launcher uses, mirrors covers/
  banners/logos, writes the manifest. Verified live: resolves **9/41 catalog rows** that have a
  downloadable mod, correct slug + kind for each. `NATIVE_SLUGS` must stay in sync with the
  `_*_SLUG` constants in main_eel (GTA V absent on purpose - bundled payload, no Worker slug).
- **Consumption (main_eel):** `_native_download_payload` falls back to the bundle when the network
  fails - **game_id is derived from `cache_dir.name`**, so all 7 native appliers inherit offline
  support with ZERO per-game code. `_seed_cache_from_bundle()` + `game_mod.cache_from_dir()` do the
  same for download mods; `_run_game_mod_install` now prefers the bundle when it is NEWER than the
  cache and uses it as the last resort when a download fails. `_load_catalog` prefers the bundle's
  catalog snapshot over the compiled-in one (it knows about games added after the exe was built).
  New RPC `get_offline_assets` + bridge slot.
- **"עדכון אופליין" (the user's idea, and it is what makes offline updates EXIST).** With no
  internet the server check is silent, so a newer bundled payload would be invisible. Added
  `game_mod.installed_version` (the version APPLIED to the game, tracked separately from the CACHE
  version) + `applied_version()`; `_with_offline_update()` folds a purely-LOCAL comparison into
  every update check and sets **`updateSource: "network" | "offline"`** (newer of the two wins;
  still respects the beta opt-in). UI: all 5 update buttons + the header chip in GameDetailPanel
  switch to "עדכון אופליין", and the DownloadsView row says "(מהחבילה האופליין - ללא אינטרנט)".
- **Images - the one real engineering piece.** Covers are ABSOLUTE Supabase URLs, and an installer
  **cannot safely fabricate entries in Chromium's internal disk-cache format on another machine**
  (versioned, opaque, evictable) - so "just put them in the cache" does not transfer. Instead the
  package ships an image mirror and `coverUrl.ts` gained `initOfflineImages()`/`resolveAssetUrl()`
  which prefer the local `file://` copy when present. **Keyed by the bucket-relative sub-path, NOT
  the basename** - a cover and its banner share the same basename (`<id>.webp`) and would collide.
  Wired at boot in App.tsx (fail-soft: no package → normal server URLs).
- **Verified:** `offline_bundle` selftest PASS, `py_compile` + `tsc -b` clean, and a **21-check
  end-to-end offline simulation** (scratchpad `test_offline_e2e.py`) proving bundle → cache →
  apply → newer-bundle → "offline update" → apply → no-longer-offered, plus the tamper refusal
  leaving the game folder untouched.
- **Remaining (by design, told to the user):** the offline machine still needs **one** online login
  (seeds `user_cache.json`; `me()` already tolerates offline afterwards) - no forgeable token; paid
  mods only for an account that owns them (verified online at build time); a package is a
  point-in-time snapshot.

### Side fixes in the same round
- **🔴 "the app opens laggy after a long time; a restart used to fix it, now it doesn't" - ROOT
  CAUSED.** The GPU safe-mode sentinel added on 2026-07-17 degraded to `--disable-gpu-compositing`
  after a **single** never-painted boot, so ONE abnormal exit (task-kill, power loss, closing the
  window while it loads) made the NEXT launch CPU-composited = visibly choppy. And "restarting"
  often did not help because **X minimises to tray by default** (set this session), so relaunching
  the shortcut just re-focused the SAME degraded process via single-instance - only a real tray-quit
  starts a fresh one. **FIX:** the flag is now a COUNTER and safe mode needs **two consecutive**
  failed boots (a genuinely broken GPU fails every boot, so the white-screen self-heal still works).
  Diagnose with Settings → ביצועים ("מצב עיבוד גרפי").
- **Splash logo appeared a beat AFTER the text** - the `<img>` was only discovered when React
  rendered the splash. Added `<link rel="preload" as="image" fetchpriority="high">` in index.html +
  `fetchPriority`/`decoding="sync"` on the img, so it decodes by the time the splash mounts.
- **The travelling menu indicator's glowing edge bar read as SHARP** - at `w-[3px]` a `rounded-full`
  cap is 1.5px, visually a square end. Now `w-[4px]` + a bigger inset + a **spread-less** glow (so
  the halo follows the rounding instead of boxing it), in both Sidebar and the Settings tabs.
- **Toast icon was cut + on a white background when the app icon is set to SQUARE** - Windows
  circle-crops the toast app-logo, and `brand-square.png` is flattened on white (it is the installer
  wizard asset). The notification logo is now pinned to the round transparent `brand` mark
  (`_TOAST_LOGO`) regardless of the user's icon-shape choice.


## "Universal brain" upgrade — self-healing + adaptive perf + cascading detection (2026-07-13, LOCAL, tested, NOT built/published)

User asked for the launcher to be UNIVERSAL (any PC / any Windows / future games+software+mods with
no rebuild), to ADAPT to the host machine's performance, to MONITOR load/idle and cut RAM/CPU/GPU in
real time, and to SELF-HEAL every error behind the scenes (try many built-in fixes in a fraction of a
second, no data loss) instead of surfacing it. **Phase 1 of that (the "brain") is built + unit-tested;
the cloud PLUGIN system + the save-backup plugin are Phase 2 (not started).** Nothing built/published.

- **🧠 `translation_manager/resilience.py` (NEW) — the self-healing engine.** An error is a problem to
  SOLVE, not a message to show. `attempt(op, fallback=…, name=…, path=…)` runs an op and, on failure,
  CLASSIFIES it (`locked`/`memory`/`corrupt`/`missing`/`diskfull`/`network`/`io`) and applies the healer
  that fixes THAT class — retry-with-tiny-backoff (AV/indexer file lock, WinError 5/32/33), clear a stray
  read-only bit, `gc`+`EmptyWorkingSet` on MemoryError, create the missing parent, sidecar fallback on
  corruption — then returns `fallback` if all fail (NEVER raises unless asked). Sub-second budget
  (`_DEFAULT_DELAYS=(.02,.06,.12)`), a **circuit-breaker** (`TRIP_AFTER=4`, `COOLDOWN_S=30`) so a
  genuinely-down resource is skipped (instant fallback, no hammering), and every recovery/failure is
  reported SILENTLY via `crash_reporter.report_event` (opt-in gated). Higher-level helpers:
  **`read_json`/`write_json`** = crash-proof JSON state — atomic (temp+os.replace), a `.bak` rescue copy
  written FROM the just-committed good bytes (so it's ALWAYS valid and a corrupt primary can NEVER poison
  it), transparent sidecar fallback (`.bak`/`.tmp`/`.json.tmp`/`.orig`) that REPAIRS the primary from the
  good copy, and a last-resort "park the payload in %TEMP%\translation-manager-recovery" so data is never
  lost. `request()` (bounded exp-backoff for network), `file_op()`, `@resilient` decorator, `health()`.
  **⚠️ recursion trap fixed:** `launcher_prefs` MUST call read/write_json with `report=False` — telemetry
  asks launcher_prefs whether reporting is allowed, so a reported prefs failure would recurse forever.
  Unit-tested: transient-heal, unrecoverable→fallback, atomic+backup, corrupt→served-from-.bak+self-repair,
  circuit-breaker trips, no-recursion, rescue-copy-never-poisoned.
- **⚙️ `translation_manager/perf_manager.py` (NEW) — machine-aware adaptive performance.** Zero new deps
  (pure ctypes Win32, safe no-op off-Windows). Senses HOST (`hardware()` → cores + RAM → tier
  low/balanced/high, cached once) + LIVE load (`snapshot()`: CPU% via GetSystemTimes deltas, RAM% via
  GlobalMemoryStatusEx, user-idle via GetLastInputInfo, foreground via GetForegroundWindow→our PID;
  state ∈ active/background/idle/hidden, 2s cache). The adaptive answer every background job reads:
  **`poll_interval(base_ms)`** stretches cadence when backgrounded (×3) / AFK (×6) / hidden (×8) / machine
  pegged (×2-3, i.e. a game is running → don't steal frames) / low-tier (×1.5), clamped [5s, 30min];
  **`should_defer_heavy()`** (CPU≥90% or <512MB free) lets a heavy job yield; **`trim_memory()`**
  = `gc`+`EmptyWorkingSet` real-time RAM release (rate-limited 60s). **🐛 CRITICAL ctypes bug found+fixed:**
  handles/HWNDs default to a 32-bit C int in ctypes → GetCurrentProcess()'s -1 truncated to 0xFFFFFFFF →
  EmptyWorkingSet silently no-op'd (RAM trim never worked). Fixed by declaring restype/argtypes as
  `c_void_p`. PROVEN: working set 16.4MB→1.5MB (freed 14.8MB) in a live measure. Wired into the Qt
  `CatalogPoller` (`poller._retune()`): the 60s poll now adapts + trims RAM when dormant.
- **🔎 Cascading universal detection (`game_detector.py`).** `deep_scan_drives(want=…)` rewritten into a
  **popularity-ordered cascade with early-exit**: tier 1 = system-drive Steam/Epic/GOG/Xbox/Games libs →
  tier 2 = other drives' libs → tier 3-4 = the wider `_COMMON_ROOTS` → tier 5 = bare drive roots; it STOPS
  the instant `want` (the still-missing ids) is empty. Measured on this PC: Cyberpunk found in **108ms**
  (tier 1) vs a **6,305ms** full scan — ~60× faster on the common path; `want=set()` exits in 25ms without
  touching the disk. `refresh_deep` now only hunts for ids the launcher registries didn't already resolve.
  Yields to a running game between roots when `should_defer_heavy()`. **🔮 Future-proof: server-driven
  detection** — `register_patterns(catalog_rows)` merges per-game `detectFolders`/`detectExes` hints from
  the live catalog at runtime (additive, idempotent), so a NEW game added on the website becomes detectable
  on every installed launcher with NO app update. `main_eel._load_catalog` calls it; `_shape_supabase_game`
  now emits `detectFolders`/`detectExes` (from optional `detect_folders`/`detect_exes` DB columns).
- **Self-healing wired into the state layer:** `paths.py`, `game_detector` persisted cache, and
  `launcher_prefs` now read/write through `resilience` → a corrupt sidecar no longer wipes the user's
  custom install paths / detected games / settings (proven: custom paths survive a corrupted
  custom_paths.json). Verified: full `py_compile`, frontend `tsc -b` clean, the 19 pre-1.0.3 audit fixes
  regress-clean.
- **NEXT — Phase 2 (the cloud PLUGIN system + first plugin), NOT started:** Settings → "תוספים" tab;
  plugins downloaded from the CLOUD (never bundled), added without reinstalling the app; **gated to a
  signed-in user who bought ≥1 GAME (not software)**. First plugin = **"גיבוי אוטומטי שמירות משחקים"**:
  AI-brain auto-locate the save folder + manual add; schedule daily/weekly/monthly/on-launch/on-boot/
  real-time. Design: a `plugins/` registry + cloud manifest (like `mod_source`), a `plugin_host` loader,
  RPCs `list/install/remove/configure_plugin` + a DRM gate `owns_any_game()`, a frontend PluginsTab.

---


## Hogwarts Legacy / Witcher 3 / Plague Tale: Requiem — launcher plumbing READY-and-waiting (2026-07-05)

User: wire these 3 (groundwork done, translation NOT yet) as full native appliers so "when the mod is
ready you just upload and it works — perfectly (install, beta, no bugs)". Built as DOWNLOAD-ONLY native
appliers (auto-update from the Worker like SM2 — no launcher rebuild for a new mod version). **Until each
publishes, the panel shows "התרגום עדיין בעבודה — בקרוב"** (gated on `game.availability!=="available"`);
publishing flips it on. **The full publish recipe is `LAUNCHER_3GAMES_PUBLISH.md`** (what the mod zip MUST
contain per game so the launcher's `rglob` `pick` finds the files, + Worker slug + Supabase steps).

- **Appliers** (`translation_manager/{hogwarts_legacy,witcher3,plague_tale_requiem}_mod.py`, all
  round-trip self-tested, modeled on `gowr_mod.py`): **HL** = additive UE4 override pak → `Phoenix\
  Content\Paks\~mods\zzz_hebrew-WindowsNoEditor_P.pak` (pakchunk0 untouched; revert=delete). **W3** =
  non-destructive `Mods\modHebrew` overlay (revert=delete folder). **PT** = overwrite `TRTEXT\tt23.pc`
  (+`.IGN`) + `FONT\ENGLISH.DPC`, originals backed up OUTSIDE the game (revert=restore). All atomic.
- **`main_eel.py`:** `_HL_ID/_HL_SLUG` (+W3/PT; slugs `hogwarts-legacy-hebrew`/`witcher3-hebrew`/
  `plague-tale-requiem-hebrew`), shared `_native_cache_dir/_native_backup_dir/_native_state/
  _native_write_state`, `_<g>_download_payload` (uses the generic `_native_download_payload`),
  `get_/install_/remove_<g>_mod` + `_run_<g>_install`, and branches in `_mod_state` +
  `_native_update_status` + the native-id tuples (now `_SM2_ID,…,_PT_ID`).
- **Frontend:** `eel.ts` 9 calls; `GameDetailPanel.tsx` generalized `isGowr`→a shared **`NATIVE_DL_API`
  map** (GoWR + these 3) with per-game activation notes — one flow covers all 4. `DownloadsView` native
  dispatch extended (also fixed a latent GoWR miss). `bridge.py` 3 slots × 3 games. Detection + Supabase
  ids already existed (`hogwarts`/`witcher3`/`plague-tale-requiem`, coming-soon/locked, showOnLauncher).
- **Language switch (Hebrew/English/Auto):** install best-effort flips W3 via `set_mode` (no-op until a
  `game_language.LANG_CONFIGS` entry is added — W3 = an "ini" kind editing `Documents\The Witcher 3\
  user.settings [Localization] TextLanguage`; HL/PT store it in an engine config/save not yet safely
  located → left in-game per the note, to avoid corrupting saves). Beta = inherited (the `_offer_update`
  beta-on-beta rule). **Built + installed locally** (per the standing local-build rule; NOT published).

---


## Native appliers now AUTO-UPDATE from the Worker + WD2 beta.4 (2026-07-05)

User: WD2 "לא מקבל עדכון" in the launcher. Root cause: native appliers (WD2/GTAV/GoWR) compared the
installed version against a hardcoded `_<GAME>_BUNDLED_VERSION`, so a new mod version reached launcher
users ONLY via a launcher rebuild. Fixed generically ("fix for all games + future games"):

- **Generic core (`main_eel.py`):** `_native_download_payload(slug, cb, cache_dir, pick)` — download the
  mod from the Worker, `pick(extracted, cache)->payload`, return `(payload, version)`, `(None,None)` on
  any failure → bundled fallback. `_native_latest_version(slug, fallback)` — manifest version for the
  update-check. A new native game inherits auto-update by giving it a Worker slug + a small `pick`.
- **WD2 wired + VERIFIED** (`watchdogs2-hebrew`): `_wd2_download_payloads` pulls the 3 files via
  `_wd2.TARGETS`; install records the SERVER version; update-check hits the manifest. Live download test
  returned beta.4 + all 3 files. **GoWR wired** (`godofwar-ragnarok-hebrew`) incl. storing the applied
  wad's sha in `state.json` (its `is_applied` is a content check) — but the slug is **NOT deployed on the
  Worker (404) → graceful bundled fallback**; needs `npx wrangler deploy` (CF token). **GTAV NOT wired**:
  no Worker slug + its published zip is OIV-format ≠ the launcher's `gtav_he_payload.zip` (raw gxt2) →
  stays bundled (would need the payload published into its release + a slug + redeploy).
- **`_offer_update` beta gate fixed:** if the INSTALLED version is a prerelease, offer newer prereleases
  WITHOUT the opt-in toggle (these mods are beta-only → a stable-only gate stranded every user on their
  first version). A STABLE build still needs the opt-in for a beta.
- **WD2 published beta.4** (label "ערבית (כתוביות)"→**"עברית"** in-game like SM2/CP2077 — patched ids
  627798/698750 in `main_arabic.loc` via decode→edit→`wd2_loc.py encode`, 48,138 strings preserved; +
  `install.bat` interactive installer). Clobbered `v1.0.0-beta.2` (releases/latest per the WD2 gotcha);
  Worker/Supabase/history all beta.4, sha `2e18076d…`. Bundled launcher asset refreshed to beta.4.
- **Launcher rebuilt + LOCALLY INSTALLED** (BUILD_ID `20260704230155`, `C:\Program Files\Translation
  Manager`); bundled WD2 loc = 1585492 (beta.4). NOT published (per the standing local-build rule) — say
  "פרסם" to ship it to other users. Website WD2 guide updated: step 5 "run without Anti-Cheat", step 6
  "Settings → Language → עברית" (matches the new label). Memory [[launcher-native-mod-and-gotchas]].

---


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


