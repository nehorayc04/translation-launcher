## Launcher 1.0.2 published to UniGetUI / winget (2026-07-10, PR #400993)

New STANDING RULE ([[launcher-release-checklist]]): **every PUBLIC launcher release on the site
(beta/stable) must ALSO be published to UniGetUI** = a `microsoft/winget-pkgs` PR for that version
(publish the SITE's version, NOT a local build). The old "PR only for stable" note is superseded.
- Source of truth = `GET /api/launcher` → version `1.0.2`, channel beta, build `20260705144705`,
  `downloadUrl` = the `v1.0.2-beta` GitHub asset, `sha256` `eb9c7416…`. **Verified** by downloading
  the actual asset (243,310,816 B) + `Get-FileHash -SHA256` == the manifest sha (winget CI re-hashes
  it, so a wrong sha fails the PR).
- The 3 local `winget-manifest/*.yaml` were already at 1.0.2; only fixed `ReleaseDate`→`2026-07-05`
  (the release's real `published_at`).
- **Method (isolated profile → gh not authed):** token from `git credential fill` (host github.com,
  login `nehorayc04`, scope `repo`) → `$env:GH_TOKEN`. `merge-upstream` fork `hebrew-translation-hub/winget-pkgs`
  master ← upstream (`66547d5`), then Git Data API: 3 blobs → tree (base_tree = fork master tree) with
  `manifests/n/Nehoray/TranslationManager/1.0.2/<name>.yaml` → commit → branch
  `Nehoray.TranslationManager-1.0.2` → PR to `microsoft/winget-pkgs:master`. Upstream had only 1.0.1;
  ADDED 1.0.2 (kept 1.0.1 — winget serves the highest). PR **#400993 OPEN, mergeable=true, 3 files**.
  wingetbot auto-validates; unsigned installer may need a moderator label (like the 1.0.1 PR, which
  merged fine).
- **Validation status (2026-07-11):** the pipeline RAN and flagged **`Validation-Defender-Error`** +
  `Needs-Author-Feedback` (Windows Defender heuristic on the UNSIGNED Inno installer = false positive,
  exactly the caveat above; `license/cla` = success). Posted an author comment
  (`#issuecomment-4948967563`) explaining it's a false positive — same publisher/package as the merged
  1.0.1 (#395277), sha verified vs the 243,310,816-B asset — and asking a moderator to re-validate.
  **Next = wait for a winget-pkgs moderator** to override/re-run the Defender check (as happened for
  1.0.1). Nothing else actionable from our side; the 3 manifest files + sha are correct.
- **STANDING RULE (user 2026-07-12) — submit a Defender false-positive on EVERY build.** To chip at the
  `Validation-Defender-Error` (unsigned Inno installer heuristic FP), run **`python submit_defender_fp.py`**
  (repo root) after every launcher build/publish. It finds the newest `Output\TranslationManager-Setup-*.exe`,
  computes SHA-256, opens the WDSI portal + explorer, and prints the exact form values. **WDSI
  (microsoft.com/en-us/wdsi/filesubmission) is LOGIN-GATED (MS account, no anonymous API)** → the script
  automates everything except the final signed-in upload (role "Software developer" → upload → paste →
  submit, ~30s). This is a MITIGATION only; the real fix is code-signing (**Azure Trusted Signing ~$10/mo**
  is the cheapest — could wire it into `build_exe.bat` to sign every build automatically). [[launcher-release-checklist]]

---


## Final QA + launcher 1.0.2-beta PUBLISHED + website launcher version-history (2026-07-05)

User: "do a final check; if clean + no bugs/upgrades, publish as 1.0.2 beta; add a launcher
version-history on the site like every game has, with the improvements, editable via the admin."
Done end-to-end (this WAS an explicit "פרסם").

- **QA gate (adversarial Workflow: 4 review dims -> independent verify).** Deterministic first:
  py_compile + import-smoke (all 15 native RPCs present) + `tsc -b` all clean. The Workflow found 2
  real bugs (both verified, low severity) - both fixed:
  1. **Plague Tale `is_applied` post-remove FALSE POSITIVE** (`plague_tale_requiem_mod.py`). The
     no-`key_sha` fallback `return True` fired when a backup + live tt23.pc both exist. On remove,
     `revert()` deliberately KEEPS the backups and restores the original, and state is cleared to
     `{}` -> key_sha None -> the card showed the mod ACTIVE after removal. Fix: require a positive
     content match (`return False` when no key_sha). Install already records the sha
     (`_run_pt_install`), revert clears state -> correct both ways (unit-tested: post-remove=False,
     installed=True, never-installed=False). (HL/W3 don't have this - their `is_applied` checks a
     file/folder that revert actually deletes.)
  2. **GoWR install hidden offline/cold-boot** (`GameDetailPanel.tsx`). The shared
     `game.availability!=="available"` "בקרוב" gate (needed for the 3 unpublished games) also hit
     GoWR, whose BUNDLED offline catalog (`games_catalog.py`/`games.json`) still said "coming-soon"
     -> its install button vanished offline. Fix: a per-game **`gated` flag** in `NATIVE_DL_API`
     (gowragnarok=false - bundled payload, always installable, its own `state.available` guards it;
     HL/W3/PT=true - respect the server availability). Bonus: aligned the stale bundled catalog
     gowragnarok -> `available` / `1.0.0-beta.1` (offline badge now correct). Also fixed an em-dash
     I had introduced in the "בקרוב" string.
- **PUBLISHED 1.0.2-beta.** Bumped all 5 version touchpoints 1.0.1->1.0.2 (channel stays beta;
  `LAUNCHER_CHANNEL` unchanged). `build_exe.bat` (BUILD_ID `20260705144705`, dev_build 46) -> ISCC
  (`...Inno Setup 6\ISCC.exe`) -> `publish_release.py 1.0.2 beta` -> GitHub `v1.0.2-beta`
  (prerelease) + Supabase `launcher_releases` id=63 (is_current), sha
  `eb9c741676f3c95dd6ad4292be671c0546ff76163b7522eeb723f52b63db452f`, 243,310,816 B. Verified
  `/api/launcher` -> version 1.0.2, channel beta, buildId == baked (no divergence). Installed
  users self-update via the build-id. Local winget manifest refreshed to 1.0.2 (NO
  microsoft/winget-pkgs PR - beta cadence; public source 1.0.1 < installed 1.0.2 => no bogus
  upgrade nag).
- **Website launcher VERSION-HISTORY (NEW, LIVE `vercel --prod`, DB-driven).** Like the per-game
  timeline, but for the launcher:
  1. **Public API** `GET /api/launcher?history=1` (`api/launcher.ts`) - beta/stable channels only
     (dev/canary are login-gated), deduped to ONE entry per (version, channel) keeping the newest
     row (in-place re-releases insert a fresh row each time), newest-first, shaped
     `{version,channel,notes,sizeMb,downloadUrl,sha256,isCurrent,releasedAt}`, cached
     `s-maxage=30,swr=120`, no auth.
  2. **Timeline** `DownloadsPage.tsx` `LauncherVersionHistory` - a vertical RTL timeline (version +
     channel badge + "גרסה נוכחית" + date/size + the admin `notes` as the "what's new"); renders
     NOTHING when the history is empty/offline.
  3. **Admin edit** `LauncherTab.tsx` - per-release inline **"ערוך תיאור / הוסף תיאור"** (textarea
     -> save/clear via the existing PATCH `notes`; empty clears it) alongside the existing
     add(register)/delete. So the user can edit/add/delete descriptions from the admin.
  Backfilled Hebrew `notes` for 1.0.0 (id 57) / 1.0.1 (id 62) / 1.0.2 (id 63) on the newest beta
  row per version; verified live (`?history=1` = 3 entries with notes). **KEY: `notes` are read
  from the DB live - a new release or an admin edit shows on the site with NO re-deploy.** 3 news
  drafts pushed.

---


## Public BETA ship — installer slimmed + image shimmer + full controller support (2026-06-30)

Big launcher session, **SHIPPED as the first PUBLIC BETA** (channel flipped `dev`→`beta` at the
user's request — beta is publicly downloadable on the site; dev/canary stay login-gated). BUILD_ID
`20260630004537`, dev_build 18, GitHub release **`v1.0.0-beta`** (prerelease), Supabase
`launcher_releases` id=55 (is_current), sha
`7e3e99d9b3673bcb5d180d4b177b0afbd9c5b9fd47118d174f5b2ce1221ce2e5`, 240,849,908 B. `/api/launcher`
verified → version 1.0.0, channel **beta**, buildId == baked. Installed dev users self-update via the
build-id. Winget manifest refreshed (URL→`v1.0.0-beta` + new sha). 4 Hebrew news drafts pushed.

- **Public version label**: the website appends the continuous `devBuild` counter ONLY for dev/canary
  now — a public **beta shows clean `v1.0.0-beta`** (was "v1.0.0-beta.18" because the counter is
  monotonic across channels). `website/src/pages/DownloadsPage.tsx` `devSuffix` gate
  (`channel==='dev'||'canary'`); deployed `vercel --prod`.
- **Installer SLIMMED 259.6MB → 229.7MB (~30MB/12%).** The size driver is Qt/Chromium (588MB raw),
  NOT game images. Trim = post-Analysis filter in `TranslationManager_qt.spec` (`_keep()` drops
  `qtwebengine_devtools_resources.debug.pak` 72MB + ALL `PySide6/translations/*.qm` 57MB +
  `Qt6Designer`/`Qt6Pdf`). Raw dist 756→657MB. **Covers/banners/logos removed from the bundle**
  (`frontend/public/covers/`→`_archive/`, junk screenshot + unused `profile.png` deleted): all 34
  games have ABSOLUTE server cover URLs so the jpgs were dead weight; `coverUrl.ts` fallback → the
  Supabase covers bucket. **Ubisoft-style cache:** `qt_shell/profile.py:_resolve_storage_root()`
  puts the QtWebEngine disk cache in `{app}\data\webengine` when frozen+writable (installer.iss
  `[Dirs] {app}\data` Permissions: users-modify; **excluded from `[Files]`** via
  `Excludes:"\data\*,\data"`; removed on uninstall), fallback `~/.translation_manager`. Delete `data`
  → re-downloads.
- **Image shimmer** (`frontend/src/components/SmartImage.tsx`): `<img>` with a `.skeleton` shimmer
  until it paints (fade-in; hides on error). Applied to HomeView carousel, GameDetailPanel hero+cover,
  AppsView, LibraryView row (GameCard already had one).
- **Full game-controller support** (`lib/spatialNav.ts` + `lib/gamepadMap.ts` +
  `components/ControllerSettings.tsx`). Left stick/D-pad navigate, **right stick scrolls** the focused
  pane, A=activate, B=back. Remappable system buttons: Share/Create/View→Home, Options/Menu→Settings
  toggle, **Guide(centre logo)→sidebar focus** (expand+focus / collapse+restore prior focus) +
  unbound Library/Downloads/Personal/Refresh. **Settings → "שלט" tab** auto-detects the pad (PS5
  DualSense / PS4 DualShock / Xbox via `Gamepad.id` vendor/product) → realistic line-art icon
  (matched to the user's reference PNGs) + type-correct glyphs (✕◯□△ vs A/B/X/Y); in-game-style
  remap (capture mode) + reset; live map via a `gamepadmap` event. Hard-won fixes: typematic
  auto-repeat + stick hysteresis + instant scroll (smooth-scroll stacking was the jank);
  `body.using-spatial-nav :focus` ring so CONTROLLER focus is visible (programmatic `.focus()` ≠
  `:focus-visible`); `navScope` keeps up/down inside sidebar/tablist; `checkVisibility` skips
  opacity-0 buttons; **rectangle-GAP cross-distance in `pick()`** so a full-width control (text-size
  slider) directly below a corner toggle is picked "down"; a 1 Hz watcher re-polls `getGamepads()`
  for native-mode pads (no `gamepadconnected` event). Live tab-switch on `[data-nav-menu]`.
- **Text-size** (`themePrefs.ts` + SettingsView): clean **5% grid 80%–120%** (12.8–19.2px, step 0.8).
  On the focused slider **R1 = +5% / L1 = −5%** (held = continuous; left/right stay for nav). Circular-
  arrow **reset-to-100%** icon button.
- **Sidebar collapse/expand animation FIXED** (icons glued left via constant flex; avatar centred when
  collapsed; padding-right synced to the width transition so nothing snaps).
- **Controller-not-detected was NOT a launcher bug** — DSX's **HidHide** cloaked the physical
  DualSense; user un-cloaked it → works. Decided (AskUserQuestion) NOT to add a "Fix Double Input"
  button (stays in DSX). The user's **PC BSODs are separate**: `0xD1 DRIVER_IRQL_NOT_LESS_OR_EQUAL`
  from the **Intel AX210 Bluetooth driver** (BTHUSB+WLANExt, across days/builds), triggered by the
  DualSense over Bluetooth → USB the pad + update the AX210 driver. Userspace can't cause 0xD1.

---


## Active-install telemetry + version-display + winget fixes (2026-06-30 PM)

Follow-up session after the public-beta ship. Four things shipped.

- **Anonymous active-install counting (NEW).** "How many users installed the launcher?" had no
  precise answer (GitHub download count is reset by `--clobber`; only proxies existed). Added a
  privacy-clean telemetry pipeline: new Supabase table **`launcher_installs`** (`device_id` PK +
  first_seen/last_seen/version/channel/build_id/os; RLS on, **`grant … to service_role`** — a
  psql-created table does NOT auto-grant the API role, same gotcha as the CT views, or the upsert
  403s "permission denied"; `NOTIFY pgrst,'reload schema'` after). The launcher pings on boot:
  `main_eel._ping_install()` (fire-and-forget daemon thread in `main()`) GETs `/api/launcher?device=
  <id>&v=&ch=&b=&os=` where `<id>` = the stable `~/.translation_manager/device_id` (random uuid, no
  PII, no IP) via the new public `auth.device_id()`. The server (`api/launcher.ts` public GET)
  upserts on `device_id` (last_seen=now, first_seen preserved) and returns **`no-store`** for a
  device ping (so an edge-cache HIT never skips the log; the no-device website read stays cached).
  Count active installs: `select count(*) from launcher_installs where last_seen > now() - interval
  '30 days'`. Verified end-to-end with a manual ping → row logged → cleaned. **Reaches real installs
  only after they self-update to a build carrying the ping** (the rebuild below). Snapshot at ship:
  13 registered accounts · 2 active signed-in installs (`profiles.active_device`) · 10 purchases / 4
  buyers · 17 website download-clicks (`analytics_events`).
- **Launcher version display fixed** (`main_eel.py`). The app showed **"v1.0.0-dev.19"** in the
  footer + "על האפליקציה" even though the public release is beta — because `LAUNCHER_CHANNEL` was
  still `"dev"` and `_display_version()` always appended `.{DEV_BUILD}`. Fix: `LAUNCHER_CHANNEL =
  "beta"` + `_display_version()` appends the `.N` counter **only on dev/canary** (beta/stable show a
  clean `v1.0.0-beta`, mirroring the website DownloadsPage `devSuffix` gate). Verified across all
  channels. Needs a rebuild to reach the binary (done below).
- **Republished the launcher** (carries the ping + the version label): `build_exe.bat` (BUILD_ID
  `20260630021416`, dev_build 20) → ISCC → `publish_release.py 1.0.0 beta` → GitHub `v1.0.0-beta`
  (asset clobbered) + Supabase `launcher_releases` id=57. Verified `/api/launcher` → version 1.0.0,
  channel beta, buildId == baked, sha `97b9e9af…`, 229.7 MB. Winget local manifest sha refreshed.
- **winget/UniGetUI stale-version fix (PR submitted).** `winget list` showed installed `1.0.0` →
  **Available 1.1.0** because the PUBLIC winget source still held the OLD `1.1.0` manifest (from
  before the version reset) → UniGetUI offered a bogus "upgrade" to the May build. Since the
  installer's ARP `DisplayVersion` is `1.0.0`, the source must reflect `1.0.0` (not a higher
  version, or it nags forever). Submitted **microsoft/winget-pkgs#395277** (via the Git Data API on
  the existing `hebrew-translation-hub/winget-pkgs` fork — one commit: add `1.0.0`, remove `1.1.0`; CLA already
  signed from the 1.1.0 merge). OPEN + MERGEABLE; awaiting winget's automated validation + moderator
  review (the unsigned installer may need a manual label, as 1.1.0 did). **Do NOT `winget upgrade`
  this package until the PR merges** — it would install the old 1.1.0 build. **UPDATE 2026-07-02:**
  the PR was retargeted from 1.0.0 to the CURRENT build **1.0.1** (still supersedes 1.1.0). Reshaped
  the fork branch `Nehoray.TranslationManager-1.0.0` via the Git Data API (blobs+tree+commit+ref: add
  `1.0.1/*` from `winget-manifest/`, drop `1.0.0/*`, keep the `1.1.0/*` removal), updated title/body,
  re-ran `@wingetbot run`. Net PR diff = add 1.0.1, remove 1.1.0. **MERGED 2026-07-03 05:20 UTC** —
  the winget public source now holds ONLY `1.0.1`, the stale `1.1.0` (May build) is gone. Installed
  1.0.1 == source 1.0.1 → winget/UniGetUI no longer offer the bogus "upgrade"; the package is safe to
  use there again (a client that still shows 1.1.0 just needs `winget source update` / a UniGetUI
  reload to resync). The stale-version saga is CLOSED.

---


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
  rebuild). Release **v1.0.0-beta.1** on `hebrew-translation-hub/spiderman2-hebrew-mods`
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


