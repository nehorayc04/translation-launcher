"""Emit the next batch of BROKEN lines for the fix-only flow. Reads this folder's
corpus.json (already filtered to defect lines, each tagged with `defect`) +
fix_done.json; writes fix_batch.json [{key, en, he, defect, hint}]. No auto-pull
(hard-capped to the assigned slice). 'QA done!' only when the slice is drained.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 25  # smaller than review — each line needs a real rewrite

HINTS = {
    "foreign": "יש כאן אות בכתב זר (גרמנית/פולנית/וייטנאמית...) בתוך העברית — תרגם אותה לעברית.",
    "seam": "עברית ולטינית מודבקות יחד (כמו 'גילherme') — תקן את התעתיק/הפרד נכון.",
    "truncated": "המשפט העברי נקטע באמצע מחשבה — השלם אותו מתוך ה-EN, מלא ונכון.",
}


def L(n): return os.path.join(HERE, n)


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def main():
    corpus = jload(L("corpus.json"), {})
    done = set(jload(L("fix_done.json"), []))
    todo = [k for k in corpus if k not in done]
    if not todo:
        print("QA done!")
        if os.path.exists(L("fix_batch.json")):
            os.remove(L("fix_batch.json"))
        return
    todo.sort(key=lambda k: len(corpus[k]["en"]))   # short, definite ones first
    batch = []
    for k in todo[:SIZE]:
        r = corpus[k]
        batch.append({"key": k, "en": r["en"], "he": r["he"],
                      "defect": r.get("defect", ""), "hint": HINTS.get(r.get("defect", ""), "")})
    json.dump(batch, open(L("fix_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch of {len(batch)} BROKEN lines -> fix_batch.json  ({len(todo)} left in this slice)")


if __name__ == "__main__":
    main()
