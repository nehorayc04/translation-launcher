import json
import sys

batch = json.load(open("to_translate_batch.json", encoding="utf-8"))
items = list(batch.items())
total = len(items)

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end = int(sys.argv[2]) if len(sys.argv) > 2 else min(total, start + 50)

print(f"Showing items {start} to {end} out of {total}:")
for i in range(start, end):
    guid, val = items[i]
    print(f"[{i}] {guid} => {repr(val)}")
