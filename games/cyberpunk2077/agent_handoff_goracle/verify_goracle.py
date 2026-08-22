"""INDEPENDENT verify of the agents' gender fixes (trusts NOTHING from merge_batch).
For every key across agent_*/fixed_female.json: require
  classify_fill(fixed, he_female_current, "") is valid  (scaffold byte-identical + a real
  Hebrew SUFFIXAL gender change, no niqqud/internal-edit)  AND  he_addressee(fixed)=='f'.
Passing keys -> verified_female.json (fed to apply_goracle.py). Reports fails per reason.
CLI: python verify_goracle.py"""
import json, os, sys, glob
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "universal"))
import gender_oracle as go
from dualgender_verify_agents import classify_fill
DELEGATE = os.path.join(HERE, "..", "gender_oracle_delegate.jsonl")
cur = {}
for l in open(DELEGATE, encoding="utf-8"):
    if l.strip():
        r = json.loads(l); cur[f'{r["src"]}|{r["section"]}|{r["pk"]}'] = r["he_female_current"]
verified = {}; reasons = Counter(); n = 0; bad = []
for f in glob.glob(os.path.join(HERE, "agent_*", "fixed_female.json")):
    for k, fixed in json.load(open(f, encoding="utf-8")).items():
        n += 1
        src = cur.get(k)
        if src is None:
            reasons["unknown_key"] += 1; continue
        val, why = classify_fill(fixed, src, "")
        if why:
            reasons[why] += 1
            if len(bad) < 12: bad.append((why, src, fixed))
            continue
        if go.he_addressee(val) != "f":
            reasons["addressee_not_fem"] += 1
            if len(bad) < 12: bad.append(("addressee_not_fem", src, fixed))
            continue
        verified[k] = val
json.dump(verified, open(os.path.join(HERE, "verified_female.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"checked {n}  VERIFIED {len(verified)}  rejected {sum(reasons.values())}")
if reasons: print("  reject reasons:", dict(reasons))
for why, s, fx in bad:
    print(f"    BAD[{why}]: cur={s[:38]!r} fixed={fx[:38]!r}")
print(f"-> verified_female.json ({len(verified)} ready for apply)")
