import json
for i in range(1, 5):
    b = json.load(open(f"batch_part{i}.json", encoding="utf-8"))
    keys = sorted([int(k) for k in b])
    print(f"Part {i}: {len(keys)} keys from {keys[0]} to {keys[-1]}")
