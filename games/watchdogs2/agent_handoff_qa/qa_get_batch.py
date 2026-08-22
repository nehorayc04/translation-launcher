"""Emit the next QA batch for the agent. Flagged (worst) lines FIRST, then the rest.
Reads corpus.json + qa_reviewed.json; writes qa_batch.json [{pk, en, he, flags}].
Prints 'QA done!' when every line has been reviewed.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.json")
REVIEWED = os.path.join(HERE, "qa_reviewed.json")
BATCH = os.path.join(HERE, "qa_batch.json")
SIZE = 40   # SMALL so the agent READS every line itself (never a find/replace dict)

# severity order so the most user-visible defects are fixed first
SEV = ["ENGLISH_LEAK", "UNTRANSLATED", "TOKEN_MISMATCH", "BRACKET", "OVERFLOW",
       "FOREIGN", "NIQQUD", "PLACENAME", "ICON_TOKEN"]
def rank(flags):
    for i, s in enumerate(SEV):
        if s in flags:
            return i
    return len(SEV) + (0 if flags else 1)

def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    reviewed = set(json.load(open(REVIEWED, encoding="utf-8"))) if os.path.exists(REVIEWED) else set()
    todo = [(pk, v) for pk, v in corpus.items() if pk not in reviewed]
    if not todo:
        print("QA done!");
        if os.path.exists(BATCH): os.remove(BATCH)
        return
    todo.sort(key=lambda kv: (rank(kv[1]["flags"]), len(kv[1]["en"])))
    batch = [{"pk": pk, "en": v["en"], "he": v["he"], "flags": v["flags"]}
             for pk, v in todo[:SIZE]]
    json.dump(batch, open(BATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch of {len(batch)} written -> qa_batch.json  ({len(todo)} remaining; "
          f"flagged-first)")

if __name__ == "__main__":
    main()
