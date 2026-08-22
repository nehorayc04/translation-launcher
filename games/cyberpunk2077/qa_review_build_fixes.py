"""qa_review_build_fixes.py — turn the workflow's collected reviewer fixes into
the opus_qa_fixes.jsonl that qa_review_apply.py consumes.

The reviewer agents return {pk, sec(basename), new, reason}. They do NOT echo
`old` (LLMs mangle control bytes / exact whitespace). We reconstruct `old`
byte-exact from the batch file (whose `he` came straight from the spine), so the
apply's `old == current` guard is reliable.

Guards:
  * leading control byte (ord < 0x20): if `old` starts with one and `new` does
    not start with the same byte, prepend it — never drop the markup-parse byte.
  * skip no-ops (new == old) and unknown (pk,sec) not present in the batch.
  * dedup by (sec, pk), first write wins.

Usage: python qa_review_build_fixes.py <collected_fixes.json> <batch.json>
Writes universal/opus_qa_fixes.jsonl (append-safe: overwrites).
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "universal")
OUT = os.path.join(UNIV, "opus_qa_fixes.jsonl")


def main():
    collected_path = sys.argv[1]
    batch_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opus_qa_batch.json"
    collected = json.load(open(collected_path, encoding="utf-8"))
    if isinstance(collected, dict):
        collected = collected.get("kept") or collected.get("fixes") or []
    batch = json.load(open(batch_path, encoding="utf-8"))
    # (basename_sec, pk) -> current HE  (byte-exact spine value)
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
        # control-byte guard
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
    print(f"built {len(rows)} fixes -> {os.path.basename(OUT)} (skipped {skipped})")


if __name__ == "__main__":
    main()
