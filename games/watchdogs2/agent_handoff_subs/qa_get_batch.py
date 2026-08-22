"""QA loop — emit the next batch of ALREADY-TRANSLATED lines for YOU to review.
Does NOT translate. Reads to_translate.json + hebrew.json + skip.json + qa_reviewed.json.
Writes qa_batch.json = [{pk, en, he}] (next SIZE lines not yet QA-reviewed).
Prints "QA done!" when every translated line has been reviewed.
"""
import json, os
SIZE = 400
to  = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()
reviewed = set(json.load(open("qa_reviewed.json", encoding="utf-8"))) if os.path.exists("qa_reviewed.json") else set()
# review every translated line (in hebrew, not skip) that hasn't been QA'd yet
todo = sorted([k for k in heb if k not in skip and k not in reviewed and k in to], key=lambda x: int(x))
if not todo:
    print("QA done!")
else:
    batch = [{"pk": k, "en": to[k], "he": heb[k]} for k in todo[:SIZE]]
    json.dump(batch, open("qa_batch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"qa_batch: {len(batch)} lines to review  (remaining {len(todo)})")
