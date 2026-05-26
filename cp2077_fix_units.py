"""
cp2077_fix_units.py
===================
Small deterministic base-game text corrections (no LM):

1. Save-screen playtime — the hour/minute unit labels were over-translated
   (`UI-Labels-Units-Hours` h->ה, `UI-Labels-Units-Minutes` m->מ), so the
   playtime read "11ה 5מ". The user wants the English letters: "11H 5M".
   -> Hours = "H", Minutes = "M".

2. "rămaining" contamination — "Time Remaining" was rendered "זמן rămaining"
   (a Latin-extended `ă` leaked in). Fix the contaminated word in place:
   "rămaining" -> "שנותר".

Applied to both onscreens.json and onscreens_final.json. Atomic write.

Run: python cp2077_fix_units.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cp2077_qa_defects as qa

TRANSLATED = qa.TRANSLATED_FILE

# secondaryKey suffix -> exact femaleVariant to set
UNIT_FIXES = {
    "UI-Labels-Units-Hours":   "H",
    "UI-Labels-Units-Minutes": "M",
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)

    units = remaining = 0
    for section in ("onscreens/onscreens.json", "onscreens/onscreens_final.json"):
        for e in translated.get(section, []):
            if not isinstance(e, dict):
                continue
            sk = e.get("secondaryKey") or ""
            fv = e.get("femaleVariant")

            # 1. playtime unit labels
            for suffix, want in UNIT_FIXES.items():
                if sk.endswith(suffix) and fv != want:
                    print(f"  units [{section.split('/')[-1]}:{e.get('primaryKey')}]"
                          f"  {sk[-26:]}  {fv!r} -> {want!r}")
                    if not dry:
                        e["femaleVariant"] = want
                    units += 1

            # 2. rămaining contamination — fix the word in place
            if isinstance(fv, str) and "rămaining" in fv:
                new = fv.replace("rămaining", "שנותר")
                print(f"  remain [{section.split('/')[-1]}:{e.get('primaryKey')}]"
                      f"  {fv!r} -> {new!r}")
                if not dry:
                    e["femaleVariant"] = new
                remaining += 1
            mv = e.get("maleVariant")
            if isinstance(mv, str) and "rămaining" in mv:
                if not dry:
                    e["maleVariant"] = mv.replace("rămaining", "שנותר")
                remaining += 1

    print(f"\n{'[dry-run] ' if dry else ''}unit-label fixes: {units}   "
          f"rămaining fixes: {remaining}")
    if (units or remaining) and not dry:
        qa.atomic_write_json(TRANSLATED, translated)
        print(f"wrote {TRANSLATED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
