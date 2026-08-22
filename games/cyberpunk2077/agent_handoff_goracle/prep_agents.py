"""Split gender_oracle_delegate.jsonl into N disjoint agent folders (md5-partitioned).
Re-copies get_batch.py / merge_batch.py / INSTRUCTIONS.md from _tpl on EVERY run (so an agent
that edited a script to weaken the anti-cheat is reverted), while PRESERVING each agent's
fixed_female.json progress. Usage:  python prep_agents.py <N>   (default 3)"""
import json, os, sys, hashlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
DELEGATE = os.path.join(HERE, "..", "gender_oracle_delegate.jsonl")
TPL = os.path.join(HERE, "_tpl")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
rows = [json.loads(l) for l in open(DELEGATE, encoding="utf-8") if l.strip()]
slots = [{} for _ in range(N)]
for r in rows:
    key = f'{r["src"]}|{r["section"]}|{r["pk"]}'
    i = int(hashlib.md5(key.encode()).hexdigest(), 16) % N
    slots[i][key] = {"en": r["en"], "he_female_current": r["he_female_current"],
                     "he_male": r.get("he_male", ""), "ar_female": r["ar_female"],
                     "src": r["src"], "section": r["section"], "pk": r["pk"]}
for i in range(N):
    d = os.path.join(HERE, f"agent_{i+1}")
    os.makedirs(d, exist_ok=True)
    json.dump(slots[i], open(os.path.join(d, "to_fix.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for f in ("get_batch.py", "merge_batch.py", "INSTRUCTIONS.md"):
        shutil.copy2(os.path.join(TPL, f), os.path.join(d, f))   # always revert scripts
    fp = os.path.join(d, "fixed_female.json")
    if not os.path.exists(fp):
        json.dump({}, open(fp, "w", encoding="utf-8"), ensure_ascii=False)
    done = json.load(open(fp, encoding="utf-8"))
    print(f"agent_{i+1}: {len(slots[i])} lines  (already fixed: {len(done)})")
print(f"\nprepped {N} agents, {sum(len(s) for s in slots)} lines total (disjoint).")
