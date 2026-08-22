# -*- coding: utf-8 -*-
"""Build a NEW-ERA corpus for Hogwarts Legacy to seed into the community-compute queue
(the R&C fleet just finished all 17,624 lines — this is the next game for the same 4 phone
streams). Hogwarts ships only ONE official non-English text: Arabic (its own gender oracle,
see [[gender-oracle-from-game-langs]]), so the reference panel here is EN + AR only (a
thinner but still real oracle — Arabic marks addressee gender/number, which English drops).

Reads the already-built, already-filtered, already-visibility-ordered community pool file
`games/hogwarts_legacy/extract/ct_strings.json` (MAIN then SUB, `string_key` prefixed
"MAIN:"/"SUB:"), joins each key back to `main_ar.json`/`sub_ar.json` by stripping the prefix.

Output: games/hogwarts_legacy/extract/newera_corpus.json  ({"items":{key:panel}, "sys":...})
Then:   python seed_jobs.py <that> --game hogwarts --mgmt
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HL = os.path.join(REPO, "games", "hogwarts_legacy")
CT = os.path.join(HL, "extract", "ct_strings.json")
MAIN_AR = os.path.join(HL, "extract", "main_ar.json")
SUB_AR = os.path.join(HL, "extract", "sub_ar.json")
OUT = os.path.join(HL, "extract", "newera_corpus.json")
sys.path.insert(0, HERE)
import cc_corpus


def main():
    rows = json.load(open(CT, encoding="utf-8"))            # ordered: MAIN then SUB
    main_ar = json.load(open(MAIN_AR, encoding="utf-8"))
    sub_ar = json.load(open(SUB_AR, encoding="utf-8"))

    order = [r["string_key"] for r in rows]
    source = {r["string_key"]: r["source_en"] for r in rows}
    ar_ref = {}
    for r in rows:
        sk = r["string_key"]
        sec, raw_key = sk.split(":", 1)
        table = main_ar if sec == "MAIN" else sub_ar
        v = table.get(raw_key, "")
        if v:
            ar_ref[sk] = v

    out = cc_corpus.build_items(source, {"AR": ar_ref}, mode="translate", order=order)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    items = out["items"]
    with_ref = sum(1 for v in items.values() if "\nAR:" in v)
    print(f"built {len(items)} New-Era lines  ({with_ref} carry an Arabic reference)  -> {OUT}")
    sk = next(iter(items))
    print("sample:\n" + items[sk][:400])


if __name__ == "__main__":
    main()
