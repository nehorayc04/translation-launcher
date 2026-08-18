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
`hebrew-translation-hub/watchdogs2-hebrew-mods`, FULL release `v1.0.0-beta.1` (so `releases/latest`
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

### WD2 in-game defects fixed before the QA run — orientation, bidi, font (2026-06-25/26)

The user's screenshots showed reversed text, broken mixed EN+HE, tofu, oversized Hebrew. Root causes
and fixes (all three are UNIVERSAL patterns, not WD2 quirks):

- **🔴🔴 REVERSED TEXT = orientation decided by the SOURCE FILE instead of the ENGINE's metadata.**
  WD2 has TWO renderers: spoken subtitles (`enum="soundbinary\N.bnk"`) go through a **bidi**
  narrative path → store **LOGICAL**; everything else (menus/HUD/descriptions/missions/messages/
  email) is **NON-bidi** → store **VISUAL** (pre-reversed). The build used to pick orientation by
  *which json the line came from* (ui→visual, sub→logical), but plenty of NAMED (frontend) content
  sat in the subtitle queue → it shipped LOGICAL into a non-bidi renderer → rendered mirrored.
  **Fix: `wd2_sub_merge.py` decides orientation from the OASIS ENUM, per line** (`soundbinary` →
  `sub_logical()`, else `UI.visual(norm_breaks())`), regardless of source file. Result 24,795 visual
  / 16,309 logical. **UNIVERSAL: when an engine has two text renderers, the per-line orientation must
  come from the engine's own metadata — never from your pipeline's file layout.** (Side effect: the
  deterministic scanner still classifies by file, so its `MISORIENTED` count is a scanner artifact,
  not a defect — see the verify note below.)
- **Mixed EN+HE / brackets = hand-rolled reversal.** The old `visual()` reversed run ORDER but kept
  every non-Hebrew run forward → multi-word Latin came out word-reversed ("Old Glory"→"Glory Old")
  and brackets were never mirrored. **Fix: run the real UBA** — `python-bidi`
  `get_display(s, base_dir='R')` — with every engine token (`[TOKEN]`/`{VALUE}`/`%d`/`&#xA;`/`\n`)
  swapped to a PUA placeholder first and restored after, or python-bidi mangles them. Full rule set
  in §8b; requires the repo **`.venv` python**.
- **Font (SDF atlas) — measure, don't guess.** Final shipped params in `work/wd2_font.py`:
  **`PX=30, RAISE=4, TRACK=7, SPACE_BUMP=4, LATIN_TRACK=0, SS=8`**, Heebo-Medium, natural Heebo
  advances. Lessons: (a) Hebrew is all cap-height (no x-height) so at equal nominal px it LOOKS
  bigger than Latin → size it ~85% of the Latin cap-height; (b) "raise it" meant **position**
  (`RAISE`), not size — ask which; (c) a constant metric gap reads *optically uneven* because it
  ignores the donor font's kerning → keep the font's **natural advances** and tune one global
  `TRACK`; (d) "uneven spacing" was really **fuzziness** — raising the supersample `SS=4→8` fixed
  both, since AA bleed distorts perceived gaps; (e) glyphs need real atlas padding or neighbours
  bleed into the sampled cell (see the GTA/GoWR notes for the same failure).

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
  verify `gh api repos/hebrew-translation-hub/watchdogs2-hebrew-mods/releases/latest` resolves to beta.2 with
  the new manifest. `games.download_url` points at the beta.1 asset (also clobbered to beta.3, so
  identical bytes — fine). Memory [[parallel-agent-qa-protocol]], [[delegate-all-translation]].

### WD2 SPOKEN subtitles + dialogue — ✅ COMPLETE + PUBLISHED beta.2 (2026-06-20)

The spoken subtitles/dialogue are DONE and shipped. The local LM ran to ~69%, then the
remaining lines + a full 3-agent QA pass (review→fix EN vs HE, the `agent_handoff_subs/`
`qa_get_batch`/`qa_merge` loop — the GOOGLE agents do the translating/fixing, NOT Claude;
see [[delegate-all-translation]]) brought ALL 21,678 lines to QA-clean. Claude verified
(0 real token mismatches, 0 foreign/niqqud, full coverage), built (`wd2_sub_merge` UI-visual +
subs-LOGICAL → `wd2_loc.py encode` → `wd2_archive.py deploy` to common/patch/patch2), and
published **`v1.0.0-beta.2`** (GitHub `hebrew-translation-hub/watchdogs2-hebrew-mods`, sha `fae97e28…`,
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


