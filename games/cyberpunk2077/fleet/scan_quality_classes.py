# -*- coding: utf-8 -*-
"""Deterministic, read-only sweep of the CP2077 Hebrew spine for the concrete bug
classes the user photographed in-game. Sizes each class + writes a per-class candidate
JSONL under fleet/qc/. NEVER writes the spine. Run: python scan_quality_classes.py
"""
import json, os, re, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
BASE = os.path.join(RES, "localization_translated.json")
DLC = os.path.join(RES, "dlc_ep1_translated.json")
EXP = os.path.join(RES, "localization_export.json")          # English source (onscreens)
OUT = os.path.join(os.path.dirname(__file__), "qc")
os.makedirs(OUT, exist_ok=True)

HEB = re.compile(r'[֐-׿]')
LATWORD = re.compile(r'[A-Za-z]{2,}')
# CP2077 engine tokens that must survive verbatim
BRACE = re.compile(r'\{[^{}]*\}')          # {VALUE,...} / {PLAYER_SKILL,number,integer}
PRINTF = re.compile(r'%[#0-9.\-+ ]*[a-zA-Z]')
LOCKEY = re.compile(r'LocKey#\d+')
TAG = re.compile(r'<[^<>]+>')
CTRL = re.compile(r'^[\x00-\x08]+')        # leading CP2077 control byte(s)
# a "real English run" = 3+ consecutive Latin words separated by spaces/punct
ENRUN = re.compile(r'(?:[A-Za-z][A-Za-z\'\-]*[ ,.:;!?]+){2,}[A-Za-z][A-Za-z\'\-]*')

def strip_ctrl(s): return CTRL.sub('', s or '')
def tokens(s):
    s = s or ''
    return collections.Counter(BRACE.findall(s) + PRINTF.findall(s) + LOCKEY.findall(s))

def load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return {}

def eng_index(exp):
    idx = {}
    for sec, items in exp.items():
        for it in items:
            idx[(sec, str(it.get("primaryKey")))] = strip_ctrl(it.get("femaleVariant", "") or "")
    return idx

def is_namey(en):
    """English that legitimately stays Latin: short proper noun / all-caps / no lowercase common word."""
    en = en.strip()
    if not en: return True
    words = en.split()
    if len(words) <= 3 and en == en.title(): return True         # proper noun phrase
    if en.isupper(): return True                                  # acronym / styled header
    if not re.search(r'[a-z]{3,}', en): return True              # codes / numbers / symbols
    return False

def main():
    base, dlc, exp = load(BASE), load(DLC), load(EXP)
    eidx = eng_index(exp)
    classes = {k: [] for k in
               ("untranslated", "english_leak", "leading_latin_bidi",
                "placeholder_broken", "empty_mv", "length_anomaly")}
    tot = 0
    for spine, is_dlc in ((base, False), (dlc, True)):
        for sec, items in spine.items():
            kind = "onscreens" if "onscreens" in sec else ("subtitles" if "subtitles" in sec else "other")
            for it in items:
                pk = str(it.get("primaryKey"))
                fv = it.get("femaleVariant", "") or ""
                mv = it.get("maleVariant", "") or ""
                if not fv and not mv: continue
                tot += 1
                fvc = strip_ctrl(fv)
                # English source: onscreens -> export; subtitles -> secondaryKey
                en = (eidx.get((sec, pk)) or "") if kind == "onscreens" else strip_ctrl(it.get("secondaryKey", "") or "")
                rec = {"id": f"{'dlc' if is_dlc else 'base'}:{sec}:{pk}", "kind": kind,
                       "en": en[:160], "fv": fv[:160], "mv": mv[:160]}
                heb = bool(HEB.search(fvc))
                # 1) untranslated whole line: no Hebrew at all + has real English + EN not a name/code
                if not heb and LATWORD.search(fvc) and en and not is_namey(en):
                    classes["untranslated"].append(rec)
                # 2) english leak: has Hebrew AND a 3+ English-word run that isn't a brand
                elif heb:
                    for m in ENRUN.finditer(fvc):
                        run = m.group(0).strip()
                        if not is_namey(run) and len(run.split()) >= 3:
                            r2 = dict(rec); r2["leak"] = run[:80]; classes["english_leak"].append(r2); break
                # 3) leading-Latin bidi: fV (after ctrl+space) starts with a Latin letter or a { / [ token
                head = fvc.lstrip()
                if head and (head[0].isascii() and head[0].isalpha() or head[0] in "{["):
                    if HEB.search(fvc):   # mixed line starting LTR -> order corruption
                        classes["leading_latin_bidi"].append(rec)
                # 4) placeholder integrity: EN token multiset != fV token multiset
                if en:
                    te, tf = tokens(en), tokens(fv)
                    if te != tf:
                        r2 = dict(rec); r2["en_tok"] = dict(te); r2["fv_tok"] = dict(tf)
                        classes["placeholder_broken"].append(r2)
                # 5) empty mV while fV present (male-V fallback / literal template)
                if fv and not mv:
                    classes["empty_mv"].append(rec)
                # 6) length anomaly: Hebrew fV >> English (mistranslation / overflow), only real prose
                if heb and en and len(en) >= 4:
                    ratio = len(fvc) / max(1, len(en))
                    if ratio >= 2.4 and len(fvc) >= 12:
                        r2 = dict(rec); r2["ratio"] = round(ratio, 2); classes["length_anomaly"].append(r2)

    print(f"scanned {tot:,} entries\n")
    for k, rows in classes.items():
        oncnt = sum(1 for r in rows if r["kind"] == "onscreens")
        subcnt = sum(1 for r in rows if r["kind"] == "subtitles")
        print(f"  {k:20s} {len(rows):>7,}   (onscreens {oncnt:,} / subtitles {subcnt:,})")
        with open(os.path.join(OUT, k + ".jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\ncandidate files -> {OUT}")
    # a few samples per class
    for k in ("untranslated", "english_leak", "leading_latin_bidi", "length_anomaly"):
        print(f"\n=== {k} samples ===")
        for r in classes[k][:5]:
            print(f"  [{r['kind']}] EN={r['en'][:45]!r}")
            print(f"        fV={r['fv'][:60]}")

if __name__ == "__main__":
    main()
