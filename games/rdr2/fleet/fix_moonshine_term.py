#!/usr/bin/env python3
"""fix_moonshine_term.py — one canonical Hebrew for RDR Online's MOONSHINE role.

MEASURED, not chosen: across the two banks the term ships in FIVE different forms —
`מונשיין` (62) · `מון-שיין` (61) · a literal `ירח` calque (53) · `מון שיין` · `משקה הירח` —
so the same role reads differently from one screen to the next.

🔴 THE CALQUE IS THE REAL DEFECT. "Moonshine" is not the moon: the fleet produced
`מבשלי הירח` ("moon brewers"), `בקבוק הירח` ("moon bottle"), `בקתת הירח`, `לבן ירח`, and — the
one that gives it away — **`ייצור הירחון` = "MAGAZINE production"** for "Moonshine production
is complete." Every single `ירח` occurrence on a moonshine line was checked and every one is
this calque; there is no line where the moon is genuinely meant.

CHOSEN FORM: **`מונשיין`**, solid. It is already the most common spelling in the bank, a
compound loanword is written solid in Hebrew, and the alternative differs only by a hyphen.
(The DRINK itself keeps `משקה חריף` where the shipped bank already uses it — this pass only
touches the calque and the spelling split, never a correct translation.)

ENGLISH-GUARDED: applied only to a line whose English source actually says moonshine, so
`ירח` keeps its real meaning everywhere else. Prefix-aware — Hebrew glues ו/ה/ב/ל/מ/ש/כ.

    python fix_moonshine_term.py            # report
    python fix_moonshine_term.py --apply    # write (backs the bank up first)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = [("hebrew_missing.json", "corpus_missing.json"),
           ("hebrew.json", "corpus.json")]

EN_GUARD = re.compile(r"moonshin", re.I)
CANON = "מונשיין"
_PREFIX = "והבלמשכ"


def _rx(w: str) -> re.Pattern:
    return re.compile(rf"(?<![א-ת])([{_PREFIX}]?){re.escape(w)}(?![א-ת])")


# ORDER MATTERS: the longest / most specific phrase first, so `הירחון` is never mangled into
# `המונשייןון` by the bare `ירח` rule that follows it.
RULES: list[tuple[re.Pattern, str]] = [
    # the prefix group must be part of the PHRASE rules too: `במשקה הירח` starts with an
    # attached ב, so a lookbehind that forbids any Hebrew letter never fires and the bare
    # `ירח` rule below picks it up instead, yielding the redundant `במשקה המונשיין`.
    (re.compile(r"(?<![א-ת])([" + _PREFIX + r"]?)משקאות\s+הירח(?![א-ת])"), CANON),
    (re.compile(r"(?<![א-ת])([" + _PREFIX + r"]?)משקה\s+ה?ירח(?![א-ת])"), CANON),
    (re.compile(r"(?<![א-ת])לבן\s+ירח(?![א-ת])"), CANON),
    (_rx("ירחון"), CANON),
    (_rx("ירח"), CANON),
    (re.compile(r"(?<![א-ת])([" + _PREFIX + r"]?)מון[-\s]שיין(?![א-ת])"), CANON),
]


def en_of(v) -> str:
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return str(v or "").strip()


def fix(he: str) -> str:
    for rx, rep in RULES:
        he = rx.sub(lambda m: (m.group(1) if m.re.groups else "") + rep, he)
    return he


def main() -> None:
    apply = "--apply" in sys.argv
    grand = 0
    for bank_name, corpus_name in TARGETS:
        bank_p = os.path.join(HERE, bank_name)
        corpus_p = os.path.join(HERE, corpus_name)
        if not (os.path.exists(bank_p) and os.path.exists(corpus_p)):
            continue
        bank = json.load(open(bank_p, encoding="utf-8"))
        corpus = json.load(open(corpus_p, encoding="utf-8"))
        changed = {}
        for k, he in bank.items():
            if not isinstance(he, str) or not he:
                continue
            if not EN_GUARD.search(en_of(corpus.get(k))):
                continue
            new = fix(he)
            if new != he:
                changed[k] = new
        print(f"{bank_name}: {len(changed):,} lines to fix (of {len(bank):,})")
        for k in list(changed)[:4]:
            print(f"   -  {bank[k][:76]}")
            print(f"   +  {changed[k][:76]}")
        grand += len(changed)
        if changed and apply:
            ts = time.strftime("%Y%m%d_%H%M%S")
            shutil.copy2(bank_p, f"{bank_p}.bak.moonshine.{ts}")
            bank.update(changed)
            tmp = bank_p + ".tmp"
            json.dump(bank, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, bank_p)
            print(f"   applied · backup {bank_name}.bak.moonshine.{ts}")
    if grand and not apply:
        print("\n(report only — pass --apply to write)")


if __name__ == "__main__":
    main()
