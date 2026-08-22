#!/usr/bin/env python3
"""ENGLISH-GUARDED name/term unification for the RDR2 missing-lines bank.

`audit_consistency.py` reports every English term the fleet rendered more than one way. Most
of that report is NOISE — Hebrew inflects, so `חולצה`/`חולצת` (construct state) and
`מגפיים`/`מגפי` are both correct and must never be "fixed". What IS a defect is a PROPER NAME
spelled two ways (`הושע` vs `הוזיא`, `מייקה` vs `מיקה`) or an outright wrong word
(`Tonic` -> `שיער`, hair).

🔴 THE GUARD IS THE POINT. A blind substring replace over the corpus is how a glossary does
more damage than it fixes: `מיקה` is a mineral as well as a character, and `שיער` is a
perfectly good word everywhere except on a line whose English says "Tonic". So every swap is
applied ONLY to a line whose ENGLISH SOURCE actually contains that term — the same
english-guarded rule the Witcher 3 pre-launch audit established.

Prefix-aware: Hebrew glues ו/ה/ב/ל/מ/ש/כ to the next word, so `והוזיא` must match too. The
lookbehind keeps a longer word that merely ENDS with the wrong form from being touched.

Usage:  fix_names_guarded.py            (report)
        fix_names_guarded.py --apply    (write; backs the bank up first)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew_missing.json")
CORPUS = os.path.join(HERE, "corpus_missing.json")

# english term -> {wrong Hebrew: canonical Hebrew}
# Every entry below came from audit_consistency.py's DIVERGENT SPELLINGS report on the live
# bank — never invented. Inflection pairs from that same report (חולצה/חולצת, מגפיים/מגפי,
# עניבה/עניבת, אפודה/אפודת, מסכה/מסכת, כרכרה/כרכרת, פרווה/פרוות, מכנסיים/מכנסי) are
# DELIBERATELY ABSENT: they are the construct state, i.e. correct Hebrew grammar.
FIXES = {
    "Hosea":       {"הוזיא": "הושע"},
    "Micah":       {"מיקה": "מייקה"},
    "Trelawny":    {"טרלווני": "טרלוני"},
    "Lemoyne":     {"למוין": "למויין"},
    "Tomahawk":    {"טומאהוק": "טומהוק"},
    "Ambarino":    {"אמבארינו": "אמברינו"},
    "Grizzlies":   {"הגריזליז": "הגריזליס"},
    "Poncho":      {"פואנטס": "פונצ'ו"},
    # ⛔ `Tonic -> שיער:שיקוי` WAS HERE AND IS REMOVED. audit_consistency reported it as a
    # divergent spelling, but reading the actual lines killed it: `J. J. McCLURE FORTIFYING
    # HAIR TONIC` -> `טוניק לשיער` is CORRECT — שיער is hair, and the game sells both a
    # health tonic and a hair tonic. The rule would have corrupted a right answer into
    # `טוניק לשיקוי`. A "divergence" between two senses of one English word is not a defect;
    # ALWAYS read the matching lines before adding a glossary pair.
    # `נדן` is a BLADE's scabbard; a revolver goes in a `נרתיק`. The corpus decides it, not
    # taste: the 217k already-shipping lines use נרתיק 106 times ("נרתיק עור משומן וצבוע,
    # תפור ידנית עם רצועת פליז") against 65 נדן — and some of those 65 are genuine knife
    # sheaths, which is exactly why this must stay ENGLISH-GUARDED on "holster" and can never
    # be a blind corpus-wide replace.
    "Holster":     {"נדן": "נרתיק"},
    # O'Driscoll: normalise the apostrophe form AND the vav spelling. Order matters — the
    # longer/apostrophe variants must be tried first, and fixing the singular also fixes the
    # plural (אודריסקולס -> אודריסקלס) because it is a strict prefix.
    "O'Driscoll":  {"או'דריסקול": "אודריסקל", "אודריסקול": "אודריסקל"},
    "O'Driscolls": {"האו'דריסקולס": "האודריסקלס", "האודריסקולס": "האודריסקלס"},
}

_PREFIX = "והבלמשכ"


def _en_of(v):
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return str(v or "").strip()


def _pat(wrong: str) -> re.Pattern:
    # allow at most ONE attached Hebrew prefix letter before the term, and refuse a match that
    # is merely the tail of a longer Hebrew word.
    return re.compile(rf"(?<![א-ת])([{_PREFIX}]?){re.escape(wrong)}")


def main() -> None:
    apply = "--apply" in sys.argv
    bank = json.load(open(BANK, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))

    pats = {en: [(w, r, _pat(w)) for w, r in sorted(m.items(), key=lambda kv: -len(kv[0]))]
            for en, m in FIXES.items()}
    en_re = {en: re.compile(rf"\b{re.escape(en)}", re.I) for en in FIXES}

    changed, per_term = {}, {}
    for k, he in bank.items():
        if not isinstance(he, str) or not he:
            continue
        en = _en_of(corpus.get(k))
        if not en:
            continue
        new = he
        for term, subs in pats.items():
            if not en_re[term].search(en):
                continue
            for wrong, right, pat in subs:
                if wrong in new:
                    new2 = pat.sub(lambda m: m.group(1) + right, new)
                    if new2 != new:
                        per_term[term] = per_term.get(term, 0) + 1
                        new = new2
        if new != he:
            changed[k] = new

    print(f"bank {len(bank):,} · lines to fix: {len(changed):,}")
    for t, n in sorted(per_term.items(), key=lambda kv: -kv[1]):
        print(f"    {t:14} {n:4}")
    for k in list(changed)[:6]:
        print(f"  - {bank[k][:70]}")
        print(f"  + {changed[k][:70]}")
    if not changed:
        return
    if not apply:
        print("\n(report only — pass --apply to write)")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BANK, f"{BANK}.bak.names.{ts}")
    bank.update(changed)
    tmp = BANK + ".tmp"
    json.dump(bank, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BANK)
    print(f"applied {len(changed):,} · backup {os.path.basename(BANK)}.bak.names.{ts}")


if __name__ == "__main__":
    main()
