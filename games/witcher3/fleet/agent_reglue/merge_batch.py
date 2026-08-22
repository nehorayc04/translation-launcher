#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the agent's translated batch and merge it into hebrew.json.

The agent fills current_batch.json values with Hebrew, in one of two shapes:
  {id: "hebrew text"}                         (simple)
  {id: {"en":..., "ar":..., "he":"hebrew"}}   (kept the object, added 'he')
Both are accepted.

Anti-cheat / structural gate (a line is REJECTED and stays queued if):
  * empty / whitespace only
  * contains a foreign script (Arabic/Cyrillic/CJK/…) or Hebrew niqqud
  * the STRUCT token multiset (<tags>, {braces}, %printf, &entities;) differs from the English
  * it is real English PROSE left untranslated (>=2 lowercase English words and no Hebrew letter),
    UNLESS the source is a bare name/code (then a verbatim copy is allowed)
Merged lines are written to hebrew.json (LOGICAL Hebrew — the build bakes RTL/visual later).
"""
import json, os, re

HERE  = os.path.dirname(os.path.abspath(__file__))
TT    = os.path.join(HERE, "to_translate.json")
HE    = os.path.join(HERE, "hebrew.json")
BATCH = os.path.join(HERE, "current_batch.json")

STRUCT  = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')
NIQ     = re.compile(r'[֑-ׇ]')
HEB     = re.compile(r'[א-ת]')
LOWERW  = re.compile(r'[a-z]{2,}')

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def is_namey(en):
    core = STRUCT.sub(" ", en).strip()
    if not LOWERW.search(core):           # no real lowercase word → code/name/number
        return True
    words = [w for w in re.findall(r"[A-Za-z']+", core)]
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)

def valid(he, en):
    if not he or not he.strip():                       return False, "empty"
    if FOREIGN.search(he):                             return False, "foreign-script"
    if NIQ.search(he):                                 return False, "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)): return False, "token-mismatch"
    if not HEB.search(he):
        # no Hebrew: only allowed if the source is a bare name/code copied verbatim
        if he.strip() == en.strip() and is_namey(en):  return True, "name-passthrough"
        return False, "no-hebrew"
    return True, "ok"

def main():
    tt = load(TT, {}); he = load(HE, {}); batch = load(BATCH, {})
    if not batch:
        print("No current_batch.json — run get_batch.py first."); return
    merged = skipped = 0; reasons = {}
    for k, v in batch.items():
        if k not in tt:            # unknown id — ignore
            continue
        hebrew = v.get("he") if isinstance(v, dict) else v
        hebrew = (hebrew or "").strip()
        # auto-REPAIR (not reject): strip Hebrew niqqud + zero-width marks. These never
        # change meaning, so a vocalized translation (וֶלֶן) is cleaned to ולן and ACCEPTED.
        hebrew = NIQ.sub("", hebrew).replace("‎", "").replace("‏", "").replace("​", "")
        ok, why = valid(hebrew, tt[k]["en"])
        if ok:
            he[k] = hebrew; merged += 1
        else:
            skipped += 1; reasons[why] = reasons.get(why, 0) + 1
    tmp = HE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HE)
    remaining = sum(1 for k in tt if k not in he)
    print(f"merged {merged}, rejected {skipped}  {reasons if reasons else ''}")
    print(f"hebrew.json now {len(he)}/{len(tt)}  ({remaining} remaining)")
    if remaining == 0:
        print("All done! Every tail line translated.")

if __name__ == "__main__":
    main()
