# -*- coding: utf-8 -*-
"""Deterministic PRE-TAGGER: enrich each review-corpus row with the taxonomy tags that the
multi-language panel can derive RELIABLY (closed-set morphology only). Everything error-prone
(referent gender X/Y/Z/G/M, IDIOM/CULT/TONE, tense nuance) is LEFT for the agent, with the panel
as evidence — we do NOT guess it (the same discipline that avoided the accusative-את / homograph
traps). Streams the jsonl; writes review_corpus/{kind}.tagged.jsonl.

Reliable derivations:
  axis        : P2 if an ADDRESSEE-marking lang splits (ar/pl/cs); P1 if only ru splits (speaker)
  player_gender: fV/mV are both live (the P2_F / P2_M pair) -> the engine picks by V's gender
  formality   : INF if an unambiguous informal 2nd-person pronoun appears (du/tu/tú/ты);
                FML if only a formal one (usted / capitalized Sie); null if only vous/вы (= ambiguous with plural)
  number      : P if an unambiguous 2nd-person PLURAL pronoun appears (vosotros/ustedes/ihr/euch)
  imperative  : IMP if the English begins with a bare verb (no subject) — a strong UI/command signal
  hom_candidate: languages diverge enough in length/content that a polysemy split (FENCE) is likely
"""
import json, os, re, sys

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "review_corpus")

# --- closed-set register pronouns (reliable) ---
DE_INF = re.compile(r'\b(du|dich|dir|deine?[mnrs]?)\b')            # German informal (lowercase)
DE_FML = re.compile(r'(?<![a-zäöü])(Sie|Ihnen|Ihre[mnrs]?)\b')     # German formal (capitalized mid-sentence)
FR_INF = re.compile(r'\b(tu|toi|ton|ta|tes)\b', re.I)
FR_FML = re.compile(r'\bvous\b', re.I)                              # also plural -> ambiguous
ES_INF = re.compile(r'\b(tú|te|ti|tuyo|contigo)\b', re.I)
ES_FML = re.compile(r'\busted\b', re.I)
RU_INF = re.compile(r'\bты\b', re.I)
RU_FML = re.compile(r'\bвы\b', re.I)                                # also plural -> ambiguous
# 2nd-person PLURAL (number)
PL2 = [re.compile(r'\b(vosotros|vosotras|ustedes|os)\b', re.I),    # es
       re.compile(r'\b(ihr|euch|eure[mnrs]?)\b')]                  # de (lowercase ihr)
# English bare-verb imperative: starts with a base verb, no leading subject/article
IMP_EN = re.compile(r'^(?:[A-Z][a-z]+)(?:\s|$)')
IMP_STOP = {"The","A","An","You","I","We","They","He","She","It","This","That","Your","My","Our"}

def formality(refs):
    inf = fml = 0
    for l, pats_i, pats_f in (("de", DE_INF, DE_FML), ("fr", FR_INF, FR_FML),
                              ("es-es", ES_INF, ES_FML), ("es-mx", ES_INF, ES_FML),
                              ("ru", RU_INF, RU_FML)):
        t = (refs.get(l) or ["", ""])[0]
        if not t: continue
        if pats_i.search(t): inf += 1
        elif pats_f.search(t): fml += 1
    if inf: return "INF"          # any unambiguous informal pronoun wins (du/tu/tú/ты)
    if fml: return "FML"          # only formal (usted / Sie)
    return None                    # only vous/вы seen, or none -> ambiguous

def number_plural(refs):
    for l in ("es-es", "es-mx", "de"):
        t = (refs.get(l) or ["", ""])[0]
        if any(p.search(t) for p in PL2): return "P"
    return None

def imperative(en):
    en = en.strip()
    if not en: return False
    first = en.split()[0].rstrip(".,:;!?")
    return bool(IMP_EN.match(en)) and first not in IMP_STOP and en[0].isupper()

def hom_candidate(refs, en):
    """Cheap polysemy proxy: among the Latin-script langs, are there >=2 clearly different
    single-word renderings for a short source? (FENCE: valla/clôture/zaun vs ricettatore)."""
    if len(en.split()) > 3: return False
    words = {}
    for l in ("es-es", "fr", "it", "de", "pt"):
        t = (refs.get(l) or ["", ""])[0].strip().lower().rstrip(".!?")
        if t and len(t.split()) <= 2:
            words[l] = t
    # normalize very loosely by first 4 chars; >=2 distinct stems on a <=3-word source = suspicious
    stems = {w[:4] for w in words.values() if len(w) >= 4}
    return len(stems) >= 3        # 3+ different Latin stems for a short line

def tag_row(r):
    refs = r.get("refs", {})
    split = r.get("split_langs", [])
    axis = []
    if any(l in split for l in ("ar", "pl", "cs")): axis.append("P2")     # addressee gendered
    if "ru" in split and not any(l in split for l in ("ar", "pl", "cs")): axis.append("P1?")  # speaker (ru past)
    tags = {
        "axis": axis,
        "player_gender": r.get("he_split", False) or bool(split),   # fV/mV pair is meaningful
        "formality": formality(refs),
        "number": number_plural(refs),
        "imperative": imperative(r.get("en", "")),
        "hom_candidate": hom_candidate(refs, r.get("en", "")),
    }
    return tags

def main():
    stats = {"P2": 0, "P1?": 0, "FML": 0, "INF": 0, "PL": 0, "IMP": 0, "HOM": 0, "n": 0}
    for kind in ("onscreens", "subtitles"):
        src = os.path.join(OUT, kind + ".jsonl")
        if not os.path.exists(src): continue
        dst = os.path.join(OUT, kind + ".tagged.jsonl")
        with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
            for line in fi:
                r = json.loads(line)
                t = tag_row(r)
                r["tags"] = t
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                stats["n"] += 1
                if "P2" in t["axis"]: stats["P2"] += 1
                if "P1?" in t["axis"]: stats["P1?"] += 1
                if t["formality"] == "FML": stats["FML"] += 1
                if t["formality"] == "INF": stats["INF"] += 1
                if t["number"] == "P": stats["PL"] += 1
                if t["imperative"]: stats["IMP"] += 1
                if t["hom_candidate"]: stats["HOM"] += 1
        print(f"  {kind}: tagged -> {dst}")
    print(f"\nreliable tags over {stats['n']:,} rows:")
    for k in ("P2", "P1?", "FML", "INF", "PL", "IMP", "HOM"):
        print(f"  {k:5s}: {stats[k]:>7,}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
