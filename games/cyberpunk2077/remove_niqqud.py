"""
remove_niqqud.py
================
Strip Hebrew Niqqud (vowel points + cantillation marks) from every
translated string we hold. CDPR's engine's RTL shaper choked on the
combining marks the LLM occasionally emitted (e.g.
'ל .םֹולָׁשְל ריִעָה זַּכְרֶמ' renders as broken glyphs).

Cleans the three sinks `translate_queue_fast.py` writes to:
  • lm_output.json
  • tm_cache.json
  • localization_translated.json (in BOTH onscreens sections, recursively)

Codepoint range removed: U+0591 .. U+05C7  (Hebrew cantillation + niqqud +
punctuation marks). Plain Hebrew letters (U+05D0..U+05EA) are kept untouched.

Idempotent — safe to re-run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
RESOURCES   = os.path.join(PROJECT, "source", "resources")

TARGETS = [
    os.path.join(SCRIPTS_DIR, "lm_output.json"),
    os.path.join(RESOURCES,  "tm_cache.json"),
    os.path.join(RESOURCES,  "localization_translated.json"),
]

NIQQUD_RE = re.compile(r"[֑-ׇ]")


def strip_niqqud(s):
    if not isinstance(s, str):
        return s, 0
    cleaned = NIQQUD_RE.sub("", s)
    return cleaned, len(s) - len(cleaned)


def scrub(obj, counters):
    """Recursively strip Niqqud from any string inside obj. Returns the
    rebuilt object (lists/dicts are rebuilt; strings are replaced)."""
    if isinstance(obj, str):
        cleaned, removed = strip_niqqud(obj)
        if removed:
            counters["chars_removed"] += removed
            counters["strings_changed"] += 1
        return cleaned
    if isinstance(obj, list):
        return [scrub(x, counters) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v, counters) for k, v in obj.items()}
    return obj


def main():
    grand_total_changed = 0
    grand_total_chars = 0

    for path in TARGETS:
        print(f"\n=== {path} ===")
        if not os.path.exists(path):
            print("  (missing — skipped)")
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        counters = {"strings_changed": 0, "chars_removed": 0}
        scrubbed = scrub(data, counters)

        if counters["chars_removed"] == 0:
            print("  no Niqqud found — nothing to write")
            continue

        bak = f"{path}.bak.niqqud.{int(time.time())}"
        shutil.copy2(path, bak)
        print(f"  backup -> {bak}")

        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(scrubbed, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

        print(f"  stripped {counters['chars_removed']:,} niqqud chars "
              f"across {counters['strings_changed']:,} strings")
        grand_total_changed += counters["strings_changed"]
        grand_total_chars += counters["chars_removed"]

    print()
    print("=" * 60)
    print(f"TOTAL: {grand_total_chars:,} chars removed "
          f"across {grand_total_changed:,} strings in {len(TARGETS)} files")
    print("=" * 60)


if __name__ == "__main__":
    main()
