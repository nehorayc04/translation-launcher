"""get_batch.py — write the next 200 still-untranslated lines of THIS slice to current_batch.json.
Skips anything already done by ANY stream (the whole fleet + this agent's own bank) so no line is redone."""
import json, glob, os
BS = 20
HERE = os.path.dirname(os.path.abspath(__file__))
BANKROOT = os.path.abspath(os.path.join(HERE, "..", "..", "agent_handoff_qa"))
if os.path.exists(os.path.join(HERE, "current_batch_he.json")):
    print("STOP: current_batch_he.json exists (unmerged). Run  python merge_batch.py  first, or delete it. Not fetching a new batch (prevents a key-mismatch race).")
    raise SystemExit(0)
slice_ = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
done = set()
for f in glob.glob(os.path.join(BANKROOT, "_pool", "nim_out_*.json")):
    if f.endswith(".skip.json") or f.endswith(".strikes.json"): continue
    try: done |= set(json.load(open(f, encoding="utf-8")).keys())
    except: pass
for folder in glob.glob(os.path.join(BANKROOT, "retrans_agent_*")):
    fc = os.path.join(folder, "retrans_corrections.json")
    if os.path.exists(fc):
        try: done |= set(json.load(open(fc, encoding="utf-8")).keys())
        except: pass
todo = {k: v for k, v in slice_.items() if k not in done}
batch = dict(list(todo.items())[:BS])
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if not batch:
    print("All done! (slice fully translated by the fleet)")
else:
    print(f"Wrote {len(batch)} lines to current_batch.json | slice-remaining {len(todo)}")
