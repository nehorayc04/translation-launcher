"""qa_review_extract.py — dump a batch of translated lines (English + Hebrew)
for OPUS to review for semantic quality. Read-only; safe to run while another
process holds the QA write-lock.

Batch source priority: onscreens_final -> onscreens -> quest subtitles.
English source: full extract for onscreens
($TEMP/en_onscreens_full/text/*.json), the entry's secondaryKey for subtitles.

Checkpoint: universal/opus_qa_checkpoint.json  {reviewed: [ "sec|pk", ... ]}
Usage: python qa_review_extract.py <count> <out.json>
Only emits CLEAN, comparable entries (parse OK, has EN + HE, real words) and
SKIPS anything already in the checkpoint or currently structurally broken
(left to the local-model truncation fixer).
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_markup_translate as mk
import get_next_audit_batch as G

SPINE = G.BASE_TR
RES = os.path.dirname(SPINE)
TEMP = os.environ["TEMP"]
CHECKPOINT = os.path.join(UNIV, "opus_qa_checkpoint.json")
EN_ONS = {
    "onscreens/onscreens.json":       os.path.join(TEMP, "en_onscreens_full", "text", "onscreens.json.json"),
    "onscreens/onscreens_final.json": os.path.join(TEMP, "en_onscreens_full", "text", "onscreens_final.json.json"),
}
# section order: highest-visibility first
ORDER = ["onscreens/onscreens_final.json", "onscreens/onscreens.json"]
HEB = mk.HEB
LATIN = mk.LATIN


def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        return set(json.load(open(CHECKPOINT, encoding="utf-8")).get("reviewed", []))
    return set()


def en_index(path):
    w = json.load(open(path, encoding="utf-8"))
    ents = w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    return {str(e.get("primaryKey")): e for e in ents}


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opus_qa_batch.json"
    spine = json.load(open(SPINE, encoding="utf-8"))
    reviewed = load_checkpoint()
    eni = {sec: en_index(p) for sec, p in EN_ONS.items()}

    batch = []
    for sec in ORDER:
        idx = eni[sec]
        for e in spine[sec]:
            if len(batch) >= count:
                break
            pk = str(e.get("primaryKey"))
            key = f"{sec}|{pk}"
            if key in reviewed:
                continue
            he = e.get("femaleVariant") or ""
            if not he or not HEB.search(he):
                continue
            if mk.parse_slots(he) is None:        # broken -> truncation fixer's job
                continue
            en = idx.get(pk)
            if not en:
                continue
            ensrc = en.get("femaleVariant") or ""
            if not ensrc or len(LATIN.findall(ensrc)) < 3:   # need real English words
                continue
            batch.append({"key": key, "sec": sec.split("/")[-1], "pk": pk,
                          "en": ensrc, "he": he})
        if len(batch) >= count:
            break

    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    print(f"dumped {len(batch)} entries to {out}  (reviewed so far: {len(reviewed)})")


if __name__ == "__main__":
    main()
