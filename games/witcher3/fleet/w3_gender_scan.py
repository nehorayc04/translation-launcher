# -*- coding: utf-8 -*-
"""Witcher 3 gender-oracle QA scan (single-Hebrew variant).

W3 stores ONE Hebrew string per str_id (not CP2077's femaleVariant/maleVariant), so the CP2077
`gender_oracle.scan` (dual-variant + WolvenKit serialized dir) does not apply. This reuses the
game-agnostic parsers (`ar_addressee`/`he_addressee`) on the FLAT maps:
  * gender source = the game's pristine Arabic  `extract/ar.json`  {str_id: arabic}   (keyID0 cleartext)
  * meaning source = English                    `extract/en.json`  {str_id: english}
  * our translation = the fleet's Hebrew         `fleet/hebrew.json` {str_id: hebrew}
join key = str_id. For every translated line where BOTH the Arabic and the Hebrew have a
determinable addressee gender, flag the disagreements (high precision — only unambiguous Arabic
markers count). Deterministic, no LM. This is the end-of-Phase-2 QA; it does NOT translate.

Usage:  python w3_gender_scan.py [--he fleet/hebrew.json] [--out suspects.jsonl] [--limit N]
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "universal"))
sys.path.insert(0, UNIV)
import gender_oracle as GO   # noqa: E402

EXTRACT = os.path.join(HERE, "..", "extract")
AR_F = os.path.join(EXTRACT, "ar.json")
EN_F = os.path.join(EXTRACT, "en.json")


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--he", default=os.path.join(HERE, "hebrew.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "w3_gender_suspects.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    ar = load(AR_F); en = load(EN_F); he = load(a.he)
    print(f"[*] arabic(gender src)={len(ar):,}  english={len(en):,}  hebrew(translated)={len(he):,}")

    checked = 0; mism = 0; rows = []
    for k, h in he.items():
        av = ar.get(k)
        if not isinstance(h, str) or not isinstance(av, str):
            continue
        a_g = GO.ar_addressee(av)
        h_g = GO.he_addressee(h)
        if a_g and h_g:
            checked += 1
            if a_g != h_g and "pl" not in (a_g, h_g):
                mism += 1
                rows.append({"pk": k, "reason": "addressee_mismatch",
                             "ar_gender": a_g, "he_gender": h_g,
                             "en": en.get(k, ""), "ar": av, "he": h})
    # rank worst-first isn't meaningful here (all equal weight); keep insertion order
    if a.limit:
        rows = rows[:a.limit]
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pct = (100 * mism / checked) if checked else 0.0
    print(f"[✓] {a.out}")
    print(f"    translated lines with a determinable addressee on BOTH sides: {checked:,}")
    print(f"    gender MISMATCH (Arabic oracle vs our Hebrew)               : {mism:,}  ({pct:.1f}% of checked)")
    print(f"    → these are the gender-debt lines to fix (morpheme only) at end-of-Phase-2.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
