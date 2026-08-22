"""Measure live device production: run `python cc_rate.py base`, wait, then
`python cc_rate.py cmp <seconds>`. Per-worker, so a device that claims but
never banks is visible (the difference that matters)."""
import json, os, sys, turso_client as tc
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cc_rate_base.json")
snap = lambda: (
    {x["id"]: x["done"] for x in tc.run(["SELECT id, done FROM cc_workers"])[0]["rows"]},
    tc.run(["SELECT COUNT(*) n FROM cc_lines WHERE status='done'"])[0]["rows"][0]["n"])
if sys.argv[1] == "base":
    w, d = snap(); json.dump({"w": w, "d": d}, open(F, "w"))
    print("baseline done:", d, "| per-worker:", {k[:12]: v for k, v in w.items()})
else:
    b = json.load(open(F)); w, d = snap(); secs = int(sys.argv[2])
    print(f"after {secs}s -> done: {d}  (+{d - b['d']})")
    for k, v in w.items():
        dl = v - b["w"].get(k, 0)
        print(f"  {k[:12]}  +{dl:<4} {'PRODUCING' if dl > 0 else 'no new output'}")
    tot = sum(w.values()) - sum(b["w"].values())
    print(f"\ncombined +{tot} lines in {secs}s = ~{tot * 3600 // secs}/hour")
