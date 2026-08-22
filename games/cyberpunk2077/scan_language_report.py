"""
scan_language_report.py — full-corpus language scanner.

Walks EVERY row of both spines (base + DLC, femaleVariant + maleVariant),
strips tags/placeholders, and records aside every row whose VISIBLE text
contains English (Latin) or any other non-Hebrew language. No LM, no writes
to the spines — report files only.

Outputs (next to this script):
  language_report.jsonl  — one record per finding (machine-readable)
  language_report.txt    — human summary: counts per kind + samples

Kinds:
  foreign_script     — Arabic / Cyrillic / CJK / Thai / Greek ... characters
  english_only       — the whole visible line is English (no Hebrew at all)
  english_in_hebrew  — Hebrew line containing English word(s)
  corrupt_midword    — Hebrew letters glued into a Latin word (e.g. 'גlitch')

Skipped (not findings): empty values, numbers/punct-only, file-paths/IDs,
bare code-tags — via smart_filter_queue.skip_reason when available.

Usage:  python scan_language_report.py            (scan + write reports)
        python scan_language_report.py --no-skip  (report even junk rows)
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

OUT_JSONL = os.path.join(HERE, "language_report.jsonl")
OUT_TXT   = os.path.join(HERE, "language_report.txt")

TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
HEB = re.compile(r"[א-ת]")
import unicodedata


def _foreign_chars(s):
    """Every LETTER that is neither Latin nor Hebrew = foreign (catches ALL
    scripts — Bengali ্য was missed by the old enumerated ranges)."""
    out = []
    for ch in s:
        o = ord(ch)
        if o < 0x80:                       # ASCII
            continue
        if 0x0590 <= o <= 0x05FF:          # Hebrew
            continue
        if (0x00C0 <= o <= 0x024F) or (0x1E00 <= o <= 0x1EFF):  # Latin ext
            continue
        if unicodedata.category(ch).startswith("L"):
            out.append(ch)
    return out


class FOREIGN:                              # drop-in for the old regex API
    @staticmethod
    def search(s):
        return bool(_foreign_chars(s))

    @staticmethod
    def findall(s):
        return _foreign_chars(s)
LATIN_WORD = re.compile(r"[A-Za-z]{2,}(?:[ '\-][A-Za-z]{2,})*")
CORRUPT = re.compile(r"[א-ת]+[a-z]{2,}")
CTRL = "\x01\x02\x03\x04\x05"


def classify(he):
    """Return (kind, evidence) for the visible text, or None if clean."""
    vis = TAG.sub(" ", he).strip().lstrip(CTRL)
    if not vis:
        return None
    if FOREIGN.search(vis):
        chars = "".join(sorted(set(FOREIGN.findall(vis))))[:20]
        return ("foreign_script", chars)
    m = CORRUPT.search(vis)
    if m:
        return ("corrupt_midword", m.group(0))
    words = LATIN_WORD.findall(vis)
    if not words:
        return None
    if not HEB.search(vis):
        return ("english_only", " ".join(words)[:60])
    return ("english_in_hebrew", " | ".join(words[:5])[:60])


def main():
    no_skip = "--no-skip" in sys.argv
    corpus, _, _ = G.build_corpus()
    print(f"scanning {len(corpus):,} rows (fv+mv where present) ...")

    findings = []
    counts = collections.Counter()
    skipped = 0
    for r in corpus:
        he = r.hebrew or ""
        if not he.strip():
            continue
        # skip rows that genuinely need no translation (IDs, numbers, codes)
        if not no_skip and SF is not None:
            try:
                if SF.skip_reason(r.english or "", he):
                    skipped += 1
                    continue
            except Exception:
                pass
        res = classify(he)
        if not res:
            continue
        kind, evidence = res
        counts[kind] += 1
        findings.append({
            "project": "dlc" if r.section.startswith("ep1") else "base",
            "section": r.section, "pk": str(r.pk), "field": r.field,
            "kind": kind, "evidence": evidence,
            "hebrew": he[:200], "english": (r.english or "")[:200],
        })

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for x in findings:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    # human summary
    lines = ["= language scan report =",
             f"rows scanned: {len(corpus):,}   junk skipped: {skipped:,}",
             f"total findings: {len(findings):,}", ""]
    for kind, n in counts.most_common():
        lines.append(f"--- {kind}: {n:,} ---")
        for x in [y for y in findings if y["kind"] == kind][:10]:
            lines.append(f"  [{x['project']}/{x['section'].split('/')[-1][:22]}] "
                         f"pk={x['pk']} :: {x['evidence']!r}")
        lines.append("")
    open(OUT_TXT, "w", encoding="utf-8").write("\n".join(lines))

    print(f"findings: {len(findings):,}  (junk skipped: {skipped:,})")
    for kind, n in counts.most_common():
        print(f"  {kind}: {n:,}")
    print(f"-> {OUT_JSONL}\n-> {OUT_TXT}")


if __name__ == "__main__":
    main()
