#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the agent's translated batch and merge it into the FLEET BANK (../banks/out_agent.json).

The fleet's pull (pull_pt.sh) merges every ../banks/out_*.json into ../hebrew.json, and the progress
pusher reads that — so writing here makes the site dashboard move automatically, in parallel with the
NIM workers. The agent stores LOGICAL Hebrew; the build (pt_rtl.to_stored) bakes RTL/visual later.

The agent fills current_batch.json values in one of two shapes:
  {id: "hebrew text"}                         (simple)
  {id: {"en":..,"ar":..,"he":"hebrew"}}       (kept the object, added 'he')

Anti-cheat / structural gate (REJECTED, stays queued, if):
  * empty / whitespace only
  * foreign script (Arabic/Cyrillic/CJK/…) or Hebrew niqqud
  * the STRUCT token multiset — {STR_..} braces, the pipe '|' line-break, %printf, %% — differs from EN
  * real English PROSE left untranslated (>=2 lowercase English words, no Hebrew), UNLESS the source
    is a bare name/code (then a verbatim copy is allowed)
"""
import json, os, re

HERE  = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.dirname(HERE)
TT    = os.path.join(HERE, "to_translate.json")
BATCH = os.path.join(HERE, "current_batch.json")
BANKS = os.path.join(FLEET, "banks")
OUTAG = os.path.join(BANKS, "out_agent.json")

STRUCT  = re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')
NIQ     = re.compile(r'[֑-ׇ]')
HEB     = re.compile(r'[א-ת]')
LOWERW  = re.compile(r'[a-z]{2,}')


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def is_namey(en):
    core = STRUCT.sub(" ", en).strip()
    if not LOWERW.search(core):
        return True
    words = re.findall(r"[A-Za-z']+", core)
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)


def valid(he, en):
    if not he or not he.strip():
        return False, "empty"
    if FOREIGN.search(he):
        return False, "foreign-script"
    if NIQ.search(he):
        return False, "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)):
        return False, "token-mismatch"
    if not HEB.search(he):
        if he.strip() == en.strip() and is_namey(en):
            return True, "name-passthrough"
        return False, "no-hebrew"
    return True, "ok"


def main():
    tt = load(TT, {})
    batch = load(BATCH, {})
    if not batch:
        print("No current_batch.json — run get_batch.py first.")
        return
    os.makedirs(BANKS, exist_ok=True)
    ag = load(OUTAG, {})
    merged = skipped = 0
    reasons = {}
    for k, v in batch.items():
        if k not in tt:
            continue
        he = v.get("he") if isinstance(v, dict) else v
        he = (he or "").strip()
        he = NIQ.sub("", he).replace("‎", "").replace("‏", "").replace("​", "")
        ok, why = valid(he, tt[k]["en"])
        if ok:
            ag[k] = he
            merged += 1
        else:
            skipped += 1
            reasons[why] = reasons.get(why, 0) + 1
    tmp = OUTAG + ".tmp"
    json.dump(ag, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUTAG)
    remaining = sum(1 for k in tt if k not in ag)
    print(f"merged {merged}, rejected {skipped}  {reasons if reasons else ''}")
    print(f"out_agent.json now holds {len(ag)} lines  (~{remaining} of this tail file left)")
    print("The fleet pull (every ~3 min) folds this into hebrew.json -> the site dashboard updates.")
    if remaining == 0:
        print("All done! Every tail line translated. Tell Claude to build + (on 'פרסם') publish.")


if __name__ == "__main__":
    main()
