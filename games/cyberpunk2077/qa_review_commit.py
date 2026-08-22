"""qa_review_commit.py — mark a reviewed batch's keys as done in the Opus-QA
checkpoint sidecar (universal/opus_qa_checkpoint.json). NO spine write, NO
lock needed — lets the read-only review loop advance while a writer holds the
QA lock. Usage: python qa_review_commit.py <batch.json>
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "universal")
CHECKPOINT = os.path.join(UNIV, "opus_qa_checkpoint.json")


def main():
    batch_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opus_qa_batch.json"
    batch = json.load(open(batch_path, encoding="utf-8"))
    reviewed = set()
    if os.path.exists(CHECKPOINT):
        reviewed = set(json.load(open(CHECKPOINT, encoding="utf-8")).get("reviewed", []))
    for e in batch:
        reviewed.add(e["key"])
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"reviewed": sorted(reviewed)}, f, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT)
    print(f"checkpoint reviewed total: {len(reviewed)} (+{len(batch)} this batch)")


if __name__ == "__main__":
    main()
