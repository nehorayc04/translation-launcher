#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the next batch of W3 lines to translate FROM ARABIC (their English source
was corrupted in extraction, so Arabic is the only clean source).

Usage:  python get_batch.py [N]     (default 40)
Writes current_batch.json = {id: {ar}}. Prints "All done!" when empty.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TT, HE, BATCH = (os.path.join(HERE, x) for x in ("to_translate.json", "hebrew.json", "current_batch.json"))

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    tt, he = load(TT, {}), load(HE, {})
    todo = [(k, v) for k, v in tt.items() if k not in he]
    if not todo:
        print("All done! 0 remaining.")
        try: os.remove(BATCH)
        except OSError: pass
        return
    json.dump(dict(todo[:n]), open(BATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Wrote {min(n,len(todo))} lines to current_batch.json  ({len(todo)} remaining, {len(he)} done).")
    print("Translate each 'ar' (Arabic) into fluent Hebrew, put it in the value, then run merge_batch.py.")

if __name__ == "__main__":
    main()
