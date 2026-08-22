"""Apply verified LQA fixes (from the wd2-sub-lqa-fix workflow) to hebrew.json.

Input : a JSON file = array of {pk, he, fixedHe}  (the workflow's `fixes`)
Guards (a fix is applied ONLY if all hold):
  * pk currently exists in hebrew.json
  * the current value still equals the reviewed `he` (no stale overwrite)
  * fixedHe preserves the SAME token/placeholder multiset as the current he
    (brackets incl. lowercase cue tokens, {tokens}, %specs, entities, literal \\n)
  * fixedHe has Hebrew, no foreign script, no niqqud
Writes hebrew.json (atomic) + syncs C:/tmp/wd2_sub_he.json.

Usage: python apply_lqa_fixes.py <fixes.json>
"""
import json, os, re, sys
from collections import Counter

HEB_F = "hebrew.json"
SYNC  = r"C:/tmp/wd2_sub_he.json"
PH = re.compile(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[diufslxeDIUFSLXE]+|%%|&#?[A-Za-z0-9]+;|' + re.escape(chr(92) + 'n'))
BAD = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')
NIQ = re.compile(r'[֑-ׇ]')
HEB = re.compile(r'[א-ת]')

def main():
    fixes = json.load(open(sys.argv[1], encoding="utf-8"))
    he = json.load(open(HEB_F, encoding="utf-8"))
    applied = 0; skip = {}
    for f in fixes:
        pk = str(f.get("pk", "")); cur = f.get("he", ""); fix = (f.get("fixedHe") or "").strip()
        if not pk or pk not in he:
            skip["no_pk"] = skip.get("no_pk", 0) + 1; continue
        if not fix:
            skip["empty_fix"] = skip.get("empty_fix", 0) + 1; continue
        if cur and he[pk] != cur:
            skip["stale"] = skip.get("stale", 0) + 1; continue
        if fix == he[pk]:
            skip["noop"] = skip.get("noop", 0) + 1; continue
        if Counter(PH.findall(fix)) != Counter(PH.findall(he[pk])):
            skip["token_mismatch"] = skip.get("token_mismatch", 0) + 1; continue
        if BAD.search(fix) or NIQ.search(fix) or not HEB.search(fix):
            skip["bad_fix"] = skip.get("bad_fix", 0) + 1; continue
        he[pk] = fix; applied += 1
    tmp = HEB_F + ".tmp"
    json.dump(he, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0); os.replace(tmp, HEB_F)
    json.dump({str(k): v for k, v in he.items()}, open(SYNC, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"applied {applied} fixes; skipped {sum(skip.values())} {skip}; hebrew.json now {len(he)}")

if __name__ == "__main__":
    main()
