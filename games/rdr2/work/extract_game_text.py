#!/usr/bin/env python3
"""Harvest the game's OWN text (every language) out of the unpacked RDR2 tree.

Until now the corpus came from a public English dump that covered only 93.9% of the keys,
so anything it missed shipped in English -- which is exactly what the in-game screenshots
show. With the archives unpacked, the authoritative source is the game's own `.yldb`
language databases, and they come with all 13 professional translations for free.

Writes games/rdr2/extract/game_text/<lang>.json = {"0xHASH": "text"}.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yldb  # noqa: E402

GAME = os.environ.get(
    "RDR2_UNPACKED",
    r"C:\Users\Nehoray_Cohen\עוד - ללא סיכרון\Red Dead Redemption 2",
)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract", "game_text")


def main() -> None:
    # every <root>/**/lang/<language>_rel folder, in path order so a patch overrides base
    langs: dict[str, list[str]] = {}
    for dirpath, dirnames, _files in os.walk(GAME):
        if os.path.basename(dirpath).lower() != "lang":
            continue
        for d in sorted(dirnames):
            if d.lower().endswith("_rel"):
                langs.setdefault(d[:-4].lower(), []).append(os.path.join(dirpath, d))

    if not langs:
        print("no lang folders found -- is the tree unpacked?")
        raise SystemExit(1)

    os.makedirs(OUT, exist_ok=True)
    total = 0
    for lang, folders in sorted(langs.items()):
        merged: dict[int, str] = {}
        for f in folders:                      # later folder (update_N) wins
            merged.update(yldb.parse_dir(f))
        data = {f"0x{h:08X}": t for h, t in merged.items()}
        with open(os.path.join(OUT, lang + ".json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        total += len(data)
        print(f"  {lang:<14} {len(data):>8,} strings   ({len(folders)} folder(s))")
    print(f"\n{len(langs)} languages, {total:,} strings -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
