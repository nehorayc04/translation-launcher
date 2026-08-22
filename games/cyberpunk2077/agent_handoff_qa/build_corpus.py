"""build_corpus.py — build the CP2077 QA corpus for the parallel-agent review.

Corpus = every UNREVIEWED, comparable onscreens_final entry: a real Hebrew
femaleVariant that parses cleanly + a real English source (>=3 Latin words).
Excludes anything already in the GLOBAL Opus checkpoint
(universal/opus_qa_checkpoint.json) so the agents never re-review the 9,280
lines Opus already did.

corpus.json shape: { "<sec>|<pk>": {sec, pk, en, he, flags:[]} }
  sec = basename ("onscreens_final.json"); the composite key matches the
  checkpoint key format so apply_corrections can mark them reviewed globally.

Usage: python build_corpus.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.dirname(HERE)
sys.path.insert(0, CP)
import qa_review_extract as X   # reuses SPINE/ORDER/EN_ONS/HEB/LATIN/load_checkpoint/en_index
import cp2077_markup_translate as mk

# onscreens_final only this round (highest-visibility; onscreens.json mirrors it)
SECTIONS = ["onscreens/onscreens_final.json"]


def main():
    spine = json.load(open(X.SPINE, encoding="utf-8"))
    reviewed = X.load_checkpoint()
    corpus = {}
    for sec in SECTIONS:
        idx = X.en_index(X.EN_ONS[sec])
        for e in spine[sec]:
            pk = str(e.get("primaryKey"))
            key = f"{sec}|{pk}"
            if key in reviewed:
                continue
            he = e.get("femaleVariant") or ""
            if not he or not X.HEB.search(he):
                continue
            if mk.parse_slots(he) is None:        # broken markup -> not for agents
                continue
            en = idx.get(pk)
            if not en:
                continue
            ensrc = en.get("femaleVariant") or ""
            if not ensrc or len(X.LATIN.findall(ensrc)) < 3:
                continue
            corpus[key] = {"sec": sec.split("/")[-1], "pk": pk,
                           "en": ensrc, "he": he, "flags": []}
    out = os.path.join(HERE, "corpus.json")
    json.dump(corpus, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"corpus: {len(corpus)} unreviewed comparable entries -> {os.path.basename(out)}")


if __name__ == "__main__":
    main()
