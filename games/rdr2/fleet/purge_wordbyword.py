#!/usr/bin/env python3
"""Purge WORD-BY-WORD damaged Hebrew from the missing-lines banks so the fleet redoes it.

The defect: a too-small model translates token-for-token and leaves Hebrew PREFIX letters
standing as separate words — `A pelt from the Legendary Onyx Wolf` ->
`אחד עור מ ה מפורסם אוניקס זאב`. It passes every structural guard (tokens intact, Hebrew
present, no niqqud, not a copy of the English), so only a linguistic check catches it.

Signature: a single Hebrew prefix letter (מ ה ל ו ב ש כ) standing as its OWN word and
followed by a Hebrew word. Real Hebrew always glues those to the next word.
⚠️ Deliberately does NOT flag the legitimate forms where the prefix attaches to something
that is not a Hebrew letter: `ב~COLOR_MP_OBJECTIVE~...`, `ל-RDO$`, `ל-Hosea`, `ה-XP`.

Removing a key from the bank AND from the shard's own out_*.json is what makes the worker
re-serve it; deleting it from only one of the two leaves it to be merged straight back.

Usage:  purge_wordbyword.py            (report)
        purge_wordbyword.py --apply    (write; backs both files up first)
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew_missing.json")
BANKS_DIR = os.path.join(HERE, "banks_missing")

BAD = re.compile(r'(?:^|(?<=[\s(]))([מהלובשכ])\s+(?=[֐-׿])')


def damaged(v: str) -> bool:
    return isinstance(v, str) and bool(BAD.search(v))


def main() -> None:
    apply = "--apply" in sys.argv
    bank = json.load(open(BANK, encoding="utf-8"))
    bad = sorted(k for k, v in bank.items() if damaged(v))
    print(f"bank {len(bank):,} · word-by-word damaged: {len(bad):,}")
    for k in bad[:8]:
        print(f"    {bank[k][:88]}")
    if not bad:
        return
    keys = os.path.join(HERE, "purged_keys.json")
    json.dump(bad, open(keys, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"key list -> {os.path.basename(keys)}")
    if not apply:
        print("\n(report only — pass --apply to write)")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BANK, f"{BANK}.bak.purge.{ts}")
    for k in bad:
        bank.pop(k, None)
    tmp = BANK + ".tmp"
    json.dump(bank, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BANK)
    print(f"bank -> {len(bank):,}")

    bs = set(bad)
    for p in sorted(glob.glob(os.path.join(BANKS_DIR, "out_*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        n = sum(1 for k in list(d) if k in bs and d.pop(k, None) is not None)
        if n:
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  {os.path.basename(p)}: -{n}")


if __name__ == "__main__":
    main()
