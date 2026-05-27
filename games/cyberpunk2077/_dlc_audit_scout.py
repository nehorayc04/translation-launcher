"""
DLC quality scout — reads dlc_ep1_translated.json + dlc_ep1_text.json,
categorizes every translated femaleVariant/maleVariant into:

  CODE_LIKE         source is mostly symbols/digits/IDs — should NEVER have
                    been translated (e.g. 'gylcrE34FUzU2R_OUR_CHOICES_…').
                    These were typically partial-transliterated by the LM.
  IDENTIFIER_LEAK   source is dev-junk / placeholder (starts with '['/'{',
                    is all caps with underscores, etc.) but got translated.
  DOUBLE_LANG       translated value still contains an English run mid-Hebrew
                    (qa.english_leak heuristic, but local copy so we can scan
                    without loading the QA stack against base-game paths).
  LENGTH_ANOMALY    translated length is < 0.3× or > 2.5× source length —
                    likely truncation or hallucination.
  TAG_DROPPED       source had a tag/placeholder that didn't survive.
  LEAD_TRANSLIT     translated value's first token is a letter-by-letter
                    transliteration of an English code-token (mixed-case
                    Latin source → naive Hebrew letters in the same spot).
  OK                no defect detected by the heuristics.

Pure scan: zero LM calls, zero writes. Reports counts + 20 samples per kind.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

_REPO_ROOT = os.path.dirname(os.path.dirname(HERE))   # games/<game>/ -> repo root
RES  = os.path.join(_REPO_ROOT, "תרגום_משחקים", "source", "resources")
DLC  = os.path.join(RES, "dlc_ep1_translated.json")
ENG  = os.path.join(RES, "dlc_ep1_text.json")

HEB     = re.compile(r"[֐-׿]")
LATIN   = re.compile(r"[A-Za-z]")
DIGIT   = re.compile(r"\d")
LETTER_OR_SPACE = re.compile(r"[A-Za-z\s]")
WORD_RE = re.compile(r"[A-Za-z]{2,}")
TAG_RE  = re.compile(r"<[^<>]+>|\{[^{}]+\}|%[a-zA-Z]")
CODE_TOKEN = re.compile(r"[A-Za-z]*\d+[A-Za-z]+\w*|\w*_[A-Z]+_\w*")

# common ASCII-letter English words present in real prose
COMMON_EN = {
    "the","and","you","your","for","with","from","this","that","they",
    "have","not","but","are","was","were","what","when","where","who",
    "all","one","out","can","get","got","make","made","like","want",
    "need","just","know","time","into","over","than","then","more",
    "some","said","very","much","take","give","come","look","find",
    "back","good","day","night","city","new","old","still","only",
    "way","right","left","first","last","next","other","every",
    "after","before","under","about","against","between","through",
    "should","would","could","will","because","since","until",
    "people","life","work","place","thing","things","really","never",
    "always","again","also","there","here","being","done","going",
    "tell","told","ask","asked","try","tried",
}
BRAND_WHITELIST = {
    "night","city","arasaka","militech","kang","tao","kiroshi","netwatch",
    "trauma","team","zetatech","biotechnica","petrochem","delamain",
    "afterlife","maelstrom","valentinos","tyger","claws","voodoo","boys",
    "animals","moxes","scavengers","samurai","johnny","silverhand","alt",
    "rogue","kerry","panam","judy","river","takemura","hanako","yorinobu",
    "saburo","evelyn","dexter","jackie","misty","viktor","regina","padre",
    "wakako","placide","brigitte","adam","smasher","blackwall","relic",
    "cyberpsycho","ncpd","max","doc","watson","kabuki","japantown",
    "westbrook","pacifica","heywood","santo","domingo","rancho","coronado",
    "charter","hill","steam","windows","android","ios","amd","nvidia",
    "intel","asus","rog","ally",
    # phantom liberty
    "phantom","liberty","dogtown","songbird","solomon","reed","myers",
    "rosalind","hansen","kurt","alex","slider","aurore","cassel","bree",
    "tucker","nele","barghest","nuance","longshore","blackline","fia",
    "luther","mr","hands","horatio","milko","stranger","ware",
}


def is_code_like(src: str) -> bool:
    """Source is mostly symbols/digits, OR is an obvious all-caps identifier."""
    if not src:
        return False
    if "<" in src or "{" in src or "%" in src:  # tags/placeholders are NOT code-like
        return False
    letters = sum(1 for c in src if c.isalpha())
    if letters == 0:
        return True
    non_alpha = sum(1 for c in src if not c.isalnum() and not c.isspace())
    alnum = letters + sum(1 for c in src if c.isdigit())
    if alnum and non_alpha / max(1, len(src)) > 0.30:
        return True
    # identifier patterns: WORD_WORD_WORD or camelCase mixed with digits
    if CODE_TOKEN.search(src):
        return True
    return False


def looks_like_identifier(src: str) -> bool:
    """Bracketed placeholders, all-caps tags, dev-junk markers."""
    s = src.strip()
    if not s:
        return False
    if s.startswith(("[", "{")) and s.endswith(("]", "}")):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]+", s):
        return True
    if re.search(r"\b(TBD|TODO|TBA|DEPRECATED|PLACEHOLDER|DEBUG|TEMP|TEST)\b", s):
        return True
    if re.search(r"\b(IGNORE|DELETE|DEV.ONLY|UNUSED)\b", s, re.IGNORECASE):
        return True
    return False


def english_run_in_hebrew(trans: str) -> str | None:
    """Find a 2+ word English run inside a Hebrew translation that contains
    at least one common English word and no whitelisted brand. Returns the
    offending run or None."""
    if not HEB.search(trans):
        return None
    for m in re.finditer(r"(?:[A-Za-z]{2,}\s+){1,}[A-Za-z]{2,}", trans):
        words = [w.lower() for w in m.group(0).split()]
        if all(w in BRAND_WHITELIST for w in words):
            continue
        if any(w in COMMON_EN for w in words):
            return m.group(0)
    return None


def length_anomaly(src: str, trans: str) -> str | None:
    if not src or not trans:
        return None
    if len(src) < 12:           # skip very short — ratios swing too wildly
        return None
    r = len(trans) / max(1, len(src))
    if r < 0.30:
        return f"too short ({len(trans)}/{len(src)} = {r:.2f}x)"
    if r > 2.50:
        return f"too long ({len(trans)}/{len(src)} = {r:.2f}x)"
    return None


def tag_dropped(src: str, trans: str) -> str | None:
    src_tags = sorted(set(TAG_RE.findall(src)))
    if not src_tags:
        return None
    missing = [t for t in src_tags if t not in trans]
    if missing:
        return f"missing tags: {missing[:3]}"
    return None


def looks_like_code_token(word: str) -> bool:
    """A word that looks like an identifier, not a normal English word."""
    if len(word) < 4:
        return False
    low = word.lower()
    if low in COMMON_EN or low in BRAND_WHITELIST:
        return False
    # camelCase / mixedCase like 'gylcrE' or 'TooltipText'
    if re.search(r"[a-z][A-Z]", word):
        return True
    # contains digits mixed with letters (only mid-word, not e.g. trailing year)
    if re.search(r"[A-Za-z]\d|\d[A-Za-z]", word):
        return True
    return False


def lead_translit(src: str, trans: str) -> bool:
    """Translation starts with letter-by-letter transliteration of a code-token
    Latin word (e.g. 'gylcrE34FUzU2R' → 'גילקרי34FUzU2R')."""
    if not src or not trans:
        return False
    m = re.match(r"([A-Za-z]{4,})", src)
    if not m:
        return False
    if not looks_like_code_token(m.group(1)):
        return False
    return bool(HEB.match(trans))


def classify(src: str, trans: str) -> tuple[str, str]:
    if not src or not trans:
        return ("EMPTY", "")
    if not LATIN.search(src):
        return ("OK", "")          # source has no English to translate
    if not HEB.search(trans):
        return ("UNTRANSLATED", "")
    if looks_like_identifier(src):
        return ("IDENTIFIER_LEAK", src[:60])
    if lead_translit(src, trans):
        return ("LEAD_TRANSLIT", f"{src[:30]} → {trans[:30]}")
    if is_code_like(src):
        return ("CODE_LIKE", src[:60])
    run = english_run_in_hebrew(trans)
    if run:
        return ("DOUBLE_LANG", run[:60])
    ld = length_anomaly(src, trans)
    if ld:
        return ("LENGTH_ANOMALY", ld)
    td = tag_dropped(src, trans)
    if td:
        return ("TAG_DROPPED", td)
    return ("OK", "")


def main() -> int:
    with open(DLC, encoding="utf-8") as f:
        dlc = json.load(f)
    with open(ENG, encoding="utf-8") as f:
        eng = json.load(f)
    # build English lookup: section → primaryKey → English source value
    eng_idx: dict = {}
    for sec, rows in eng.items():
        if not isinstance(rows, list):
            continue
        idx = {}
        for e in rows:
            if isinstance(e, dict):
                pk = str(e.get("primaryKey", ""))
                if pk:
                    idx[pk] = e
        eng_idx[sec] = idx

    counts = Counter()
    samples: dict[str, list] = {}
    for sec, rows in dlc.items():
        if not isinstance(rows, list):
            continue
        ek = eng_idx.get(sec, {})
        for e in rows:
            if not isinstance(e, dict):
                continue
            src_e = ek.get(str(e.get("primaryKey", "")), {})
            for fld in ("femaleVariant", "maleVariant"):
                trans = e.get(fld) or ""
                src   = src_e.get(fld) or e.get("secondaryKey") or ""
                if not trans:
                    continue
                kind, detail = classify(src, trans)
                counts[kind] += 1
                if kind not in ("OK", "EMPTY") and len(samples.setdefault(kind, [])) < 20:
                    samples[kind].append(
                        f"  [{sec[:30]:<30}] {fld[0]} src={src[:55]!r}  trans={trans[:55]!r}"
                        + (f"  ({detail})" if detail else "")
                    )

    out = os.path.join(HERE, "_dlc_audit_scout_report.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("DLC quality scout — defect counts:\n")
        for k, v in sorted(counts.items(), key=lambda x: -x[1]):
            f.write(f"  {k:<18} {v:>8,}\n")
        f.write("\n")
        for kind, lines in samples.items():
            f.write(f"--- {kind} samples ({len(lines)}) ---\n")
            for ln in lines:
                f.write(ln + "\n")
            f.write("\n")
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
