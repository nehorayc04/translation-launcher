import json
import os
import sys

HERE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\gtav\agent_handoff_update2"
sys.path.insert(0, HERE)
from _tokens import real_word

src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
skip = json.load(open(os.path.join(HERE, "skip.json"), encoding="utf-8"))

real_word_skips = []
for k in skip:
    if k in src:
        en = src[k]
        if real_word(en):
            real_word_skips.append((k, en))

print(f"Total skips in to_translate: {sum(1 for k in skip if k in src)}")
print(f"Skips with real words: {len(real_word_skips)}")
print("First 40 real-word skips:")
for k, en in real_word_skips[:40]:
    print(f"  {k}: {en}")
