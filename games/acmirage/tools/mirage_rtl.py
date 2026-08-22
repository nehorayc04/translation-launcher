#!/usr/bin/env python3
"""
mirage_rtl.py — logical Hebrew -> the VISUAL order AC Mirage's UI renders.

In-game finding (2026-07-22, menu proof #3): the shipped **Arabic renders correctly**
while our LOGICAL Hebrew came out mirrored. So the engine runs its RTL pipeline for the
ARABIC SCRIPT only and draws Hebrew in storage order — the same signature as The
Witcher 3 patch 4.00. Therefore Hebrew must be stored **VISUAL (pre-reversed)**.

Per the store-VISUAL rules (CLAUDE.md §8b) this does NOT hand-roll run reversal — a
hand-rolled reversal keeps neutral runs forward, which is invisible on a one-word menu
label (a 1-char neutral reverses to itself) and wrong on essentially every real
sentence. It runs the **real Unicode Bidi Algorithm** (`python-bidi`) with an RTL base,
with the engine's own tokens protected as atomic LTR runs.

Tokens kept verbatim and treated as single LTR units:
    <img src='...'/>  ·  <style name='...'>  ·  </style>  ·  {0} {1}  ·  [CT_Foo]

    python mirage_rtl.py selftest
"""
import re
import sys

try:
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover
    get_display = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HEB = re.compile(r"[֐-׿]")
# engine tokens that must survive byte-for-byte and never be reordered internally
TOKEN = re.compile(r"<[^>]{0,120}>|\{\d+\}|\[[A-Za-z0-9_]{1,40}\]|%[sd]")
_PUA = 0xE000                      # private-use placeholders: atomic, strong-LTR


def to_visual(s):
    """Logical Hebrew -> the byte order this engine must be fed. Idempotent-safe on
    strings with no Hebrew (returned unchanged)."""
    if not s or not HEB.search(s):
        return s
    if get_display is None:
        raise RuntimeError("python-bidi is required (use the repo .venv python)")
    # protect tokens
    toks = []

    def _stash(m):
        toks.append(m.group(0))
        return chr(_PUA + len(toks) - 1)

    # line breaks are ORDER-BEARING: convert each line independently so line order
    # is never flipped by the reversal.
    out_lines = []
    for line in s.split("\n"):
        toks.clear()
        protected = TOKEN.sub(_stash, line)
        vis = get_display(protected, base_dir="R")
        for i, t in enumerate(toks):
            vis = vis.replace(chr(_PUA + i), t)
        out_lines.append(vis)
    return "\n".join(out_lines)


def _selftest():
    cases = [
        ("משחק חדש", "שדח קחשמ"),
        ("טען משחק", "קחשמ ןעט"),
        ("קרדיטים", "םיטידרק"),
        ("ZZ-P-C", "ZZ-P-C"),                       # no Hebrew -> untouched
        ("UBISOFT CONNECT", "UBISOFT CONNECT"),
    ]
    ok = 0
    for src, want in cases:
        got = to_visual(src)
        good = got == want
        ok += good
        print(f"  {'OK  ' if good else 'FAIL'} {src!r} -> {got!r}" + ("" if good else f"  want {want!r}"))
    # structural checks that a hand-rolled reversal would get wrong
    extra = [
        "שלום ABC 123",
        "מספרים: 1, 2 ו-3. שאלה? תשובה: כן.",
        "פיסוק (סוגריים) \"מרכאות\" - סוף!",
        "שורה ראשונה\nשורה שנייה",
        "לחץ [CT_ParkourUp] כדי לטפס",
        "יש לך {0} מטבעות",
    ]
    print("  --- structural (round-trip must restore the original) ---")
    for s in extra:
        v = to_visual(s)
        back = to_visual(v)
        rt = back == s
        ok += rt
        print(f"  {'OK  ' if rt else 'FAIL'} {s!r}\n         -> {v!r}")
    print(f"\n  {ok}/{len(cases)+len(extra)} checks passed")
    return 0 if ok == len(cases) + len(extra) else 1


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
    sys.exit(_selftest())
