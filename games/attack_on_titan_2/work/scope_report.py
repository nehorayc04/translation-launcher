"""
AoT2 scope report — the three honest numbers per the groundwork skill:
records / per-file uniques / GLOBAL uniques, for Phase-2 translation planning.

Scans every entry of a LINKDATA_REGION_*.BIN archive, decodes any entry that
parses as a DataTable, and classifies each table by string count into the two
observed content families:
    - "battle text"  : ~250-450 strings/table (mission objectives/HUD combat
                        callouts — short, high-repetition across ~230+ tables)
    - "story/dialogue": >450 strings in one table (cutscene narration — long,
                        largely unique prose)
Anything under ~20 strings or that fails a basic printable-ratio sanity check
is treated as non-text data (skipped from the scope count).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import LinkData, is_datatable, parse_datatable, read_cstring  # noqa: E402

BATTLE_MIN, BATTLE_MAX = 20, 450  # heuristic split observed in this game's tables


def printable_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if c.isprintable())
    return ok / len(s)


def scan(path: Path):
    ld = LinkData(path)
    battle_records = 0
    battle_tables = 0
    story_records = 0
    story_tables = 0
    battle_strings: set[str] = set()
    story_strings: set[str] = set()
    skipped_tables = 0

    for i in range(ld.files):
        try:
            content = ld.read(i)
        except Exception:
            continue
        if not is_datatable(content):
            continue
        blobs = parse_datatable(content)
        if len(blobs) < BATTLE_MIN:
            continue
        strings = []
        for b in blobs:
            if b is None:
                continue
            s = read_cstring(b)
            if not s or printable_ratio(s) < 0.5:
                continue
            strings.append(s)
        if len(strings) < BATTLE_MIN * 0.5:
            skipped_tables += 1
            continue

        if len(blobs) <= BATTLE_MAX:
            battle_tables += 1
            battle_records += len(strings)
            battle_strings.update(strings)
        else:
            story_tables += 1
            story_records += len(strings)
            story_strings.update(strings)

    return {
        "path": str(path),
        "total_entries": ld.files,
        "battle_tables": battle_tables,
        "battle_records": battle_records,
        "battle_per_file_uniques_avg": (len(battle_strings) / battle_tables) if battle_tables else 0,
        "battle_global_uniques": len(battle_strings),
        "story_tables": story_tables,
        "story_records": story_records,
        "story_global_uniques": len(story_strings),
        "skipped_tables": skipped_tables,
        "battle_strings": battle_strings,
        "story_strings": story_strings,
    }


def main():
    root = Path(r"F:\Games\Attack on Titan 2\LINKDATA\REGION")
    eu_backup = root / "LINKDATA_REGION_EU.BIN.he_backup"
    eu = eu_backup if eu_backup.exists() else root / "LINKDATA_REGION_EU.BIN"
    targets = [
        eu,
        root / "LINKDATA_REGION_JP.BIN",
        root / "LINKDATA_REGION_AS.BIN",
    ]
    all_battle: set[str] = set()
    all_story: set[str] = set()
    print("=" * 78)
    print("AoT2 — Phase-1 scope report (records / per-file uniques / GLOBAL uniques)")
    print("=" * 78)
    for t in targets:
        if not t.exists():
            print(f"\n(skip, missing) {t}")
            continue
        r = scan(t)
        print(f"\n{t.name}  ({r['total_entries']} archive entries)")
        print(f"  BATTLE TEXT tables : {r['battle_tables']}")
        print(f"    records          : {r['battle_records']}")
        print(f"    per-file uniques : ~{r['battle_per_file_uniques_avg']:.0f} avg/table")
        print(f"    GLOBAL uniques   : {r['battle_global_uniques']}")
        print(f"  STORY/DIALOGUE tables: {r['story_tables']}")
        print(f"    records          : {r['story_records']}")
        print(f"    GLOBAL uniques   : {r['story_global_uniques']}")
        print(f"  (skipped non-text tables: {r['skipped_tables']})")
        all_battle |= r["battle_strings"]
        all_story |= r["story_strings"]

    print("\n" + "=" * 78)
    print(f"CROSS-ARCHIVE GLOBAL unique battle strings : {len(all_battle)}")
    print(f"CROSS-ARCHIVE GLOBAL unique story strings  : {len(all_story)}")
    print(f"CROSS-ARCHIVE GLOBAL unique TOTAL          : {len(all_battle | all_story)}")
    print("=" * 78)
    print("NOTE: pure UI/menu chrome (New Game/Continue/Options/Save labels) was")
    print("searched for extensively across REGION_EU.BIN and NOT located — its")
    print("storage is still unknown. This report scopes ONLY what was confirmed:")
    print("battle-mission text + story/cutscene dialogue.")


if __name__ == "__main__":
    main()
