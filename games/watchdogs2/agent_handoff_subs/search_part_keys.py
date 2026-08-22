import json
for i in range(1, 5):
    b = json.load(open(f"batch_part{i}.json", encoding="utf-8"))
    if "688537" in b:
        print(f"Key 688537 is in batch_part{i}.json!")
        print(b["688537"])
        break
else:
    print("Key 688537 not found in any batch_part file.")
