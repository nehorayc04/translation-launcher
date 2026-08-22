"""I/O helper — emit the next 500 UNtranslated SUBTITLE strings. Does NOT translate.
Reads  : to_translate.json {id: english}   hebrew.json {id: hebrew}
Writes : current_batch.json {id: english}  (next 500 ids not yet in hebrew.json)
Prints : "All done!" when nothing remains.
"""
import json, os
SIZE = 1500
to  = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
# skip.json = ids that are UNtranslatable by design (handles / leetspeak / code /
# foreign-language song or place names) — they stay Latin in-game. Counted as "done".
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()
rem = sorted([k for k in to if k not in heb and k not in skip], key=lambda x: int(x))
if not rem:
    print("All done!")
else:
    batch = {k: to[k] for k in rem[:SIZE]}
    json.dump(batch, open("current_batch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch: {len(batch)} written to current_batch.json  (remaining {len(rem)})")
