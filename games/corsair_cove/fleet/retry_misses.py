"""Retry the specific keys still missing after retry_targeted.py, a few extra times each --
the model occasionally avoids whatever pattern triggered a token-drop or a false gender flag
on a fresh sample."""
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_nim as W

src, prev_out, dst = sys.argv[1], sys.argv[2], sys.argv[3]
corpus = json.load(open(src, encoding="utf-8"))
done = json.load(open(prev_out, encoding="utf-8")) if os.path.exists(prev_out) else {}
W._KEYS = W.load_keys()

missing = [k for k in corpus if k not in done]
print(f"{len(missing)} still missing: {missing}")

result = dict(done)
for k in missing:
    v = corpus[k]
    for attempt in range(1, 4):
        res, ok, seen = W.do_batch([(k, v)])
        if k in res:
            result[k] = res[k]
            print(f"OK  (try {attempt}) {k} -> {res[k][:70]}")
            break
        print(f"  still failing try {attempt} for {k}")
    else:
        print(f"GIVE UP after 3 tries: {k}")

json.dump(result, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n{len(result)}/{len(corpus)} total -> {dst}")
