"""I/O helper - split current_batch.json into 4 parts. Does NOT translate.
Writes batch_part1.json .. batch_part4.json  ({guid: english}, ids sorted).
"""
import json
import math
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

b = json.load(open("current_batch.json", encoding="utf-8"))
keys = sorted(b, key=lambda x: int(x))
PARTS = 4
per = max(1, math.ceil(len(keys) / PARTS))
for i in range(PARTS):
    chunk = keys[i * per:(i + 1) * per]
    json.dump({k: b[k] for k in chunk}, open(f"batch_part{i+1}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
print(f"split {len(keys)} into {PARTS} parts")
