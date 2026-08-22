#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""simple_auto_check.py — deterministic simple-QA over a game's Hebrew.

Trigger: the user says "תעשה בדיקה אוטומטי [פשוטה]". Run this over the game's
LOGICAL Hebrew (before any RTL bake), then a human judges each hit.

Input: a JSON file mapping {key: hebrew_value} (e.g. a fleet hebrew.json / spine).
Usage: python simple_auto_check.py <hebrew.json> [--samples N]

Checks (report counts + samples per category):
  nonfinal_at_end   word ends in כ/מ/נ/פ/צ (should be ך/ם/ן/ף/ץ)
  final_midword     ך/ם/ן/ף/ץ not at the end of a Hebrew run
  mixed_heb_latin   one token has BOTH Hebrew and Latin letters
  heb_digit         a token has Hebrew letters AND a digit glued
  latin_digit       a token has Latin letters AND a digit glued (often legit)
  lone_heb_letter   an isolated single Hebrew letter that is NOT a valid prefix
  niqqud            any niqqud vowel point
  foreign           any non-Hebrew non-Latin letter (Cyrillic/Arabic/CJK/…)

STRUCT tokens ({STR_...}, |, %-specs, <tags>, [TOKEN]) are stripped first so they
are never mistaken for words.
"""
from __future__ import annotations
import json, re, sys, argparse

FINAL = set("ךםןףץ")
NONFINAL_OF = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
VALID_PREFIX = set("ובלהמשכד")          # legit one-letter Hebrew prefixes / conjunctions
HEB = re.compile(r"[א-ת]")     # Hebrew letters (no final/niqqud ambiguity here)
HEB_ALL = re.compile(r"[א-תךםןףץ]")
NIQQUD = re.compile(r"[֑-ֽֿׁׂ]")
LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"[0-9]")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힯Ѐ-ӿ]")
STRUCT = re.compile(r"\{[^}]*\}|<[^>]*>|\[[^\]]*\]|%[#0-9.*\-+]*[a-zA-Z]+|%%")
HEBRUN = re.compile(r"[א-תךםןףץ]+")


def strip_struct(s: str) -> str:
    s = STRUCT.sub(" ", s)
    return s.replace("|", " ")


def tokens(s: str):
    # split on whitespace and common punctuation, keep letters/digits/gershayim together
    return re.split(r"[\s,.!?;:()'\"–—־…“”«»\-]+", s)


def check(key: str, val: str, hits: dict):
    if NIQQUD.search(val):
        hits["niqqud"].append((key, val))
    if FOREIGN.search(val):
        hits["foreign"].append((key, val))
    core = strip_struct(val)
    for tok in tokens(core):
        if not tok:
            continue
        has_heb = bool(HEB_ALL.search(tok))
        has_lat = bool(LATIN.search(tok))
        has_dig = bool(DIGIT.search(tok))
        if has_heb and has_lat:
            hits["mixed_heb_latin"].append((key, tok, val))
        if has_heb and has_dig:
            hits["heb_digit"].append((key, tok, val))
        if has_lat and has_dig and not has_heb:
            hits["latin_digit"].append((key, tok, val))
        # final-form position checks on each Hebrew run inside the token
        for run in HEBRUN.findall(tok):
            # final form in the middle
            for i, ch in enumerate(run):
                if ch in FINAL and i != len(run) - 1:
                    hits["final_midword"].append((key, tok, val)); break
            # non-final at the end
            last = run[-1]
            if last in NONFINAL_OF and len(run) > 1:
                hits["nonfinal_at_end"].append((key, tok, val))
            # lone single Hebrew letter that isn't a valid prefix
            if len(run) == 1 and run == tok and run not in VALID_PREFIX:
                hits["lone_heb_letter"].append((key, tok, val))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--samples", type=int, default=12)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.load(open(a.path, encoding="utf-8"))
    hits = {k: [] for k in ("nonfinal_at_end", "final_midword", "mixed_heb_latin",
                            "heb_digit", "latin_digit", "lone_heb_letter", "niqqud", "foreign")}
    n = 0
    for key, val in data.items():
        if isinstance(val, str) and val.strip():
            n += 1
            check(key, val, hits)
    print(f"scanned {n} Hebrew values from {a.path}\n")
    for cat, lst in hits.items():
        print(f"=== {cat}: {len(lst)} ===")
        seen = set()
        shown = 0
        for row in lst:
            k = row[0]
            if k in seen:
                continue
            seen.add(k)
            print("   " + " | ".join(str(x) for x in row))
            shown += 1
            if shown >= a.samples:
                break
        print()


if __name__ == "__main__":
    main()
