#!/usr/bin/env python3
r"""gender_qa.py — Hogwarts Legacy gender ORACLE scan (addressee axis). END-OF-PHASE-2 QA.

Per GENDER_ORACLE_ROLLOUT.md: the game ships an OFFICIAL Arabic locale, so the gender source is
the game's own `arAE` text (Arabic ≈ Hebrew). For every translated line we compare our Hebrew's
addressee gender (`he_addressee`) to the Arabic's (`ar_addressee`); a high-confidence disagreement
means the Hebrew guessed the wrong gender from genderless English.

Run this AFTER Phase-2 translation, on the LOGICAL Hebrew (Hogwarts stores LOGICAL — the engine's
native ICU bidi reorders; there is NO visual bake to undo). Deterministic, no LM. It only REPORTS
([[delegate-all-translation]]) — fix a flagged line by re-inflecting ONLY the gender morpheme
(אתה↔את + verb form), meaning untouched.

  # Hebrew source options (auto-detected, first that exists):
  #   1) a file passed as argv[1]  ({string_key: hebrew})
  #   2) games/hogwarts_legacy/agent_handoff/hebrew.json (+ hebrew_*.json shards)
  #   3) the live pool export:  python universal/community_translate.py export hogwarts --out he.json
  python gender_qa.py [hebrew.json]     # -> gender_suspects.jsonl (ranked)

The Arabic gender source is `extract/gender_source.json` (built by build_gender_source.py), keyed
by the SAME `MAIN:`/`SUB:` string_key as the pool, so the join is exact.
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import gender_oracle as go  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXTRACT = os.path.join(HERE, "..", "extract")
HANDOFF = os.path.join(HERE, "..", "agent_handoff")
OUT = os.path.join(HERE, "..", "gender_suspects.jsonl")


def _load_hebrew(argv):
    """{string_key: hebrew} from argv[1], else the agent_handoff shards, else empty."""
    he = {}
    paths = []
    if len(argv) > 1 and os.path.isfile(argv[1]):
        paths = [argv[1]]
    else:
        paths = ([os.path.join(HANDOFF, "hebrew.json")]
                 + sorted(glob.glob(os.path.join(HANDOFF, "hebrew_*.json"))))
    for p in paths:
        if os.path.isfile(p):
            he.update(json.loads(open(p, encoding="utf-8").read()))
    return he


def main(argv):
    he = _load_hebrew(argv)
    if not he:
        print("No Hebrew found. Pass a {string_key: hebrew} JSON, or export the pool:\n"
              "  python universal/community_translate.py export hogwarts --out he.json\n"
              "  python gender_qa.py he.json")
        return 0
    gs = json.loads(open(os.path.join(EXTRACT, "gender_source.json"), encoding="utf-8").read())

    suspects = []
    checked = 0
    for sk, hebrew in he.items():
        if not isinstance(hebrew, str) or not hebrew.strip():
            continue
        info = gs.get(sk)
        if not info:
            continue
        ar = info.get("ar", "")
        # STRICT Arabic oracle (pronouns + vocalized ـكَ/ـكِ) — no noisy ت…ين verb heuristic.
        a = go.ar_addressee_strict(ar)
        h = go.he_addressee(hebrew)
        if a and h:
            checked += 1
        mismatch = bool(a and h and a != h and not (a == "pl" or h == "pl"))
        if mismatch:
            suspects.append({"string_key": sk, "he": hebrew, "ar": ar,
                             "ar_gender": a, "he_gender": h})

    # rank: feminine-Arabic-but-masc-Hebrew first (the systematic default-to-masc debt)
    suspects.sort(key=lambda s: (s["ar_gender"] != "f", s["string_key"]))
    with open(OUT, "w", encoding="utf-8") as f:
        for s in suspects:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"checked (both genders determinable): {checked}")
    print(f"gender suspects (Arabic vs Hebrew addressee disagree): {len(suspects)} -> {OUT}")
    for s in suspects[:12]:
        print(f"  [ar={s['ar_gender']} he={s['he_gender']}] {s['string_key']}: {s['he'][:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
