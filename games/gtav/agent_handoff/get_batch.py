#!/usr/bin/env python3
"""get_batch.py — print the next N untranslated UI strings for the agent to translate.

Reads to_translate.json {key: english}, subtracts hebrew.json (done) + skip.json
(parked names/codes), and prints a JSON object {key: english} of the next batch.
Run from this folder:  python get_batch.py [N]   (default 40)
When nothing is left it prints exactly:  All done!
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(name, default):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    src = load("to_translate.json", {})
    done = load("hebrew.json", {})
    skip = set(load("skip.json", []))
    todo = [k for k in src if k not in done and k not in skip]
    if not todo:
        print("All done!")
        return
    batch = {k: src[k] for k in todo[:n]}
    print(json.dumps(batch, ensure_ascii=False, indent=1))
    sys.stderr.write(f"[get_batch] {len(batch)} of {len(todo)} remaining "
                     f"({len(done)} done, {len(skip)} skipped, {len(src)} total)\n")


if __name__ == "__main__":
    main()
