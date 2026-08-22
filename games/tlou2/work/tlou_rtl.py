#!/usr/bin/env python3
r"""
tlou_rtl.py - RTL visual-reversal transform for The Last of Us Part I.

TLOU Part I ships NO Arabic/RTL locale, and the Naughty Dog engine performs NO
bidi reordering and NO shaping - it draws glyphs in raw byte order and honors
literal line breaks (confirmed by the ND-Arabic-localization case study + the
existing Arabic fan-translations, which all use an offline "RTL baker"). So we
hijack an LTR slot and bake direction into the DATA: store each line in *visual*
order so the strictly-left-to-right engine renders it as correct RTL.

Hebrew needs NO cursive joining/shaping (unlike Arabic) - only visual reversal +
holding LTR islands (Latin words, numbers, tokens) forward + mirroring brackets.

TLOU inline token grammar (must survive verbatim):
  MARKUP tags (styling spans / breaks) - kept verbatim AND in LOGICAL order so an
    <open>...</open> pair still wraps the reversed text:
      <font face="default" color="t2-white">...</font>  <br>  <break/>  <hang></hang>
  ISLAND tokens (button glyphs / bracket vars / printf) - LTR atoms that mirror to
    the correct visual position, like a Latin word or number:
      |gen:interact|  |menu:select|  |l3|  |T|  |@01|  [A]  [TEXT]  %d  {value}

The translator/agents ALWAYS work in LOGICAL Hebrew; to_visual() is applied ONLY
at build time, exactly once, per line. Multi-line values are split on real
newlines / literal `\n` and each segment reversed independently (line order kept).

Zero third-party deps.  `python tlou_rtl.py` runs the self-test.

NOTE: whether the engine wants markup tags in LOGICAL or reversed order, and
whether it wants text VISUAL at all, is the Phase-1 MENU-PROOF question - this
transform is the expected default; confirm in-game before the full run.
"""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _is_ltr_char(c):
    return c.isascii() and c.isalnum()   # Latin letters + digits read forward


MARKUP_RE = r"</?font[^>]*>|<br\s*/?>|<break\s*/?>|</?hang>|<[^<>]+>"
ISLAND_RE = r"\|[^|]+\||\[[^\[\]]*\]|%[#0-9.+\- ]*[sdiufFgGxXeEoc%]|\{[^{}]*\}|&[a-zA-Z]+;"
TOKEN_RE = re.compile("(" + MARKUP_RE + ")|(" + ISLAND_RE + ")")

_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[",
           "{": "}", "}": "{", "<": ">", ">": "<"}

_PUA_LO = 0xE000
_PUA_HI = 0xF8FF
_PUA_RE = re.compile("[-]")


def _protect(s):
    toks = []          # list of (text, is_markup)

    def sub(m):
        toks.append((m.group(0), m.group(1) is not None))
        return chr(_PUA_LO + len(toks) - 1)
    return TOKEN_RE.sub(sub, s), toks


def _is_atom(c):
    o = ord(c)
    return _is_ltr_char(c) or (_PUA_LO <= o <= _PUA_HI)


def _reverse_segment(seg: str) -> str:
    protected, toks = _protect(seg)
    rev = protected[::-1]
    out, i, n = [], 0, len(rev)
    while i < n:
        if _is_atom(rev[i]):                 # keep LTR runs (Latin/digits/tokens) forward
            j = i
            while j < n and _is_atom(rev[j]):
                j += 1
            out.append(rev[i:j][::-1])
            i = j
        else:
            out.append(_MIRROR.get(rev[i], rev[i]))   # mirror brackets, pass Hebrew/space
            i += 1
    visual = "".join(out)
    # Restore tokens. Markup tags re-emit in LOGICAL order (scanning output L->R)
    # so a wrapping pair keeps open-before-close around the reversed text; island
    # tokens restore to their own (mirror-positioned) value.
    markup_seq = [t for t, mk in toks if mk]
    mk_i = [0]

    def restore(m):
        text, is_mk = toks[ord(m.group(0)) - _PUA_LO]
        if is_mk:
            v = markup_seq[mk_i[0]]
            mk_i[0] += 1
            return v
        return text
    return _PUA_RE.sub(restore, visual)


_NL_RE = re.compile(r"(\r\n|\n|\\n)")   # real newlines OR literal backslash-n


def to_visual(logical: str) -> str:
    """Logical Hebrew (mixed LTR islands) -> visual RTL for storage. Run exactly
    once, at build time, on the logical Hebrew."""
    if not logical:
        return logical
    parts = _NL_RE.split(logical)
    return "".join(p if _NL_RE.fullmatch(p) else _reverse_segment(p) for p in parts)


# ----------------------------------------------------------------------------
def _selftest():
    cases = [
        ("שלום", "םולש"),                        # shalom -> reversed
        ("עברית", "תירבע"),            # ivrit -> reversed
        ("יש לי 25 מטבעות",             # number stays forward
         "תועבטמ 25 יל שי"),
        ("טען Ezio עכשיו",                        # Latin word forward
         "וישכע Ezio ןעט"),
        ("(שמור)", "(רומש)"),                     # bracket mirrors
        ("לחץ [A] לקפיצה",                   # [A] island preserved
         "הציפקל [A] ץחל"),
        ("לחץ |gen:interact| לפתיחה",        # pipe glyph preserved
         "החיתפל |gen:interact| ץחל"),
        ('<font color="t2-red">סכנה</font>',                          # wrapping pair logical
         '<font color="t2-red">הנכס</font>'),
        ("שלום\\nעולם",                           # newline: order kept
         "םולש\\nםלוע"),
    ]
    ok = True
    for logical, expected in cases:
        got = to_visual(logical)
        flag = "OK " if got == expected else "FAIL"
        ok = ok and got == expected
        print(f"  [{flag}] {logical!r}")
        if got != expected:
            print(f"          got={got!r}\n          exp={expected!r}")
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
