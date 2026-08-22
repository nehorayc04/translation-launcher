"""Split the AC2 New-Era corpus into N disjoint slices (stable md5 partition) - one per stream.

Order inside each slice = UI first (highest visibility), then subtitles, short lines before long
ones, so the menus a player sees immediately are translated first.
"""
import sys, os, json, hashlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = sys.argv[1] if len(sys.argv) > 1 else r"c:/tmp/ac2_corpus.json"
STREAMS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["vm3", "desktop"]

corpus = json.load(open(CORPUS, encoding="utf-8"))
done = {}
bank = os.path.join(HERE, "banks")
if os.path.isdir(bank):
    for f in os.listdir(bank):
        if f.startswith("out_") and f.endswith(".json"):
            try: done.update(json.load(open(os.path.join(bank, f), encoding="utf-8")))
            except Exception: pass
heb = os.path.join(HERE, "hebrew.json")
if os.path.exists(heb):
    try: done.update(json.load(open(heb, encoding="utf-8")))
    except Exception: pass

todo = {k: v for k, v in corpus.items() if k not in done}
print(f"corpus {len(corpus)} | already translated {len(done)} | to do {len(todo)}")


def rank(item):
    k, v = item
    return (0 if k.startswith("ui:") else 1, len(v["en"]))


n = len(STREAMS)
slices = {s: {} for s in STREAMS}
for k, v in sorted(todo.items(), key=rank):
    i = int(hashlib.md5(k.encode()).hexdigest(), 16) % n
    slices[STREAMS[i]][k] = v
os.makedirs(os.path.join(HERE, "splits"), exist_ok=True)
for s, d in slices.items():
    p = os.path.join(HERE, "splits", f"corpus_{s}.json")
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    ui = sum(1 for k in d if k.startswith("ui:"))
    ch = sum(len(v["en"]) for v in d.values())
    print(f"  {s:8} {len(d):6} lines  (ui {ui}, sub {len(d)-ui})  {ch:,} chars -> {p}")
