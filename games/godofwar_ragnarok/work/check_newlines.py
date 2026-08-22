# -*- coding: utf-8 -*-
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
en = json.load(open(os.path.join(HERE, "english.json"), encoding="utf-8"))

for fn in ["trans_21_part_1.json", "trans_21_part_2.json", "trans_21_part_3.json", "trans_21_part_4.json"]:
    fp = os.path.join(HERE, fn)
    if not os.path.exists(fp):
        print(f"{fn} does not exist")
        continue
    data = json.load(open(fp, encoding="utf-8"))
    mismatches = 0
    for k, v in data.items():
        if k not in en:
            continue
        en_m = len(list(re.finditer(r"(\n|\\\\n)+", en[k])))
        he_m = len(list(re.finditer(r"(\n|\\\\n)+", v)))
        if en_m != he_m:
            mismatches += 1
            print(f"{fn} key={k}: EN newlines={en_m}, HE newlines={he_m}")
    if mismatches == 0:
        print(f"{fn}: OK ({len(data)} keys)")
    else:
        print(f"{fn}: {mismatches} mismatches")
