# -*- coding: utf-8 -*-
"""Refined, read-only TRUE-bug sizing after removing the known false positives
(literal %, brand names, labels, empty-mV=normal). Deterministic. Writes qc2/*.jsonl.
"""
import json, os, re, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
EXP = os.path.join(RES, "localization_export.json")
OUT = os.path.join(os.path.dirname(__file__), "qc2"); os.makedirs(OUT, exist_ok=True)

HEB = re.compile(r'[֐-׿]')
BRACE = re.compile(r'\{[^{}]*\}')                # ONLY real engine value tokens
LOCKEY = re.compile(r'LocKey#\d+')
CTRL = re.compile(r'^[\x00-\x08]+')
# romanized-Hebrew: a Latin run using letter combos that are transliteration, not English/brand.
# heuristic: 2+ Latin words where a word ends in -iim/-ot/-ut/-ei or has qq/kh/tz/'  (translit markers)
TRANSLIT = re.compile(r'\b[a-z]+(?:iim| iim|ot|ut|ei|im)\b', re.I)
ENRUN = re.compile(r'(?:[A-Za-z][A-Za-z\'\-]*[ ,.:;!?]+){2,}[A-Za-z][A-Za-z\'\-]*')

def sc(s): return CTRL.sub('', s or '')
def braces(s): return collections.Counter(BRACE.findall(s or '') + LOCKEY.findall(s or ''))

def is_brand(en):
    en = (en or '').strip()
    if not en: return True
    if re.search(r'\d', en) and len(en.split()) <= 4: return True     # model/radio: "92.9 FM","M221"
    if en.isupper(): return True
    words = en.split()
    if len(words) <= 3 and en == en.title(): return True
    if not re.search(r'\b(the|a|to|with|of|and|is|are|you|your|this|for|on|in|will|can)\b', en.lower()) \
       and len(words) <= 4: return True                                # no function word + short = name
    return False

def main():
    exp = json.load(open(EXP, encoding="utf-8"))
    base = json.load(open(os.path.join(RES,"localization_translated.json"), encoding="utf-8"))
    try: dlc = json.load(open(os.path.join(RES,"dlc_ep1_translated.json"), encoding="utf-8"))
    except: dlc = {}
    eidx = {}
    for sec, items in exp.items():
        for it in items: eidx[(sec, str(it.get("primaryKey")))] = sc(it.get("femaleVariant","") or "")

    C = collections.Counter(); S = collections.defaultdict(list)
    for spine, dlcflag in ((base,False),(dlc,True)):
        for sec, items in spine.items():
            kind = "onscreens" if "onscreens" in sec else ("subtitles" if "subtitles" in sec else "other")
            for it in items:
                pk = str(it.get("primaryKey")); fv = it.get("femaleVariant","") or ""
                if not fv: continue
                fvc = sc(fv)
                en = (eidx.get((sec,pk)) or "") if kind=="onscreens" else sc(it.get("secondaryKey","") or "")
                heb = bool(HEB.search(fvc))
                rec = {"id":f"{'dlc' if dlcflag else 'base'}:{sec}:{pk}","kind":kind,"en":en[:120],"fv":fv[:120]}
                # A) real brace/LocKey token DROPPED (not %)
                if en:
                    lost = braces(en) - braces(fv)
                    if lost:
                        C["brace_dropped"]+=1; (S["brace_dropped"].append({**rec,"lost":dict(lost)}) if len(S["brace_dropped"])<40 else None)
                # B) untranslated PROSE (no Hebrew, real English sentence, not a brand)
                if not heb and en and not is_brand(en) and re.search(r'[a-z]{3,}.*\s.*[a-z]{3,}', en):
                    C["untranslated_prose"]+=1; (S["untranslated_prose"].append(rec) if len(S["untranslated_prose"])<40 else None)
                # C) romanized-Hebrew leak (Latin transliteration inside a Hebrew line)
                if heb:
                    for m in ENRUN.finditer(fvc):
                        run=m.group(0).strip()
                        if TRANSLIT.search(run) and not is_brand(run):
                            C["romanized_hebrew"]+=1; (S["romanized_hebrew"].append({**rec,"run":run[:60]}) if len(S["romanized_hebrew"])<40 else None); break
                # D) real bidi sentence: mixed line, starts LTR, Hebrew part is a PHRASE (>=4 heb words)
                head=fvc.lstrip()
                if head and heb and (head[0].isascii() and head[0].isalpha()):
                    hebwords=len(HEB.findall(fvc)) and len([w for w in fvc.split() if HEB.search(w)])
                    if hebwords>=4:
                        C["bidi_sentence"]+=1; (S["bidi_sentence"].append(rec) if len(S["bidi_sentence"])<40 else None)
    for k in ("brace_dropped","untranslated_prose","romanized_hebrew","bidi_sentence"):
        print(f"  {k:20s} {C[k]:>6,}")
        json.dump(S[k], open(os.path.join(OUT,k+".json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print()
    for k in ("brace_dropped","untranslated_prose","romanized_hebrew","bidi_sentence"):
        print(f"=== {k} samples ===")
        for r in S[k][:5]:
            extra = r.get("lost") or r.get("run") or ""
            print(f"  {str(extra)[:40]:40s} EN={r['en'][:45]!r} fV={r['fv'][:50]}")
        print()

if __name__ == "__main__": main()
