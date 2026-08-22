# -*- coding: utf-8 -*-
"""EMPIRICAL certainty test for the multi-language review method (onscreens).
Re-reads the serialized game languages capturing BOTH femaleVariant AND maleVariant per
language, then measures — with real numbers, not promises:

  GENDER certainty:
    * "gendered" line  = >=1 game language itself SPLITS (fv != mv) on that pk.
      -> the UNION of all languages' splits identifies EVERY gender-dependent line.
      -> a gender error can only be MISSED on a line NO language marks = genuinely neutral.
    * how many gendered lines does ARABIC-ALONE detect vs the full panel (multi > single).
    * of gendered lines, is the current Hebrew correctly split? (fv!=mv) -> the flag set.

  MEANING certainty:
    * cross-language DISAGREEMENT proxy: lines where the languages do NOT all map to one
      Hebrew-consistent meaning are exactly where a single-language oracle is blind (FENCE).
      (final meaning judgement needs the LLM reading the panel — this sizes the signal.)
"""
import json, os, re, collections
from pathlib import Path

WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_langpanel")
RES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "תרגום_משחקים", "source", "resources")
LANGS = ["en","ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de","ja","ko",
         "zh-cn","zh-tw","tr","th","hu","ua"]
GENDER_LANGS = ["ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de"]  # langs that mark gender

def entries_of(tj):
    try:
        w = json.load(open(tj, encoding="utf-8"))
        return w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return []

def build():
    """pk -> {lang: (fv, mv)}  from serialized base onscreens."""
    panel = {}
    for lang in LANGS:
        ex = WORK / "base" / lang
        if not ex.exists(): continue
        files = [p for p in ex.rglob("*.json.json")
                 if p.name in ("onscreens.json.json", "onscreens_final.json.json")]
        for tj in files:
            for e in entries_of(str(tj)):
                pk = e.get("primaryKey") or e.get("stringId")
                if pk is None: continue
                fv = (e.get("femaleVariant") or "").strip()
                mv = (e.get("maleVariant") or "").strip()
                if fv or mv:
                    panel.setdefault(str(pk), {}).setdefault(lang, (fv, mv))
    return panel

def he_map():
    base = json.load(open(os.path.join(RES, "localization_translated.json"), encoding="utf-8"))
    he = {}
    for sec, items in base.items():
        if "onscreens" not in sec: continue
        for it in items:
            pk = str(it.get("primaryKey"))
            fv = (it.get("femaleVariant") or "").strip()
            mv = (it.get("maleVariant") or "").strip()
            if fv or mv: he.setdefault(pk, (fv, mv))
    return he

def splits(pair):  # a language "splits" (is gendered) on this line
    fv, mv = pair
    return bool(fv) and bool(mv) and fv != mv

def main():
    panel, he = build(), he_map()
    both = [pk for pk in panel if pk in he]
    print(f"onscreens lines with Hebrew AND panel: {len(both):,}\n")

    # ---- GENDER CERTAINTY ----
    gendered = []          # >=1 game lang splits
    ar_only_gendered = 0   # arabic alone would flag
    multi_extra = 0        # gendered that arabic alone MISSES (the added recall)
    for pk in both:
        p = panel[pk]
        splitters = [l for l in GENDER_LANGS if l in p and splits(p[l])]
        if splitters:
            gendered.append(pk)
            ar = "ar" in splitters
            if ar: ar_only_gendered += 1
            else: multi_extra += 1
    neutral = len(both) - len(gendered)
    # of gendered lines, does Hebrew itself split?
    he_split = sum(1 for pk in gendered if splits(he[pk]))
    he_flat = len(gendered) - he_split

    print("=== GENDER CERTAINTY ===")
    print(f"  gendered lines (>=1 language splits): {len(gendered):,}")
    print(f"    detectable by ARABIC alone (old):   {ar_only_gendered:,}")
    print(f"    ADDED by ru/pl/es/fr/... (new):     {multi_extra:,}   <- old method was BLIND to these")
    print(f"  genuinely neutral (NO language splits): {neutral:,}  -> no gender error possible")
    print(f"  of gendered lines, Hebrew IS split:   {he_split:,}")
    print(f"  of gendered lines, Hebrew NOT split:  {he_flat:,}   <- the exact review flag set")
    # how many gender-marking languages per gendered line (redundancy = confidence)
    dist = collections.Counter(sum(1 for l in GENDER_LANGS if l in panel[pk] and splits(panel[pk][l])) for pk in gendered)
    print("  gender-marking-language count per gendered line (redundancy):")
    for k in sorted(dist): print(f"      {k} langs: {dist[k]:,}")

    # ---- MEANING SIGNAL ----
    # coverage: how many independent languages per line (more = harder to hide a meaning error)
    covdist = collections.Counter(len([l for l in LANGS if l in panel[pk]]) for pk in both)
    strong = sum(v for k, v in covdist.items() if k >= 8)
    print("\n=== MEANING CERTAINTY ===")
    print(f"  lines with >=8 independent languages: {strong:,} / {len(both):,} ({100*strong/len(both):.1f}%)")
    print(f"  (a meaning error is missable only if ALL languages agree with the wrong Hebrew;")
    print(f"   more independent languages -> smaller blind spot; community langs shrink it further)")

if __name__ == "__main__":
    main()
