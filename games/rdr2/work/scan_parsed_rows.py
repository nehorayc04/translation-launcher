#!/usr/bin/env python3
"""scan_parsed_rows.py — find every string the engine PARSES into buttons, and rule each one.

WHY THIS EXISTS. A row like `~INPUT_FRONTEND_ACCEPT~ Yes ~INPUT_FRONTEND_CANCEL~ No` is a WIDGET
the engine parses ("glyph, label, glyph, label"), not prose it draws. Our store-VISUAL transform
moves the leading glyph to the visual end, the parse fails, and the WHOLE row disappears -- every
warning dialog lost its Yes/No buttons that way.

TWO VERDICTS:
  fix   -- glyph-led structure confirmed (against the English when we have it, against the
           Hebrew's own shape when we don't) ⇒ `rdr2_rtl.to_visual_row` pins the tokens
  omit  -- the English pairs but our Hebrew's glyph multiset DIFFERS ⇒ a `.yldb` mis-pair, the
           content is wrong, so the only correct answer is to ship the game's own English

🔴 THREE ROUNDS OF REAL BUGS FOUND BY MEASURING THIS SCAN AGAINST THE CORPUS, EACH TIME COSTING A
SHIP THAT STILL HAD A BROKEN ROW SOMEWHERE:
  1. `"0xE234DD49".upper()` is `"0XE234DD49"` -- uppercasing the whole key mangled the `0x`
     prefix and silently missed every hash-keyed English lookup. Normalise the DIGITS only.
  2. `ROW` had no trailing-STYLE alternative, so `~s~~INPUT_ACCEPT~ Yes~s~` (a real button, glyph
     followed by a style-reset code) failed to match and never got a verdict at all.
  3. `SENT` (a "is this a sentence, not a row" veto on words like to/the/press/use) turned out to
     be REDUNDANT once ROW's structure was tightened, and it was ACTIVELY HARMFUL: any string
     that structurally decomposes into (style)*glyph(label≤26 chars), repeated, with NOTHING
     else, cannot ALSO be a real sentence — the anchored `^...$` match forbids any prose outside
     that shape. Removing SENT recovered 20 more real button rows (13 -> 33) with the class
     verified BY HAND, zero false positives (`Select the cricket`, `Connect Wire`, `Walk with the
     chain gang` are all short in-game prompts, not paragraph sentences).
Lesson: a "does this look like a sentence" word-list veto is a worse instrument than a tight
STRUCTURAL match — the structure IS the answer once it is anchored end-to-end.

A FOURTH class needed a NEW mechanism, not a regex fix: 21 Hebrew values are glyph-led (a widget
row by their OWN shape) but have no English counterpart to compare against at all — the earlier
scan silently dropped them at the `isinstance(eng, str)` gate and they kept getting the ordinary
whole-sentence UBA treatment, which is exactly the transform that breaks a widget row. There is no
mis-pair risk to check (no English to disagree with), so these always verdict "fix" from their own
structure.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gtav", "work"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from gtav_gxt2 import joaat  # noqa: E402

FLEET = os.path.join(HERE, "..", "fleet")
EXTRACT = os.path.join(HERE, "..", "extract")
OUT = os.path.join(HERE, "parsed_rows.json")

# a style/colour code is NOT a button glyph -- it may lead OR trail a row harmlessly
STYLE = r"(?:~(?:s|e|o|r|b|g|y|p|q|h|m|w|lr|rp|fg|fo|COLOR_[^~]*|HUD_[^~]*)~)*"
GLYPH_RE = r"~INPUT(?:GROUP)?_[^~]*~"
# glyph, then ≤26 chars of label, repeated -- and now a trailing STYLE is allowed too, or a real
# button carrying a reset code after its label (`~s~~INPUT_ACCEPT~ Yes~s~`) never matches at all.
ROW = re.compile(rf"^\s*{STYLE}{GLYPH_RE}[^~]{{0,26}}(?:{STYLE}{GLYPH_RE}[^~]{{0,26}})*{STYLE}\s*$")
GLYPH = re.compile(GLYPH_RE)
GLYPH_LED = re.compile(rf"^\s*{STYLE}{GLYPH_RE}")
HEB = re.compile(r"[א-ת]")


def load_english() -> dict:
    out = {}
    for sub in ("game_text", "game_text_v2"):
        p = os.path.join(EXTRACT, sub, "american.json")
        if os.path.exists(p):
            out[sub] = json.load(open(p, encoding="utf-8"))
    return out


def english_for(key: str, books: dict):
    """Normalise only the HEX DIGITS -- `.upper()` on the whole key mangles the `0x` prefix."""
    if key.startswith("0x"):
        forms = [key, "0x" + key[2:].upper(), "0x" + key[2:].lower()]
    else:
        h = joaat(key)
        forms = [f"0x{h:08X}", f"0x{h:08x}"]
    for book in books.values():
        for f in forms:
            if f in book:
                return book[f]
    return None


def scan() -> dict:
    spine = json.load(open(os.path.join(FLEET, "hebrew.json"), encoding="utf-8"))
    spine.update(json.load(open(os.path.join(FLEET, "hebrew_missing.json"), encoding="utf-8")))
    books = load_english()

    rows = {}
    for key, ours in spine.items():
        if not isinstance(ours, str):
            continue
        eng = english_for(key, books)

        if isinstance(eng, str) and len(eng) <= 130 and "~INPUT" in eng and ROW.match(eng):
            same_glyphs = sorted(GLYPH.findall(eng)) == sorted(GLYPH.findall(ours))
            verdict = "fix" if (same_glyphs and HEB.search(ours)) else "omit"
            rows[key] = {"en": eng, "he": ours, "verdict": verdict,
                        "why": "" if verdict == "fix" else "glyph multiset differs -> .yldb mis-pair"}
            continue

        # no comparable English (missing, too long, or not a row there) -- fall back to the
        # HEBREW's own shape. A glyph-led value is a widget row by construction; there is no
        # English to disagree with, so it can never be an "omit" here.
        if eng is None and len(ours) <= 130 and GLYPH_LED.match(ours) and ROW.match(ours):
            rows[key] = {"en": None, "he": ours, "verdict": "fix",
                        "why": "no English match -- classified from the Hebrew's own glyph-led shape"}
    return rows


def main() -> None:
    rows = scan()
    fix = {k: v for k, v in rows.items() if v["verdict"] == "fix"}
    omit = {k: v for k, v in rows.items() if v["verdict"] == "omit"}
    print(f"parsed button rows: {len(rows)}   fix {len(fix)}   omit {len(omit)}\n")
    for label, group in (("FIX (translate labels, pin the glyphs)", fix),
                         ("OMIT (mis-paired -> ship the game's English)", omit)):
        print(f"-- {label}")
        for k, v in sorted(group.items(), key=lambda x: x[1]["en"] or x[1]["he"]):
            print(f"   {k:<18} en={v['en']!r}")
            print(f"   {'':<18} he={v['he'][:64]!r}")
        print()
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
