import json

with open("to_translate_batch.json", encoding="utf-8") as f:
    to_trans = json.load(f)

with open("trans_part_1.json", encoding="utf-8") as f:
    trans = json.load(f)

missing = set(to_trans.keys()) - set(trans.keys())
print(f"Missing {len(missing)} translations from the current batch:")
for k in sorted(list(missing)):
    print(f'"{k}": "{to_trans[k]}",')
