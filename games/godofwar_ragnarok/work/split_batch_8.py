# -*- coding: utf-8 -*-
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EN_F = os.path.join(HERE, "english.json")
IDS_F = os.path.join(HERE, "prompts", "batch_003_ids.json")

def main():
    en = json.load(open(EN_F, encoding="utf-8"))
    ids = json.load(open(IDS_F, encoding="utf-8"))
    
    # Get the English strings
    batch_data = []
    for k in ids:
        batch_data.append([k, en[k]])
        
    print(f"Loaded {len(batch_data)} strings from batch_003")
    
    # Split into 4 parts of 125 each
    part_size = 125
    for i in range(4):
        part = batch_data[i*part_size : (i+1)*part_size]
        part_file = f"batch_8_part{i+1}.json"
        with open(part_file, "w", encoding="utf-8") as f:
            json.dump(part, f, ensure_ascii=False, indent=2)
        print(f"Saved {part_file} with {len(part)} strings.")

if __name__ == "__main__":
    main()
