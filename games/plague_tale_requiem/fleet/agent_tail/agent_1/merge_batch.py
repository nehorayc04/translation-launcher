#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate + merge THIS agent's batch into its own fleet bank (../../banks/out_agent1.json).
The fleet pull folds every ../../banks/out_*.json into hebrew.json -> the site dashboard moves.
LOGICAL Hebrew (RTL baked later). Anti-cheat: no foreign/niqqud, {STR_}/|/% token multiset must match,
real English prose must be translated (bare name/code copy allowed)."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.abspath(os.path.join(HERE, "..", ".."))
TT = os.path.join(HERE, "to_translate.json")
BATCH = os.path.join(HERE, "current_batch.json")
BANKS = os.path.join(FLEET, "banks")
MYBANK = os.path.join(BANKS, "out_agent1.json")
STRUCT  = re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')
NIQ = re.compile(r'[֑-ׇ]')
HEB = re.compile(r'[א-ת]')
LOWERW = re.compile(r'[a-z]{2,}')
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def is_namey(en):
    core = STRUCT.sub(" ", en).strip()
    if not LOWERW.search(core): return True
    words = re.findall(r"[A-Za-z']+", core)
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)
def valid(he, en):
    if not he or not he.strip(): return False, "empty"
    if FOREIGN.search(he): return False, "foreign-script"
    if NIQ.search(he): return False, "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)): return False, "token-mismatch"
    if not HEB.search(he):
        if he.strip() == en.strip() and is_namey(en): return True, "name-passthrough"
        return False, "no-hebrew"
    return True, "ok"
def main():
    tt = load(TT, {}); batch = load(BATCH, {})
    if not batch:
        print("No current_batch.json - run get_batch.py first."); return
    os.makedirs(BANKS, exist_ok=True)
    mine = load(MYBANK, {}); merged = skipped = 0; reasons = {}
    for k, v in batch.items():
        if k not in tt: continue
        he = v.get("he") if isinstance(v, dict) else v
        he = (he or "").strip()
        he = NIQ.sub("", he).replace("‎", "").replace("‏", "").replace("​", "")
        ok, why = valid(he, tt[k]["en"])
        if ok: mine[k] = he; merged += 1
        else: skipped += 1; reasons[why] = reasons.get(why, 0) + 1
    tmp = MYBANK + ".tmp"
    json.dump(mine, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, MYBANK)
    remaining = sum(1 for k in tt if k not in mine)
    print("merged %d, rejected %d  %s" % (merged, skipped, reasons if reasons else ""))
    print("%s now %d  (~%d of this slot left). The fleet pull (~3 min) folds it into hebrew.json." % ("out_agent1.json", len(mine), remaining))
    if remaining == 0: print("All done! This slot is fully translated.")
if __name__ == "__main__": main()
