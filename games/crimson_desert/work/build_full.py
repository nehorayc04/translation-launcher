#!/usr/bin/env python3
"""build_full.py - deploy the fleet's CURRENT translated corpus into the live game.

LOCAL-ONLY partial/incremental build (whatever fraction of the fleet has banked so far).
No revert needed first: every key the fleet translates is a REAL paloc key (the fleet reads
the actual gamedata/localizationstring_eng.paloc, never a synthetic one), so patching them
here naturally overwrites any leftover Phase-1 proof test-content (markers/alphabet/etc.) on
whichever keys the proof happened to reuse -- they're ordinary duplicate-instance menu keys,
same ones the fleet also translates. Untranslated keys (the other ~70% right now) are left
at their original English value; only what's actually banked gets patched.

Bidi: this engine does ZERO reordering (confirmed in-game via the Phase-1 LOGICAL/VISUAL A/B
proof) -> every Hebrew value must be pre-reversed (store-VISUAL) before it is written.

Usage:
    build_full.py             deploy whatever's in fleet/hebrew.json right now
    build_full.py --dry-run   parse + transform + report, write nothing
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)                       # games/crimson_desert
FLEET_DIR = os.path.join(GAME_DIR, "fleet")

sys.path.insert(0, os.path.join(GAME_DIR, "tools"))
import cd_container as cd  # noqa: E402
from bidi.algorithm import get_display  # noqa: E402

GAME_ROOT = r"C:\Games\Crimson Desert"
LOC_GROUP = "0020"
LOC_FILENAME = "localizationstring_eng.paloc"
HEBREW_JSON = os.path.join(FLEET_DIR, "hebrew.json")


def visual(s: str) -> str:
    return get_display(s, base_dir="R")


def main():
    dry = "--dry-run" in sys.argv

    heb = json.load(open(HEBREW_JSON, encoding="utf-8"))
    print(f"fleet/hebrew.json: {len(heb):,} banked entries")

    # strip the "ui:"/"dialogue:" kind prefix -> the real paloc key
    replacements = {}
    for k, v in heb.items():
        if v.get("iss") != "ok":
            continue
        real_key = k.split(":", 1)[1] if ":" in k else k
        replacements[real_key] = visual(v["he"])

    print(f"  -> {len(replacements):,} unique paloc keys to patch (store-VISUAL applied)")

    if dry:
        sample = list(replacements.items())[:5]
        for k, v in sample:
            print(f"   {k}  ->  {v!r}")
        print("(dry-run, nothing written)")
        return

    result = cd.patch_paloc_values(GAME_ROOT, LOC_GROUP, LOC_FILENAME, replacements)
    print(f"success={result.success}")
    print(f"message={result.message}")
    print(f"paz_crc={result.paz_crc}  pamt_crc={result.pamt_crc}  papgt_crc={result.papgt_crc}")
    if result.errors:
        print(f"errors ({len(result.errors)}):")
        for e in result.errors[:20]:
            print(f"   {e}")
        if len(result.errors) > 20:
            print(f"   ... +{len(result.errors) - 20} more")

    # read-back verify: re-parse the LIVE file, spot-check a random sample
    pamt = cd.parse_pamt(os.path.join(GAME_ROOT, LOC_GROUP, "0.pamt"),
                          paz_dir=os.path.join(GAME_ROOT, LOC_GROUP))
    want = f"gamedata/localizationstring_{'eng'}.paloc"
    entry = next(e for e in pamt.file_entries if e.path.lower() == want)
    entries = cd.parse_paloc(cd.read_file(entry))
    by_key = {e.key: e.value for e in entries}

    import random
    sample_keys = random.sample(list(replacements.keys()), min(10, len(replacements)))
    ok = 0
    for k in sample_keys:
        live = by_key.get(k)
        expect = replacements[k]
        match = live == expect
        ok += match
        print(f"   verify {k}: {'OK' if match else 'MISMATCH'}  live={live!r}")
    print(f"verify: {ok}/{len(sample_keys)} spot-checked keys match")
    print(f"paloc total entries after patch: {len(entries):,}")


if __name__ == "__main__":
    main()
