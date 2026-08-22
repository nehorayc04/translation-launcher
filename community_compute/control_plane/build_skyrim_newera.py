# -*- coding: utf-8 -*-
"""Seed the community-compute queue with Skyrim (the RDR2/corsair-cove VM fleet is running
this same corpus in parallel on streams #1-21; this is the SAME "next game for the idle
phone streams" pattern used for Hogwarts/R&C - both of which are now fully done, freeing
their 4 volunteer devices).

Reads the already-built games/skyrim/fleet/corpus.json (multilang_review New-Era-2 rows,
{id: {en, refs:{lang:[fv,mv]}, ...}}) and flattens each ref language to its masculine
variant (matching the same default used by skyrim_nim.py), so the phone worker's prompt
carries the identical six-language reference panel as the VM fleet.

Output: games/skyrim/fleet/newera_cc.json  ({"items":{id:panel}, "sys":...})
Then:   python seed_jobs.py <that> --game skyrim --mgmt
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CORPUS = os.path.join(REPO, "games", "skyrim", "fleet", "corpus.json")
OUT = os.path.join(REPO, "games", "skyrim", "fleet", "newera_cc.json")
sys.path.insert(0, HERE)
import cc_corpus

PANEL = ("ru", "pl", "de", "fr", "es", "it")


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    order = list(corpus.keys())
    en = {k: v.get("en", "") for k, v in corpus.items()}
    refs = {L.upper(): {} for L in PANEL}
    for k, v in corpus.items():
        r = v.get("refs") or {}
        for L in PANEL:
            pair = r.get(L)
            if isinstance(pair, list) and pair:
                fv = pair[0] if len(pair) > 0 else ""
                mv = pair[1] if len(pair) > 1 else fv
                val = mv or fv
                if val:
                    refs[L.upper()][k] = val

    out = cc_corpus.build_items(en, refs, mode="translate", order=order)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    items = out["items"]
    print(f"built {len(items)} New-Era lines -> {OUT}")
    sk = next(iter(items))
    print("sample:\n" + items[sk][:500])


if __name__ == "__main__":
    main()
