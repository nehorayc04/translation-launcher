import json
import re

batch = json.load(open("to_translate_batch.json", encoding="utf-8"))
trans = json.load(open("trans_part_1.json", encoding="utf-8"))

problem_ids = ["803501", "803523", "803524", "803548", "803588", "803623", "803656", "803658"]

for pid in problem_ids:
    print(f"ID: {pid}")
    print(f"EN: {repr(batch.get(pid))}")
    print(f"HE: {repr(trans.get(pid))}")
    print("-" * 40)
