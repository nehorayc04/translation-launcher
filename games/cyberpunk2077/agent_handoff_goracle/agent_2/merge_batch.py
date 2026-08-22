"""Validate + merge the agent's current_batch.json into fixed_female.json.
ANTI-CHEAT (a line is ACCEPTED only if ALL hold):
  1. non-empty
  2. scaffold preserved — every NON-Hebrew char (tokens <..>/{..}/[..]/%d/\\n, Latin names,
     digits, punctuation, the leading control byte) is byte-identical to he_current. Only
     Hebrew letters may change. (A dropped leading control byte is auto-repaired, not rejected.)
  3. he_addressee(fixed) == 'f' — the ADDRESSEE is now feminine (the whole point).
  4. no niqqud.
Rejected lines are printed + left un-merged (get_batch re-serves them)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "universal"))
import gender_oracle as go
from dualgender_verify_agents import scaffold, heb, lead_ctrl
NIQ = re.compile(r'[֑-ׇֽֿׁׂׅׄ]')
def jl(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
batch = jl(os.path.join(HERE, "current_batch.json"), {})
tofix = jl(os.path.join(HERE, "to_fix.json"), {})
done  = jl(os.path.join(HERE, "fixed_female.json"), {})
ok = rej = 0; rejected = []
for k, r in batch.items():
    cur = tofix.get(k, {}).get("he_female_current", "")
    fx  = (r.get("he_feminine") or "").strip("\n")
    if not fx.strip():
        rej += 1; rejected.append((k, "empty")); continue
    # auto-repair a dropped leading control byte
    lc = lead_ctrl(cur)
    if lc and not lead_ctrl(fx):
        fx = lc + fx
    if scaffold(fx) != scaffold(cur):
        rej += 1; rejected.append((k, "scaffold changed (you altered non-Hebrew chars/tokens/name)")); continue
    if NIQ.search(fx):
        rej += 1; rejected.append((k, "niqqud")); continue
    if go.he_addressee(fx) != "f":
        rej += 1; rejected.append((k, "addressee NOT feminine — flip אתה→את + the verb forms")); continue
    done[k] = fx; ok += 1
json.dump(done, open(os.path.join(HERE, "fixed_female.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"merged {ok}  rejected {rej}  |  total fixed {len(done)} / {len(tofix)}")
for k, why in rejected[:15]:
    print("  REJECT", k[-40:], "—", why)
remaining = [k for k in tofix if k not in done]
print("All done!" if not remaining else f"{len(remaining)} remaining — run get_batch.py again")
