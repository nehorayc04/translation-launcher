# -*- coding: utf-8 -*-
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EN_F = os.path.join(HERE, "english.json")
AR_F = os.path.join(HERE, "arabic.json")
HEB_F = os.path.join(HERE, "hebrew.json")

def main():
    en = json.load(open(EN_F, encoding="utf-8"))
    ar = json.load(open(AR_F, encoding="utf-8"))
    heb = json.load(open(HEB_F, encoding="utf-8"))
    
    # Get all untranslated keys starting from 64016
    untrans = [k for k in sorted(ar.keys(), key=int) if int(k) >= 64016 and k not in heb and k in en]
    
    # We want 500 keys for batch 9
    batch_keys = untrans[:500]
    print(f"Total untranslated: {len(untrans)}. Selected first {len(batch_keys)} for Batch 9.")
    print(f"Batch 9 key range: {batch_keys[0]} to {batch_keys[-1]}")
    
    # Split into 4 parts of 125 each
    part_size = 125
    for i in range(4):
        part_keys = batch_keys[i*part_size : (i+1)*part_size]
        part_data = [[k, en[k]] for k in part_keys]
        part_file = f"batch_9_part{i+1}.json"
        with open(os.path.join(HERE, part_file), "w", encoding="utf-8") as f:
            json.dump(part_data, f, ensure_ascii=False, indent=2)
        print(f"Saved {part_file} with {len(part_data)} strings.")

if __name__ == "__main__":
    main()
