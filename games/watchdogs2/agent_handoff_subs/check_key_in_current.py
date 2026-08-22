import json
current = json.load(open("current_batch.json", encoding="utf-8"))
print("688537" in current)
if "688537" in current:
    print(current["688537"])
else:
    # Print the sorted keys of current to see what they are
    keys = sorted(list(current.keys()), key=lambda x: int(x))
    print(f"Total keys in current: {len(keys)}")
    print(f"First key: {keys[0]}, Last key: {keys[-1]}")
