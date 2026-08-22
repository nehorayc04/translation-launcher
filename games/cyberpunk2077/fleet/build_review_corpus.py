# -*- coding: utf-8 -*-
"""Build the FLEET-READY multi-language review corpus (everything up to the translation step).
For every Hebrew line it emits one review row the fleet agent consumes to judge MEANING + GENDER
+ other errors — with NO further lookups needed:

  { id, kind, section, order,
    en,                       # English source
    refs: {lang:[fv,mv]},     # all shipped game languages (fv+mv -> shows gender splits)
    he:  [fv,mv],             # current Hebrew
    gendered, split_langs,    # DETERMINISTIC gender partition (union of langs that split fv!=mv)
    he_split,                 # does Hebrew itself distinguish gender
    det: {...} }              # deterministic pre-flags (token/niqqud/foreign/bidi/leak)

Reads the serialized language dirs directly (fv+mv). Onscreens panel is complete; subtitles are
folded in as their extraction finishes (re-runnable). Ordered by visibility (UI first).
Writes review_corpus/{onscreens,subtitles}.jsonl + a coverage report. Read-only vs the spine.
"""
import json, os, re, collections
from pathlib import Path

HERE = os.path.dirname(__file__)
RES = os.path.join(HERE, "..", "..", "..", "תרגום_משחקים", "source", "resources")
ON_WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_langpanel")
SUB_WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_subpanel")
OUT = os.path.join(HERE, "review_corpus"); os.makedirs(OUT, exist_ok=True)
LANGS = ["en","ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de","ja","ko",
         "zh-cn","zh-tw","tr","th","hu","ua"]
GENDER_LANGS = ["ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de"]

HEB = re.compile(r'[֐-׿]')
NIQ = re.compile(r'[ֽ-ׇ]')
FOREIGN = re.compile(r'[\u0600-\u06ff\u0400-\u04ff\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]')
BRACE = re.compile(r'\{[^{}]*\}')
LOCKEY = re.compile(r'LocKey#\d+')
CTRL = re.compile(r'^[\x00-\x08]+')
ENRUN = re.compile(r'(?:[A-Za-z][A-Za-z\'\-]*[ ,.:;!?]+){2,}[A-Za-z][A-Za-z\'\-]*')

def sc(s): return CTRL.sub('', s or '')
def braces(s): return collections.Counter(BRACE.findall(s or '') + LOCKEY.findall(s or ''))

def entries_of(tj):
    try:
        w = json.load(open(tj, encoding="utf-8"))
        return w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return []

def panel_from(work, names):
    """pk -> {lang:(fv,mv)} from serialized dirs. names = allowed CR2W basenames (onscreens) or None (subtitles: all)."""
    panel = {}
    for scope in ("base", "ep1"):
        for lang in LANGS:
            ex = work / scope / lang
            if not ex.exists(): continue
            files = [p for p in ex.rglob("*.json.json")
                     if names is None or p.name in names]
            for tj in files:
                for e in entries_of(str(tj)):
                    pk = e.get("primaryKey") or e.get("stringId")
                    if pk is None: continue
                    fv = (e.get("femaleVariant") or "").strip()
                    mv = (e.get("maleVariant") or "").strip()
                    if fv or mv:
                        panel.setdefault(str(pk), {}).setdefault(lang, (fv, mv))
    return panel

def he_spine(kind):
    base = json.load(open(os.path.join(RES, "localization_translated.json"), encoding="utf-8"))
    dlc = {}
    try: dlc = json.load(open(os.path.join(RES, "dlc_ep1_translated.json"), encoding="utf-8"))
    except FileNotFoundError: pass
    rows = {}
    order = 0
    for spine in (base, dlc):
        for sec, items in spine.items():
            if kind not in sec: continue
            for it in items:
                pk = str(it.get("primaryKey") or it.get("stringId"))
                fv = it.get("femaleVariant", "") or ""; mv = it.get("maleVariant", "") or ""
                if not fv and not mv: continue
                rows.setdefault(pk, (sec, order, fv, mv)); order += 1
    return rows

def splits(pair): fv, mv = pair; return bool(fv) and bool(mv) and fv != mv

def det_flags(en, fv):
    fvc = sc(fv); flags = {}
    if NIQ.search(fvc): flags["niqqud"] = True
    if FOREIGN.search(fvc): flags["foreign"] = True
    lost = braces(en) - braces(fv)
    if lost: flags["brace_dropped"] = list(lost)
    head = fvc.lstrip()
    if head and head[0].isascii() and head[0].isalpha() and HEB.search(fvc):
        flags["leading_latin"] = True
    if HEB.search(fvc):
        for m in ENRUN.finditer(fvc):
            r = m.group(0).strip()
            if len(r.split()) >= 3:
                flags["english_run"] = r[:60]; break
    return flags

def build(kind, panel):
    rows = he_spine(kind)
    out_path = os.path.join(OUT, kind + ".jsonl")
    n = gendered = covered = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for pk, (sec, order, fv, mv) in sorted(rows.items(), key=lambda kv: kv[1][1]):
            p = panel.get(pk, {})
            en = sc(p.get("en", ("",""))[0]) if "en" in p else ""
            split_langs = [l for l in GENDER_LANGS if l in p and splits(p[l])]
            row = {
                "id": f"{sec}:{pk}", "kind": kind, "section": sec, "order": order,
                "en": en,
                "refs": {l: [sc(p[l][0]), sc(p[l][1])] for l in LANGS if l in p and l != "en"},
                "he": [fv, mv],
                "gendered": bool(split_langs),
                "split_langs": split_langs,
                "he_split": splits((fv, mv)),
                "det": det_flags(en, fv),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            if split_langs: gendered += 1
            if len(row["refs"]) >= 6: covered += 1
    return n, gendered, covered, out_path

def main():
    print("building onscreens review corpus (panel complete)...")
    on = panel_from(ON_WORK, {"onscreens.json.json", "onscreens_final.json.json"})
    n, g, c, path = build("onscreens", on)
    print(f"  onscreens: {n:,} rows | gendered {g:,} | >=6 langs {c:,} ({100*c/max(1,n):.1f}%) -> {path}")

    # subtitles: only if any subtitle serialization exists yet
    have_sub = any((SUB_WORK/sc/l).exists() and any((SUB_WORK/sc/l).rglob("*.json.json"))
                   for sc in ("base","ep1") for l in LANGS)
    if have_sub:
        print("building subtitles review corpus (partial panel = as far as extraction reached)...")
        sub = panel_from(SUB_WORK, None)
        n, g, c, path = build("subtitles", sub)
        langs_present = sorted({l for v in sub.values() for l in v})
        print(f"  subtitles: {n:,} rows | gendered {g:,} | >=6 langs {c:,} | langs so far: {langs_present}")
    else:
        print("subtitles: panel not ready yet (extraction running) — re-run when it finishes.")

if __name__ == "__main__":
    main()
