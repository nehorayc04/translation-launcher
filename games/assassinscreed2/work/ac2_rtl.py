#!/usr/bin/env python3
r"""
AC2 RTL visual-reversal transform.

AC2's Scimitar engine (2009) has NO bidi/RTL layout (it ships only LTR European
locales). The proven fan-translation method (Persian/Arabic AC2 patches) is to
bake direction into the DATA: store each line in *visual* order so the strictly
left-to-right engine renders it as correct RTL on screen.

Hebrew (unlike Arabic) needs NO letter-joining/reshaping — only visual reversal.
A line is mostly Hebrew with embedded LTR islands (numbers, Latin words, tags and
placeholders) that must keep their own left-to-right order. So the algorithm is a
minimal bidi for an RTL base direction:

  1. Protect opaque tokens (tags/placeholders/escapes) as atomic LTR units.
  2. Reverse the whole line.
  3. Un-reverse every maximal LTR run (Latin letters, digits, atoms) so numbers
     and Latin words read forward again.
  4. Mirror paired punctuation ( ) [ ] { } < > so brackets point the right way.
  5. Restore the protected tokens.

`to_visual(logical_he)` is idempotent-safe in the sense that the stored string is
what the engine draws; re-running on already-reversed text is NOT supported (run
exactly once, at build time, on the logical Hebrew).

This module has zero third-party deps. If a future line needs full UAX#9 bidi,
`python-bidi` can be dropped in behind the same `to_visual` signature.
"""
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HEBREW = lambda c: "֐" <= c <= "׿" or "יִ" <= c <= "ﭏ"
def LTR_CHAR(c):
    return c.isascii() and c.isalnum()  # Latin letters + digits read forward

# Opaque tokens that must survive verbatim AND act as LTR islands.
TOKEN_RE = re.compile(
    r"""(
        \\n | \\t | \\r            # escapes
      | %[#0-9.+\- ]*[sdiufFgGxXeEoc%]   # printf specs
      | \{[^{}]*\}               # {VALUE} / {0} style
      | \[[^\[\]]*\]             # [TOKEN] / [LF] style
      | <[^<>]+>                 # <tag> markup
      | &[a-zA-Z]+;              # &rlm; html entities
    )""",
    re.VERBOSE,
)

_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[",
           "{": "}", "}": "{", "<": ">", ">": "<"}

# Private-use placeholders for protected tokens (each is one LTR atom).
_PUA_BASE = 0xE000


def _protect(s):
    toks = []

    def sub(m):
        toks.append(m.group(0))
        return chr(_PUA_BASE + len(toks) - 1)
    return TOKEN_RE.sub(sub, s), toks


def _is_ltr_unit(c):
    return LTR_CHAR(c) or (_PUA_BASE <= ord(c) < _PUA_BASE + 0x1000)


def to_visual(logical: str) -> str:
    """Convert a logical Hebrew (mixed) string to visual RTL order for storage."""
    if not logical:
        return logical
    protected, toks = _protect(logical)

    rev = protected[::-1]
    # un-reverse LTR runs (Latin/digits/atoms) so they read forward
    out = []
    i, n = 0, len(rev)
    while i < n:
        if _is_ltr_unit(rev[i]):
            j = i
            while j < n and _is_ltr_unit(rev[j]):
                j += 1
            out.append(rev[i:j][::-1])
            i = j
        else:
            ch = rev[i]
            out.append(_MIRROR.get(ch, ch))   # mirror brackets
            i += 1
    visual = "".join(out)

    # restore tokens (placeholders are single chars in `visual`)
    def restore(m):
        return toks[ord(m.group(0)) - _PUA_BASE]
    visual = re.sub("[-]", restore, visual)
    return visual


# ----------------------------------------------------------------------------
def _selftest():
    cases = [
        # (logical, expected visual). '+' marks the human-checked expected order.
        ("שלום", "םולש"),
        ("עברית", "תירבע"),
        # number stays forward, Hebrew reverses, whole line RTL:
        ("יש לי 25 מטבעות", "תועבטמ 25 יל שי"),
        # Latin word kept forward inside Hebrew:
        ("טען Ezio עכשיו", "וישכע Ezio ןעט"),
        # bracket mirrors:
        ("(שמור)", "(רומש)"),
        # token preserved verbatim and placed as LTR island:
        ("נותרו {0} חיים", "םייח {0} ורתונ"),
        ("לחץ [A] לקפיצה", "הציפקל [A] ץחל"),
    ]
    ok = True
    for logical, expected in cases:
        got = to_visual(logical)
        flag = "OK " if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"  [{flag}] {logical!r}\n         got={got!r}\n         exp={expected!r}")
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


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
