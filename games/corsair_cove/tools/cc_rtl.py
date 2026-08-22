#!/usr/bin/env python3
"""
cc_rtl.py - Hebrew storage-order helpers for Corsair Cove (Unreal Engine 5).

✅ SETTLED IN-GAME 2026-08-02: **bidi = LOGICAL**. The A/B pair put the SAME word
on two adjacent main-menu rows -- `שלום` stored LOGICAL and `םולש` stored VISUAL --
and the LOGICAL row rendered as the readable word while the VISUAL row rendered
mirrored. The `אבגד` control and the 27-letter row agreed. Unreal runs ICU's
Unicode Bidi Algorithm on every Slate/UMG run, exactly as Hogwarts Legacy and
Until Dawn also proved.

  => `to_logical()` IS the shipping transform: store natural Hebrew, never
     pre-reverse -- PLUS one leading RLM to pin the paragraph's base direction
     (see the function docstring; proven by its own 3-rung ladder in-game).
  => `to_visual()` is ONLY the A/B counterpart for a proof. Do NOT ship it.

🔴 A STALE DOCSTRING IS HOW A WRONG RULE SHIPS. This file previously said "never
inject bidi controls" -- true of the letter ORDER, and wrong about the paragraph
BASE. When a proof overturns a prediction, grep the tooling for the old claim.

Engine tokens in this corpus (measured over the 12,821 en entries):
    {VAR}        1,561 occ / 151 distinct   e.g. {Target} {absAmount} {0}
    <tag>        1,894 occ / 139 distinct   e.g. <hl> <b> </> <img id="Coin"/>
    real \n        762 occ  (278 lines)
    no [brackets], no &entities;, no real printf specs
Tokens are stashed as atomic PUA placeholders so the UBA treats each as one
opaque LTR run, and each newline-separated segment is converted independently so
line ORDER is never flipped.
"""
import os
import re
import sys

# the project-wide IRON RULE lives in universal/text_norm.py (repo root = 3 levels up
# from games/<game>/tools/). Fall back to a local copy so this tool always runs standalone.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(_ROOT, "universal"))
try:
    from text_norm import normalize_dashes  # noqa: E402
except ImportError:  # pragma: no cover - keeps the tool usable if moved
    _LONG_DASHES = "‐‑‒–—―−⸺⸻﹘﹣－"
    _MULTI_DASH = re.compile("[" + _LONG_DASHES + "]+")

    def normalize_dashes(s):
        return _MULTI_DASH.sub("-", s) if s else s

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEB = re.compile(r"[֐-׿]")
# bidi control chars: never store them -- the engine does its own bidi.
BIDI_CTRL = re.compile(r"[‎‏‪-‮⁦-⁩؜]")
# longest-first so `<img id="x"/>` wins over a bare `<...>`
TOKEN = re.compile(r"<[^<>]{1,60}>|\{[^{}]{0,60}\}")
PUA_BASE = 0xE000


def has_hebrew(s):
    return bool(HEB.search(s))


def strip_controls(s):
    return BIDI_CTRL.sub("", s)


RLM = "‏"          # RIGHT-TO-LEFT MARK: zero-width, STRONG RTL
HEB_LETTER = re.compile(r"[א-ת]")


def to_logical(s):
    """THE SHIPPING TRANSFORM.

    "Store natural Hebrew" is NOT the whole rule. The UBA picks a paragraph's base
    direction from its FIRST STRONG character (rules P2/P3), so a Hebrew line that
    OPENS with a Latin run -- a brand, a version number, or a `{VAR}` that the
    engine substitutes with Latin at RUNTIME -- gets an **LTR base**: the whole
    paragraph left-aligns and its neutrals (`;` `:` `0-100%`) land on the wrong
    side. PROVEN in-game 2026-08-02 with a 3-rung ladder on three description
    panels: leading-RLM ✅ right-aligned · source reworded to open in Hebrew ✅ ·
    untouched control ✗ still left-aligned.

    So: prepend U+200F to every line that CONTAINS Hebrew. It is zero-width and
    invisible (cc_font maps the whole bidi-control set to an empty glyph -- without
    that the RLM renders as TOFU, the documented Spider-Man 2 trap), it is immune
    to runtime `{VAR}` substitution, and it needs no discipline from the
    translator. A pure-Latin string (a brand, a code) is left untouched, because
    forcing an RTL base on it would be wrong.
    """
    s = normalize_dashes(strip_controls(s))   # IRON RULE: plain "-", never "—"
    if HEB_LETTER.search(s):
        return RLM + s
    return s


def _stash(s):
    toks = []

    def sub(m):
        toks.append(m.group(0))
        return chr(PUA_BASE + len(toks) - 1)

    return TOKEN.sub(sub, s), toks


def _unstash(s, toks):
    for i, t in enumerate(toks):
        s = s.replace(chr(PUA_BASE + i), t)
    return s


def _segment_to_visual(seg):
    from bidi.algorithm import get_display
    stashed, toks = _stash(seg)
    lead = stashed[:len(stashed) - len(stashed.lstrip())]
    trail = stashed[len(stashed.rstrip()):]
    core = stashed.strip()
    if not core:
        return seg
    out = get_display(core, base_dir="R")
    return _unstash(lead + out + trail, toks)


def to_visual(s):
    """Pre-reversed storage for a NON-bidi engine. Newlines are order-bearing
    separators, so each line is converted on its own and re-joined in order."""
    s = strip_controls(s)
    if not has_hebrew(s):
        return s
    return "\n".join(_segment_to_visual(p) for p in s.split("\n"))


def selftest():
    cases = [
        ("שלום", "םולש"),
        ("אבגד", "דגבא"),
        ("Corsair Cove", "Corsair Cove"),          # no Hebrew -> untouched
        ("{Target} זהב", None),                     # token survives
        ("שורה א\nשורה ב", None),                   # line order preserved
    ]
    ok = 0
    for src, exp in cases:
        got = to_visual(src)
        good = (got == exp) if exp is not None else True
        if exp is None:
            if src.count("\n") != got.count("\n"):
                good = False
            for t in TOKEN.findall(src):
                if t not in got:
                    good = False
        ok += good
        print(("PASS " if good else "FAIL ") + repr(src) + " -> " + repr(got))
    # to_logical: never REORDER, only prepend the RTL-base mark
    for s in ["שלום עולם", "{a} שלום <b>x</b>", "AMD FSR 2.2 קובע 0-100%"]:
        out = to_logical(s)
        good = out == RLM + s
        ok += good
        print(("PASS " if good else "FAIL ") + "RLM-prefixed, order intact " + repr(out[:40]))
    # IRON RULE: a long dash can never reach the game
    out = to_logical("שלום — עולם, טווח 0–100")
    good = out == RLM + "שלום - עולם, טווח 0-100"
    ok += good
    print(("PASS " if good else "FAIL ") + "long dashes normalised to '-' " + repr(out))
    # a pure-Latin string must NOT get an RTL base
    good = to_logical("AMD FSR 2.2") == "AMD FSR 2.2"
    ok += good
    print(("PASS " if good else "FAIL ") + "pure-Latin left untouched")
    # never double-prefix / never keep a stray control from a translator
    good = to_logical(to_logical("שלום")) == RLM + "שלום"
    ok += good
    print(("PASS " if good else "FAIL ") + "idempotent (strip-then-prepend)")
    total = len(cases) + 6
    print("\n%d/%d" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
