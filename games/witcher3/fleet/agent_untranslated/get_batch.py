# -*- coding: utf-8 -*-
"""Serve the next N untranslated W3 subtitle lines (still showing Arabic in-game) -> current_batch.json.
Each = {id: {"en":.., "ar":.., "ru":.., "gender":"f"/"m"/"pl"/""}}. Translate "en" into Hebrew.
Run:  python get_batch.py 40   (use 15 for long paragraphs)
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
tob = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
try:
    done = json.load(open(os.path.join(HERE, "hebrew_out.json"), encoding="utf-8"))
except Exception:
    done = {}
todo = {k: v for k, v in tob.items() if k not in done}
batch = dict(list(todo.items())[:N])
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"served {len(batch)} | remaining {len(todo)} | done {len(done)}/{len(tob)}")
if not batch:
    print("All done!")
