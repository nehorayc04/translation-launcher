"""Setup for parallel agents. Carve the next N UNtranslated strings into PARTS
source files src_part_1.json..src_part_K.json ({guid: english}), and clear any
stale trans_part_*/skip_part_* from a prior round.
Usage: python make_parts.py [N] [PARTS]   (defaults 800 4)
"""
import json, math, os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 800
PARTS = int(sys.argv[2]) if len(sys.argv) > 2 else 4

to = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()

rem = sorted([k for k in to if k not in heb and k not in skip], key=lambda x: int(x))
take = rem[:N]

# clear stale round files
for i in range(1, PARTS + 1):
    for pat in (f"trans_part_{i}.json", f"skip_part_{i}.json", f"src_part_{i}.json"):
        if os.path.exists(pat):
            os.remove(pat)

per = max(1, math.ceil(len(take) / PARTS))
for i in range(PARTS):
    chunk = take[i * per:(i + 1) * per]
    json.dump({k: to[k] for k in chunk}, open(f"src_part_{i+1}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
print(f"carved {len(take)} untranslated into {PARTS} src_part files (remaining total {len(rem)})")
