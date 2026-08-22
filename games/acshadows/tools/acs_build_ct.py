#!/usr/bin/env python3
"""
acs_build_ct.py — merge the per-forge AC Shadows English oasis dumps into one
normalized community-translation strings file (the contract consumed by
universal/community_translate.py import ac-shadows <out>).

Merge order = boot -> patch_01 -> patch_02 (later patch wins per lineID, since
a title-update carries the corrected/latest English source). Skips empty /
whitespace-only / pure-control entries.

    python acs_build_ct.py <out.json> <dump1.json> [<dump2.json> ...]
"""
import sys
import json
import re

# keep real text; drop entries that are only whitespace or only [tag]/{var}/control
_TOKEN = re.compile(r"\[\[?[^\]]*\]?\]|\{[^}]*\}|<[^>]*>|[\s‎‏‪-‮]")


def _is_empty(s):
    return not _TOKEN.sub("", s).strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out_path = sys.argv[1]
    merged = {}
    for p in sys.argv[2:]:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except FileNotFoundError:
            print(f"  WARN: {p} missing, skipped")
            continue
        before = len(merged)
        merged.update(d)            # dict update = later file wins per key
        print(f"  {p}: {len(d)} strings (merged total {len(merged)}, +{len(merged)-before} new keys)")
    rows = []
    skipped = 0
    for i, (lid, txt) in enumerate(sorted(merged.items(), key=lambda kv: int(kv[0]))):
        if not isinstance(txt, str) or _is_empty(txt):
            skipped += 1
            continue
        rows.append({
            "string_key": str(lid),
            "source_en": txt,
            "current_he": "",
            "context": "dialogue",
            "section": "dialogue",
            "order_index": i,
        })
    json.dump(rows, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE: {len(rows)} rows ({skipped} empty/markup-only skipped) -> {out_path}")


if __name__ == "__main__":
    main()
