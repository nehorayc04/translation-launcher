# -*- coding: utf-8 -*-
"""rtl_anchor.py — per-segment RTL punctuation anchoring (shared).

Hebrew uses the NEUTRAL `?` / `!` / `.` / `:` etc. (unlike Arabic's strong-RTL `؟`),
so a sentence-final punctuation mark at the end of a `<ts>` segment FLIPS to the
right (visual start) under an LTR container base unless a `&rlm;` (U+200F) is placed
right after it. The game's official Arabic localization anchors every neutral
terminal punctuation this way (measured: `.` 18,600 anchored / `؟` ~0). This module
reproduces that for Hebrew, where `?` ALSO needs the anchor.

`anchor_value(v)` adds the missing `&rlm;` per `<ts>` segment (idempotent, structure
preserving). `strip_rlm(v)` removes anchors (for showing clean text to a reviewer).
"""
import re

TS_SPLIT = re.compile(r'(<ts="[^"]*">)')
RLM_ENT  = "&rlm;"
RLM_CHR  = "‏"
# terminal punctuation that is NEUTRAL in Hebrew and therefore needs an RTL anchor.
_TERMINAL = ".!?…:;,"
_CLOSERS  = "\"'»)]”’"          # a closing quote/paren may sit after the punct
_OPENERS  = "\"“«(‘"             # a segment-initial opener flips left → needs a LEADING anchor
                                # ([ ] excluded on purpose: dual-use with [TOKEN]/[sound cue] brackets)
# body ends with: a terminal punct (+ optional closer)  OR  a dash run
_NEEDS_TRAIL = re.compile(r'(?:[' + re.escape(_TERMINAL) + r'][' + re.escape(_CLOSERS) + r']?|--|—|–|(?<![A-Za-z֐-׿])-)$')
_LEAD_OPENER = re.compile(r'^\s*([' + re.escape(_OPENERS) + r'])')


def _anchor_part(part: str) -> str:
    """Anchor BOTH boundaries of one segment's text:
       - LEADING &rlm; if it starts with a neutral opener (quote/paren) — else the
         opener flips to the visual left under the LTR container base (UBA-verified).
       - TRAILING &rlm; if it ends with neutral terminal punctuation."""
    if not part.strip():
        return part
    # --- leading opener anchor ---
    if _LEAD_OPENER.match(part) and not part.lstrip().startswith((RLM_ENT, RLM_CHR)):
        lead_ws = part[:len(part) - len(part.lstrip())]
        part = lead_ws + RLM_ENT + part[len(lead_ws):]
    # --- trailing punct anchor ---
    m = re.match(r'^(.*?)(\s*)$', part, re.S)     # body + trailing whitespace
    body, ws = m.group(1), m.group(2)
    if body and not (body.endswith(RLM_ENT) or body.endswith(RLM_CHR)) and _NEEDS_TRAIL.search(body):
        part = body + RLM_ENT + ws
    return part


def anchor_value(v: str) -> str:
    """Add a leading &rlm; before a segment-initial opener AND a trailing &rlm; after
    neutral terminal punctuation, per <ts> segment. Skips <span> (menu-style) values."""
    if not isinstance(v, str) or "<span" in v:
        return v
    parts = TS_SPLIT.split(v)               # [text, tag, text, tag, ... , text]
    return "".join(p if i % 2 else _anchor_part(p) for i, p in enumerate(parts))


def strip_rlm(v: str) -> str:
    if not isinstance(v, str):
        return v
    return v.replace(RLM_ENT, "").replace(RLM_CHR, "")


if __name__ == "__main__":
    # quick self-test
    tests = [
        ('<ts="0;1">מה קורה?', '<ts="0;1">מה קורה?&rlm;'),
        ('<ts="0;1">בבית הספר? <ts="2;3">במכללה?', '<ts="0;1">בבית הספר?&rlm; <ts="2;3">במכללה?&rlm;'),
        ('<ts="0;1">כבר אנכר.&rlm;', '<ts="0;1">כבר אנכר.&rlm;'),          # idempotent
        ('<ts="0;1">היי Miles,', '<ts="0;1">היי Miles,&rlm;'),
        ('<ts="0;1">מה--', '<ts="0;1">מה--&rlm;'),
        ('<ts="0;1">שם בלי פיסוק', '<ts="0;1">שם בלי פיסוק'),              # no punct -> untouched
        ('סתם דיאלוג.', 'סתם דיאלוג.&rlm;'),                               # plain (no ts)
        ('<span>בתוך ספאן.</span>', '<span>בתוך ספאן.</span>'),           # span -> skip
        # leading openers (quote/paren) -> leading &rlm; + trailing punct anchor
        ('<ts="0;1">"ו-... כוחות-על."', '<ts="0;1">&rlm;"ו-... כוחות-על."&rlm;'),
        ('(היי, מה קורה?)', '&rlm;(היי, מה קורה?)&rlm;'),
        ('<ts="0;1">[שיעול] של גוש שיער.', '<ts="0;1">[שיעול] של גוש שיער.&rlm;'),  # [ excluded
        ('<ts="0;1">[צוחק]', '<ts="0;1">[צוחק]'),                                   # sound cue [ untouched
        ('&rlm;"כבר מעוגן."&rlm;', '&rlm;"כבר מעוגן."&rlm;'),             # idempotent both ends
        ('אמר "שלום" וברח.', 'אמר "שלום" וברח.&rlm;'),                     # mid-quote untouched, trailing anchored
    ]
    ok = 0
    for src, exp in tests:
        got = anchor_value(src)
        flag = "OK " if got == exp else "FAIL"
        if got == exp: ok += 1
        print(f"  {flag} {src!r} -> {got!r}" + ("" if got == exp else f"  EXPECTED {exp!r}"))
    print(f"{ok}/{len(tests)} passed")
