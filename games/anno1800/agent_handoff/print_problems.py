import glob, json, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tokens import tokens

src = json.load(open("to_translate.json", encoding="utf-8"))
problems = []
for p in sorted(glob.glob("trans_part_*.json")):
    data = json.load(open(p, encoding="utf-8"))
    for k, he in data.items():
        en = src.get(k, "")
        if Counter(tokens(en)) != Counter(tokens(he)):
            problems.append((k, en, he))

for k, en, he in problems:
    print(f"Key: {k}")
    print(f"EN: {en}")
    print(f"HE: {he}")
    print(f"EN tokens: {Counter(tokens(en))}")
    print(f"HE tokens: {Counter(tokens(he))}")
    print("-" * 40)
