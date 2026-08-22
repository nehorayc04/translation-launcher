import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.json")
SHARDS = os.path.join(HERE, "shards")
MACHINES = ["desktop", "laptop", "vm4", "vm5", "vm", "vm2", "vm3"]
PROVIDERS = ["groq", "sambanova", "nim"]
def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    streams = [(m, p) for m in MACHINES for p in PROVIDERS]
    n = len(streams)
    buckets = {s: {} for s in streams}
    for i, (k, v) in enumerate(corpus.items()):
        buckets[streams[i % n]][k] = v
    os.makedirs(SHARDS, exist_ok=True)
    for (m, p), d in buckets.items():
        path = os.path.join(SHARDS, f"corpus_{m}_{p}.json")
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {m:<10} {p:<10} {len(d):>6,} lines")
if __name__ == "__main__":
    main()
