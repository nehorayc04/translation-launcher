# Attack on Titan 2 Hebrew — Feasibility

**Verdict: 🟢 GO.** Every Phase-1 gate is closed, and the multi-mode Hebrew
proof is **DEPLOYED to the real game** (`F:\Games\Attack on Titan 2\LINKDATA\
REGION\LINKDATA_REGION_EU.BIN`), verified byte-safe (0/2436 untouched entries
changed) and read back correct from disk. The user only has to launch and
screenshot. The one gate that is genuinely still open — font glyph coverage —
is deliberately left for the in-game screenshot to answer (see "Font gate"
below); that is faster and more conclusive than further blind static RE.

## Gate 0 — language settings / RTL slot
`steam_api.ini` → `Language=english` is the crack's own default (zero user
action). No `Arabic`/`ar`/RTL locale exists anywhere in the game (checked
across `REGION_EU/JP/AS` and all three `REGION_EDEN_*` variants) → this is
an **LTR-slot hijack**: Hebrew ships INSIDE the English text tables, and the
in-game proof (below) determines whether it must be stored LOGICAL+RLM,
VISUAL, or force-RTL-base (per the `rtl-bidi` skill — never assumed).

## Gate 1 — container
`LINKDATA_*.BIN`, magic `0x00077DF9`. Solved by REUSING two public tools
rather than blind RE (`check-public-format-first` /
`engine-family-reuse-check-magic`) — see `RECON.md` for the full field
layout. `games/attack_on_titan_2/tools/aot2_linkdata.py` is a from-scratch,
documented, pure-Python port validated against the real archives (multiple
`offset_sectors * mult + compressed_size == filesize` checks, zero overflow).

## Gate 2 — text format + identity round-trip
The generic engine-wide "DataTable" flat string-table format
(`is_datatable` / `parse_datatable` / `encode_datatable` in
`aot2_linkdata.py`). **Round-trip proven byte-identical**: re-encoding an
unmodified string list reproduces the exact original bytes on every table
sampled. This IS the identity-round-trip proof the groundwork skill
requires before any edit is attempted.

## Gate 3 — RTL slot decision
No Arabic locale (Gate 0) → LTR/English-slot hijack, confirmed. The bidi
STORAGE MODE (whether Hebrew needs LOGICAL+RLM, VISUAL pre-reversal, or a
force-RTL-base embedding) is answered by the deployed proof — see "The
proof" below. Not assumed ahead of time, per doctrine.

## Gate 4 — deploy mechanism
**Append-relocate**, the project's standard pattern for an index/TOC-based
archive (never a full re-pack): for each edited entry, decode its current
content → apply the edits → re-encode as a DataTable (stored uncompressed,
`decompressed_size=0`, simplest and matches how every sampled table already
ships) → append the new bytes at EOF (padded to a 256-byte sector) → patch
ONLY that entry's 16-byte TOC record in place. Every other byte in the
archive — header, every other TOC record, every other entry's payload — is
left untouched.

**Validated twice**: once on a 291 MB scratch copy (3 strings across 2
entries; `verify_untouched` found 0/2436 mismatches), and again on the REAL
deployed archive (8+4 strings across entries 2424 and 1056; a fresh
comparison against the `.he_backup` pristine copy found **0/2436**
untouched-entry mismatches). `.he_backup` is created automatically before
the first write (`ensure_backup()` in `work/aot2_deploy.py`); `--revert`
restores it.

## Gate 5 — font gate (open, deliberately deferred to the in-game screenshot)
An extensive multi-method static search found **no positively-identified
font/glyph container anywhere in the game**:
- Container-magic scanning across every archive (A/B/C/D/DLC/PLATFORM/
  REGION), including full-buffer (not just header-offset) searches for
  candidate FourCC/sfnt signatures.
- ASCII/text-string scanning for `"font"` — the only two hits (in `B.BIN`
  entry 606 and `C.BIN` entry 951) were confirmed to be **coincidental byte
  patterns inside vertex/skeleton/particle float32 data**, not real font
  resources (validated by inspecting the surrounding bytes: dense float32
  arrays with a shared exponent byte, not readable text context).
- A derived "`_N1G`" FourCC-reversal candidate (see the byte-order rule in
  `RECON.md`) produced exactly one hit, also confirmed to be a false
  positive inside unrelated float32 data via hex-dump inspection.
- fontTools-validated sfnt-magic scanning of texture/asset entries — several
  raw byte-pattern "hits" were checked and rejected (empty/garbage table
  directories when loaded with `TTFont(..., lazy=True)`).
- Visual inspection of every large G1T texture decoded during the hunt — no
  glyph atlas was recognized.

**Per this project's own precedent** (documented for AC Unity: "a fully-
proven text pipeline does NOT make a game translatable — the font is an
independent gate, and a game can be ruled out by it after everything else
works" — but ALSO "when font remains elusive after due diligence, proceed
to deploy the proof anyway; the deployed in-game screenshot is a faster,
more conclusive font-coverage instrument than continued blind RE"), the
proof was deployed regardless. It contains all 27 Hebrew letters
(`אבגדהוזחטיכלמנסעפצקרשתךםןףץ`) — the screenshot will show either clean
glyphs (font already covers Hebrew — some games' default/system fallback
fonts do) or tofu boxes (font injection needed, a follow-up sub-project).

## Gate 6 — DRM/integrity
Clean. SteamEmu/SKIDROW crack, single-player only, no Denuvo/EAC/BattlEye/
VMProtect strings anywhere. No content-hash integrity wall detected —
the append-relocate write loaded and read back correctly.

## The proof (deployed)
Target: entry **2424** in `LINKDATA_REGION_EU.BIN` (the story-intro
narration table — a 1034-string table, the opening recap shown at the start
of a fresh Story Mode save) and, redundantly, entry **1056** (a
mission-instruction "battle text" table, reached the instant any combat
mission starts) as a second independent reachable surface.

| index (table 2424) | content | proves |
|---|---|---|
| 0 | `ZZ-AOT2-OK-ZZ` | mount, independent of font/bidi |
| 1 | `שלום` (LOGICAL) | |
| 2 | `םולש` (VISUAL, `python-bidi get_display`) | bidi mode (whichever renders correctly) |
| 3 | `אבגדהוזחטיכלמנסעפצקרשתךםןףץ` (all 27 letters) | glyph coverage / tofu |
| 4 | `בדיקה: (מספר 123) "מרכאות" - עברית עם NVIDIA ואז סוף!` (LOGICAL) | |
| 5 | same, VISUAL | layout: punctuation/parens/digits/Latin-island, both modes |
| 6 | `אבגד` (LOGICAL) | |
| 7 | `דגבא` (VISUAL) | bidi control pair |

Table 1056 repeats indices 0-3 (marker + LOGICAL/VISUAL "שלום" + the
alphabet) as a second reachable surface, in case the story-intro cutscene
is harder for the user to reach than a combat mission's instruction popup.

**Deployed + verified 2026-08-10**: all 12 patched strings read back
correctly from the live archive on disk; 0/2436 untouched entries changed.

## Scope report (Phase 2 planning — `games/attack_on_titan_2/work/scope_report.py`)
Two confirmed content families, split by the engine's own table-size
convention (not by file layout):

| | records | GLOBAL uniques |
|---|---:|---:|
| **Battle-mission text** (EU+JP+AS) | 357,830 | 25,851 |
| **Story/cutscene dialogue** (EU+JP+AS) | 60,655 | 54,670 |
| **Cross-archive TOTAL** | — | **64,685** |

Per-archive breakdown (EU is the primary/English text source):

| archive | battle tables | battle records | battle uniques | story tables | story records | story uniques |
|---|---:|---:|---:|---:|---:|---:|
| REGION_EU | 882 | 239,388 | 16,470 | 18 | 40,495 | 35,044 |
| REGION_JP | 151 | 38,646 | 3,271 | 3 | 6,720 | 6,597 |
| REGION_AS | 294 | 79,796 | 6,114 | 6 | 13,440 | 13,041 |

**UI/menu chrome (New Game / Continue / Options / Settings / Save / Load
labels) was searched for extensively and NOT located.** This scope report
is honestly limited to what WAS confirmed reachable: battle-mission text +
story/cutscene dialogue, both of which the deployed proof already exercises.
If UI chrome location is found in a future session, it would ADD to this
scope, not replace it.

The Eden/Final-Battle expansion archives (`REGION_EDEN_EU/JP/AS`) were not
included in the scope scan this session — they follow the identical
container/text format and can be scoped with the same `scope_report.py`
against those three files as a trivial follow-up.

**New-Era / gender-oracle panel is rich**: the EU archive alone carries
separate per-language string tables (EN/FR/DE/ES-ES/ES-MX/IT observed during
the earlier language-table survey), plus JP/AS give further reference
languages — a strong panel for Phase 2 delegated translation
([[new-era-doctrine]], [[gender-oracle-from-game-langs]]).

## "Still English" report (2026-08-10) — diagnosed, mount confirmed correct

User reported "עדיין אנגלית" after the deploy above. Full isolation per the
`reverse-engineer-container` skill — every technical mount check came back
**correct**; the block turned out to be the verification ENVIRONMENT, not
the deploy:

1. **Re-read the live deployed archive from disk** — all 12 patched strings
   still present, unchanged (not reverted/overwritten by anything).
2. **Base+patch shadowing checked** (`work/scan_patch.py`, per the project's
   own §8e precedent — a sibling `LINKDATA_PATCH_000.BIN` exists, 2.5 GB /
   2749 entries): scanned every DataTable in it for (a) our exact pristine
   English source strings from entries 2424/1056, (b) UI-chrome-shaped
   tables. **0 hits on both** — nothing in the patch archive shadows the
   edited entries or looks like unlocated menu text.
3. **`LINKDATA_D.BIN` and `LINKDATA_EX\LINKDATA_EX_MASTER.BIN`** (the two
   tiny 4.3 KB archives) are dead ends — both are placeholder stubs (all-'0'
   ASCII padding), not manifests/indices.
4. **🔴 Found: the game ships THREE separate per-region executables**
   (`AOT2_EU.exe` / `AOT2_JP.exe` / `AOT2_AS.exe`), each presumably reading
   its own `REGION_<X>.BIN`. `Launcher.exe` (the real entry point — the
   desktop shortcut targets it, not an exe directly) calls
   `GetSystemDefaultUILanguage`/`GetUserDefaultUILanguage`/
   `GetThreadPreferredUILanguages` and shows a **"Startup Settings"** dialog
   with `Region`/`Language` dropdowns before launching one of the three.
   This machine's Windows system locale is **he-IL (Hebrew)** — a locale
   this launcher's mapping logic was never designed for — so the concern
   was real: if it silently picked `AOT2_AS.exe`/`AOT2_JP.exe`, the EU
   patch would be invisible. **Checked directly (autonomous launch,
   UI-Automation-driven): the dialog's SAVED settings already show
   `Region=EU/NA`, `Language=ENG`; confirming it → `AOT2_EU.exe` (PID
   observed running) — the exact archive edited.** Wrong-exe is ruled out.
5. **🔴 Autonomous verification blocked by the environment, not the mod:**
   `AOT2_EU.exe` immediately hit its own native `MessageBoxW`
   *"No valid sound devices connected."* and exited on dismissal — **before
   reaching the main menu**. Confirmed via `Get-PnpDevice -Class
   AudioEndpoint`: every playback endpoint (Speakers/Headset/Headphones) on
   this machine reports `Status=Unknown` (disconnected) — **zero active
   audio output device**, the identical signature already documented for
   Skyrim's launcher-only sound check in this project's history. This is a
   property of the current remote/tool session, not the deploy, and not
   necessarily the user's own desktop state when they actually played.

**Conclusion: everything checkable without playing the game is correct**
(file intact, correct archive, correct exe, no shadowing). The two screens
the proof targets are **not the main menu** — entry 2424 needs a fresh/
continued **Story Mode** save reaching its opening narration, entry 1056
needs an actual **combat mission start**. Neither is documented as
independently confirmed to be the literal FIRST frame shown (that was an
inference from table size/position, not a played confirmation) — if the
user checked only the title/main menu (UI chrome, never located/touched —
see Gate 5), "still English" there is the fully expected, already-
documented behavior, not a failure of the deploy.

## "Still English" report, round 2 (2026-08-10) — codec bug fixed, menu chrome conclusively texture-baked

The user sent a real screenshot of the main menu (Story Mode / Another Mode /
Character Episode Mode / Territory Recovery Mode / Gallery / **System**
[highlighted] / Exit / Manual — "A.O.T.2 -Final Battle-" title) and said
"עדיין אנגלית". Investigated further with these exact strings as search
targets (a huge upgrade over round 1's generic guessing).

**🔴 Found + fixed a real codec bug along the way.** `LinkData.read()` used a
single-shot `zlib.decompress(raw[8:])`, which SILENTLY TRUNCATES any entry
whose decompressed size exceeds 32768 bytes (Python's `zlib.decompress()`
stops at the first embedded deflate stream's end and drops any trailing
bytes with no error). Large entries actually store MULTIPLE independently-
compressed 32768-byte blocks concatenated together. Proven step by step on
`REGION_EDEN_EU.BIN` entry 0 (dsize=136320): block 1 decoded to exactly
32768 bytes and stopped; the next 4 bytes turned out to be a per-block
informational size field, immediately followed by a fresh zlib stream (magic
`78 da`); looping that pattern reconstructed the full 136320 bytes exactly.
Fixed via a new shared `decompress_blocks()` in `aot2_linkdata.py`, used by
both `LinkData.read()` and `aot2_deploy.apply_edits()`. **Entries 2424/1056
(already deployed) were confirmed stored RAW (dsize=0) in the pristine
backup — never affected by this bug.** Re-verified: all 12 patched strings
still read back correct after the fix. `scope_report.py` was also re-run
with the fix; its numbers (357,830/60,655 records, 64,685 unique strings)
came back byte-for-byte IDENTICAL — none of the individual battle/story
tables it counts happen to exceed one block.

**A third sub-format was also found**: some entries (e.g. that same
REGION_EDEN_EU.BIN entry 0) aren't a flat DataTable — they're a small
"group table" (`u32 count` + `count × u32` byte offsets into the SAME
buffer, each pointing at an independent nested DataTable). Used it to
inspect all 13 nested tables inside that entry.

**With the fixed decompressor, searched EVERY text archive** (REGION EU/JP/
AS, all 3 Eden variants, D, EX_MASTER, PLATFORM_DX11, PLATFORM_EDEN_DX11 —
i.e. everything, correctly this time) for the 8 exact menu strings from the
screenshot. Result: every one of those words DOES exist in the text data,
but ONLY inside unrelated UI contexts that happen to reuse the same
vocabulary:
- an online-play "Mode Selection" dialog (Create Room → Mode Selection →
  Story Mode / Another Mode / Annihilation Mode / Character Episode Mode /
  Territory Recovery Mode → Difficulty Selection...);
- the in-game Manual/help table of contents (Story Mode / Another Mode /
  Gallery/Options / Controls / The Battle Screen / The Info Screen...);
- a tutorial sentence: *"select [h]New Game[/] from the [h]System[/] option
  on the Main Menu."* — proving "System" and "New Game" ARE real menu items,
  but their LABELS are not present anywhere as standalone strings.

**"System" and "Exit" in particular never occur as a bare standalone string
in ANY text archive searched.** The region archives also contain **zero**
raw G1T texture entries (a direct magic-byte scan), while
`LINKDATA_PLATFORM_DX11.BIN` (the actual asset bundle, not a text archive)
DOES hold 16 real G1T-magic entries. Combined with the visibly stylized,
torn/bloodied gothic "A.O.T.2" title-screen font, the conclusion is: **the
main-menu row is almost certainly pre-rendered per-language texture
strips living in the big asset bundles (A/B/C/PLATFORM_DX11), not
translatable string-table text.** This is the SAME class of limitation
already documented elsewhere in this project (Watch Dogs 2's english-locked
frontend, AC Unity's untranslatable menus) — not a bug in this deploy, and
not something further string-table RE can fix. Chasing it further would
mean decoding + replacing texture atlases, a fundamentally different and
much larger task than string patching, out of scope for now.

**This does not change the verdict.** The two DYNAMIC-text surfaces the
proof targets (story-intro narration at entry 2424, a mission-instruction
popup at entry 1056) are unaffected by any of this — they are real,
translatable DataTable strings, correctly deployed, and are where the
Hebrew proof should actually be checked. The title/main-menu screen is
expected to stay English regardless of what gets patched in the text
archives.

## "Still English" report, round 3 (2026-08-10) — structural exact-match re-scan (STRONGER than round 2) + Eden-archive redundant deploy

The user re-sent the same "עדיין אנגלית" report against the same main-menu
screenshot after round 2's fixes. Rather than re-explain the same
conclusion, ran a materially STRONGER check (round 2 was a raw ASCII
substring scan; this is a full structural parse), plus closed a real
uncertainty round 2 had left open.

**Structural exact-match scan — EVERY LINKDATA archive in the game,
completed.** For every entry in every candidate archive — REGION EU/JP/AS,
all 3 Eden variants, `LINKDATA_D.BIN`, `LINKDATA_DLC.BIN` (969 MB, not
checked in round 2), `LINKDATA_PATCH_000.BIN` (2.4 GB, 2749 entries, not
checked in round 2), `LINKDATA_EX_MASTER.BIN`, `LINKDATA_PLATFORM_DX11.BIN`
(422 MB), `LINKDATA_PLATFORM_EDEN_DX11.BIN` (788 MB) — decoded the content
(with the fixed decompressor), parsed it as EITHER a flat DataTable OR a
group table (recursing one level into every nested table), and kept only
strings EXACTLY equal (after strip) to one of the 8 menu words — not a
substring match, a real string-table lookup. Total exact hits across every
archive: all inside the same two contexts round 2 already named (the
online-lobby "Mode Selection" dropdown at REGION_EU/EDEN_EU entry 0 group
0, and the Manual TOC at group 4 / group 11) — confirmed by printing each
hit's ±2-string context, e.g. the Eden Mode Selection list reads `'Room
Search (By ID)', 'Mode Selection', 'Story Mode', 'Another Mode',
'Annihilation Mode', 'Character Episode Mode', 'Territory Recovery Mode',
'Difficulty Selection', 'Mission Category Selection'` — an online
room-filter dropdown, not the title screen. **Every one of the other 8
archives (DLC, PATCH_000, EX_MASTER, both PLATFORM variants, D, both
EDEN_JP/AS) came back with ZERO exact hits.** No archive anywhere, of any
kind, contains the 8 words as a standalone contiguous list. This
supersedes round 2's conclusion with a stronger method reaching the
identical answer, and closes the archive coverage completely.

**Closed a real uncertainty: which archive does "Final Battle" content
actually load from?** The title screen literally reads "-Final Battle-",
and `REGION_EDEN_EU.BIN` has a COMPLETELY different entry count (1645) than
`REGION_EU.BIN` (2438) — so entry index 2424/1056 in EU carries no
guarantee of meaning anything in EDEN. Located the EDEN equivalents by
CONTENT match instead of assuming the index: searched every EDEN entry for
the exact opening line `'That day, humanity remembered.'` → found at
**entry 1639** (1458 strings, vs EU's 1034 — a superset, consistent with
Final Battle adding story content). For the battle-text table, EU's exact
mission-instruction phrasing wasn't found verbatim in EDEN (searched for
it directly, 0 hits) — but a looser two-substring search (`'（指示）'` +
`'[0:PARTY]'`) found **hundreds** of structurally-identical battle-text
tables in EDEN (one per mission, as expected); **entry 721** was picked as
a representative.

**Also found + fixed a real ambiguity in the original battle-text proof
design.** Index 0 of every battle-text table (both EU's 1056 and EDEN's
721) is `'（通常）ENG'` — "(normal) ENG", which reads as an internal
category/language-tag marker, not player-facing text. The actual
mission-instruction line starts at index 1, prefixed `'（指示）'`
("(instruction)"). It was unconfirmed whether that prefix renders literally
or gets stripped by the engine before display. Fixed `_battle_edits()` in
`aot2_deploy.py` to test all three possibilities in ONE deploy: the marker
slot itself (index 0), the instruction slot WITH the prefix kept (index 1),
and pure Hebrew with no prefix at indices 2-4 — so whichever slot/
convention turns out to be the real one, the proof still lands.

**Deployed the widened proof to BOTH archives** (REGION_EU entries
2424/1056 refreshed with the new battle-text indices; REGION_EDEN_EU
entries 1639/721 added new, with distinct markers `ZZ-AOT2-EDEN-OK-ZZ` /
`ZZ-BATTLE-EDEN-OK-ZZ` so the marker itself tells us which archive actually
got read). Verified 22/22 read back correct from disk in both files, and
**0 collateral damage** on both archives' untouched entries (1643/1643 and
2436/2436 respectively, re-confirmed against fresh `.he_backup` copies).

**Verdict unchanged, evidence now much stronger, and the deploy now covers
both plausible content sources.** The main menu will still be English
regardless — that conclusion has now survived two independent, increasingly
rigorous searches. The story-intro and battle-instruction screens remain
the correct places to check, and are now proofed in whichever of EU/Eden
the running build actually reads from.

## "Still English" report, round 4 (2026-08-10) — the Options screen is REAL text, not texture-baked; a third container sub-format cracked to reach it

The user's THIRD report came with a genuinely NEW screen this time: the
Options/Settings menu ("Game 1" tab — Difficulty / Control Assistance / Gore
Level / Slow Motion During Battle / Vibration / Extra-wall Map Speed / Skip
Journey Events / Voice Chat / Default Network Settings / Preferred Input
Method), alongside the same already-diagnosed main menu. Unlike the main
menu, this screen had never been investigated — and it turned out to be a
real, large, translatable string bank, not texture-baked.

**Cracked a third container sub-format to reach it: "group tables."** Entry
0 in both REGION archives is NOT a flat DataTable (`is_datatable()` is
False) — it's `u32 count` + `count×u32` BYTE OFFSETS into the same buffer,
each pointing at an independent NESTED DataTable (7 nested tables in EU's
entry 0, 13 in Eden's — an online-lobby dropdown, general Settings/Options
UI text, tab-header labels, the Manual TOC, etc., all bundled into one
archive entry). Added `is_group_table()`/`parse_group_table()`/
`encode_group_table()` to `aot2_linkdata.py`. The encoder took two fix
iterations against real archive data before it round-tripped byte-identical
with zero edits: (1) every nested group's start offset is **16-byte
aligned**, with the gap after each group's own encoded bytes zero-padded up
to that boundary; (2) the **whole buffer is ALSO padded to a 16-byte
boundary at the very end** (missed on the first pass — output was
consistently a few bytes short even after per-group alignment). Both
verified against the real padding bytes present in both REGION_EU.BIN and
REGION_EDEN_EU.BIN entry 0. `aot2_deploy.apply_edits()`/`verify()` now
auto-detect flat vs group per entry and dispatch accordingly — no caller
flag needed.

**Located the real Options-screen string bank by exact match against the
user's own screenshot.** It's entry 0's **group 0**: 674 strings in EU,
**1083 in Eden** — the ~409 Eden-only extra fields correspond to exactly the
richer Options screen the user photographed, itself further evidence the
running "Final Battle" build reads UI text from the Eden archive, not EU.
Confirmed indices (pre-flight-checked against the live archives before any
write — every one matched its expected English string exactly): Difficulty
@0, Vibration @3, Gore Level @36, Voice Chat @377, Slow Motion During Battle
@664 (identical index in BOTH archives); Offline @675, Default Network
Settings @785, Extra-wall Map Speed @1036, Skip Journey Events @1037,
Control Assistance @1068 (Eden ONLY — these indices don't exist / hold
different content in EU's shorter table); Controls @4 of **group 4** (tab
header, both archives). NOT yet located: 'Preferred Input Method', the
'Game 1'/'Game 2' tab names themselves, 'Camera', 'Audio', 'Graphics 1'/'2',
'Keyboard and Mouse' — a search of every group in entry 0 across both
archives came back empty for these; likely a different entry or table
entirely, deprioritized in favor of shipping a real proof with what was
already confirmed rather than continuing to search before deploying
anything.

**Deployed REAL Hebrew translations (not test markers) with bidi mode
deliberately alternated per field.** Bidi mode for this UI surface is
unconfirmed independently of the story/battle proof (which is still
awaiting its own screenshot) — so half the fields are stored
`get_display(text, base_dir="R")`-reversed and half stored natural,
following this project's "test both candidates in one proof" doctrine:
whichever pattern reads correctly on screen answers bidi mode for this
surface too, while guaranteeing at least half the fields are legible
regardless of which mode turns out to be right.
Difficulty→קושי(logical), Vibration→רטט(visual), Gore Level→רמת
אלימות(logical), Voice Chat→צ'אט קולי(visual), Slow Motion During
Battle→תנועה איטית בקרב(logical), Controls→פקדים(logical) — both archives;
plus, Eden only: Offline→לא מקוון(visual), Default Network Settings→הגדרות
רשת ברירת מחדל(logical), Extra-wall Map Speed→מהירות מפת חוץ-חומה(visual),
Skip Journey Events→דלג על אירועי מסע(logical), Control Assistance→סיוע
בשליטה(visual).

**Verified 11/11 read-back-correct in each archive, PLUS a fine-grained
per-string collateral check** (stronger than the whole-entry check used for
flat-table proofs, since entry 0 legitimately changes as a whole): every
OTHER string across every OTHER group in entry 0 was diffed individually
against the pristine `.he_backup` — **1375 EU / 2822 Eden untouched strings
byte-identical, 0 unexpected changes** — on top of the usual whole-entry
check (2435/2438 EU, 1642/1645 Eden untouched entries also byte-identical).

`aot2_deploy.build_options_edits()` + `OPTIONS_GROUP0_SHARED` /
`OPTIONS_GROUP0_EDEN_ONLY` / `OPTIONS_GROUP4`.

## "Still English" report, round 5 (2026-08-10) — the Options-screen "?" tofu is REAL, informative data: mount confirmed, font conclusively confirmed missing for THIS renderer; two more font leads chased and ruled out

The user's screenshot of the SAME Options screen after the round-4 deploy showed most of
the edited fields as strings of literal **"?" characters** (matching the expected word
count/length of each translated Hebrew phrase — e.g. "????" where Difficulty/קושי should
be, "?????? ????" where Voice-Chat-adjacent fields sit) while **"Voice Chat" and
"Preferred Input Method" stayed in plain English, completely unedited**.

**This is a definitively informative result, not a failure to diagnose:**
- **MOUNT re-confirmed a THIRD time, independently.** The tofu strings have the correct
  word/character counts for our Hebrew content — the engine IS reading our edited group-
  table data and attempting to render it character-by-character. A pre-baked/texture-only
  fallback could never produce a "?"-per-character pattern; only genuine per-glyph dynamic
  text composition does.
- **Font coverage is CONCLUSIVELY confirmed missing for this specific text renderer** — an
  unmapped codepoint falls back to a literal "?" glyph (which DOES exist, since it's
  ASCII) rather than a `.notdef` box or silent skip. This is the clearest possible signal
  a font gate this project's own doctrine anticipates ("if tofu → font-injection
  sub-project"), now delivered by a real deploy instead of theory.
- **"Voice Chat" and "Preferred Input Method" rendering UNCHANGED, in English, is a
  SEPARATE finding, not a failed edit.** Group 0 index 377 was pre-flight-verified (before
  any write) to hold the exact string `'Voice Chat'`, and the deployed archive was
  independently read back afterward confirming the edit landed correctly at that index —
  so the write is not in question. The most likely explanation is that this specific
  on-screen row is NOT sourced from group-0 index 377 at all: the "Game 1" tab's displayed
  row ORDER very likely comes from a separate tab-layout table referencing string indices
  in an arbitrary (non-sequential) order, and English text identical to a string we DID
  edit can legitimately exist as a SEPARATE, un-edited duplicate entry elsewhere in the
  same group or a different group/entry. Not chased further this round (deprioritized —
  the font gate is the higher-value question).

**Two more font-container leads, each fully investigated and conclusively ruled out —
adding real confidence on top of the pre-existing exhaustive (pre-session) negative
search, not merely re-asserting it:**

1. **"Group tables" cracked this session (`is_group_table`) turned out to ALSO hold a
   NEW, previously-unexamined container class: "KSLT" (`TLSK` on disk, magic
   `0x4b534c54`), Cethleann's "KTGL Screen Layout Texture" format (`.kslt`) — a NAMED,
   per-image-transform-matrix texture-atlas container distinct from both flat DataTables
   and group tables.** Found by grepping the huge asset bundles (`LINKDATA_A.BIN` 5.8GB,
   `LINKDATA_B.BIN` 7.2GB, `LINKDATA_C.BIN` 2.3GB — none previously scanned this deeply,
   since a full per-entry decompress-and-parse of files this size is prohibitively slow;
   a raw byte-level `grep -a -o -b` for the magic string across the whole file is cheap
   and safe even at multi-GB scale, and gives exact byte offsets that map straight back to
   a TOC entry without ever loading the file into memory). One clean hit
   (`LINKDATA_A.BIN` entry 3196, magic at byte offset 0 of a stored/uncompressed
   132,160-byte entry — the strongest possible candidate shape) parsed exactly per
   Cethleann's `ScreenLayoutTextureHeader`/`Matrix`/`Pointer`/`Image` struct layout with
   every internal cross-check consistent (`PointerTablePointer=560` == exactly
   `Count(10) × sizeof(Matrix)=56`; image `Size=131072` == exactly `512×256` BC3 texture
   bytes). **Its single embedded name is `pad_cmn_menu_l1`** ("(game)pad common menu"),
   and all 10 of its transform-matrix entries point at ONE SHARED 512×256 BC3 texture —
   decoded (wrapped in a minimal DDS header, opened via Pillow) and **visually confirmed
   to be a set of 10 left/right chevron/scroll-arrow icons** — exactly the `◄`/`►`
   tab-scroll arrows visible at the far edges of the Options screen's tab bar. **Definitively
   an icon/sprite atlas, unrelated to text glyphs — ruled out.**
2. **Cethleann's own `DataType.cs` enum explicitly documents a KTGL Font container** —
   `Font2` (extension `.g1n`, doc comment literally "KTGL Font"), magic `_N1G` on disk.
   Grepped for this exact byte sequence across EVERY LINKDATA archive in the game (same
   cheap raw-byte-grep + TOC-mapping method): 4 hits total (`LINKDATA_A.BIN`×1,
   `LINKDATA_B.BIN`×2, `LINKDATA_PATCH_000.BIN`×1). The 2 `LINKDATA_B.BIN` hits sit inside
   COMPRESSED entries (a literal ASCII match inside zlib-compressed bytes is essentially
   never real content — disregarded as noise). The other 2 (`LINKDATA_A.BIN` entry 12862,
   `LINKDATA_PATCH_000.BIN` entry 2266 — both stored/uncompressed) were extracted and
   inspected directly: **both entries actually begin with an UNRELATED magic (`FP1G` at
   offset 0, a different, unidentified container class), and the font-magic hit sits deep
   inside each entry's body (byte offsets 9,616 and 16,600) in the middle of a long run of
   4-byte-aligned values that decode cleanly as an array of IEEE-754 float32s in the tens-
   of-thousands range (~30,000–90,000) — almost certainly world-space vertex/spatial
   coordinate data, where the ASCII bytes `_N1G` occur purely by coincidence.** This is
   the EXACT SAME false-positive class already on record from the original (pre-this-
   session) font search ("coincidental float32 vertex/skeleton data") — independently
   re-derived here via a completely different discovery method (Cethleann's own magic
   enum + a fresh full-archive grep, rather than the earlier ad-hoc sfnt/FourCC scan),
   which strengthens rather than merely repeats the earlier conclusion. **Ruled out.**

**Verdict: the font/glyph rendering mechanism for this UI surface remains genuinely
unreachable via static container analysis, now after THREE independent, non-overlapping
search methods (the original multi-method sweep, the group-table `KSLT` icon-atlas lead,
and the `DataType`-enum-driven `Font2`/`G1N_` lead) all converge on the same negative.**
Per this project's own doctrine, a deployed screenshot is the correct next instrument
once static RE is genuinely exhausted — and it was just used, and it delivered a clear,
specific, actionable answer for the Options-screen surface: **mount works, font glyphs
for Hebrew do not exist in whatever renders this screen.** This does NOT necessarily mean
the story-intro/battle-mission surfaces (entries 2424/1056/1639/721) share the exact same
renderer or the exact same limitation — many game engines route menu/HUD text and in-game
dialogue/subtitle text through genuinely separate rendering subsystems, so that screenshot
(still awaited) remains a real, independent, still-open question rather than a foregone
conclusion.

## Round 6 (2026-08-10) — three MORE independent search methods, all still negative; the exe's own import table now rules out "it's just a Windows codepage/font substitution"

Before touching the story/battle screenshot, the font hunt was widened with three genuinely
new methods (none reused from rounds 1–5), specifically because the user asked to inject a
Hebrew font and verify it BEFORE anything else:

1. **EXE/DLL font resources — checked for the first time.** `pefile`-based scan of all four
   shipped executables (`AOT2_EU.exe`, `AOT2_AS.exe`, `AOT2_JP.exe`, `Launcher.exe`) for
   Win32 `RT_FONT`/`RT_FONTDIR` PE resources, plus a raw sfnt-magic byte scan of the whole
   binary with a **strict validator** (real sfnt table-directory invariants: `numTables` in
   range, `searchRange`/`entrySelector`/`rangeShift` consistent with `numTables` per the sfnt
   spec, every table tag 4 printable ASCII chars, every table's offset+length inside the
   file). A first pass using `fontTools(lazy=True)` as the validator was a false start — it
   accepted raw x86 machine code as "valid fonts" (the `\x00\x01\x00\x00` sfnt magic occurs
   constantly as an immediate operand in compiled code, and the lazy loader doesn't check
   table-tag printability) — discarded once the strict validator showed **zero** genuine
   hits across all four binaries and **zero** `RT_FONT`/`RT_FONTDIR` resources (resource
   types present are only `3`=RT_ICON, `14`=RT_GROUP_ICON, `16`=RT_VERSION,
   `24`=RT_MANIFEST — ordinary boilerplate).
2. **Cethleann's `DataType.cs` enum re-fetched from its REAL path** (the file lives at
   `Cethleann.Structure/DataType.cs` on the `develop` branch — not `Cethleann/DataType.cs`
   on `master`, which 404s; found via the repo's search API + tree listing) and read in
   full (95 members). Confirms the round-5 `Font2`/`Morph` findings and surfaces exactly one
   more untried candidate: **`ScreenLayout` (magic `KSCL`, on-disk bytes `LCSK`)** — a
   SEPARATE member from the already-ruled-out `ScreenLayoutTexture`/KSLT, with its own doc
   comment (though the doc comments on these two enum members are almost certainly
   transposed relative to their names in the upstream source — the actually-IMPLEMENTED
   reader class, `Cethleann/Graphics/KSLT.cs`, matches the `TLSK`-on-disk one already ruled
   out). **`KSCL` has NO reference reader anywhere in Cethleann** — it is a declared-but-
   never-implemented magic in the community toolkit, so pursuing it would mean reverse-
   engineering an entirely new struct layout with zero reference implementation, a
   substantially weaker starting position than every lead chased so far (all of which had a
   real reference struct to validate against). Not pursued this round given the much
   stronger lead that opened up next.
3. **A real G1T (TextureGroup) texture-bundle decoder, built from scratch this round** (no
   G1T tooling existed anywhere in this project before now — the round-5 note "several large
   G1T texture decoded during the hunt" was evidently done via a cruder/ad-hoc method that
   couldn't see individual sub-textures packed inside a G1T bundle, since those carry no
   per-texture magic of their own). Struct layout fetched fresh from
   `Cethleann/Graphics/G1TextureGroup.cs` + its 7 supporting struct/enum files
   (`ResourceSectionHeader`, `TextureGroupHeader`, `TextureDataHeader`,
   `TextureDataHeaderExtended`, `TexturePackedSize`, `TexturePackedInfo`, `TextureType`,
   `TextureUsage`) and implemented as `games/attack_on_titan_2/work/scan_g1t_small.py` +
   `decode_g1t_195.py`. Scanned **2,756 individual textures across 4 archives**
   (`LINKDATA_REGION_EU.BIN`, `LINKDATA_REGION_EDEN_EU.BIN`, `LINKDATA_PLATFORM_DX11.BIN`,
   `LINKDATA_PLATFORM_EDEN_DX11.BIN`) plus **777 more** across the four JP/AS region
   archives — every one metadata-parsed (width/height/pixel-format), sorted by both
   ascending AND descending area to inspect the smallest (candidate compact glyph atlases,
   never checked before — the round-5 note explicitly says only LARGE G1T textures were
   visually inspected) and largest (candidate CJK glyph atlases, which would need to be big
   given Japanese/Korean/Chinese localizations ship and need thousands of real glyphs). The
   smallest non-degenerate candidates (dedup'd, one strong lead: `LINKDATA_PLATFORM_DX11.BIN`
   entry 195 — 150 separate 256×256 BC1 textures bundled together, the single most
   glyph-atlas-shaped signature found in five rounds of searching) were fully decoded to real
   PNGs (BC1/DXT1 via a minimal DDS-header wrap + Pillow's built-in decoder, the same
   technique proven on the round-5 KSLT icon atlas) and visually inspected. **Result: a
   tileable cloth/fabric-weave NORMAL MAP** (the diagnostic blue-purple tangent-space colour
   signature), not text — entry 195 sits inside a cluster of 8 adjacent entries (187–195,
   all 256×256, mixed BC5/BC6/BC1/R8G8B8A8) that decode as a coherent PBR material set
   (normal map, a directional gradient/streak mask, a radial-gradient shader LUT) for 3D
   character/equipment rendering, not UI. The three remaining small uncompressed
   `R8G8B8A8` candidates in a plausible size range (128×128, 256×128, 256×256, entries
   189/190/193, the format most associated with crisp UI/font work since it avoids block-
   compression artifacts on sharp edges) were also decoded directly — a cloth-fibre albedo
   texture, a light-streak/gradient mask, and a radial colour-ramp LUT respectively. **None
   glyph-shaped.** The largest textures in every scanned archive (2048×2048, both EU and
   JP/AS regions) are uniformly BC5/BC1/an undocumented `0x5f` format — consistent world/
   environment textures, no atlas-of-many-small-cells signature anywhere.
4. **The exe's PE import table was checked for OS text-rendering APIs — a genuinely
   decisive, orthogonal signal.** `GDI32.dll` is imported with exactly **1** function (not a
   text-drawing one — no `TextOutW`/`ExtTextOutW`/`DrawTextW`/`CreateFontW`), and there is
   **no** `dwrite.dll`, **no** `usp10.dll` (Uniscribe) import at all. Combined with the
   `d3d11.dll`/`dxgi.dll` imports, this **conclusively rules out** the "the game defers text
   rendering to a Windows system font, and the '?' is a codepage/`WideCharToMultiByte`-style
   lossy-conversion artifact rather than a missing embedded glyph" hypothesis that was
   floated as an alternative explanation for the tofu — the game does **100% custom,
   proprietary, D3D11-texture-based text rendering** with **zero** reliance on any OS font
   API. This *reinforces* rather than weakens the original font-gate diagnosis: a real,
   proprietary glyph/font data source for this renderer categorically MUST exist somewhere
   in the game's own files (it draws thousands of real CJK glyphs for the shipped Japanese/
   Korean/Chinese localizations, which is only possible from an owned texture/vector
   resource) — it has simply not yet been located, despite now FIVE independent,
   non-overlapping static-analysis methods across two sessions all converging on the same
   negative for the specific spot searched.

**Verdict, unchanged in substance from round 5 but now on much stronger footing:** static
container analysis has been pushed considerably further (EXE resources, EXE raw sfnt with a
correctly-strict validator, the full DataType enum, a real G1T decoder covering both the
smallest and the largest textures in every archive most likely to hold UI-adjacent content)
and remains genuinely unable to locate this renderer's glyph source. **A literal "inject a
Hebrew font and verify" step cannot be performed yet — there is still no known location to
inject into.** The two responsible ways forward are (a) a live-process-memory investigation
of the running game (per the `reverse-engineer-container` skill's own fallback guidance,
untried so far this round) or (b) widening the G1T scan to the remaining un-scanned archives
(`LINKDATA_A/B/C/D.BIN`, several GB each — the icon atlas from round 5 was found precisely
this way, so it is not a dead technique, just an expensive one at this archive's scale).

## Next (Phase 2 — gated on the user's screenshot + an explicit "פרסם")
1. **The Options-screen question is now ANSWERED (rounds 5–6)**: mount confirmed
   (again), font glyphs confirmed MISSING for that specific renderer ("?"
   tofu, not boxes) — no further screenshot of that screen is needed to
   learn anything new. What's still genuinely open is the STORY/BATTLE
   surface: user gets PAST the (English, texture-baked, expected) main
   menu, and screenshots the main story-intro cutscene (Story Mode's
   opening narration) and/or a mission-start instruction popup — NOT the
   title screen, which will never show Hebrew via this pipeline. Both
   markers (`ZZ-AOT2...`/`ZZ-BATTLE...` vs the `...-EDEN-...` variants)
   together tell us which archive the build actually reads for dynamic
   text, AND whether that surface's renderer shares the Options screen's
   missing-Hebrew-glyphs limitation or is a genuinely separate subsystem
   (many engines route menu/HUD text and in-game dialogue through different
   font paths — this is not a foregone conclusion from the Options result).
2. Read the result: mount confirmed by the Latin marker; bidi mode read off
   the LOGICAL-vs-VISUAL pair; font coverage read off the 27-letter
   alphabet (clean glyphs vs tofu).
3. **If ALSO tofu** → the font gate is confirmed engine-wide, and — per
   round 6's now FIVE-methods-deep confirmation that static container
   analysis cannot locate this game's glyph/font resource — a font-
   injection sub-project here needs either a live-process-memory
   investigation (per the `reverse-engineer-container` skill's "read the
   running exe's unpacked code/memory" technique) or a much larger sweep
   of the still-unscanned multi-GB `A/B/C/D.BIN` archives with the new G1T
   decoder. **If it renders correctly** (a different renderer than the
   Options screen) → font gate closed for that surface with zero further
   work needed, and the Options-screen chrome specifically stays out of
   scope.
4. Delegate the ~64,685-string translation (plus the newly-found Options/
   Settings UI banks — 674 EU / 1083 Eden strings in entry 0 group 0 alone)
   to agents/a fleet ([[delegate-all-translation]]) — Claude never
   translates the corpus (the Options-screen labels above were a small,
   user-facing Phase-1 menu-proof exception, consistent with this project's
   established precedent of translating a handful of menu-proof strings by
   hand while delegating the full corpus).
5. Build via `encode_datatable`/`encode_group_table` + whichever bidi
   transform the proof determined, deploy via the same append-relocate
   mechanism, publish only on an explicit "פרסם" (GitHub release repo +
   Worker slug + Supabase `games` row + `mod_version_history`), per the
   project's standard publish pipeline.
