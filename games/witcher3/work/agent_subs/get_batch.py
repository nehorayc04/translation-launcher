#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the next batch of untranslated W3 motion-comic subtitle lines to the agent.

Usage:  python get_batch.py [N]        (default N=30)
Writes current_batch.json = {key: {en, ar, ru, pl, es, it, fr, de}} of the next untranslated lines.
Prints "All done!" when nothing is left.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TT    = os.path.join(HERE, "to_translate.json")
HE    = os.path.join(HERE, "hebrew.json")
BATCH = os.path.join(HERE, "current_batch.json")


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    tt = load(TT, {}); he = load(HE, {})
    todo = [(k, v) for k, v in tt.items() if k not in he]
    if not todo:
        print("All done! 0 remaining.")
        try:
            os.remove(BATCH)
        except OSError:
            pass
        return
    batch = {k: dict(v) for k, v in todo[:n]}
    for v in batch.values():
        v["he"] = ""          # <-- fill each with your Hebrew, then run merge_batch.py
    with open(BATCH, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(batch)} lines to current_batch.json  ({len(todo)} remaining, {len(he)} done).")
    print("Fill each item's \"he\" with fluent LOGICAL Hebrew (New-Era: cross-check gender vs ar/ru/pl/es/it/fr/de),")
    print("then run:  python merge_batch.py")


if __name__ == "__main__":
    main()
