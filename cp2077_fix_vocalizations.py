"""
cp2077_fix_vocalizations.py
===========================
Deterministic cleanup pass for non-lexical vocalizations.

The QA sweep's LM translator cannot "translate" interjections like "Hmm..."
or "Haha." — there is nothing to translate, so it leaves them in Latin and
they read as an English leak in the Hebrew subtitles. This pass transliterates
that closed set of vocalizations into Hebrew with a fixed map (no LM, 100%
deterministic) and writes them straight into localization_translated.json.

Only an entry whose femaleVariant is EXACTLY one of the known English
vocalization forms is touched — so a real translated line can never be hit.

Run: python cp2077_fix_vocalizations.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cp2077_qa_defects as qa

RES = os.path.join(_HERE, "תרגום_משחקים", "source", "resources")
TRANSLATED = qa.TRANSLATED_FILE

# Closed set of vocalization forms seen in the audit, mapped to a natural
# Hebrew rendering. Hum -> המממ, laugh -> חה חה — trailing punctuation kept.
VOCAL_MAP = {
    "Hmm...":                 "המממ...",
    "Hmm…":              "המממ…",
    "Hmm.":                   "המממ.",
    "Hmmm...":                "המממ...",
    "Hmmm…":             "המממ…",
    "Hmmm.":                  "המממ.",
    "Hmmmm...":               "המממ...",
    "Hm...":                  "המ...",
    "hmmm…":             "המממ…",
    "Hmmm-hmmm, hmmm-hmmm…": "המממ־המממ, המממ־המממ…",
    "Haha.":                  "חה חה.",
    "Haha!":                  "חה חה!",
    "Haha…":             "חה חה…",
    "Heh…":              "חה…",
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)

    fixed = 0
    by_form: dict[str, int] = {}
    for section, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            fv = e.get("femaleVariant")
            heb = VOCAL_MAP.get(fv) if isinstance(fv, str) else None
            if heb is None:
                continue
            if not dry:
                e["femaleVariant"] = heb
            by_form[fv] = by_form.get(fv, 0) + 1
            fixed += 1

    print(f"{'[dry-run] ' if dry else ''}vocalizations transliterated: {fixed}")
    for form, n in sorted(by_form.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}x  {form!r} -> {VOCAL_MAP[form]!r}")

    if fixed and not dry:
        qa.atomic_write_json(TRANSLATED, translated)
        print(f"\nwrote {TRANSLATED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
