import json
import os

skip = set(json.load(open("skip.json", encoding="utf-8")))

for i in range(1, 5):
    b = json.load(open(f"batch_part{i}.json", encoding="utf-8"))
    rem = [k for k in b if k not in skip]
    print(f"Part {i}: {len(rem)} keys remaining to translate.")
