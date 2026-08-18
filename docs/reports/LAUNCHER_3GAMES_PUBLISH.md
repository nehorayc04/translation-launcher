# Publishing Hogwarts Legacy / The Witcher 3 / A Plague Tale: Requiem to the launcher

The launcher plumbing for these 3 games is **already wired** as DOWNLOAD-ONLY native
appliers (they fetch the mod from the Worker + auto-update like SM2 — no launcher
rebuild needed for a new mod version). Until you publish, the panel shows
**"התרגום עדיין בעבודה — בקרוב"**; the moment the 3 publish steps below are done the
install button appears and works.

**Each game needs, once the translation is ready:** (1) a GitHub release whose zip
contains the exact files the launcher's `pick` looks for, (2) the Worker slug added +
deployed, (3) the Supabase `games` row flipped to `available` + version/download_url +
a `mod_version_history` row. That's it — no launcher rebuild.

The launcher downloads the mod via `_native_download_payload(slug, …)` and extracts the
files it needs with `rglob` (recursive), so the files can sit anywhere inside the zip —
**only the file NAMES matter.**

---

## 1. Hogwarts Legacy  (`hogwarts`)

| Piece | Value |
|---|---|
| Worker slug | **`hogwarts-legacy-hebrew`** (add to `games/steam/steam_mod_worker/src/index.js` REPOS → `"hebrew-translation-hub/hogwarts-legacy-hebrew-mods"`, then `npx wrangler deploy`) |
| GitHub repo | `hebrew-translation-hub/hogwarts-legacy-hebrew-mods` |
| **Zip MUST contain** | **exactly one `*.pak`** file (the built override pak, e.g. `pakchunk111-WindowsNoEditor_P.pak`). The launcher picks the FIRST `*.pak` in the zip and deploys it as `Phoenix\Content\Paks\~mods\zzz_hebrew-WindowsNoEditor_P.pak`. |
| Deploy done by launcher | additive override pak into `~mods` (pakchunk0 untouched, no backup needed; remove = delete our pak). |
| Activation | in-game Settings → Text Language = العربية (Arabic). |

## 2. The Witcher 3: Wild Hunt  (`witcher3`)

| Piece | Value |
|---|---|
| Worker slug | **`witcher3-hebrew`** (add to the Worker REPOS → `"hebrew-translation-hub/witcher3-hebrew-mods"`, `npx wrangler deploy`) |
| GitHub repo | `hebrew-translation-hub/witcher3-hebrew-mods` |
| **Zip MUST contain** | a top-level **`modHebrew/`** folder holding `content\<mirror>\*.w3strings` (+ per-DLC). The launcher copies the whole `modHebrew` tree → `<game>\Mods\modHebrew`. |
| Deploy done by launcher | non-destructive `Mods\modHebrew` overlay (base `content\` untouched; remove = delete the folder). |
| Activation | in-game Options → Text Language = العربية (Arabic). Speech independent (English kept). |

## 3. A Plague Tale: Requiem  (`plague-tale-requiem`)

| Piece | Value |
|---|---|
| Worker slug | **`plague-tale-requiem-hebrew`** (add to the Worker REPOS → `"hebrew-translation-hub/plague-tale-requiem-hebrew-mods"`, `npx wrangler deploy`) |
| GitHub repo | `hebrew-translation-hub/plague-tale-requiem-hebrew-mods` |
| **Zip MUST contain** | **`tt23.pc`** (required — the Hebrew text slot), and optionally **`tt23.IGN`** + **`ENGLISH.DPC`** (the Hebrew-glyph font pack). The launcher picks each by name and overwrites `<game>\TRTEXT\tt23.pc`, `<game>\TRTEXT\tt23.IGN`, `<game>\FONT\ENGLISH.DPC` (originals backed up in the launcher cache). |
| Deploy done by launcher | overwrite the 3 files (backup outside the game; remove = restore the exact originals). |
| Activation | in-game Options → Text Language = العربية (Arabic). English VO kept. |

---

## The 3 publish steps (per game, when the mod is ready)

1. **GitHub release** — build the mod, package the zip with the files above + a
   `manifest.json` (`{archive_name, sha256, version, channel:"beta", scope}`), create a
   FULL release (so `releases/latest` resolves). Model on
   `games/watchdogs2/pack_and_release.py` (copy it into the game folder + swap the FILES
   list). Keep ONE tag and CLOBBER its assets each build (don't mint `-beta.N` tags that
   sort below the stable tag — see the § "Publish + version sync" playbook).

2. **Worker slug** — add the slug→repo pair to `games/steam/steam_mod_worker/src/index.js`
   `REPOS`, then `cd games/steam/steam_mod_worker && npx wrangler deploy` (needs the CF
   token). Verify: `curl …workers.dev/<slug>/manifest` → 200.

3. **Supabase** — `python universal/publish_version.py <id> <ver> --stage beta --sha … \
   --size … --archive-url <release-zip> --apply` (sets `games.version`/`release_stage` +
   `mod_version_history`), then PATCH the `games` row: `availability='available'`,
   `status='beta'`, `download_url`→the zip, keep `show_on_website`/`show_on_launcher=true`.
   game ids: `hogwarts` / `witcher3` / `plague-tale-requiem`.

After step 3 the launcher's `game.availability` flips to `available` → the install button
appears; `check_game_mod_update` reads the Worker manifest so future versions auto-offer
(beta users on a beta get the newer beta with no toggle). The website Download button uses
`games.download_url` (GitHub direct) — no Worker needed for the website.

## Beta channel — already covered for ALL available games
Every mod ships on the `beta` channel. A user already on a beta of a mod is offered a newer
beta automatically (no opt-in toggle); a stable user needs the Settings "עדכוני תרגומים"
opt-in. This is the `_offer_update` rule (2026-07-05) and applies to every game.

## Language switch (Hebrew / English / Auto) — status
The in-panel 3-way switch needs a `translation_manager/game_language.py` `LANG_CONFIGS`
entry per game (it flips the game's OWN text-language setting). Done today: the install
best-effort flips Witcher 3 via `set_mode` (no-op until a config is added) + every panel
shows the in-game activation note. **Follow-up to enable the live switch:** Witcher 3 =
add an "ini" kind editing `Documents\The Witcher 3\user.settings` `[Localization]
TextLanguage=AR/EN` (safe, editable file). Hogwarts / Plague Tale store the active
language in an engine config/save that hasn't been safely located — leave activation
in-game (the note tells the user) until the storage is confirmed, to avoid corrupting saves.

## Launcher code map (what's wired, for reference)
- Appliers: `translation_manager/{hogwarts_legacy,witcher3,plague_tale_requiem}_mod.py`
  (apply/revert/is_applied — round-trip-tested).
- `main_eel.py`: `_HL_ID/_HL_SLUG` (+ W3/PT), `_native_cache_dir/_native_backup_dir/
  _native_state/_native_write_state`, `_<g>_download_payload`, `get_/install_/remove_<g>_mod`
  + `_run_<g>_install`, and branches in `_mod_state`/`_native_update_status`/the native-id
  tuples (`_SM2_ID,…,_PT_ID`).
- `qt_shell/bridge.py`: 3 slots × 3 games. `frontend/src/lib/eel.ts`: 9 calls.
  `frontend/src/views/GameDetailPanel.tsx`: the shared `NATIVE_DL_API` map (GoWR + these 3).
