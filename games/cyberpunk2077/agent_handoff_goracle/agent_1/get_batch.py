"""Write the next batch of un-fixed lines to current_batch.json for the agent to fill.
Run this, fill `he_feminine` for every key in current_batch.json, then run merge_batch.py.
Repeat until it prints "All done!"."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
BATCH = 40
def jl(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
tofix = jl(os.path.join(HERE, "to_fix.json"), {})
done  = jl(os.path.join(HERE, "fixed_female.json"), {})
todo = [k for k in tofix if k not in done]
if not todo:
    print("All done! (0 remaining) — nothing to fill.")
    json.dump({}, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"), ensure_ascii=False)
    raise SystemExit
batch = {}
for k in todo[:BATCH]:
    r = tofix[k]
    batch[k] = {
        "en": r["en"],                       # English = MEANING only (do not translate)
        "he_current": r["he_female_current"],# the Hebrew to fix (addressee is MASCULINE / wrong)
        "ar_female": r["ar_female"],         # the game's Arabic feminine = GROUND TRUTH for gender
        "he_feminine": "",                   # << FILL THIS: he_current with the ADDRESSEE flipped to feminine
    }
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"Wrote {len(batch)} lines to current_batch.json  |  remaining: {len(todo)} / {len(tofix)}")
print("Fill 'he_feminine' for EVERY key, then run:  python merge_batch.py")
