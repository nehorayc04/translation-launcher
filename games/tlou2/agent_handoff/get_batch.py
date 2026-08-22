#!/usr/bin/env python3
r"""
get_batch.py - hand the next chunk of untranslated TLOU strings to an agent.

Single agent:      python get_batch.py                 (slot 0 of 1)
N parallel agents: python get_batch.py <slot> <N>      (slot in 0..N-1, disjoint)

Partition is by md5-key modulo N, so N agents never collide. Writes
`batch_<slot>.json` = { key: {"en": <english>, "he": ""} }. The agent fills every
"he" with LOGICAL Hebrew (natural reading order - NOT reversed), preserving every
token, then runs merge_batch.py. Repeat until it prints "All done for this slot!".
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
BATCH = int(os.environ.get("TLOU_BATCH", "250"))


def _load(name, default):
    p = os.path.join(HERE, name)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return default


def done_keys():
    done = {}
    for p in [os.path.join(HERE, "hebrew.json")] + sorted(glob.glob(os.path.join(HERE, "hebrew_*.json"))):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                done.update(json.load(f))
    return set(done)


def main():
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    nslots = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    k2en = _load("to_translate.json", {})
    gsrc = _load("gender_source.json", {})     # {key: {ru, es, fr, gender?}} gender oracle
    cats = _load("categories.json", {})        # {key: Hebrew category} -> serve by category order
    done = done_keys()
    # serve BY CATEGORY (highest-visibility first): UI/menus -> story subtitles -> background barks,
    # then by key inside a category. So each agent finishes the most-visible text first (shippable partial).
    CAT_ORDER = {"ממשק ותפריטים": 0, "כתוביות עלילה": 1, "דיבורי רקע": 2}
    mine = sorted((k for k in k2en if (int(k, 16) % nslots) == slot and k not in done),
                  key=lambda k: (CAT_ORDER.get(cats.get(k, ""), 9), k))
    batch = {}
    for k in mine[:BATCH]:
        entry = {"en": k2en[k]}
        if cats.get(k):
            entry["cat"] = cats[k]                   # category (register cue: UI=terse, subtitles=spoken)
        g = gsrc.get(k, {})
        for fld in ("ru", "es", "fr", "gender"):   # gendered locales: read the gender, don't guess
            if g.get(fld):
                entry[fld] = g[fld]
        entry["he"] = ""                            # <- fill this (LOGICAL Hebrew)
        batch[k] = entry
    outp = os.path.join(HERE, f"batch_{slot}.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"slot {slot}/{nslots}: {len(done)} done total, {len(mine)} remaining in slot; "
          f"wrote {len(batch)} -> batch_{slot}.json")
    if not batch:
        print("All done for this slot!")


if __name__ == "__main__":
    main()
