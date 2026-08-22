# Split out.json into out_groq/out_sambanova/out_nim.json by md5%3 (so 3 pinned workers resume,
# not restart). Idempotent: merges into any existing per-provider out file.
import json, os, hashlib
d = os.path.dirname(os.path.abspath(__file__))
o = os.path.join(d, "out.json")
old = json.load(open(o, encoding="utf-8")) if os.path.exists(o) else {}
names = {0: "groq", 1: "sambanova", 2: "nim"}
buck = {0: {}, 1: {}, 2: {}}
for k, v in old.items():
    buck[int(hashlib.md5(k.encode()).hexdigest(), 16) % 3][k] = v
for i, nm in names.items():
    p = os.path.join(d, f"out_{nm}.json")
    cur = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    cur.update(buck[i])
    json.dump(cur, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"out_{nm}.json {len(cur)}")
