#!/usr/bin/env python3
"""gtav_rtl.py - logical Hebrew -> the VISUAL byte order GTA V's Scaleform UI draws.

GTA V runs **no bidi** (Autodesk's own docs list Hebrew/Arabic as unsupported in Scaleform
GFx), so the text has to be stored already reversed.

It replaces `gxt2.visual_line`, whose hand-rolled run-reversal keeps every non-Hebrew run
FORWARD - correct for a Latin island, wrong for a NEUTRAL run, which belongs to the RTL
flow and must be reversed with its brackets mirrored (UBA rule L4). Measured over the whole
141,001-string corpus, the two disagree on **68,422 strings (48.5 %)**, and in every sampled
case the UBA is the correct one:

    logical  תצפית (דרום)              Kuruma (משוריין)
    old      )םורד (תיפצת              )ןיירושמKuruma (      <- parens flipped, space lost
    UBA      (םורד) תיפצת              (ןיירושמ) Kuruma      <- correct

The defect was predicted in CLAUDE.md when RDR2 hit it ("GTA V ships the SAME visual_line →
it very likely carries this identical mid-sentence punctuation defect") and then confirmed
in-game on Enhanced.

**Token order also gets fixed, not just punctuation.** Of the 5,951 strings whose token
sequence changes, 4,233 are a plain reversal (correct for RTL) and 1,718 are cases where the
old reversal wrongly flipped an ADJACENT token pair - e.g.
`~INPUT_VEH_MELEE_LEFT~/~INPUT_VEH_MELEE_RIGHT~` came out RIGHT-then-LEFT, silently swapping
"left" and "right" in a control hint, and `~a~~s~` came out `~s~~a~`, moving a colour reset
in front of the value it was meant to follow. Holding each token as one atomic LTR unit keeps
those pairs in their logical order.

Rules, same shape as `games/rdr2/work/rdr2_rtl.py`:
  * every engine token (`~…~`, `<tag>`, printf) is stashed as an atomic private-use char so
    the UBA treats it as one LTR run and cannot reorder its insides;
  * `~n~` and real newlines are ORDER-BEARING separators - each segment is converted on its
    own so line order is never flipped;
  * each segment's edge whitespace is stripped: under an RTL base a logical-trailing space
    lands at the visual START, i.e. in the left margin, where it shows as a stray indent;
  * a string with no Hebrew is returned untouched (never reverse a pure-Latin value).
"""
import re

from bidi.algorithm import get_display

_HEB = re.compile(r"[֐-׿]")
# GTA tokens/tags/printf - identical to the set build_full_gxt2 validates against.
_TOKEN = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]")
# separators whose position carries meaning
_SEP = re.compile(r"(~n~|\r\n|\n)")
_PUA = 0xE000


def has_hebrew(s):
    return bool(s) and bool(_HEB.search(s))


def _segment_to_visual(seg):
    """UBA-convert ONE separator-free segment, every engine token held atomic."""
    seg = seg.strip()
    if not has_hebrew(seg):
        return seg
    toks = []

    def _hold(m):
        toks.append(m.group(0))
        return chr(_PUA + len(toks) - 1)

    protected = _TOKEN.sub(_hold, seg)
    vis = get_display(protected, base_dir="R")
    for i, t in enumerate(toks):
        vis = vis.replace(chr(_PUA + i), t)
    return vis


def to_visual(s):
    """Logical Hebrew -> the visual byte order the Scaleform UI should draw."""
    if not has_hebrew(s):
        return s
    parts = _SEP.split(s)
    return "".join(p if _SEP.fullmatch(p) else _segment_to_visual(p) for p in parts)


def _selftest():
    cases = [
        # (logical, expected visual)
        ("שלום", "םולש"),
        ("תצפית (דרום)", "(םורד) תיפצת"),
        ("Kuruma (משוריין)", "(ןיירושמ) Kuruma"),
        # a pure-Latin value must never be touched
        ("Move Tab", "Move Tab"),
        ("", ""),
    ]
    ok = 0
    for src, want in cases:
        got = to_visual(src)
        flag = "OK " if got == want else "FAIL"
        if got == want:
            ok += 1
        else:
            print(f"  {flag} {src!r}\n       got  {got!r}\n       want {want!r}")
    # structural invariants over a token-heavy line
    t = "החזק ~INPUT_A~ והקש ~INPUT_LEFT~/~INPUT_RIGHT~ כדי לדחוף.~n~שורה שנייה"
    v = to_visual(t)
    inv = [
        ("token multiset preserved", sorted(_TOKEN.findall(t)) == sorted(_TOKEN.findall(v))),
        ("adjacent pair keeps logical order",
         v.index("~INPUT_LEFT~") < v.index("~INPUT_RIGHT~")),
        ("line order preserved", v.index("~n~") > 0 and "שורה שנייה"[::-1] in v),
        ("no PUA leaked", not any(0xE000 <= ord(c) <= 0xF8FF for c in v)),
    ]
    for name, cond in inv:
        print(f"  {'OK ' if cond else 'FAIL'} {name}")
        ok += bool(cond)
    total = len(cases) + len(inv)
    print(f"selftest {ok}/{total}")
    return ok == total


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

to_visual = _iron_rule(to_visual)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(0 if _selftest() else 1)
