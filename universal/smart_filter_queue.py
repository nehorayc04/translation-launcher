"""smart_filter_queue.py — deterministic (NO-AI) pre-filter for the
Cyberpunk localization corpus.

The local model wastes GPU time + hallucinates on strings that need no AImt
review at all (file paths, UI ids, bare code-tags, numbers, untranslated
proper nouns). This script reads the source translation JSONs, SKIPS those,
and writes only the rows that carry real conversational/descriptive text to
`ai_work_queue.jsonl` — each row carrying its original key + file source so it
can be re-merged later. It NEVER calls the model.

Row enumeration reuses the audit's own corpus builder (get_next_audit_batch.
build_corpus) so the filtered queue stays consistent with the live pipeline.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import get_next_audit_batch as G

OUT = os.path.join(HERE, "ai_work_queue.jsonl")

LETTER = re.compile(r"[A-Za-z֐-׿]")                       # any Latin/Hebrew letter
TAGS = re.compile(r"%[a-zA-Z\d]|\{[^{}]*\}|<\/?[^<>]*>")   # placeholders / tags
PATHSEP = re.compile(r"[/\\]")
IDENT = re.compile(r"^[A-Za-z0-9_.\-]+$")                  # bare identifier, no spaces


def skip_reason(en: str, he: str):
    en, he = (en or "").strip(), (he or "").strip()
    if len(he) < 1:
        return "empty"
    if not LETTER.search(he):
        return "numbers_or_symbols_only"            # only digits/punct/special
    # bare code-tags: strip every placeholder/tag, see if anything real remains
    if not LETTER.search(TAGS.sub("", he)):
        return "code_tags_only"
    # file path / UI identifier in the source (not translatable text)
    if " " not in en and (PATHSEP.search(en) or (IDENT.match(en) and "-" in en or "_" in en)):
        return "file_path_or_id"
    # untranslated proper noun / label kept identical in both languages
    if en and en == he:
        return "proper_noun_identical"
    # very short single-token label that is a proper noun (no spaces, capitalized)
    if " " not in en and len(en) <= 24 and en[:1].isupper() and not en.isupper() is False and len(he.split()) <= 1 and en == he:
        return "short_proper_noun"
    return None


def main():
    corpus, base_n, dlc_n = G.build_corpus()
    total = len(corpus)
    skipped = {}
    queue = []
    for r in corpus:
        why = skip_reason(r.english, r.hebrew)
        if why:
            skipped[why] = skipped.get(why, 0) + 1
        else:
            queue.append({
                "id": f"{r.project}|{r.section}|{r.pk}|{r.field}",
                "source": f"{r.project}/{r.section}",
                "pk": r.pk, "field": r.field,
                "english": r.english, "hebrew": r.hebrew,
            })

    with open(OUT, "w", encoding="utf-8") as f:
        for q in queue:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    skip_total = sum(skipped.values())
    print(f"Total original rows: {total}")
    print(f"Rows skipped: {skip_total}  {skipped}")
    print(f"Rows sent to AI queue: {len(queue)}  -> {os.path.basename(OUT)}")


if __name__ == "__main__":
    main()
