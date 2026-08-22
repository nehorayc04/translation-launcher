"""I/O helper - emit the next 400 UNtranslated strings. Does NOT translate.
Reads : to_translate.json {guid: english}   hebrew.json {guid: hebrew}
        skip.json [guid,...] = untranslatable-by-design (pure data-binds / codes /
        numbers); treated as done so the loop can reach "All done!".
Writes: current_batch.json {guid: english}  (next 400 not yet done)
Prints: "All done!" when nothing remains.
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIZE = 400
to = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()

rem = sorted([k for k in to if k not in heb and k not in skip], key=lambda x: int(x))
if not rem:
    print("All done!")
else:
    batch = {k: to[k] for k in rem[:SIZE]}
    json.dump(batch, open("current_batch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch: {len(batch)} written  (remaining {len(rem)})")
