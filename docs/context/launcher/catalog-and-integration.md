## 🎮 FOUR GAMES BROUGHT INTO THE LAUNCHER — Anno 1800 · Hogwarts · RDR2 · Corsair Cove (2026-08-14, LOCAL build, NOT published)

The ask was "full and smooth support" for four titles. Measuring first showed the real gap was
narrow and identical across all four: **every one was already published, downloadable and correct
on the WEBSITE — and `show_on_launcher=false` on all four**, so none could be installed with a
click. Two were fully wired in the launcher and just gated by the flag; two had no launcher
presence at all.

| | Worker slug | launcher applier | what was missing |
|---|---|---|---|
| **Hogwarts** | ✅ beta.1 | ✅ native (`hogwarts_legacy_mod`) | the flag only — **validated 9/9 end-to-end against the LIVE Worker** (download → apply → is_applied → revert, `pakchunk0` byte-untouched) |
| **Anno 1800** | ✅ beta.2 | ✅ generic + `data4` hook | the flag + a payload-cleanliness fix |
| **RDR2** | ❌ 404 | ❌ none | slug + config |
| **Corsair Cove** | ❌ 404 | ❌ none (not even a GameConfig) | slug + config + a deploy-subdir mechanism |

- **🔑 THE BIG WIN — NEITHER NEW GAME NEEDED AN APPLIER, AN RPC, A BRIDGE SLOT OR A UI BRANCH.**
  Reading the two published packages decided it: RDR2's is a flat Lenny's-Mod-Loader tree that
  drops into the game root, and Corsair Cove's is two paks that overwrite the game's own stubs —
  both are exactly what the GENERIC download-mod path already does. They ride `mod_slug` +
  `mod_files` like CP2077/Anno, and inherit the DRM gate, progress, update check and cache
  machinery for free. **Read the artifact before writing an applier** — the earlier plan was two
  native modules plus ~8 wiring sites.
- **🔴🔴 THE SAFETY HOLE THAT THIS EXPOSED, now closed for EVERY download-mod: the generic
  installer had no backup.** It `shutil.copy2`'d over whatever was there and `disable()` DELETED
  the same paths — so a user whose RDR2 already had a `dinput8.dll` from another ASI mod would
  have it silently replaced, and then **deleted** on remove, breaking that other mod. New
  `game_mod.orig_dir(game_id)` captures the user's file ONCE on the first overwrite (`not
  keep.exists()`, so a re-install/update can never overwrite a real original with our own copy)
  and `_restore_or_delete()` puts it back on remove/clear-cache — the proven `.orig` scheme from
  `steam_mod`, now generic. **The backups are a SIBLING of the cache dir** (`<id>__orig`), never
  inside it, or the payload glob would deploy them as mod files.
  **Proven on the real packages: install shadows the user's `dinput8.dll`, remove restores it
  BYTE-EXACT** (and the same for Corsair Cove's two 339-byte stubs).
- **🔴 A SENTINEL MUST BE UNMISTAKABLY OURS.** `mod_files` doubles as the removal fallback for a
  user who installed BY HAND (no `installed_files` record). Listing RDR2's generic `dinput8.dll`
  there would delete a loader that may belong to a different mod, so the sentinels are the two
  files only this translation ships (`Ko Games Studio.gxt2` + the Hebrew-injected
  `font_lib_efigs.gfx`) — dropping those already reverts the game to English, which is exactly
  what the mod's own readme says uninstall means.
- **Package metadata no longer lands in the user's game folder.** `_payload_files` copied
  EVERYTHING in the cache, so Anno was depositing `install.py`, the Hebrew readme AND a 2.5 MB
  duplicate `data4.rda` into `Documents\Anno 1800\mods`. Now a generic depth-0 skip
  (`install.py` / `manifest.json` / `readme*` / `קרא_אותי*` / `*.md`) plus a per-game
  `GameConfig.payload_exclude` (Anno: `data4.rda`, which the maindata hook reads FROM THE CACHE).
  Matched at depth 0 only, so a payload that legitimately contains such a name deeper in its tree
  is never dropped — verified both ways.
- **`GameConfig.deploy_subdir` (NEW)** — a FLAT package that belongs in a fixed sub-folder.
  Corsair Cove ships its two paks at the archive root but they live in
  `CorsairCove\Content\Paks`; `_deploy_root()` now appends it (ignored when `documents_subdir` is
  set). Verified live: `deploy = E:\Games\Corsair Cove\CorsairCove\Content\Paks`.
- **🔴 THE DETECTOR NEVER READ `common_paths` — a DRM-free install only appeared after the
  minutes-long deep drive scan.** `detect_via_launchers()` asked eight store registries and
  nothing else, so Corsair Cove (`E:\Games\Corsair Cove`, RUNE) was simply absent. New
  `detect_common_paths()` walks each GameConfig's `common_paths` and confirms every hit with that
  config's own `validation_file` (so a leftover/empty folder is never accepted). It runs **LAST**,
  so a real store registry always wins over a fixed guess. Cost: **0.10 s**, 16 → 17 games, and
  Corsair Cove is now found instantly. Helps every non-store title, not just this one.
- **`find_exe` now prefers the config's own `validation_file`** when it ends in `.exe` — a fixed,
  verified answer that beats guessing a name across a list of `bin/` sub-folders. Anno's exe
  (`Bin\Win64\Anno1800.exe`) went from `None` to resolved; **all 7 detected games now resolve an
  exe** (it feeds the Settings EXE field and the launch ladder).
- **Verified through the layer the UI actually consumes**, not the raw catalog: `get_game()` →
  all four `available` + `has_mod_support` + `is_installed`; `get_game_mod_state()` → the three
  generic ones carry their `modSlug` (Hogwarts is deliberately blank — it is a NATIVE applier and
  the panel routes it through `NATIVE_DL_API`); `check_game_mod_update()` answers for all four
  with the right `latestVersion` from the Worker. ⚠️ A first pass read `_load_catalog()` and got a
  STALE SWR snapshot (`availability=translating`, two games missing entirely) — **call
  `refresh_catalog()` before asserting anything about catalog state, or you will debug a cache.**
- Activation notes added for the two new panels: both need **zero in-game action** (RDR2 renders
  on launch, Corsair Cove's Hebrew sits in the already-default locale slot).
- **⚠️ THE FLAG IS LIVE, THE CODE IS NOT — a real gap to decide on.** `show_on_launcher` is read
  from the catalog by EVERY installed launcher, but the published build is **`20260719225516`
  (July 19)**, which predates the Anno maindata hook (`anno1800_data4.py`, late July) and knows
  nothing of the two new configs. So for a user on the published 1.1.0 right now: **Hogwarts
  installs correctly** (its plumbing shipped 2026-07-05), while **Anno would deploy the loose mod
  WITHOUT the maindata font injection** (garbled pre-baked screens) and **RDR2 / Corsair Cove show
  a card with no install support** (`has_mod_support=False` → the honest disabled chip, not a
  crash). Reaching other users correctly needs a launcher publish; until then this is the user's
  call to leave on or roll back.
- **STATE: local build only.** BUILD_ID **`20260813212621`** (DEV 237, UTC — the local clock reads
  00:26). All four flipped to `show_on_launcher=true` in Supabase, bundled
  offline parity updated (`games_catalog.py` + `games.json`: Anno → available/beta.2, RDR2 →
  available/beta.1 + ₪53, Corsair Cove added), Worker redeployed with both slugs (`/manifest` +
  `/archive` verified 200). Nothing about the MODS themselves was re-published.


