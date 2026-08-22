#!/usr/bin/env python3
"""Deterministic UI corrections for the RDR2 Hebrew mod (no LLM, one right answer each).

Every entry here was found by reading the game's OWN template strings, not by guessing at
the rendered result:

* `TIME_AND_TEMP_*` is the HUD clock template and ships as `~1~:~2~~3~ | ~4~°C` — the
  time and the AM/PM token are ADJACENT with no separator. In English "12:56PM" reads
  acceptably; with a 5-character Hebrew label it renders as `אחה"צ12:56`, which is what the
  screenshot shows. The gap belongs in the TEMPLATE, not in the label.
* `AM` was left as the Latin "AM" (a 2-letter token reads as a code to a translator) while
  `PM` was translated — so the clock switched language at noon.

Idempotent: re-running changes nothing. Backs up hebrew.json first.
"""
from __future__ import annotations

import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SPINE = os.path.join(HERE, "hebrew.json")

# key -> exact replacement value (LOGICAL Hebrew; the visual bake happens at build time)
# TWO spaces, not one: the user asked for a bigger gap than they saw, and what they saw was
# ZERO (the shipped template has none). A Hebrew label butting against a digit crowds harder
# than a Latin one, and this is a short right-aligned corner element — one extra space cannot
# push anything off screen. The interior run survives the visual bake (only EDGE whitespace
# is stripped per segment).
FIXES = {
    "AM": 'לפנה"צ',
    "TIME_AND_TEMP_C": "~1~:~2~  ~3~ | ~4~°C",
    "TIME_AND_TEMP_F": "~1~:~2~  ~3~ | ~4~°F",
}


def main() -> None:
    heb = json.load(open(SPINE, encoding="utf-8"))
    changed = {}
    for k, v in FIXES.items():
        if k in heb and heb[k] != v:
            changed[k] = (heb[k], v)
            heb[k] = v
        elif k not in heb:
            changed[k] = ("<absent>", v)
            heb[k] = v

    if not changed:
        print("nothing to do (already applied)")
        return

    shutil.copy2(SPINE, SPINE + f".bak.uifix2.{int(time.time())}")
    tmp = SPINE + ".tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, SPINE)
    for k, (old, new) in changed.items():
        print(f"  {k:<20} {old!r} -> {new!r}")
    print(f"{len(changed)} fix(es) applied")


if __name__ == "__main__":
    main()
