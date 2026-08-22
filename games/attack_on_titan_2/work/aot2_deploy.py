"""
Append-relocate deploy for AoT2 LINKDATA_*.BIN archives.

For each edited entry:
  - decode its current DataTable content (handles both stored and zlib-compressed
    entries transparently)
  - apply the string-index -> new-string edits
  - re-encode as a DataTable, ALWAYS stored uncompressed (decompressed_size=0) —
    simplest and safest; every text table sampled so far is already stored this
    way, and there is no requirement to compress on write
  - append the new bytes at EOF, padded to a `mult`-byte (256) sector boundary
  - patch ONLY that entry's 16-byte TOC record (offset_sectors, 0, new_size, 0)

Every other byte in the archive — header, every other TOC record, every other
entry's payload — is left untouched. Offline-validated on a scratch copy of the
real LINKDATA_REGION_EU.BIN: identity edits + 2-entry edits both round-trip
correctly and 0/2436 other entries differ from the pristine original.

Usage:
    python aot2_deploy.py --deploy
    python aot2_deploy.py --revert
    python aot2_deploy.py --status
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import (  # noqa: E402
    MAGIC,
    LinkData,
    decompress_blocks,
    encode_datatable,
    encode_group_table,
    is_datatable,
    is_group_table,
    parse_datatable,
    parse_group_table,
    read_cstring,
)

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
REGION_EU = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN"
REGION_EDEN_EU = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN"
ALL_TARGETS = [REGION_EU, REGION_EDEN_EU]


def backup_path(p: Path) -> Path:
    return p.with_suffix(p.suffix + ".he_backup")


def ensure_backup(p: Path) -> None:
    bak = backup_path(p)
    if not bak.exists():
        shutil.copy2(p, bak)
        print(f"  backup -> {bak}")


def apply_edits(
    path: Path,
    edits: dict[int, dict[int, str] | dict[int, dict[int, str]]],
) -> dict[int, tuple[int, int]]:
    """`edits` = {entry_idx: string_edits}. For a FLAT-table entry,
    string_edits = {string_idx: new_value}. For a GROUP-table entry (a
    top-level container of nested DataTables — see aot2_linkdata.py),
    string_edits = {group_idx: {string_idx: new_value}} instead — detected
    automatically per entry, no caller flag needed."""
    ensure_backup(path)
    data = bytearray(path.read_bytes())
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    assert code == MAGIC, f"bad magic in {path}"

    results: dict[int, tuple[int, int]] = {}
    for entry_idx, string_edits in edits.items():
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + entry_idx * 16)
        start = eo * mult
        raw = bytes(data[start : start + csize])
        if dsize == 0:
            content = raw
        else:
            content = decompress_blocks(raw[8:], dsize)

        if is_datatable(content):
            blobs = parse_datatable(content)
            strings = [read_cstring(b) if b is not None else None for b in blobs]
            for si, newval in string_edits.items():
                strings[si] = newval
            new_content = encode_datatable(strings)  # type: ignore[arg-type]
        elif is_group_table(content):
            groups = parse_group_table(content)
            for gi, group_edits in string_edits.items():
                target = groups[gi]
                assert target is not None, f"entry {entry_idx} group {gi} is not a datatable"
                for si, newval in group_edits.items():  # type: ignore[union-attr]
                    target[si] = newval
            new_content = encode_group_table(content, groups)
        else:
            raise AssertionError(f"entry {entry_idx} is neither a flat nor a group datatable")

        eof = len(data)
        pad_needed = (-eof) % mult
        if pad_needed:
            data += b"\x00" * pad_needed
            eof = len(data)
        new_sector = eof // mult
        data += new_content
        new_size = len(new_content)

        struct.pack_into("<IIII", data, 16 + entry_idx * 16, new_sector, 0, new_size, 0)
        results[entry_idx] = (new_sector, new_size)
        print(f"  entry {entry_idx}: {len(string_edits)} strings patched, "
              f"appended @ sector {new_sector} ({new_size} bytes)")

    path.write_bytes(bytes(data))
    return results


def revert(path: Path) -> None:
    bak = backup_path(path)
    if not bak.exists():
        print(f"  no backup found for {path} — nothing to revert")
        return
    shutil.copy2(bak, path)
    print(f"  reverted {path} from {bak}")


# ---------------------------------------------------------------------------
# The Phase-1 menu/proof content — every open gate closed in ONE deploy:
#   - a pure-Latin marker (mount proof, font-independent)
#   - the SAME word stored LOGICAL vs VISUAL on adjacent lines (bidi mode)
#   - all 27 Hebrew letters (glyph coverage / tofu)
#   - a punctuation/parens/digits/Latin-island paragraph in BOTH modes (layout)
# Target: the story-intro narration table (entry 2424 in REGION_EU — the
# opening "That day, humanity remembered." recap, the first thing shown on a
# fresh Story Mode save) + the mission-instruction battle-text table (entry
# 1056 — reached the instant any combat mission starts), as two independent
# reachable surfaces.
# ---------------------------------------------------------------------------
from bidi.algorithm import get_display  # noqa: E402

HEB_ALPHABET = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
PARAGRAPH_LOGICAL = 'בדיקה: (מספר 123) "מרכאות" - עברית עם NVIDIA ואז סוף!'
PARAGRAPH_VISUAL = get_display(PARAGRAPH_LOGICAL, base_dir="R")


def _battle_edits(marker: str) -> dict[int, str]:
    """Entry index 0 in every 'battle text' table is a category marker
    ('（通常）ENG' = "(normal) ENG"), NOT display text — the real
    mission-instruction line is index 1 onward, prefixed with '（指示）'
    ("(instruction)"). Since it's unconfirmed whether that prefix is stripped
    before rendering or shown literally, this tests all three: the marker
    slot itself, prefix-kept, and prefix-stripped — so one screenshot answers
    which slot (and which convention) is the real one."""
    return {
        0: marker,
        1: f"（指示）{marker}",
        2: "שלום",
        3: get_display("שלום", base_dir="R"),
        4: HEB_ALPHABET,
    }


def _visual(s: str) -> str:
    return get_display(s, base_dir="R")


# Entry 0 in both REGION archives is a GROUP TABLE bundling several unrelated
# string banks (see aot2_linkdata.is_group_table). Group 0 is the general
# Settings/Options UI string bank (674 strings in EU, 1083 in Eden — the
# Eden-only tail is additional Options fields not present in EU's shorter
# table, matching the "Final Battle" build's richer Options screen the user
# actually screenshotted); group 4 holds the tab-header strings. Indices
# below were located by EXACT string match against the confirmed English
# labels visible in the user's screenshot.
#
# Bidi mode for THIS engine/surface is still unconfirmed (independently being
# tested via the story-intro/battle-text proof at entries 2424/1056/1639/721)
# — so real, user-recognizable translations are deliberately ALTERNATED
# between LOGICAL and VISUAL storage across these rows: whichever pattern
# reads correctly on screen answers bidi mode for this surface too, while
# guaranteeing at least half the fields are legible either way.
OPTIONS_GROUP0_SHARED = {
    0: ("Difficulty", "קושי", "logical"),
    3: ("Vibration", "רטט", "visual"),
    36: ("Gore Level", "רמת אלימות", "logical"),
    377: ("Voice Chat", "צ'אט קולי", "visual"),
    664: ("Slow Motion During Battle", "תנועה איטית בקרב", "logical"),
}
OPTIONS_GROUP0_EDEN_ONLY = {
    675: ("Offline", "לא מקוון", "visual"),
    785: ("Default Network Settings", "הגדרות רשת ברירת מחדל", "logical"),
    1036: ("Extra-wall Map Speed", "מהירות מפת חוץ-חומה", "visual"),
    1037: ("Skip Journey Events", "דלג על אירועי מסע", "logical"),
    1068: ("Control Assistance", "סיוע בשליטה", "visual"),
}
OPTIONS_GROUP4 = {
    4: ("Controls", "פקדים", "logical"),
}


def _apply_mode(text: str, mode: str) -> str:
    return _visual(text) if mode == "visual" else text


def build_options_edits() -> dict[Path, dict[int, dict[int, dict[int, str]]]]:
    """Returns {archive_path: {0: {group_idx: {string_idx: new_value}}}} —
    entry 0 is a group table in both archives (see module comment above)."""
    eu_group0 = {si: _apply_mode(he, mode) for si, (_en, he, mode) in OPTIONS_GROUP0_SHARED.items()}
    eu_group4 = {si: _apply_mode(he, mode) for si, (_en, he, mode) in OPTIONS_GROUP4.items()}
    eden_group0 = dict(eu_group0)
    eden_group0.update(
        {si: _apply_mode(he, mode) for si, (_en, he, mode) in OPTIONS_GROUP0_EDEN_ONLY.items()}
    )
    eden_group4 = dict(eu_group4)
    return {
        REGION_EU: {0: {0: eu_group0, 4: eu_group4}},
        REGION_EDEN_EU: {0: {0: eden_group0, 4: eden_group4}},
    }


def build_proof_edits() -> dict[Path, dict[int, dict[int, str]]]:
    """Returns {archive_path: {entry_idx: {string_idx: new_value}}}.

    The main-menu/title-screen chrome (Story Mode / Another Mode / Character
    Episode Mode / Territory Recovery Mode / Gallery / System / Exit /
    Manual) was searched for EXHAUSTIVELY across every text archive (with the
    corrected multi-block decompressor, both flat AND group tables, exact
    string matching) and every hit is inside an unrelated UI context (the
    online-lobby "Mode Selection" dropdown, the in-game Manual/help table of
    contents) — never as its own standalone contiguous list. Strong evidence
    it's rendered from pre-baked texture strips, not translatable text. See
    FEASIBILITY.md "Still English" report rounds 2-3.

    The two proven-reachable dynamic-text surfaces (story intro + a
    battle-mission popup) are proofed in BOTH REGION_EU (the base game) AND
    REGION_EDEN_EU (the "Final Battle" content the title screen's own label
    names) — the two archives have completely different entry indexing
    (2438 vs 1645 entries), so the Eden equivalents were located by CONTENT
    match, not by assuming the same index: entry 1639 in EDEN contains the
    exact same intro line ("That day, humanity remembered.") as EU's 2424,
    and entry 721 is one of many structurally-identical battle-text tables
    matching EU's 1056's template. Deploying to both means the proof lands
    regardless of which archive the "Final Battle" build actually resolves
    story/mission content from."""
    return {
        REGION_EU: {
            2424: {
                0: "ZZ-AOT2-OK-ZZ",
                1: "שלום",
                2: get_display("שלום", base_dir="R"),
                3: HEB_ALPHABET,
                4: PARAGRAPH_LOGICAL,
                5: PARAGRAPH_VISUAL,
                6: "אבגד",
                7: get_display("אבגד", base_dir="R"),
            },
            1056: _battle_edits("ZZ-BATTLE-OK-ZZ"),
        },
        REGION_EDEN_EU: {
            1639: {
                0: "ZZ-AOT2-EDEN-OK-ZZ",
                1: "שלום",
                2: get_display("שלום", base_dir="R"),
                3: HEB_ALPHABET,
                4: PARAGRAPH_LOGICAL,
                5: PARAGRAPH_VISUAL,
                6: "אבגד",
                7: get_display("אבגד", base_dir="R"),
            },
            721: _battle_edits("ZZ-BATTLE-EDEN-OK-ZZ"),
        },
    }


def verify(path: Path, edits: dict[int, dict[int, str] | dict[int, dict[int, str]]]) -> None:
    ld = LinkData(path)
    for idx, se in edits.items():
        buf = ld.read(idx)
        if is_datatable(buf):
            dt = parse_datatable(buf)
            for si, expected in se.items():
                got = read_cstring(dt[si])
                status = "OK" if got == expected else "MISMATCH"
                print(f"    {path.name} entry {idx}[{si}] = {got!r}  [{status}]")
        elif is_group_table(buf):
            groups = parse_group_table(buf)
            for gi, group_edits in se.items():
                target = groups[gi]
                for si, expected in group_edits.items():  # type: ignore[union-attr]
                    got = target[si] if target is not None else None
                    status = "OK" if got == expected else "MISMATCH"
                    print(f"    {path.name} entry {idx}[group {gi}][{si}] = {got!r}  [{status}]")
        else:
            print(f"    {path.name} entry {idx}: neither flat nor group table — verify skipped")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--deploy", action="store_true")
    g.add_argument("--revert", action="store_true")
    g.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        for t in ALL_TARGETS:
            bak = backup_path(t)
            print(f"target:  {t}  exists={t.exists()}")
            print(f"backup:  {bak}  exists={bak.exists()}")
        return

    if args.revert:
        for t in ALL_TARGETS:
            revert(t)
        return

    if args.deploy:
        story_plan = build_proof_edits()
        options_plan = build_options_edits()
        plan: dict[Path, dict] = {}
        for path in ALL_TARGETS:
            merged: dict = dict(story_plan.get(path, {}))
            merged.update(options_plan.get(path, {}))
            plan[path] = merged
        for path, edits in plan.items():
            print(f"deploying proof to {path}")
            apply_edits(path, edits)
        print("done. Verifying by reading back from disk...")
        for path, edits in plan.items():
            verify(path, edits)


if __name__ == "__main__":
    main()
