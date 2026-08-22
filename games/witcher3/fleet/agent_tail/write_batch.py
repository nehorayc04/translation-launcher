#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

translations = {
 "1085899": "יוצרים: 1C-SOFTCLUB, SNOWBALL STUDIOS", # Replaced Cyrillic С with Latin C
}

with open("current_batch.json", "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, indent=1)
print("Written OK:", len(translations), "entries")
