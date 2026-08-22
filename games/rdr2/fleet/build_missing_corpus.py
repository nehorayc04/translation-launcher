#!/usr/bin/env python3
"""Corpus for the RDR2 lines the old translation never had.

The original corpus came from a public English dump that covered 93.9% of the keys, so the
rest shipped in English -- which is what the in-game screenshots show. Unpacking the
archives gave us the game's OWN `.yldb` databases: the complete key set AND all 12
professional translations, so every missing line arrives with a full New-Era panel instead
of English alone.

Ordered by VISIBILITY (UI/menus before ambient dialogue) so a partial run still covers what
players actually read.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_TEXT = os.path.join(HERE, "..", "extract", "game_text")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "gtav", "work")))
from gtav_gxt2 import joaat  # noqa: E402

# The New-Era panel, strongest first: ru/pl mark speaker AND addressee gender, de carries
# register, fr/es/it referent gender.
PANEL = ["russian", "polish", "german", "french", "spanish", "italian", "brazilian"]

TOK = re.compile(r"~[^~]*~")


def real_text(t: str) -> bool:
    return len(re.findall(r"[A-Za-z]{2,}", TOK.sub("", t))) >= 1


def main() -> None:
    en = json.load(open(os.path.join(GAME_TEXT, "american.json"), encoding="utf-8"))
    heb = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))

    # our existing keys, normalised to the game's hash space
    done = set()
    for k in heb:
        done.add(int(k, 16) if (k.startswith("0x") and len(k) == 10) else joaat(k))

    panel = {}
    for lang in PANEL:
        p = os.path.join(GAME_TEXT, lang + ".json")
        if os.path.exists(p):
            panel[lang] = json.load(open(p, encoding="utf-8"))

    rows = {}
    for k, txt in en.items():
        if int(k, 16) in done or not real_text(txt):
            continue
        refs = {}
        for lang, m in panel.items():
            v = m.get(k)
            if v and v != txt:
                refs[lang[:2]] = v
        # dialogue carries the ~z~ speech tag; everything else is UI/menu/mission text
        rows[k] = {"en": txt, "refs": refs,
                   "sec": "כתוביות ודיאלוג" if txt.startswith("~z~") else "ממשק ומשימות"}

    # visibility order: UI first, then short dialogue, then long
    order = sorted(rows, key=lambda k: (rows[k]["sec"] != "ממשק ומשימות", len(rows[k]["en"])))
    out = {k: rows[k] for k in order}

    with open(os.path.join(HERE, "corpus_missing.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)

    ui = sum(1 for v in out.values() if v["sec"] == "ממשק ומשימות")
    withref = sum(1 for v in out.values() if v["refs"])
    avg = sum(len(v["refs"]) for v in out.values()) / max(len(out), 1)
    print(f"missing lines : {len(out):,}")
    print(f"  UI/missions : {ui:,}")
    print(f"  dialogue    : {len(out) - ui:,}")
    print(f"  with a panel: {withref:,} ({100.0 * withref / max(len(out),1):.1f}%), avg {avg:.1f} languages")


if __name__ == "__main__":
    main()
