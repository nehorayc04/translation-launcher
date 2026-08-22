"""BUG-FIX pass - scan every translated line for STRUCTURAL defects and REMOVE the
bad ones from hebrew.json, so get_batch.py re-serves them and you redo them in the
loop. Run ONCE at the start (and any time to re-verify). Does NOT translate.

Catches: empty / foreign script / niqqud / lost-or-added token / model-refusal leak /
length blow-up / untranslated-English leak (with a name/code passthrough so a proper
noun or pure data-bind kept in Latin is NOT flagged).
Writes qa_removed.json {guid: reason}.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tokens import tokens, strip_tokens  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NIQQUD = re.compile(r"[֑-ׇ]")
BAD = re.compile(r"[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]")
HEB = re.compile(r"[א-ת]")
REFUSAL = re.compile(r"(as an ai|i\s+(cannot|can'?t|am unable|am sorry)|here('?s| is) the translation"
                     r"|אינני יכול לתרגם|לא ניתן לתרגם)", re.I)

src = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()

bad = {}
for k, he in heb.items():
    if k in skip:
        continue
    en = src.get(k, "")
    r = None
    if not he or not he.strip():
        r = "empty"
    elif BAD.search(he):
        r = "foreign_script"
    elif NIQQUD.search(he):
        r = "niqqud"
    elif Counter(tokens(en)) != Counter(tokens(he)):
        r = "token_mismatch"
    elif REFUSAL.search(he):
        r = "refusal_leak"
    elif len(en) >= 8 and len(he) > 2.4 * len(en) + 40:
        r = "length_anomaly"
    elif he.strip() == en.strip() and not HEB.search(he):
        core = strip_tokens(en).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r"[a-z]{2,}", core)
        is_handle = (" " not in core and bool(re.search(r"[a-z][A-Z]", core)
                     or re.search(r"\d", core) or len(core) >= 11))
        if core and not (is_namey or no_real_word or is_handle):
            r = "untranslated"   # name/code passthrough (MUST match the translator rule)
    if r:
        bad[k] = r

if bad:
    for k in bad:
        heb.pop(k, None)
    json.dump(heb, open("hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace("hebrew.json.tmp", "hebrew.json")
    json.dump(bad, open("qa_removed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"removed {len(bad)} defective (now {len(heb)} good) -> redo in the loop. see qa_removed.json")
