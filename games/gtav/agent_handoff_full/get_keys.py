import json

with open("current_batch.json", encoding="utf-8") as f:
    d = json.load(f)

print("data = {")
for i, k in enumerate(list(d.keys())[:1500]):
    print(f"    {json.dumps(k, ensure_ascii=False)}: \"\",")
print("}")
