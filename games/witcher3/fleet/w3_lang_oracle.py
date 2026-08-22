# -*- coding: utf-8 -*-
"""Multi-language ADDRESSEE gender/number oracle for The Witcher 3.

W3 ships the same str_id in 17 languages. Several mark the *addressee* ("you") gender/number
morphologically. Arabic alone (the prior scan) gave false positives because it could not tell a
1st-person SPEAKER verb from a 2nd-person ADDRESSEE verb. Cross-referencing several independent
gendered languages and taking a CONSENSUS both (a) separates speaker from addressee and (b) raises
precision: a Hebrew line is only a real gender/number bug when >=2 languages AGREE on an addressee
value that disagrees with the Hebrew.

Strong addressee-gender markers used here (each conservative, 2nd-person only):
  * Arabic  — أنتَ/أنتِ/أنتم + 2nd-person verb morphology            (GO.ar_addressee)
  * Russian — ты + past-tense -л/-ла (subject == addressee, no я)     (GO.ru_addressee)
  * Polish  — 2nd-sg past -łeś/-łaś, jesteś + adj, wy/-cie plural     (pl_addressee)
  * Spanish — estás/eres + adj-o/a, vosotros/2pl verbs               (es_addressee)
  * Italian — sei/eri + adj-o/a, voi/2pl verbs                        (it_addressee)
Returns one of 'm' | 'f' | 'pl' | None.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "universal")))
import gender_oracle as GO  # noqa: E402

ar_addressee = GO.ar_addressee
ru_addressee = GO.ru_addressee
he_addressee = GO.he_addressee


# ── Polish ───────────────────────────────────────────────────────────────────
# 2nd-sg past: verb-stem + łeś (masc) / łaś (fem).  plural: wy, jesteście, past -liście/-łyście,
# present 2pl -cie.  adjectives gotowy/gotowa, pewien/pewna, sam/sama after jesteś.
_PL_TOK = re.compile(r"[a-ząćęłńóśźż]+", re.I)
_PL_ADJ_F = {"gotowa", "pewna", "sama", "zmęczona", "pijana", "szalona", "głupia", "martwa",
             "bezpieczna", "wolna", "cicha", "ślepa", "chora", "silna"}
_PL_ADJ_M = {"gotowy", "pewien", "pewny", "sam", "zmęczony", "pijany", "szalony", "głupi", "martwy",
             "bezpieczny", "wolny", "cichy", "ślepy", "chory", "silny"}


def pl_addressee(text):
    if not text:
        return None
    toks = _PL_TOK.findall(text.lower())
    ts = set(toks)
    # plural addressee
    if "wy" in ts or "jesteście" in ts or "wasze" in ts or "wasz" in ts:
        return "pl"
    if any(t.endswith("liście") or t.endswith("łyście") for t in toks):
        return "pl"
    f = m = False
    for t in toks:
        if len(t) >= 5 and t.endswith("łaś"):
            f = True
        elif len(t) >= 5 and t.endswith("łeś"):
            m = True
        elif t in _PL_ADJ_F:
            f = True
        elif t in _PL_ADJ_M:
            m = True
    if f and not m:
        return "f"
    if m and not f:
        return "m"
    return None


# ── Spanish (es / esmx) ──────────────────────────────────────────────────────
# 2nd-person copula/verb + predicate adj -o/-a  → addressee gender.  vosotros / -áis-éis-ís → plural.
_ES_2P_G = re.compile(
    r"\b(?:estás|estabas|eres|serás|fuiste|quedaste|estuviste|te\s+ves|te\s+sientes|"
    r"pareces|sigues)\s+(?:muy\s+|tan\s+|un\s+poco\s+|bastante\s+|el\s+|la\s+)?"
    r"[a-záéíóúñ]{3,}?([oa])s?\b", re.I)
_ES_WELCOME = re.compile(r"\bbienvenid([oa])s?\b", re.I)
_ES_PL = re.compile(r"\b(?:vosotros|vosotras|ustedes|estáis|sois|seréis|fuisteis|habéis|"
                    r"tenéis|podéis|queréis|debéis|sabéis|estabais|vuestr[oa]s?)\b", re.I)


def es_addressee(text):
    if not text:
        return None
    if _ES_PL.search(text):
        return "pl"
    m = _ES_2P_G.search(text) or _ES_WELCOME.search(text)
    if m:
        return "f" if m.group(1).lower() == "a" else "m"
    return None


# ── Italian ──────────────────────────────────────────────────────────────────
_IT_2P_G = re.compile(
    r"\b(?:sei|eri|sarai|fosti)\s+(?:molto\s+|tanto\s+|un\s+po'\s+|piuttosto\s+)?"
    r"[a-zàèéìòù]{3,}?([oa])\b", re.I)
_IT_WELCOME = re.compile(r"\bbenvenut([oa])\b", re.I)
_IT_PL = re.compile(r"\b(?:voi|siete|sarete|foste|avete|potete|volete|dovete|sapete|vostr[oaie])\b", re.I)


def it_addressee(text):
    if not text:
        return None
    if _IT_PL.search(text):
        return "pl"
    m = _IT_2P_G.search(text) or _IT_WELCOME.search(text)
    if m:
        return "f" if m.group(1).lower() == "a" else "m"
    return None


# ── consensus ────────────────────────────────────────────────────────────────
PARSERS = {"ar": ar_addressee, "ru": ru_addressee, "pl": pl_addressee,
           "es": es_addressee, "it": it_addressee}


def votes(langs):
    """langs = {'ar':txt,'ru':txt,...} -> {lang: 'm'|'f'|'pl'} for those that determined one."""
    out = {}
    for l, fn in PARSERS.items():
        g = fn(langs.get(l, "")) if langs.get(l) else None
        if g:
            out[l] = g
    return out


def consensus(langs):
    """-> (value, n_agree, votes). value = the addressee gender/number agreed by the plurality,
    n_agree = how many languages voted for it (confidence). None if no votes."""
    v = votes(langs)
    if not v:
        return None, 0, v
    tally = {}
    for g in v.values():
        tally[g] = tally.get(g, 0) + 1
    best = max(tally, key=lambda k: (tally[k], k))
    return best, tally[best], v


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tests = [
        ("pl", "Jesteś pewna? Zrobiłaś to sama.", "f"),
        ("pl", "Byłeś tam wczoraj, prawda?", "m"),
        ("pl", "Wy nic nie wiecie o ich zwyczajach.", "pl"),
        ("es", "¿Estás segura de que no somos nosotros?", "f"),
        ("es", "Estás cansado, ve a casa.", "m"),
        ("es", "Vosotros no sabéis nada.", "pl"),
        ("it", "Sei sicura? L'hai fatto da sola.", "f"),
        ("it", "Voi non sapete niente.", "pl"),
    ]
    ok = 0
    for lang, txt, exp in tests:
        got = PARSERS[lang](txt)
        hit = got == exp
        ok += hit
        print(f"  [{'OK ' if hit else 'MISS'}] {lang}_addressee={got} exp={exp}  {txt[:38]}")
    print(f"{ok}/{len(tests)} selftests")
