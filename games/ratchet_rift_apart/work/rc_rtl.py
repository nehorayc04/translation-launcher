"""R&C Rift Apart — store-VISUAL RTL transform for the full corpus (§8b).

The engine does NO bidi (proven in-game: bidi A/B, 2026-07-12), so Hebrew must be
stored PRE-REVERSED. A hand-rolled run-reversal is correct only for single-word menu
labels; on real subtitles it mis-places neutral punctuation (a comma lands on the wrong
side) and mirrors brackets wrong. So we run the REAL Unicode Bidi Algorithm and protect
the engine's markers, exactly like games/rdr2, games/acmirage, games/acorigins.

Two marker classes:
  * STRUCTURAL, order-bearing  — <ts="a;b">, <name="X">, <br>. These separate independent
    display chunks (a subtitle's timed segments / line breaks). We split on them and
    convert each text chunk on its own, re-emitting the markers in their original order,
    so segment order is NEVER flipped.
  * INLINE atomic — <span..>, </span>, <h2>, [TOKEN], {VALUE}, %d. Inside a chunk these are
    stashed as PUA placeholders so the UBA treats each as one neutral unit, then restored.

Input/output are the loc-NATIVE escaped form (&quot; / &amp;): we unescape, transform,
re-escape, so <ts=&quot;..&quot;> round-trips untouched.

    python rc_rtl.py            # run the selftest
"""
import re

try:
    from bidi.algorithm import get_display as _bidi
except Exception:                                   # pragma: no cover
    _bidi = None

HEBREW = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'(<ts="[^"]*">|<name="[^"]*">|<br\s*/?>)')
INLINE = re.compile(r'<[^>]+>|\[[A-Za-z][A-Za-z0-9_]+\]|\{[^}]*\}|%[#0-9.\-+]*[dsifuxX]')
PUA0 = 0xE000


def _unesc(s): return s.replace("&quot;", '"').replace("&quot", '"').replace("&amp;", "&")
def _esc(s):   return s.replace("&", "&amp;").replace('"', "&quot;")


def _display(text):
    """UBA on a single display chunk (RTL base), with inline tokens PUA-protected."""
    if not HEBREW.search(text):
        return text                                 # Latin / tag-only chunk stays forward
    toks = []
    def stash(m):
        toks.append(m.group(0))
        return chr(PUA0 + len(toks) - 1)
    protected = INLINE.sub(stash, text)
    try:
        vis = _bidi(protected, base_dir='R')
    except TypeError:                               # older python-bidi signature
        vis = _bidi(protected)
    for i, t in enumerate(toks):
        vis = vis.replace(chr(PUA0 + i), t)
    return vis


def to_visual(escaped):
    """Loc-native escaped Hebrew (logical) -> loc-native escaped VISUAL (pre-reversed)."""
    s = _unesc(escaped)
    out = []
    for part in STRUCT.split(s):
        if not part:
            continue
        if STRUCT.fullmatch(part):
            out.append(part)                        # structural marker: fixed position
        else:
            out.append(_display(part))              # text chunk: UBA
    return _esc("".join(out))


# ------------------------------------------------------------------ selftest
def _selftest():
    assert _bidi is not None, "python-bidi not installed"
    def tok_multiset(s):
        return sorted(re.findall(r'<[^>]+>|\[[A-Za-z][A-Za-z0-9_]+\]|\{[^}]*\}|%[#0-9.\-+]*[dsifuxX]',
                                 _unesc(s)))
    cases = [
        # (logical escaped, human note)
        ('שלום, עולם!', 'comma stays inside the RTL flow'),
        ('<ts=&quot;0;1.5&quot;>הם לא יכולים לעלות!', 'single ts preserved'),
        ('<ts=&quot;0;1.4&quot;>שלום <ts=&quot;1.5;3&quot;>עולם', 'two ts: order preserved'),
        ('<name=&quot;NCPA&quot;><ts=&quot;0;5&quot;>ברוכים הבאים', 'name+ts prefix intact'),
        ('שלום world 42!', 'Latin island + digits forward'),
        ('לחצו [BTN_SHORTCUT_1] כדי לדלג', 'button token atomic'),
        ('<span class=&quot;emphasis&quot;>מגנים</span> קשים.', 'inline span emphasis'),
        ('IAN GARGLE', 'Latin-only credit unchanged'),
    ]
    for esc, note in cases:
        v = to_visual(esc)
        assert tok_multiset(esc) == tok_multiset(v), f"TOKEN DRIFT: {esc!r} -> {v!r}"
        # every structural marker preserved verbatim (count)
        for rx in (r'<ts="[^"]*">', r'<name="[^"]*">'):
            assert len(re.findall(rx, _unesc(esc))) == len(re.findall(rx, _unesc(v))), \
                f"MARKER DROP: {esc!r} -> {v!r}"
        # no stray PUA leaked
        assert not any(PUA0 <= ord(c) <= PUA0 + 500 for c in v), f"PUA leak: {v!r}"
        print(f"  ok  {esc!r}\n      -> {v!r}   ({note})")
    # the decisive property: a Hebrew word comes out reversed (VISUAL storage)
    assert to_visual('שלום') != 'שלום' and to_visual('שלום')[::-1].startswith('של'), "not reversed"
    # Latin-only is byte-identical
    assert to_visual('IAN GARGLE') == 'IAN GARGLE'
    print("\nselftest PASS (8/8)")


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
