# -*- coding: utf-8 -*-
"""I/O helper — validate + merge your translations into hebrew_fixes.json. Does NOT
translate.
Reads  : trans_batch.json  ({id: full_hebrew_value} you wrote — the COMPLETE value for
         that key, not just the missing part)
         to_translate.json (source, for tag/token validation)
Writes : hebrew_fixes.json (atomic — only CLEAN ids merged)
Reports: any id that fails validation. Fix ONLY that id in trans_batch.json, re-run.
"""
import json, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# same token set the review fleet + apply_ne2_review.py already enforce for this corpus:
# <ts="a;b"> timing tags, &rlm;/&amp;/other entities, {VALUE}, [NAME ICON] portrait
# selectors, [ALLCAPS_TOKEN] engine tokens (incl. <br>/<br/> via the first alternative).
STRUCT = re.compile(r'<[^<>]{1,120}>|&[a-zA-Z]{2,8};|\{[^{}]{0,80}\}'
                    r'|\[[A-Z][A-Z0-9_]* ICON\]|\[[A-Z0-9_]{1,40}\]|%[#0-9.*+-]*[a-zA-Z]')
NIQQUD = re.compile(r'[֑-ׇ]')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿'
                     r'ऀ-ॿ一-鿿가-힣]')  # Arabic/Cyrillic/Greek/Thai/Deva/CJK/Hangul
HEB = re.compile('[א-ת]')

src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
batch_path = os.path.join(HERE, "trans_batch.json")
if not os.path.exists(batch_path):
    print("trans_batch.json not found — write your translations there first."); raise SystemExit(1)
batch = json.load(open(batch_path, encoding="utf-8"))

merged = {}; problems = []
for k, he in batch.items():
    info = src.get(k)
    if info is None:
        problems.append((k, "UNKNOWN_ID")); continue
    en = info["en"]
    if not isinstance(he, str) or not he.strip():
        problems.append((k, "EMPTY")); continue
    if not HEB.search(he):
        problems.append((k, "NO_HEBREW")); continue
    if Counter(STRUCT.findall(en)) != Counter(STRUCT.findall(he)):
        problems.append((k, f"TOKEN_MISMATCH en_tokens={STRUCT.findall(en)} he_tokens={STRUCT.findall(he)}"))
        continue
    if FOREIGN.search(STRUCT.sub(' ', he)):
        problems.append((k, "FOREIGN_SCRIPT")); continue
    if NIQQUD.search(he):
        problems.append((k, "NIQQUD")); continue
    # for a subtitle_segment fix, the PRE-EXISTING translated segments must stay
    # byte-identical -- only the previously-English segment(s) may differ.
    if info["kind"] == "subtitle_segment":
        cur = info["current_he"]
        TS = re.compile(r'<ts="[^"]*">')
        cur_segs = TS.split(cur)
        new_segs = TS.split(he)
        if len(cur_segs) != len(new_segs):
            problems.append((k, "SEGMENT_COUNT_CHANGED")); continue
        changed = sum(1 for a, b in zip(cur_segs, new_segs) if a.strip() != b.strip())
        if changed == 0:
            problems.append((k, "NOTHING_CHANGED")); continue
    merged[k] = he

if problems:
    for k, r in problems[:80]:
        print(f"{r[:14]:14} {k}")
        if len(r) > 14:
            print(f"   {r}")
    print(f"--- {len(problems)} problem ids — fix ONLY those in trans_batch.json, re-run merge_batch.py ---")

if merged:
    out_path = os.path.join(HERE, "hebrew_fixes.json")
    heb = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    heb.update(merged)
    tmp = out_path + ".tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)
    print(f"merged {len(merged)} clean -> hebrew_fixes.json (total {len(heb)})")
else:
    print("nothing merged")
