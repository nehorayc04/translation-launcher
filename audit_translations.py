"""Quick quality audit for localization_translated.json.

Scans every femaleVariant / maleVariant in every section, flagging entries
whose Hebrew translation leaked another script (Cyrillic, Arabic, Thai,
Greek, CJK, ...) or kept Niqqud vowel-points the SYSTEM_PROMPT bans.

Output:
  console summary (per-script counts, overall bad rate)
  audit_translations_report.txt  — full per-entry detail for follow-up
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
TRANSLATED  = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources",
                           "localization_translated.json")
REPORT      = os.path.join(SCRIPTS_DIR, "audit_translations_report.txt")

# Ranges we explicitly do NOT want to see in a Hebrew translation. Hebrew
# itself is U+0590-U+05FF and we allow the basic-Latin/ASCII range plus
# common punctuation. Anything matching below is a quality flag.
SCRIPT_RANGES = {
    "cyrillic":   (0x0400, 0x04FF),    # Russian, Ukrainian, etc.
    "cyrillic_supplement": (0x0500, 0x052F),
    "arabic":     (0x0600, 0x06FF),
    "arabic_supplement": (0x0750, 0x077F),
    "arabic_extended_a": (0x08A0, 0x08FF),
    "thai":       (0x0E00, 0x0E7F),
    "greek":      (0x0370, 0x03FF),
    "armenian":   (0x0530, 0x058F),
    "devanagari": (0x0900, 0x097F),
    "han_cjk":    (0x4E00, 0x9FFF),
    "hiragana":   (0x3040, 0x309F),
    "katakana":   (0x30A0, 0x30FF),
    "hangul":     (0xAC00, 0xD7AF),
    "ethiopic":   (0x1200, 0x137F),
    "georgian":   (0x10A0, 0x10FF),
}

NIQQUD_RANGE = (0x0591, 0x05C7)
HEBREW_RANGE = (0x0590, 0x05FF)


_TAG_RE = re.compile(r"<[^<>]*>|\{[^{}]*\}")


def detect_scripts(text: str) -> set[str]:
    # Strip CR2W passthrough markup first — `<kiroshi l="jpn" o="…"/>` audio
    # cues, `<Rich color="…">` formatting, `{VALUE,number,…}` placeholders.
    # Foreign chars *inside* these tags are legitimate game data (the JP
    # audio transcript, attribute names), not translation contamination.
    stripped = _TAG_RE.sub(" ", text)
    hits: set[str] = set()
    for ch in stripped:
        cp = ord(ch)
        for name, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                hits.add(name)
                break
        if NIQQUD_RANGE[0] <= cp <= NIQQUD_RANGE[1]:
            hits.add("niqqud")
    return hits


def has_hebrew(text: str) -> bool:
    return any(HEBREW_RANGE[0] <= ord(c) <= HEBREW_RANGE[1] for c in text)


def main() -> int:
    if not os.path.exists(TRANSLATED):
        sys.exit(f"missing {TRANSLATED}")

    with open(TRANSLATED, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_entries     = 0
    total_with_hebrew = 0
    bad_entries: list[dict] = []
    per_script_count: dict[str, int] = defaultdict(int)

    for section, rows in data.items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            for field in ("femaleVariant", "maleVariant"):
                val = entry.get(field) or ""
                if not val:
                    continue
                total_entries += 1
                if has_hebrew(val):
                    total_with_hebrew += 1
                hits = detect_scripts(val)
                if hits:
                    for h in hits:
                        per_script_count[h] += 1
                    bad_entries.append({
                        "section":  section,
                        "pk":       entry.get("primaryKey"),
                        "skey":     entry.get("secondaryKey"),
                        "field":    field,
                        "scripts":  sorted(hits),
                        "value":    val,
                    })

    print(f"Scanned: {total_entries:,} variants across {len(data)} sections")
    print(f"  with Hebrew chars: {total_with_hebrew:,}")
    print(f"  flagged for foreign-script / niqqud contamination: {len(bad_entries):,}")
    if total_entries:
        print(f"  bad rate: {len(bad_entries) / total_entries * 100:.2f}%")

    print("\nPer-script tallies:")
    for s, c in sorted(per_script_count.items(), key=lambda kv: -kv[1]):
        print(f"  {s:<22} {c:>6,}")

    # Detailed report — first 200 of each script for sampling, plus full list.
    with open(REPORT, "w", encoding="utf-8") as fout:
        fout.write(f"# Translation quality audit\n")
        fout.write(f"# Total variants scanned: {total_entries:,}\n")
        fout.write(f"# Flagged entries:        {len(bad_entries):,}\n")
        fout.write(f"# Per-script tallies:\n")
        for s, c in sorted(per_script_count.items(), key=lambda kv: -kv[1]):
            fout.write(f"#   {s:<22} {c:>6,}\n")
        fout.write("\n")
        # Group by script for easier triage
        by_script: dict[str, list[dict]] = defaultdict(list)
        for b in bad_entries:
            for s in b["scripts"]:
                by_script[s].append(b)
        for script in sorted(by_script.keys(), key=lambda s: -len(by_script[s])):
            entries = by_script[script]
            fout.write(f"\n{'='*60}\n")
            fout.write(f"# {script.upper()} — {len(entries):,} entries\n")
            fout.write(f"{'='*60}\n")
            for e in entries[:500]:                # cap per-script dump
                fout.write(
                    f"  {e['section']} pk={e['pk']} skey={e['skey']!s} "
                    f"field={e['field']}\n"
                    f"    {e['value']}\n\n"
                )
            if len(entries) > 500:
                fout.write(f"  ... and {len(entries) - 500:,} more\n")

    print(f"\nFull report: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
