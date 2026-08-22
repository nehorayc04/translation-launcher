"""qa_review_commit_completed.py — SHORT-SAVE commit. Marks reviewed ONLY the
entries from chunks that actually completed (a fixes_<NNN>.json exists on disk
next to chunk_<NNN>.json). A chunk whose review failed (e.g. session limit)
writes no fixes file, so it stays uncommitted and is re-reviewed next run — no
600-line batch is lost when a workflow is interrupted mid-flight.

Usage: python qa_review_commit_completed.py <chunkDir>
"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "universal")
CHECKPOINT = os.path.join(UNIV, "opus_qa_checkpoint.json")


def main():
    chunk_dir = sys.argv[1]
    reviewed = set()
    if os.path.exists(CHECKPOINT):
        reviewed = set(json.load(open(CHECKPOINT, encoding="utf-8")).get("reviewed", []))
    before = len(reviewed)
    committed_chunks = 0
    for fx in sorted(glob.glob(os.path.join(chunk_dir, "fixes_*.json"))):
        idx = os.path.basename(fx)[len("fixes_"):-len(".json")]
        chunk_path = os.path.join(chunk_dir, f"chunk_{idx}.json")
        if not os.path.exists(chunk_path):
            continue
        for e in json.load(open(chunk_path, encoding="utf-8")):
            reviewed.add(e["key"])
        committed_chunks += 1
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"reviewed": sorted(reviewed)}, f, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT)
    print(f"committed {committed_chunks} completed chunks; reviewed total "
          f"{len(reviewed)} (+{len(reviewed) - before} this run)")


if __name__ == "__main__":
    main()
