# -*- coding: utf-8 -*-
"""Validate + merge the agent's translated batch into hebrew_out.json.
current_batch.json maps {id: "<Hebrew>"} (or keeps the dict with a "he" key). Accept only when:
  - has Hebrew (or the EN source is a bare proper name/code -> a verbatim copy is allowed);
  - no niqqud, no Arabic/other foreign script (Latin allowed for names/tokens);
  - the same tag/placeholder multiset as EN (<..> {..} %s %d %1 &ent;), same count.
Run: python merge_batch.py
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')       # Arabic/CJK/Hangul/Cyrillic
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
HEB = re.compile(r'[֐-׿]')
TOK = re.compile(r'<[^>]*>|\{[^}]*\}|%[0-9]*[sdfx]|%[0-9]|&[a-zA-Z#0-9]+;')
LOWER = re.compile(r'[a-z]{2,}')


def _val(v):
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("he") or v.get("fix") or ""
    return ""


def main():
    tob = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
    batch = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
    try:
        done = json.load(open(os.path.join(HERE, "hebrew_out.json"), encoding="utf-8"))
    except Exception:
        done = {}
    ok = rej = 0
    reasons = {}
    for k, v in batch.items():
        if k not in tob:
            continue
        new = _val(v).strip()
        en = tob[k]["en"]
        name_like = not LOWER.search(en)         # EN has no real lowercase word -> a name/code
        r = None
        if not new:
            r = "empty"
        elif FOREIGN.search(new) or NIQ.search(new):
            r = "foreign/niqqud"
        elif not HEB.search(new) and not name_like:
            r = "no-hebrew"
        elif sorted(TOK.findall(new)) != sorted(TOK.findall(en)):
            r = "token-mismatch"
        if r:
            rej += 1
            reasons[r] = reasons.get(r, 0) + 1
            continue
        done[k] = new
        ok += 1
    tmp = os.path.join(HERE, "hebrew_out.json.tmp")
    json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HERE, "hebrew_out.json"))
    print(f"merged {ok} | rejected {rej} {reasons} | total {len(done)}/{len(tob)}")
    if len(done) >= len(tob):
        print("All done!")


if __name__ == "__main__":
    main()
