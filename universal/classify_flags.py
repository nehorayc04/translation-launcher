"""classify_flags.py - deterministic (NO-AI) false-positive filter for the
cross-validation audit flags.

Rule:
  KEEP  -> an OBJECTIVE, machine-detectable defect is present:
             * foreign-script letters in the Hebrew (Cyrillic/Arabic/Thai/
               CJK/Hangul/Kana/Devanagari/Greek/Armenian/Vietnamese)
             * a placeholder / tag present in the English is MISSING from the
               Hebrew (%s, %d, {VALUE...}, <Rich>, <kiroshi>, </...>)
             * a control character leaked into the Hebrew
  DROP  -> none of the above -> the prior judge over-flagged otherwise-valid
           Hebrew (formatting, parentheticals, style it merely disliked).

Subjective defects (stilted phrasing, wrong register, V->וי) are NOT caught
here by design - they need a real judge. A separate `needs_ai_review.jsonl`
keeps the DROP rows that still carry real prose, so nothing is silently lost.

The Opus verdicts already produced (flag_cleanup_verdicts.json, keyed by flag
line index) OVERRIDE the rule where present. Reads the flags file READ-ONLY.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
FLAGS = os.path.join(HERE, "cross_audit_flags.json")
OPUS = r"c:\tmp\flag_cleanup_verdicts.json"          # optional overlay
OUT_KEEP = os.path.join(HERE, "cross_audit_flags_clean.json")
OUT_DROP = os.path.join(HERE, "cross_audit_flags_dropped.json")
OUT_AI = os.path.join(HERE, "needs_ai_review.jsonl")

# ── objective detectors (all-escape: no literal control/exotic chars) ───────
FOREIGN = re.compile(
    "[Ѐ-ӿ"   # Cyrillic
    "؀-ۿ"    # Arabic
    "܀-ݏ"    # Syriac
    "฀-๿"    # Thai
    "一-鿿"    # CJK
    "぀-ヿ"    # Hiragana + Katakana
    "가-힣ᄀ-ᇿ"   # Hangul
    "ऀ-ॿ"    # Devanagari
    "Ͱ-Ͽ"    # Greek
    "԰-֏"    # Armenian
    "Ḁ-ỿ]"   # Latin-Extended-Additional (Vietnamese diacritics)
)
CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
PLACEHOLDER = re.compile(r"%[a-zA-Z]|%\d|\{[^{}]{0,40}\}|<\/?[A-Za-z][^<>]{0,40}>")
WORD = re.compile(r"[A-Za-z֐-׿]{2,}")


def objective_defect(en, he):
    en, he = en or "", he or ""
    if FOREIGN.search(he):
        return "foreign_script"
    if CTRL.search(he):
        return "control_char"
    for ph in set(PLACEHOLDER.findall(en)):
        if ph and ph not in he:
            return "missing_placeholder"
    return None


def _slim(r):
    return {"project": r.get("project"), "section": r.get("section"),
            "pk": r.get("pk"), "field": r.get("field"),
            "english": r.get("english", ""), "current_hebrew": r.get("current_hebrew", "")}


def main():
    opus = {}
    if os.path.exists(OPUS):
        for v in json.load(open(OPUS, encoding="utf-8")):
            opus[v["id"]] = v

    keep, drop, ai = [], [], []
    n = 0
    by_rule = {"foreign_script": 0, "control_char": 0, "missing_placeholder": 0,
               "opus_keep": 0, "opus_drop": 0}
    with open(FLAGS, encoding="utf-8") as f:
        for i, ln in enumerate(f):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            n += 1
            en, he = r.get("english", ""), r.get("current_hebrew", "")

            ov = opus.get(i)
            if ov is not None:                       # Opus overlay wins
                if ov["verdict"] == "KEEP":
                    by_rule["opus_keep"] += 1
                    keep.append({**_slim(r), "verdict": "KEEP", "source": "opus",
                                 "category": ov.get("category"), "confidence": ov.get("confidence"),
                                 "critique": ov.get("critique", ""), "suggest": ov.get("suggest", "")})
                else:
                    by_rule["opus_drop"] += 1
                    drop.append({**_slim(r), "verdict": "DROP", "source": "opus"})
                continue

            rule = objective_defect(en, he)
            if rule:
                by_rule[rule] += 1
                keep.append({**_slim(r), "verdict": "KEEP", "source": "rule",
                             "category": "integrity", "rule": rule,
                             "critique": r.get("critic_feedback", "")})
            else:
                drop.append({**_slim(r), "verdict": "DROP", "source": "rule"})
                if len(WORD.findall(he)) >= 3:
                    ai.append({"section": r.get("section"), "pk": r.get("pk"),
                               "field": r.get("field"), "english": en, "hebrew": he})

    for path, data in ((OUT_KEEP, keep), (OUT_DROP, drop)):
        with open(path, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_AI, "w", encoding="utf-8") as f:
        for r in ai:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"flags read         : {n}")
    print(f"KEEP (real defect) : {len(keep)}  -> {os.path.basename(OUT_KEEP)}")
    print(f"DROP (false flag)  : {len(drop)}  -> {os.path.basename(OUT_DROP)}")
    print(f"  by rule/source   : {by_rule}")
    print(f"needs-AI prose tail: {len(ai)}  -> {os.path.basename(OUT_AI)} "
          f"(DROP'd by rules but real prose -> subjective review later)")


if __name__ == "__main__":
    main()
