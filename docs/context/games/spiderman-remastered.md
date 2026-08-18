## Marvel's Spider-Man Remastered Hebrew — mod build COMPLETE, but CONFIRMED INCOMPATIBLE with the officially-updated v3.618+ exe; safe only on the original 2022 build (2026-08-10/11, "דור 3")

New game at `games/spiderman_remastered/` (RECON/FEASIBILITY/PIPELINE + `tools/`
+ `work/` + `extract/`). Install `D:\Games\Spider-man Remastered` (FLT crack, exe
`Spider-Man.exe`, built 2022-08-12). games.id = **`spiderman`** (already existed
— artwork uploaded, `game_detector.py` already resolved it — NOT `spiderman2`,
a separate already-shipping title). Same Insomniac **"Luna"** engine as
Spider-Man 2 / Ratchet & Clank Rift Apart, so most of the reusable machinery
(`dat1lib`, the index-redirect deploy pattern, the DAT1 loc codec's 5-tag layout)
carried straight over — the differences (older MSMR-generation toc split into 6
separate sections instead of RCRA's combined ones, Scaleform GFx UI instead of
cohtml, a per-title non-sequential language enum) each needed their own port.

- **🟢 Container = `dat1lib`'s OWN older `VERSION_MSMR = 202200` branch, reads
  natively — no new reader code needed.** `toc` magic `0x77AF12AF` + zlib DAT1,
  **771,670 assets across 6 sections** (Spans/AssetIds/KeyAssets/Sizes/Offsets/
  Archives — location is SPLIT across two parallel 8-and-12-byte sections, unlike
  SM2/R&C's single combined `RcraSizeEntry`). 46 archives (34 game + 12
  per-language voice, only `.us`=English installed on disk).
- **🔴 THE variant→span map is NOT arithmetic** (breaks R&C's clean "variant N →
  span N×8" rule — spans 16/136/160/176/192 are skipped in MSMR's 23-variant
  set). Resolve every span by scanning, never by formula.
- **🟢 Text = `localization/localization_all.localization`, 23 variants, BYTE-
  IDENTICAL 5-tag DAT1 layout to R&C** (`0xD540A903` ENTRY_COUNT / `0x4D73CEBD`
  KEYS / `0xA4EA55B2` KEY_OFFSETS / `0x70A382B8` VALUES / `0xF80DEEB4`
  TEXT_OFFSETS). `tools/msmr_loc.py` — **identity round-trip 23/23 SEMANTIC-PASS,
  0 mismatches**; single-key patch test isolates exactly 1 changed value.
  57,368 KEYS records; scope = **49,351 non-empty English / 46,556 GLOBAL
  UNIQUE** (UI 10,987 · subtitles 33,252 · credits 5,112).
- **🔴🔴 A WHOLE-FILE Unicode script sniff LIES on this format.** All 23
  variants report identical `hebrew=2703/arabic=6439/cyrillic=6563` — that's
  shared binary-table noise from the OTHER 4 sections, not text. Classifying the
  VALUES section only gave the true, load-bearing answer: **`arabic=0` across
  every variant** ⇒ MSMR has NO real Arabic translation anywhere (span 152, the
  `kLanguageArabic` slot, is English TEXT paired only with the Arabic VOICE
  track — a menu-picker label with no populated foreign content behind it).
  **⇒ RETRACTS an earlier unsupported claim** ("a Nexus mod proves engine RTL
  on this title") — the page is unreachable/no Wayback snapshot, and there was
  never an Arabic slot to have proven anything with. Reclassified: **LTR-slot
  hijack, store-VISUAL class** (Playbook §8b — AC2/Anno/GTA/TLOU/R&C family),
  not the free-engine-RTL Arabic-slot class.
- **🔴🔴 THE language enum is PER-TITLE, and it is non-obvious, silently-wrong-if-
  copied.** MSMR's own 32-slot `kLanguage*` exe string table:
  `1=English · 19=Arabic` — **differs from SM2's `hebrew:18` AND R&C's own
  distinct numbering** (MSMR inserts `kLanguageMxSpanish` at 17, shifting
  everything after it). **Proven, not guessed:** cross-checked against which
  enum values have an installed VOICE-dub archive (12 archives: `us fr de it jp
  pl pt ru es br ar la`) — only `enum value == table position` (not `position-1`)
  satisfies zero orphans. **This machine's registry `TextLanguage` was found
  already set to `19`** (resolving to span 152, a completely different variant
  than the naive "span 0 = English default" assumption) — a single-span deploy
  targeting the wrong slot would very likely have been INVISIBLE on launch.
  **Fix: reset the registry to `1`** (the true English default, span 8) AND
  build a **3-candidate ladder** (spans 0/8/152, each with its own distinct
  Latin marker) so one screenshot names the live slot unambiguously regardless
  of outcome — [[measure-with-a-ladder]].
- **🟢 Font = Scaleform `DefineFont3`, format already solved (Witcher 3 codec,
  reused VERBATIM).** MSMR's UI is Scaleform GFx, NOT SM2's cohtml (confirmed:
  exe scan `Scaleform`×167 / `cohtml`×0). `.gfx` files are **bare uncompressed
  Scaleform containers** (magic `"GFX"`+version, no CR2W/CFX wrapper — the
  simplest container class in this project). `Font_LatinAS3.gfx` = 5 faces
  (Azbuka Pro Bold/Bold-Italic/Medium, Courier New, Digital — "Azbuka Pro" is
  the same family SM2 uses), **0/27 Hebrew in all 5**. `tools/msmr_font.py`
  (direct port of `games/witcher3/work/inject_gfxfontlib.py`'s ADD-not-replace
  logic — Hebrew's codepoint range sits below the faces' max code, must be
  INSERTED at the sorted position) added **135 Hebrew glyphs total (27×5)**,
  self-verified by re-parse, and confirmed the rebuilt file re-opens cleanly in
  FFdec. Donor: Heebo-Regular.
- **🟢 Deploy = index-redirect, offline-validated AND live-deployed (after one
  real bug found + fixed on the FIRST live deploy).**
  `tools/msmr_deploy.py`, ported from the proven `translation_manager/
  spiderman2_mod.py` pattern to MSMR's older split-section toc. Offline
  (`validate_offline`, run on a scratch COPY first): **771,669 untouched
  assets confirmed drift=0**, redirect round-trips through the toc's own
  reader, revert byte-identical. Backup name `toc.tm_he_backup` deliberately
  distinct from Overstrike/ALERT's own `toc.BAK` (no collision — confirmed no
  `toc.BAK` exists on this machine, so no prior suit-mod install to clash with).
  **🔴🔴 THE FIRST deploy showed the pre-game "Launcher" settings screen
  (a separate, always-reachable UI reading the SAME loc asset) render every
  visible label as its RAW KEY name, and the game HUNG after the boot logos.**
  Root cause: `append_archive()` cloned BOTH `install_bucket` (safe — shared
  `0` on every base-game archive) AND `chunkmap` (a small, per-archive-UNIQUE
  sequential id, `g00sNNN`→`1000N`) from an existing archive — 4 new rows all
  claimed the SAME chunkmap the archive I cloned from already held.
  **`dat1lib` itself never reads `chunkmap`** (grep-confirmed: `extract_asset`
  resolves purely `archive_index→filename`), so **every offline validation
  this session ran passed cleanly** — the collision was invisible to my own
  tooling; the real Insomniac archive/chunk-streaming resolver evidently keys
  off it and misdirected reads back onto the original archive. Fix: assign
  each appended archive `max(existing chunkmap)+1`, recomputed per call.
  Re-verified: 4 new archives got unique values, and a FULL-CORPUS diff (all
  ~57,361 unpatched keys of the live span-8 asset, read through the real
  game's own toc) showed 0 unexpected changes. Redeployed.
  **⚠️ MSMR-specific, NOT a bug in the shipped SM2 mod** — SM2/R&C run the
  newer RCRA toc generation, whose `ArchiveFileEntry` has no chunkmap field at
  all (its equivalent constants are genuinely shared across every archive).
  **UNIVERSAL: when appending an archive-table entry on ANY engine/toc
  generation, verify each cloned field's semantic role individually — a
  per-archive-unique id sitting beside shared constants in the same struct is
  invisible until the REAL engine (not your own reader) is tested, and it
  varies per toc generation even within one engine family.**
- **🔴 A SECOND, still-open cosmetic bug found post-fix: the pre-game "Launcher" overlay
  (Play/Settings/PlayStation PC/Quit, appears BEFORE the Insomniac logo) shows raw KEY names**
  (`LAUNCHER_PLAY` etc) instead of resolved text, on our mod but not on vanilla — isolated to
  "appending even ONE new archive entry breaks this screen's string lookup, regardless of which
  asset/span is redirected" (proven: a minimal single-asset deploy still breaks it; the
  `ArchiveFileEntry` struct has only 2 fields, both correct; `dat1lib`'s section-repositioning
  logic traced and confirmed sound; full-corpus diffs of all 3 spans show 0 unexpected changes via
  our own reader). Root cause NOT yet found — likely this overlay is a structurally separate
  component from the main engine with its own archive-table assumption `dat1lib` doesn't model.
  **Not blocking**: pressing Enter/clicking Play advances past it into the real boot regardless.
- **✅ THE ORIGINAL "hang after boot logos" WAS A MISDIAGNOSIS.** Autonomous relaunch+capture
  testing found: (1) the Launcher overlay is a static idle menu waiting for input, not frozen —
  pressing Enter reliably advances past it into Marvel logo → further logos → loading → a
  difficulty-select screen with a Sony data-consent popup that needs its OWN confirmation;
  (2) **`dxcam` intermittently fails during this game's DX12 exclusive-fullscreen transitions on
  this machine** — a direct cross-check caught `dxcam` reporting mean=0.12 "black" for the SAME
  instant a simultaneous `PIL.ImageGrab` showed mean=82.4 (a normal lit Marvel-logo frame),
  proving several "stuck black screen" reads across this investigation were capture artifacts —
  use GDI, not dxcam, for MSMR captures going forward; (3) **boot-sequence stalls reproduce on a
  100%-vanilla, byte-for-byte unmodified toc too** (MD5-verified) — this crack's boot is
  inherently flaky/slow on this machine independent of any mod work; no evidence found that the
  mod makes it worse than vanilla's own baseline flakiness. Recommend the user retry launching
  manually a few times, clicking through BOTH the Launcher overlay and the Sony consent popup.
  Full writeup: `games/spiderman_remastered/PIPELINE.md`.
- **🔴🔴 ROUND 2 (2026-08-10) — a genuine, real hard stall, exhaustively isolated and proven
  MOD-INDEPENDENT.** User re-reported the window stuck black mid-load. Signature: log grows
  normally to a short `[Save] Request type 3 failed with code 0x00000002` burst (proven benign —
  a same-machine `Marvel's Spider-Man Miles Morales.log` shows the identical burst self-resolving
  in ~3s on a working launch, reaching confirmed active gameplay ~4m44s after boot) then goes
  **100% silent permanently**, while CPU stays pinned ~150-250% (~2 cores non-stop, no plateau)
  and WorkingSet does a repeating multi-GB spike→drop sawtooth — a tight native retry loop, not
  slow loading (which would plateau) or shader compile (which would hold memory, not free it).
  **Isolated 7 independent variables, each ruling one out completely** (12/10-min patient monitors
  per test, not the earlier premature 2-5min kills): GPU adapter (confirmed real AMD RX 9070, not
  the co-installed Parsec virtual display) · on-screen-keyboard input-focus theft (closed, sent
  Enter directly to the real window by title-matched HWND) · `flt.ini Offline=1` vs `=0` ·
  FLT's vs Goldberg's `steam_api64.dll`+`steam_settings` (all 4 crack loaders ship in `NoDVD/`) ·
  12 continuous minutes of patience (722s, zero change). **The decisive test: reverted the toc to
  100% pristine vanilla (`msmr_deploy.revert`, confirmed zero mod files) and it stalls IDENTICALLY
  — 602s, zero log growth, same dead-flat screen.** Conclusively proves this has nothing to do
  with the Hebrew mod, chunkmap fix, loc redirects, or font injection. Root trigger itself NOT
  found (no Windows crash/hang event ever logged, `Responding=True` throughout — an active
  spin/retry loop needing a real debugger to pin down, out of scope this round). State left clean:
  FLT `steam_api64.dll` restored (md5-verified), Goldberg test files removed, the chunkmap-fixed
  proof (spans 0/8/152 + font) **re-deployed + read-back-verified** since vanilla is equally
  stalled. Two untried next steps for the user: try a different repack of the game entirely, or
  roll back the AMD driver (updated 24/07/2026, close to when this was first noticed). Full
  writeup: `games/spiderman_remastered/PIPELINE.md`.
- **⚠️ ROUND 3 (2026-08-10, same day) — the official Nixxes stability-patch chain does NOT
  eliminate the stall; it remains INTERMITTENT at v3.618, exactly matching Round 2's own
  established conclusion that this is inherent boot flakiness, not a build-vintage bug.**
  The installed game was the completely unpatched
  **2022 launch-day build** (`flt.ini BuildId=9304506`) — the user tracked down + downloaded 3
  official update packages via the fitgirl-repacks.site/cs.rin.ru/ElAmigos community convention
  and handed me their local paths: `…_b9304506_to_b12423814_AiO_MULTI23-CS.rar`,
  `…_b12423814_to_b14752622_v3.618-CS.rar`, `…_from_v3.618_to_v4.630-ElAmigos.rar`.
  - **Update #1 + #2 applied BYTE-PERFECT** (b9304506 → b12423814 → b14752622/"v3.618"):
    23 `asset_archive` shards (g00s000…g00s033) hpatchz-patched **in-place** (HDiffPatch
    `-f -s-2g`, its OWN documented safe same-path mode — writes to a temp file, atomically
    renames over the original only on success) + ~30 straight-replacement files (exe, DLLs,
    `dag`/`toc`) extracted from each package's `update.exe`. **Verified against the official
    59-entry SHA1 manifest shipped in package #2: all 59/59 match exactly** (excluding the
    deliberately-cracked `steam_api64.dll`, restored to the FLT version after an update.exe run
    silently overwrote it with the real Steam DLL — backup `steam_api64.dll.flt_backup`).
    `flt.ini BuildId` updated `9304506→14752622` to match.
  - **🔴 `patch.exe`/`update.exe` are genuine 7-Zip SFX archives** (`7z.exe l` reveals an
    embedded `Silent=1, Overwrite=1` comment-block) — **NOT** the GNU-patch-style tool the
    shipping `.bat`'s own flag usage (`-s -x -y`) implied; those flags are simply wrong for this
    format. **Fix: `7z.exe x <src> -o<destGameDir> -y`, run DIRECTLY from the pristine
    Downloads-extracted source** — never stage these large exes inside the game folder itself
    (they were observed to repeatedly and unexplainedly vanish from there; traced to the `.bat`
    script's own unconditional cleanup `del /f /q`, NOT antivirus, which was directly ruled out).
  - **🔴🔴 cmd.exe (BOTH Git-Bash's `cmd //c` AND native PowerShell's `cmd.exe /c`) fails to
    launch certain valid PE executables** (`update.exe`, `hpatchz-x64.exe`) — reports "is not
    recognized as an internal or external command" even though the files demonstrably exist
    with valid MZ/PE headers — **while PowerShell's `&` call operator / `Start-Process` launches
    the identical files instantly and reliably.** Root cause not fully explained; not an AV issue
    (ruled out directly — ESET's `ekrn.exe` was running throughout with zero interference via
    PowerShell). **STANDING RULE for this game folder: never invoke an executable via cmd.exe —
    always PowerShell `&`/`Start-Process`, or `7z.exe x` directly, bypassing execution.**
  - **🔴 Update #3 (v3.618→v4.630, ElAmigos Inno Setup installer) silently NO-OPS** under both
    `/VERYSILENT` and `/SILENT` (no log file ever created, nothing changes). Leading theory (not
    confirmed, not fixed): a **stale HKLM Inno Setup uninstall registry entry**
    (`...\Uninstall\Spider-man Remastered_is1`, `InstallLocation=F:\Game Lab\Spider-man
    Remastered\` — confirmed absent from disk) from an old install location, which an
    Inno "update"-style installer typically validates against before proceeding — would need
    admin/HKLM write access to fix (this session's context is Medium Mandatory Level, non-
    elevated). **Deferred** rather than chased further, since v3.618 already delivers the result
    below.
  - **First launch attempt on this build (vanilla, mod-reverted state from Round 2's isolation)
    SUCCEEDED — reached the SELECT DIFFICULTY screen** (title bar `Marvel's Spider-Man
    Remastered v3.618.0.0`, `flt.ini Language=English`), **user-confirmed via screenshot.**
    This is far past the Round-2 stall point on its own — a genuinely encouraging data point —
    but with an INTERMITTENT bug, one success proves nothing on its own (Round 2 already
    established stalls reproduce on vanilla too; a single clean boot doesn't distinguish
    "fixed" from "got lucky this time").
  - **🔴🔴 THE MOD (`msmr_deploy.apply()`, the chunkmap-fixed proof from Round 2, re-deployed +
    read-back-verified 100% correct on the fresh v3.618 toc) WAS THEN DEPLOYED, and the VERY
    NEXT launch attempt STALLED AGAIN — user-confirmed via screenshot, `flt.ini Language`
    still English (span 8, the same slot both launches read).** Signature is IDENTICAL to
    Round 2: window frame + title bar visible, content 100% black except the small spider
    watermark bottom-right, process alive (`Get-Process`: `Responding=True`, CPU climbing
    continuously — 273.6 CPU-seconds accumulated by the time it was checked, consistent with
    the ~2-cores-pinned spin/retry loop already documented). An autonomous background
    launch+capture attempt (`34_gdi_watch.py`) run moments earlier on the SAME toc state
    independently corroborates this — its process-liveness poll flapped (falsely read
    "process exited" at one tick, contradicted by the process still being alive and CPU-
    accumulating when checked directly moments later — a WMI polling race, not a real exit)
    and its GDI capture caught only the bare desktop with no visible game window at t=71s,
    10s before that false "exited" reading — i.e. **the automated tooling's own signals were
    inconclusive/misleading here; only the user's direct screenshot gave ground truth.**
    Process killed to unblock the user (`taskkill /F /IM Spider-Man.exe /T`).
  - **CORRECTED CONCLUSION: the update chain (2022 build → v3.618) does NOT fix the stall —
    it is still present, still intermittent, on the SAME updated build, with AND without the
    Hebrew mod deployed.** This directly reproduces Round 2's own "reverted to 100% pristine
    vanilla and it stalls identically" result, just one build-generation later: build vintage
    was never the cause. The earlier successful boot was a lucky attempt, not evidence of a
    fix — **do not draw a conclusion from a single successful launch on an intermittent bug;
    only a run of several consecutive successes (or a genuine root-cause fix) would qualify.**
    The mod itself remains exonerated exactly as in Round 2 (deployed AND reverted states both
    stall) — this is not a regression introduced tonight, it is the same pre-existing,
    unsolved, mod-independent, build-independent flakiness. Update #3 (→v4.630) therefore has
    no reason to be expected to help either, on top of being blocked (see above).
  - **STATE LEFT:** Hebrew mod proof (spans 0/8/152 + font) is DEPLOYED and read-back-verified
    on the current v3.618 toc (not reverted — its correctness is independent of the stall, per
    Round 2). Registry `TextLanguage=1`. The stuck process was killed; no other state changed.
  - **NEXT (unchanged from Round 2, still the only untried real leads):** try a different
    repack of the game entirely, or roll back the AMD driver — both still untried. Retrying the
    launch a few times remains the only known mitigation for any GIVEN session (it is
    non-deterministic, so a retry can succeed even though nothing was fixed). Once/if a launch
    reaches the menu with the mod deployed, screenshot the boot splash (names the live span via
    the marker) + the main menu (Continue/New Game/Load Game/Quit Game) + the language screen —
    the bidi/glyph-coverage/layout gates below were never actually retested in-game this round.
- **🔴🔴 ROUND 4 (2026-08-11) — CONFIRMED: on the OFFICIALLY-UPDATED v3.618 exe specifically, the
  Hebrew mod deploy causes the boot stall.** User directly, three times in a row on the SAME toc,
  correlated the mod deploy with the stall (revert → clean boot; re-deploy → stuck; re-deploy
  again → stuck again; revert again → clean boot again, user-confirmed with a screenshot reaching
  Select Difficulty). This is the OPPOSITE of Round 2's conclusion on the ORIGINAL (2022,
  unpatched) exe, where the identical deploy mechanism was proven mod-independent (vanilla stalled
  too). **The two are not a contradiction — they are two different exe binaries** (the official
  update wholesale-replaced `Spider-Man.exe`), so Round 2's mod-independence proof does not
  transfer to this newer exe; it very plausibly validates/streams archives more strictly than the
  2022 build did, in a way this project's byte-level checks (chunkmap uniqueness, toc semantic
  round-trip — both re-verified clean this round, see below) cannot see. **Do NOT re-deploy this
  mod build against the updated exe until the actual incompatibility is root-caused** — took it
  seriously and re-ran the two most
  likely structural checks, on THIS toc specifically (not the original one Round 2 tested):
  (1) **chunkmap/install_bucket collision** (the exact class of bug already fixed once) — verified
  clean: the 4 appended archives got `install_bucket=0` correctly cloned from a real base archive
  and 4 sequential UNIQUE chunkmap values (112146-112149), zero collision against the 46
  pre-existing archives. (2) **A blind identity round-trip of the WHOLE pristine v3.618 toc**
  (read → write back with ZERO edits, via the exact same dat1lib read/save path `apply()` uses) —
  the output is NOT byte-identical (−12,098 B, expected zlib-recompression variance, same class
  already documented project-wide for dat1lib serializers) but is **100% semantically identical**:
  0 mismatches across all 771,677 offset/size entries and all 46 archive entries. Neither check
  found anything wrong with the deploy mechanism on this new toc.
  **A live process check during one of the reported stalls found something the earlier Round 2
  signature did NOT have: an active `[Render]` FPS-stat log line (fps≈236) appearing ~57s after
  the same `[Save] Request type 3` / PSN-auth burst**, i.e. the render loop is genuinely alive and
  swapping frames, not 100% silent-forever — yet the user's own screenshot showed the window still
  black. This is either the render thread free-spinning on an empty/cleared frame while some other
  resource/async-load never resolves, or simply a later stage of the same underlying issue; not
  conclusively distinguished this round. **Also discovered: this desktop runs several concurrent
  Antigravity/Claude sessions with overlapping windows (other games in this same multi-project
  workspace), so this session's own automated dxcam/GDI screen captures are UNRELIABLE here** —
  a capture attempted mid-stall grabbed an unrelated IDE window sitting on top of the game, not
  the game itself. The user's own direct screenshots are the only trustworthy visual ground truth
  in this environment for this game. **STATE LEFT: mod REVERTED, game back to its confirmed-clean
  vanilla v3.618 state, USER-RECONFIRMED via a 4th screenshot** (Select Difficulty, clean boot) —
  `msmr_deploy.revert()`, verified `backup:false, manifest:false`, and NOT re-deployed since. The
  stuck process was killed each time it happened to unblock the user. **Byte-level structural
  correctness (chunkmap uniqueness, toc semantic round-trip) is NOT sufficient proof a deploy is
  safe on this newer exe** — both checks passed clean, and the mod still reliably stalled it 2/2
  attempts, with a matching 2/2 clean-boot rate on revert. **STANDING RULE until root-caused: do
  not deploy this Hebrew mod build against the officially-updated (v3.618+) exe — it is confirmed
  to break it. It remains safe/proven only on the original 2022 unpatched exe (b9304506), where
  Round 2 already proved mod-independence.**
  - **🔴🔴 Round 4b (same session) — attempted a genuine alternative deploy mechanism, and it
    revealed WHY `apply()`'s append-new-archive design is the ONLY viable option here, not an
    arbitrary choice.** Theory: maybe the updated exe distrusts a brand-new, never-seen
    archive/chunkmap/filename entry specifically; an append-RELOCATE into an EXISTING, already-
    trusted archive_index (same technique proven elsewhere in this project for AC Unity/RDR2/007)
    would avoid that. Built `apply_inplace()`/`revert_inplace()` in `msmr_deploy.py` + a new
    `work/21_build_menu_proof_inplace.py`, offline-validated clean on a scratch copy (0 mismatches,
    byte-exact revert), then deployed for real onto `asset_archive/g00s000` (archive_index 0).
    **The deploy itself wrote correctly** (raw seek+read at the file level confirmed our exact
    bytes landed at the exact redirected offsets) **but dat1lib's OWN `extract_asset()` read-back
    failed** (`UnicodeDecodeError` on garbage bytes) — because **`g00s000` (like ALL 34 game
    archives, g00s000-033) is a `DSAR`-magic'd COMPRESSED archive**: `extract_asset()` routes any
    read through a block-map decompression scheme (`f.seek(12)` → blocks-header-end → 32-byte
    block descriptors `real_offset/comp_offset/real_size/comp_size`) instead of a simple
    `seek+read`, and a naive raw append past the declared block map is neither decompressed nor
    reachable by it. **Growing the block-map to add a legitimate new block would require shifting
    every byte of existing compressed data after it — a full multi-GB archive rebuild, not a small
    in-place append — with no existing dat1lib write support for this format at all.** Checked all
    46 archives: the only non-`DSAR` one is `a00s034.us` (the English voice pack, a completely
    different, unknown container — not safe to raw-append arbitrary loc/font data into either).
    **⇒ There is no existing, already-trusted archive this engine can be raw-appended into.
    `apply()`'s append-a-brand-new-archive-entry design is therefore the ONLY architecturally
    viable way to inject uncompressed loose data into this toc format — not a flaw to fix.**
    Immediately reverted the broken experiment (`g00s000` truncated back to its exact original
    2,124,037,740 B, confirmed byte-count-for-byte-count; toc restored, `toc_is_ours=False`), then
    **re-deployed the proven original `apply()` mechanism** (11/11 keys + 135 font glyphs
    read-back-verified) — the game is left in the SAME state Round 4 already found stalls on the
    updated exe. **Net result: the append-new-archive design is now proven to be the only option,
    not just the current one — so "fix the deploy mechanism" is closed as a dead end.** If the mod
    truly is incompatible with the updated exe (still not 100% certain — see Round 4's own
    caveats about capture reliability on this desktop), the actual fix would have to be something
    the updated exe checks OUTSIDE the toc/archive-table model entirely (e.g. a new validation
    layer added by the stability patch, or an environment/timing factor) — reachable only via a
    real debugger session attached to the process, comparing exact behavior with vs without the
    appended archives. Not attempted; genuinely out of scope for a single sitting without that tool.
  - **🔑🔑 Round 4c/4d/4e (later session) — a THIRD deploy mechanism (in-place DSAR block overwrite,
    ZERO toc/archive-table changes at all) was built, and FOUR clean isolating tests against it
    cleanly proved the trigger is purely "does the DECOMPRESSED content differ from vanilla" —
    independent of archive structure, write events, file location, and even compression method.**
    `games/spiderman_remastered/tools/msmr_dsar_patch.py` (NEW): span 8's loc asset is perfectly
    block-aligned (24 whole 262144-B blocks) in `g00s019`, so its content can be recompressed
    block-by-block with standard `lz4.block.compress(..., store_size=False)` (proven byte-for-byte
    compatible with `dat1lib`'s own decoder) and written back IN PLACE at the exact same
    `comp_offset`s the game's own encoder used, shrinking only the block-map header's own
    `comp_size` field when the new data is smaller (🔴 NEVER zero-pad the leftover space — the
    decoder's `while real_i <= real_size and comp_i < comp_size` loop condition re-enters and
    parses garbage/crashes past the buffer; found + fixed live). Four tests, in order:
    1. Content-DIFFERENT marker patch, in-place, zero toc changes → **STALLED** (user: "עדיין לא") —
       rules out archive-table growth ENTIRELY as the cause (not just as one possible mechanism).
    2. Antivirus ruled out too: Defender confirmed disabled, ESET confirmed active but a PATH
       exclusion already covers the whole game folder (user-confirmed).
    3. A TRUE byte-identical rewrite (same bytes, real write, real `LastWriteTime` change) →
       **SUCCEEDED** (user: "תפתח", reached Select Difficulty normally) — proves an OS write event
       alone is 100% safe; the trigger is specifically content DIFFERING from vanilla.
    4. Content-IDENTICAL re-encode via a hand-built zero-match "literal-only" LZ4 stream (totally
       different compressed-byte shape, same decompressed bytes, verified round-trip before
       writing) → **SUCCEEDED** (user: "נדלק") — rules out compression shape/algorithm (and any
       hardware/DirectStorage-decompressor-path theory tied to it) as a factor too.
    **Searched exhaustively for a stored content hash and found NONE anywhere on disk:** the DSAR
    archive header's previously-undecoded bytes are a version-tag constant + a plain block count
    (not content-derived); the block-map's trailing padding u32s are constants across every block;
    the toc's `ArchivesSection` struct (`install_bucket, chunkmap, filename` per
    `dat1lib/types/sections/toc/archives.py`) has no hash field; `Spider-Man.exe`'s strings hold no
    conclusive integrity/hash marker tied to archive content (`EnableDirectStorage`/
    `SetInstallState` look like unrelated telemetry-tag/state-machine name lists); and the only
    manifest-like file anywhere in the install tree, `_Redist\fitgirl.md5`, is the FitGirl repack's
    OWN third-party, manually-run SFV self-check tool (paired with `QuickSFV.EXE`) — never
    referenced in the exe, never touched by the running game. **⇒ Static file analysis is now
    genuinely exhausted for this question.** The mechanism is real and precisely isolated
    (decompressed content ≠ vanilla ⇒ stall, and ONLY that) but pinpointing WHERE in the exe's own
    code it is computed needs a live debugger attached to the running process — the standing rule
    above (mod safe only on the original 2022 `b9304506` exe, confirmed unsafe on v3.618+ until
    root-caused) is now the most rigorously proven version of that conclusion this project has
    reached, and remains in force.
  Full writeup: `games/spiderman_remastered/PIPELINE.md`.
- **🟢🟢🟢 SUPERSEDED (2026-08-12) — THE STANDING RULE ABOVE IS OVERTURNED. Real Hebrew content
  DOES boot correctly on the updated v3.618 exe — the earlier "any content difference from vanilla
  ⇒ stall" conclusion was itself CONFOUNDED, and the confound is now resolved.** Two things changed
  at once, and BOTH were needed:
  1. **`msmr_loc.encode()` (the old full-rebuild encoder) does NOT round-trip identically even on a
     no-op patch** — it dedupes the VALUES blob by content and relayouts every section's offset
     from scratch. Every prior "content-different" test that failed (incl. round 4c's marker patch)
     was very likely built with this encoder, so it was never a clean test of "does content differ",
     it also broke internal structural invariants (the hash/sorted-index/permutation section triple
     `0x06a58050`/`0xc43731b5`/`0x0cd2cfe9`) that a genuine vanilla asset never has broken.
     **`msmr_loc.encode_minimal()` (NEW)** fixes this: `encode_minimal({})` is BYTE-IDENTICAL to the
     source, and a real patch only touches the target keys — same-length values edited truly in
     place, different-length values appended past VALUES' own end with just that key's
     TEXT_OFFSETS entry repointed (relative to VALUES' own section start) and VALUES' own
     section-table size patched. Everything else in the file is untouched.
  2. **The delivery mechanism must be `msmr_dsar_patch.py`'s in-place, same-block-position DSAR
     overwrite — NOT `msmr_deploy.apply()`'s new-archive-entry mechanism, even after matching that
     mechanism's `install_bucket`/`chunkmap` values to a real, field-proven community tool**
     (`team-waldo/InsomniacArchive`'s `ArchiveDirectory.SaveArchives`: `install_bucket=2,
     chunkmap=0x0001CCCC`, ONE new archive file + ONE new entry for every patched asset, not one
     per asset — `msmr_deploy.append_archive()`/`apply()` were rewritten to match this exactly).
     **This STILL failed in-game with clean `encode_minimal()` content** — proving the archive-table
     mechanism (any brand-new-archive-entry approach, however faithfully constructed) is itself
     incompatible with the updated exe, independent of content cleanliness. The ONLY mechanism that
     has ever worked on v3.618 is the one that touches **zero** toc/archive-table bytes at all:
     overwrite the SAME 262144-byte DSAR blocks the asset already occupies, at their existing
     `comp_offset`s, re-encoded with standard LZ4 (`lz4.block.compress(mode="high_compression")`,
     shrinking the block-map header's own `comp_size` field when the new data is smaller — NEVER
     zero-pad the leftover, `dat1lib`'s decompress loop condition is `<=` not `<` and re-enters once
     past the end).
  **Proof, in order, all user-confirmed in-game:** (a) Round 4f (`msmr_dsar_patch.plan_reencode_
  asset`, built earlier but never actually run/reported) — DECOMPRESSED content 100% byte-identical
  to vanilla, but every one of the 24 blocks' `comp_size` header field deliberately SHRUNK via a
  stronger compressor → **SUCCEEDED**. This alone already refuted "any comp_size-patch is fatal"
  and, combined with round 4c's failure, pinned the remaining candidate down to genuine content
  difference OR the encoder/mechanism confound. (b) A REAL, distinct Hebrew payload — 5 keys,
  translated text on the splash/confirm/settings screens, each padded with trailing U+0020 to the
  EXACT UTF-8 byte length of its English original (so `encode_minimal()` takes the pure same-length
  in-place path and the TOTAL blob stays byte-for-byte the same length as vanilla, 6,039,380 B),
  delivered via the SAME in-place DSAR mechanism → **SUCCEEDED**, readback through
  `dat1lib.types.toc.TOC.extract_asset()` (the exact engine-reader code path) confirmed all 5
  Hebrew strings correct and all other 57,398 keys byte-identical to vanilla.
  **🔴🔴 THE HARD CONSTRAINT this mechanism carries forward: NO GROWTH.** `msmr_dsar_patch.plan()`
  requires `len(new_blob) <= sz.value` (the toc's declared asset size) and refuses otherwise — it
  only overwrites bytes an asset already legitimately occupies, never touches the toc, never grows
  the archive's block-map. A real ~57,403-key Hebrew localization will almost certainly need SOME
  entries longer in UTF-8 bytes than their English source (Hebrew letters are 2 B/char vs 1 B for
  ASCII, even though word/character COUNTS often run shorter) — whether the FULL corpus fits inside
  the vanilla asset's exact total byte budget (or needs partial/prioritized coverage, or a
  DSAR-block-map-growing extension of this same in-place approach — reasoned through, NOT yet
  attempted: extend `blocks_header_end` by one 32-byte record and shift every byte after it in the
  multi-GB archive) is now the open, MEASURABLE next question — not a mystery anymore, an
  engineering budget problem. **No live debugger was ever needed.**
  **Tools:** `games/spiderman_remastered/tools/msmr_loc.py` (`encode_minimal`, NEW) ·
  `msmr_dsar_patch.py` (`plan`/`apply_plan`/`plan_reencode_asset`/`revert`, the PROVEN safe path) ·
  `msmr_deploy.py` (`apply`/`apply_inplace`, BOTH now known-bad on v3.618+ — kept only as reference/
  for the original-2022-exe fallback path, do not use them for the updated exe again).
- **✅ ROUND 2 (2026-08-12) — 12 MORE keys deployed on the user's own screenshots (main menu +
  Select-Difficulty screen), STACKED on top of the 5 already-proven keys, all 17 verified live
  in one blob. User asked to see natural Hebrew on the EXACT screens they photographed rather than
  screens the mod happened to touch — a real lesson: don't guess which screen a key belongs to,
  derive the key names from the visible strings via an exact-match search against the live loc
  dict, THEN translate those.** Keys + Hebrew (all exact-byte-padded to their English source):
  `LAUNCHER_OPTIONS`="הגדר" (8B, root/imperative form of "settings" — "הגדרות" is 12B, too long),
  `LAUNCHER_QUIT`="צא" (4B exact — "exit"), `TEXT_DIFFICULTY_TITLE`="בחר קושי" (15B/17B),
  `TEXT_DIFFICULTY_SUPER_EASY`="קל ביותר" (15B/21B, "easiest" — the FRIENDLY NEIGHBORHOOD comic
  pun couldn't fit), `TEXT_DIFFICULTY_EASY`="ידיד" (8B exact, "friend" — echoes FRIENDLY),
  `TEXT_DIFFICULTY_NORMAL`="טוב" (6B/7B, "good" — no 3-letter Hebrew word means "amazing"),
  `TEXT_DIFFICULTY_HARD`="מאתגר" (10B/11B, "challenging"),
  `TEXT_DIFFICULTY_NORMAL_DESC`="מתאים למי שרוצה חוויה מאוזנת ומאתגרת." (68B/79B, a natural full
  sentence — the widest budget of the batch), `TEXT_DIFFICULTY_SLIDER_HEADER`="כוח" (6B/7B,
  "force" — no 3-letter word for "enemies" plural fits), `TEXT_DIFFICULTY_AGGRESSIVENESS`=
  "תוקפנות" (14B exact), `TEXT_DIFFICULTY_DAMAGE`="נזק" (6B exact), `TEXT_DIFFICULTY_HEALTH`=
  "גוף" (6B exact, "body" — no 3-letter word for "health" fits; paired with "נזק" it reads fine
  as a stat pair). **`LAUNCHER_PLAY` (4B, "Play") was DELIBERATELY LEFT ENGLISH** — 4 bytes = 2
  Hebrew letters max, and no 2-letter Hebrew word means "play" in a button-label sense; forcing one
  would ship nonsense. This is a genuine, disclosed limit of the no-growth mechanism, not an
  oversight.
  **🔴 Deploy required a REVERT-FIRST step not needed on round 1.** Re-`plan()`ing the combined
  17-key blob directly against the round-1-deployed archive FAILED — `apply_plan` raised
  `"plan says NOT all blocks fit"` even though the new blob's TOTAL length exactly equalled
  vanilla. Root cause: `plan()`'s per-block `fits` check compares against that block's CURRENT
  on-disk `comp_size` header field, not the original vanilla one — and Round 4f's earlier
  best-of-3-compression-levels test had already shrunk several blocks' `comp_size` to the tightest
  size achievable for THEIR content at the time; the new round-2 content (different text mix)
  didn't necessarily compress into that already-shrunk budget. **Fix: `msmr_dsar_patch.revert(GAME)`
  first** (restores every previously-touched block's ORIGINAL bytes + ORIGINAL comp_size from the
  accumulated backup manifest — verified: `status()` before/after showed `24 blocks` → `backup:
  False`, i.e. fully back to pristine vanilla headroom), THEN re-`plan()`+`apply_plan()` the SAME
  built blob (which already had the 5 round-1 keys baked in from `raw = dp.verify_readback(...)`
  taken BEFORE the revert, so nothing was lost) — this time `all_fit: True` on all 24 blocks.
  **UNIVERSAL LESSON for this mechanism: a block's compression headroom is a property of its
  CURRENT on-disk state, not vanilla — always `revert()` to true vanilla before re-planning a
  combined/updated patch, never stack a new `plan()` directly on top of a previous deploy's
  already-shrunk `comp_size` fields.** Verified: readback via `dat1lib`'s real `extract_asset()`
  matches the built blob byte-for-byte (6,039,380 B), all 17 patched keys correct, all other
  57,386 keys untouched. **Awaiting the user's in-game confirmation on the main menu + Select
  Difficulty screen** (the exact two screens they photographed).
- **🔴🔴 THE FONT GATE — user screenshots confirmed the pre-game "Launcher" overlay renders Hebrew
  clean, but IN-GAME the Select Difficulty screen showed pure tofu (small boxes) for every
  character — TWO SEPARATE FONT SYSTEMS.** The Launcher overlay is a different, already
  Hebrew-capable rendering layer (unrelated to this asset); the actual GAME UI draws with a
  Scaleform GFX font-lib, `ui/export/fonts/Font_LatinAS3.gfx` (aid `0xB1BC4746124FA7ED`, ALSO in
  archive `g00s019` — the same archive as the loc text, at a different byte range) — read live and
  confirmed **0/27 Hebrew across all 5 embedded `DefineFont3` faces** (Azbuka Pro Bold Italic/Bold/
  Medium, Courier New, Digital). `games/spiderman_remastered/tools/msmr_font.py` already existed
  from an earlier session (Hebrew-glyph injector, ported from the Witcher 3 SWF codec) but had
  never actually been DEPLOYED into the live archive — only validated offline against a standalone
  extracted copy.
  **🔴 Injecting Hebrew into all 5 faces GROWS the asset by 12,127 B — and the in-place, no-growth
  DSAR mechanism has ZERO slack**: `msmr_dsar_patch.plan()`'s block-alignment check requires the
  covering blocks' DECOMPRESSED total to equal the toc's declared size EXACTLY (`total_real !=
  sz.value` → refuse), so even a single added byte fails — this is a harder constraint than the
  loc text's `len(new_blob) <= sz.value` check (which merely refuses GROWTH; here there was no
  slack to shrink INTO from either).
  **✅ FIX — drop one unused face wholesale to fund the others' Hebrew glyphs, entirely within the
  SAME asset, ZERO toc/archive-table changes.** Measured that trimming the Hebrew alphabet itself
  saved nothing (26 of 27 letters are actually used across all 17 patched strings — only final-Tsadi
  ץ is unused). Instead: **"Digital"** (font_id=4, 66 glyphs, 8,290 B — a numeral/7-segment-style
  display face, structurally distinct from the 3 "Azbuka Pro" body-text faces) was removed ENTIRELY
  (whole `DefineFont3` tag, header+body) via a new `msmr_font._rebuild_gfx_drop()` (a
  removal-capable sibling of `build_font.rebuild_gfx` — copies every untouched tag verbatim, skips
  emitting anything for a dropped tag's index, corrects the GFX header's `fileLength` field by the
  net delta). Hebrew was then injected into the 3 prose-worthy faces (Bold Italic, Bold, Medium —
  `+27` each = 81 total) via `msmr_font.inject(..., only_faces={...}, drop_faces={"Digital"})`
  (both params newly added); **Courier New was left completely untouched** (monospace/dev-console
  face, unlikely to render translated UI prose, and touching it wasn't needed once Digital's budget
  covered the other three). Net: **−955 B vs vanilla** (comfortable margin, zero-padded by
  `plan_by_path()`).
  **🔑 Deploy needed a NEW resolution path, `msmr_dsar_patch.plan_by_path()`** (added alongside the
  existing span/asset_id-based `plan()`, refactored to share a common `_plan_slot()` core): fonts
  and other non-localization assets have no "span" (language-variant) concept, so they're resolved
  directly via `crc64.hash(path)` → `t.get_asset_entries_by_assetid()` — the SAME lookup
  `10_font_hunt.py`'s `stage_paths()` already used for read-only recon. This is now the general
  pattern for patching ANY single-instance MSMR asset via the proven-safe in-place DSAR mechanism.
  **DEPLOYED + VERIFIED**: `dp.apply_plan()` → readback via `t.extract_asset()` (the exact
  engine-reader path) confirmed **BYTE-IDENTICAL to the zero-padded built blob**; re-parsed faces
  show `Bold Italic/Bold/Medium = 27/27 Hebrew`, `Courier New = 0/27` (untouched, as intended),
  `Digital` absent. **The earlier loc-text patch (17 keys) was independently re-verified intact in
  the SAME archive** — the two DSAR block ranges (text asset vs. font asset) are fully independent,
  confirmed by re-reading both through their own engine-reader paths after the font deploy.
  **⚠️ Disclosed tradeoff, not yet in-game confirmed:** removing "Digital" carries a modest,
  unverified risk if some OTHER screen (a countdown timer / stylized numeral HUD) references it —
  lower blast radius than any toc-level change (a font-face regression is localized and trivially
  revertible via `dp.revert(GAME)`, unlike a boot stall). If the user ever sees a broken/blank
  numeral display elsewhere, that face is the first suspect.
  **Tools:** `games/spiderman_remastered/tools/msmr_font.py` (`inject(only_faces=, drop_faces=)`,
  `_rebuild_gfx_drop`, NEW params) · `msmr_dsar_patch.py` (`plan_by_path`, `_plan_slot`, NEW —
  generalizes the proven mechanism beyond the loc span system to any path-addressable asset).
- **🔴🔴 bidi = STORE-VISUAL, confirmed live once the font gate was closed** (§8b class — same
  family as RDR2/GTA/AC2/Anno/TLOU/GoT/007). With real Hebrew glyphs finally visible, the
  Select-Difficulty screen showed every string in EXACT reverse character order —
  `בחר קושי` rendered as `ישוק רחב` (a Latin-name reads: reverse the whole logical string). **The
  in-game render was the proof, not a guess**: `bidi.algorithm.get_display('בחר קושי',
  base_dir='R')` independently reproduces `ישוק רחב` byte-for-byte, confirming this engine draws
  Scaleform text in pure storage order with ZERO bidi processing of its own.
  **Fix: run the REAL Unicode Bidi Algorithm on every value (never a hand reversal — see §8b rule
  1), then re-apply the SAME trailing-space padding used to hit the exact byte budget.** Padding
  position is a non-issue here specifically BECAUSE the engine does no bidi at all — a trailing
  space in storage order stays a trailing (invisible) space in the rendered output, so there's no
  visual-margin subtlety to account for (unlike an engine that DOES run bidi, where a
  logical-trailing space can land in the visual LEFT margin as a stray indent). Re-derived all 17
  values (`core = stored.rstrip(" ")` → `get_display(core, base_dir='R')` → re-pad) — every
  transform preserved the exact UTF-8 byte length (same codepoints, only reordered), so the whole
  round-trip stayed inside `encode_minimal()`'s proven same-length in-place path with 0 drift on
  the other 57,386 keys.
  **Redeploy needed a full `revert()` first** (undoes BOTH the text and font blocks, restoring
  true vanilla per-block compression headroom — same rule as the round-2 text-only redeploy),
  then a fresh `plan()`/`apply_plan()` for the text asset AND a fresh `plan_by_path()`/
  `apply_plan()` for the font asset (the font blob itself was UNCHANGED — same
  `msmr_font_hebrew_blob2.bin` — since only the TEXT content changed, not which glyphs the font
  carries). **Both verified independently, live, through the real engine-reader path**: text
  readback byte-identical to the built blob, all 17 values now in visual (pre-reversed) order,
  and the 3 Hebrew-injected font faces still intact (27/27 each, Courier New still untouched).
  **Awaiting the user's re-check of the Select Difficulty screen** — every string should now read
  correctly left-to-right in natural Hebrew reading order.
- **🔴🔴 …AND THE VISUAL FIX BROKE A DIFFERENT SURFACE THAT SHARES THE SAME TWO KEYS — bidi is
  PER SURFACE, not per product (the exact §8g/#[[bidi-per-surface-not-per-product]] class).**
  Flipping all 17 keys to VISUAL fixed the in-game Select-Difficulty screen but the SAME deploy
  broke the pre-game "Launcher" (Play/Settings/Quit) overlay — `LAUNCHER_OPTIONS`/`LAUNCHER_QUIT`
  now showed `רדגה`/`אצ` there (the earlier, PRE-fix logical values had rendered correctly on
  THAT screen — proven by the round-2 screenshot). **Two renderers read the exact same loc
  keys with OPPOSITE bidi behavior**: the pre-game Launcher overlay is a different, native
  UI layer that runs a real bidi engine (needs LOGICAL Hebrew, like the Scaleform PC-settings
  pages documented elsewhere in this project); the in-game Scaleform difficulty screen does
  ZERO bidi (needs VISUAL/pre-reversed, as just confirmed).
  **Fix — split by KEY PREFIX, the cleanest available signal for which surface owns which key.**
  `LAUNCHER_*` keys (only `LAUNCHER_OPTIONS`/`LAUNCHER_QUIT`/`LAUNCHER_PLAY` exist in this batch)
  → reverted to LOGICAL (`הגדר`/`צא`, their original round-1 values); every other key
  (`TEXT_DIFFICULTY_*`, `ABANDON_CONFIRM_*`, `ACCESS_*`) → stays VISUAL. Redeployed via the same
  revert-then-fresh-plan discipline (both the text and font assets), verified live: readback
  byte-identical to the built blob, `LAUNCHER_OPTIONS/QUIT` back to logical, all 15 in-game keys
  still visual with **zero drift** on the split.
  **⚠️ UNVERIFIED ASSUMPTION, disclosed:** this fix assumes `LAUNCHER_*` keys are read ONLY by
  the pre-game Launcher and NEVER by any in-game screen (e.g. an in-game pause menu that might
  also show "Settings"/"Quit" via these SAME shared keys). No such in-game screen has been seen
  yet, so this is the best-supported hypothesis from the evidence in hand, not a certainty — if
  the user later spots `LAUNCHER_OPTIONS`/`LAUNCHER_QUIT` rendering wrong somewhere IN-GAME, that
  would mean this pair is a genuine, unsolvable-with-one-stored-value conflict between the two
  surfaces (the string would need to live under two DIFFERENT keys, one per surface, to satisfy
  both — not attempted, since no evidence yet requires it).
- **🟢🟢 REAL ASSET GROWTH BUILT — the in-place mechanism's "NO GROWTH" limit is LIFTED for this
  archive (2026-08-12, user chose "invest in growth support" over budget-fit alternatives when
  the launcher wording — "הגדרות"/"הפעל"/"יציאה" — didn't fit the old exact-byte budget).**
  `msmr_dsar_patch.py` gained `plan_growth`/`plan_growth_by_path`/`apply_growth`/`revert_growth`/
  `status_growth`. **THE KEY FINDING that made this safe, not guessed:** a diagnostic probe
  (`msmr_growth_probe.py`/`probe2.py`) proved the archive's real (virtual) address space is
  PACKED with **zero gaps anywhere** (extending the last block in place always collides with
  another asset that starts exactly where ours ends) and the block-map table has **zero free
  slack** (no room to insert a new record without shifting the whole file) — so neither
  "extend in place" nor "insert one more record for free" exists. **The mechanism that DOES
  work: relocate the WHOLE asset to `V_END`** (the max `real_offset+real_size` across every
  block — proven the one genuinely unclaimed address, since the table has 0 gaps anywhere else)
  **and REUSE the asset's OWN already-covering block-table records in place** (same 32-byte
  positions, same table size, `blocks_header_end` never moves) **to describe the new blocks
  instead — new content is compressed with the game's own LZ4 and pure-appended at the archive's
  current EOF (no existing byte moves).** toc footprint: exactly TWO u32 fields change (Offsets.
  offset + Sizes.value for OUR ONE slot) — the Archives section (new archive_index/filename/
  chunkmap) is **never touched**, which is precisely the mechanism `msmr_deploy.apply()` used and
  which was already proven to correlate with the boot stall on the updated v3.618+ exe — so this
  is a genuinely different, narrower toc footprint than either of the two previously-failed
  mechanisms (`apply()`: new archive row; `apply_inplace()`: raw bytes outside the DSAR block-map,
  provably undecodable). If fewer new blocks are needed than the asset used to occupy, the
  leftover old records are left **completely untouched** (dead, unreferenced, harmless — same
  "dead space" pattern already used elsewhere in this file for a shrunk `comp_size`'s leftover
  bytes). **Documented, not-yet-needed limit:** can reclaim at most as many blocks as the asset's
  own current block count (24 for span 8 today, ⇒ ~252 KB of headroom above the current
  ~6.04 MB) — beyond that would need the much larger whole-archive `comp_offset`-shift extension
  (insert K new table records → shift every later block's `comp_offset` by `32×K` → full-file
  rewrite), reasoned through but deliberately NOT built since nothing has needed it yet.
  **Offline-validated on a full scratch copy of the real 2.23 GB archive BEFORE touching the live
  game** (`msmr_growth_validate2.py`): built blob readback exact · **all 771,676 OTHER assets'
  Offsets/Sizes proven zero-drift** · Archives row count unchanged (46→46) · `blocks_header_end`
  unchanged · exactly 24 table records differ, all 24 intentionally reclaimed, zero unexpected
  diffs · every compressed byte from `blocks_header_end` to the ORIGINAL EOF byte-identical
  (proves only a pure append happened) · `revert_growth()` restores BOTH the archive and the toc
  to byte-identical md5 vs pristine. **Deployed live and verified through `dat1lib`'s real
  `extract_asset()` reader** (not just a raw write): `LAUNCHER_OPTIONS` `הגדר`→**`הגדרות`**,
  `LAUNCHER_QUIT` `צא`→**`יציאה`**, `LAUNCHER_PLAY` `Play`→**`הפעל`** (its first-ever Hebrew — was
  left English every prior round since its old 4-byte budget fit nothing meaningful); total
  growth **+33 B** (6,039,380→6,039,413), archive file **+2,621,979 B** (the 24 re-appended
  compressed blocks; the OLD 24 blocks' bytes stay on disk as harmless orphaned dead weight). The
  font asset (separate slot, same archive) reverified byte-for-byte untouched. **Awaiting the
  user's in-game check of the SAME pre-game Launcher screen.**
- **🟢 DRM — the cleanest profile measured in this project.** `Spider-Man.exe`:
  0 Denuvo/VMProtect/`.vmp`/BattlEye/EasyAntiCheat, `SHA256`×2/`integrity`×4/
  `tamper`×0, ordinary unpacked PE. Overstrike ships first-class MSMR support
  (`GameMSMR.cs`) — a live modding scene routinely edits this exact toc.
- **✅✅ THE PROOF — deployed live, 3-span ladder + full bidi/glyph/layout gates
  on the primary candidate.** `work/20_build_menu_proof.py --deploy` (already
  run): span 0/8/152 each get a distinct Latin marker
  (`ZZ-SPAN0-NONE-ZZ`/`ZZ-SPAN8-ENGLISH-ZZ`/`ZZ-SPAN152-ARABIC-ZZ`) on
  `TEXT_SPLASHSCREEN_CONTINUE`; span 8 (the primary, English-default target)
  ADDITIONALLY carries `TEXT_CONTINUE`="שלום" LOGICAL vs `TEXT_NEW_GAME`=VISUAL
  (bidi A/B pair), `TEXT_LOAD_GAME`="אבגד" (4-letter direction control),
  `TEXT_QUIT_GAME`=all 27 Hebrew letters (glyph coverage), and a punctuation/
  parens/digits/Latin-island paragraph in both LOGICAL (`LANGUAGE_ENGLISH`) and
  VISUAL (`TEXTLANGUAGE_TITLE`) on the language-settings screen. All verified
  by **reading BACK through the live toc's own `extract_asset()`** (never
  trusted from the just-written state): `span 0 1/1 · span 8 7/7 · span 152
  1/1 · font 135/135 Hebrew glyphs — all PASS`. Registry `TextLanguage` reset
  `19→1` before deploy. Revert: `python work/20_build_menu_proof.py --revert`
  (registry NOT auto-reverted — restore `19` by hand if needed).
- **NEXT — awaiting the user's ONE screenshot** (launch `Spider-Man.exe`,
  photograph the boot splash to see which marker won, then if `ZZ-SPAN8-…` as
  expected, the main menu + language screen). Then Phase 2: delegate the
  46,556-line corpus ([[delegate-all-translation]], New-Era panel free from
  the 22 sibling language variants already extracted) → build the confirmed
  bidi mode into the full patch → re-deploy via the same `msmr_deploy.apply()`
  → publish only on an explicit "פרסם" (GitHub `spiderman-remastered-hebrew-mods`
  + Worker slug + flip the existing `games` row `planned/locked`→`available`,
  price per [[mod-price-53-default]]).


