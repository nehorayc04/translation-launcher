# -*- coding: utf-8 -*-
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
en = json.load(open(os.path.join(HERE, "english.json"), encoding="utf-8"))

# Find which part files contain these keys
keys_to_fix = ["102754", "102756", "102764", "102801", "102853"]

for i in range(1, 5):
    fn = f"trans_21_part_{i}.json"
    fp = os.path.join(HERE, fn)
    data = json.load(open(fp, encoding="utf-8"))
    for k in keys_to_fix:
        if k in data:
            print(f"{fn} KEY {k}:")
            print(f"  EN: {repr(en[k])}")
            print(f"  HE: {repr(data[k])}")
            print()
