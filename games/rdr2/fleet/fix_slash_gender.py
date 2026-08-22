#!/usr/bin/env python3
"""fix_slash_gender.py — collapse `את/ה יכול/ה` slash-gender notation to masculine singular.

The mod's standing rule is a MASCULINE SINGULAR addressee, and RDR2's engine has no gender
substitution — it prints `את/ה יכול/ה לשבת` literally. 69 lines carry it.

🔴 A BLANKET `X/Y -> X` RULE CORRUPTS REAL TEXT. Of the 43 distinct slash forms in the corpus
only some are gender notation; the rest are ordinary alternatives that must survive verbatim:
    gender    את/ה x37 · יכול/ה x15 · יודע/ת x8 · מוזמן/ת x5 · בוא/י x3 …
    NOT       ו/או x26 (and/or) · הפעל/כבה x4 (on/off) · קודם/הבא x3 (prev/next) ·
              שלח/קבל x2 · אחז/בחר · דואר/פרס · מיער/נהר …
The discriminator is measured, not guessed: gender notation appends a SINGLE gender letter
(ה ת י ך); a genuine alternative appends a whole word.

Two more traps inside the gender set itself:
  • `את/ה` is the ONE form whose BASE is the FEMININE word — masculine is base+ה (`אתה`).
    Taking the base, as every other form requires, would flip the player's gender.
  • A base can end in a NON-FINAL letter that only exists because the suffix followed it:
    `אשמ/ה` -> `אשמ` is not a word, it is `אשם`; `שייכ/ת` -> `שייך`.

    python fix_slash_gender.py            # review every change, write nothing
    python fix_slash_gender.py --apply
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SPINES = [os.path.join(HERE, "hebrew.json"), os.path.join(HERE, "hebrew_missing.json")]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GENDER_SUFFIX = set("התיך")
FINAL = {"מ": "ם", "נ": "ן", "צ": "ץ",
         "פ": "ף", "כ": "ך"}
# the second half may be a whole word (`תהיה/תהיי`), so it is NOT capped at 3 letters —
# `masculine()` is what decides whether a match is gender notation at all.
SLASH = re.compile(r"([א-ת]+)/([א-ת]{1,10})(?![א-ת])")
# the pronoun pair written out in full, e.g. `את/אתה` — masculine is the SECOND half
FULL_PRONOUN = re.compile(r"(?<![א-ת])את/(ו?אתה)(?![א-ת])")


def _shared_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def masculine(base: str, suf: str) -> str | None:
    """-> the masculine form, or None when this slash is NOT gender notation."""
    if len(suf) != 1 or suf not in GENDER_SUFFIX:
        # A gender pair can also be written out in FULL (`תהיה/תהיי`), which the single-letter
        # test misses and which then leaves a line half-collapsed. Such a pair shares almost
        # all of its letters; a genuine alternative shares none. Measured over all 43 forms in
        # the corpus: `תהיה/תהיי` shares 3 of 4 (75 %), while ו/או, הפעל/כבה, קודם/הבא,
        # שלח/קבל, אחז/בחר, דואר/פרס, מיער/נהר … every one of them shares ZERO.
        # ⚠️ Compare with a leading Hebrew PREFIX letter stripped from the base: `שתהיה/תהיי`
        # shares nothing while the ש is attached, and would be silently left half-collapsed.
        stem = base[1:] if len(base) > 3 and base[0] in "והבלמכש" else base
        if len(suf) >= 3 and _shared_prefix(stem, suf) >= 0.6 * min(len(stem), len(suf)):
            return base
        return None                      # ו/או, הפעל/כבה, קודם/הבא … leave alone
    if base.endswith("את") and suf == "ה":
        return base + suf                # את/ה ואת/ה שאת/ה -> אתה ואתה שאתה
    if base and base[-1] in FINAL:
        return base[:-1] + FINAL[base[-1]]   # אשמ -> אשם · שייכ -> שייך
    return base


def fix(v: str):
    out = FULL_PRONOUN.sub(lambda m: m.group(1), v)

    def _sub(m):
        r = masculine(m.group(1), m.group(2))
        return m.group(0) if r is None else r

    return SLASH.sub(_sub, out)


def main() -> None:
    apply = "--apply" in sys.argv
    total = 0
    for p in SPINES:
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        edits = {}
        for k, v in d.items():
            if not isinstance(v, str) or "/" not in v:
                continue
            nv = fix(v)
            if nv != v:
                edits[k] = nv
        print(f"\n{os.path.basename(p)}: {len(edits)} lines to fix")
        for k, nv in list(edits.items())[:80]:
            print(f"   {k}\n     -  {d[k][:76]}\n     +  {nv[:76]}")
        total += len(edits)
        if apply and edits:
            shutil.copy2(p, f"{p}.bak.slash.{time.strftime('%Y%m%d_%H%M%S')}")
            d.update(edits)
            tmp = f"{p}.{os.getpid()}.tmp"
            json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            for w in (0, 0.6, 2.0):
                if w:
                    time.sleep(w)
                try:
                    os.replace(tmp, p)
                    print(f"   -> wrote {len(edits)}")
                    break
                except OSError:
                    pass
    print(f"\ntotal: {total} lines" + ("" if apply else "   (report only — pass --apply)"))


if __name__ == "__main__":
    main()
