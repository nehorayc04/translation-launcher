#!/usr/bin/env python3
"""qa_scan.py — full-spine QA over hebrew.json vs to_translate.json.

Reports every defect class (token mismatch / niqqud / foreign script / missing Hebrew
on a real-word source / empty). Run any time:  python qa_scan.py
Exit 0 = clean, 1 = defects found. Does NOT modify anything.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _tokens import tokens, has_hebrew, has_niqqud, foreign_chars, real_word  # noqa
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(name, d):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def main():
    src = load("to_translate.json", {})
    he = load("hebrew.json", {})
    skip = set(load("skip.json", []))
    bad = {"token": [], "niqqud": [], "foreign": [], "no_hebrew": [], "empty": []}
    for k, h in he.items():
        en = src.get(k, "")
        if h == "" and real_word(en):
            bad["empty"].append(k); continue
        if tokens(h) != tokens(en):
            bad["token"].append(k)
        if has_niqqud(h):
            bad["niqqud"].append(k)
        if foreign_chars(h):
            bad["foreign"].append(k)
        if not has_hebrew(h) and real_word(en) and k not in skip:
            bad["no_hebrew"].append(k)
    total = len(src)
    cov = len(he) + len(skip)
    print(f"coverage: {cov}/{total}  ({len(he)} translated, {len(skip)} skipped, "
          f"{total - cov} untranslated)")
    n = sum(len(v) for v in bad.values())
    for kind, ks in bad.items():
        if ks:
            print(f"  {kind}: {len(ks)}  e.g. {ks[:6]}")
    print("RESULT:", "CLEAN" if n == 0 else f"{n} DEFECTS")
    sys.exit(0 if n == 0 else 1)


if __name__ == "__main__":
    main()
