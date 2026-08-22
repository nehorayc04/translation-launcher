#!/usr/bin/env python3
r"""
aco_rtl.py — Hebrew storage order for AC Odyssey + the engine's token contract.

🔴🔴 **bidi = NONE for HEBREW ⇒ STORE VISUAL.** Confirmed in-game 2026-07-27: the
user reported the deployed LOGICAL build as "עברית ראי" (mirror Hebrew).

The measurement that made me predict LOGICAL was real but ANSWERED THE WRONG
QUESTION. From the shipped Arabic: 2,101,526 standard-block chars, **0 presentation
forms, 0 bidi controls**, 32,749 lines ending `. ! ? ،` vs 108 starting with one.
That proves the engine shapes and reorders **ARABIC** — it says NOTHING about
whether that pipeline is gated to the Arabic SCRIPT. It is. Odyssey therefore
behaves exactly like its engine sibling **AC Mirage** (and Witcher 3 patch 4.00):
Arabic renders correctly, Hebrew is drawn in storage order.

⚠️ I first read the proof screenshot as "LOGICAL is correct" — the
[[hebrew-screenshot-transcription-trap]]. Transcribing Hebrew from an image
returns READING order, not PIXEL order, so a mirrored line and a correct line
transcribe identically. **The user looking at the screen is the authority.**
The reusable instrument is a DIGIT or Latin island whose SIDE is unambiguous, or
an A/B pair of the same word stored both ways on adjacent rows.

⇒ `to_visual()` is the SHIPPING transform. `to_logical()` is kept only as the
A/B counterpart and to strip stray bidi controls.

── TOKEN CONTRACT (measured over all 59,553 EN strings) ────────────────────────
  <tag>       16,439 occ / 86 distinct  — <font face='DINPro_Bold'> </font> <i> </i>
                                          <style name='Quest'> </style>
  {NAME}       2,705 occ / 88 distinct  — NAMED as well as numeric: {NAME} {0}
                                          {FULLNAME} {TARGET_NAME} {price}
                                          ⚠️ a `\{\d+\}`-only regex MISSES these
  %spec            7 occ                — %l %d
  \n           1,416 occ
  &entity;         0 occ

🔴🔴 BRACKETS ARE OVERLOADED — do NOT treat every `[...]` as a token. Measured
against the game's own PROFESSIONAL Arabic, which TRANSLATES 1,160 of them and
keeps only 30 verbatim:
    ENGINE TOKEN (keep verbatim):  [CT_ParkourUp] [LT] [RT] [NYI] [2105455]
                                   -> inner is CT_*, ALL-CAPS, or all-digits
    TRANSLATOR PROSE (translate):  [sigh] [beat] [&gasp] [&breath] [Save Icon]
                                   [laughing to himself] [[knock out]]
                                   -> Arabic renders [&gasp] as [&شهقة],
                                      [sigh] as [تنهيدة], [[knock out]] as
                                      [[طرح على الأرض]]
A structural guard that compares every bracket verbatim would silently strike out
~1,350 real dialogue lines (the AC2 failure class). Use `is_engine_token()`.

    python aco_rtl.py selftest
"""
import re
import sys

try:
    from bidi.algorithm import get_display
except Exception:                                       # pragma: no cover
    get_display = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HEB = re.compile(r"[֐-׿]")
BIDI_CTRL = re.compile(r"[‎‏‪-‮⁦-⁩]")

# Bracket contents that ARE engine tokens (everything else is prose).
_ENGINE_BR = re.compile(r"^(?:CT_[A-Za-z0-9_]+|[A-Z0-9_]{2,}|\d+)$")

# Engine tokens, in the order they must be matched.
TOKEN = re.compile(
    r"<[^>]{1,120}>"                       # <font face='...'> </font> <i> <style ...>
    r"|\{[^}\n]{1,60}\}"                   # {NAME} {0} {FULLNAME} {price}
    r"|\[(?:CT_[A-Za-z0-9_]+|[A-Z0-9_]{2,}|\d+)\]"   # engine brackets ONLY
    r"|%[-0-9.]*[a-zA-Z]"                  # %d %l
)

_PUA = 0xE000                              # atomic strong-LTR placeholders


def is_engine_token(bracket: str) -> bool:
    """True for `[CT_Foo]` / `[LT]` / `[2105455]`; False for `[sigh]` / `[&gasp]`."""
    inner = bracket[1:-1] if bracket.startswith("[") and bracket.endswith("]") else bracket
    return bool(_ENGINE_BR.match(inner))


def tokens(s: str):
    """Multiset of engine tokens — the structural guard for Phase 2."""
    return sorted(TOKEN.findall(s or ""))


def to_logical(s: str) -> str:
    """The SHIPPING transform for this engine: keep natural order, only strip stray
    bidi control chars a translator/agent may have inserted by reflex."""
    if not s:
        return s
    return BIDI_CTRL.sub("", s)


def to_visual(s: str) -> str:
    """The A/B counterpart used by the menu proof ONLY. Runs the REAL Unicode Bidi
    Algorithm with an RTL base, engine tokens stashed as atomic LTR runs, and each
    `\\n` segment converted independently so line order is preserved."""
    if not s or not HEB.search(s):
        return s
    if get_display is None:
        raise RuntimeError("python-bidi is required (use the repo .venv python)")
    return "\n".join(_seg_to_visual(seg) for seg in s.split("\n"))


def _seg_to_visual(seg: str) -> str:
    seg = seg.strip()                       # edge whitespace becomes a margin indent
    if not seg or not HEB.search(seg):
        return seg
    stash = []

    def _hide(m):
        stash.append(m.group(0))
        return chr(_PUA + len(stash) - 1)

    protected = TOKEN.sub(_hide, seg)
    out = get_display(protected, base_dir="R")
    for i, tok in enumerate(stash):
        out = out.replace(chr(_PUA + i), tok)
    return out


# ------------------------------------------------------------------ selftest
def _selftest():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  [{'ok ' if good else 'FAIL'}] {label}\n        got ={got!r}\n        want={want!r}")

    # bracket classification — the measured Odyssey rule
    for b, want in [("[CT_ParkourUp]", True), ("[LT]", True), ("[2105455]", True),
                    ("[NYI]", True), ("[sigh]", False), ("[&gasp]", False),
                    ("[Save Icon]", False), ("[laughing to himself]", False)]:
        got = is_engine_token(b)
        chk(f"is_engine_token({b})", got, want)

    # token extraction must catch NAMED placeholders and skip prose brackets
    s = "<i>{NAME}</i> hit [CT_ParkourUp] for {0}% [sigh] %d"
    chk("tokens()", tokens(s),
        sorted(["<i>", "{NAME}", "</i>", "[CT_ParkourUp]", "{0}", "%d"]))

    # logical = identity apart from stray controls
    chk("to_logical strips controls", to_logical("‏שלום‫ עולם‬"), "שלום עולם")
    chk("to_logical keeps text", to_logical("שלום {NAME}"), "שלום {NAME}")

    # visual: tokens survive verbatim, line order preserved
    v = to_visual("שלום {NAME}\nעולם")
    chk("to_visual keeps token", "{NAME}" in v, True)
    chk("to_visual keeps 2 lines", len(v.split("\n")), 2)
    chk("to_visual line order", v.split("\n")[1], to_visual("עולם"))
    chk("to_visual no-op on Latin", to_visual("Options"), "Options")

    print("\nSELFTEST", "PASS" if ok else "FAIL")
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

to_logical = _iron_rule(to_logical)
to_visual = _iron_rule(to_visual)


if __name__ == "__main__":
    sys.exit(_selftest() if len(sys.argv) > 1 and sys.argv[1] == "selftest"
             else (print(__doc__) or 0))
