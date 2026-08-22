# One-off worker-pipeline probe. Prints ONLY the result/error — never the key.
import importlib.util, json, time, sys
spec = importlib.util.spec_from_file_location("w", "w3ut_nim.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._KEYS = m.load_keys(); m._KI = 0
c = json.load(open("corpus.json", encoding="utf-8"))
out = {}
try: out = json.load(open("out.json", encoding="utf-8"))
except Exception: pass
rem = [k for k in c if k not in out]
# pick 3 clean real lines still remaining (prefer english narrative)
picks = []
for k in rem:
    v = c[k]; st = m.src_text(v)
    if len(st) > 30 and len(picks) < 3:
        picks.append(k)
print("remaining=", len(rem), "probing", picks)
for k in picks:
    v = c[k]; t = time.time()
    src = m.src_text(v)[:50]
    try:
        r = m.do_batch([(k, v)])
        dt = round(time.time() - t, 1)
        if k in r:
            print(f"OK  {k} [{dt}s] src={src!r} -> HE={r[k][:70]!r}")
        else:
            # why rejected? re-run the raw chat to see
            print(f"REJECT {k} [{dt}s] src={src!r} (do_batch returned nothing)")
    except Exception as e:
        print(f"ERR {k} [{round(time.time()-t,1)}s] {type(e).__name__}: {str(e)[:140]}")
