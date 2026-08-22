#!/usr/bin/env python3
r"""
merge_batch.py - validate a filled batch and merge it into hebrew_<slot>.json.

    python merge_batch.py            (slot 0)
    python merge_batch.py <slot>

Reads `batch_<slot>.json`, validates every filled "he" (token multiset preserved,
no niqqud, no foreign script, real Hebrew unless the source is a name/code, not
left as English on prose), merges the good ones into `hebrew_<slot>.json`, and
reports rejects by reason. REJECTED entries stay untranslated and come back in the
next get_batch - so a cheated/broken line cannot slip through.
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _tokens import validate          # noqa: E402


def main():
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    bp = os.path.join(HERE, f"batch_{slot}.json")
    hp = os.path.join(HERE, f"hebrew_{slot}.json")
    if not os.path.isfile(bp):
        print(f"no batch_{slot}.json - run get_batch.py {slot} first")
        return
    with open(bp, encoding="utf-8") as f:
        batch = json.load(f)
    heb = {}
    if os.path.isfile(hp):
        with open(hp, encoding="utf-8") as f:
            heb = json.load(f)

    ok = 0
    rej = {}
    examples = []
    for k, o in batch.items():
        he = (o.get("he") or "").strip()
        if not he:
            continue
        good, reason = validate(o["en"], he)
        if good:
            heb[k] = he
            ok += 1
        else:
            rej[reason] = rej.get(reason, 0) + 1
            if len(examples) < 8:
                examples.append((reason, o["en"][:50], he[:50]))

    tmp = hp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(heb, f, ensure_ascii=False)
    os.replace(tmp, hp)

    print(f"merged {ok} -> hebrew_{slot}.json (total {len(heb)}); rejected {sum(rej.values())}")
    for r, c in sorted(rej.items(), key=lambda x: -x[1]):
        print(f"  reject {r}: {c}")
    for reason, en, he in examples:
        print(f"    [{reason}] EN={en!r}  HE={he!r}")


if __name__ == "__main__":
    main()
