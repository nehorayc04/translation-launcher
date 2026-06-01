"""
cp2077_lqa_check.py — Linguistic QA pass
========================================
Checks the translated localization for three quality issues:
  1. UI Overflow            (Hebrew >2.5x original, original >10 chars)
  2. Punctuation Mismatch   (... ? ! on EN side missing on HE side)
  3. Glossary Inconsistency (literal translations of proper nouns)

Only inspects entries from onscreens/ or subtitles/ that actually contain Hebrew.
"""

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


BASE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים\source\resources"
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")

ALLOWED_FOLDERS = ["onscreens", "subtitles"]
FIELDS = ("femaleVariant", "maleVariant")

OVERFLOW_RATIO = 2.5
OVERFLOW_MIN_LEN = 10

GLOSSARY_BAD = {
    "Night City":  ["עיר הלילה"],
    "Ripperdoc":   ["רופא קרעי", "קרע-דוק"],
    "Netrunner":   ["רץ רשת", "רץ-רשת"],
}

HEBREW_RE = re.compile(r"[֐-׿]")


def has_hebrew(s):
    return bool(HEBREW_RE.search(s)) if isinstance(s, str) else False


def in_allowed_folder(path):
    return any(f in path.lower() for f in ALLOWED_FOLDERS)


def short(s, n=70):
    s = (s or "").replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + "..."


def banner(title):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def get_trailing_punct(text):
    """Return one of '...', '?', '!' if the string ends with it (after trimming
    spaces/quotes), else None. Order matters: check '...' before '.'."""
    if not isinstance(text, str):
        return None
    s = text.rstrip(' \t\n\r"\'`)]')
    if s.endswith("..."):
        return "..."
    if s.endswith("?"):
        return "?"
    if s.endswith("!"):
        return "!"
    return None


def main():
    banner("CYBERPUNK 2077 — Linguistic QA Report")
    print(f"  Original:   {ORIGINAL_FILE}")
    print(f"  Translated: {TRANSLATED_FILE}\n")

    print("  Loading...")
    with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
        original = json.load(f)
    print(f"    [OK] export      ({len(original):,} files)")

    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)
    print(f"    [OK] translated  ({len(translated):,} files)")

    inspected = 0
    overflow_hits = []      # (ratio, len_orig, len_trans, fp, i, field, ov, tv)
    punct_hits = {"...": [], "?": [], "!": []}
    glossary_hits = {term: [] for term in GLOSSARY_BAD}

    for filepath, orig_entries in original.items():
        if not in_allowed_folder(filepath):
            continue
        trans_entries = translated.get(filepath, [])

        for i, orig in enumerate(orig_entries):
            if i >= len(trans_entries):
                continue
            t = trans_entries[i]
            if not isinstance(t, dict):
                continue
            for field in FIELDS:
                ov = orig.get(field, "")
                tv = t.get(field, "")
                if not isinstance(ov, str) or not isinstance(tv, str):
                    continue
                if not ov.strip() or not tv.strip():
                    continue
                if not has_hebrew(tv):
                    continue

                inspected += 1

                # 1. UI Overflow
                if len(ov) > OVERFLOW_MIN_LEN:
                    ratio = len(tv) / len(ov)
                    if ratio > OVERFLOW_RATIO:
                        overflow_hits.append(
                            (ratio, len(ov), len(tv), filepath, i, field, ov, tv)
                        )

                # 2. Punctuation Mismatch
                punct = get_trailing_punct(ov)
                if punct and get_trailing_punct(tv) != punct:
                    punct_hits[punct].append((filepath, i, field, ov, tv))

                # 3. Glossary Inconsistency
                for term, bad_variants in GLOSSARY_BAD.items():
                    for bad in bad_variants:
                        if bad in tv:
                            glossary_hits[term].append(
                                (filepath, i, field, bad, ov, tv)
                            )
                            break

    # ── Report ──────────────────────────────────────────────────────────
    banner("INSPECTION SCOPE")
    print(f"  Hebrew-bearing entries inspected: {inspected:,}")

    # 1. UI Overflow
    banner("1. UI OVERFLOW  (Hebrew length / English length > 2.5)")
    print(f"  Total entries flagged: {len(overflow_hits):,}\n")
    if overflow_hits:
        overflow_hits.sort(key=lambda x: x[0], reverse=True)
        print("  Top 5 by ratio:")
        for ratio, lo, lt, fp, i, field, ov, tv in overflow_hits[:5]:
            short_fp = fp.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            print(f"\n    [{short_fp}#{i}.{field}]  ratio {ratio:.2f}x  ({lo} → {lt} chars)")
            print(f"      EN: {short(ov)!r}")
            print(f"      HE: {short(tv)!r}")

    # 2. Punctuation
    banner("2. PUNCTUATION MISMATCH")
    total_punct = sum(len(v) for v in punct_hits.values())
    print(f"  Total entries flagged: {total_punct:,}")
    for sym in ("...", "?", "!"):
        hits = punct_hits[sym]
        print(f"    Missing trailing '{sym}': {len(hits):,}")
    if total_punct:
        print("\n  Sample (up to 3 per symbol):")
        for sym in ("...", "?", "!"):
            hits = punct_hits[sym]
            if not hits:
                continue
            print(f"\n    --- '{sym}' ---")
            for fp, i, field, ov, tv in hits[:3]:
                short_fp = fp.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                print(f"    [{short_fp}#{i}.{field}]")
                print(f"      EN: {short(ov)!r}")
                print(f"      HE: {short(tv)!r}")

    # 3. Glossary
    banner("3. GLOSSARY INCONSISTENCIES")
    total_glos = sum(len(v) for v in glossary_hits.values())
    print(f"  Total entries flagged: {total_glos:,}")
    for term, hits in glossary_hits.items():
        bad_list = ", ".join(f"'{b}'" for b in GLOSSARY_BAD[term])
        print(f"    {term:12s} (bad: {bad_list}): {len(hits):,}")
    if total_glos:
        print("\n  Sample (up to 3 per term):")
        for term, hits in glossary_hits.items():
            if not hits:
                continue
            print(f"\n    --- {term} ---")
            for fp, i, field, bad, ov, tv in hits[:3]:
                short_fp = fp.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                print(f"    [{short_fp}#{i}.{field}]  found: '{bad}'")
                print(f"      EN: {short(ov)!r}")
                print(f"      HE: {short(tv)!r}")

    # ── Final ───────────────────────────────────────────────────────────
    banner("LQA SUMMARY")
    print(f"  Inspected:                {inspected:,}")
    print(f"  UI overflow flags:        {len(overflow_hits):,}")
    print(f"  Punctuation mismatches:   {total_punct:,}")
    print(f"  Glossary inconsistencies: {total_glos:,}")
    print()


if __name__ == "__main__":
    main()
