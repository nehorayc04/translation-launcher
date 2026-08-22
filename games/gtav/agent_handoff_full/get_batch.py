"""I/O helper — emit the next UNtranslated GTA V strings. Does NOT translate.

Two modes:
  single  : python get_batch.py [SIZE]            -> current_batch.json   (one agent)
  PARALLEL: python get_batch.py <slot> <nslots>   -> current_batch_<slot>.json
            Each string is assigned to ONE slot by a STABLE md5 hash (cross-process
            deterministic — NOT Python's salted hash()), so N agents running at once
            NEVER touch the same string. Each agent merges to its OWN hebrew_<slot>.json,
            so there is no shared-write race either.  e.g.  agent A: get_batch.py 0 2
                                                            agent B: get_batch.py 1 2

Reads  : to_translate.json {english:""}, hebrew.json {english:hebrew},
         hebrew_*.json (per-slot outputs), skip.json [..], reuse_he.json {..}
Prints : "All done!" when nothing remains for this slot.
"""
import glob, hashlib, json, os, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda f: json.load(open(os.path.join(HERE, f), encoding="utf-8"))
exists = lambda f: os.path.exists(os.path.join(HERE, f))

to = J("to_translate.json")
done = set()
if exists("hebrew.json"):
    done |= set(J("hebrew.json"))
for g in glob.glob(os.path.join(HERE, "hebrew_*.json")):
    done |= set(json.load(open(g, encoding="utf-8")))
if exists("skip.json"):
    done |= set(J("skip.json"))
if exists("reuse_he.json"):
    done |= set(J("reuse_he.json"))

args = sys.argv[1:]
if len(args) >= 2:                                   # PARALLEL slot mode
    slot, nslots = int(args[0]), int(args[1])
    size = int(args[2]) if len(args) > 2 else 1500
    md5 = lambda k: int(hashlib.md5(k.encode("utf-8")).hexdigest(), 16)
    rem = [k for k in to if k not in done and md5(k) % nslots == slot]
    out = f"current_batch_{slot}.json"
    tag = f"slot {slot}/{nslots}"
else:                                                # single-agent legacy mode
    size = int(args[0]) if args else 1500
    rem = [k for k in to if k not in done]
    out = "current_batch.json"
    tag = "single"

if not rem:
    print("All done!")
else:
    json.dump({k: "" for k in rem[:size]},
              open(os.path.join(HERE, out), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"[{tag}] batch: {len(rem[:size])} written to {out}  (remaining {len(rem):,})")
