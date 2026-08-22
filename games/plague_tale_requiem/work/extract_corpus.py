#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_corpus.py — dump the English source corpus + a counting report.

Outputs (into games/plague_tale_requiem/extract/, gitignored — derived game data):
  * en.json            {key: english_value}   (the translation SOURCE, 20,661 keys)
  * ct_strings.json    community-pool import format:
                       [{string_key, source_en, current_he:"", context, section, order_index}]
  * report.txt         UI-vs-subtitle counts + token stats.

The English source is tt01.pc; keys are shared with every language so Hebrew maps
back 1:1 by key. Nothing here writes a game file.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_text as T          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")


def main():
    src = T.lang_path(T.SOURCE_ID)
    if not os.path.exists(src):
        print(f"[error] source not found: {src}")
        sys.exit(1)
    rows = T.parse(src)
    os.makedirs(OUT_DIR, exist_ok=True)

    en = {r.key: r.value for r in rows}
    json.dump(en, open(os.path.join(OUT_DIR, "en.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    ct = [{
        "string_key": r.key,
        "source_en": r.value,
        "current_he": "",
        "context": r.key,
        "section": T.category(r.key),
        "order_index": r.idx,
    } for r in rows]
    json.dump(ct, open(os.path.join(OUT_DIR, "ct_strings.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    # report
    cat = Counter(T.category(r.key) for r in rows)
    tok = Counter(re.findall(r"\{[^}]*\}", " ".join(r.value for r in rows)))
    pipe_rows = sum(1 for r in rows if "|" in r.value)
    lens = [len(r.value) for r in rows]
    lines = [
        "A Plague Tale: Requiem — corpus report",
        f"total strings: {len(rows)}",
        f"  UI:        {cat['ui']}",
        f"  subtitles: {cat['subtitle']}",
        f"  credits:   {cat['credit']}",
        f"rows with a | line-break: {pipe_rows}",
        f"max value length (chars): {max(lens)}",
        f"distinct {{STR_}} tokens: {len(tok)}",
        "top tokens: " + ", ".join(f"{t}({c})" for t, c in tok.most_common(10)),
    ]
    report = "\n".join(lines)
    open(os.path.join(OUT_DIR, "report.txt"), "w", encoding="utf-8").write(report + "\n")
    print(report)
    print(f"\nwrote: {os.path.abspath(OUT_DIR)}/{{en.json, ct_strings.json, report.txt}}")


if __name__ == "__main__":
    main()
