"""Emit the next 40-line QA batch (CP2077). Reads this folder's corpus.json +
qa_reviewed.json; writes qa_batch.json [{key, en, he}].

AUTO-PULL: when this folder's slice is fully reviewed, atomically CLAIM the next
CLAIM lines from the GLOBAL pool (../corpus.json) — excluding everything already
reviewed globally and every other agent's claimed slice — append them here, and
keep going. So one session grinds chunk after chunk with no manual re-prep. Prints
"QA done!" only when the WHOLE global pool is exhausted. SIZE small on purpose so
the agent READS every line (never a find/replace dict).
"""
import json, os, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIZE = 40
CLAIM = 500


def L(n): return os.path.join(HERE, n)
def R(n): return os.path.join(ROOT, n)


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def claim_more():
    """Atomically pull the next CLAIM unclaimed+unreviewed lines into this folder."""
    pool = jload(R("corpus.json"), {})
    lock = R("pool.lock")
    try:                                   # break a stale lock (crashed holder)
        if os.path.isdir(lock) and time.time() - os.path.getmtime(lock) > 30:
            os.rmdir(lock)
    except Exception:
        pass
    got = False
    for _ in range(100):
        try:
            os.mkdir(lock); got = True; break
        except FileExistsError:
            time.sleep(0.3)
    if not got:
        return 0
    try:
        taken = set(jload(R("progress_reviewed.json"), []))
        for d in glob.glob(R("agent_*")):
            if os.path.isdir(d):
                taken |= set(jload(os.path.join(d, "corpus.json"), {}).keys())
        cand = [(k, v) for k, v in pool.items() if k not in taken]
        cand.sort(key=lambda kv: len(kv[1]["en"]), reverse=True)
        nxt = cand[:CLAIM]
        if nxt:
            corpus = jload(L("corpus.json"), {})
            corpus.update(dict(nxt))
            json.dump(corpus, open(L("corpus.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
        return len(nxt)
    finally:
        try: os.rmdir(lock)
        except Exception: pass


def main():
    corpus = jload(L("corpus.json"), {})
    reviewed = set(jload(L("qa_reviewed.json"), []))
    todo = [k for k in corpus if k not in reviewed]
    if not todo:
        # AUTO-PULL DISABLED (2026-06-30): scripting agents exploited claim_more to
        # chew the whole global pool with junk (10k lines in minutes). An agent is
        # now hard-capped to its own assigned slice — finishing it ends the session.
        print("QA done!")
        if os.path.exists(L("qa_batch.json")):
            os.remove(L("qa_batch.json"))
        return
    todo.sort(key=lambda k: len(corpus[k]["en"]), reverse=True)
    batch = [{"key": k, "en": corpus[k]["en"], "he": corpus[k]["he"]} for k in todo[:SIZE]]
    json.dump(batch, open(L("qa_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch of {len(batch)} written -> qa_batch.json  ({len(todo)} remaining in this slice)")


if __name__ == "__main__":
    main()
