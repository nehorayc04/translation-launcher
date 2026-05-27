"""
cp2077_fix_corrupted_markup.py
==============================
Repairs entries whose <kiroshi>/<mothertongue> markup was destroyed by an
old non-markup-aware translation pass — the tag itself got transliterated
("<kiroshi" -> "קירושי"), the verbatim foreign o/m attribute got translated,
and the structure collapsed into garbage.

Detection: secondaryKey carries valid markup but femaleVariant no longer does
AND femaleVariant shows corruption (attribute remnants / a transliterated tag
name / a stray foreign script). The clean type — femaleVariant is a fluent
Hebrew sentence with merely the wrapper dropped — is NOT touched.

Repair: rebuild femaleVariant from the English skeleton in secondaryKey via
the markup translator's slot model — translate only the TR slots, copy the
foreign o/m attributes verbatim. If the LM result is not clean, fall back to
the English skeleton (valid markup, untranslated — never garbage).

Run: python cp2077_fix_corrupted_markup.py [--dry-run]
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

import audit_translations as au
import cp2077_qa_defects as qa
import cp2077_markup_translate as mk
import patch_615_flagged as p615

TRANSLATED = qa.TRANSLATED_FILE


def is_corrupt(fv: str) -> bool:
    """femaleVariant shows markup-corruption garbage (not clean Hebrew)."""
    if not fv:
        return False
    return ('="' in fv or 'קירושי' in fv or 'קירוש' in fv
            or fv[:8].count('=') >= 1 and ('ל=' in fv or 'l=' in fv)
            or bool(au.detect_scripts(fv)))


def rebuild(english: str):
    """Rebuild a clean Hebrew markup value from the English skeleton.
    Returns the rebuilt value, or the English skeleton as a safe fallback."""
    if not english or not qa.is_markup(english):
        return None
    slots = mk.parse_slots(english)
    if slots is None:
        return english                       # truncated source -> valid EN skeleton
    tr_texts = [t for k, t in slots if k == "TR"]
    if not tr_texts:
        return english
    hebrew = mk.translate_pieces(tr_texts)
    rebuilt, hi = [], 0
    for kind, text in slots:
        if kind == "TR":
            he = hebrew[hi] if hi < len(hebrew) else ""
            hi += 1
            rebuilt.append(("TR", he if mk.valid_piece(text, he) else text))
        else:
            rebuilt.append((kind, text))
    out = mk.reassemble(rebuilt)
    return out if qa.value_is_clean(out) else english


def main() -> int:
    dry = "--dry-run" in sys.argv
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)

    targets = []
    for section, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            sk = e.get("secondaryKey") or ""
            fv = e.get("femaleVariant") or ""
            if qa.is_markup(sk) and not qa.is_markup(fv) and is_corrupt(fv):
                targets.append((section, e))

    print(f"corrupted-markup entries: {len(targets)}")
    if dry:
        for section, e in targets:
            print(f"  [{section.split('/')[-1][:30]}:{e.get('primaryKey')}]")
            print(f"     now: {(e.get('femaleVariant') or '')[:70]!r}")
            print(f"     EN : {(e.get('secondaryKey') or '')[:70]!r}")
        return 0

    from openai import OpenAI
    client = OpenAI(base_url=p615.LM_URL, api_key="lm-studio", timeout=600)
    mk.lm_client = client

    fixed = restored = 0
    touched = set()
    for section, e in targets:
        english = e.get("secondaryKey") or ""
        out = rebuild(english)
        if not out:
            continue
        before = e.get("femaleVariant") or ""
        e["femaleVariant"] = out
        touched.add(section)
        if qa.value_is_clean(out):
            fixed += 1
            print(f"  [OK]  {section.split('/')[-1][:26]}:{e.get('primaryKey')}  "
                  f"'{before[:34]}' -> '{out[:46]}'")
        else:
            restored += 1
            print(f"  [EN]  {section.split('/')[-1][:26]}:{e.get('primaryKey')}  "
                  f"restored valid English skeleton")

    if touched:
        qa.atomic_write_json(TRANSLATED, translated)
        with open(os.path.join(_HERE, "corrupted_markup_sections.txt"),
                  "w", encoding="utf-8") as f:
            f.write(",".join(sorted(touched)))
    print(f"\nfixed (clean Hebrew): {fixed}   restored (EN skeleton): {restored}")
    print(f"touched {len(touched)} sections -> corrupted_markup_sections.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
