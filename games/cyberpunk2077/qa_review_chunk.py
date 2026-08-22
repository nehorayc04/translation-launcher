"""qa_review_chunk.py — split an Opus-QA batch file into fixed-size chunk
files so a fleet of reviewer subagents can each Read one slice.

Usage: python qa_review_chunk.py <batch.json> <out_dir> <chunk_size>
Prints the number of chunks written (the workflow reads this as args.chunkCount).
Chunk files are named chunk_000.json, chunk_001.json, ...
"""
import json, os, sys

def main():
    batch_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opus_qa_batch.json"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opus_qa_chunks"
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    batch = json.load(open(batch_path, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    # wipe stale chunk + per-chunk fixes + collected from a previous run
    for fn in os.listdir(out_dir):
        if (fn.startswith("chunk_") or fn.startswith("fixes_") or fn == "collected.json") and fn.endswith(".json"):
            os.remove(os.path.join(out_dir, fn))
    n = 0
    for i in range(0, len(batch), size):
        chunk = batch[i:i + size]
        with open(os.path.join(out_dir, f"chunk_{n:03d}.json"), "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=1)
        n += 1
    print(n)

if __name__ == "__main__":
    main()
