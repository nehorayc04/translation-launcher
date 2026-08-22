"""I/O helper — split current_batch.json into 4 parts of <=125. Does NOT translate.
Writes batch_part1.json .. batch_part4.json  ({id: english}, ids sorted).
"""
import json, math
b = json.load(open("current_batch.json", encoding="utf-8"))
keys = sorted(b, key=lambda x: int(x))
PARTS = 4
per = max(1, math.ceil(len(keys) / PARTS))
for i in range(PARTS):
    chunk = keys[i*per:(i+1)*per]
    d = {k: b[k] for k in chunk}
    json.dump(d, open(f"batch_part{i+1}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch_part{i+1}.json: {len(d)}")
