#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the gender-REVIEW corpus for the fleet: every non-marker line whose ARABIC carries a
gender/number signal (2nd-person addressee gender, plural, feminine referent) -> {key:{en,ar,he}}
with he = our CURRENT Hebrew. These are the ONLY lines where the Arabic can correct the Hebrew
gender; a line with zero gender signal in Arabic cannot inform a fix, so reviewing it is a no-op.

Reads: ../hebrew.json (current) + ../../extract/gender_source.json (en+ar) + ../marker_keys.json
Writes: gender_corpus.json = {key:{en,ar,he}}  (the fleet slices this)
Run:  python build_gender_corpus.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "universal"))
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(FLEET)))  # repo root
sys.path.insert(0, os.path.join(ROOT, "universal"))
import gender_oracle as go

# broad Arabic gender/number signal: addressee gender (via oracle) OR explicit 2nd-person/plural markers
_SIG = re.compile(
    r'أنتِ|أنتَ|أنتما|أنتم|أنتن|'          # 2nd-person pronouns (gendered / plural)
    r'ـكِ|ـكَ|كِ\b|كَ\b|كما\b|كم\b|كن\b|'  # 2nd-person object/possessive suffixes
    r'ين\b|تين\b|'                          # 2nd-fem present ending (تفعلين) / dual
    r'وا\b|ون\b|'                            # masc-plural verb/noun
    r'تن\b|تما\b'                            # 2nd-fem-plural / dual past
)


def has_signal(ar: str) -> bool:
    if not ar or not ar.strip():
        return False
    if go.ar_addressee(ar):          # oracle-detected addressee gender/number
        return True
    return bool(_SIG.search(ar))


def main():
    heb = json.load(open(os.path.join(FLEET, "hebrew.json"), encoding="utf-8"))
    src = json.load(open(os.path.join(FLEET, "..", "extract", "gender_source.json"), encoding="utf-8"))
    try:
        markers = set(json.load(open(os.path.join(FLEET, "marker_keys.json"), encoding="utf-8")))
    except Exception:
        markers = set()

    corpus = {}
    for k, he in heb.items():
        if k in markers or not isinstance(he, str) or not he.strip():
            continue
        v = src.get(k)
        ar = (v.get("ar") if isinstance(v, dict) else None) or ""
        en = (v.get("en") if isinstance(v, dict) else v) or ""
        if has_signal(ar):
            corpus[k] = {"en": en, "ar": ar, "he": he}

    out = os.path.join(HERE, "gender_corpus.json")
    json.dump(corpus, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"reviewable (Arabic has gender signal) = {len(corpus)} / {len(heb)} banked lines -> {out}")


if __name__ == "__main__":
    main()
