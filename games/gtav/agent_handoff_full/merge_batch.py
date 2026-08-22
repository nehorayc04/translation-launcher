"""I/O helper — validate + merge a filled batch. Does NOT translate.

Two modes:
  single  : python merge_batch.py        current_batch.json   -> hebrew.json
  PARALLEL: python merge_batch.py <slot>  current_batch_<slot>.json -> hebrew_<slot>.json
            Each agent writes ONLY its own hebrew_<slot>.json -> no shared-write race.

Validation (per entry vs its English key):
  * non-empty Hebrew
  * GTA token/placeholder multiset preserved (~..~ tokens, <..> tags, %d/%s/%%)
  * no foreign script, no niqqud
  * NO-HEBREW on real prose is REJECTED (blocks the 'fill empty keys with English'
    cheat) — a name/code/label with no translatable word is allowed to stay English.
A rejected entry stays in the batch (fix it, re-run); it is never silently merged.
"""
import json, os, re, sys
from collections import Counter
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifxX]+|%%")
NIQQUD = re.compile(r"[֑-ׇ]")
BAD = re.compile(r"[؀-ۿЀ-ӿͰ-Ͽ฀-๿"
                 r"ऀ-ॿ一-鿿가-힯]")
HEB = re.compile(r"[א-ת]")


def real_prose(en):
    """True when the English source is real prose (>=2 lowercase words >=3 chars) —
    it MUST be Hebrew. A name/code/label is allowed to stay English."""
    core = re.sub(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[a-zA-Z]|[^A-Za-z ]", " ", en or "")
    return sum(1 for w in core.split() if len(w) >= 3 and w.islower()) >= 2


arg = sys.argv[1] if len(sys.argv) > 1 else None
if arg is not None:                                  # PARALLEL slot mode
    slot = int(arg)
    batch_path = os.path.join(HERE, f"current_batch_{slot}.json")
    out_path = os.path.join(HERE, f"hebrew_{slot}.json")
else:                                                # single-agent legacy mode
    batch_path = os.path.join(HERE, "current_batch.json")
    out_path = os.path.join(HERE, "hebrew.json")

if not os.path.exists(batch_path):
    print(f"no {os.path.basename(batch_path)} — run get_batch.py first"); sys.exit(0)
batch = json.load(open(batch_path, encoding="utf-8"))

merged, problems = {}, []
for en, he in batch.items():
    if not he or not str(he).strip():
        problems.append((en, "EMPTY")); continue
    if Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(he)):
        problems.append((en, "TOKEN MISMATCH")); continue
    if BAD.search(he):
        problems.append((en, "FOREIGN SCRIPT")); continue
    if NIQQUD.search(he):
        problems.append((en, "NIQQUD")); continue
    if not HEB.search(he) and real_prose(en):
        problems.append((en, "NO HEBREW (prose left English — translate it!)")); continue
    merged[en] = he

if problems:
    for en, r in problems[:60]:
        print(f"{r}: en={en[:60]!r}")
    print(f"--- {len(problems)} problem entries — fix ONLY those in {os.path.basename(batch_path)}, re-run ---")

if merged:
    heb = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    heb.update(merged)
    tmp = out_path + ".tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, out_path)
    print(f"merged {len(merged)} clean -> {os.path.basename(out_path)} (total {len(heb):,})")
else:
    print("nothing merged")
