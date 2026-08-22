#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gender_qa.py — END-OF-PHASE-2 gender QA for A Plague Tale: Requiem
(per universal/GENDER_ORACLE_ROLLOUT.md — "the oracle IS the QA").

Cross-checks the finished Hebrew against the game's OWN Arabic (the gender source):
for every line where BOTH the Arabic AND the Hebrew carry an unambiguous addressee
marker, flag the ones that DISAGREE (e.g. Arabic says the addressee is female
"تتوقفي" but the Hebrew used masculine "אל תעצור"). English can't reveal this — the
Arabic can. Output ranked suspects for a deterministic morpheme fix
(universal/dualgender_inflect.py) or delegate; NEVER retranslate meaning.

Hebrew input = a {KEY: hebrew} JSON. Sources, in order:
  1. --he <file.json>                    (explicit)
  2. the /translate approved export       (universal/community_translate.py export …)
  3. the built Hebrew tt23 spine          (once Phase-2 has produced it)
Arabic source = extract/gender_source.json (the cached pristine Arabic per KEY).

SAFETY: read-only. Only writes gender_suspects.jsonl. Touches no game file.
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import gender_oracle as G   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GS = os.path.join(HERE, "..", "extract", "gender_source.json")
OUT = os.path.join(HERE, "..", "extract", "gender_suspects.jsonl")


def main():
    he_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not he_path or not os.path.exists(he_path):
        print("usage: python gender_qa.py <hebrew_KEY_to_text.json>")
        print("  (run after Phase-2: export the approved Hebrew first, then pass it here)")
        return
    src = json.load(open(GS, encoding="utf-8"))          # {KEY: {en, ar, hint}}
    he = json.load(open(he_path, encoding="utf-8"))       # {KEY: hebrew}
    suspects = []
    checked = 0
    for k, hv in he.items():
        s = src.get(k)
        if not s or not s.get("ar") or not hv:
            continue
        checked += 1
        r = G.check_line(hv, s["ar"])     # {ar, he, mismatch}
        if r.get("mismatch"):
            suspects.append({"key": k, "en": s["en"], "he": hv, "ar": s["ar"],
                             "ar_gender": r.get("ar"), "he_gender": r.get("he")})
    with open(OUT, "w", encoding="utf-8") as f:
        for row in suspects:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"checked {checked} lines (both he+ar marked) -> {len(suspects)} gender suspects")
    print("wrote", os.path.abspath(OUT))
    for row in suspects[:8]:
        print(f"  AR={row['ar_gender']} HE={row['he_gender']} | {row['en'][:40]!r} | {row['he'][:34]}")


if __name__ == "__main__":
    main()
