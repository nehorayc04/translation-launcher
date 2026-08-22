# -*- coding: utf-8 -*-
"""Fill current_batch.json with the next N items still missing a correct male variant.
Usage: python get_batch.py [N]   (default N=80). Run from THIS agent folder."""
import json, os, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 80

todo = json.load(open(os.path.join(HERE, "to_fix.json"), encoding="utf-8"))
donep = os.path.join(HERE, "fixed_male.json")
done = json.load(open(donep, encoding="utf-8")) if os.path.exists(donep) else {}

remaining = [k for k in todo if k not in done]
if not remaining:
    print("All done!")
    sys.exit(0)

batch = {}
for k in remaining[:N]:
    it = todo[k]
    batch[k] = {
        "en": it.get("en", ""),
        "he_female": it["he_female"],
        "he_male_current": it.get("he_male", ""),
        "fixed_male": "",
    }
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"{len(remaining)} items remaining. Wrote {len(batch)} to current_batch.json.")
print("Fill the 'fixed_male' field for each item, then run: python merge_batch.py")
