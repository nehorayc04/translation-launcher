"""qa_review_finish.py — merge the workflow's per-chunk fixes (fixes_*.json in
the chunk dir) and build universal/opus_qa_fixes.jsonl for qa_review_apply.py.

Reviewer agents return {pk, sec(basename), new, reason}; they do NOT echo `old`
(LLMs mangle control bytes / exact whitespace). We reconstruct `old` byte-exact
from the batch file (whose `he` came straight from the spine), so the apply's
`old == current` guard is reliable.

Guards: leading control byte preserved; skip no-ops + unknown (pk,sec); dedup.

Usage: python qa_review_finish.py <chunkDir> <batch.json>
"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "universal")
OUT = os.path.join(UNIV, "opus_qa_fixes.jsonl")


def main():
    chunk_dir = sys.argv[1]
    batch_path = sys.argv[2]
    # merge
    collected = []
    bad = []
    for f in sorted(glob.glob(os.path.join(chunk_dir, "fixes_*.json"))):
        try:
            arr = json.load(open(f, encoding="utf-8"))
            if isinstance(arr, list):
                collected.extend(arr)
            else:
                bad.append(os.path.basename(f))
        except Exception as e:
            bad.append(f"{os.path.basename(f)}:{str(e)[:40]}")
    batch = json.load(open(batch_path, encoding="utf-8"))
    cur = {(e["sec"], str(e["pk"])): e["he"] for e in batch}

    seen = set()
    rows, skipped = [], 0
    for fx in collected:
        sec = fx.get("sec", "")
        pk = str(fx.get("pk", ""))
        new = fx.get("new", "")
        key = (sec, pk)
        if key in seen:
            continue
        old = cur.get(key)
        if old is None:
            skipped += 1
            continue
        if old and ord(old[0]) < 0x20 and (not new or new[0] != old[0]):
            new = old[0] + new
        if not new or new == old:
            skipped += 1
            continue
        seen.add(key)
        full_sec = sec if "/" in sec else "onscreens/" + sec
        rows.append({"sec": full_sec, "pk": pk, "field": "femaleVariant",
                     "old": old, "new": new, "reason": fx.get("reason", "")})

    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"merged {len(collected)} (bad={bad}) -> built {len(rows)} fixes, skipped {skipped}")


if __name__ == "__main__":
    main()
