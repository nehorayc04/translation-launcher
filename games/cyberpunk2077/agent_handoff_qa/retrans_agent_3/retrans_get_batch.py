"""Emit the next RE-TRANSLATE batch (CP2077). Each line is translated FRESH from
the English — the current Hebrew is deliberately NOT shown, so the agent must
actually translate (it cannot copy/bulk-"OK"). Reads this folder's corpus.json +
retrans_done.json; writes retrans_batch.json [{key, en}]. No auto-pull.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 20


def L(n): return os.path.join(HERE, n)


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def main():
    corpus = jload(L("corpus.json"), {})
    done = set(jload(L("retrans_done.json"), []))
    todo = [k for k in corpus if k not in done]
    if not todo:
        print("QA done!")
        if os.path.exists(L("retrans_batch.json")):
            os.remove(L("retrans_batch.json"))
        return
    todo.sort(key=lambda k: len(corpus[k]["en"]))
    batch = [{"key": k, "en": corpus[k]["en"]} for k in todo[:SIZE]]
    json.dump(batch, open(L("retrans_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch of {len(batch)} lines to TRANSLATE -> retrans_batch.json  ({len(todo)} left in this slice)")


if __name__ == "__main__":
    main()
