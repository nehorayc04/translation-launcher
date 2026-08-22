"""Emit the next N untranslated Arabic dialogue lines for the agent to translate.
Writes current_batch.json = {id: {"ar": <arabic source>}}. Run repeatedly; when it
prints "All done!" the 313 are finished."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
done = json.load(open(os.path.join(HERE, "done_translate.json"), encoding="utf-8"))
todo = [k for k in src if k not in done]
if not todo:
    print("All done! (%d translated)" % len(done)); sys.exit(0)
batch = {k: {"ar": src[k], "he": ""} for k in todo[:N]}
json.dump(batch, open(os.path.join(HERE, "current_batch.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote current_batch.json: %d lines (%d/%d done). Fill each \"he\", then merge_batch.py."
      % (len(batch), len(done), len(src)))
