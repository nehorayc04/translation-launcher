#!/usr/bin/env python3
r"""
qa_scan.py - independent structural QA over ALL merged Hebrew (hebrew_*.json).
Re-validates every translated line against its English source and reports failures
by reason + overall coverage. Never trust an agent's own "done" - run this.

    python qa_scan.py
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _tokens import validate          # noqa: E402


def main():
    with open(os.path.join(HERE, "to_translate.json"), encoding="utf-8") as f:
        k2en = json.load(f)
    heb = {}
    for p in [os.path.join(HERE, "hebrew.json")] + sorted(glob.glob(os.path.join(HERE, "hebrew_*.json"))):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                heb.update(json.load(f))

    bad = {}
    examples = []
    for k, he in heb.items():
        en = k2en.get(k)
        if en is None:
            bad["orphan_key"] = bad.get("orphan_key", 0) + 1
            continue
        good, reason = validate(en, he)
        if not good:
            bad[reason] = bad.get(reason, 0) + 1
            if len(examples) < 12:
                examples.append((reason, en[:50], he[:50]))

    total = len(k2en)
    print(f"coverage: {len(heb)}/{total} unique strings translated ({100*len(heb)//max(total,1)}%)")
    print(f"structural failures: {sum(bad.values())}")
    for r, c in sorted(bad.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")
    for reason, en, he in examples:
        print(f"    [{reason}] EN={en!r}  HE={he!r}")


if __name__ == "__main__":
    main()
