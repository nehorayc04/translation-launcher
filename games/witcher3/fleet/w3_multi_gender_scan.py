# -*- coding: utf-8 -*-
"""Line-by-line multi-language gender/number QA for The Witcher 3.

For every translated Hebrew line, gather the ADDRESSEE gender/number as marked by each gendered
language of the SAME str_id (Arabic, Russian, Polish, Spanish, Italian), take a CONSENSUS, and flag
the line ONLY when >=2 languages AGREE on a value that disagrees with our Hebrew (a clear majority,
no tie). Multi-language agreement separates a real addressee-gender bug from oracle noise (a lone
Arabic false-positive on a 1st-person speaker verb can't reach a 2-language consensus).

Outputs (sorted most-confident first):
  w3_multi_suspects.jsonl  — {pk, consensus, n_agree, votes{lang:g}, he_g, en, he, ar, ru, pl, es, it}
Run:  python w3_multi_gender_scan.py [--he hebrew.json] [--min 2]
"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
import w3_lang_oracle as O

EX = os.path.join(HERE, "..", "extract")


def load(name):
    try:
        return json.load(open(os.path.join(EX, name), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--he", default=os.path.join(HERE, "hebrew.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "w3_multi_suspects.jsonl"))
    ap.add_argument("--min", type=int, default=2, help="min languages that must agree")
    a = ap.parse_args(argv)

    he = json.load(open(a.he, encoding="utf-8"))
    L = {l: load(f"{l}.json") for l in ("en", "ar", "ru", "pl", "es", "it")}
    print("[*] " + "  ".join(f"{l}={len(L[l]):,}" for l in L) + f"  he={len(he):,}")

    rows = []
    checked = 0
    for k, h in he.items():
        if not isinstance(h, str):
            continue
        hg = O.he_addressee(h)
        if not hg:
            continue
        langs = {l: L[l].get(k, "") for l in ("ar", "ru", "pl", "es", "it")}
        val, n, v = O.consensus(langs)
        if not val or n < a.min:
            continue
        # require a CLEAR majority (no equal-tie for another value)
        tally = {}
        for g in v.values():
            tally[g] = tally.get(g, 0) + 1
        if sorted(tally.values())[-2:] == [n, n]:      # a tie at the top
            continue
        checked += 1
        if val != hg:
            rows.append({"pk": k, "consensus": val, "n_agree": n, "he_g": hg, "votes": v,
                         "en": L["en"].get(k, ""), "he": h,
                         "ar": langs["ar"], "ru": langs["ru"], "pl": langs["pl"],
                         "es": langs["es"], "it": langs["it"]})
    rows.sort(key=lambda r: (-r["n_agree"], r["pk"]))
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    by = Counter((r["n_agree"], r["consensus"]) for r in rows)
    print(f"[✓] lines with a >= {a.min}-lang clear consensus: {checked:,}")
    print(f"    consensus DISAGREES with our Hebrew (suspects): {len(rows):,}")
    print(f"    by (n_agree, consensus): {dict(sorted(by.items(), reverse=True))}")
    print(f"    -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
