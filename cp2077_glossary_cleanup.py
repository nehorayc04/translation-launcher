"""
cp2077_glossary_cleanup.py
--------------------------
Post-run pass that fixes glossary-term inconsistencies in
localization_translated.json without going back to the LM.

For each cell where the SOURCE English contains a Cyberpunk franchise term
(Night City, Choom, Netrunner, ...) but the translation uses a non-canonical
Hebrew rendering, replace the wrong rendering with the canonical one from
the script's glossary.

Safe because:
  * Replacements only happen INSIDE cells whose English source contains the
    matching glossary term — so we never touch unrelated occurrences of
    the same Hebrew word (e.g. plain "חום" meaning "brown" elsewhere stays
    untouched).
  * Atomic save (.tmp + os.replace).
  * --dry-run prints proposed changes without writing.
  * Writes a backup copy beside the original before mutating.

Usage:
    python cp2077_glossary_cleanup.py             # apply, write backup
    python cp2077_glossary_cleanup.py --dry-run   # show planned changes only
"""

import io
import json
import os
import re
import sys
from collections import Counter

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True
    )

BASE = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources"
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
BACKUP_FILE = os.path.join(BASE, "localization_translated.before_glossary_cleanup.json")

# ── glossary ──────────────────────────────────────────────────────────────────
# For each English term: the canonical Hebrew, plus the non-canonical renderings
# we've actually observed the LM produce. Replacements only fire when the source
# contains the English term, so listing common synonyms like חבר / תאגיד here is
# safe — they only get rewritten in contexts that explicitly use Cyberpunk slang.

GLOSSARY = {
    "Night City": {
        "correct": "נייט סיטי",
        "wrong": ["Noice City", "עיר הלילה", "עיר לילה", "ניית סיטי", "נייט-סיטי"],
    },
    "Netrunner": {
        "correct": "נטראנר",
        "wrong": ["נט-ראנר", "נטרנר", "רץ רשת", "רץ-רשת", "רצי רשת", "נטרנא"],
    },
    "Ripperdoc": {
        "correct": "ריפרדוק",
        "wrong": ["ריפר-דוק", "ריפר דוק", "רופא רשע", "רופא חיתוך", "ריפר_דוק"],
    },
    "Corpo": {
        "correct": "קורפו",
        # NOTE: תאגיד is sometimes a legitimate generic translation, but in
        # Cyberpunk dialogue we want the franchise slang. The source-scoping
        # makes this safe.
        "wrong": ["קורפ", "קורפורציה", "תאגידן"],
    },
    "Choom": {
        "correct": "צ'ום",
        "wrong": ["חום", "חמוד", "צ'ומבה", "צ'ומב"],
    },
    "Choomba": {
        "correct": "צ'ום",
        "wrong": ["חומבה", "חמובה", "צ'ומבה"],
    },
    "Braindance": {
        "correct": "בריינדאנס",
        # BD stays as BD per the system prompt — don't touch "BD".
        "wrong": ["ריקוד מוח", "ריקוד מוחי", "ברייןדנס", "מחול מוח"],
    },
    "Cyberware": {
        "correct": "סייברוור",
        "wrong": ["סייבר-וור", "סייבר וור", "ציוד סייבר", "ציוד קיברנטי", "חומרת סייבר"],
    },
}


def fix_cell(en_src: str, he_trg: str) -> tuple[str, list[str]]:
    """Apply glossary fixes to one cell. Returns (new_trg, list_of_terms_fixed)."""
    if not isinstance(he_trg, str) or not he_trg:
        return he_trg, []
    if not isinstance(en_src, str) or not en_src:
        return he_trg, []

    en_lower = en_src.lower()
    fixed_terms = []
    new_trg = he_trg

    for term_en, spec in GLOSSARY.items():
        if term_en.lower() not in en_lower:
            continue
        correct = spec["correct"]
        # If translation already contains the canonical form, nothing to do.
        if correct in new_trg:
            continue
        # Try each known-wrong rendering. Use word-boundary-ish replacement so
        # we don't mangle longer words that happen to contain the substring.
        for wrong in spec["wrong"]:
            if wrong not in new_trg:
                continue
            # Hebrew has no word boundaries in regex's \b sense, so we use a
            # lookahead/behind for letter chars. This keeps "חום" from being
            # replaced inside e.g. "חומק" (which legitimately has those chars).
            pattern = r"(?<![\w֐-׿])" + re.escape(wrong) + r"(?![\w֐-׿])"
            try:
                replaced = re.sub(pattern, correct, new_trg)
            except re.error:
                replaced = new_trg.replace(wrong, correct)
            if replaced != new_trg:
                new_trg = replaced
                fixed_terms.append(f"{term_en}({wrong}->{correct})")
                break  # one wrong-form per term per cell

    return new_trg, fixed_terms


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"[*] Loading {TRANSLATED_FILE}")
    with open(TRANSLATED_FILE, encoding="utf-8") as f:
        translated = json.load(f)

    print(f"[*] Loading {ORIGINAL_FILE}")
    with open(ORIGINAL_FILE, encoding="utf-8") as f:
        original = json.load(f)

    print(f"[*] Mode: {'DRY-RUN (no writes)' if dry_run else 'APPLY (will write backup + file)'}")
    print()

    per_term_count = Counter()
    cell_count = 0
    sample_changes: list[tuple[str, str, str, list[str]]] = []

    for filepath, entries in translated.items():
        if filepath not in original:
            continue
        orig_entries = original[filepath]
        n = min(len(entries), len(orig_entries))
        for i in range(n):
            for field in ("femaleVariant", "maleVariant"):
                src = orig_entries[i].get(field, "") or ""
                trg = entries[i].get(field, "") or ""
                if not src or not trg:
                    continue
                new_trg, fixed = fix_cell(src, trg)
                if not fixed:
                    continue
                entries[i][field] = new_trg
                cell_count += 1
                for f_ in fixed:
                    per_term_count[f_.split("(")[0]] += 1
                if len(sample_changes) < 12:
                    sample_changes.append((src[:70], trg[:90], new_trg[:90], fixed))

    print(f"[*] Cells modified: {cell_count}")
    print(f"[*] Per-term counts: {dict(per_term_count) if per_term_count else 'NONE'}")
    print()

    if sample_changes:
        print("=== Sample changes ===")
        for src, before, after, fixes in sample_changes:
            print(f"  src   : {src!r}")
            print(f"  before: {before!r}")
            print(f"  after : {after!r}")
            print(f"  fixes : {', '.join(fixes)}")
            print()

    if cell_count == 0:
        print("[*] Nothing to fix. Done.")
        return

    if dry_run:
        print("[*] Dry-run complete. Re-run without --dry-run to apply.")
        return

    # Copy the pristine on-disk file as backup (don't dump the mutated in-memory dict)
    if not os.path.exists(BACKUP_FILE):
        import shutil
        shutil.copy2(TRANSLATED_FILE, BACKUP_FILE)
        print(f"[*] Backup written -> {BACKUP_FILE}  ({os.path.getsize(BACKUP_FILE):,} bytes)")
    else:
        print(f"[*] Backup already exists, skipping: {BACKUP_FILE}")

    print(f"[*] Saving cleaned file -> {TRANSLATED_FILE}")
    tmp = TRANSLATED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED_FILE)
    print(f"  size: {os.path.getsize(TRANSLATED_FILE):,} bytes")
    print()
    print("[*] Done.")


if __name__ == "__main__":
    main()
