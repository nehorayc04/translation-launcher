import json
import re

current_batch = json.load(open("current_batch.json", encoding="utf-8"))

phone_keys = []
for k, v in current_batch.items():
    if "-" in v and any(char.isdigit() for char in v):
        phone_keys.append((k, v))

print(f"Total matching phone-like keys: {len(phone_keys)}")
for k, v in phone_keys[:10]:
    print(f"  {k}: {repr(v)}")
