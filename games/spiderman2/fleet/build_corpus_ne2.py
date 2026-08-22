# -*- coding: utf-8 -*-
"""review_corpus/*.final.jsonl -> corpus.json  {id: row}, the shape sm2ne2_nim.py consumes.
Subtitles first: they are the story the player reads, so a partial pass covers what matters.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "corpus.json")
rows = {}
for kind in ("subtitles", "dialogue"):          # visibility order, not glob order
    p = os.path.join(HERE, "review_corpus", f"{kind}.final.jsonl")
    if not os.path.exists(p):
        continue
    for line in open(p, encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            rows[d["id"]] = d
tmp = OUT + ".tmp"
json.dump(rows, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, OUT)
print(f"corpus.json: {len(rows):,} rows")
