import json
b = json.load(open("current_batch.json", encoding="utf-8"))
fives = [k for k, v in b.items() if "555" in v]
print(f"Total keys containing 555: {len(fives)}")
if fives:
    print("Example:", fives[0], b[fives[0]])
