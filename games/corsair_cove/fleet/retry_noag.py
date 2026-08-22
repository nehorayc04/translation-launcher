"""Retry ONE key with its 'ag' field stripped -- for self-addressed monologue lines
(ad="self") where the gender guard mistakes a THIRD-PERSON feminine verb about a female
character (e.g. "he wants" -> "hi rotza") for a second-person address. Hebrew present tense
uses the identical form for 2nd-fem-singular and 3rd-fem-singular, so the guard cannot tell
"at rotza" (you-fem want) from "hi rotza" (she wants) by shape alone -- and there IS no real
addressee on a monologue line, so the constraint should never have applied here."""
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_nim as W

src, key, dst = sys.argv[1], sys.argv[2], sys.argv[3]
corpus = json.load(open(src, encoding="utf-8"))
v = dict(corpus[key])
v.pop("ag", None)
W._KEYS = W.load_keys()

result = {}
for attempt in range(1, 4):
    res, ok, seen = W.do_batch([(key, v)])
    if key in res:
        result[key] = res[key]
        print(f"OK (try {attempt}): {res[key]}")
        break
    print(f"still failing try {attempt}")
else:
    print("GIVE UP")

json.dump(result, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
