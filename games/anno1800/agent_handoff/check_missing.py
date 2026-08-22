import json
import os

handoff = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff"

for p in [1, 2, 3, 4]:
    with open(os.path.join(handoff, f"batch_part{p}.json"), "r", encoding="utf-8") as f:
        b = json.load(f)
    with open(os.path.join(handoff, f"trans_part_{p}.json"), "r", encoding="utf-8") as f:
        t = json.load(f)
    missing = set(b.keys()) - set(t.keys())
    print(f"Part {p} missing: {len(missing)}")
    if missing:
        for k in sorted(list(missing))[:10]:
            print(f"  {k}: {b[k]}")
