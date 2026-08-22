"""Merge ALL trans_part_*.json (any count) into hebrew.json with the same
validation as loop_merge (tokens multiset / foreign script / niqqud), fold ALL
skip_part_*.json into skip.json, sync to ../work/hebrew.json, print status.
"""
import glob, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tokens import tokens  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NIQQUD = re.compile(r"[֑-ׇ]")
BAD = re.compile(r"[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]")

src = json.load(open("to_translate.json", encoding="utf-8"))
merged, problems = {}, []
bad_files = []
for p in sorted(glob.glob("trans_part_*.json")):
    try:
        data = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        bad_files.append((p, str(e)[:60]))
        continue
    for k, he in data.items():
        en = src.get(k, "")
        if he:
            he = NIQQUD.sub("", he).replace("‏", "").replace("‎", "")  # niqqud/zero-width are safe to drop
        if not he or not he.strip():
            problems.append((k, "EMPTY"))
        elif Counter(tokens(en)) != Counter(tokens(he)):
            problems.append((k, "TAG"))
        elif BAD.search(he):
            problems.append((k, "FOREIGN"))
        else:
            merged[k] = he

if merged:
    heb = json.load(open("hebrew.json", encoding="utf-8"))
    heb.update(merged)
    json.dump(heb, open("hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace("hebrew.json.tmp", "hebrew.json")

# fold skips
sp = "skip.json"
sk = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else []
seen = set(sk)
nadd = 0
for p in sorted(glob.glob("skip_part_*.json")):
    for g in json.load(open(p, encoding="utf-8")):
        g = str(g)
        if g not in seen:
            sk.append(g); seen.add(g); nadd += 1
json.dump(sk, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# sync to work
heb = json.load(open("hebrew.json", encoding="utf-8"))
json.dump(heb, open(os.path.join("..", "work", "hebrew.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)

rem = sorted([k for k in src if k not in heb and k not in seen], key=lambda x: int(x))
by = Counter(r for _, r in problems)
print(f"merged {len(merged)} | rejected {len(problems)} {dict(by)} | skip+={nadd} | total {len(heb)} | remaining {len(rem)}")
if bad_files:
    print("UNPARSEABLE (re-queued):", bad_files)
