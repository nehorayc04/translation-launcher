# -*- coding: utf-8 -*-
"""I/O helper — emit the next batch of un-translated ids. Does NOT translate.
Reads  : to_translate.json {id: {kind, en, current_he}}   hebrew_fixes.json {id: hebrew}
Writes : current_batch.json {id: {kind, en, current_he}}  (next SIZE ids not yet done)
Prints : "All done!" when nothing remains.
"""
import json, os
SIZE = 30
HERE = os.path.dirname(os.path.abspath(__file__))
to  = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
heb_path = os.path.join(HERE, "hebrew_fixes.json")
heb = json.load(open(heb_path, encoding="utf-8")) if os.path.exists(heb_path) else {}
skip_path = os.path.join(HERE, "skip.json")
skip = set(json.load(open(skip_path, encoding="utf-8"))) if os.path.exists(skip_path) else set()
rem = sorted(k for k in to if k not in heb and k not in skip)
if not rem:
    print("All done!")
else:
    batch = {k: to[k] for k in rem[:SIZE]}
    json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
               ensure_ascii=False, indent=1)
    print(f"batch: {len(batch)} written to current_batch.json  (remaining {len(rem)})")
