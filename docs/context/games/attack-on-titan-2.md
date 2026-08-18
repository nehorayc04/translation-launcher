## Attack on Titan 2 (A.O.T.2) Hebrew — ✅✅ PHASE 1 COMPLETE, every gate CLOSED except font (CONFIRMED missing via a real screenshot, not just theory) (2026-08-10, "דור 3")

New game at `games/attack_on_titan_2/` (`RECON.md`/`FEASIBILITY.md`/`PIPELINE.md` +
`tools/aot2_linkdata.py` + `work/{aot2_deploy,scope_report}.py`). Install
`F:\Games\Attack on Titan 2` (Koei Tecmo/Omega Force 2018, SteamEmu/SKIDROW crack,
`steam_api.ini` appid `601050`). **Container/text/repack/deploy pipeline fully solved
and PROVEN — a REAL Hebrew Options-screen translation (11 fields, a THIRD container
sub-format cracked to reach it — "group tables") was deployed and the user's own
screenshot confirmed: mount WORKS (correct char-counts render), but the font that
draws that screen has NO Hebrew glyphs — unmapped codepoints fall back to a literal
"?" per character. Two more font-container leads were then chased and conclusively
ruled out (an icon/sprite atlas, and a coincidental float-data false-positive) — the
actual glyph resource now resists THREE independent search methods. The story/battle
proof is still deployed to both archives and remains the one open question (may use
a different renderer than the Options screen).**
Memory [[aot2-groundwork-go]].

- **🔴 THE MAIN MENU / TITLE SCREEN IS TEXTURE-BAKED, NOT TRANSLATABLE TEXT —
  confirmed 2026-08-10 by exhaustive search, not "not found yet".** User's own
  screenshot showed the title menu still English ("עדיין אנגלית"). Found + fixed a
  **critical codec bug** first: `LinkData.read()` used a single-shot
  `zlib.decompress(raw[8:])`, which **silently TRUNCATES** any entry whose
  decompressed size exceeds 32768 bytes (Python's `zlib.decompress()` stops at the
  first embedded deflate stream and drops trailing bytes with NO error). Large
  entries actually store MULTIPLE independently-compressed 32768-byte blocks
  concatenated (block 1 starts right after the entry's 8-byte header; every later
  block is preceded by a 4-byte informational field then its own fresh zlib
  stream) — fixed via a shared `decompress_blocks()` now used by both
  `LinkData.read()` and `aot2_deploy.apply_edits()`. **The already-deployed proof
  (entries 2424/1056) was confirmed stored RAW (dsize=0) — never affected**, still
  reads back 12/12 correct after the fix; `scope_report.py`'s numbers came back
  byte-identical too (none of its counted tables exceed one block). A THIRD
  sub-format was also found along the way: some entries are a "group table"
  (`u32 count` + `count×u32` byte offsets into the same buffer, each pointing at
  an independent nested DataTable) rather than a flat DataTable.
  **With the codec fixed, searched EVERY text archive** (REGION EU/JP/AS + all 3
  Eden variants + D + EX_MASTER + PLATFORM_DX11 + PLATFORM_EDEN_DX11) for the
  EXACT 8 menu strings from the screenshot (Story Mode/Another Mode/Character
  Episode Mode/Territory Recovery Mode/Gallery/System/Exit/Manual). Every word
  exists in the text data, but ONLY inside unrelated contexts reusing the same
  vocabulary (an online-play mode-select dialog; the in-game Manual/help table of
  contents; a tutorial sentence *"select [h]New Game[/] from the [h]System[/]
  option on the Main Menu"* — proving those ARE real menu items, just not stored
  as standalone labels anywhere). `"System"`/`"Exit"` never occur standalone at
  all. Region archives have **0** raw G1T texture entries; `PLATFORM_DX11.BIN`
  (the real asset bundle) has **16**. Conclusion: the menu row is almost
  certainly pre-rendered per-language texture strips in the big asset bundles —
  same class of limitation as WD2's english-locked frontend / AC Unity's
  untranslatable menus, not a deploy bug, and out of scope to chase further
  (texture-atlas replacement is a different, much larger task than string
  patching). **The verdict is unchanged** — the two DYNAMIC-text surfaces
  (story-intro at entry 2424, mission popup at entry 1056) are unaffected and
  are the correct screens to actually verify Hebrew on; the main menu will
  always stay English via this pipeline.

- **🔴🔴 Round 3 (2026-08-10, user re-reported "still English" a 2nd time) — a
  STRUCTURAL exact-match scan (not substring), covering 2 archives round 2
  missed (`LINKDATA_DLC.BIN` 969MB, `LINKDATA_PATCH_000.BIN` 2.4GB), reaches the
  IDENTICAL conclusion on stronger footing.** Parsed EVERY entry in EVERY
  candidate archive as either a flat DataTable or a group table (recursing into
  nested tables), keeping only exact string-equality hits. Every hit anywhere
  lands in one of the same two contexts round 2 found (an online-lobby "Mode
  Selection" dropdown, or the Manual TOC) — never a standalone contiguous
  8-item list; DLC.BIN and PATCH_000.BIN both came back 0 exact hits.
  **Also closed a real uncertainty round 2 left open: which archive does
  "Final Battle" content actually load from?** `REGION_EDEN_EU.BIN` has a
  totally different entry count (1645 vs EU's 2438), so entry index 2424/1056
  in EU carries no guarantee of meaning anything there. Located the Eden
  equivalents by CONTENT match: entry **1639** contains the exact intro line
  `'That day, humanity remembered.'` (1458 strings, a superset of EU's 1034);
  entry **721** is one of hundreds of structurally-identical battle-text
  tables (EU's exact phrasing wasn't found verbatim in Eden, but the same
  template class is everywhere). Also found + fixed a real ambiguity in the
  battle-text proof: index 0 of every battle-text table is `'（通常）ENG'` —
  an internal category MARKER, not display text; the real instruction line is
  index 1, prefixed `'（指示）'` whose literal-vs-stripped rendering was
  unconfirmed. The widened proof now tests marker-slot, prefix-kept, and
  prefix-stripped all at once (`_battle_edits()` in `aot2_deploy.py`).
  **Deployed the SAME proof to `REGION_EDEN_EU.BIN` entries 1639/721 too**
  (distinct markers `ZZ-AOT2-EDEN-OK-ZZ`/`ZZ-BATTLE-EDEN-OK-ZZ` so the marker
  itself names which archive was actually read), verified 22/22 read-back
  correct + 0 collateral damage on both archives against fresh `.he_backup`
  copies.

- **🆕🆕 Round 4 (2026-08-10, user sent a THIRD report — this time a NEW screen:
  the Options/Settings menu, "Game 1" tab) — the Options screen is a REAL,
  large, translatable string bank, not texture-baked, and a THIRD container
  sub-format ("group tables") had to be cracked to reach it.** Some archive
  entries (incl. entry 0 in both REGION archives) are NOT a flat DataTable —
  they're a `u32 count` + `count×u32` BYTE OFFSETS array pointing at several
  INDEPENDENT nested DataTables inside the same entry (an online-lobby
  dropdown, a general Settings/Options UI bank, tab-header labels, the Manual
  TOC, etc. — 7 nested tables in EU's entry 0, 13 in Eden's). Read via
  `is_group_table()`/`parse_group_table()`; write via `encode_group_table()`
  — took 2 fix iterations to nail the exact layout: every nested group's
  start offset is **16-byte aligned** (zero-padded gap after each group's own
  content), AND the **whole buffer is ALSO padded to a 16-byte boundary at
  the very end** (missed on the first pass, output was consistently a few
  bytes short). Proven byte-identical round-trip on real archive data before
  any edit, per doctrine. `aot2_deploy.apply_edits()`/`verify()` now
  auto-dispatch per entry between the flat-table path (`{string_idx: value}`)
  and this new nested path (`{group_idx: {string_idx: value}}`) — no caller
  flag needed, `is_datatable()`/`is_group_table()` are mutually exclusive and
  self-detecting.
  **Located the Options screen's real string bank by EXACT match against
  every English label visible in the user's screenshot**: it's entry 0's
  group 0 — 674 strings in EU, **1083 in Eden** (the ~409 Eden-only extra
  fields match the richer "Final Battle" Options screen the user actually
  photographed — further evidence the running build reads UI text from Eden).
  Confirmed indices: Difficulty@0, Vibration@3, Gore Level@36, Voice Chat@377,
  Slow Motion During Battle@664 (both archives, identical index); Offline@675,
  Default Network Settings@785, Extra-wall Map Speed@1036, Skip Journey
  Events@1037, Control Assistance@1068 (Eden ONLY); Controls@4 of group 4
  (both archives, a tab-header label). Not yet found: 'Preferred Input
  Method', 'Game 1'/'Game 2' tab names, 'Camera', 'Audio', 'Graphics 1'/'2',
  'Keyboard and Mouse' — likely a different entry, deprioritized this round.
  **Deployed REAL Hebrew (not markers), alternating LOGICAL/VISUAL bidi per
  field** since this UI surface's bidi mode is independently unconfirmed —
  whichever pattern reads correctly on screen answers bidi mode for THIS
  surface too, while guaranteeing at least half the fields are legible either
  way: קושי(L)/רטט(V)/רמת אלימות(L)/צ'אט קולי(V)/תנועה איטית בקרב(L)/פקדים(L)
  in both archives, plus לא מקוון(V)/הגדרות רשת ברירת מחדל(L)/מהירות מפת
  חוץ-חומה(V)/דלג על אירועי מסע(L)/סיוע בשליטה(V) in Eden only. Verified
  11/11 read-back-correct in EACH archive + **0 collateral damage at
  FINE-GRAINED per-string granularity** inside entry 0 (1375 EU / 2822 Eden
  untouched strings byte-identical, on top of the usual whole-entry check —
  2435/2438 EU and 1642/1645 Eden untouched entries also byte-identical).
  `aot2_deploy.build_options_edits()` + `OPTIONS_GROUP0_SHARED` /
  `OPTIONS_GROUP0_EDEN_ONLY` / `OPTIONS_GROUP4`.

- **🆕🆕🆕 Round 5 (2026-08-10, same-day re-screenshot of the deployed Options screen) —
  MOUNT re-confirmed, FONT CONCLUSIVELY CONFIRMED MISSING for this renderer; two more
  font-container leads chased and ruled out, bringing independent negative confirmations
  to THREE.** Most edited fields rendered as strings of literal **"?" characters**
  matching the exact word/char-count of the Hebrew content — proof the engine reads +
  attempts to render our data character-by-character (a pre-baked/texture surface could
  never do this), with unmapped codepoints falling back to a real "?" glyph rather than
  an empty box. `Voice Chat`/`Preferred Input Method` stayed unedited English on screen —
  NOT a failed write (pre-flight + post-deploy read-back both confirmed the edit landed
  at the correct index) — most likely that on-screen row sources a DIFFERENT string index
  via a separate tab-layout table; not chased further (deprioritized vs the font finding).
  **Two more font leads, both fully investigated:**
  1. **"KSLT" (`TLSK` on disk, Cethleann's "KTGL Screen Layout Texture" `.kslt`)** — found
     by extending the raw byte-level `grep -a -o -b` method to the huge asset bundles
     (`LINKDATA_A.BIN` 5.8GB / `B.BIN` 7.2GB / `C.BIN` 2.3GB, never scanned this deeply —
     a whole-file grep is cheap/safe even at multi-GB scale and its offsets map straight to
     a TOC entry with no in-memory load of the full file). One clean hit (`A.BIN` entry
     3196, magic at byte 0 of a stored 132,160-byte entry) parsed exactly per Cethleann's
     struct layout with every internal cross-check consistent (`PointerTablePointer=560`
     == `Count(10)×56`; image `Size=131072` == `512×256` BC3 bytes exactly). Its one
     embedded name is **`pad_cmn_menu_l1`**, and all 10 of its texture entries point at
     ONE shared 512×256 BC3 image — decoded (wrapped in a minimal DDS header, opened via
     Pillow) and **visually confirmed to be 10 left/right scroll-arrow icons**, matching
     the `◄`/`►` tab-scroll chevrons on the Options screen's own tab bar. **Icon/sprite
     atlas, unrelated to text glyphs — ruled out.**
  2. **`Font2`/`.g1n`** — Cethleann's own `DataType.cs` enum EXPLICITLY documents a "KTGL
     Font" container (magic `_N1G` on disk). Grepped it across EVERY LINKDATA archive:
     4 hits (`A.BIN`×1, `B.BIN`×2, `PATCH_000.BIN`×1). The 2 `B.BIN` hits sit inside
     COMPRESSED entries (disregarded — a literal-ASCII match inside zlib data is never
     real). The 2 stored hits (`A.BIN` entry 12862, `PATCH_000.BIN` entry 2266) were
     extracted directly: **both entries actually begin with an unrelated magic (`FP1G`),
     and the font-magic bytes sit deep inside a long run of values that decode cleanly as
     IEEE-754 float32s in the 30,000–90,000 range** (almost certainly world-space/spatial
     coordinate data) — `_N1G` occurring by pure coincidence. **This is the EXACT SAME
     false-positive class already on record from the ORIGINAL pre-session font search**
     ("coincidental float32 vertex/skeleton data"), now independently re-derived via a
     completely different discovery method (the DataType enum + a fresh full-archive
     grep, vs the earlier ad-hoc sfnt/FourCC scan) — strengthens rather than merely
     repeats the earlier conclusion. **Ruled out.**
  **Per project doctrine, once static RE is genuinely exhausted (now 3 independent
  methods, all negative) a deployed screenshot is the correct next instrument — and it
  was just used, delivering a clear answer FOR THE OPTIONS SCREEN specifically.** This is
  NOT necessarily true engine-wide: the story/battle proof (still deployed) may route
  through a genuinely different text renderer than menu/HUD UI (a common split across game
  engines), so it remains a real, independent, still-open question — the ORIGINAL,
  still-unfulfilled ask.
- **🆕🆕🆕🆕 Round 6 (2026-08-10, same day — user asked to inject a Hebrew font BEFORE
  anything else) — THREE more independent methods, all still negative, plus one decisive
  orthogonal ruling.** (1) EXE/DLL font resources checked for the FIRST time: `pefile` scan
  of all 4 shipped exes for `RT_FONT`/`RT_FONTDIR` + a raw sfnt-magic scan with a properly
  STRICT validator (a first attempt using `fontTools(lazy=True)` falsely "validated" raw x86
  machine code as fonts — `\x00\x01\x00\x00` is a common compiled-code immediate; the fix
  checks the real sfnt table-directory invariants: numTables/searchRange/entrySelector/
  rangeShift mutually consistent, every tag 4 printable ASCII chars, every offset in-bounds)
  → **zero** hits, **zero** RT_FONT resources, across all 4 binaries. (2) The REAL
  `DataType.cs` re-fetched (true path `Cethleann.Structure/DataType.cs` on `develop` — NOT
  `Cethleann/DataType.cs` on `master`, which 404s) and read in full (95 members): surfaces
  one more untried magic, `ScreenLayout`/KSCL (`LCSK` on disk, distinct from the
  already-ruled-out KSLT) — but it has **NO reference reader anywhere in Cethleann**
  (declared, never implemented) → not pursued given a stronger lead. (3) **A real G1T
  (TextureGroup) decoder built from scratch** (no G1T tooling existed in this project
  before — the earlier "large G1T textures inspected" claim was evidently done by a cruder
  method blind to sub-textures packed inside a bundle). Struct layout fetched fresh from
  `Cethleann/Graphics/G1TextureGroup.cs` + 7 supporting structs; scanned **2,756 textures**
  across 4 archives + **777 more** across the JP/AS region archives, sorted BOTH ascending
  (compact glyph-atlas candidates, never checked before) and descending (CJK-atlas
  candidates — the game ships JP/KO/CN, so a real CJK glyph source must exist somewhere).
  The single strongest candidate in 5 rounds — `LINKDATA_PLATFORM_DX11.BIN` entry 195, 150×
  256×256 BC1 textures bundled together — decoded (DDS-wrap + Pillow, the proven KSLT
  technique) to a **tileable cloth-weave normal map** (blue-purple tangent-space colour
  signature), part of an 8-entry PBR material cluster (normal/gradient-mask/colour-ramp-LUT)
  for 3D rendering — not text. Three more small uncompressed R8G8B8A8 candidates decoded to
  a cloth albedo, a light-streak mask, and a radial LUT. The largest textures everywhere are
  ordinary BC5/BC1/`0x5f` world textures. **No glyph-atlas signature anywhere.** (4) **The
  exe's PE import table settles a real alternative hypothesis**: `GDI32.dll` has exactly 1
  import (not text-drawing), **zero** `dwrite.dll`, **zero** `usp10.dll` (Uniscribe) — with
  `d3d11.dll`/`dxgi.dll` present, this **rules out** "the game defers to a Windows system
  font, and the '?' is a codepage/`WideCharToMultiByte`-style lossy-conversion artifact" —
  the game does 100% custom D3D11 text rendering, which *reinforces* the font-gate diagnosis
  (a real glyph source categorically must exist, since it renders thousands of real CJK
  glyphs for the shipped localizations) while still not revealing WHERE. **Verdict: after
  FIVE independent, non-overlapping static-analysis methods, a literal font-injection step
  still cannot be performed — no container has been found.** Two responsible ways forward:
  a live-process-memory investigation (per `reverse-engineer-container`'s own fallback
  guidance, untried), or widening the G1T scan to the still-unscanned multi-GB
  `LINKDATA_A/B/C/D.BIN` (the round-5 icon atlas was found precisely this way). Tools:
  `games/attack_on_titan_2/work/{scan_exe_fonts2,scan_g1t_small,decode_g1t_195}.py`.

- **🟢 Container = `LINKDATA_*.BIN`, magic `0x00077DF9` — CRACKED via REUSING two
  public tools** ([[check-public-format-first]]/[[engine-family-reuse-check-magic]]):
  `the-real-thunderlol/AOT2-MODDING-TOOLKIT` (AoT2 field layout) cross-validated
  against `neptuwunium/Cethleann`'s authoritative C# `LINKDATA.cs`/`Leonhart.cs` (the
  general Koei Tecmo "KTGL" engine-family reader — same format across several Koei
  Tecmo titles, not AoT2-only). Header `u32 magic·count·offset_multiplier·pad` +
  16-byte entries `offset_sectors·pad·compressed_size·decompressed_size`.
  **`offset_multiplier=256` for every AoT2 archive** (NOT the older sibling title's
  2048 — proven via `max(offset*256+csize)==filesize` exactly, zero overflow).
  `decompressed_size=0`→stored raw; else zlib with an 8-byte custom header (the 2nd
  field is informational, `zlib.decompress(raw[8:])` alone decodes it).
- **🟢 Text = the engine-wide "DataTable" flat string format, CRACKED + round-trip
  PROVEN byte-identical.** `count`→`count×{offset,size}`→packed NUL-terminated UTF-8
  blobs. `is_datatable()` = Cethleann's own heuristic (`first.offset == 4+count*8`,
  unaligned or 16-aligned). `encode_datatable()` reproduces the exact original bytes
  on a re-encode with no changes — the identity-round-trip proof required before any
  edit, per the groundwork skill.
- **🔴 NO Arabic locale anywhere** (checked EU/JP/AS + all 3 EDEN variants) →
  **LTR-slot (English) hijack**. `steam_api.ini [GameSettings] Language=english` is
  the crack's own DEFAULT → **zero user action** to land on the hijacked slot. bidi
  storage mode (LOGICAL+RLM/VISUAL/force-RTL-base) is decided by the deployed proof,
  never assumed.
- **🟢 Deploy = append-relocate** (never a full re-pack): decode→edit→re-encode
  (stored uncompressed)→append at EOF (256-byte sector-aligned)→patch ONLY that
  entry's 16-byte TOC record in place. **Validated TWICE**: a 291MB scratch copy
  (0/2436 untouched entries changed) AND the REAL deployed archive (0/2436 changed,
  re-verified against the auto-created `.he_backup`).
- **🟡 Font gate — OPEN, deliberately deferred to the screenshot** (per this
  project's own precedent: a fully-solved text pipeline doesn't guarantee font
  coverage, AND when font remains elusive after due diligence the deployed
  screenshot is a faster/more conclusive instrument than continued blind RE).
  Extensive multi-method search (container-magic scan of every archive incl.
  full-buffer, ASCII `"font"` string scan, a derived FourCC-reversal candidate,
  fontTools-validated sfnt scanning, visual G1T-texture inspection) found **0
  positively-identified font/glyph container** — every candidate hit was confirmed
  a false positive (coincidental float32 vertex/skeleton data). The proof's 27-letter
  alphabet string will show clean glyphs or tofu on the user's screenshot.
- **🟢 DRM — clean.** SteamEmu/SKIDROW, single-player, 0 Denuvo/EAC/BattlEye/
  VMProtect strings; no content-hash integrity wall (append-relocate write loaded +
  read back clean).
- **✅✅ THE PROOF — DEPLOYED to BOTH `LINKDATA\REGION\LINKDATA_REGION_EU.BIN`**
  (entry 2424 = story-intro, entry 1056 = battle-text) **AND
  `LINKDATA_REGION_EDEN_EU.BIN`** (entry 1639 = story-intro equivalent, entry 721
  = battle-text equivalent, found by content-match since Eden's entry indexing is
  completely different): `ZZ-AOT2-OK-ZZ`/`ZZ-BATTLE-OK-ZZ` vs the `...-EDEN-...`
  variants (mount, font-independent, AND names which archive the build reads) ·
  `שלום` LOGICAL vs `םולש` VISUAL (bidi mode) · all 27 Hebrew letters (glyph
  coverage/tofu) · a punctuation/parens/digit/NVIDIA-Latin-island paragraph in both
  modes (layout) · `אבגד`/`דגבא` control pair · battle-text tables ALSO test the
  marker-slot vs real-instruction-slot vs `（指示）`-prefix ambiguity. Verified by
  reading every patched string back OUT of the live files on disk — 22/22 correct,
  0 collateral damage on either archive. Revert:
  `python games/attack_on_titan_2/work/aot2_deploy.py --revert`.
- **📊 Scope report** (`work/scope_report.py`, classifies by the engine's own
  table-size convention: 20-450 strings/table = battle text, >450 = story/dialogue):
  **battle 357,830 records / 25,851 GLOBAL uniques · story 60,655 records / 54,670
  GLOBAL uniques · cross-archive TOTAL 64,685 unique strings** (EU+JP+AS). UI/menu
  chrome (New Game/Continue/Options/Save labels) was searched for extensively and
  **NOT located** — scope is honestly limited to what's confirmed reachable
  (battle+story), which the deployed proof already exercises. Eden/Final-Battle
  archives (`REGION_EDEN_*`) not yet scoped — trivial follow-up, same format.
  New-Era panel is rich: EU carries separate EN/FR/DE/ES-ES/ES-MX/IT tables + JP/AS.
- **NEXT (Phase 2, gated on the user's screenshots + an explicit "פרסם"):**
  TWO screenshots would now close every remaining question at once —
  (1) the SAME Options screen the user already showed, now carrying real
  Hebrew (קושי/רטט/רמת אלימות/צ'אט קולי/תנועה איטית בקרב/פקדים, plus the
  5 Eden-only fields if that's the archive in play) → answers bidi mode +
  font coverage for the UI surface on a screen the user is ALREADY looking
  at, no extra navigation needed; (2) Story Mode's opening narration or a
  mission-start popup (the original, still-unfulfilled ask — both reports so
  far were menu/settings, not story/battle) → answers bidi mode + which
  archive [EU vs Eden] for the DYNAMIC-text surfaces via which marker shows.
  The main menu itself answers nothing, don't re-chase it (texture-baked,
  confirmed by two independent exhaustive searches). Once bidi mode is
  confirmed on at least one surface → very likely applies engine-wide →
  delegate the ~64,685-string (+ Options UI banks) translation to agents/a
  fleet ([[delegate-all-translation]]) → build via `encode_datatable`/
  `encode_group_table` + the confirmed bidi transform → deploy via the same
  `apply_edits` → publish only on "פרסם" (GitHub release repo + Worker slug +
  Supabase `games` row + `mod_version_history`).


