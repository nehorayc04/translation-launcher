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
| `website/` | The public translation-hub site (Vite + React + Tailwind + Supabase + Vercel functions) — **its own git repo**, pushed to `github.com/hebrew-translation-hub/A-translation-hub`. The outer repo ignores it (`/.gitignore`); to commit/push site changes, `cd website` and use git there. Old chat sessions for this project moved with the folder — see "Claude Code sessions" below. |
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
[Releases](https://github.com/hebrew-translation-hub/translation-launcher/releases).

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

- **Mod published — `v1.0.2`** on `hebrew-translation-hub/cp2077-hebrew-mods` via
  `pack_cp2077_mod.py 1.0.2` (full release, NOT prerelease, so the Worker's
  `releases/latest` resolves it). The Worker now serves
  `/cp2077-hebrew/manifest` → `version:"1.0.2"`, sha256
  `8b91b55e4e9a9acb2db532d256d07ce9821a75b3b64fe816701a62129a2da55a`
  (92.3 MB zip — all 3 archives, ~206 verified semantic fixes baked in).
  **`pack_cp2077_mod.py` `MOD_DIR` was repointed** to
  `Game Lab/Cyberpunk 2077/archive/pc/mod` (where the bake scripts deploy —
  the old `Cyberpunk 2077/…` path was empty). ⚠️ **2026-08-21: Game Lab moved
  out of the project tree to `C:\Game Lab\` (it was 409 GB inside a folder
  Google Drive was trying to back up). Every script was re-pointed; the paths in
  the older per-game notes below are kept as the record of what was true then.**
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


## License

See repository for license terms.

---


