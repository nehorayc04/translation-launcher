"""Hebrew ordering for Forza Horizon 6.

FH6 ships NO RTL locale (23 text languages, all Latin/Cyrillic/Greek/CJK) and
its XAML UI never sets FlowDirection to anything but LeftToRight, so the
prediction is that the renderer does NO bidi -> store VISUAL. The menu proof
decides; until it does, BOTH modes are produced and `to_visual` is the one that
is only used where the proof says so.

`to_visual` runs the REAL Unicode Bidi Algorithm (python-bidi) with an RTL base
after stashing every engine token as an atomic private-use placeholder, which
is what keeps `{0}`, `[HIGHLIGHT:{0}]`, `<tag>` and `%s` from being reordered
or mangled. Newlines are order-preserving segment separators, and each segment
is edge-stripped (a logical-trailing space becomes a visible left indent
otherwise).
"""
from __future__ import annotations

import re
from typing import Dict, List

from bidi.algorithm import get_display

# engine tokens, longest-first so [HIGHLIGHT:{0}] wins over {0}
TOKEN = re.compile(
    r"\[[^\]\n]*\]"                 # [TOKEN] / [HIGHLIGHT:{0}] / [Alt:...]
    r"|<[^>\n]*>"                   # <tag>
    r"|\{[^}\n]*\}"                 # {0}
    r"|%[-+ #0]*[\d.*]*(?:hh|h|ll|l|L|z|j|t)?[diouxXeEfgGaAcspn%]"
)
PUA_BASE = 0xE000
_HEB = re.compile(r"[֐-׿]")


def _stash(s: str) -> tuple[str, List[str]]:
    keep: List[str] = []

    def sub(m):
        keep.append(m.group(0))
        return chr(PUA_BASE + len(keep) - 1)

    return TOKEN.sub(sub, s), keep


def _unstash(s: str, keep: List[str]) -> str:
    for i, tok in enumerate(keep):
        s = s.replace(chr(PUA_BASE + i), tok)
    return s


def _segment_to_visual(seg: str) -> str:
    seg = seg.strip()
    if not seg:
        return seg
    masked, keep = _stash(seg)
    vis = get_display(masked, base_dir="R")
    return _unstash(vis, keep)


def to_visual(s: str) -> str:
    """logical Hebrew -> pre-reversed VISUAL, preserving line order + tokens."""
    if not s or not _HEB.search(s):
        return s
    return "\n".join(_segment_to_visual(p) for p in s.split("\n"))


def to_logical(s: str) -> str:
    """Identity — the engine is asked to do the bidi itself."""
    return s


def selftest() -> None:
    cases = [
        ("שלום", "םולש"),
        ("אבגד", "דגבא"),
    ]
    ok = 0
    for src, want in cases:
        got = to_visual(src)
        ok += got == want
        print(f"  {'OK ' if got == want else 'BAD'} {src!r} -> {got!r} (want {want!r})")
    # tokens must survive intact and stay atomic
    for s in ["שלום {0} עולם", "נא ללחוץ [HIGHLIGHT:{0}] כדי להמשיך",
              "שורה אחת\nשורה שתיים", "מהירות: 240 קמ\"ש (Forza)"]:
        v = to_visual(s)
        a, b = sorted(TOKEN.findall(s)), sorted(TOKEN.findall(v))
        same_lines = s.count("\n") == v.count("\n")
        good = a == b and same_lines
        ok += good
        print(f"  {'OK ' if good else 'BAD'} tokens/lines preserved: {s!r} -> {v!r}")
    print(f"selftest {ok}/{len(cases) + 4}")


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
to_logical = _iron_rule(to_logical)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    selftest()
