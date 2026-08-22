import json

with open("current_batch.json", encoding="utf-8") as f:
    d = json.load(f)

empty_keys = [k for k, v in d.items() if not v]
print(f"Total empty keys remaining: {len(empty_keys)}")

if empty_keys:
    print(json.dumps(empty_keys[:300], ensure_ascii=False, indent=4))
