#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the agent's Arabic->Hebrew batch and merge into hebrew.json.

Rejected (line stays queued) if:
  * empty
  * NO Hebrew letters (must actually translate to Hebrew)
  * ANY Arabic letter left (didn't copy/leave the source)
  * mojibake (CJK/Hangul/PUA)
  * Hebrew niqqud (auto-stripped first, so this only fires on leftovers)
  * STRUCT token multiset (<tags>, {..}, %spec, &ent;) differs from the Arabic source
Stored LOGICAL (the build bakes visual RTL later).
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
TT, HE, BATCH = (os.path.join(HERE, x) for x in ("to_translate.json", "hebrew.json", "current_batch.json"))

STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
HEB = re.compile(r'[א-ת]')
ARAB = re.compile(r'[؀-ۿﭐ-﻿]')
MOJI = re.compile("[　-퟿-]")
NIQ = re.compile(r'[֑-ׇ]')

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def valid(he, ar):
    if not he or not he.strip(): return False, "empty"
    if MOJI.search(he): return False, "mojibake"
    if not HEB.search(he): return False, "no-hebrew"
    if ARAB.search(he): return False, "arabic-left"
    if NIQ.search(he): return False, "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(ar)): return False, "token-mismatch"
    return True, "ok"

def main():
    tt, he, batch = load(TT, {}), load(HE, {}), load(BATCH, {})
    if not batch:
        print("No current_batch.json — run get_batch.py first."); return
    merged = skipped = 0; reasons = {}
    for k, v in batch.items():
        if k not in tt: continue
        hebrew = (v.get("he") if isinstance(v, dict) else v) or ""
        hebrew = NIQ.sub("", hebrew).replace("‎", "").replace("‏", "").strip()
        ok, why = valid(hebrew, tt[k]["ar"])
        if ok: he[k] = hebrew; merged += 1
        else: skipped += 1; reasons[why] = reasons.get(why, 0) + 1
    json.dump(he, open(HE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(HE + ".tmp", HE)
    rem = sum(1 for k in tt if k not in he)
    print(f"merged {merged}, rejected {skipped}  {reasons if reasons else ''}")
    print(f"hebrew.json now {len(he)}/{len(tt)}  ({rem} remaining)")
    if rem == 0: print("All done! Every line translated.")

if __name__ == "__main__":
    main()
