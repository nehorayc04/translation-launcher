"""
scan_word_anomalies.py — find ILLOGICAL WORDS across the whole corpus.

Detects, per visible word (tags/placeholders stripped):
  mixed_script_word   — Hebrew + foreign letter in the SAME word (גlitch, bלך)
  hebrew_digit_word   — digit embedded inside a Hebrew word (ב4וקר)
  single_hebrew_letter— an isolated single Hebrew letter ("ב" alone)
  single_latin_letter — an isolated single Latin letter (except V — the protagonist)
  punct_inside_word   — ?!.,;: glued INSIDE a word (שח?לום) — ' ׳ - ־ are legit
  niqqud              — vowel points (forbidden by project rules)
  repeated_letters    — the same letter 4+ times in a row (הההה)
  control_chars       — control bytes inside the visible text
  double_space        — two or more consecutive spaces

Output: ONE human-ordered file — word_anomalies_report.txt — grouped by
category, each line shows [project/section] pk, the suspicious word, the full
Hebrew line and the English source, so it can be reviewed top-to-bottom.
(Also writes word_anomalies.jsonl for scripting.)

Read-only: never touches the spines. Usage: python scan_word_anomalies.py
"""
import os, sys, json, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))

import get_next_audit_batch as G
try:
    import smart_filter_queue as SF
except Exception:
    SF = None

OUT_TXT   = os.path.join(HERE, "word_anomalies_report.txt")
OUT_JSONL = os.path.join(HERE, "word_anomalies.jsonl")

TAG    = re.compile(r"<[^>]*>|\{[^}]*\}")
# literal subtitle formatting codes: backslash-n / -r / -t (two characters in
# the data) — line-break markup, NOT words; must not produce 'n' tokens
ESC    = re.compile(r"\\[nrt]")
CTRL   = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
HEB    = re.compile(r"[א-ת]")
LAT    = re.compile(r"[A-Za-z]")
NIQQUD = re.compile(r"[ְ-ׇֽֿׁׂ]")
# a "word" = letters/digits plus the in-word-legit marks: ' ׳ ״ " - ־
# ASCII double-quote included — Hebrew abbreviations are written מ"מ / דוא"ל
WORD   = re.compile(r"[A-Za-zא-ת0-9'׳״\"\-־]+")
MIXED  = re.compile(r"(?:[א-ת][A-Za-z])|(?:[A-Za-z][א-ת])")
HEBDIG = re.compile(r"(?:[א-ת][0-9])|(?:[0-9][א-ת])")
PUNCTW = re.compile(r"[A-Za-zא-ת][?!.,;:][A-Za-zא-ת]")
REPEAT = re.compile(r"([A-Za-zא-ת])\1{3,}")
DSPACE = re.compile(r"  +")

ORDER = ["mixed_script_word", "hebrew_digit_word", "single_hebrew_letter",
         "single_latin_letter", "punct_inside_word", "niqqud",
         "repeated_letters", "control_chars", "double_space",
         "hebrew_too_long", "long_latin_run"]


def find_anomalies(he):
    """Yield (category, evidence) pairs for one value."""
    vis = ESC.sub(" ", TAG.sub(" ", he))
    if CTRL.search(vis.lstrip("\x01\x02\x03\x04\x05")):
        yield ("control_chars", repr(CTRL.search(vis).group(0)))
    vis = vis.lstrip("\x01\x02\x03\x04\x05")
    if NIQQUD.search(vis):
        yield ("niqqud", vis[max(0, NIQQUD.search(vis).start() - 6):NIQQUD.search(vis).start() + 6])
    # double-space judged with tags/escapes replaced by a placeholder CHAR —
    # both ''-removal and ' '-substitution fabricate false double spaces
    if DSPACE.search(ESC.sub("§", TAG.sub("§", he)).strip()):
        yield ("double_space", "")
    m = REPEAT.search(vis)
    if m:
        yield ("repeated_letters", m.group(0))
    m = PUNCTW.search(vis)
    if m:
        yield ("punct_inside_word", m.group(0))
    for w in WORD.findall(vis):
        if MIXED.search(w):
            yield ("mixed_script_word", w)
        elif HEBDIG.search(w):
            yield ("hebrew_digit_word", w)
    # single-letter detection runs on a TAG-JOINED view: a prefix letter
    # attached to a tag (ל<n>פלטהד</n>) is NOT an isolated letter
    vis_joined = ESC.sub(" ", TAG.sub("", he)).lstrip("\x01\x02\x03\x04\x05")
    for w in WORD.findall(vis_joined):
        if len(w) == 1:
            if HEB.match(w):
                yield ("single_hebrew_letter", w)
            elif LAT.match(w) and w != "V":   # V = the protagonist, legit
                yield ("single_latin_letter", w)
        # a single Hebrew "word" running 22+ letters with no space = likely a
        # word-spacing bug / doubled/runaway translation
        elif len(w) >= 22 and HEB.search(w) and not LAT.search(w):
            yield ("hebrew_too_long", w[:30])
    # a long uninterrupted Latin run (5+ words / 30+ chars) inside Hebrew text
    # = probably untranslated English left in (not a short brand name)
    if HEB.search(vis):
        for m in re.finditer(r"[A-Za-z][A-Za-z '\-]{29,}", TAG.sub(" ", vis)):
            run = m.group(0).strip()
            if len(run.split()) >= 5:
                yield ("long_latin_run", run[:40])


def main():
    corpus, _, _ = G.build_corpus()
    print(f"scanning {len(corpus):,} rows ...")
    by_cat = collections.defaultdict(list)
    skipped = 0
    for r in corpus:
        he = r.hebrew or ""
        if not he.strip():
            continue
        if SF is not None:
            try:
                if SF.skip_reason(r.english or "", he):
                    skipped += 1
                    continue
            except Exception:
                pass
        seen = set()
        for cat, ev in find_anomalies(he):
            key = (cat, ev)
            if key in seen:           # one report per (category,evidence) per row
                continue
            seen.add(key)
            by_cat[cat].append({
                "project": "dlc" if r.section.startswith("ep1") else "base",
                "section": r.section, "pk": str(r.pk), "field": r.field,
                "category": cat, "word": ev,
                "hebrew": he[:160], "english": (r.english or "")[:100],
            })

    total = sum(len(v) for v in by_cat.values())
    # ── the one ordered review file ──
    lines = ["דוח מילים לא-הגיוניות — לעבור קטגוריה-קטגוריה",
             "=" * 60,
             f"שורות שנסרקו: {len(corpus):,} | junk שדולג: {skipped:,} | סך ממצאים: {total:,}",
             ""]
    for cat in ORDER:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append("")
        lines.append("#" * 60)
        lines.append(f"## {cat}  —  {len(items):,} ממצאים")
        lines.append("#" * 60)
        for x in items:
            lines.append(f"[{x['project']}/{x['section'].split('/')[-1][:24]}] pk={x['pk']} ({x['field']})")
            if x["word"]:
                lines.append(f"  מילה: {x['word']!r}")
            lines.append(f"  HE: {x['hebrew']}")
            if x["english"]:
                lines.append(f"  EN: {x['english']}")
            lines.append("")
    open(OUT_TXT, "w", encoding="utf-8").write("\n".join(lines))

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for cat in ORDER:
            for x in by_cat.get(cat, []):
                f.write(json.dumps(x, ensure_ascii=False) + "\n")

    print(f"findings: {total:,}  (junk skipped: {skipped:,})")
    for cat in ORDER:
        if by_cat.get(cat):
            print(f"  {cat}: {len(by_cat[cat]):,}")
    print(f"-> {OUT_TXT}")


if __name__ == "__main__":
    main()
