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
- **Published `pack_and_release.py`** → GitHub `hebrew-translation-hub/gtav-hebrew-mods` release
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

### 🔴🔴 ERR_GEN_ZLIB_2 after a launcher install — ROOT-CAUSED + FIXED (2026-06-29, dev_build 8, BUILD_ID `20260629034518`, release id=52)

User report: the launcher install "completed" but the game **failed to load Story Mode with
`ERR_GEN_ZLIB_2`**; pressing שחזור restored it and the game booted fine. The mod content was
never the problem — **the ARCHIVE LAYOUT was.**

- **ROOT CAUSE — a full re-pack drops the original padding.** `serialize_open_rpf` re-lays every
  file from scratch, so `mods\update\update.rpf` came out **2.6 GB → 1.8 GB** (~800 MB of original
  inter-file padding gone). RAGE streams these archives by absolute block offset, so a re-laid
  (even if internally-consistent) archive breaks the engine's expectations → zlib read failure at
  story load. **OpenIV never re-lays — it edits IN PLACE.**
- **FIX = `gtav_rpf7.serialize_inplace(original_buf, root)`** — start from the ORIGINAL bytes, walk
  the tree, and for each file marked `_dirty` **append** its new bytes at a fresh 512-aligned offset
  at EOF and patch **only that file's 16-byte TOC entry** (`NameOffset | csize | offsetBlocks |
  resource-bit`, plus `usize`/`flags`). Every untouched file keeps its exact original offset AND the
  padding between files survives. `Node.__slots__` gained `_name_off` + `_dirty`; `parse_open_rpf`
  records `_idx`/`_name_off`; `replace_file_data` sets `_dirty=True`. `gtav_mod._patch_update2`/
  `_patch_update` now call it (the small NESTED rpfs are still fully rebuilt — that is correct, they
  are re-embedded whole as one file).
- **Verified:** update2 **+5.5 MB** (grew, as expected — appended), `update.rpf` stayed **2.74 GB**
  (was shrinking to 1.8 GB), all other files byte-identical.
- **⚠️ FALSE LEADS burned on the way (do not re-chase):** (a) the bit-63 **resource flag** — real bug,
  but `gtav_rpf7.py` already carried the fix; (b) "the Hebrew fonts are resources" — they are
  `_res=0` binary; (c) **4,293 ".meta inflate failures"** in my verifier were **false positives** —
  those files use a non-deflate codec and round-trip byte-exact.
- **⇒ RULE 11 in `orchestration/RULES.md` (universal, any container):** a read-modify-write of a
  game archive must be **IN-PLACE** (preserve offsets + padding, append the changed files, patch only
  their TOC entries) — never a full re-pack. **Always compare output size to the original; a dramatic
  shrink is a red flag**, and the failure surfaces only in-game, long after the "install succeeded".

### Text reverts round 2 + launcher ship (2026-06-29)

- The 2026-06-26 wording changes were **REVERTED per the user**: `EXIT`/"עזוב" → **"יציאה"** (the
  entry the user saw is the ALL-CAPS `EXIT`), `Story Mode` → **"מצב סיפור"**, "נכנס למצב עלילה" →
  **"נכנס למצב סיפור"**, "צא" → **"יציאה"**. Applied to `agent_handoff_full/reuse_he.json`
  (backups `.bak_exitstory`, `.bak_revert`) → rebuilt the 610 gxt2 → regenerated BOTH the
  launcher payload `translation_manager/assets/gtav/gtav_he_payload.zip` (6,083,766 B, EXIT=יציאה
  verified inside) and the two OIVs.
- **PUBLISHED (gate #3 approved by the user, "פרסם את התוכנה החדשה כולל התיקונים"):** `build_exe.bat`
  → BUILD_ID `20260629034518` → ISCC → `publish_release.py 1.0.0 dev` → GitHub `v1.0.0-dev` (asset
  clobbered, sha `66c115e945728a280e18705e9ae3edb83b8e512252b9097cb5107721ee52c1cc`, 259,594,152 B)
  + Supabase `launcher_releases` id=52 is_current. Verified `/api/launcher` buildId == baked.
  winget manifest sha + ReleaseDate refreshed.
- **⚠️ STILL OPEN:** (1) the user's **in-game confirmation** that a launcher install now loads Story
  Mode (revert is one click); (2) the **website OIV is still the OLD text** (`EXIT=צא`) — republishing
  it is gate #2 and was NOT approved; (3) `games/gtav/tools/rpf7_writer.py` (the standalone dev copy)
  still lacks `serialize_inplace` + the bit-63 fix — **sync it before using it for any deploy**
  (the OIV build path does not use it, so it is not currently dangerous).

### ✅ Community `/translate` pool LIVE — 141,212 rows in 3 Hebrew categories (2026-06-29)

Uploaded the whole updated GTA text layer to the public pool, categorized like every other game.
Builder: **`games/gtav/work/build_ct_strings.py`** → `extract/ct_strings.json` →
`universal/community_translate.py import gtav …`.

- **Categories (visibility order, `section`):** `ממשק ותפריטים` **52,465** (any string present in
  `global.gxt2` — menus/HUD/settings/weapon+vehicle names) → `כתוביות עלילה` **46,665** (per-mission
  tables: objectives/help/cutscene text) → `דיבורי רקע` **42,082** (`*aud.gxt2`-only = spoken
  conversation / ambient banter). Derived from `agent_handoff_full/occurrences.json` (`{EN: [[file,
  hash]…]}`), so the split is measured from the real archive, not guessed.
- **Scope:** 197,223 unique EN → drop **51,920** via the run's own `skip.json` (codes/labels/URLs/
  emails — audited: only 85 of them even *look* like prose, and those are URLs/emails/song titles) →
  drop **4,082** with no real letter once engine tokens are stripped → **141,221 uploaded**
  (140,987 already translated, 234 open). ⚠️ **The remaining 4,316 "untranslated" from a naive
  count were almost all junk** — the token/number-only filter is what turned 4,316 open into 234.
- **🔑 `string_key` = the raw ENGLISH source string**, because `build_full_gxt2.load_translations()`
  is keyed by it → an approved `community_translate.py export gtav` is **literally `hebrew.json`**
  and drops into the builder with ZERO glue (CLAUDE.md §17 rule 4). Safe here: max EN length is
  **2,103 chars**, under Postgres' ~2,704-byte btree index limit (the builder asserts at 2,400).
- **🔴 `current_he` must be the SHIPPING Hebrew, not the raw accumulator.** `hebrew.json` still
  carries the agent's Latin glosses (`פרנקלין (Franklin)`, `נער את המשטרה (cops).`) which
  `strip_gloss()` removes at bake time — so the pool applies **the bake's own `strip_gloss`** before
  upload. Otherwise contributors review text the game never renders. **UNIVERSAL: seed the pool with
  the value the BUILD emits, not the value the translator wrote.**
- **⚠️ `community_translate.py` `.strip()`s `string_key`** → 9 GTA pairs that differ only by
  surrounding whitespace (`"vehicles"`/`"vehicles "`, `mph`, `km/h`, `D`, `Crate`…) collapsed to one
  row (141,221 sent → **141,212** stored). Harmless (all 9 are already translated on both variants);
  only a future community edit wouldn't map back to the whitespace variant. Know it before debugging
  a small count mismatch after any EN-keyed import.
- **🔴 The post-import cache refresh timed out (57014) and the game did NOT appear on `/translate`.**
  `/api/translate?action=games` reads the precomputed `translation_progress_cache`, so a failed
  recount = an invisible game even though all 141k rows are in the DB. Re-running the single-game
  RPC (`refresh_translation_progress_cache {p_game:"gtav"}`) fixed it in one call. **Two fixes made
  so this can't repeat: `community_translate.py` now RETRIES the refresh 3× — and catches
  `BaseException`, because `_req()` calls `sys.exit()` on an HTTPError and `SystemExit` is NOT an
  `Exception`, so the existing "never fail an import" guard had never actually worked.**
- **⚠️ PostgREST auth reminder:** this project's `SUPABASE_SERVICE_ROLE_KEY` is an `sb_secret_…` key,
  which PostgREST **rejects from a browser User-Agent** (401 "Forbidden use of secret API key in
  browser") — the opposite of the Supabase *Management* API, which REQUIRES one (Cloudflare 1010).
- **Verified live:** `/api/translate?action=games` → gtav 141,212 · `action=list` → the 3 Hebrew
  category chips with the exact counts, `context` showing the source file + occurrence count
  (`abgail2.gxt2 +1 · 6 מופעים`), and `currentText` = the gloss-stripped shipping Hebrew.
- **Observation for a later QA pass (not fixed — [[delegate-all-translation]]):** name handling is
  inconsistent — `Michael→מייקל`/`Franklin→פרנקלין` are Hebraized while `Trevor` stays Latin
  mid-sentence. A `name_registry.json` sweep like SM2/PT would unify it
  ([[name-registry-and-internet-check]]).

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


## GTA V **Enhanced** Hebrew — pipeline BUILT + validated, 🟢 GO, blocked only on the one-time OpenIV bootstrap (2026-08-02)

New project at `games/gtav_enhanced/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/`).
Install `E:\Games\Grand Theft Auto V Enhanced`, **v1.0.1158.13**. **Nothing in the game folder
was modified** — read-only recon + a toolchain validated against the LEGACY install.

- **🔑 THE MAGIC DECIDED IT — `7FPR` = RPF7, the SAME container as Legacy**
  ([[engine-family-reuse-check-magic]]). One `head -c 16` collapsed container + codec + writer +
  RTL into pure reuse. Enhanced `update.rpf` = 3.12 GB / 1,790 entries / **enc=NG**, i.e. exactly
  the state Legacy-vanilla is in (Legacy vanilla NG 1,644 · Legacy `mods\` OPEN 1,659).
- **🔴 NG EVERYWHERE — no readable island, proven by exhaustive scan, not assumed.** A
  512-byte-aligned sweep of the whole 3.1 GB `update.rpf` found **220 nested RPFs, all 220 NG**;
  all **97** `update\x64\dlcpacks\**\*.rpf` are NG; `update\x64\data\` holds only
  `errorcodes\*.txt`; **0 loose `.gxt2` and 0 loose `.gfx`** anywhere. `rpf.cache` (16 MB, magic
  `HSHR`) is a hash cache with **no filenames**; `index.bin` is opaque. GTAUtil only prompts
  interactively; OpenIV is not installed. ⇒ **Enhanced's own vanilla text cannot be read until
  the OPEN `mods\` copies exist** — the SAME documented bootstrap gap as Legacy, not a regression.
- **🟢 Deploy mechanism survives:** Enhanced keeps `mods\`, via **OpenRPF.asi + `dsound.dll`**
  (the Enhanced replacement for `OpenIV.asi` + `dinput8.dll`) plus **ZEnhanced** so OpenIV
  recognises the install. BattlEye guards Online, not the SP `mods\` path.
- **🔑 THE PROPERTY THAT MAKES THE PORT CHEAP: the corpus is keyed by the ENGLISH SOURCE STRING**
  (141,001 EN→HE in `games/gtav/agent_handoff_full/`, shared — no second corpus). It is therefore
  independent of whatever Enhanced re-hashed/renamed: shared English → Hebrew automatically,
  Enhanced-only English → stays English (a readable fallback, never blank).
- **🔴🔴 NEVER ship Legacy's BUILT gxt2 into Enhanced.** A gxt2 **replaces the whole table**, so an
  Enhanced-only key missing from Legacy's file renders **BLANK** — worse than English. The build
  must always overlay onto **Enhanced's own vanilla tables**, which is why the bootstrap is a hard
  prerequisite rather than a convenience.
- **✅ THE WHOLE CHAIN IS VALIDATED AGAINST REAL ARCHIVES** (Legacy `mods\`, since Enhanced can't be
  read yet): lazy RPF7 walk → nested archive → GXT2 decode → `global.gxt2` = **69,209 entries,
  64,354 Hebrew**; extraction produced **656 gxt2 + 3 font libraries, exit 0**; and the new build
  script reproduces the documented Legacy build **EXACTLY** — 278,749 entries / 165,093 Hebrew
  (59.2 %) / 47 token deviations. That exact-match is the proof the ported code path is correct.
- **🔴 A per-file ENCRYPTION flag exists even under an OPEN table-of-contents.** A binary entry's
  last u32 is **`IsEncrypted`**, not a generic flag word: `mods\x64b.rpf` reads OPEN while **562 of
  its 602 gxt2 stay encrypted**. Fix = AES-256-ECB ×16 (the public GTA5 key) **before** the raw
  inflate — decrypt then inflate, never the reverse. `tools/rpf_lazy.py` does it and treats a
  still-unreadable payload as *skipped + reported*, never fatal. **UNIVERSAL: an archive-level
  "OPEN" says nothing about its individual payloads — check the per-entry flag, and make an
  extractor tolerate one unreadable file instead of aborting the sweep.**
- **Tools (run with the repo `.venv` python):** `tools/rpf_lazy.py` (NEW — lazy read-only RPF7
  walker; the write-path `rpf7.py` materialises every payload and would cost ~3 GB of RAM on
  `update.rpf`) · `tools/rpf7.py` (the **vendored** `translation_manager/gtav_rpf7.py`, the only
  copy with `serialize_inplace` + the bit-63 resource-flag fix — the dev copy in `games/gtav/tools/`
  still lacks `serialize_inplace`) · `tools/gxt2.py` · `work/extract_vanilla.py` (**discovers** the
  language/font paths instead of hard-coding Legacy's) · `work/build_hebrew.py` (imports
  `strip_gloss`/`_toks`/`load_translations` from the Legacy builder so the two can never drift;
  emits `build/coverage.json` whose `missing_english` IS the Enhanced-only work item) ·
  `work/build_oiv.py` (paths taken from `extract/layout.json`, never hard-coded).
- **Verified Legacy layout** (what the extractor expects to find, and re-verifies on Enhanced):
  `update2.rpf → x64/data/lang/american_rel.rpf` = the base table (**610 gxt2**) ·
  `update.rpf → x64/patch/data/lang/american_rel.rpf` = a 44 KB patch delta ·
  `update.rpf → x64/data/cdimages/scaleform_platform_pc.rpf` + `scaleform_generic.rpf` = the fonts.
- **✅✅ BUILT — the two OIV packages exist and are content-verified (2026-08-02).** The user supplied
  the OpenIV export; everything after it ran unattended.
  `release/gtav_enhanced_hebrew.oiv` (11,594,499 B) + `release/gtav_enhanced_restore.oiv`
  (10,831,295 B), **1,220 `<replace>` each** (610 gxt2 × the two byte-identical tables).
  Verified by reading back **out of the package**: `content/update/update2.rpf/x64/data/lang/
  american_rel.rpf/…`, and its `global.gxt2` = **74,140 entries / 64,935 Hebrew**, sample
  `'בוזא םוח עבצ'` = VISUAL order, correct.
  Build: **569,854 entries / 331,358 Hebrew (58.1 %) / 47 token deviations** (the same benign `~s~`
  set as Legacy).
- **🔴🔴 THE OpenIV EXPORT TRAP — "export the archive" ≠ "export its contents".** The user's first
  export produced the OUTER trees of `update.rpf` (3.7 GB) + `update2.rpf` (650 MB) as folders, but
  **every one of the 248 nested `.rpf` was copied out still NG-encrypted** — including the one that
  matters. The gxt2 only appear when you open `american_rel.rpf` *itself* in OpenIV and export from
  inside it. **UNIVERSAL: when a tool "extracts" a container, check whether nested containers came
  out as DATA or as still-sealed blobs — a 4.3 GB export that contains zero usable files looks like
  success from the outside.** `extract_vanilla.py --from-export DIR` now ingests such a loose export
  directly (walks for `.gxt2`/`.gfx`, lays them out, writes `layout.json`).
- **🔑 `american_rel.rpf` IS BYTE-IDENTICAL IN `update.rpf` AND `update2.rpf`** (md5 `06e01d53…`,
  5,494,784 B, 611 entries — 610 gxt2 + the root dir, matching Legacy's 611 exactly). Load order
  decides which wins, so the OIV patches **both**.
- **🔑 OpenIV rewrites NESTED archives as OPEN when it edits** — proven on Legacy, whose
  `mods\update\update2.rpf` → `x64/data/lang/american_rel.rpf` reads **OPEN / 611 entries**. So the
  deploy needs no OPEN archive from us: installing the OIV is what converts them.
- **📊 THE ENHANCED-ONLY CORPUS IS SMALL AND MOSTLY IRRELEVANT — measured, not assumed.**
  Legacy unique EN 197,223 · Enhanced unique EN 201,943 ⇒ **only 4,959 strings are new**. Of the
  61,193 untranslated, **51,918 are the deliberate skip-list** (codes/brands/identifiers) and 4,959
  are Enhanced-only; the new ones are overwhelmingly **new graphics-settings acronyms** (`TAA`,
  `DLAA`, `HBAO`, `2X/3X/4X` — which stay Latin in Hebrew anyway) plus **332 GTA+/Online marketing**
  strings unreachable in single-player. ⇒ single-player coverage is effectively identical to Legacy.
  Full list at `build/enhanced_only.json`.
- **Installed into the game root (reversible, delete to undo):** `OpenRPF.asi` (the **standalone**
  build, 2025-12-17 — 5 months newer than the 0.2 bundled in ZEnhanced) + `xinput1_4.dll` (the ASI
  loader; Enhanced's proxy is **`xinput1_4.dll`**, not Legacy's `dinput8.dll`). ZEnhanced staged at
  `C:\Users\Nehoray_Cohen\Tools\ZEnhanced\`; `OpenIV.exe` backed up to `OpenIV.exe.zenh_backup`
  (md5 `9329cfae…`) before running it. ⚠️ Do NOT click ZEnhanced's "Enhanced Files" — it would
  overwrite the newer OpenRPF with 0.2. ⚠️ BattlEye ships with Enhanced: an ASI loader is
  single-player only, never go Online with it.
- **⚠️ OpenIV WAS installed all along** — at `%LOCALAPPDATA%\New Technology Studio\Apps\OpenIV\`
  (4.1.0.1502), NOT in Program Files, and with no uninstall registry entry. An earlier "OpenIV is
  not installed" call was wrong. **Check `%LOCALAPPDATA%\<vendor>\Apps\` before concluding a
  portable-style app is absent.**
- **✅ FONTS INJECTED — into ENHANCED's OWN faces, not copied from the Legacy build.** GTA V's
  native `SET_TEXT_FONT` draws from the Scaleform libraries, so the gxt2 alone would render tofu.
  Chain (proven Legacy tooling, unchanged): `ffdec-cli -swf2xml` → `games/gtav/work/font_add_hebrew.py`
  (donor `work/fontwork/gen_allheb.xml`) → `-xml2swf`. Injected into **EVERY face**
  ([[font-inject-every-face]] — the Menyoo lesson): `font_lib_efigs_pc.gfx` **9/9 faces**
  240,056 → 299,971 B, `font_lib_efigs.gfx` **7/7 faces** 96,789 → 125,965 B, all export names
  preserved (renaming breaks Scaleform's name linkage). **Consistency check that the method is
  right: the rebuilt `font_lib_efigs.gfx` came out at 125,965 B — byte-for-byte the size of the one
  extracted from the LIVE Legacy mod.**
  🔑 **`font_lib_efigs.gfx` is byte-identical between the two editions (md5 `fc85caca…`) but
  `font_lib_efigs_pc.gfx` is NOT** (240,056 vs Legacy's 232,883) — which is exactly why both were
  re-injected from Enhanced's own vanilla instead of shipping Legacy's `_HEBREW.gfx`.
- **🔴🔴 THE OIV SYNTAX TRAP — OpenIV REPORTS SUCCESS WHILE INSTALLING NOTHING.** The first
  package used `<replace>name</replace>` inside a nested `<archive>`; OpenIV's log shows
  **`Unknown archive action at node: "content>archive>archive>replace"`** ×1,222 and then finishes
  with no error dialog. **`<replace>` is not an OIV action.** The correct, proven form (copied from
  `games/gtav/release/gtav_hebrew_FULLTEXT.oiv`) is **`<add source="FLAT_NAME">target.ext</add>`**,
  with `<archive path=…>` using **BACKSLASHES**, `createIfNotExist="True"`, and `source` a **FLAT**
  name inside `content/` (no sub-directories — a nested source path is silently ignored too).
  **UNIVERSAL: when a GUI installer has a working precedent in this repo, read that artifact's own
  manifest and copy its syntax verbatim — do not infer the schema; and read the tool's LOG rather
  than trusting its exit state, because "installed successfully" can mean "matched zero actions".**
- **FINAL PACKAGES — `release/gtav_enhanced_hebrew.oiv` (5,947,610 B) +
  `gtav_enhanced_restore.oiv` (5,555,016 B), 1,222 `<add>` actions over 612 payload files.**
  The two tables are byte-identical, so the 610 gxt2 are stored **once** and referenced from both
  archive blocks (half the package size). The restore carries the **vanilla** fonts
  (240,056 / 96,789), so the revert is a true revert.
- **✅✅ INSTALLED AND VERIFIED IN THE LIVE GAME ARCHIVES (2026-08-02).** After the syntax fix the
  log shows real `Replace file in archive` actions, and both `mods\update\*.rpf` flipped
  **NG → OPEN** and grew (3,122,239,488 → 3,151,890,944 · 656,189,440 → 662,006,272).
  Read back with `tools/rpf_lazy.py` **out of the live game folder**:
  `update2.rpf` → `american_rel.rpf` = **610 gxt2**, `global.gxt2` **74,140 entries / 64,935
  Hebrew**; `update.rpf` = the same table **plus** `font_lib_efigs_pc.gfx` **299,971 B** and
  `font_lib_efigs.gfx` **125,965 B**, both carrying the Hebrew glyphs. Deploy is DONE; only the
  in-game screenshot is outstanding.
  🔑 **A plain copy into `mods\` stays NG — OpenIV rewrites an archive as OPEN only when it
  actually WRITES into it.** So "the mods archive is still NG" is itself a reliable signal that an
  install matched zero actions.
- **🔴 `FATAL: Init1 failed` from "openCamera for GTA V" was NOT the mod — LEGACY prerequisites got
  installed into an ENHANCED game.** ZEnhanced/OpenIV's ASI-Manager step dropped
  `dinput8.dll` (131,072) + `OpenIV.asi` (135,168) + `openCameraV.asi` (126,976) into the game root
  — a byte-size match for ZEnhanced's `data\legacy\` folder. `openCameraV.asi` is a Legacy plugin
  loaded by the Legacy `dinput8.dll` proxy and dies on Enhanced. Fix = remove all three and keep
  **only** the Enhanced pair `xinput1_4.dll` + `OpenRPF.asi` (moved to
  `Tools\ZEnhanced\_removed_from_enhanced\`, reversible). **UNIVERSAL: when a tool ships per-edition
  prerequisite sets, verify by FILE SIZE which set actually landed — a crash naming a plugin you
  never chose means the wrong edition's bundle was installed, and it says nothing about your mod.**
- **✅✅ CONFIRMED IN-GAME BY THE USER ("עובד", 2026-08-02).** Screenshots show the legal/privacy
  page, the pause-menu tabs (מפה · בקצרה · סטטיסטיקה · הגדרות · משחק · אונליין), the whole
  controller-settings screen and the big Pricedown-style **יציאה** title all rendering as clean
  right-to-left Hebrew with zero tofu — so the text layer, the font injection into **every** face
  (including the title face) and the VISUAL storage order are all proven on Enhanced.
- **🔴🔴 THE PREDICTED `visual_line` PUNCTUATION DEFECT FIRED — and it is in LEGACY too.** The user
  reported wrong parentheses and guessed it also exists in the older game; CLAUDE.md had already
  written that prediction when RDR2 hit it ("GTA V ships the SAME `visual_line` → it very likely
  carries this identical mid-sentence punctuation defect; audit `games/gtav` before its next
  release"). Confirmed by running both transforms over the corpus:
  `תצפית (דרום)` → old `)םורד (תיפצת` vs UBA `(םורד) תיפצת`;
  `Kuruma (משוריין)` → old `)ןיירושמKuruma (` (parens flipped **and** the space lost) vs UBA
  `(ןיירושמ) Kuruma`.
  **Measured impact: the two disagree on 68,422 of 141,001 strings (48.5 %)** — any string with
  mid-sentence punctuation, because a hand-rolled reversal treats a NEUTRAL run as a forward Latin
  island instead of reversing it and mirroring its brackets (UBA rule L4).
- **🔑 THE TOKEN-ORDER HALF IS THE MORE DANGEROUS ONE, and it only surfaced by CLASSIFYING the
  diffs instead of counting them.** Of the 5,951 strings whose token sequence changes, 4,233 are a
  plain reversal (correct for RTL) and **1,718 are adjacent token PAIRS the old code wrongly
  flipped** — `~INPUT_VEH_MELEE_LEFT~/~INPUT_VEH_MELEE_RIGHT~` shipped as RIGHT-then-LEFT, i.e. a
  control hint that **silently swapped left and right**, and `~a~~s~` shipped as `~s~~a~`, moving a
  colour reset in front of the value it was meant to follow. Same family as the documented
  multi-word-Latin bug (`'Welcome to Los Santos'` → `'Santos Los to Welcome'`).
  **UNIVERSAL: when replacing a transform that already "works", don't stop at "N strings differ" —
  bucket the diffs by KIND (punctuation vs token order vs reversal) and read a sample of each. The
  scary-looking 48.5 % was benign punctuation; the quiet 1.2 % was a left/right swap in gameplay
  instructions.**
- **✅ FIX SHIPPED — `tools/gtav_rtl.py`** (the real UBA, modelled on `games/rdr2/work/rdr2_rtl.py`):
  `python-bidi get_display(base_dir="R")` with every `~…~`/`<tag>`/printf token stashed as an atomic
  private-use char, `~n~`/newline treated as ORDER-BEARING separators so line order is never
  flipped, per-segment edge-strip (a logical-trailing space lands in the visual LEFT margin as a
  stray indent), and a no-Hebrew passthrough. Selftest 9/9. `work/build_hebrew.py` now calls it
  instead of `gxt2.visual_line`. Rebuilt: same coverage (331,358), and the built tables now hold
  **3,464 correctly-ordered parentheticals** (the 3 flagged are multi-paren Latin credits lines, a
  limitation of the check, not defects).
- **⚠️ `games/gtav` (LEGACY) STILL SHIPS THE BROKEN `visual_line`** — same left/right swap, same
  flipped parentheses. Port `gtav_rtl.py` there and rebake before its next release.
- **The still-English lines are NOT a defect** — `Move Tab`, `Resume Story`, `Play Grand Theft Auto
  V's Story Mode.` and Enhanced's re-worded quit dialog are simply absent from the corpus (we have
  *"…and return to desktop?"*, Enhanced uses *"…Any unsaved progress will be lost."*). They are part
  of the measured 4,959 Enhanced-only strings and render as ordinary English.
- **NEXT:** re-install the rebuilt `release/gtav_enhanced_hebrew.oiv` and re-check the parentheses
  in-game. Publish only on an explicit "פרסם".


## Menyoo (GTA V trainer MOD) Hebrew — DEPLOYED locally, 301 strings (2026-06-23)

Not a game — the **Menyoo v2.3.0** trainer MOD's own menu, in `F:\Games\Grand Theft Auto V Legacy`.
Distinct from the GTA V game-text project above (that one = GXT2 in RPF7). Memory [[gta-menyoo-hebrew]].

- **Text = a built-in language system, NO binary patching.** `menyooStuff/Language/<Lang>.json` =
  `{english_string: hebrew}` (keys are the EXACT English UI strings, verbatim), activated by
  `menyooConfig.ini [settings] language = Hebrew`. A key that's absent simply renders English →
  **partial translation degrades gracefully**. `menyooLog.txt` confirms `Loaded language file ...`.
- **🔑 THE SCOPE-DISCOVERY TRICK (UNIVERSAL, reusable for any mod/game with a lookup-based loc):**
  Menyoo logs **`ERROR - Missing translation for: <string>`** for EVERY string it looked up and did
  not find. So: ship a PARTIAL language file → play through the menus once → **harvest the log** =
  the authoritative, complete key universe, straight from the engine. Far better than guessing from
  a community translation (the shipped `French.json` covered only 234 of ~520 real strings).
- **🔑 SEPARATING UI LABELS FROM PROPER NOUNS — the plural/singular heuristic.** The harvested list is
  dominated by vehicle names that must STAY English. Clean separator found: **menu CATEGORY labels are
  PLURAL, vehicle-name modifiers are SINGULAR** — `Compacts`/`Planes`/`Boats`/`Coupes` (categories,
  translate) vs `Blista Compact`/`Cargo Plane`/`Cheetah Classic` (vehicles, keep). Dropping the
  singular forms from the keyword filter took the false-positive rate to ~0 (92→80 candidates, all
  genuine UI). Result: 80 UI strings vs 205 names/codes (`keep_english_names.json`).
- **Font — GTA V native text is SCALEFORM-backed (see §8c below for the full map).** Menyoo draws with
  native `SET_TEXT_FONT`+`_DRAW_TEXT`; glyphs come from `font_lib_efigs_pc.gfx`. Hebrew injected into
  `$Font2`/`$Font2_cond` via FFDec, shipped as an `.oiv` → `mods/update/update.rpf/x64/data/cdimages/
  scaleform_platform_pc.rpf/`. **bidi: NONE → store VISUAL** (Scaleform has no RTL engine).
- **🔴🔴 THE BUG THAT MADE IT ALL TOFU — font-ID vs injected-export mismatch.** Hebrew was injected into
  `$Font2` (native font **0**) and `$Font2_cond` (font **4**), but `menyooConfig [fonts]` selected
  **title=7 (Pricedown), options/selection=4, breaks=1 (HouseScript)** — 7 and 1 are SEPARATE exports
  that got NO Hebrew → the menu title and section breaks rendered boxes. **FIX: collapse every menu
  font slot to 0** (`title/options/selection/breaks/font_xyzh = 0`) so only ONE face needs Hebrew.
  **UNIVERSAL: after injecting glyphs into a font, verify which font ID / face the target text ACTUALLY
  uses — injecting into the wrong export is invisible offline and looks exactly like "the font failed".**
- **Pipeline (final):** translating agent produces **LOGICAL** Hebrew (`Hebrew_logical.json`, per
  [[delegate-all-translation]]) → Claude applies `visual()` from repo `translate_menyoo.py` → writes
  `Hebrew.json`. Keeping the logical file as the source of truth means the visual bake is re-runnable
  and the translation is never corrupted by a reversal bug.
- **State:** **301 strings deployed** (234 base + 67 UI harvested from the log). Deliberately English:
  205 vehicle/ped names + codes, and **13 `N. Unlock '<Mission>'` achievement lines** (multi-word Latin
  title — see the visual() limitation in §8b #10). `[fonts]`→0 applied. Backups `*.bak.<ts>` for
  `Hebrew.json` / `Hebrew_logical.json` / `menyooConfig.ini`. **Pending: the user's in-game check**
  (F8); if still tofu, try `[fonts]`=4 (font 4 also got Hebrew).
- **⚠️ VERIFICATION LESSONS (cost real time this session):**
  1. **A prior agent's written report claimed "installed successfully / verified"** while the
    render-breaking `[fonts]` gap was untouched. Only reading the ACTUAL files exposed it — never
    accept a hand-off report as verification.
  2. **`strings` does NOT exist in this Git-Bash.** `strings file | grep X` therefore returned EMPTY
    and I nearly concluded "the .gfx contains no font data" — a completely wrong verdict from a
    silently-failing pipeline. **Confirm a binary exists before trusting an empty grep**; extract
    binary strings with Python (`re.findall(rb'[\x20-\x7e]{4,}', data)`) instead.
  3. **How to validate a font injection OFFLINE** (no game launch): (a) size vs the vanilla backup
    (97 KB → 711 KB = glyphs really added), (b) the original **export names must still be present**
    (`$Font2`, `$Font2_cond` — renaming to "Arial" breaks Scaleform's name linkage → fallback/tofu),
    (c) count **LE-u16 codepoints in the target Unicode block** (2,071 hits in 0x0590–05FF = Hebrew
    is mapped in the code tables).


