import json
with open("current_batch.json", "r", encoding="utf-8") as f:
    original = json.load(f)

for k in original:
    if not original[k]:
        original[k] = k

with open("current_batch.json", "w", encoding="utf-8") as f:
    json.dump(original, f, ensure_ascii=False, indent=4)
