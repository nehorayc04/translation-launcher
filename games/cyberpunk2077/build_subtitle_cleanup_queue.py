"""
build_subtitle_cleanup_queue.py
===============================
Builds cleanup_queue.json containing every still-untranslated SUBTITLE
entry, so translate_cleanup_all.py can sweep them to Hebrew.

"Untranslated" = a subtitle-section femaleVariant that has no Hebrew and is
either:
  - a multi-word English string  (a real dialogue line left in English), or
  - empty                        (English source pulled from localization_export.json)

Single-word English values are skipped — those are almost always proper
nouns / codes (NCPD, Arasaka, V, …) that are intentionally left as-is.

Outputs:
  cleanup_queue.json              — the queue translate_cleanup_all.py reads
  subtitle_cleanup_sections.txt   — comma-joined section list for the re-bake
                                    step (rebuild_subtitles_and_pack.py
                                    --sections-file)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
RES         = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources")
TRANSLATED  = os.path.join(RES, "localization_translated.json")
EXPORT      = os.path.join(RES, "localization_export.json")
QUEUE       = os.path.join(SCRIPTS_DIR, "cleanup_queue.json")
SECTIONS_TXT = os.path.join(SCRIPTS_DIR, "subtitle_cleanup_sections.txt")

HEB = re.compile(r"[֐-׿]")
LAT = re.compile(r"[A-Za-z]")


def main() -> int:
    for p in (TRANSLATED, EXPORT):
        if not os.path.exists(p):
            print(f"FATAL: missing {p}")
            return 1

    print(f"[*] Loading {TRANSLATED}")
    translated = json.load(open(TRANSLATED, encoding="utf-8"))
    print(f"[*] Loading {EXPORT}")
    export = json.load(open(EXPORT, encoding="utf-8"))

    # English index — only needed to resolve empty entries.
    eng_idx: dict[tuple[str, str], dict] = {}
    for sec, rows in export.items():
        if sec.startswith("subtitles/") and isinstance(rows, list):
            for e in rows:
                if isinstance(e, dict) and e.get("primaryKey") is not None:
                    eng_idx[(sec, str(e["primaryKey"]))] = e

    queue: list[dict] = []
    skipped_proper_noun = 0
    for sec, rows in translated.items():
        if not sec.startswith("subtitles/") or not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            val = (e.get("femaleVariant") or "").strip()
            pk  = e.get("primaryKey")

            if HEB.search(val):
                continue                                   # already Hebrew

            if val and LAT.search(val):
                if len(val.split()) < 2:
                    skipped_proper_noun += 1                # proper noun / code
                    continue
                english = val                              # untranslated line
            elif not val:
                eng_entry = eng_idx.get((sec, str(pk)))
                english = ((eng_entry.get("femaleVariant")
                            or eng_entry.get("maleVariant") or "")
                           if eng_entry else "")
            else:
                continue                                   # not English, not empty

            if not english.strip():
                continue

            queue.append({
                "section":        sec,
                "primaryKey":     pk,
                "secondaryKey":   e.get("secondaryKey") or "",
                "english_female": english,
                "english_male":   "",
            })

    # Back up any existing queue before overwriting.
    if os.path.exists(QUEUE):
        bak = QUEUE + ".bak." + time.strftime("%Y%m%d_%H%M%S")
        os.replace(QUEUE, bak)
        print(f"[*] Backed up existing queue -> {os.path.basename(bak)}")

    payload = {
        "_metadata": {
            "built":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "purpose": "untranslated subtitle entries",
            "count":   len(queue),
        },
        "queue": queue,
    }
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    sections = sorted({it["section"] for it in queue})
    with open(SECTIONS_TXT, "w", encoding="utf-8") as f:
        f.write(",".join(sections))

    print()
    print(f"[*] queued {len(queue):,} untranslated subtitle entries")
    print(f"    ({skipped_proper_noun:,} single-word English values skipped as proper nouns)")
    print(f"[*] {len(sections):,} subtitle sections affected")
    print(f"[*] queue   -> {QUEUE}")
    print(f"[*] sections -> {SECTIONS_TXT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
