"""QA loop — validate + apply YOUR corrections, then mark the batch reviewed.
Does NOT translate.
Reads  : qa_fixes.json  {pk: corrected_hebrew}   (ONLY the lines you decided to change)
         qa_batch.json   (the batch you just reviewed — every pk here is marked reviewed)
         hebrew.json, to_translate.json
Writes : hebrew.json (atomic — only CLEAN corrections merged)
         qa_reviewed.json (adds every pk in qa_batch.json — fixed AND left-as-is — so the loop advances)
Reports: any correction rejected by validation (fix it in qa_fixes.json + re-run), then
         DELETE qa_fixes.json before the next batch.
"""
import json, os, re
from collections import Counter

TOKEN = re.compile(
    r'\[[A-Za-z0-9_]+\]|\{[^}]*\}'
    r'|%[0-9.]*[diufslxeDIUFSLXE]+|%%|&#?[A-Za-z0-9]+;'
    + r'|' + re.escape(chr(92) + 'n'))     # also require the literal \n line-break to be preserved
NIQQUD = re.compile(r'[֑-ׇ]')
BAD    = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')
HEB    = re.compile(r'[א-ת]')

to  = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
fixes = json.load(open("qa_fixes.json", encoding="utf-8")) if os.path.exists("qa_fixes.json") else {}
batch = json.load(open("qa_batch.json", encoding="utf-8")) if os.path.exists("qa_batch.json") else []

merged = 0; problems = []
for pk, new in fixes.items():
    pk = str(pk)
    if pk not in heb:
        problems.append((pk, "UNKNOWN PK")); continue
    if not new or not new.strip():
        problems.append((pk, "EMPTY")); continue
    cur = heb[pk]
    # the correction must preserve the line's token multiset (tokens + literal \n)
    if Counter(TOKEN.findall(cur)) != Counter(TOKEN.findall(new)):
        problems.append((pk, "TAG/LINEBREAK MISMATCH vs current")); continue
    if BAD.search(new):
        problems.append((pk, "FOREIGN SCRIPT")); continue
    if NIQQUD.search(new):
        problems.append((pk, "NIQQUD")); continue
    if not HEB.search(new) and HEB.search(cur):
        problems.append((pk, "LOST ALL HEBREW")); continue
    heb[pk] = new; merged += 1

if problems:
    for pk, r in problems[:60]:
        print(f"{r} {pk}: en={to.get(pk,'')[:50]!r}")
    print(f"--- {len(problems)} rejected — fix ONLY those in qa_fixes.json, re-run qa_merge ---")

if merged:
    tmp = "hebrew.json.tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0); os.replace(tmp, "hebrew.json")
    # keep the canonical mirror in sync for the build
    try:
        json.dump({str(k): v for k, v in heb.items()}, open(r"C:/tmp/wd2_sub_he.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    except OSError:
        pass

# mark the whole batch reviewed (fixed + unchanged) so the loop advances
reviewed = set(json.load(open("qa_reviewed.json", encoding="utf-8"))) if os.path.exists("qa_reviewed.json") else set()
for row in batch:
    reviewed.add(str(row["pk"]))
json.dump(sorted(reviewed, key=lambda x: int(x)), open("qa_reviewed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"merged {merged} corrections; batch of {len(batch)} marked reviewed (total reviewed {len(reviewed)})")
