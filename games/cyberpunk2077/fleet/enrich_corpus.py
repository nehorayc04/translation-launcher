# -*- coding: utf-8 -*-
"""Enrich qa_corpus.json with the MULTILINGUAL addressee oracle per the "עידן חדש" doctrine
(universal/NEW_ERA_LANGUAGE_ROLES.md), keyed by pk, from the game's own ar/ru/pl/es/it
(lang_maps/*.json). Runs on the HOST (imports the canonical Witcher-3 oracle w3_lang_oracle.py); the
verdict is BAKED into the corpus so the standalone VM worker (cpqa_nim.py, copied from w3qa_nim.py)
just consumes it.

Per line it attaches:
  ar/ru/pl/es/it = the game's text in those langs (LLM cross-reference context)
  ag  = ADDRESSEE gender/number m|f|pl  — Arabic decides ALONE (vocalized); else the CONSENSUS of
        >=2 of {Russian, Polish, Spanish, Italian}. A lone noisy vote never flips a line.
  num = 'pl'    genuine plural addressee (ag=='pl' — Arabic أنتم is the only confound-free plural).
  formal = True the FORMAL-YOU TRAP: a non-Arabic lang marks plural (ru вы / it voi / es usted) while
                Arabic does NOT → polite-SINGULAR → Hebrew must stay אתה/את, never אתם.

Backs up the old corpus. Reports coverage per axis. Mirrors w3qa_nim.gender_facts exactly.
"""
import json, os, sys, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "witcher3", "fleet"))  # canonical oracle
import w3_lang_oracle as O  # noqa: E402  (ar/ru/pl/es/it addressee parsers + consensus)

CORPUS = os.path.join(HERE, "qa_corpus.json")
MAPS = os.path.join(HERE, "lang_maps")
CTX_LANGS = ["ar", "ru", "pl", "es", "it"]   # baked as LLM context (doctrine set; fr dropped — noisy)


def _txt(v):
    if isinstance(v, dict):
        return v.get("f") or v.get("m") or ""
    return v or ""


def gender_facts(ar, ru, pl, es, it):
    """(ag, num, formal) — Arabic decides alone; else >=2 of {ru,pl,es,it} agree on m/f. formal =
    a non-Arabic plural with no Arabic plural (polite-singular trap). Exact copy of the doctrine rule."""
    a = O.ar_addressee(ar) if ar else None
    non_ar = [O.ru_addressee(ru) if ru else None, O.pl_addressee(pl) if pl else None,
              O.es_addressee(es) if es else None, O.it_addressee(it) if it else None]
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
            # need >=2 and no tie between m and f
            if votes[best] >= 2 and not (len(votes) > 1 and sorted(votes.values())[-2:] == [votes[best], votes[best]]):
                ag = best
    num = "pl" if ag == "pl" else None
    return ag, num, formal


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    print(f"corpus: {len(corpus):,}")
    maps = {lg: (json.load(open(os.path.join(MAPS, f"{lg}.json"), encoding="utf-8"))
                 if os.path.exists(os.path.join(MAPS, f"{lg}.json")) else {}) for lg in CTX_LANGS}
    for lg in CTX_LANGS:
        print(f"  {lg}: {len(maps[lg]):,} keys")
    cov = {k: 0 for k in CTX_LANGS + ["ag", "formal", "num_pl"]}
    for key, item in corpus.items():
        pk = key.rsplit(":", 1)[-1]
        t = {lg: _txt(maps[lg].get(pk)) for lg in CTX_LANGS}
        for f in list(item.keys()):
            if f in ("ar", "ru", "pl", "es", "it", "fr", "ag", "sg", "rg", "formal", "num"):
                item.pop(f, None)
        ag, num, formal = gender_facts(t["ar"], t["ru"], t["pl"], t["es"], t["it"])
        for lg in CTX_LANGS:
            if t[lg]:
                item[lg] = t[lg][:240]; cov[lg] += 1
        if ag:
            item["ag"] = ag; cov["ag"] += 1
        if formal:
            item["formal"] = True; cov["formal"] += 1
        if num == "pl":
            item["num"] = "pl"; cov["num_pl"] += 1
    bak = CORPUS + ".pre_newera"
    if not os.path.exists(bak):
        shutil.copy2(CORPUS, bak)
    json.dump(corpus, open(CORPUS, "w", encoding="utf-8"), ensure_ascii=False)
    n = len(corpus)
    print(f"enriched -> {CORPUS}  (backup {os.path.basename(bak)})")
    for k, v in cov.items():
        print(f"  {k:8} {v:,} ({100*v/n:.1f}%)")


if __name__ == "__main__":
    main()
