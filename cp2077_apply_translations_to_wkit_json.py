"""
cp2077_apply_translations_to_wkit_json.py
==========================================
Safely applies our Hebrew translations to a WolvenKit-decoded text JSON.

Only modifies femaleVariant / maleVariant fields where the entry's primaryKey
matches one in localization_translated.json. Touches NO metadata, NO indices,
NO headers — just the two text fields per entry.

Usage:
    python cp2077_apply_translations_to_wkit_json.py <wkit_json_path> <archive_relpath>

Example:
    python cp2077_apply_translations_to_wkit_json.py /tmp/cr2w_pipeline/text_json/onscreens.json.json onscreens/onscreens.json
"""

import json
import sys
import os

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TRANSLATED_JSON = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources\localization_translated.json"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    wkit_json_path = sys.argv[1]
    archive_relpath = sys.argv[2]

    print(f"Loading WolvenKit text JSON: {wkit_json_path}")
    with open(wkit_json_path, "r", encoding="utf-8") as f:
        wkit = json.load(f)

    print(f"Loading translations: {TRANSLATED_JSON}")
    with open(TRANSLATED_JSON, "r", encoding="utf-8") as f:
        all_trans = json.load(f)

    if archive_relpath not in all_trans:
        print(f"[!] {archive_relpath} not found in translations JSON")
        sys.exit(1)

    trans_entries = all_trans[archive_relpath]
    print(f"  {len(trans_entries):,} translated entries available for {archive_relpath}")

    # Build lookup keyed by primaryKey (handle both int and string forms)
    trans_lookup = {}
    for e in trans_entries:
        pk = e.get("primaryKey", 0)
        trans_lookup[str(pk)] = e
        trans_lookup[int(pk) if isinstance(pk, str) and pk.isdigit() else pk] = e

    # Navigate to the entries array in the WolvenKit structure
    try:
        entries = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except (KeyError, TypeError) as ex:
        print(f"[!] Unexpected JSON structure: {ex}")
        sys.exit(1)

    print(f"  {len(entries):,} entries in WolvenKit JSON")

    matched = 0
    fv_updated = 0
    mv_updated = 0
    unchanged = 0

    for entry in entries:
        pk = entry.get("primaryKey")
        if pk is None:
            continue
        # Try string lookup first (WolvenKit stores pk as string)
        t = trans_lookup.get(str(pk)) or trans_lookup.get(pk)
        if not t:
            continue
        matched += 1
        new_fv = t.get("femaleVariant", "")
        new_mv = t.get("maleVariant", "")
        if new_fv and new_fv != entry.get("femaleVariant", ""):
            entry["femaleVariant"] = new_fv
            fv_updated += 1
        if new_mv and new_mv != entry.get("maleVariant", ""):
            entry["maleVariant"] = new_mv
            mv_updated += 1
        if (new_fv == entry.get("femaleVariant", "")) and (new_mv == entry.get("maleVariant", "")):
            unchanged += 1

    print(f"  Matched primary keys: {matched:,}")
    print(f"  femaleVariant updated: {fv_updated:,}")
    print(f"  maleVariant updated:   {mv_updated:,}")

    print(f"Saving modified JSON in place...")
    with open(wkit_json_path, "w", encoding="utf-8") as f:
        json.dump(wkit, f, ensure_ascii=False, indent=2)

    size_after = os.path.getsize(wkit_json_path)
    print(f"  [OK] Saved ({size_after:,} bytes)")


if __name__ == "__main__":
    main()
