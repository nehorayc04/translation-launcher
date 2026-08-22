# -*- coding: utf-8 -*-
"""Fold the w3qa banks into ONE audit file: fleet/qa_reviewed.json.

    {id: {"old": <current hebrew.json line>, "new": <reviewer's line>, "iss": <tag>, "en": ..}}

Only lines the reviewer actually CHANGED are kept (iss != "ok"); an "ok" line means the
reviewer confirmed the existing translation, which we record only as a count.

⚠️ hebrew.json is NEVER written here. This is the audit for the SECOND mod update — apply it
with `apply_qa_review.py` after the changes have been eyeballed.
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
HEB = os.path.join(HERE, "hebrew.json")
OUT = os.path.join(HERE, "qa_reviewed.json")
BANKS = os.path.join(HERE, "banks")


def main():
    he = json.load(open(HEB, encoding="utf-8"))
    try:
        en = json.load(open(os.path.join(HERE, "..", "extract", "en.json"), encoding="utf-8"))
    except Exception:
        en = {}
    prev = {}
    if os.path.exists(OUT):
        prev = json.load(open(OUT, encoding="utf-8"))

    reviewed = 0
    changed = dict(prev)
    tags = collections.Counter()
    for fn in sorted(os.listdir(BANKS)):
        if not fn.startswith("qa_out_") or not fn.endswith(".json"):
            continue
        try:
            bank = json.load(open(os.path.join(BANKS, fn), encoding="utf-8"))
        except Exception as e:
            print(f"  {fn}: unreadable ({e})")
            continue
        for k, v in bank.items():
            if not isinstance(v, dict):
                continue
            reviewed += 1
            iss = v.get("iss", "ok")
            tags[iss] += 1
            if iss == "ok":
                continue
            new = v.get("he")
            old = he.get(k)
            if not isinstance(new, str) or not isinstance(old, str):
                continue
            if new.strip() == old.strip():
                continue
            e = en.get(k)
            changed[k] = {"old": old, "new": new, "iss": iss,
                          "en": e if isinstance(e, str) else ""}

    json.dump(changed, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"reviewed lines in banks : {reviewed}")
    print("  " + ", ".join(f"{t}:{n}" for t, n in tags.most_common()))
    print(f"proposed changes (audit): {len(changed)}  -> {os.path.basename(OUT)}")
    print("hebrew.json UNTOUCHED (this is for the 2nd update).")


if __name__ == "__main__":
    main()
