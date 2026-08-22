# -*- coding: utf-8 -*-
"""Serve the next N gender/number-fix lines that aren't done yet -> current_batch.json.
Each = {id: {"en":..., "he":<current, WRONG gender/number>, "ar":<Arabic ground truth>,
             "target":"f"/"m"/"pl"}}.
The agent rewrites each id's value to the SAME Hebrew line but with the addressee
gender/number fixed to match the Arabic. Run:  python get_batch.py 40
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
tofix = json.load(open(os.path.join(HERE, "to_fix.json"), encoding="utf-8"))
try:
    done = json.load(open(os.path.join(HERE, "fixed.json"), encoding="utf-8"))
except Exception:
    done = {}
todo = {k: v for k, v in tofix.items() if k not in done}
batch = dict(list(todo.items())[:N])
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"served {len(batch)} | remaining {len(todo)} | done {len(done)}/{len(tofix)}")
if not batch:
    print("All done!")
