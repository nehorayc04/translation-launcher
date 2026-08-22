#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pt_rtl.py — RTL storage transform for A Plague Tale: Requiem (Zouna engine).

THE ENGINE'S BIDI MODEL (reverse-engineered from the game's own shipped Arabic,
tt23.pc — a THIRD engine class, distinct from the two in the playbook):

    The engine does RIGHT-TO-LEFT directional character LAYOUT (it positions the
    stored characters right-to-left), but performs NO bidi reordering of embedded
    LTR runs and NO Arabic shaping.

So the STORED form = the LOGICAL form with:
  * RTL scripts (Arabic/Hebrew) kept in LOGICAL order (the RTL layout reads them
    correctly),
  * every LTR ISLAND (Latin/digit run) PRE-REVERSED in place (so it reads L->R
    once the engine lays it out R->L),
  * `{STR_...}` button tokens kept VERBATIM, forward, in place,
  * run ORDER preserved (words are NOT reordered).

Ground truth from tt23.pc (this is the game's own working Arabic):
  * "Complete chapter 12"  digit "12"        -> stored "21"     (ACHIEVEMENT__DESC_12)
  * "XVII - <title>"        roman "XVII"       -> stored "IIVX"   (MENU__CHAPTER17;
     IV->VI, IX->XI, XII->IIX ... and the " - " separator stays after the numeral)
  * "Asobo Studio"          multi-word Latin   -> stored "oidutS obosA" (words swap)
  * "in Asobo Studio and"   embedded in Arabic -> "...oidutS obosA..." IN PLACE,
     surrounding Arabic stays logical (run order preserved)  (CREDIT__ENUMS_343)
  * "Hold {STR_CRAFT} ..."  token             -> "...{STR_CRAFT}..." verbatim, forward

Hebrew needs NO shaping (unlike Arabic) -> we store base Hebrew U+05D0-05EA logical
and only pre-reverse LTR islands. This mirrors the game's Arabic EXACTLY, so it is
high-confidence to render correctly (the one remaining unknown = whether the slot
font carries Hebrew glyphs, answered by the menu proof).

`to_stored` is an involution (reversing an island twice restores it), so
`from_stored == to_stored`.
"""

from __future__ import annotations

import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_TOKEN_RE = re.compile(r"\{[^}]*\}")          # {STR_CRAFT} etc. — atomic, forward

# The em/en-dash (U+2014/U+2013) is NOT in the Arabic (BIG_ARABIC) font, so it renders
# from the game's big Latin font -> a huge dash that dwarfs the Hebrew. The ASCII hyphen
# IS in BIG_ARABIC at Hebrew size, so normalise dashes to a spaced hyphen " - " (natural
# in Hebrew, small, and the spaces keep it out of any LTR island).
_DASH_RE = re.compile(r"\s*[—–]\s*")


def _normalize(text: str) -> str:
    return _DASH_RE.sub(" - ", text)

# An LTR ISLAND = one or more alphanumeric "words" joined by SINGLE spaces; a word
# may carry internal attached punctuation (apostrophe / dot / hyphen / slash / &).
# Reversed as a unit -> matches the game's Arabic for digits, roman numerals AND
# multi-word Latin names. The pattern only crosses a space when the NEXT char is
# alphanumeric, so a " - " separator (space+dash+space) is NOT absorbed:
# "XVII - <title>" -> "IIVX - <title>" (dash stays put), exactly like MENU__CHAPTER17.
_ISLAND = re.compile(
    r"[0-9A-Za-z]+(?:[.'’/&\-][0-9A-Za-z]+)*"
    r"(?:[ ][0-9A-Za-z]+(?:[.'’/&\-][0-9A-Za-z]+)*)*"
)

# The engine does RTL char LAYOUT but NO bidi glyph-mirroring, so a paired bracket
# must be stored MIRRORED to render correctly — matching the game's own Arabic
# EXACTLY: "Soldiers (Various)" -> stored "ﺍﻟﺠﻨﻮﺩ )ﻣﺨﺘﻠﻔﻮﻥ(" (the "(...)" become ")...(").
# For a Latin island the reversal already swaps its own brackets; this pass also
# fixes brackets around Hebrew/standalone. `{}` are NEVER mirrored (they are
# {STR_...} tokens, and _stored_text only ever sees the non-token parts anyway).
_MIRROR = str.maketrans("()[]<>«»‹›", ")(][><»«›‹")


def _stored_text(text: str) -> str:
    """Reverse every LTR island, then mirror paired brackets; Hebrew, spaces,
    dashes, stray punctuation stay in logical position (the engine lays the whole
    string out right-to-left)."""
    return _ISLAND.sub(lambda m: m.group(0)[::-1], text).translate(_MIRROR)


def _stored_segment(seg: str) -> str:
    """Transform one text run, protecting `{...}` tokens (kept verbatim + forward)."""
    if not seg:
        return seg
    out = []
    pos = 0
    for m in _TOKEN_RE.finditer(seg):
        out.append(_stored_text(seg[pos:m.start()]))
        out.append(m.group(0))        # token: verbatim, forward, in place
        pos = m.end()
    out.append(_stored_text(seg[pos:]))
    return "".join(out)


def to_stored(logical: str) -> str:
    """LOGICAL string -> the STORED (on-disk) form for tt23.pc, mirroring how the
    game itself stores Arabic. Pure-Hebrew / pure-punctuation input is returned
    unchanged (no island matches). A pure-Latin value (a proper noun kept in Latin)
    IS reversed so it renders correctly under the engine's RTL layout — do NOT gate
    on Hebrew presence. `|` is the in-value line break; islands never cross it."""
    if not logical:
        return logical
    logical = _normalize(logical)
    # `|` isn't alphanumeric so islands can't span it; a plain sub over the whole
    # (token-protected) string is correct. Kept explicit for clarity/safety.
    return "".join(
        _stored_segment(part) if part != "|" else "|"
        for part in re.split(r"(\|)", logical)
    )


from_stored = to_stored


# --------------------------------------------------------------------------- #
# self-test  (expectations validated against the game's own tt23.pc conventions)
# --------------------------------------------------------------------------- #
# --- PROJECT-WIDE IRON RULE: the plain ASCII hyphen `-`, never a long dash `—`. ---
# Enforced HERE, at the last gate before storage, so no translator/agent/fleet output can
# ever carry one into the game. One-for-one character swap; see universal/text_norm.py.
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))), "universal"))
try:
    from text_norm import normalize_dashes as _norm_dashes
except ImportError:  # keeps the tool runnable if moved
    import re as _re
    _DASHES = _re.compile("[‐‑‒–—―−⸺⸻﹘﹣－]")
    def _norm_dashes(s):
        return _DASHES.sub("-", s) if s else s


def _iron_rule(_fn):
    def _wrapped(s, *a, **kw):
        return _fn(_norm_dashes(s) if isinstance(s, str) else s, *a, **kw)
    _wrapped.__name__ = _fn.__name__
    _wrapped.__doc__ = _fn.__doc__
    return _wrapped

to_stored = _iron_rule(to_stored)


if __name__ == "__main__":
    failures = []

    def check(name, got, want):
        ok = got == want
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"      got : {got!r}\n      want: {want!r}")
            failures.append(name)

    # pure Hebrew stays LOGICAL (engine lays it out RTL)
    check("pure hebrew unchanged", to_stored("שלום עולם"), "שלום עולם")
    check("hebrew comma logical", to_stored("שלום, עולם"), "שלום, עולם")

    # digits reverse (matches ACHIEVEMENT__DESC_12 "12"->"21")
    check("two-digit reversed", to_stored("השלם פרק 12"), "השלם פרק 21")
    check("single digit unchanged", to_stored("5 עכברים"), "5 עכברים")

    # roman numeral reverses, " - " separator stays after it (MENU__CHAPTER17)
    check("roman numeral + separator",
          to_stored("XVII - מורשת משפחת דה רון"),
          "IIVX - מורשת משפחת דה רון")
    check("roman IV -> VI", to_stored("IV - חובת המגן"), "VI - חובת המגן")

    # multi-word Latin name reverses as a UNIT (words swap) — CREDIT__ENUMS_343
    check("latin name island (words swap)",
          to_stored("צוות Asobo Studio כאן"),
          "צוות oidutS obosA כאן")

    # {STR_} token kept verbatim + forward, in place (HUD__BUTTONS_A_CRAFT)
    check("STR token verbatim",
          to_stored("החזק {STR_CRAFT} כדי לייצר"),
          "החזק {STR_CRAFT} כדי לייצר")

    # pipe = line break: each segment transformed independently, pipes preserved
    check("pipe segments independent",
          to_stored("שורה 12|שורה שנייה"),
          "שורה 21|שורה שנייה")

    # apostrophe word stays one island
    check("apostrophe word", to_stored("של Amicia's כאן"), "של s'aicimA כאן")

    # brackets around HEBREW are MIRRORED (matches the game's Arabic
    # "الجنود )مختلفون(" — the reported in-game paren bug)
    check("parens around hebrew mirror",
          to_stored("החיילים (מגוונים)"), "החיילים )מגוונים(")
    check("hebrew paren phrase",
          to_stored("ירי (בזמן כיוון)"), "ירי )בזמן כיוון(")
    check("brackets around latin island still swap",
          to_stored("קוד (ABC)"), "קוד )CBA(")

    # empty passthrough
    check("empty passthrough", to_stored(""), "")

    # involution: applying twice restores the original
    for s in ["שלום Asobo 10 עולם", "החזק {STR_CRAFT}|פרק 12",
              "צוות Asobo Studio כאן", "XVII - מורשת"]:
        check(f"involution: {s!r}", to_stored(to_stored(s)), s)

    print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED"))
    sys.exit(1 if failures else 0)
