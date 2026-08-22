# Attack on Titan 2 Hebrew — Pipeline (operational reference)

Run everything with the repo `.venv` python (`python-bidi` lives there;
`fontTools` was used ad-hoc during the font hunt but is not required by the
permanent tooling below).

## Tools (`games/attack_on_titan_2/`)

| file | role |
|---|---|
| `tools/aot2_linkdata.py` | Container codec — `LinkData` reader (`raw(i)`/`read(i)`), `is_datatable`/`parse_datatable`/`read_cstring` (decode) + `encode_datatable` (encode) for FLAT tables; `is_group_table`/`parse_group_table`/`encode_group_table` for the nested "group table" sub-format (a `count`+offsets array pointing at several independent nested DataTables inside one entry). Both encoders round-trip byte-identical on an unmodified string list. |
| `work/aot2_deploy.py` | Deploy — `apply_edits(path, edits)` (append-relocate, auto-backup, auto-dispatches flat vs group per entry), `revert(path)`, `build_proof_edits()` (the story/battle menu-proof content, flat tables), `build_options_edits()` (the Options/Settings-screen real-Hebrew content, a group-table entry), CLI `--deploy` / `--revert` / `--status`. |
| `work/scope_report.py` | Phase-2 scope counter — classifies every DataTable in `REGION_EU/JP/AS` into "battle text" (20-450 strings/table) vs "story/dialogue" (>450 strings/table), reports records / per-file uniques / GLOBAL uniques for each, plus a cross-archive total. |

## Deploy targets

Both archives (backup: same path + `.he_backup`, created automatically on
first write):
- `F:\Games\Attack on Titan 2\LINKDATA\REGION\LINKDATA_REGION_EU.BIN` (base
  game, 2438 entries)
- `F:\Games\Attack on Titan 2\LINKDATA\REGION\LINKDATA_REGION_EDEN_EU.BIN`
  ("Final Battle" content — the title screen literally reads "-Final
  Battle-", so this may be the archive actually read for story/mission
  content; the two archives have TOTALLY different entry indexing — 2438 vs
  1645 entries — so the Eden targets below were located by CONTENT match,
  not by assuming the same index carries the same thing)

Edited entries (indices into each archive's own TOC, 0-based):
- **REGION_EU entry 2424** / **REGION_EDEN_EU entry 1639** — story-intro
  narration DataTable (the "That day, humanity remembered." opening recap;
  confirmed the SAME line at both indices, in their respective archives).
  Proof uses indices 0-7.
- **REGION_EU entry 1056** / **REGION_EDEN_EU entry 721** — a
  mission-instruction "battle text" DataTable (many structurally-identical
  tables exist, one per mission; 721 is just a representative). Proof uses
  indices 0-4 (see `_battle_edits()` in `aot2_deploy.py` — index 0 is a
  category marker `'（通常）ENG'`, NOT display text; the real instruction
  line starts at index 1 with a `'（指示）'` prefix whose rendering
  behavior was unconfirmed, so the proof tests marker-slot, prefix-kept, and
  prefix-stripped all at once).
- **REGION_EU entry 0 / REGION_EDEN_EU entry 0 — a GROUP TABLE, not a flat
  DataTable.** Group 0 is the Settings/Options UI string bank (674 strings
  EU, 1083 Eden — the extra ~409 are Eden-only Options fields); group 4
  holds tab-header labels. `build_options_edits()` writes 10-11 REAL Hebrew
  translations here (not markers) at indices located by exact match against
  the user's Options-screen screenshot — see `OPTIONS_GROUP0_SHARED` /
  `OPTIONS_GROUP0_EDEN_ONLY` / `OPTIONS_GROUP4` in `aot2_deploy.py`. Bidi
  mode is deliberately ALTERNATED per field (logical/visual) since it's
  unconfirmed for this surface independently of the story/battle proof.

## Commands

```
# check current deploy/backup state
python games/attack_on_titan_2/work/aot2_deploy.py --status

# deploy the Phase-1 multi-mode menu proof (auto-backs-up first)
python games/attack_on_titan_2/work/aot2_deploy.py --deploy

# revert to the pristine backup
python games/attack_on_titan_2/work/aot2_deploy.py --revert

# Phase-2 scope report (records / per-file uniques / GLOBAL uniques)
python games/attack_on_titan_2/work/scope_report.py
```

## Verifying a deploy did no collateral damage

`apply_edits`/`--deploy` already prints a read-back verification of every
edited string. To independently confirm every OTHER entry in the archive is
byte-identical to the pristine backup (the collateral-damage check that
proved 0/2436 mismatches this session):

```python
import sys
sys.path.insert(0, "games/attack_on_titan_2/tools")
from aot2_linkdata import LinkData

orig = LinkData(r"F:\Games\Attack on Titan 2\LINKDATA\REGION\LINKDATA_REGION_EU.BIN.he_backup")
new  = LinkData(r"F:\Games\Attack on Titan 2\LINKDATA\REGION\LINKDATA_REGION_EU.BIN")
touched = {2424, 1056, 0}
mismatches = sum(
    1 for i in range(orig.files)
    if i not in touched and orig.raw(i) != new.raw(i)
)
print(mismatches, "of", orig.files - len(touched))
```

**For entry 0 (a group table), the whole-entry check above only proves
entries OTHER than 0 are untouched — entry 0 itself must be checked at the
per-STRING level**, since it legitimately changes as a whole (only a few of
its ~2000+ nested strings are edited):

```python
from aot2_linkdata import parse_group_table

old_groups = parse_group_table(orig.read(0))
new_groups = parse_group_table(new.read(0))
edited = {0: {0, 3, 36, 377, 664}, 4: {4}}  # {group_idx: {string_idx,...}}
bad = sum(
    1 for gi, (og, ng) in enumerate(zip(old_groups, new_groups))
    if og is not None
    for si in range(len(og))
    if si not in edited.get(gi, set()) and og[si] != ng[si]
)
print(bad, "unexpected changes among the untouched strings")
```

## Building a real translation edit set (Phase 2, once delegated)

`build_proof_edits()` in `aot2_deploy.py` is the template shape:
`dict[entry_index, dict[string_index, new_string]]`. A real Phase-2 build
will need to:
1. Enumerate every text-bearing DataTable entry across `REGION_EU.BIN` (and
   `REGION_JP/AS.BIN` if the JP/AS-only content is ever in scope) via
   `scope_report.scan()`'s classification logic.
2. Map each unique English string to its approved Hebrew translation
   (delegated to agents — [[delegate-all-translation]]).
3. Apply whichever bidi transform the deployed proof determined is correct
   (LOGICAL+RLM / VISUAL / force-RTL-base — see `rtl-bidi` skill) to every
   translated string before writing.
4. Call `apply_edits(REGION_EU, edits)` with the full edit set — the
   append-relocate mechanism handles archive growth automatically (each
   edited entry's new content is appended once, regardless of size).

## Known unknowns (documented, not blocking)

- **UI/menu chrome (title-screen labels) is almost certainly baked as
  texture graphics, NOT dynamic text — confirmed 2026-08-10 by TWO rounds of
  exhaustive negative search, not merely "not found yet".** Round 2 (raw
  ASCII substring scan, all archives): every one of the 8 title-screen words
  DOES exist in the text data, but only inside unrelated contexts (an
  online-play mode-select dialog, the in-game Manual TOC, a tutorial
  sentence). Round 3 (2026-08-10, after the user re-reported "still English"
  a second time) went further: a FULL structural parse (both flat DataTables
  AND the group-table sub-format, recursively) of EVERY entry in EVERY
  candidate archive (REGION EU/JP/AS, all 3 Eden variants, D, DLC — 969MB,
  PATCH_000 — 2.4GB, EX_MASTER, both PLATFORM_DX11 variants), keeping only
  EXACT string-equality hits (not substring) against the 8 words. Result:
  every exact hit is inside ONE of exactly two contexts — an online-lobby
  "Mode Selection" dropdown (bounded by "Room Search (By ID)" before and
  "Difficulty Selection" after) or the in-game Manual's table of contents —
  never a standalone contiguous 8-item list. "System" and "Exit" never occur
  as a bare standalone string anywhere. `LINKDATA_DLC.BIN` and
  `LINKDATA_PATCH_000.BIN` (not checked in round 2) were included this time
  and also came back with 0 exact hits. Region archives also contain zero
  raw G1T texture entries (confirmed magic-scan), while
  `LINKDATA_PLATFORM_DX11.BIN` DOES hold 16 real G1T-magic entries —
  consistent with the visibly stylized, torn/bloodied "A.O.T.2"
  title-screen font: the menu row is very likely pre-rendered per-language
  texture strips in the big asset bundles (A/B/C/PLATFORM_DX11), not
  translatable string-table text. Chasing that further is texture-atlas
  replacement — a different, much larger task than string patching, and out
  of scope for now.
  The two PROVEN dynamic-text surfaces (story intro, a mission-instruction
  popup) are unaffected and are now deployed REDUNDANTLY into BOTH
  REGION_EU and REGION_EDEN_EU (the "Final Battle" archive — see "Deploy
  targets" above), located by content-match since the two archives have
  completely different entry indexing. This covers whichever archive the
  running "Final Battle" build actually resolves story/mission content
  from.

- **🔴 CRITICAL codec bug found + fixed 2026-08-10 — the old decoder
  SILENTLY TRUNCATED any zlib-compressed entry with `dsize > 32768`.**
  `LinkData.read()` used a single `zlib.decompress(raw[8:])` call; large
  entries are actually stored as MULTIPLE independently-compressed
  32768-byte blocks concatenated together (block 1's zlib stream starts
  right after the entry's 8-byte header; every later block is preceded by
  a 4-byte informational field, then its own fresh zlib stream — see
  `aot2_linkdata.py`'s module docstring + `decompress_blocks()`). Python's
  `zlib.decompress()` does not error on trailing unconsumed bytes, so this
  looked correct for years on every small entry and only manifested as
  missing/garbled strings past byte 32768 of any bigger table. FIXED via
  a shared `decompress_blocks()` in `aot2_linkdata.py`, used by both
  `LinkData.read()` and `aot2_deploy.apply_edits()`. Re-verified: entries
  2424/1056 (already deployed) were stored RAW (dsize=0) in the pristine
  archive, so they were NEVER affected by this bug — the deployed proof is
  unchanged and still reads back 12/12 correct. `scope_report.py`'s counts
  (64,685 unique strings) were ALSO re-run with the fix and came back
  byte-for-byte identical (357,830/60,655 records both times) — none of
  the individual battle/story tables it counts happen to exceed one block.
  **Anyone extending this pipeline: always go through `LinkData.read()` /
  `decompress_blocks()`, never a raw `zlib.decompress()` call.**

- **A THIRD sub-format was discovered AND is now fully solved + shipped:
  "group tables".** Some archive entries (entry 0 in both REGION_EU.BIN and
  REGION_EDEN_EU.BIN — 69,056 / 136,320 bytes pristine) are not a flat
  DataTable — `is_datatable()` on the top-level content is False. Instead
  they're `u32 group_count` followed by `group_count × u32` BYTE OFFSETS
  (not offset+size pairs) into the SAME buffer, each pointing at the start
  of its own independent nested DataTable — a container-of-containers used
  to bundle several unrelated string banks (an online-lobby dropdown, the
  general Settings/Options UI bank, tab-header labels, the Manual TOC) into
  one archive entry. `is_group_table`/`parse_group_table`/
  `encode_group_table` in `aot2_linkdata.py` fully read+write it —
  **proven byte-identical round-trip on real archive data**, two subtleties
  that cost two fix iterations: every nested group's start offset is
  **16-byte aligned** with a zero-padded gap after each group's own
  encoded content, AND the **whole buffer is padded to a 16-byte boundary
  at the very end** too. `aot2_deploy.apply_edits()`/`verify()` auto-detect
  which format an entry is and dispatch accordingly — no caller flag
  needed. **NOW used by the deploy pipeline**: `build_options_edits()`
  writes real Hebrew into entry 0's group 0 (Options/Settings UI, 674 EU /
  1083 Eden strings) and group 4 (tab headers) in both archives — see
  "Deploy targets" above.
- **Font glyph coverage is unknown** — no font container was positively
  identified anywhere in the game despite an extensive multi-method search
  (see `FEASIBILITY.md` Gate 5). Resolved by the deployed proof's 27-letter
  alphabet string once the user screenshots it. If tofu, port the G1T
  texture-atlas approach from `scratchpad_g1t_extractor.py` (adapted from
  the public `AOT2-G1T-EXTRACTOR` tool) IF the font turns out to live in a
  texture atlas — otherwise a fresh font-location search is needed.
- **Eden/Final-Battle expansion archives** (`REGION_EDEN_EU/JP/AS`) were not
  scoped this session — same format, trivial to add to `scope_report.py`'s
  target list.
