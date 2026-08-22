# -*- coding: utf-8 -*-
"""Build the CP2077 line-by-line QA corpus for the 5-stream NIM fleet.

Joins, per (section, primaryKey):
  EN  = localization_export.json     (English source, femaleVariant)
  HE  = localization_translated.json (our Hebrew, femaleVariant — what we review)
  AR  = gender_oracle_suspects.jsonl (the game's Arabic, WHERE we already have it — the gender guard)

Output: fleet/qa_corpus.json = { "<src>:<section>:<pk>": {en, he, sec, src, ar?, ag?} }
  src = base|dlc ; ag = ar_gender (m/f) where the Arabic oracle already decided.

Only REVIEWABLE prose is kept: has real Hebrew, EN has >=3 letters, not a bare code/name/dev-junk
(the §7 name/code passthrough rule — else the fleet churns on proper nouns). Structural tokens are
preserved downstream by the worker, not stripped here.
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(CP, "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")

BASE_HE = os.path.join(RES, "localization_translated.json")
BASE_EN = os.path.join(RES, "localization_export.json")
DLC_HE = os.path.join(RES, "dlc_ep1_translated.json")
DLC_EN = os.path.join(RES, "dlc_ep1_text.json")
SUSPECTS = os.path.join(CP, "gender_oracle_suspects.jsonl")
OUT = os.path.join(HERE, "qa_corpus.json")

HE_RE = re.compile(r"[א-ת]")
LAT_WORD = re.compile(r"[A-Za-z]{3,}")
# strings that are pure code / dev-junk / bracketed markers -> skip (never review)
JUNK = re.compile(r"^\s*(\[[^\]]*\]|\{[^}]*\}|[<>\d\s.,:%_\-/]+|[A-Z0-9_.\-]+)\s*$")


def is_reviewable(en, he):
    if not he or not HE_RE.search(he):
        return False
    if not en or not LAT_WORD.search(en):   # EN must carry a real word
        return False
    if JUNK.match(he):
        return False
    return True


def load_ar_gender():
    """pk-level Arabic gender decisions already computed (addressee axis)."""
    m = {}
    if not os.path.exists(SUSPECTS):
        return m
    for ln in open(SUSPECTS, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
            key = f"{r.get('src','base')}:{r.get('section')}:{r.get('pk')}"
            m[key] = {"ar": r.get("ar_female") or r.get("ar_male") or "", "ag": r.get("ar_gender")}
        except Exception:
            continue
    return m


def build(he_path, en_path, src, arg, corpus):
    he = json.load(open(he_path, encoding="utf-8"))
    en = json.load(open(en_path, encoding="utf-8"))
    kept = 0
    for sec, rows in he.items():
        if not isinstance(rows, list):
            continue
        enrows = {str(r.get("primaryKey")): r for r in en.get(sec, []) if isinstance(r, dict)}
        for r in rows:
            pk = str(r.get("primaryKey"))
            hv = r.get("femaleVariant") or ""
            ev = (enrows.get(pk) or {}).get("femaleVariant") or r.get("secondaryKey") or ""
            if not is_reviewable(ev, hv):
                continue
            key = f"{src}:{sec}:{pk}"
            item = {"en": ev, "he": hv, "sec": sec, "src": src}
            g = arg.get(key)
            if g:
                item["ar"], item["ag"] = g["ar"], g["ag"]
            corpus[key] = item
            kept += 1
    return kept


def main():
    arg = load_ar_gender()
    print(f"arabic gender decisions loaded: {len(arg)}")
    corpus = {}
    b = build(BASE_HE, BASE_EN, "base", arg, corpus)
    print(f"base reviewable: {b}")
    d = 0
    if os.path.exists(DLC_HE) and os.path.exists(DLC_EN):
        d = build(DLC_HE, DLC_EN, "dlc", arg, corpus)
        print(f"dlc reviewable:  {d}")
    with_ar = sum(1 for v in corpus.values() if "ar" in v)
    json.dump(corpus, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"TOTAL corpus: {len(corpus)} (base {b} + dlc {d}), with-Arabic-guard {with_ar}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
