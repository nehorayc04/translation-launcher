"""Logical Hebrew -> the byte order Skyrim's Scaleform renderer needs.

Skyrim's UI is Scaleform GFx 4.0 (2011) with NO bidi pass -- the community's own
Arabic tooling (xTranslator's "Arabic RTL -> LTR conversion") pre-reverses the text,
which is the classic store-VISUAL signature. So we run the REAL Unicode Bidi
Algorithm offline (python-bidi, RTL base) and store its visual output.

Rules that a hand-rolled run-reversal always gets wrong (see CLAUDE.md 8b):
  * neutrals (punctuation) belong to the RTL flow -> the UBA must resolve them,
  * engine tokens must stay ATOMIC and forward -> stash them as PUA placeholders,
  * line separators are ORDER-PRESERVING -> split, convert each segment, rejoin,
  * strip each segment's edge whitespace (a logical-trailing space lands in the
    visual LEFT margin and renders as a stray indent).

Skyrim token inventory (measured over 78,042 unique English strings):
    <...>   8,343   <Alias=City> <mag> <dur> <br> </p> <font face='$X'> <p align="...">
    [...]   1,979   [Activate] [Sneak] [Mouse Move]   (control-name substitutions)
    %d %s %i   42
"""
from __future__ import annotations

import re
import sys

try:
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover
    get_display = None

# order-bearing separators: keep them, convert each side independently
_SEP = re.compile(r"(\r\n|\r|\n)")

# atomic engine tokens (never reordered internally, never reversed)
# NOTE: <...> cap widened 80->200 -- some <img src='...'> book-illustration tags
# run up to 112 chars; an 80-char cap let them fall through unprotected and get
# mangled mid-tag during the bidi reversal (found + fixed 2026-08-11).
_TOKEN = re.compile(r"<[^<>\n]{1,200}>|\[[A-Za-z][A-Za-z0-9 _/]{0,30}\]|%[sdi]")

_PUA_BASE = 0xE000
HEB = re.compile(r"[֐-׿]")


def _protect(s: str) -> tuple[str, list[str]]:
    toks: list[str] = []

    def sub(m: re.Match) -> str:
        toks.append(m.group(0))
        return chr(_PUA_BASE + len(toks) - 1)

    return _TOKEN.sub(sub, s), toks


def _restore(s: str, toks: list[str]) -> str:
    if not toks:
        return s
    out = []
    for ch in s:
        i = ord(ch) - _PUA_BASE
        out.append(toks[i] if 0 <= i < len(toks) else ch)
    return "".join(out)


def _segment_to_visual(seg: str) -> str:
    if not HEB.search(seg):
        return seg                      # pure Latin/number -> never touch
    body = seg.strip()
    if not body:
        return seg
    prot, toks = _protect(body)
    vis = get_display(prot, base_dir="R")
    return _restore(vis, toks)


def to_visual(s: str) -> str:
    """Convert a LOGICAL Hebrew string into the visual order Skyrim renders."""
    if not s or not HEB.search(s):
        return s
    if get_display is None:
        raise RuntimeError("python-bidi missing -- run with the repo .venv python")
    parts = _SEP.split(s)
    return "".join(p if _SEP.fullmatch(p) else _segment_to_visual(p) for p in parts)


# ------------------------------------------------------------------ selftest
_CASES = [
    ("שלום", "םולש"),
    ("אבגד", "דגבא"),
    ("", ""),
    ("Skyrim", "Skyrim"),                                   # no Hebrew -> untouched
    ("שלום\r\nעולם", "םולש\r\nםלוע"),                        # line ORDER preserved
    (" שלום ", "םולש"),                                      # edge whitespace stripped
]


def selftest() -> int:
    bad = 0
    for src, want in _CASES:
        got = to_visual(src)
        if got != want:
            bad += 1
            print(f"FAIL {src!r} -> {got!r} (want {want!r})")
    # structural invariants on richer strings
    checks = [
        ("שלום <Alias=City> עולם", "<Alias=City>"),
        ("נזק [Activate] כאן", "[Activate]"),
        ("ערך %d נקודות", "%d"),
        ("<font face='$HandwrittenFont'>מכתב</font>", "<font face='$HandwrittenFont'>"),
    ]
    for src, tok in checks:
        got = to_visual(src)
        if tok not in got:
            bad += 1
            print(f"FAIL token lost: {src!r} -> {got!r}")
        if sorted(got.replace(tok, "")) != sorted(src.replace(tok, "").strip()):
            # same multiset of remaining chars (order may differ; content must not)
            bad += 1
            print(f"FAIL char multiset: {src!r} -> {got!r}")
    # a real sentence: punctuation must move to the visual LEFT under RTL
    s = "ברוך הבא לסקיירים, בן דרקון!"
    v = to_visual(s)
    if not v.startswith("!"):
        bad += 1
        print(f"FAIL terminal punctuation not at visual start: {v!r}")
    # idempotence guard: converting twice must NOT equal converting once
    if to_visual(v) == v and HEB.search(v):
        bad += 1
        print("FAIL to_visual looks idempotent (suspicious)")
    print(f"selftest: {'PASS' if bad == 0 else f'{bad} FAILURES'}")
    return bad


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
    raise SystemExit(1 if selftest() else 0)
