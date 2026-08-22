"""One-shot targeted retry for a small hand-picked set of keys the fleet parked.
Run ON a machine that already has cc_nim.py + fleet_providers.py + keys.json deployed.

    python retry_targeted.py targeted.json out.json
"""
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_nim as W

src, dst = sys.argv[1], sys.argv[2]
corpus = json.load(open(src, encoding="utf-8"))
W._KEYS = W.load_keys()

items = list(corpus.items())
result = {}
for k, v in items:
    res, ok, seen = W.do_batch([(k, v)])
    if k in res:
        result[k] = res[k]
        print("OK  ", k, "->", res[k][:60])
    else:
        print("MISS", k, "ok=", ok, "seen=", seen)

json.dump(result, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n{len(result)}/{len(items)} translated -> {dst}")
