# -*- coding: utf-8 -*-
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
part3 = json.load(open(os.path.join(HERE, "batch_part3.json"), encoding="utf-8"))

with open(os.path.join(HERE, "part3_keys.txt"), "w", encoding="utf-8") as f:
    for k, v in sorted(part3.items(), key=lambda x: int(x[0])):
        f.write(f"{k}: {repr(v)}\n")

