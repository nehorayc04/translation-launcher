#!/usr/bin/env python3
r"""
aor_rtl.py — Hebrew storage order for AC Origins + the engine's token contract.

🔴🔴 **bidi = NONE for HEBREW ⇒ STORE VISUAL.** Confirmed in-game 2026-07-27: the
user reported the deployed LOGICAL build as "עברית ראי" (mirror Hebrew).

The measurement that made me predict LOGICAL was real but ANSWERED THE WRONG
QUESTION. From the shipped Arabic: 2,101,526 standard-block chars, **0 presentation
forms, 0 bidi controls**, 32,749 lines ending `. ! ? ،` vs 108 starting with one.
That proves the engine shapes and reorders **ARABIC** — it says NOTHING about
whether that pipeline is gated to the Arabic SCRIPT. It is. Origins therefore
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

    python aor_rtl.py selftest
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
# ⚠️ ORIGINS DELTA vs Odyssey: this game also uses `KB_*` keyboard tokens
# (`[KB_LeftShift]`) and stick names (`[RightStick]`, `[CT_StoneCircle RightStick]`),
# none of which are ALL-CAPS, so the Odyssey pattern classified them as PROSE.
# Measured on the Origins corpus; without them a Phase-2 guard would let an agent
# translate a key prompt.
_ENGINE_BR = re.compile(
    r"^(?:CT_[A-Za-z0-9_ ]+|KB_[A-Za-z0-9_]+|[A-Z0-9_]{2,}|\d+"
    r"|(?:Left|Right)(?:Stick|Trigger|Bumper|Shoulder))$"
)

# Engine tokens, in the order they must be matched.
_BR_INNER = (r"CT_[A-Za-z0-9_ ]+|KB_[A-Za-z0-9_]+|[A-Z0-9_]{2,}|\d+"
             r"|(?:Left|Right)(?:Stick|Trigger|Bumper|Shoulder)")
TOKEN = re.compile(
    r"<[^>]{1,120}>"                       # <font face='...'> </font> <i> <style ...>
    r"|\{[^}\n]{1,60}\}"                   # {0} {1} {2} {DD} {HH}
    r"|\[(?:" + _BR_INNER + r")\]"         # engine brackets ONLY
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
    """NOT the shipping transform — kept as the A/B counterpart and to strip stray
    bidi control chars a translator/agent inserted by reflex.

    ⚠️ This docstring used to claim `to_logical` was the shipping transform. The
    in-game A/B settled it the other way on BOTH surfaces (UI round 1, subtitles
    round 2): the LOGICAL row renders MIRRORED. Use `to_visual`."""
    if not s:
        return s
    return BIDI_CTRL.sub("", s)


def to_visual(s: str) -> str:
    """✅ THE SHIPPING TRANSFORM, on both the UI and the subtitle surface (proven
    in-game 2026-07-27 by an A/B pair on one screen). Runs the REAL Unicode Bidi
    Algorithm with an RTL base, engine tokens stashed as atomic LTR runs, and each
    `\\n` segment converted independently so line order is preserved.

    ⚠️ For anything long enough for the engine to wrap, call `to_visual_wrapped`
    instead — the engine wraps in STORAGE order, which inverts the LINE ORDER."""
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


# ------------------------------------------------------- pre-wrap (Phase 2)
#
# 🔴 WHY THIS EXISTS: the engine word-wraps in STORAGE order, so a VISUAL string
# long enough to wrap renders with its LINE ORDER INVERTED (proven in-game: the
# logical start of a paragraph came out on the BOTTOM line). 34.3 % of Origins
# subtitle rows are >60 chars, so this is a build requirement, not a polish item.
# Fix: greedy-wrap the LOGICAL text ourselves, join with the real `\n` the corpus
# already uses, and let `to_visual` convert each line independently.
#
# 📏 BOX_EM_SUBTITLE was MEASURED in-game with a `W‹n›` ruler (2026-07-27):
#     W48 (23.655 em) fit on ONE line          -> box >= 23.655
#     W54 broke after 40 chars and not 50      -> box <  24.355
#   => box ∈ [23.66, 24.35) em, a 3 % bracket. We ship the LOWER bound, because a
#   string of exactly that width was SEEN to fit. Erring low costs at most one
#   extra break per paragraph; erring high lets the engine wrap, which is the one
#   failure that matters. Measured in Heebo advances, which makes it
#   FACE-INDEPENDENT — Heebo is injected into all 9 faces.
BOX_EM_SUBTITLE = 23.66

# A `{NAME}` / `[CT_*]` is substituted at RUNTIME, so its drawn width is unknown
# here; charge a nominal so a line carrying one is not wrapped over-optimistically.
NOMINAL_TOKEN_EM = 4.0
_MARKUP = re.compile(r"<[^>]{1,120}>")      # <font …> / <i> — draws nothing

_METRICS = None


def _metrics():
    """(upm, hmtx, cmap) for the Heebo donor. Lazy: the deploy path never needs it."""
    global _METRICS
    if _METRICS is None:
        import os
        from fontTools.ttLib import TTFont
        here = os.path.dirname(os.path.abspath(__file__))
        f = TTFont(os.path.join(here, "..", "..", "spiderman2", "extracted",
                                "_heebo", "Heebo-Regular.ttf"))
        _METRICS = (f["head"].unitsPerEm, f["hmtx"].metrics, f.getBestCmap())
    return _METRICS


def text_em(s: str) -> float:
    """Rendered width in EMs, token-aware: markup draws nothing, a runtime-
    substituted placeholder is charged NOMINAL_TOKEN_EM, prose is measured."""
    upm, hm, cm = _metrics()
    total = 0.0
    for part in filter(None, re.split(r"(" + TOKEN.pattern + r")", s or "")):
        if _MARKUP.fullmatch(part):
            continue                                    # zero-width markup
        if TOKEN.fullmatch(part):
            total += NOMINAL_TOKEN_EM
            continue
        for ch in part:
            g = cm.get(ord(ch))
            total += (hm[g][0] / upm) if g and g in hm else 0.0
    return total


def wrap_logical(s: str, box_em: float = BOX_EM_SUBTITLE) -> str:
    """Greedy word-wrap LOGICAL text to the box, preserving any breaks already in
    the source. Returns LOGICAL text with real `\\n` separators."""
    if not s:
        return s
    out = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else cur + " " + word
            if not cur or text_em(cand) <= box_em:
                cur = cand
            else:
                out.append(cur)
                cur = word
        out.append(cur)
    return "\n".join(out)


def to_visual_wrapped(s: str, box_em: float = BOX_EM_SUBTITLE) -> str:
    """THE Phase-2 subtitle transform: pre-wrap, then convert each line to VISUAL.
    Order matters — wrapping AFTER the conversion would wrap reversed text."""
    return to_visual(wrap_logical(s, box_em))


# ------------------------------------------------------------------ selftest
def _selftest():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  [{'ok ' if good else 'FAIL'}] {label}\n        got ={got!r}\n        want={want!r}")

    # bracket classification — the measured Origins rule
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

    # ---- pre-wrap (the Phase-2 subtitle path) ------------------------------
    try:
        chk("markup is zero-width", round(text_em("<i></i>"), 6), 0.0)
        chk("token charged nominal", round(text_em("{NAME}"), 3),
            round(NOMINAL_TOKEN_EM, 3))

        long_he = "אני חייב למצוא את הרוצח של בני לפני שהוא יעזוב את אלכסנדריה לתמיד"
        wl = wrap_logical(long_he)
        chk("wrap splits a long line", len(wl.split("\n")) > 1, True)
        chk("no wrapped line exceeds the box",
            max(text_em(l) for l in wl.split("\n")) <= BOX_EM_SUBTITLE, True)
        chk("wrap loses no word", wl.replace("\n", " ").split(), long_he.split())
        chk("wrap keeps an existing break",
            len(wrap_logical("שלום\nעולם").split("\n")), 2)
        chk("short line untouched", wrap_logical("שלום עברית"), "שלום עברית")

        vw = to_visual_wrapped(long_he)
        chk("wrapped visual keeps line count",
            len(vw.split("\n")), len(wl.split("\n")))
        chk("wrapped visual != plain visual", vw != to_visual(long_he), True)
        chk("wrapped visual preserves tokens",
            tokens(to_visual_wrapped("שלום {NAME} <i>עולם</i> [CT_Foo] " + long_he)),
            tokens("שלום {NAME} <i>עולם</i> [CT_Foo] " + long_he))
    except ImportError:                                 # pragma: no cover
        print("  (skipped pre-wrap tests — fontTools missing; use the .venv python)")

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
to_visual_wrapped = _iron_rule(to_visual_wrapped)


if __name__ == "__main__":
    sys.exit(_selftest() if len(sys.argv) > 1 and sys.argv[1] == "selftest"
             else (print(__doc__) or 0))
