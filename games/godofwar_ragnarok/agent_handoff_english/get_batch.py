"""Emit the next N half-English GoWR strings for the agent to COMPLETE into Hebrew.
Writes current_batch.json = {id: {he_partial, en, ar, he:""}}. Loop until "All done!"."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
done_p = os.path.join(HERE, "done_translate.json")
done = json.load(open(done_p, encoding="utf-8")) if os.path.exists(done_p) else {}
todo = [k for k in src if k not in done]
if not todo:
    print("All done! (%d completed)" % len(done)); sys.exit(0)
batch = {k: {**src[k], "he": ""} for k in todo[:N]}
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote current_batch.json: %d lines (%d/%d done). Fill each \"he\", then merge_batch.py."
      % (len(batch), len(done), len(src)))
