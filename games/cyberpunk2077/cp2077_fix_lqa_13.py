"""
cp2077_fix_lqa_13.py
====================
Manual fix for the 13 entries flagged by the LQA report:
  - 4 UI Overflow (including the two 'אמ' infinite-loop corruptions)
  - 9 Punctuation Mismatch (... ? ! lost in translation)

Applies hand-crafted Hebrew translations directly to localization_translated.json
with atomic save. Only touches femaleVariant of the 13 listed entries.
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


BASE = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources"
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")

# (filepath, index, field, hebrew_translation, category)
FIXES = [
    # ── UI Overflow ───────────────────────────────────────────────────────
    (
        "onscreens/onscreens.json", 21801, "femaleVariant",
        "שיחה מארכיון: לאסלו נג'י ואלנה \"פאמפקין\" אספוזיטו",
        "OVERFLOW",
    ),
    (
        "onscreens/onscreens.json", 21802, "femaleVariant",
        "\x07לאסלו: בדרך אלייך עכשיו פאמפקין\\nלאסלו: בבקשה אל תכעסי\\nפאמפקין: אני לא",
        "OVERFLOW",
    ),
    (
        "onscreens/onscreens_final.json", 13555, "femaleVariant",
        "מנהל QA",
        "OVERFLOW",
    ),
    (
        "onscreens/onscreens_final.json", 19323, "femaleVariant",
        "האקינג מהיר: שליטה במצלמה",
        "OVERFLOW",
    ),

    # ── Punctuation Mismatch ─────────────────────────────────────────────
    (
        "onscreens/onscreens.json", 8243, "femaleVariant",
        "גוסטבו אורטה\\n\"ללכת ולחיות, או להישאר ולמות?\"",
        "PUNCT-?",
    ),
    (
        "onscreens/onscreens.json", 19133, "femaleVariant",
        "אימון עושה מושלם!",
        "PUNCT-!",
    ),
    (
        "onscreens/onscreens.json", 37815, "femaleVariant",
        "טוב, אה, עכשיו. נחכה לך. נתראה בקרוב!",
        "PUNCT-!",
    ),
    (
        "onscreens/onscreens.json", 38496, "femaleVariant",
        "היי רנדי! :P מה שלומו? משתפר, אני מקווה?",
        "PUNCT-?",
    ),
    (
        "onscreens/onscreens.json", 39035, "femaleVariant",
        "טוען קובץ שמירה.\\nנא להמתין...",
        "PUNCT-...",
    ),
    (
        "onscreens/onscreens.json", 43166, "femaleVariant",
        "מה לעזאזל אתה חושב שאני עושה עכשיו?!?",
        "PUNCT-?",
    ),
    (
        "onscreens/onscreens.json", 43298, "femaleVariant",
        "אני כן. ואודיע לך כשאהיה פנוי שוב, מבטיח!",
        "PUNCT-!",
    ),
    (
        "onscreens/onscreens.json", 43354, "femaleVariant",
        "סטודיו פרחים בלאק דליה\\n\\nבחר זר!",
        "PUNCT-!",
    ),
    (
        "onscreens/onscreens_final.json", 8243, "femaleVariant",
        "גוסטבו אורטה\\n\"ללכת ולחיות, או להישאר ולמות?\"",
        "PUNCT-?",
    ),
]


def atomic_save(translated):
    tmp = TRANSLATED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED_FILE)


def main():
    print("=" * 72)
    print("  CYBERPUNK 2077 — Manual Fix: 13 LQA Entries")
    print("=" * 72)
    print(f"  File: {TRANSLATED_FILE}\n")

    print("  Loading translated JSON...")
    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)
    print(f"    [OK] {len(translated):,} files loaded\n")

    applied = 0
    missing = 0

    print("  Applying fixes:\n")
    for fp, idx, field, new_he, cat in FIXES:
        if fp not in translated:
            print(f"    [MISS] {cat:11s}  {fp}#{idx}.{field}  — file not in translated JSON")
            missing += 1
            continue
        entries = translated[fp]
        if idx >= len(entries):
            print(f"    [MISS] {cat:11s}  {fp}#{idx}.{field}  — index out of range ({len(entries)})")
            missing += 1
            continue
        old = entries[idx].get(field, "")
        entries[idx][field] = new_he
        applied += 1
        print(f"    [FIX]  {cat:11s}  {fp}#{idx}.{field}")
        print(f"           OLD: {old[:60]!r}")
        print(f"           NEW: {new_he[:60]!r}")

    print(f"\n  Saving (atomic write)...")
    atomic_save(translated)
    print(f"  [OK] Saved.\n")

    print("=" * 72)
    print(f"  SUMMARY:  {applied} applied, {missing} missed (out of {len(FIXES)} total)")
    print("=" * 72)
    print()
    print("  All 13 fixed Hebrew translations:")
    print()
    for fp, idx, field, new_he, cat in FIXES:
        short_fp = fp.rsplit("/", 1)[-1]
        print(f"    [{cat:10s}] {short_fp}#{idx}")
        print(f"      → {new_he}")
        print()


if __name__ == "__main__":
    main()
