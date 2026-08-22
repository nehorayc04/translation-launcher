"""
gl_rtl.py — VISUAL bidi transform for 007 First Light (Glacier engine does NO bidi,
confirmed from the community Arabic mod bundling python-bidi + arabic_reshaper).

Hebrew needs NO letter-shaping (unlike Arabic) — only visual reordering:
  - reverse each Hebrew run AND the order of runs on a line
  - keep Latin / digits / {tokens} / <tags> / %specs forward (they are LTR islands)
  - split on <br/>, <br>, \\n so multi-line strings keep line order
  - mirror bracket pairs that wrap a reversed run

Store LOGICAL during translation; apply to_visual ONLY at build time.
Modeled on the proven WD2/GTA `visual_line`.
"""
import re

# Hebrew block U+0590-U+05FF + Hebrew presentation forms U+FB1D-U+FB4F
HEBREW = "֐-׿יִ-ﭏ"
_HEB_RE = re.compile(f"[{HEBREW}]")
_HEB_CH = re.compile(f"[{HEBREW}]$")   # single-char test
# LTR islands kept forward: tags, {tokens}, [tokens], %d/%s specs, &entities;
_TOKEN = re.compile(
    r"(<[^>]+>|\{[^}]*\}|\[[^\]]*\]|%[-0-9.]*[a-zA-Z]|&[a-zA-Z#0-9]+;)")
_LINE_SPLIT = re.compile(r"(<br\s*/?>|\r\n|\n)")
_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{",
           "<": ">", ">": "<", "«": "»", "»": "«"}


def _has_hebrew(s):
    return bool(_HEB_RE.search(s))


def _is_heb_char(ch):
    return bool(_HEB_CH.match(ch))


def _visual_segment(seg: str) -> str:
    """Reverse a single line segment for a NON-bidi engine, keeping LTR islands intact."""
    if not _has_hebrew(seg):
        return seg
    parts = _TOKEN.split(seg)
    runs = []          # (text, kind) kind: 'island' | 'heb' | 'ltr'
    for k, part in enumerate(parts):
        if part == "":
            continue
        if k % 2 == 1:                     # protected LTR island (token/tag)
            runs.append((part, "island"))
            continue
        # split into 3 run classes: hebrew / whitespace / other-ltr.
        # whitespace is its own run so a space BETWEEN two words stays between
        # them after the run order is reversed (else it drifts to the edge).
        def _cls(ch):
            if _is_heb_char(ch):
                return "heb"
            if ch.isspace():
                return "ws"
            return "ltr"
        buf = ""
        cur = None
        for ch in part:
            c = _cls(ch)
            if cur is None:
                cur = c
            if c == cur:
                buf += ch
            else:
                runs.append((buf, cur))
                buf = ch
                cur = c
        if buf:
            runs.append((buf, cur))
    out = []
    for text, kind in reversed(runs):      # reverse run ORDER
        if kind == "heb":
            out.append("".join(_MIRROR.get(c, c) for c in reversed(text)))
        else:
            out.append(text)               # island / ltr kept forward
    return "".join(out)


def to_visual(s: str) -> str:
    """Apply the visual transform to a full (possibly multi-line) string."""
    if not _has_hebrew(s):
        return s
    segs = _LINE_SPLIT.split(s)
    return "".join(seg if _LINE_SPLIT.fullmatch(seg) else _visual_segment(seg)
                   for seg in segs)


def _selftest():
    # (source_logical, expected_visual)  -- expected uses reversed Hebrew
    cases = [
        ("שלום עולם",       # "שלום עולם"
         "םלוע םולש"),      # "םלוע םולש"
        ("טען משחק",             # "טען משחק"
         "קחשמ ןעט"),            # "קחשמ ןעט"
        ("פרק 5",                                    # "פרק 5"
         "5 קרפ"),                                   # "5 קרפ"
    ]
    ok = 0
    for src, exp in cases:
        got = to_visual(src)
        good = got == exp
        ok += good
        print(f"  {src!r} -> {got!r}  {'OK' if good else 'FAIL exp '+repr(exp)}")
    # token + multiline preservation (no strict expected, just show)
    for s in ("שגיאה: {0}",
              "קו 1<br/>קו 2"):
        print(f"  {s!r} -> {to_visual(s)!r}")
    print(f"selftest: {ok}/{len(cases)} exact")


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
    _selftest()
