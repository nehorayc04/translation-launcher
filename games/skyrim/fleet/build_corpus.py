import json, os, glob
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "corpus.json")
def main():
    rows = {}
    for f in glob.glob(os.path.join(HERE, "review_corpus", "*.final.jsonl")):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip(): continue
                d = json.loads(line)
                rows[d["id"]] = d
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"corpus.json: {len(rows)} rows")
if __name__ == "__main__":
    main()
