"""
build_corpus.py — assemble the fleet-ready corpus for 007 First Light.

Joins ct_upload.json (string_key/source_en/section/context, deduped by EN text) with
gender_context.json (ru/es/fr/it/pt reference text per string_key, from extract_gender_context.py)
and derives a DETERMINISTIC addressee/speaker gender (ag/sg) from the game's own Russian via
universal/gender_oracle.py's ru_addressee/ru_speaker (a CLOSED set — never guessed from an open
class, same rule crimson-desert's דור-3 corpus follows).

Shape (per key), matching cd_nim.py's PANEL/_payload() expectations 1:1 so the same New-Era
prompt-building code works unmodified:
  {"en": "...", "ctx": "<section>: <context>", "ru": "...", "es": "...", "fr": "...",
   "it": "...", "pt": "...", "ag": "m"|"f"|"pl" (optional), "sg": "m"|"f"|"pl" (optional)}

Output: games/007_first_light/fleet/corpus.json
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import gender_oracle as go   # noqa: E402

EXTRACT = os.path.join(HERE, "..", "extract")
FLEET = os.path.join(HERE, "..", "fleet")


def main():
    ct = json.load(open(os.path.join(EXTRACT, "ct_upload.json"), encoding="utf-8"))
    gctx = json.load(open(os.path.join(FLEET, "gender_context.json"), encoding="utf-8"))

    corpus = {}
    ag_count = sg_count = 0
    for r in ct:
        k = r["string_key"]
        v = {"en": r["source_en"]}
        ctx_bits = [b for b in (r.get("section"), r.get("context")) if b]
        if ctx_bits:
            v["ctx"] = " | ".join(ctx_bits)
        ref = gctx.get(k, {})
        for lang in ("ru", "es", "fr", "it", "pt"):
            if ref.get(lang):
                v[lang] = ref[lang]
        ru = ref.get("ru", "")
        ag = go.ru_addressee(ru)
        sg = go.ru_speaker(ru)
        if ag:
            v["ag"] = ag; ag_count += 1
        if sg:
            v["sg"] = sg; sg_count += 1
        corpus[k] = v

    tmp = os.path.join(FLEET, "corpus.json.tmp")
    json.dump(corpus, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(FLEET, "corpus.json"))
    print(f"corpus: {len(corpus):,} lines -> fleet/corpus.json")
    print(f"  addressee_gender hard facts: {ag_count:,} ({100*ag_count/len(corpus):.1f}%)")
    print(f"  speaker_gender   hard facts: {sg_count:,} ({100*sg_count/len(corpus):.1f}%)")


if __name__ == "__main__":
    main()
