# -*- coding: utf-8 -*-
"""Build the New-Era QA corpus for w3qa_nim (line-by-line review of EVERY translated line).

Corpus item = {id: {en, he, ar, ru, pl, es, it}} — the worker derives the gender oracle
(ag/num/formal) itself from ar/ru/pl/es/it, so nothing else is needed.

  * EXCLUDES ids already in w3_newera_passed.json (they went through the New-Era pass).
  * DROPS a mojibake English source (the XOR-corrupt extraction) so the model falls back to
    the clean Arabic instead of "translating" garbage — the w3ut lesson.
  * Ordered by VISIBILITY (UI labels -> base content -> long/DLC prose) so that even a run
    that takes days improves the most-seen text first.
  * Splits into N disjoint slices by a STABLE hash of the id, each keeping that order.

    py build_qa_corpus.py            # report only
    py build_qa_corpus.py --write 2  # write qa_slice_0.json .. qa_slice_<N-1>.json
"""
import json, os, re, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..")
EX = os.path.join(G, "extract")

LANGS = ("ar", "ru", "pl", "es", "it")
MOJI = re.compile("[　-퟿-]")
SENT = re.compile(r"[.!?;:]")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def visibility(en, he, path):
    """0 = most visible (short UI label), 3 = least (long prose / DLC)."""
    base = "content0" in path
    n = len(en or he)
    if n <= 45 and not SENT.search(en or ""):
        return 0 if base else 1
    if n <= 160:
        return 1 if base else 2
    return 2 if base else 3


def main():
    he = load(os.path.join(G, "fleet", "hebrew.json"))
    en = load(os.path.join(EX, "en.json"))
    idx = load(os.path.join(EX, "index.json"))
    other = {l: load(os.path.join(EX, f"{l}.json")) for l in LANGS}
    passed = set(str(x) for x in load(os.path.join(HERE, "w3_newera_passed.json")))
    # Optional: also exclude ids already REVIEWED (a union of the bank keys), so a
    # re-slice across MORE machines splits only the not-yet-reviewed remainder and
    # nothing is re-done. `--exclude <file>` where <file> is a JSON list of ids.
    if "--exclude" in sys.argv:
        exf = sys.argv[sys.argv.index("--exclude") + 1]
        passed |= set(str(x) for x in load(exf))

    rows, skipped_passed, skipped_empty, moji = [], 0, 0, 0
    for k, hv in he.items():
        if not isinstance(hv, str) or not hv.strip():
            skipped_empty += 1
            continue
        if k in passed:
            skipped_passed += 1
            continue
        ev = en.get(k)
        ev = ev if isinstance(ev, str) else ""
        if ev and MOJI.search(ev):
            ev = ""            # corrupt extraction -> rely on Arabic
            moji += 1
        item = {"en": ev, "he": hv}
        for l in LANGS:
            v = other[l].get(k)
            if isinstance(v, str) and v.strip():
                item[l] = v
        # a line with neither English nor Arabic has no ground truth at all
        if not item["en"] and "ar" not in item:
            skipped_empty += 1
            continue
        rows.append((visibility(ev, hv, idx.get(k, "")), k, item))

    rows.sort(key=lambda r: (r[0], r[1]))
    tiers = {}
    for t, _, _ in rows:
        tiers[t] = tiers.get(t, 0) + 1

    print("=== New-Era QA corpus ===")
    print(f"  total hebrew.json      : {len(he)}")
    print(f"  already New-Era passed : {skipped_passed} (excluded)")
    print(f"  no source / empty      : {skipped_empty} (excluded)")
    print(f"  mojibake EN dropped    : {moji} (Arabic used instead)")
    print(f"  TO REVIEW              : {len(rows)}")
    print("  by visibility tier     : " + ", ".join(f"{t}:{tiers[t]}" for t in sorted(tiers)))
    langcov = {l: sum(1 for _, _, it in rows if l in it) for l in LANGS}
    print("  language coverage      : " + ", ".join(f"{l}:{langcov[l]}" for l in LANGS))

    if "--write" not in sys.argv:
        print("\n(report only) re-run with:  --write <N>")
        return
    n = int(sys.argv[sys.argv.index("--write") + 1])
    slices = [{} for _ in range(n)]
    for _, k, item in rows:
        s = int(hashlib.md5(k.encode()).hexdigest(), 16) % n
        slices[s][k] = item
    for i, s in enumerate(slices):
        p = os.path.join(HERE, f"qa_slice_{i}.json")
        json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  wrote {os.path.basename(p)}: {len(s)} lines")
    assert sum(len(s) for s in slices) == len(rows), "slice split lost lines"
    assert len(set().union(*[set(s) for s in slices])) == len(rows), "slices overlap"
    print("  disjoint + complete: OK")


if __name__ == "__main__":
    main()
