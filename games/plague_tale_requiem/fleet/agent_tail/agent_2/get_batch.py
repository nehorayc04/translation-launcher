#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the next batch for THIS agent slot (a disjoint md5 slice of the PT tail).
Usage: python get_batch.py [N]   (default 60). Prints "All done!" when the slot is empty."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.abspath(os.path.join(HERE, "..", ".."))
TT = os.path.join(HERE, "to_translate.json")
BANK = os.path.join(FLEET, "hebrew.json")
MYBANK = os.path.join(FLEET, "banks", "out_agent2.json")
BATCH = os.path.join(HERE, "current_batch.json")
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def ne(v): return isinstance(v, str) and v.strip() != ""
def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    tt = load(TT, {}); bank = load(BANK, {}); mine = load(MYBANK, {})
    done = {k for k, v in bank.items() if ne(v)} | {k for k, v in mine.items() if ne(v)}
    todo = [(k, v) for k, v in tt.items() if k not in done]
    if not todo:
        print("All done! 0 remaining in this slot.")
        try: os.remove(BATCH)
        except OSError: pass
        return
    json.dump(dict(todo[:n]), open(BATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Wrote %d lines to current_batch.json (%d remaining, %d done)." % (min(n, len(todo)), len(todo), len(done)))
    print("Translate each 'en' into Hebrew (value); keep {STR_...} and the pipe | verbatim; then run merge_batch.py.")
if __name__ == "__main__": main()
