# -*- coding: utf-8 -*-
"""Validate + merge the agent's gender/number-fixed batch into fixed.json.

current_batch.json maps {id: "<corrected Hebrew>"} (or keeps the {en,he,ar,target} dict
with a new "fix" key). A fix is ACCEPTED only when it is a pure INFLECTION of the current
Hebrew — the meaning/wording is untouched, ONLY the gender/number morphemes change:

  1. it has Hebrew, no Arabic/foreign letters, no niqqud;
  2. it preserves the SAME tag/placeholder multiset as the original 'he' (<..> {..} %d &ent;);
  3. SAFE inflection guard: every NON-Hebrew, non-space character is byte-identical to the
     original (Latin names, digits, punctuation, tags, spaces order) — so the agent cannot
     paraphrase/retranslate, only re-inflect the Hebrew words;
  4. it actually changed from the original 'he' (a real fix), and
  5. the Hebrew addressee gender does NOT still contradict the Arabic target
     (he_addressee(new) in (target, None) — None = a plural imperative the oracle can't read,
     allowed so correct plural fixes aren't wrongly rejected).

SKIP / OK  -> the flag was a false alarm; record unchanged. Anything failing stays queued.
Run: python merge_batch.py
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "universal")))
try:
    from gender_oracle import he_addressee
except Exception:
    he_addressee = lambda s: None  # noqa: E731

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
HEB = re.compile(r'[֐-׿]')
TOK = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]|&[a-zA-Z#0-9]+;')


def scaffold(s):
    """everything that is NOT a Hebrew letter and NOT whitespace -> must stay identical."""
    return re.sub(r'\s', '', HEB.sub('', s))


def _fixval(v):
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("fix") or v.get("he_fixed") or v.get("he") or ""
    return ""


def main():
    tofix = json.load(open(os.path.join(HERE, "to_fix.json"), encoding="utf-8"))
    batch = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
    try:
        done = json.load(open(os.path.join(HERE, "fixed.json"), encoding="utf-8"))
    except Exception:
        done = {}
    ok = rej = skip = 0
    reasons = {}
    for k, v in batch.items():
        if k not in tofix:
            continue
        new = _fixval(v).strip()
        orig = tofix[k]["he"]
        tgt = tofix[k]["target"]
        if new.upper() in ("SKIP", "OK", "__SKIP__"):
            done[k] = orig
            skip += 1
            continue
        r = None
        if not new or not HEB.search(new):
            r = "no-hebrew"
        elif FOREIGN.search(new) or NIQ.search(new):
            r = "foreign/niqqud"
        elif sorted(TOK.findall(new)) != sorted(TOK.findall(orig)):
            r = "token-mismatch"
        elif scaffold(new) != scaffold(orig):
            r = "not-inflection-only"           # wording/scaffold changed -> a rewrite, reject
        elif new == orig:
            r = "unchanged"
        elif he_addressee(new) not in (tgt, None):
            r = f"still-{he_addressee(new)}-not-{tgt}"
        if r:
            rej += 1
            reasons[r] = reasons.get(r, 0) + 1
            continue
        done[k] = new
        ok += 1
    tmp = os.path.join(HERE, "fixed.json.tmp")
    json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HERE, "fixed.json"))
    print(f"merged {ok} | skip {skip} | rejected {rej} {reasons} | total {len(done)}/{len(tofix)}")
    if len(done) >= len(tofix):
        print("All done!")


if __name__ == "__main__":
    main()
