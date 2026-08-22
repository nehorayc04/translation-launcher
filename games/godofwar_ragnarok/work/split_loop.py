# -*- coding: utf-8 -*-
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BATCH_F = os.path.join(HERE, "current_batch.json")

def main():
    if not os.path.exists(BATCH_F):
        print("current_batch.json does not exist!")
        return
    batch = json.load(open(BATCH_F, encoding="utf-8"))
    keys = sorted(batch.keys(), key=int)
    
    part_size = 125
    for i in range(4):
        part_keys = keys[i*part_size : (i+1)*part_size]
        part_data = {k: batch[k] for k in part_keys}
        part_file = f"batch_part{i+1}.json"
        with open(os.path.join(HERE, part_file), "w", encoding="utf-8") as f:
            json.dump(part_data, f, ensure_ascii=False, indent=2)
        print(f"Saved {part_file} with {len(part_data)} strings.")

if __name__ == "__main__":
    main()
