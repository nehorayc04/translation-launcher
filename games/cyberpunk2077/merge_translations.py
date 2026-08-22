"""merge_translations.py — write the clean translations from
translation_results.jsonl back into the source spine.

Only rows with translated==true are merged, and each is gated through
cp2077_qa_defects.value_is_clean() so a merge can never introduce a defect.
Backs up each spine file before writing; atomic write; re-verifies.
"""
import os, sys, json, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_qa_defects as Q
import get_next_audit_batch as G

RESULTS = os.path.join(HERE, "translation_results.jsonl")
TARGETS = {"base": G.BASE_TR, "dlc": G.DLC_TR}


def _index(data):
    idx = {}
    for sec, rows in data.items():
        if isinstance(rows, list):
            for e in rows:
                if isinstance(e, dict):
                    for k in ("primaryKey", "stringId"):
                        v = e.get(k)
                        if v not in (None, ""):
                            idx[(sec, str(v))] = e
    return idx


def _atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    rows = [json.loads(l) for l in open(RESULTS, encoding="utf-8") if l.strip()]
    clean = [r for r in rows if r.get("translated")]
    # parse id = project|section|pk|field
    byproj = {"base": [], "dlc": []}
    for r in clean:
        parts = r["id"].split("|")
        if len(parts) < 4:
            continue
        proj, field, pk = parts[0], parts[-1], parts[-2]
        section = "|".join(parts[1:-2])
        byproj.setdefault(proj, []).append((section, pk, field, r["hebrew"]))

    if not Q.acquire_lock("merge_translations"):
        sys.exit("[abort] QA lock held — not safe to write.")
    try:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        merged = rejected = notfound = 0
        for proj, items in byproj.items():
            if not items:
                continue
            path = TARGETS[proj]
            data = json.load(open(path, encoding="utf-8"))
            idx = _index(data)
            applied = 0
            for section, pk, field, he in items:
                e = idx.get((section, str(pk)))
                if not e:
                    notfound += 1; continue
                if not (he and Q.value_is_clean(he)):
                    rejected += 1; continue
                e[field] = he
                applied += 1
            if applied:
                bak = f"{path}.bak.merge.{stamp}"
                shutil.copy2(path, bak)
                _atomic(path, data)
                print(f"[{proj}] merged {applied} -> backup {os.path.basename(bak)}")
            merged += applied
        print(f"MERGED {merged} clean translations  (rejected by clean-gate {rejected}, "
              f"not-found {notfound})")

        # ── verify: the merged fields now hold the new Hebrew ──
        ok = 0
        for proj, items in byproj.items():
            if not items:
                continue
            idx = _index(json.load(open(TARGETS[proj], encoding="utf-8")))
            for section, pk, field, he in items:
                e = idx.get((section, str(pk)))
                if e and e.get(field) == he:
                    ok += 1
        print(f"VERIFY: {ok}/{merged} merged values confirmed in spine")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
