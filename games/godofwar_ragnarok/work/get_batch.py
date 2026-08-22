# -*- coding: utf-8 -*-
"""Utility: split to_translate.json into sequential batches of 500."""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "to_translate.json")
HEB = os.path.join(HERE, "hebrew.json")

def get_next_batch(n=500):
    src = json.load(open(SRC, encoding="utf-8"))
    heb = json.load(open(HEB, encoding="utf-8"))
    untrans = [k for k in sorted(src.keys(), key=int) if k not in heb]
    batch = untrans[:n]
    if not batch:
        print("All done!")
        return
    print(f"Untranslated: {len(untrans)}. Batch: {batch[0]} – {batch[-1]} ({len(batch)} keys)")
    # Write batch source for reference
    out = {k: src[k] for k in batch}
    with open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Saved current_batch.json")

if __name__ == "__main__":
    get_next_batch()
