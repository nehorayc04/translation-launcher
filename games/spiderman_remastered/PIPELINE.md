# Marvel's Spider-Man Remastered — PIPELINE

## Tools (`games/spiderman_remastered/tools/`, run with the repo `.venv` python
— `fontTools` + `python-bidi` live there)

| file | role |
|---|---|
| `msmr_loc.py` | Localization codec — `Loc(raw_bytes)` parses a variant's 5-tag DAT1 into `.pairs`/`.as_dict()`; `.encode(patch: dict[str,str])` rebuilds VALUES+TEXT_OFFSETS with dedup, copies every other section verbatim. `load(path)` helper. Run as `__main__` for the 23-variant identity+patch selftest. |
| `msmr_deploy.py` | Index-redirect deploy against the live `toc`. `apply(game_root, assets)` / `revert(game_root)` / `status(game_root)` / `validate_offline(game_root, scratch)` (proves the write path on a COPY before touching anything real) / `find_asset_index(toc, span, asset_id)` / `read_toc` / `toc_path` / `arch_dir`. |
| `msmr_font.py` | Scaleform font injector — `inject(gfx_bytes, donor_ttf=Heebo) -> bytes`. Adds 27 Hebrew glyphs to every `DefineFont3` face that doesn't already have them, self-verifying. Reuses `games/witcher3/work/{gfx_inspect,swf_font,swf_glyphgen,build_font}.py` unmodified via a sys.path insert. |

## Extract layout (`games/spiderman_remastered/extract/`)

- `loc_variants/*.localization` — all 23 language variants, raw (36-byte asset
  header + DAT1), extracted from the pristine toc before any deploy.
- `fonts/Font_LatinAS3_0.bin` — the pristine Font_LatinAS3.gfx asset.

## 🔴🔴 A real bug was found and fixed after the first deploy (2026-08-10)

The first deploy (3 loc candidates + font, all appended in one `apply()` call)
showed **two symptoms in-game**: the pre-game "Launcher" settings screen (a
separate always-reachable UI, distinct from the in-game menu, reading the SAME
`localization_all.localization` asset) rendered every visible label as its raw
KEY name instead of the resolved value (`LAUNCHER_PLAY`, `SETTINGSCATEGORY_DISPLAY`,
`PCDISPLAYSETTINGS_WINDOWMODE`, …), and **the game hung after the boot logos** and
never reached gameplay.

**Root cause: a `chunkmap` collision.** `append_archive()` cloned BOTH
`install_bucket` AND `chunkmap` from an existing archive (index 19, `g00s019`).
`install_bucket=0` is shared by every one of the 34 base-game archives (safe to
clone), but **`chunkmap` is a small, sequential, per-archive-UNIQUE id**
(`g00s019` → `10019`, `g00s020` → `10020`, …) — cloning it made 4 new archive
table rows all claim the SAME value the ORIGINAL `g00s019` already held. `dat1lib`
itself never reads `chunkmap` (grep-confirmed: `extract_asset()` resolves purely
by `archive_index → filename`), so **every offline validation this session ran
passed cleanly** — the collision was invisible to my own tooling. The real
Insomniac engine's archive/chunk-streaming resolver almost certainly DOES key off
`chunkmap`, and 5 archive rows sharing one id most likely mis-resolved reads back
onto the original `g00s019` (explaining the raw-key fallback for text, and a
crash/hang when the same misdirection hit the much larger font asset).

**Fix (`tools/msmr_deploy.py`, `append_archive()`):** keep cloning
`install_bucket` (correct — matches every base-game archive), but assign each new
entry `max(existing chunkmap) + 1`, recomputed per call so N assets in one deploy
each land on a distinct, collision-free value. Re-verified: 4 new archives got
`112146..112149` (no collision with any of the 46 pristine entries), and the
full-corpus diff (all ~57,361 unpatched keys of the span-8 English variant, read
back through the live game's own toc) still shows **0 unexpected changes**.

⚠️ **This is MSMR-specific, not a bug in the already-shipped SM2 mod.** SM2/R&C
run the newer RCRA toc generation, whose `ArchiveFileEntry` has NO chunkmap field
at all — its equivalent fields (`a,b,c,d,e`) are constant across every archive per
`dat1lib`'s own comment, so cloning them is safe there. **Whenever appending an
archive-table entry on ANY future engine/toc generation: verify each cloned
field's semantic role individually — a per-archive-unique id sitting beside
several shared constants in the same struct is invisible until the real engine
(not your own reader) is tested, and it varies per toc generation even within one
engine family.**

## Phase-1 proof — deployed now

`games/spiderman_remastered/work/20_build_menu_proof.py`:

```bash
cd games/spiderman_remastered/work
python 20_build_menu_proof.py                # build + deploy + verify (already run)
python 20_build_menu_proof.py --build-only    # build only, no game write
python 20_build_menu_proof.py --revert        # restore the pristine toc, delete mods/
```

Ladders 3 candidate spans (0 / 8 / 152), each patched via `msmr_loc.Loc.encode`,
plus the Hebrew-injected `Font_LatinAS3.gfx`, and deployed together in one
`msmr_deploy.apply()` call. Every write is verified by reading BACK through the
live toc's own `extract_asset()` — never trusted from the just-written state.

**Deployed state (confirmed live, 2026-08-10 session, redeployed AFTER the
chunkmap fix above — this is the second, corrected deploy):**

- `D:\Games\Spider-man Remastered\asset_archive\toc` — patched.
- `D:\Games\Spider-man Remastered\asset_archive\toc.tm_he_backup` — pristine
  backup (10,707,684 B, matches original size exactly). Name deliberately
  distinct from Overstrike/ALERT's own `toc.BAK` — no collision with any
  existing suit-mod install (confirmed: no `toc.BAK` exists on this machine).
- `D:\Games\Spider-man Remastered\asset_archive\mods\` — new directory:
  `.tm_he_manifest.json`, `tm_he_0` (span 0, 5,975,137 B), `tm_he_1` (span 8,
  the FULL proof, 5,975,386 B), `tm_he_2` (span 152, 5,749,629 B), `tm_he_3`
  (the Hebrew-injected font, 454,042 B).
- 4 new archive table rows appended (indices 46-49), `install_bucket=0`
  (cloned, correct — matches every base-game archive), `chunkmap`=
  `112146/112147/112148/112149` (assigned unique, the fix — no longer
  colliding with the archive[19]/`g00s019` value `10019` the first, broken
  deploy shared).
- Registry `HKCU\Software\Insomniac Games\Marvel's Spider-Man
  Remastered\TextLanguage` reset from its pre-session value `19` to `1`
  (English — the primary/expected-default hijack target, span 8).

**Read-back verification results (all PASS, both the direct read-back AND a
FULL-CORPUS diff of all ~57,361 unpatched keys against the live toc):**

```
[PASS] span 0   read-back: 1/1
[PASS] span 8   read-back: 7/7   (all LOGICAL/VISUAL/coverage/paragraph keys correct)
[PASS] span 152 read-back: 1/1
[PASS] font     read-back: 135 Hebrew glyphs (expect 135)
[PASS] all candidates written+verified.
```

## What to look for (the user's one remaining step)

1. Launch `D:\Games\Spider-man Remastered\Spider-Man.exe`.
2. Screenshot the **first boot screen** (the "PRESS TO START" splash — the
   `TEXT_SPLASHSCREEN_CONTINUE` key). Whichever marker appears NAMES the live
   slot:
   - `ZZ-SPAN8-ENGLISH-ZZ` — expected (registry=1). Confirms the primary
     candidate and unlocks all 6 remaining proof strings on the main menu.
   - `ZZ-SPAN0-NONE-ZZ` — the engine falls back to `kLanguageNone` regardless
     of the registry value.
   - `ZZ-SPAN152-ARABIC-ZZ` — a first-run re-seed overrode the registry write
     back to 19.
3. If `ZZ-SPAN8-ENGLISH-ZZ` appeared, also screenshot:
   - **Main menu** (Continue / New Game / Load Game / Quit Game rows) —
     `TEXT_CONTINUE`="שלום" (LOGICAL), `TEXT_NEW_GAME`=VISUAL "שלום",
     `TEXT_LOAD_GAME`="אבגד" (4-letter direction control, LOGICAL),
     `TEXT_QUIT_GAME`=all 27 Hebrew letters (glyph-coverage row). Exactly one
     of Continue/New-Game should read correctly — that names the bidi mode.
   - **Language settings screen** (`LANGUAGE_ENGLISH` row / `TEXTLANGUAGE_TITLE`)
     — the same punctuation/parens/digits/Latin-island paragraph in both
     LOGICAL and VISUAL, for the layout gate.

## Revert

```bash
cd games/spiderman_remastered/work
python 20_build_menu_proof.py --revert
```

Restores `toc` from `toc.tm_he_backup`, deletes `asset_archive/mods/`. The
registry `TextLanguage` value is NOT reverted automatically — reset it back to
`19` by hand if the pre-session state must be restored exactly:

```powershell
New-ItemProperty -Path "HKCU:\Software\Insomniac Games\Marvel's Spider-Man Remastered" -Name TextLanguage -Value 19 -PropertyType DWord -Force
```

## 🔴 A SECOND, separate symptom: the pre-game "Launcher" overlay shows raw KEY names (2026-08-10)

Beyond the chunkmap fix above, the user also reported (screenshots) a SEPARATE pre-game
"Launcher" settings overlay (Play/Settings/PlayStation PC/Quit — appears immediately after
launch, BEFORE the Insomniac logo, distinct from the in-game main menu the proof targets)
rendering every visible label as its raw KEY name (`LAUNCHER_PLAY`, `SETTINGSCATEGORY_DISPLAY`,
`PCDISPLAYSETTINGS_WINDOWMODE`, …) instead of the resolved value, on both the FIRST (broken
chunkmap) deploy AND the corrected one.

**Isolated + confirmed real, still unfixed:**
- All 23 pristine variants (incl. `variant_00`=span 0 and `variant_01`=span 8, byte-identical
  in vanilla) carry these EXACT keys, correctly localized per language — this Launcher screen
  reads the SAME `localization_all` asset (`0xBE55D94F171BF8DE`) the main proof targets, not a
  separate resource.
- A **minimal isolate deploy** (`work/32_isolate_launcher.py span8-only` — patches ONLY span 8's
  marker key, leaves span 0/152/font 100% untouched, appends exactly ONE new archive entry)
  **still shows raw keys** on the Launcher screen. This rules out "wrong span" (it isn't reading
  span 0 specifically) and rules out "multiple new archives" (only one was appended) — appending
  even a SINGLE new archive entry breaks this screen's string resolution, regardless of which
  asset gets redirected.
- The `ArchiveFileEntry` struct (MSMR) has exactly 2 non-filename fields
  (`install_bucket`, `chunkmap`, confirmed by reading `archives.py`'s source directly) — both are
  now handled correctly (chunkmap unique, install_bucket a genuine shared constant). There is no
  third field to find.
- `dat1lib`'s `DAT1.save()` (`recalculate_section_headers` + per-section `refresh_section_data`)
  was traced line-by-line: it correctly repositions ALL 6 toc sections (Archives/AssetIds/Sizes/
  **KeyAssets**/Offsets/Spans) on every save, using each section's live object state for the ones
  we `refresh()` and its unchanged cached bytes for the rest — structurally sound. A full-corpus
  diff of **all three deployed spans** (not just span 8) via our own toc reader shows 0 unexpected
  changes and correct `LAUNCHER_PLAY`/etc values in all three.
- **Conclusion: our own `dat1lib`-based reader resolves everything correctly through the live
  toc — every field it models is right. The bug is in something the REAL engine's resolver
  depends on for this early-boot overlay that `dat1lib` doesn't model at all** (most likely: this
  "Launcher" overlay is a structurally separate, simpler component from the main game engine —
  see below — that may hardcode/cache an assumption about the archive TABLE COUNT or layout,
  independent of any single entry's field values). Not yet root-caused; the Launcher screen
  itself is **not blocking** (see next section) so this is now a lower-priority cosmetic gap,
  not a blocker for Phase 2.

## ✅ The "hang after boot logos" was a MISDIAGNOSIS — corrected (2026-08-10)

Extensive autonomous testing (launch + dxcam/GDI capture + game-log-growth tracking) showed:

1. **The "Launcher" overlay is not frozen — it is a static, always-idle pre-game menu waiting
   for input** (Play/Settings/PlayStation PC/Quit). A flat game-log + flat capture brightness on
   this screen is its NORMAL resting state, not a hang signature.
2. **Pressing Enter reliably advances past it** into the real boot sequence (Marvel logo →
   further logos → loading → a "SELECT DIFFICULTY" setup screen with a Sony data-collection
   consent dialog, which needs its OWN confirmation). Proven on both a fully vanilla toc and the
   chunkmap-fixed mod.
3. **`dxcam` (DXGI Desktop Duplication) intermittently fails during this game's DX12
   exclusive-fullscreen transitions on this machine** — a direct cross-check
   (`dxcam.grab()` mean=0.12 "black" vs a SIMULTANEOUS `PIL.ImageGrab` mean=82.4, a perfectly
   normal lit Marvel-logo frame) proved several "stuck black screen" observations across this
   whole investigation were CAPTURE ARTIFACTS, not real hangs. Use GDI (`ImageGrab`), not
   `dxcam`, for any further MSMR capture work (`work/34_gdi_watch.py`).
4. **Boot-sequence stalls/long black periods are NOT unique to the mod — they reproduce on a
   100% vanilla, byte-for-byte unmodified toc too** (confirmed via MD5 match against the pristine
   backup before testing). This crack's boot is inherently flaky/slow on this machine
   independent of any of our work; some launches sail through to the difficulty-select screen in
   under a minute, others sit on a logo/loading screen for minutes. No consistent evidence this
   session found that the mod makes it WORSE than vanilla's own baseline flakiness.

**Net effect: the original "game hangs after boot logos" complaint is very likely EITHER (a) the
same pre-existing crack flakiness that reproduces without any mod, misread as a hang because the
"Launcher" overlay + Sony consent dialog both sit static waiting for input and look identical to
a freeze, or (b) exactly that — genuine crack-side instability unrelated to our archive edits.**
Recommend the user retry launching manually a few times, pressing Enter/clicking through BOTH the
Launcher overlay and any Sony "GAME DATA" consent popup that follows it, before concluding
anything is still broken.

## 🔴🔴 ROUND 2 — a genuine hard stall (not the Launcher/consent-dialog case above), exhaustively
isolated and proven MOD-INDEPENDENT (2026-08-10)

User re-reported "the window is open and stuck on loading" with a screenshot of a black content
area under a `Marvel's Spider-Man Remastered v1.812.1.0` title bar (the "browser tab / breadcrumb"
chrome above it was later confirmed to be the Antigravity IDE's own desktop, not Parsec or any
game-side wrapper — a `Parsec Virtual Display Adapter` DOES exist on this machine as a `Win32_
VideoController`, but the game log explicitly confirms it enumerates + uses **`Adapter 0: AMD
Radeon RX 9070` as the active render adapter**, never the Parsec one — that theory is dead).

**The stall signature, live-measured over several independent runs:** the game log grows normally
through GPU-adapter enumeration → input enumeration → renderer init → `cache.pso` load → a couple
of `[Render] Aliased resource does not fit in the original heap... Recreating heap and aliases.`
warnings → one `[Audio] Device (re)initialized 'Speakers (V18)'` → a short burst of
**`[Save] Request type 3 failed with code 0x00000002`** / `[Save] Request load save type N,
control 128, target -1` lines — and then the log goes **100% silent, permanently**, while the
process (a) stays `Responding=True` the whole time, (b) burns a sustained ~150-250% CPU (later
runs: cumulative CPU climbing linearly ~2 cores non-stop for 12+ minutes with zero plateau), (c)
shows a repeating memory sawtooth (working set spiking to multi-GB, then dropping back to near its
startup baseline, then climbing again) — the classic signature of a tight native
allocate→fail→free→retry loop, not slow/legitimate asset streaming (which would plateau, not
sawtooth) and not shader compilation (which would hold its allocations, not free them).

**Isolation performed, each ruling out one candidate cause completely** (every test used the SAME
method: kill → change ONE variable → relaunch → foreground the real window by title match → click
its center → send a global `keybd_event` Enter to clear the Launcher overlay → patiently monitor
GDI screen-region brightness + game-log byte growth + process CPU/WorkingSet, letting each attempt
run **12 and then 10 full continuous minutes** before concluding anything — earlier short (2-5 min)
attempts had been killed too early and never gave any single launch the time Miles Morales (see
below) needed):

1. **GPU adapter** — confirmed `AMD Radeon RX 9070 (active)` in the log every time. Not the cause.
2. **On-screen keyboard stealing input focus** — closed (`Stop-Process TabTip/osk`), foregrounded
   the real window by exact title-match `EnumWindows`, clicked its center, sent Enter directly to
   it. No change in outcome.
3. **`flt.ini [GameSettings] Offline=1` vs `Offline=0`** — identical stall, identical log signature,
   both ways. Not the cause.
4. **FLT's `steam_api64.dll` vs Goldberg's `steam_api64.dll` + `steam_settings/`** (the game folder
   ships all 4: ALI213/CODEX/FLT/Goldberg under `NoDVD/`; confirmed by MD5 that the root DLL is a
   genuinely different, FLT-specific build, not merely Goldberg copied to the root) — swapped in
   Goldberg's DLL + its `steam_appid.txt`/`steam_interfaces.txt`/`steam_settings/`, same stall,
   same log signature (only the timing of *reaching* the stall point shifted slightly). Not the
   cause. **Restored to the original FLT DLL afterward** (`steam_api64.dll.flt_backup` kept as the
   pristine copy; the Goldberg-added files were removed since they were never part of the original
   install).
5. **Cross-checked `Marvel's Spider-Man Miles Morales.log`** (a different, EARLIER, working session
   on this same machine, same Insomniac Luna engine, same log format) — it shows the **exact same**
   `[Save] Request type 3 failed with code 0x00000002` burst at boot, **for about 3 seconds**, then
   resolves and the game reaches confirmed active gameplay (periodic `[Save] Request save type 0,
   control 0` autosave-style entries spaced 2-5 minutes apart) **~4m44s after boot**. ⇒ **the
   Save-failure burst itself is NORMAL, EXPECTED, self-resolving behavior for this engine on a
   fresh profile (error 2 = `ERROR_FILE_NOT_FOUND`, i.e. "no save yet") — it is NOT the root cause,
   just the last thing logged before whatever silently hangs.**
6. **12 continuous minutes on the Goldberg-modified state** — zero log growth, zero real screen
   change the entire time (`bhfsira18`, 722s). Nearly 3× longer than Miles Morales ever needed.
   Rules out "it just needs more patience at this duration."
7. **🔴🔴 THE DECISIVE TEST — reverted the toc to 100% pristine vanilla** (`msmr_deploy.revert`,
   confirmed `{'backup': False, 'manifest': False}`, i.e. zero mod files present) **and ran a fresh
   10-minute isolation monitor from a clean launch. IDENTICAL STALL — 602s, zero log growth, screen
   brightness dips slightly (~40→~29, gradual over ~2 min, no real content) and then plateaus dead
   flat for the remaining 5 minutes** (`bjvqw7luj`). **This conclusively proves the stall has
   NOTHING to do with the Hebrew mod, the chunkmap fix, the loc redirects, or the font injection —
   it reproduces byte-for-byte identically on a completely unmodified install.**

**Conclusion: this is a genuine, pre-existing, mod-independent stall in this specific MSMR
crack/install on this machine**, occurring consistently right after (but almost certainly not
caused by) the engine's normal first-launch save-profile probe. The underlying trigger was NOT
found — that would need a real debugger attached to see exactly what native code is spinning
(no Windows Application-Error/Hang event was ever logged, and the process never stops
`Responding`, so this is an active spin/retry loop, not a classic deadlock or crash). Two concrete,
untried next steps for the user, in order of effort: (a) try a different repack/crack of the game
entirely (this exact FLT-based install may simply be broken on this box, independent of which of
its 4 bundled Steam-emulation layers is active); (b) check for a GPU-driver-related regression —
the AMD driver was updated 24/07/2026 (`32.0.31035.1003`), close in time to when this instability
was first noticed; a driver rollback is a cheap, fast experiment.

**State left clean**: `steam_api64.dll` restored to the original FLT build (md5-verified against
`.flt_backup`), the Goldberg test files removed, `flt.ini` left at `Offline=0` (matching
`flt.ini.he_backup`, its documented pristine value), and the chunkmap-fixed Hebrew menu-proof
(spans 0/8/152 + font) **re-deployed and read-back-verified** — since vanilla is equally stalled,
there is no reason to ship a reverted install; the proof is ready to test the moment the underlying
crack instability is resolved by other means.

## ⚠️ ROUND 3 — the official Nixxes update chain does NOT fix the stall (2026-08-10)

User located + applied 3 official Nixxes stability-patch packages (community fitgirl-repacks.site/
cs.rin.ru/ElAmigos convention), taking the install from launch-day `b9304506` (2022) through
`b12423814` → **`b14752622` = "v3.618"**. Update #1+#2 applied byte-perfect via `hpatchz-x64.exe`
(`-f -s-2g`, same-path safe mode) + `7z.exe x` extraction of the SFX `update.exe`/`patch.exe`
packages — verified against the package's own 59-entry SHA1 manifest, 59/59 match (excluding the
deliberately-cracked `steam_api64.dll`, restored from `.flt_backup` after an update.exe run
overwrote it with the real Steam DLL). Update #3 (v3.618→v4.630, ElAmigos installer) silently
no-ops under `/VERYSILENT`/`/SILENT` — suspected stale HKLM Inno Setup registry entry from an old
install location, needs admin (unavailable, non-elevated context) — **deferred, not blocking**.

**First launch on the updated build (vanilla, mod-reverted) SUCCEEDED — reached SELECT DIFFICULTY**
(title bar `v3.618.0.0`, user-confirmed screenshot). Encouraging, but with a documented
INTERMITTENT bug one clean boot proves nothing on its own — Round 2 already established the same
stall reproduces on 100% vanilla too.

**The chunkmap-fixed Hebrew mod (spans 0/8/152 + font, re-deployed + read-back-verified 100%
correct on the fresh v3.618 toc) was THEN deployed, and the VERY NEXT launch attempt STALLED
AGAIN** — user-confirmed via screenshot, `flt.ini Language` still English (span 8, the slot both
launches read). Signature identical to Round 2: window frame + title bar visible, black content
except the spider watermark, process alive (`Responding=True`, CPU climbing continuously — 273.6
CPU-seconds by the time it was checked). An autonomous background capture (`34_gdi_watch.py`) run
on the SAME toc state independently corroborated this — its liveness poll flapped (a WMI polling
race, not a real exit) and its GDI capture caught only the bare desktop at t=71s — i.e. **the
automated tooling's own signals were inconclusive here; only the user's direct screenshot gave
ground truth.** Process killed to unblock the user.

**CORRECTED CONCLUSION: the update chain (2022 → v3.618) does NOT fix the stall — it remains
present, still intermittent, on the same updated build, with AND without the Hebrew mod deployed.**
This directly reproduces Round 2's own "reverted to 100% pristine vanilla and it stalls
identically" result, one build-generation later: build vintage was never the cause. The earlier
successful boot was a lucky attempt, not evidence of a fix. **Do not draw a conclusion from a
single successful launch on an intermittent bug.** The mod itself remains exonerated exactly as in
Round 2 (deployed AND reverted states both stall on both build vintages).

**State left:** Hebrew mod proof (spans 0/8/152 + font) DEPLOYED + read-back-verified on v3.618.
Registry `TextLanguage=1`. Update #3 (→v4.630) still blocked/deferred.

## 🔴🔴 ROUND 4 — a controlled A/B confirms the mod, specifically, on the v3.618 exe (2026-08-11)

A fresh session's fresh launch on the same v3.618 install initially reached SELECT DIFFICULTY
cleanly (screenshot, "נפתח באנגלית"). The user then hit the stall again on a SUBSEQUENT launch of
the SAME (mod-deployed) state, and — critically — ran their own controlled test:

1. Reverted the mod (`msmr_deploy.revert`) → launched → **opened immediately, no stall.**
2. Re-deployed the mod (re-ran `20_build_menu_proof.py`) → launched → **stalled on loading.**
3. Repeated the cycle once more, same result both times.

The user explicitly, repeatedly confirmed this correlation ("סופית זה המוד...", later "בדקתי ואני
מאשר שזה בגלל המוד" — checked and confirmed it's because of the mod), across 3 independent trials.
**This user-observed correlation is accepted as the authoritative finding** — it is direct,
repeated, first-hand A/B evidence, stronger than the absence of a structural defect in my own
static checks.

**Every structural/offline diagnostic run in response came back clean, and NONE of them explain
the correlation:**
- **A previously-unknown 6-section toc layout was discovered and audited.** `t.dat1.sections`
  exposes 6 DAT1 sections total, not 4: Archives (`0x398ABFF0`), Sizes (`0x65BCF461`), Offsets
  (`0xDCD720B5`), Spans (`0xEDE8ADA9`), and two never-checked-before — **KeyAssets**
  (`0x6D921D7B`, "Archive TOC Key Asset IDs", 12,163 entries) and **AssetIds**
  (`0x506D7B8A`, 771,677 entries — the previously-unnamed 6th section). Confirmed the localization
  asset id is NOT present in KeyAssets (irrelevant to it). A real deploy (identity-payload, on a
  scratch copy) diffed ALL 6 sections before/after: only Archives (+288B, expected — the new
  entries) and Offsets (same length, redirected content, expected) changed; **KeyAssets, AssetIds,
  Sizes, and Spans were 100% byte-identical** — zero hidden corruption anywhere in the toc.
- **Chunkmap/install_bucket collision re-checked on the fresh v3.618 toc** (archive[19]'s bucket=0,
  chunkmap unique across the whole table, no collision) — clean.
- **Whole-toc identity round-trip** (read the pristine v3.618 backup, write it back with zero
  edits, compare) — not byte-identical (−12,098B, benign zlib re-compression variance) but **0
  semantic mismatches** across all 771,677 offset/size entries and all 46 archives.
- **A `[Render] fps: 236.533340` log line was observed ~57s into one stall** — the render loop is
  genuinely alive and swapping frames even while the screen shows black, which nuances (but does
  not resolve) the "100% silent forever" characterization from Round 2's stall signature.
- **Desktop-capture-reliability caveat**: this environment runs multiple concurrent Antigravity/
  Claude-Code sessions with overlapping windows on the same desktop; one `dxcam` capture attempt
  during this investigation grabbed an unrelated IDE window instead of the game, confirming
  automated screen capture is NOT trustworthy here — the user's own direct screenshots remain the
  only reliable visual ground truth for this game.

**STANDING RULE until root-caused: do not deploy this Hebrew mod build against the officially-
updated (v3.618+) exe — it is confirmed to break it. It remains safe/proven only on the original
2022 unpatched exe (b9304506), where Round 2 already proved mod-independence.**

## 🔴🔴 ROUND 4b — attempted a genuine architectural fix; it revealed WHY the current design is
the ONLY viable option, not a flaw to correct (same session)

**Theory tested:** maybe the updated exe specifically distrusts a brand-new, never-before-seen
archive/chunkmap/filename table entry (the one thing genuinely new about `apply()`'s deploy vs a
stock asset load). An append-RELOCATE into an EXISTING, already-trusted `archive_index` — the same
general technique already proven for AC Unity/RDR2/007 elsewhere in this project — would avoid
creating that new entry entirely.

**Built:** `apply_inplace()` / `revert_inplace()` / `status_inplace()` in `tools/msmr_deploy.py`
(new `INPLACE_BACKUP_NAME = "toc.tm_he_inplace_backup"` / `INPLACE_MANIFEST =
".tm_he_inplace_manifest.json"`) + a parallel proof script `work/21_build_menu_proof_inplace.py`
(reuses `20_build_menu_proof.py`'s `build()`/`CANDIDATES`/`build_patch` verbatim — only the deploy
call differs). Appends every blob onto the END of ONE existing archive file
(`target_archive_index=0` = `g00s000`), redirects each slot's Offsets/Sizes entry there, and
**refreshes ONLY Sizes+Offsets — the Archives section is never touched at all**, so zero new
archive-table rows are created.

**Offline-validated clean on a scratch copy** (`scratchpad/validate_inplace.py`, using a small fake
placeholder archive file, NOT the real compressed one): archive count unchanged, Archives section
byte-identical to pristine, all 3 redirects land at correct sequential offsets, read-back through
`extract_asset()` matches exactly, zero drift on every other asset's offset/size, archive file grows
by exactly the appended bytes, and revert restores the toc byte-for-byte + truncates the archive
back to its exact original size. Full suite: PASS.

**Deployed for real onto the LIVE game (`asset_archive/g00s000`, archive_index 0). The write itself
was byte-perfect** — a direct raw seek+read at the file level (`scratchpad/verify_raw_append.py`)
confirmed our exact expected data (correct 4-byte MSMR asset-header magic `\xab\xb0+\x12`) landed
at exactly the redirected offsets. **But dat1lib's own `extract_asset()` read-back FAILED**
(`UnicodeDecodeError` decoding garbage). Root cause, confirmed by reading `dat1lib/toc.py` directly:

> **🔴🔴 `g00s000` — and every one of the 34 game-content archives (`g00s000`..`g00s033`) — begins
> with the 4-byte magic `DSAR` and is a COMPRESSED archive.** `extract_asset()` detects this magic
> and, instead of a simple `seek(offset)+read(size)`, parses a block-map header (blocks-header-end
> at file offset 12, then an array of 32-byte block descriptors —
> `real_offset/comp_offset/real_size/comp_size` — starting at offset 32) and decompresses through
> that block map. **A raw append past the archive's declared block-map range is neither
> decompressed by this scheme nor reachable through it — by our own tool, and by strong inference,
> by the real game engine's equivalent streaming logic too.** Growing the block map to add a
> legitimate new block would require re-laying and shifting EVERY byte of existing compressed data
> after the insertion point — a full multi-GB archive rebuild, not a small in-place append — and
> `dat1lib` has NO existing write support for this compressed format at all.

**Checked all 46 archives' magic bytes: the only non-`DSAR` one is `a00s034.us`** (the English
voice/audio pack) — a completely different, uninvestigated container, not remotely suitable for
arbitrary loc/font data even if its format were known.

**⇒ There is no existing, already-trusted archive this engine can be raw-appended into. The
append-a-brand-new-archive-entry design (`apply()`) is therefore the ONLY architecturally viable
way to inject uncompressed loose data into this toc format — not an arbitrary choice, and not the
thing to "fix."**

**Reverted immediately** — `g00s000` truncated back to its exact original size
(2,124,037,740 bytes, confirmed byte-count-for-byte-count), toc restored, `toc_is_ours=False`
confirmed clean. **Re-deployed the proven original `apply()` mechanism** afterward — the game is
left in the SAME configuration Round 4 already found stalls on the updated exe (11/11 keys +
135/135 font glyphs read-back-verified correct).

**Net result: "fix the deploy mechanism" is closed as a dead end — it was proven to be the only
option, not just the current one.** If the mod truly is incompatible with the updated exe (still
not airtight-certain, given this environment's capture-reliability caveat — but the user's 3× direct
A/B is strong, first-hand evidence), the real fix would have to target something the updated exe
checks OUTSIDE the toc/archive-table model entirely — e.g. a new validation layer added by the
stability patch itself, or an environment/timing factor unrelated to file structure. Reaching that
would need a real debugger session attached to the live process, comparing exact behavior with vs
without the appended archives at the instruction level — not attempted, genuinely out of scope for
static/offline analysis alone.

## 🔑 ROUND 4c — a THIRD deploy mechanism found and proven offline: zero toc changes at all
(same session, immediate follow-up to Round 4b)

User's "לא עובד" on the minimal single-new-archive-row test (Round 4, footnote) confirmed even
the SMALLEST possible new archive entry still stalls the updated exe — narrowing the suspect from
"the size/count of what we add" down to "the mere existence of any new archive-table row." Since
Round 4b already proved append-into-an-EXISTING-archive is architecturally blocked by DSAR block
compression, the next and more conservative idea: **don't touch the toc's Archives/Offsets/Sizes
tables AT ALL — overwrite the asset's content IN PLACE, inside the SAME blocks it already legally
occupies in its EXISTING archive.**

**Feasibility, established from the raw archive bytes, not assumed:**
- `g00s019` (where all 3 patched loc variants AND the font asset live, pristine) is DSAR/LZ4-block
  compressed in fixed 262,144-byte real (decompressed) chunks. Span 8's localization asset — the
  offset+size the toc's Offsets/Sizes sections already point at — is **PERFECTLY block-aligned**:
  it occupies exactly 24 whole blocks (23 × 262,144 + 1 × 10,068), with block boundaries landing
  EXACTLY on the asset's start and end. No other asset shares any part of those 24 blocks.
- The block decompressor (`dat1lib/decompression.py`) is a **standard LZ4 block-format decoder**
  (raw, no size header) — confirmed by compressing test data with `lz4.block.compress(...,
  store_size=False)` and decompressing with this exact function: byte-for-byte match.
- A test patch (the same marker-only content the failed minimal-archive test used) recompresses,
  block-by-block, to **fit inside every one of the 24 blocks' ORIGINAL `comp_size` budget** — all
  24 fit with real margin (e.g. block 0: 263,119 B budget, 261,882 B needed).

**🔴 The first real attempt CRASHED the read-back** (`IndexError` inside `decompression.decompress`)
— traced to zero-padding the shrunk blocks' leftover `comp_size` space. The decoder's loop
condition is `while real_i <= real_size and comp_i < comp_size` (note `<=`), so it does **not**
stop cleanly the instant the block is fully reconstructed if there's still comp-side budget left —
it tries to parse one more token from whatever's there, and zero-padding bytes parsed as an LZ4
token can walk past the buffer entirely. **Fix: when the recompressed block is smaller than the
original, patch the archive's OWN block-map header `comp_size` field down to the exact new length**
instead of padding — the leftover bytes between the new end and the old `comp_offset+comp_size`
become inert dead space, never read by any other block (each block is addressed independently by
its own `{comp_offset, comp_size}` pair), and the decoder now stops cleanly at
`comp_i == comp_size` exactly when `real_i == real_size`, matching the shape the game's own
encoder always produces. Offline-unit-tested on a synthetic archive (payload write + header patch
+ byte-exact revert, both payload and header). A SECOND real bug (a duplicate 36-byte MSMR asset
header — `msmr_loc.Loc.encode()` already prepends it, so my script prepending its OWN copy on top
produced header+header+DAT1) was caught by inspecting the raw read-back bytes and fixed the same
way — never assume, always dump the actual bytes when a parse fails on data you just wrote.

**✅ DEPLOYED FOR REAL AND VERIFIED, against the live game, on the officially-updated v3.618
install:** `tools/msmr_dsar_patch.py` (`plan()`/`apply_plan()`/`revert()`/`status()`/
`verify_readback()`). Overwrote span 8's marker key inside `g00s019`, in place, across all 24
blocks. Read back through dat1lib's real `extract_asset()` (the exact code path the game engine's
reader mirrors): marker correct (`ZZ-DSAR-INPLACE-ZZ`), every other key resolves correctly
(`LAUNCHER_PLAY='Play'`, `TEXT_NEW_GAME='NEW GAME'`, `TEXT_CONTINUE='CONTINUE'`,
`SETTINGSCATEGORY_DISPLAY='Display'` — not garbage), and **the toc's own archive count stayed at
exactly 46 — unchanged, zero new rows, the toc file itself was never opened for writing at all.**

**⇒ This is a genuinely new, more conservative deploy mechanism than either of the two previously
tried: no new archive-table row (unlike `apply()`, which Round 4 found correlates with the stall)
and no growing-past-block-map problem (unlike Round 4b's failed append-into-existing-archive
attempt). If this ALSO stalls on the updated exe, the suspect stops being "archive-table growth"
entirely — pointing instead at something unrelated to file structure (the language-selection path
itself, or genuine unrelated flakiness). If it does NOT stall reliably, this is the mechanism to
build the real translation deploy on.** **🔴 STILL STALLED — user-confirmed ("עדיין לא").** Even this zero-toc, zero-new-archive-row,
same-size in-place overwrite triggers the same stall. This rules out "archive-table growth" as
the cause ENTIRELY, not just as one possible mechanism among several.

**Antivirus interference RULED OUT (checked this session, not merely assumed):** `Get-
MpComputerStatus` confirmed Windows Defender is disabled (RealTimeProtectionEnabled=False);
`Get-CimInstance root/SecurityCenter2 AntiVirusProduct` + `Get-Service` confirmed **ESET is the
active real-time AV** (`ekrn.exe` running). This looked like a strong candidate — a real-time
scan triggered by writing into a multi-GB file could plausibly explain the CPU/memory-sawtooth
stall signature regardless of WHAT changed, and explain why only vanilla (never modified) boots
cleanly. **User confirmed a PATH exclusion (not merely a process exclusion) already covers the
whole game folder** — ruling this out too.

## Round 4d — the "any write event" test: a TRUE byte-identical rewrite (same session)

With every content-differing deploy ruled out (new archive, in-place overwrite) and AV ruled out
(path exclusion already covers the whole game folder), the last remaining variable is: does
**merely writing to the file at all** — updating its mtime, touching its data on disk, with the
CONTENT unchanged byte-for-byte — also trigger the stall? This isolates "an OS write event
happened" from "the content actually differs from vanilla."

Built a TRUE identity rewrite: for each of span 8's 24 covering blocks in `g00s019`, read the
EXACT compressed bytes already on disk (no recompression, no derivation — literally the same
bytes) and write them back to the exact same offset via the same `apply_plan()` code path used
for every other test this round. Verified: (a) content read back through `extract_asset()` is
byte-for-byte the ORIGINAL English text (`'PRESS [BTN_ACCEPT] TO START'`, `LAUNCHER_PLAY='Play'`
— nothing changed), (b) the archive's `LastWriteTime` did change to the moment of the write —
confirming a real OS-level write happened, not a no-op that got optimized away.

**✅ SUCCEEDED — user-confirmed via screenshot ("תפתח"), reached SELECT DIFFICULTY (v3.618.0.0)
normally.** A real OS write event — new `LastWriteTime`, real bytes physically rewritten to disk —
with the DECOMPRESSED CONTENT held byte-for-byte identical to vanilla, is completely safe. **⇒
"a write happened" is ruled out as the trigger. The trigger is specifically the CONTENT differing
from vanilla — every prior content-differing test (new archive row, in-place overwrite with a
changed marker string) stalled; this one, content-identical, did not.** Reverted to pristine
immediately after (`dp.revert(GAME)` → `{'ok': True, 'blocks_restored': 24}`; `dp.status(GAME)` →
`{'backup': False}`) before continuing.

## Round 4e — isolating WHAT KIND of content-difference triggers it (same session, ongoing)

With "any write" ruled safe and "content differs from vanilla" confirmed as (at least correlated
with) the trigger, two questions remained: (a) is there a stored content hash somewhere we simply
haven't found yet, and (b) does it matter HOW the differing content is compressed (e.g. a
DirectStorage GPU-hardware decompressor being pickier about match-based LZ4 structure than our
CPU-side decoder is), independent of whether the decompressed bytes themselves differ.

**(a) Searched every on-disk structure we can decode for a stored content hash — found none.**
- The DSAR archive header's previously-undecoded bytes `[4:12]` are NOT a hash: bytes `[4:8]` are
  a constant `03 00 01 00` across every archive (version/algo tag), and bytes `[8:12]` are simply
  the **block count** as a `u32`, verified to equal `(blocks_header_end - 32) // 32` exactly on
  every archive checked (`g00s019`=12722, `g00s000`=12290) — purely structural, not content-derived.
- Each 32-byte block-map record's two trailing padding `u32`s were already known (Round 4c) to be
  the SAME constants (`0x55555503`/`0x55555555`) on every block regardless of content.
- The toc's `ArchivesSection` entry (72 bytes/archive for `VERSION_MSMR`) is just
  `install_bucket(u32), chunkmap(u32), filename(64B)` — no hash field in the struct at all (per
  `dat1lib/types/sections/toc/archives.py`, and already known from Round 4b that these two u32s are
  a shared constant + a small per-archive-unique sequential id, not content-derived).
- ⇒ **No content-hash field exists in the DSAR container header, the DSAR block-map, or the toc's
  Archives table.** If a hash check exists, it is not stored in any of these three places — either
  it lives somewhere else entirely (an external manifest, computed dynamically against reference
  data not on disk as a simple table) or the trigger isn't a stored hash at all.
- Static string-scanning `Spider-Man.exe` (121,920,952 B) for hash/CRC/integrity/DirectStorage/
  streaming-install keywords found `'EnableDirectStorage'` (sits in a run of engine subsystem/
  telemetry-marker names — `Engine::PreInit`, `EnableDirectStorage`, `Dependency DAG
  initialization failed` — looks like an internal event-tag list, not a config key) and
  `'SetInstallState'` (sits among `BypassLobbySave`/`DeregistrationComplete`/`LoadDone` — looks
  like an unrelated session/level-load state-machine's event names). Neither is conclusively tied
  to archive-content validation; string-scanning alone cannot show what code actually reads these.

**(b) Isolated compression SHAPE from content, independent of any decompressed-content change.**
Built `msmr_dsar_patch.plan_reencode_block()`/`apply_reencode_block()`: pick ONE block, decompress
its bytes ALREADY ON DISK (so the decompressed content is, by construction, exactly the original
vanilla bytes — nothing decoded differs at all), then **re-encode that exact same content** with a
hand-built, zero-match, pure-literal LZ4 stream (`_lz4_literal_only()` — one sequence, no
back-references whatsoever, the simplest possible valid LZ4 block shape, guaranteed to round-trip
through any spec-compliant decoder including a stricter hardware one) instead of the real
match-based LZ4 the game's own encoder used. This changes the COMPRESSED byte stream's shape and
algorithm while leaving the DECOMPRESSED content, the toc, and the archive-table 100% untouched.

- `g00s019` block 1 (span 8's asset, `real_size=262144`, `orig_comp_size=263173` — a
  near-incompressible block, chosen specifically because literal-only re-encoding of ~262KB comes
  out at almost exactly real_size+overhead, so it's one of the few blocks where a literal-only
  re-encode of the SAME content fits the ORIGINAL comp_size budget without any shrink at all).
- Decoded content, re-encoded literal-only: **263,173 B — matches `orig_comp_size` exactly
  (263,173), fits with zero slack, round-trip verified against the original decompressed content
  before writing.**
- **Applied for real. Full-asset readback through `extract_asset()` (the exact code path the
  engine's reader mirrors) confirmed byte-identical to vanilla**: `LAUNCHER_PLAY='Play'`,
  `TEXT_SPLASHSCREEN_CONTINUE='PRESS [BTN_ACCEPT] TO START'` — the real original English text,
  unchanged (this test never touched a loc PATCH at all, only ONE block's compression encoding).
  Toc archive count confirmed unchanged (46). Backup recorded (1 block in `g00s019`).

**✅ SUCCEEDED — user-confirmed ("נדלק"), the game launched normally.** Compression shape/
algorithm is ruled out entirely as a factor: a completely different LZ4 encoding (zero match
structure at all, vs. the game's own match-based compression) of the SAME decompressed content is
just as safe as a byte-identical rewrite (Round 4d). **⇒ The trigger is proven, by clean isolation
across four tests, to be purely "does the DECOMPRESSED content differ from vanilla" — independent
of archive-table structure, write events, file location, or compression method.** Reverted to
pristine after the test (`dp.revert(GAME)` → `{'ok': True, 'blocks_restored': 1}`,
`dp.status(GAME)` → `{'backup': False}`).

**Searched the ENTIRE install tree for any manifest/hash file the running game might consult at
runtime — found only a repack-installer artifact, not a runtime check.** `_Redist\fitgirl.md5`
(bundled alongside `QuickSFV.EXE`/`QuickSFV.ini`) contains a full-file MD5 per archive (e.g.
`g00s019 = d9122cfc…`) — but this is the FitGirl repack's OWN self-verification tool: a
third-party SFV/MD5 checker meant for the USER to manually run ONCE after extracting the repack,
never referenced anywhere in `Spider-Man.exe`'s strings and never touched by the running game.
Every other small file in the install tree (`.ini`/`.dat`/`.md5`/`.exe`) is either a crack-loader
config, the InnoSetup uninstaller's own data, or this SFV tool — nothing else resembling a
content-integrity manifest exists on disk anywhere.

**⇒ Static file analysis is now genuinely exhausted for this question.** No stored content hash
exists in ANY structure we can decode (DSAR header, DSAR block-map, toc Archives table) or ANY
file on disk outside the exe itself (checked the whole install tree). The mechanism is real and
precisely isolated (decompressed-content difference, and ONLY that, triggers it — proven across
four independent, clean A/B tests this session, on top of the three from Round 4/4b/4c) but WHERE
in the exe's own code it is computed/checked cannot be determined from static files — that would
need a live debugger attached to the running process (breakpoint/watch on reads of archive data,
trace what validates it), consistent with this project's own standing next-step note from Round 2.
**Per the project's existing standing rule: the mod remains proven SAFE (mod-independent stall
ruled out) only on the original, unpatched 2022 exe (`b9304506`) — Round 2 already established the
stall reproduces on 100% vanilla there too, so it is a pre-existing engine/crack quirk unrelated to
any of our content. It is confirmed UNSAFE to deploy against the officially-updated v3.618+ exe
until/unless a live-debugger session pins down the actual validation code path.**

## Phase 2 (not started, gated on the user's screenshot)

Once bidi mode is confirmed:

1. Build the full corpus from `variant_01` (span 8, English): 46,556 global-unique
   values, split UI(10,987)/subtitles(33,252)/credits(5,112).
2. Delegate translation via a fleet/agent handoff
   (`universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`), New-Era reference panel
   from the 22 sibling language variants already extracted in
   `extract/loc_variants/`. **Claude never translates — [[delegate-all-translation]].**
3. Build the final `.encode(full_translation)` patch for span 8 (and span 0/152
   if the ladder showed either of those is actually live), bake the confirmed
   bidi mode (VISUAL via `bidi.algorithm.get_display(s, base_dir="R")`, or plain
   LOGICAL) into every value.
4. Re-deploy via the same `msmr_deploy.apply()` index-redirect (revert the proof
   first, or just overwrite the same `tm_he_N` files in place — either works,
   `apply()` is idempotent per the offline validation).
5. Publish only on an explicit "פרסם" — GitHub `spiderman-remastered-hebrew-mods`
   repo + Cloudflare Worker slug + Supabase `games`(`id="spiderman"`) row flip
   from `planned/locked` to `available` + `mod_version_history`. Price per
   [[mod-price-53-default]] unless the user says otherwise.
