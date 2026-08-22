"""BUG-FIX pass — scan every already-translated line for STRUCTURAL defects and
REMOVE the bad ones from hebrew.json, so get_batch.py re-serves them and you
re-translate them correctly in the normal loop. Run this ONCE at the start (and
again any time you want to re-verify). Does NOT translate.

Catches: empty · foreign script · niqqud · lost/added tokens · model-refusal
leak · length blow-up (rambling) · untranslated English leak (with a name/code
passthrough so a proper noun kept in Latin is NOT flagged).
Writes qa_removed.json {id: reason} for your record.
"""
import json, re, os
from collections import Counter

TOKEN = re.compile(
    r'\[CSS_[A-Z]+\]|\[[A-Z][A-Za-z0-9_]*\]|\{[^}]*\}'
    r'|%[0-9.]*[diufslxX]+|%%|&#?[A-Za-z0-9]+;')
NIQQUD = re.compile(r'[֑-ׇ]')
BAD    = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')
HEB    = re.compile(r'[א-ת]')
REFUSAL = re.compile(
    r"(as an ai|i\s+(cannot|can'?t|am unable|am sorry|apolog)"
    r"|unable to (translate|comply|process)|cannot (translate|comply|fulfil)"
    r"|here('?s| is) the translation|i\s+don'?t\s+understand"
    r"|לתרגם את הבקשה|אינני יכול לתרגם|לא ניתן לתרגם)", re.I)

src = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()
bad = {}
for k, he in heb.items():
    if k in skip:        # untranslatable-by-design — never flag
        continue
    en = src.get(k, "")
    r = None
    if not he or not he.strip():
        r = "empty"
    elif BAD.search(he):
        r = "foreign_script"
    elif NIQQUD.search(he):
        r = "niqqud"
    elif Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(he)):
        r = "placeholder_mismatch"
    elif REFUSAL.search(he):
        r = "refusal_leak"
    elif len(en) >= 8 and len(he) > 2.4 * len(en) + 40:
        r = "length_anomaly"
    elif he.strip() == en.strip() and not HEB.search(he):
        core = TOKEN.sub("", en).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        # single-token camelCase / has-digit / long concatenation = a handle/id
        # ("doneGOOFED") — stays Latin, not a defect.
        is_handle = (" " not in core and
                     bool(re.search(r'[a-z][A-Z]', core) or re.search(r'\d', core) or len(core) >= 11))
        if core and not (is_namey or no_real_word or is_handle):
            r = "untranslated"
    if r:
        bad[k] = r

if bad:
    for k in bad:
        heb.pop(k, None)
    tmp = "hebrew.json.tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, "hebrew.json")
    json.dump(bad, open("qa_removed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"scanned {len(src)} source ids; removed {len(bad)} defective from hebrew.json "
      f"(now {len(heb)} good). They are untranslated again -> re-do them in the loop. "
      f"see qa_removed.json")
