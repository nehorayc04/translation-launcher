# -*- coding: utf-8 -*-
"""Build per-language {pk_or_stringId: text} gender-oracle maps from the WolvenKit-serialized
game localizations (C:\\tmp\\cpqa_lang\\<lang>\\*.json — the GAME's real ar/ru/es/fr/it, NOT our
Hebrew). Keyed by primaryKey (onscreens) / stringId (subtitles) — disjoint value spaces, so a
global {pk: text} join to the corpus (whose key ends in :<pk>) is safe. Prefers a non-empty
femaleVariant, falls back to maleVariant. Writes fleet/lang_maps/<lang>.json.

Collision note: WolvenKit flattens the tree, so two source files with the same basename would
clash. We MERGE all entries across all json anyway (keyed by pk), and a same-basename file would
only cost us that file's pks; coverage is reported so we can catch it. Run after extract_langs.sh.
"""
import json, os, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LANGROOT = r"C:\tmp\cpqa_lang"
OUTDIR = os.path.join(HERE, "lang_maps")
os.makedirs(OUTDIR, exist_ok=True)
LANGS = ["ar", "ru", "pl", "es", "it", "fr"]


def parse_file(path, m):
    try:
        d = json.load(open(path, encoding="utf-8"))
        entries = d["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return 0
    n = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        pk = e.get("primaryKey")
        if pk is None:
            pk = e.get("stringId")
        if pk is None:
            continue
        pk = str(pk)
        fv = e.get("femaleVariant") or ""
        mv = e.get("maleVariant") or ""
        txt = fv if fv.strip() else mv
        if not txt.strip():
            continue
        # keep the female form as primary (for addressee/referent gender); stash male too
        m[pk] = {"f": fv, "m": mv} if (fv and mv and fv != mv) else txt
        n += 1
    return n


def build(lang):
    dirs = [os.path.join(LANGROOT, lang), os.path.join(LANGROOT, lang + "_ep1")]
    files = []
    for d in dirs:
        if os.path.isdir(d):
            files += glob.glob(os.path.join(d, "*.json"))
    if not files:
        print(f"  {lang}: no files ({dirs})")
        return
    m = {}
    for f in files:
        parse_file(f, m)
    out = os.path.join(OUTDIR, f"{lang}.json")
    json.dump(m, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  {lang}: {len(files)} files -> {len(m):,} keys -> {out}")


def main():
    only = sys.argv[1:] or LANGS
    for lang in only:
        build(lang)
    # coverage vs corpus (base pks)
    cp = os.path.join(HERE, "qa_corpus.json")
    if os.path.exists(cp):
        c = json.load(open(cp, encoding="utf-8"))
        pks = [k.rsplit(":", 1)[-1] for k in c]
        for lang in only:
            p = os.path.join(OUTDIR, f"{lang}.json")
            if os.path.exists(p):
                m = json.load(open(p, encoding="utf-8"))
                hit = sum(1 for pk in pks if pk in m)
                print(f"  coverage {lang}: {hit:,}/{len(pks):,} ({100*hit/len(pks):.1f}%)")


if __name__ == "__main__":
    main()
