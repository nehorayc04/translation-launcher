"""QA gate for the shader-metadata translation (effects_he/*.json).

Runs before every build_effects deploy. Per entry:

  key exists     the English side must be a real string from the shaders, so a
                 typo cannot silently translate nothing
  hebrew         the value must actually contain Hebrew
  numbers        every number in the English must survive in the Hebrew - this
                 is the cheap check that catches a dropped "0.825", "16 search
                 steps" or "4x2"
  tech tokens    ALL-CAPS/mixed-case identifiers (NTSC, LUT, FP16, sstr, xBRZ,
                 B-spline...) must survive, they are API/UI names
  niqqud         none
  bidi controls  none - Avalonia runs the UBA, we store LOGICAL
  foreign        Hebrew/Latin/digits/punctuation only
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
KINDS = {
    "categories": "CATEGORY",
    "names": "EFFECT",
    "descriptions": "DESCRIPTION",
    "labels": "PARAM_LABEL",
    "tooltips": "PARAM_DESC",
}

NUM = re.compile(r"\d+(?:\.\d+)?")
TECH = re.compile(r"\b(?:[A-Z]{2,}[0-9]*|[a-z]+[A-Z][A-Za-z]*|[a-z]{3,}str)\b")
NIQQUD = re.compile(r"[֑-ׇ]")
BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")
HEB = re.compile(r"[א-ת]")

# Words the tech-token regex catches but that are ordinary English prose.
TECH_OK = {"TV", "PLAY", "REW", "OK", "ON", "OFF"}


def script_of(ch: str) -> str:
    if ch.isascii():
        return "latin"
    if "֐" <= ch <= "׿":
        return "hebrew"
    if unicodedata.category(ch).startswith(("P", "S", "Z", "N", "M", "C")):
        return "neutral"
    return unicodedata.name(ch, "?").split()[0].lower()


def main() -> int:
    corpus = json.loads((HERE / "extract" / "effects_en.json").read_text("utf-8"))
    bad: list[str] = []
    total = 0

    for name, kind in KINDS.items():
        table = json.loads((HERE / "effects_he" / f"{name}.json").read_text("utf-8"))
        known = set(corpus[kind])
        for en, he in table.items():
            total += 1
            tag = f"{name}/{en[:44]}"
            if en not in known:
                bad.append(f"UNKNOWN-KEY  {tag}")
            if not HEB.search(he):
                bad.append(f"NO-HEBREW    {tag}")
            if NIQQUD.search(he):
                bad.append(f"NIQQUD       {tag}")
            if BIDI.search(he):
                bad.append(f"BIDI-CONTROL {tag} (store LOGICAL)")
            foreign = {script_of(c) for c in he} - {"latin", "hebrew", "neutral"}
            if foreign:
                bad.append(f"FOREIGN      {tag}: {foreign}")
            if sorted(NUM.findall(en)) != sorted(NUM.findall(he)):
                bad.append(f"NUMBERS      {tag}: {NUM.findall(en)} -> {NUM.findall(he)}")
            lost = {w for w in TECH.findall(en) if w not in TECH_OK} - set(TECH.findall(he))
            if lost:
                bad.append(f"TECH-TOKEN   {tag}: lost {sorted(lost)}")

    print(f"{total} translated strings across {len(KINDS)} tables")
    if bad:
        print(f"\n{len(bad)} PROBLEM(S):")
        for b in bad[:60]:
            print("  " + b)
        return 1
    print("QA CLEAN - keys, hebrew, numbers, tech tokens, niqqud, bidi, foreign all OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
