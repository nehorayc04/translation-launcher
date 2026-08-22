"""I/O helper — validate + merge your translations into hebrew.json. Does NOT translate.
Reads  : trans_part_1.json .. trans_part_4.json  ({id: hebrew} you wrote)
         to_translate.json (the English source, for tag validation)
Writes : hebrew.json (atomic update — only the CLEAN ids are merged)
Reports: any id that fails validation (fix that id in its trans_part file, re-run).
"""
import json, re, os
from collections import Counter

# every token/placeholder that MUST be preserved (same multiset in source & translation)
TOKEN = re.compile(
    r'\[CSS_[A-Z]+\]'              # [CSS_BLUE] [CSS_RED] [CSS_END] ...
    r'|\[[A-Z][A-Za-z0-9_]*\]'    # [RELOAD] [HIDEINCAR] [PLACEWAYPOINT] button/icon tokens
    r'|\{[^}]*\}'                  # {VALUE}
    r'|%[0-9.]*[diufslxX]+|%%'     # %d %s %ls %0.2f %%
    r'|&#?[A-Za-z0-9]+;')          # &#xA; &amp; &gt; &nbsp;
NIQQUD = re.compile(r'[֑-ׇ]')
BAD    = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿'
                    r'ऀ-ॿ一-鿿가-힯]')   # Arabic/Cyrillic/Greek/Thai/Deva/CJK/Hangul

src = json.load(open("to_translate.json", encoding="utf-8"))
merged = {}; problems = []
for i in range(1, 5):
    p = f"trans_part_{i}.json"
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    for k, he in d.items():
        en = src.get(k, "")
        if not he or not he.strip():
            problems.append((k, "EMPTY")); continue
        if Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(he)):
            problems.append((k, "TAG MISMATCH")); continue
        if BAD.search(he):
            problems.append((k, "FOREIGN SCRIPT")); continue
        if NIQQUD.search(he):
            problems.append((k, "NIQQUD")); continue
        merged[k] = he

if problems:
    for k, r in problems[:60]:
        print(f"{r} {k}: en={src.get(k,'')[:50]!r}")
    print(f"--- {len(problems)} problem ids — fix ONLY those in their trans_part file, re-run loop_merge ---")

if merged:
    heb = json.load(open("hebrew.json", encoding="utf-8"))
    heb.update(merged)
    tmp = "hebrew.json.tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, "hebrew.json")
    print(f"merged {len(merged)} clean -> hebrew.json (total {len(heb)})")
else:
    print("nothing merged")
