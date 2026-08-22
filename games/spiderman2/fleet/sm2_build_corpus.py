# -*- coding: utf-8 -*-
"""עידן חדש — build the SM2 line-by-line QA corpus.

corpus.json = {id: {en, he, ar, ru, pl, es, it, ag, num, formal}}  — one row per translated
narrative line (subtitles + dialogue). `he` = the CURRENT Hebrew (logical, with <ts>/&rlm;);
en/ar/ru/pl/es/it = the game's own professional translations; ag/num/formal = the multi-language
gender consensus baked in (so the standalone NIM worker enforces it without re-deriving).

The gender parsers here are IDENTICAL to the ones embedded in sm2qa_nim.py (the worker runs
standalone on the VMs) — keep them in lockstep. See universal/NEW_ERA_LANGUAGE_ROLES.md.

Run:  python sm2_build_corpus.py       (writes fleet/corpus.json)
"""
import os, re, sys, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")
EXTRACT = os.path.join(HERE, "extract")
OUT = os.path.join(HERE, "corpus.json")

HEB = re.compile(r'[֐-׿]')

# ── multi-language addressee oracle (SAME code as sm2qa_nim.py) ───────────────
_AR_FATHA = "َ"; _AR_KASRA = "ِ"
_AR_YOU_F_PRON = re.compile("(?:أنت|إنت)" + _AR_KASRA)
_AR_YOU_M_PRON = re.compile("(?:أنت|إنت)" + _AR_FATHA)
_AR_YOU_PL = re.compile(r"أنتم|أنتن|إنتوا|أنتوا")
_AR_SUF_KF = re.compile("ك" + _AR_KASRA + r"(?![ء-يـ])")
_AR_SUF_KM = re.compile("ك" + _AR_FATHA + r"(?![ء-يـ])")
_AR_F_VERBS = ["تريدين", "تعرفين",
    "تعلمين", "تفعلين",
    "تقولين", "تفكرين",
    "تعتقدين", "تستطيعين",
    "تذهبين", "تأتين",
    "تسمعين", "تشعرين",
    "تحتاجين", "تجدين",
    "تكونين", "تحبين",
    "تظنين", "تحاولين",
    "ترين", "تدركين",
    "تتذكرين", "تنظرين",
    "تعملين", "تصدقين",
    "تملكين", "تعيشين",
    "تموتين", "تخبرين",
    "تسألين", "تفهمين",
    "تقصدين", "تحملين",
    "تقاتلين", "تتعلمين",
    "تخافين", "تستحقين",
    "تتوقعين", "تلعبين"]
# ⛔ NO colloquial "بت/هت…ي" rule. Measured on SM2's real Egyptian corpus it was 482/551 WRONG:
# a trailing ي is also the verb ROOT of weak-final verbs (هتيجي "will you come" — جي=come), a
# 1st-person OBJECT suffix (بترجعني "bring ME back"), and the possessive بتاعي/بتاعتي "mine".
# Egyptian 2nd-fem cannot be regexed without morphology → precision over recall (a wrong `ag`
# actively corrupts good Hebrew; a missing one merely leaves the line to the ru/pl/es/it consensus).
# (?<![ء-ي]) = the verb must START a word — without it `تحملين` matches INSIDE `متحملينه`
# (a 3rd-person plural participle), inventing a feminine addressee. Keep in lockstep with sm2qa_nim.py.
_AR_YOU_F_VERB = re.compile(r"(?<![ء-ي])(?:" + "|".join(sorted(_AR_F_VERBS, key=len, reverse=True)) +
                            r")(?:ه|ها|هم|هن|ك|كم|كن|ني|نا)?")


def ar_gender(text):
    if not text:
        return None
    if _AR_YOU_PL.search(text):
        return "pl"
    fem = bool(_AR_YOU_F_PRON.search(text) or _AR_SUF_KF.search(text) or _AR_YOU_F_VERB.search(text))
    masc = bool(_AR_YOU_M_PRON.search(text) or _AR_SUF_KM.search(text))
    return "f" if fem and not masc else "m" if masc and not fem else None


_RU_TOK = re.compile(r"[а-яё]+", re.I)
_RU_ADJ_F = {"готова", "уверена",
    "рада", "должна", "сама",
    "одна", "права", "жива", "мертва"}
_RU_ADJ_M = {"готов", "уверен", "рад",
    "должен", "сам", "один",
    "прав", "жив", "мёртв", "мертв"}


def _ru_axis(text):
    gs = set()
    for w in _RU_TOK.findall(text.lower()):
        if w in _RU_ADJ_F or (len(w) >= 4 and w.endswith("ла")):
            gs.add("f")
        elif w in _RU_ADJ_M or (len(w) >= 3 and w.endswith("л") and not w.endswith("ль")):
            gs.add("m")
    return "f" if gs == {"f"} else "m" if gs == {"m"} else None


def ru_addr(text):
    if not text:
        return None
    t = _RU_TOK.findall(text.lower())
    if "вы" in t:
        return "pl"
    if "ты" in t and "я" not in t:
        return _ru_axis(text)
    return None


_PL_TOK = re.compile(r"[a-ząćęłńóśźż]+", re.I)
_PL_ADJ_F = {"gotowa", "pewna", "sama", "zmęczona", "pijana", "martwa", "bezpieczna", "wolna", "chora", "silna"}
_PL_ADJ_M = {"gotowy", "pewien", "pewny", "sam", "zmęczony", "pijany", "martwy", "bezpieczny", "wolny", "chory", "silny"}


def pl_addr(text):
    if not text:
        return None
    t = _PL_TOK.findall(text.lower()); ts = set(t)
    if "wy" in ts or "jesteście" in ts or any(w.endswith("liście") or w.endswith("łyście") for w in t):
        return "pl"
    f = any(w.endswith("łaś") and len(w) >= 5 for w in t) or bool(ts & _PL_ADJ_F)
    m = any(w.endswith("łeś") and len(w) >= 5 for w in t) or bool(ts & _PL_ADJ_M)
    return "f" if f and not m else "m" if m and not f else None


_ES_2P = re.compile(r"\b(?:estás|estabas|eres|serás|fuiste|quedaste|estuviste|pareces|sigues)\s+"
                    r"(?:muy\s+|tan\s+|un\s+poco\s+|bastante\s+)?[a-záéíóúñ]{3,}?([oa])s?\b", re.I)
_ES_WEL = re.compile(r"\bbienvenid([oa])s?\b", re.I)
_ES_PL = re.compile(r"\b(?:vosotros|vosotras|estáis|sois|habéis|tenéis|podéis|queréis|sabéis|vuestr[oa]s?)\b", re.I)


def es_addr(text):
    if not text:
        return None
    if _ES_PL.search(text):
        return "pl"
    m = _ES_2P.search(text) or _ES_WEL.search(text)
    return ("f" if m.group(1).lower() == "a" else "m") if m else None


_IT_2P = re.compile(r"\b(?:sei|eri|sarai|fosti)\s+(?:molto\s+|tanto\s+|piuttosto\s+)?[a-zàèéìòù]{3,}?([oa])\b", re.I)
_IT_WEL = re.compile(r"\bbenvenut([oa])\b", re.I)
_IT_PL = re.compile(r"\b(?:voi|siete|sarete|foste|avete|potete|volete|dovete|sapete|vostr[oaie])\b", re.I)


def it_addr(text):
    if not text:
        return None
    if _IT_PL.search(text):
        return "pl"
    m = _IT_2P.search(text) or _IT_WEL.search(text)
    return ("f" if m.group(1).lower() == "a" else "m") if m else None


def gender_facts(v):
    """(ag, num, formal). Arabic decides addressee alone; else >=2 non-Arabic agree.
    formal=True when a non-Arabic marks plural but Arabic does NOT (polite-singular trap)."""
    a = ar_gender(v.get("ar", ""))
    non_ar = [f(v.get(l, "")) for l, f in (("ru", ru_addr), ("pl", pl_addr), ("es", es_addr), ("it", it_addr))]
    formal = (a != "pl") and ("pl" in non_ar)
    if a in ("m", "f", "pl"):
        ag = a
    else:
        votes = {}
        for g in non_ar:
            if g in ("m", "f"):
                votes[g] = votes.get(g, 0) + 1
        ag = None
        if votes:
            best = max(votes, key=lambda k: votes[k])
            if votes[best] >= 2 and not (len(votes) > 1 and sorted(votes.values())[-2:] == [votes[best], votes[best]]):
                ag = best
    num = "pl" if ag == "pl" else None
    return ag, num, formal


def main():
    he = {}
    for fn in ("subtitles_he.json", "dialogue_he.json"):
        he.update(json.load(open(os.path.join(WORK, fn), encoding="utf-8")))
    langs = {l: json.load(open(os.path.join(EXTRACT, f"{l}.json"), encoding="utf-8"))
             for l in ("en", "ar", "ru", "pl", "es", "it")}

    corpus = {}
    skipped = 0
    for k, h in he.items():
        if not isinstance(h, str) or not HEB.search(h):
            skipped += 1
            continue
        en = langs["en"].get(k, "")
        row = {"en": en, "he": h}
        for l in ("ar", "ru", "pl", "es", "it"):
            t = langs[l].get(k, "")
            if t and t.strip():
                row[l] = t
        ag, num, formal = gender_facts(row)
        if ag:
            row["ag"] = ag
        if num:
            row["num"] = num
        if formal:
            row["formal"] = True
        corpus[k] = row

    json.dump(corpus, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    ag_n = sum(1 for v in corpus.values() if v.get("ag"))
    num_n = sum(1 for v in corpus.values() if v.get("num"))
    formal_n = sum(1 for v in corpus.values() if v.get("formal"))
    print(f"corpus.json: {len(corpus)} lines (skipped {skipped} non-Hebrew)")
    print(f"  gender baked: ag={ag_n}  num(plural)={num_n}  formal-trap={formal_n}")


if __name__ == "__main__":
    main()
