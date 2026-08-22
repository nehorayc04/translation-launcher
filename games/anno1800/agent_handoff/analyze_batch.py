import json
from collections import Counter

batch = json.load(open("to_translate_batch.json", encoding="utf-8"))
c = Counter(batch.values())
print(f"Unique values count: {len(c)}")
for val, count in c.most_common(10):
    print(f"  {count} times: {val!r}")
