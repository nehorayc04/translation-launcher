#!/usr/bin/env python3
"""Driver: run acbf_scan_batch over the whole forge in crash-isolated batches.
A batch that segfaults (Oodle on a bad resource) is skipped; all others complete.
Aggregates loc/Arabic hits by hash and writes JSON."""
import subprocess, sys, os, json, time
from collections import Counter, defaultdict

def _load(n):
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
AF = _load("acbf_forge")

fn = sys.argv[1]
batch = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
batch_script = sys.argv[3] if len(sys.argv) > 3 else "acbf_scan_batch.py"
info = AF.parse(fn); n = info["count"]
here = os.path.dirname(os.path.abspath(__file__))
hits = []
crashed = []
t0 = time.time()
for lo in range(0, n, batch):
    hi = min(n, lo + batch)
    p = subprocess.run([sys.executable, os.path.join(here, batch_script), fn, str(lo), str(hi)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 and not p.stdout:
        crashed.append((lo, hi))
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try: hits.append(json.loads(line))
            except Exception: pass
    if lo % 20000 == 0:
        print(f"  {hi}/{n}  hits={len(hits)} crashedBatches={len(crashed)} ({time.time()-t0:.0f}s)", flush=True)
print(f"\nDONE {hi}/{n} hits={len(hits)} crashedBatches={len(crashed)} ({time.time()-t0:.0f}s)")
# aggregate
by_hash = defaultdict(lambda: {"tag": 0, "ar": 0, "n": 0, "sample_tag": "", "sample_ar": ""})
for h in hits:
    d = by_hash[h["hash"]]; d["n"] += 1
    if h["tag"]:
        d["tag"] += 1
        if not d["sample_tag"]: d["sample_tag"] = h["sample"]
    if h["ar"]:
        d["ar"] += 1
        if not d["sample_ar"]: d["sample_ar"] = h["sample"]
print("\nhash : #res : tag : ar : samples")
for hh, d in sorted(by_hash.items(), key=lambda kv: -kv[1]["n"]):
    print(f"  {hh} : {d['n']:>5} : tag={d['tag']:>4} ar={d['ar']:>4}  "
          f"TAG:{d['sample_tag']!r}  AR:{d['sample_ar']!r}")
json.dump({"hits": hits, "crashed": crashed}, open("/tmp/acbf_scan_all.json", "w"), ensure_ascii=False)
print(f"\ncrashed batches: {crashed[:20]}")
print("-> /tmp/acbf_scan_all.json")
