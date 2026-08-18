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

Private repo **`hebrew-translation-hub/steam-hebrew-mods`** is the source of truth.
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

