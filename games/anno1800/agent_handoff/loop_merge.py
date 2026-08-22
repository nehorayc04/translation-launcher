"""I/O helper - validate + merge trans_part_*.json into hebrew.json. Does NOT translate.
Reads : trans_part_1.json .. trans_part_4.json  ({guid: hebrew} you wrote)
        to_translate.json (english source, for token validation)
Writes: hebrew.json (atomic - only the CLEAN ids are merged)
Reports: any id that fails validation (fix that id in its trans_part file, re-run).

Validation per id:
  - not empty
  - SAME multiset of tokens as the source (<br/>, [..nested..], %spec)  -> "TAG MISMATCH"
  - no foreign script (Arabic/Cyrillic/Greek/Thai/Devanagari/CJK/Hangul)  -> "FOREIGN SCRIPT"
  - no niqqud                                                            -> "NIQQUD"
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tokens import tokens  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NIQQUD = re.compile(r"[֑-ׇ]")
BAD = re.compile(r"[؀-ۿЀ-ӿͰ-Ͽ฀-๿"
                 r"ऀ-ॿ一-鿿가-힯]")

src = json.load(open("to_translate.json", encoding="utf-8"))
merged = {}
problems = []
for i in range(1, 5):
    p = f"trans_part_{i}.json"
    if not os.path.exists(p):
        continue
    for k, he in json.load(open(p, encoding="utf-8")).items():
        en = src.get(k, "")
        if not he or not he.strip():
            problems.append((k, "EMPTY"))
        elif Counter(tokens(en)) != Counter(tokens(he)):
            problems.append((k, "TAG MISMATCH"))
        elif BAD.search(he):
            problems.append((k, "FOREIGN SCRIPT"))
        elif NIQQUD.search(he):
            problems.append((k, "NIQQUD"))
        else:
            merged[k] = he

if problems:
    for k, r in problems[:60]:
        print(f"{r} {k}: en={src.get(k,'')[:60]!r}")
    print(f"--- {len(problems)} problem ids - fix ONLY those in their trans_part, re-run ---")
if merged:
    heb = json.load(open("hebrew.json", encoding="utf-8"))
    heb.update(merged)
    json.dump(heb, open("hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace("hebrew.json.tmp", "hebrew.json")
    print(f"merged {len(merged)} clean -> hebrew.json (total {len(heb)})")
else:
    print("nothing merged")
