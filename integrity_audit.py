"""
integrity_audit.py
==================
Truncation-focused integrity scan across BOTH the base-game
(localization_translated.json) and the Phantom Liberty DLC
(dlc_ep1_translated.json).

Four truncation signals:

  CUT_MID_SENTENCE     Hebrew ends inside a clause — last token is a
                       connector word (ו/ב/ל/מ/של/את/על/עם/לא/כי/אם/או)
                       or a hanging preposition that demands what comes
                       after it. Strong "AI stopped generating" signal.

  MISSING_TERMINAL     Source ends with terminal punct (./!/?) but the
                       Hebrew translation doesn't end with ANY terminal
                       punct (./!/?/׃/...) — the closing thought is gone.

  SENTENCE_COUNT_LOSS  Source has N sentences (separated by ./!/?), the
                       Hebrew has < N/2 sentences AND covers < 60 % of
                       the source length — the LM dropped 50 %+ of the
                       sentences.

  LENGTH_TRUNCATION    Hebrew is < 30 % of source length AND source is
                       multi-sentence (≥2 . / ! / ?) AND source ≥ 80
                       chars — concise translation can't explain this.

Pure scan — zero LM calls, zero writes. Per task spec: NEVER apply fixes
that could break CR2W structure or exceed buffer limits. This script only
reports. Output goes to integrity_audit_report.json + .md.

Severity ranking:
  CRITICAL  multiple signals on the same entry (e.g. CUT_MID_SENTENCE +
            LENGTH_TRUNCATION) — clearly truncated, player-visible.
  HIGH      single strong signal: CUT_MID_SENTENCE or SENTENCE_COUNT_LOSS.
  MEDIUM    MISSING_TERMINAL alone (could be a stylistic choice).
  LOW       LENGTH_TRUNCATION alone on short text (often legitimate).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, asdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "תרגום_משחקים", "source", "resources")
BASE_TRANS = os.path.join(RES, "localization_translated.json")
BASE_ENG   = os.path.join(RES, "localization_export.json")
DLC_TRANS  = os.path.join(RES, "dlc_ep1_translated.json")
DLC_ENG    = os.path.join(RES, "dlc_ep1_text.json")

HEB = re.compile(r"[֐-׿]")
LATIN = re.compile(r"[A-Za-z]")
TAG_RE = re.compile(r"<[^<>]+>|\{[^{}]+\}|%[a-zA-Z]|&\w+;")
SENT_END_RE = re.compile(r"[.!?](?:\s|$)")
WORD_RE = re.compile(r"\S+")

TERMINAL_PUNCT = ".!?…׃"           # what counts as a "closing" mark
# Tightened to ONLY words that are almost-never legitimate sentence enders
# in Hebrew. Removed: "זה", "מה", "כן", "לא", "כל", "מי", "אם", "או", "גם",
# "רק", "אך", "כי", "אל", "יש", "אין", "כך" — these can all end sentences
# in natural Hebrew. Kept only true binding words and English-fallback tags.
CONNECTOR_WORDS = {
    # one-letter prefixes that almost never stand alone as words; if they do,
    # the LM truncated mid-word (e.g. "אלך לבית הקפה ו" — clearly cut)
    "ו", "ב", "ל", "מ", "כ", "ש", "ה",
    # binding two-letter words that demand a following noun
    "של", "את",
    # English words at the end of Hebrew text — strong sign the LM fell back
    # to English (e.g. "לקובץ DOWNLOAD")
    "the", "and", "to", "of", "for", "with", "from", "is", "are", "was",
}


@dataclass
class Finding:
    project: str       # "base" or "dlc"
    section: str
    pk: str
    field: str
    src: str
    trans: str
    signals: list      # which truncation signals fired
    severity: str      # CRITICAL / HIGH / MEDIUM / LOW
    src_len: int
    trans_len: int
    ratio: float
    src_sent_count: int
    trans_sent_count: int
    suggestion: str    # human-readable fix recommendation


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s or "")


def count_sentences(s: str) -> int:
    if not s:
        return 0
    bare = strip_tags(s)
    return max(1, len(SENT_END_RE.findall(bare)))


def last_word(s: str) -> str:
    bare = strip_tags(s).rstrip()
    if not bare:
        return ""
    # strip trailing punct/quotes/brackets so we can inspect the actual word
    bare = re.sub(r"[\"\'\)\]\}»׳ \t\n\r]+$", "", bare)
    m = re.search(r"\S+$", bare)
    return m.group(0) if m else ""


def ends_with_terminal(s: str) -> bool:
    bare = strip_tags(s).rstrip()
    bare = re.sub(r"[\"\'\)\]\}»׳]+$", "", bare)
    return bool(bare) and bare[-1] in TERMINAL_PUNCT


def detect(src: str, trans: str) -> tuple[list, str]:
    """Returns (signals, severity). Empty list = no issue."""
    if not src or not trans:
        return ([], "")
    if not LATIN.search(src):           # no English to translate
        return ([], "")
    if not HEB.search(trans):           # untranslated — handled elsewhere
        return ([], "")

    bare_src = strip_tags(src)
    bare_trans = strip_tags(trans)
    sl = len(bare_src)
    tl = len(bare_trans)
    if sl < 12:                         # too short to be meaningful
        return ([], "")
    ratio = tl / max(1, sl)
    src_sent = count_sentences(bare_src)
    trans_sent = count_sentences(bare_trans)

    signals = []

    # CUT_MID_SENTENCE — last visible Hebrew word is a connector.
    # Lowercased compare lets the English-fallback words match regardless
    # of case ("THE", "the", "The" all hit).
    tail = last_word(trans)
    bare_tail_no_punct = re.sub(r"[^֐-׿A-Za-z]", "", tail)
    if bare_tail_no_punct and bare_tail_no_punct.lower() in CONNECTOR_WORDS:
        signals.append("CUT_MID_SENTENCE")

    # MISSING_TERMINAL — source closes a thought, translation doesn't.
    # Only flag when:
    #   - source has terminal punct ./!/?  (NOT colon/semicolon/ellipsis)
    #   - source ≥ 30 chars (short UI labels often drop punct in Hebrew
    #     by convention, and that's not a defect)
    #   - source has ≥ 2 sentences (single-sentence labels are noise)
    bare_src = strip_tags(src).rstrip()
    bare_src_clean = re.sub(r"[\"\'\)\]\}»׳]+$", "", bare_src)
    if (bare_src_clean
            and bare_src_clean[-1] in ".!?"
            and sl >= 30
            and src_sent >= 2
            and not ends_with_terminal(trans)):
        signals.append("MISSING_TERMINAL")

    # SENTENCE_COUNT_LOSS — translation dropped half the sentences
    if (src_sent >= 3
            and trans_sent <= src_sent // 2
            and ratio < 0.60):
        signals.append("SENTENCE_COUNT_LOSS")

    # LENGTH_TRUNCATION — translation is ≪ 30 % AND source is multi-sentence
    if ratio < 0.30 and src_sent >= 2 and sl >= 80:
        signals.append("LENGTH_TRUNCATION")

    if not signals:
        return ([], "")

    # severity rules
    strong = {"CUT_MID_SENTENCE", "SENTENCE_COUNT_LOSS", "LENGTH_TRUNCATION"}
    n_strong = len(set(signals) & strong)
    if n_strong >= 2:
        return (signals, "CRITICAL")
    if n_strong == 1:
        return (signals, "HIGH")
    if "MISSING_TERMINAL" in signals:
        return (signals, "MEDIUM")
    return (signals, "LOW")


def build_suggestion(src: str, trans: str, signals: list) -> str:
    if "LENGTH_TRUNCATION" in signals:
        return (f"Re-translate fully — source has {count_sentences(src)} "
                f"sentences but Hebrew has {count_sentences(trans)}. "
                "Preserve any \\n line breaks; do not exceed "
                f"~{int(len(src) * 1.3)} chars (safe buffer).")
    if "SENTENCE_COUNT_LOSS" in signals:
        return ("Re-translate — LM dropped sentences. Send src in two halves "
                "(split on a newline or sentence boundary) and join, so the "
                "model sees the full thought.")
    if "CUT_MID_SENTENCE" in signals:
        return ("Re-translate as a single self-contained sentence. The "
                "Hebrew tail is a connector word, meaning the model halted "
                "mid-stream — likely a max_tokens cutoff.")
    if "MISSING_TERMINAL" in signals:
        return ("Likely OK content — add the missing terminal punct "
                "deterministically (no LM): if source ends with `.`, append "
                "`.` to the Hebrew; same for `!` and `?`.")
    return "Manual review."


def scan_file(project: str, trans_path: str, eng_path: str,
              eng_pk_field: str = "primaryKey") -> list[Finding]:
    """eng_pk_field — onscreens key by primaryKey, subtitles by stringId."""
    with open(trans_path, "r", encoding="utf-8") as f:
        trans = json.load(f)
    with open(eng_path, "r", encoding="utf-8") as f:
        eng = json.load(f)

    # build English lookup: section → {pk → entry}
    eng_idx: dict = {}
    for sec, rows in eng.items():
        if not isinstance(rows, list):
            continue
        d = {}
        for e in rows:
            if not isinstance(e, dict):
                continue
            for key in ("primaryKey", "stringId"):
                v = e.get(key)
                if v not in (None, ""):
                    d[str(v)] = e
        eng_idx[sec] = d

    findings: list[Finding] = []
    for sec, rows in trans.items():
        if not isinstance(rows, list):
            continue
        ek = eng_idx.get(sec, {})
        for e in rows:
            if not isinstance(e, dict):
                continue
            src_e = (ek.get(str(e.get("primaryKey", ""))) or
                     ek.get(str(e.get("stringId", ""))) or {})
            for fld in ("femaleVariant", "maleVariant"):
                trans_val = e.get(fld) or ""
                src_val = (src_e.get(fld) or
                           e.get("secondaryKey") or "")
                signals, sev = detect(src_val, trans_val)
                if not signals:
                    continue
                src_sent = count_sentences(src_val)
                trans_sent = count_sentences(trans_val)
                tl = len(strip_tags(trans_val))
                sl = len(strip_tags(src_val))
                findings.append(Finding(
                    project=project, section=sec,
                    pk=str(e.get("primaryKey") or e.get("stringId") or ""),
                    field=fld,
                    src=src_val,
                    trans=trans_val,
                    signals=signals, severity=sev,
                    src_len=sl, trans_len=tl,
                    ratio=round(tl / max(1, sl), 3),
                    src_sent_count=src_sent,
                    trans_sent_count=trans_sent,
                    suggestion=build_suggestion(src_val, trans_val, signals),
                ))
    return findings


def severity_rank(sev: str) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(sev, 9)


def main() -> int:
    print(f"[*] base scan…")
    base = scan_file("base", BASE_TRANS, BASE_ENG)
    print(f"  base: {len(base)} findings")
    print(f"[*] dlc scan…")
    dlc = scan_file("dlc", DLC_TRANS, DLC_ENG)
    print(f"  dlc: {len(dlc)} findings")

    all_findings = sorted(base + dlc,
                          key=lambda f: (severity_rank(f.severity), -f.src_len))

    sev_counts = Counter(f.severity for f in all_findings)
    sig_counts = Counter(sig for f in all_findings for sig in f.signals)

    print()
    print(f"=== TOTAL: {len(all_findings)} truncation findings ===")
    for k in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        print(f"  {k:<10} {sev_counts.get(k, 0):>5}")
    print()
    print("=== signals ===")
    for sig, n in sig_counts.most_common():
        print(f"  {sig:<20} {n:>5}")

    # JSON output (machine-readable)
    out_json = os.path.join(HERE, "integrity_audit_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": len(all_findings),
                "by_severity": dict(sev_counts),
                "by_signal": dict(sig_counts),
                "by_project": {
                    "base": len(base),
                    "dlc": len(dlc),
                },
            },
            "findings": [asdict(f) for f in all_findings],
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[*] JSON report -> {out_json}")

    # Markdown report — descending severity, top 50 per severity
    out_md = os.path.join(HERE, "integrity_audit_report.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Integrity Audit — truncation detector\n\n")
        f.write(f"**Total:** {len(all_findings)} findings "
                f"(base={len(base)}, dlc={len(dlc)})\n\n")
        f.write("## Severity counts\n\n| severity | count |\n|---|---:|\n")
        for k in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            f.write(f"| {k} | {sev_counts.get(k, 0)} |\n")
        f.write("\n## Signals seen\n\n| signal | count |\n|---|---:|\n")
        for sig, n in sig_counts.most_common():
            f.write(f"| `{sig}` | {n} |\n")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            in_bucket = [x for x in all_findings if x.severity == sev]
            if not in_bucket:
                continue
            f.write(f"\n## {sev} ({len(in_bucket)} findings — "
                    f"showing top {min(50, len(in_bucket))} by source length)\n\n")
            for x in in_bucket[:50]:
                f.write(f"### `{x.project}` · {x.section} · pk={x.pk} · {x.field}\n")
                f.write(f"- **signals:** {', '.join(x.signals)}\n")
                f.write(f"- **length:** src={x.src_len}, trans={x.trans_len}, "
                        f"ratio={x.ratio}\n")
                f.write(f"- **sentence count:** src={x.src_sent_count}, "
                        f"trans={x.trans_sent_count}\n")
                f.write(f"- **EN source:**\n")
                f.write(f"```\n{(x.src or '')[:400]}\n```\n")
                f.write(f"- **HE current:**\n")
                f.write(f"```\n{(x.trans or '')[:400]}\n```\n")
                f.write(f"- **fix recommendation:** {x.suggestion}\n\n")
    print(f"[*] Markdown report -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
