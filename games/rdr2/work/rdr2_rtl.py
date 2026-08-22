#!/usr/bin/env python3
"""rdr2_rtl.py — logical Hebrew -> VISUAL storage for RAGE/RDR2 (no bidi in the engine).

WHY THIS EXISTS (proof #3, 2026-07-19). We first reused GTA V's `gtav_gxt2.visual_line`,
which reverses Hebrew runs and flips the RUN ORDER while keeping every non-Hebrew run
FORWARD. In-game that renders SHORT lines correctly, but it is wrong the moment a
*multi-character neutral run* sits between Hebrew words, because a neutral run belongs to
the RTL flow and must be reversed (and brackets mirrored) — it is not a Latin island.
Screenshot evidence:

    logical   סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה. סוף!
    old       !ףוס. הדוקנ, ףקמ" — תואכרמ) "םיירגוס: (קוסיפ ינמיס     <- ": (" and ") \"" kept
    correct   !ףוס .הדוקנ ,ףקמ — "תואכרמ" (םיירגוס) :קוסיפ ינמיס

So the colon landed before the wrong word, `(סוגריים)` displayed as `)סוגריים(`, and every
comma/period attached to the wrong side. It is invisible on a one-clause menu label (a
1-char neutral run reverses to itself, which is why `?` and `—` looked fine) and wrong on
essentially every real sentence — i.e. on most of the 217,758-line corpus.

THE FIX: run the real Unicode Bidirectional Algorithm with an RTL base (`python-bidi`)
and store its visual output. That is exactly the right tool here precisely BECAUSE the
engine does no bidi at all — we are doing the engine's job offline. Verified identical to
the old function on every case that was already confirmed working in-game (no regression),
and correct on all the cases it got wrong.

RAGE token handling, matched to the shipping Ko Games Arabic mod:
  * LEADING control tokens stay at the very front — all 162,997 of their `~z~` lines start
    with it (0 elsewhere), and UBA would otherwise push a paragraph-initial LTR run to the
    visual end.
  * `~n~` and `~sl:a:b~` are ORDER-PRESERVING SEGMENT SEPARATORS: each segment is converted
    on its own and the separators are re-emitted in place, so line order and subtitle
    timing stay bound to the right text. (Reversing across `~n~` is the classic
    bottom-to-top paragraph bug.)
  * inline tokens (`~COLOR_*~`, `~INPUT_*~`, `~s~`, `~1~`, …) are swapped for private-use
    placeholders so UBA treats each as one atomic LTR run, then restored verbatim.

Also here: `wrap_logical()` — the engine word-wraps in STORAGE order, so a long VISUAL
paragraph wraps with its LINE ORDER INVERTED (proven in-game: markers (1)…(6) ran bottom-up).
Long values must therefore be pre-wrapped into explicit `~n~` lines before conversion.

BRACKETS: `python-bidi` does not apply L4 mirroring, which looks wrong on paper. Verified against
the game's OWN shipping Arabic (also VISUAL-stored): every parenthetical there has `(` at the
visual LEFT and `)` at the visual RIGHT — `(ﺖﻳﻮﺼﺗ) ﺔﻫﺩﺮﻟﺍ ﻦﻣ ﺔﻠﻛﺭ` — which is exactly what
`get_display` produces. So do NOT pre-mirror brackets.

NOTE: run this with the repo `.venv` python — `python-bidi` lives there, so an IDE analyser
pointed at the base interpreter will report `bidi.algorithm` as missing. It is not.
"""
import re
import sys

from bidi.algorithm import get_display

# Measured in-game with the proof-#4 ruler (lines of exactly N chars stamped [N] at BOTH
# ends; the largest N whose markers stay on ONE line is the width). Boot/legal splash:
# 120 fits, 130 wraps  ->  usable 120-129, so 110 leaves a safety margin for wide letters.
# ⚠️ PER-SURFACE. Subtitle and item-description boxes are much narrower and need their own
# ruler run in Phase 2. A char count is only a proxy for pixel width — the exact fix is to
# wrap on the DefineCompactedFont advance widths (they are in the font XML we already build).
WIDTH_SPLASH = 110

_HEB = re.compile(r"[֐-׿]")
_TOKEN = re.compile(r"~[^~]*~")
# separators whose position carries meaning: keep them, and the surrounding order, intact
# ORDER-BEARING separators: the text between them is a line / a subtitle CARD, and the storage
# order IS the play order — so they must never be moved by the UBA.
# `~rp~` was missing here, which reversed the phrase order of 1,567 dialogue values. Proven from
# the shipping Arabic: Ko Games kept every `~rp~` phrase in the English's order, and across 5,692
# of their values the FIRST `~sl:` in storage is the EARLIEST time in 95.6% of cases.
_SEP = re.compile(r"(~n~|\r\n|\n|~sl:[^~]*~|~lr:[^~]*~|~rp~)")
_LEAD = re.compile(r"^(?:~[^~]*~)+")
# 🔴🔴 A LEADING TOKEN MAY ONLY BE PINNED IF IT DRAWS NOTHING.
# `_LEAD` was written for `~z~` (an invisible dialogue marker that must stay first) and it
# matched ANY leading token run — so a VISIBLE token got torn off the string and stapled to the
# visual LEFT, i.e. to the END of the reading order in an RTL line. Measured: 1,110 strings.
#   `~INPUT_FRONTEND_ACCEPT~ כן ~INPUT_FRONTEND_CANCEL~ לא`  (the alert's whole button row)
#   shipped as  ACCEPT-glyph | לא | CANCEL-glyph | כן  — every label paired with the WRONG
#   glyph, which reads in-game as "the Yes/No buttons are gone".
#   `~1~ מתוך ~2~ צמידים נמצאו` put the counter at the far left instead of the sentence start.
# A CONTENT token (a button glyph, a value slot) is text: it must go through the UBA with
# everything else. Only markers and style switches may be pinned.
_CONTENT_TOK = re.compile(r"^~(?:INPUT|INPUTGROUP)[^~]*~$"      # button glyphs
                          r"|^~\d+[a-z$]?~$"                    # value slots ~1~ ~1p~ ~1$~ ~2b~
                          r"|^~a~$")                            # generic value slot
_PUA = 0xE000


def has_hebrew(s):
    return bool(s) and bool(_HEB.search(s))


def _segment_to_visual(seg):
    """UBA-convert ONE segment (no separators inside), tokens held atomic.

    Edges are STRIPPED first. A separator like `~n~` is a line break, so whitespace written
    around it (`"…~n~ שורה …"`) is decorative — but under an RTL base the logical-LEADING
    space moves to the visual END and the logical-TRAILING space moves to the visual START,
    i.e. straight into the left margin, where it renders as a stray indent. (Caught in-game:
    of a three-line header only the middle line — the one padded on BOTH sides — came out
    indented; the Latin-only line was never converted and the third had a space on one side
    only.) Stripping also keeps `align_right` padding exact, since the pad is prepended after
    this returns.
    """
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
    """Logical Hebrew -> the visual byte order the RAGE frontend should draw."""
    if not has_hebrew(s):
        return s
    lead = ""
    m = _LEAD.match(s)
    if m:                       # ~z~ / ~sl:~ prefix stays at the front, like Ko Games
        # ...but stop at the FIRST token that actually draws something: a button glyph or a
        # value slot is content and must be reordered by the UBA with the rest of the line.
        run = _TOKEN.findall(m.group(0))
        keep = 0
        for t in run:
            if _CONTENT_TOK.match(t):
                break
            keep += len(t)
        if keep:
            lead, s = s[:keep], s[keep:]
    parts = _SEP.split(s)
    body = "".join(p if _SEP.fullmatch(p) else _segment_to_visual(p) for p in parts)
    return lead + body


def visible_len(s):
    """Width in characters the player actually SEES.

    `len()` is the wrong ruler for a pre-wrap budget: `~INPUT_FRONTEND_ACCEPT~` is 23 characters
    of storage and draws ONE small glyph, while `~a~` is 3 characters and expands to a runtime
    value. Counting storage made a 40-char line measure 60+ and the wrap fired in the wrong
    places. Charge a token two columns — near enough for a glyph, and it never under-counts.
    """
    return len(_TOKEN.sub("  ", s).strip())


def wrap_logical_vis(text, width):
    """Greedy word-wrap on LOGICAL text by VISIBLE width, preserving any authored `~n~`.

    🔴 THIS IS THE DEFENCE AGAINST INVERTED LINE ORDER. The engine wraps in STORAGE order, so a
    VISUAL-stored paragraph it wraps itself renders bottom-line-first — the reader sees the
    sentence start on the last line and climb. An explicit `~n~` takes that decision away from
    the engine, and it honours ours (proven in-game).

    `width` is the box, in visible chars, measured per key family by `measure_boxes.py` from the
    game's OWN authored breaks and from Ko Games' shipping Arabic. Err NARROW: too narrow costs a
    taller block, too wide costs an unreadable paragraph.

    ⚠️ Measure PER SEGMENT, not per value. `~sl:`/`~rp~` split a value into separate subtitle
    CARDS that are drawn one after another, so a value of three 30-column cards is not a
    90-column line — treating it as one made the wrap fire on values that already fit.
    """
    out = []
    for part in _SEP.split(text):
        if not part or _SEP.fullmatch(part):
            out.append(part)                        # a separator: emitted in place, untouched
            continue
        if visible_len(part) <= width:
            out.append(part)
            continue
        # keep the edge whitespace: it is what separates this chunk from the neighbouring token,
        # and dropping it GLUES two words together across the seam.
        lead = part[:len(part) - len(part.lstrip())]
        tail = part[len(part.rstrip()):]
        words, lines, cur = part.split(), [], ""
        for w in words:
            cand = w if not cur else cur + " " + w
            if visible_len(cand) > width and cur:
                lines.append(cur)
                cur = w
            else:
                cur = cand
        if cur:
            lines.append(cur)
        out.append(lead + "~n~".join(lines) + tail)
    return "".join(out)


_ROW_SPLIT = re.compile(r"(~[^~]*~)")


def to_visual_row(s):
    """A row the engine PARSES into buttons -- pin every token, reverse only the labels.

    `~INPUT_FRONTEND_ACCEPT~ Yes ~INPUT_FRONTEND_CANCEL~ No` is a WIDGET, not prose: the engine
    reads it as "glyph, label, glyph, label". `to_visual` correctly treats a button glyph as
    content and lets the UBA move it (right for a SENTENCE like "Press ~X~ to open"), which here
    destroys the parse -- and the engine then draws NOTHING, so every warning dialog lost its
    Yes/No row with no error anywhere.

    So keep the token skeleton byte-identical to the game's own string and convert each label on
    its own. Edge whitespace is preserved because it is what delimits label from glyph.
    Which keys get this is decided by `scan_parsed_rows.py`, never by hand.
    """
    out = []
    for part in _ROW_SPLIT.split(s):
        if not part:
            continue
        if part.startswith("~") and part.endswith("~") and len(part) > 1:
            out.append(part)                       # a token: never moved, never touched
            continue
        core = part.strip()
        if not core:
            out.append(part)
            continue
        lead = part[:len(part) - len(part.lstrip())]
        tail = part[len(part.rstrip()):]
        out.append(lead + _segment_to_visual(core) + tail)
    return "".join(out)


def wrap_logical(text, width):
    """Greedy word-wrap on the LOGICAL text, joined with ~n~.

    MUST be applied to any value long enough for the engine to wrap it itself: the engine
    wraps in storage order, so an un-broken VISUAL paragraph comes out with its lines in
    reverse order. Explicit ~n~ breaks take that decision away from the engine.
    """
    if len(text) <= width:
        return text
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if len(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return "~n~".join(lines)


def wrap_visual(text, width, *, align_right=False):
    """Pre-wrap a long LOGICAL value and convert each line to visual.

    `align_right` pads each visual line on its LEFT so every line ends at the same right
    edge. That matters because the game's text boxes are LEFT-aligned and JUSTIFY only the
    lines THEY wrap — our explicit `~n~` lines are each treated as a final line, so without
    padding the right edge (= where an RTL reader's eye starts) comes out ragged and the
    paragraph reads as broken. Padding the visual left pushes the text right; we do it AFTER
    the UBA conversion so the algorithm never sees, and never reorders, the spaces.

    Wrap as close to the real box width as possible: a 70-char wrap inside a 120-char box
    leaves every line ~40% short, which is exactly what makes the raggedness obvious.
    """
    out = []
    for line in wrap_logical(text, width).split("~n~"):
        vis = _segment_to_visual(line)
        if align_right:
            vis = " " * max(0, width - len(line)) + vis
        out.append(vis)
    return "~n~".join(out)


def justify_visual_px(text, max_px, face):
    """Pre-wrap + FULL JUSTIFICATION: flush on both edges, like the game's own English.

    Every line except the last is stretched by widening its word GAPS (`rdr2_metrics.justify`)
    rather than padded at the margin, so no line starts indented — leading-space padding
    right-aligns but leaves a ragged left edge, and the paragraph's FIRST line then visibly
    begins with a space next to the flush English paragraphs the game draws.

    The LAST line keeps the leading pad: typographically a final line stays ragged, and in RTL
    "ragged" means flush RIGHT (where reading starts) with the gap on the left.

    ⚠️ Wrap GREEDILY at the full `max_px` here — do NOT balance first. Balancing shrinks the
    lines so their widths match, but justification then stretches every one of them back to
    the full measure, so the shrink turns straight into word gaps: a line balanced to ~6,800
    units stretched to 13,500 rendered with enormous holes between the words (seen in-game).
    Balancing belongs to the RAGGED path (`wrap_visual_px`), where it keeps the margin pads
    small; for justified text a greedy wrap already leaves each line near the measure, so the
    stretch is only a few spaces.

    ⚠️ A line whose gaps would have to open wider than MAX_GAP is NOT justified — it is
    right-aligned instead. That happens when the next word is long and unbreakable (a URL),
    so the line breaks early and the leftover is huge; stretching it then tears "rivers" of
    white through the text. `LEGAL_SPLASH_2` breaks right before
    `http://www.rockstargames.com/socialclub.` (~5,000 units) and needed 7-space gaps.
    Leaving such a line flush-right with the slack in one margin is what a typesetter does.
    """
    from rdr2_metrics import justify, pad_spaces, text_width, wrap_px

    MAX_GAP = 2                      # extra spaces per gap before it reads as a hole
    lines = wrap_px(text, max_px, face)
    out = []
    for i, line in enumerate(lines):
        gaps = max(1, len(line.split()) - 1)
        deficit = max_px - text_width(line, face)
        stretchy = i < len(lines) - 1 and deficit / gaps <= MAX_GAP * 58
        if stretchy:
            out.append(_segment_to_visual(justify(line, max_px, face)))
        else:
            out.append(" " * pad_spaces(line, max_px, face) + _segment_to_visual(line))
    return "~n~".join(out)


def wrap_visual_px(text, max_px, face, *, align_right=True):
    """Pixel-accurate pre-wrap + right-align, using the font's real glyph advances.

    The character-count version (`wrap_visual`) is only an approximation: in this font a
    Hebrew letter advances ~129 units and a space only ~60, i.e. **one letter is worth ~2.2
    spaces**. Padding one space per missing CHARACTER therefore covers barely half the
    distance — which is exactly what the in-game test showed, a paragraph that came out
    centred instead of right-aligned. Measuring in font units fixes both the wrap width and
    the padding.

    `max_px` is in the face's own units (nominalSize per em). Calibrate it from an in-game
    ruler run: the boot splash fits the 120-char ruler = 13537 units and rejects the 130-char
    one = 14849, so ~13500 is a proven-safe budget for that surface.

    ⚠️ The wrap is BALANCED, not greedy. A greedy wrap fills every line to the brim and dumps
    the remainder on the last one, so that line needs a huge left pad (71 spaces was measured)
    and any error in the space advance is multiplied by exactly that count. Balancing evens the
    widths out, which keeps every pad in the ~20-space range. (Balancing belongs HERE and must
    never be combined with justification — there it turns straight into word gaps.)
    """
    from rdr2_metrics import pad_spaces, wrap_px_balanced  # local: keeps metrics optional

    out = []
    for line in wrap_px_balanced(text, max_px, face):
        vis = _segment_to_visual(line)
        if align_right:
            vis = " " * pad_spaces(line, max_px, face) + vis
        out.append(vis)
    return "~n~".join(out)


def _selftest():
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(("PASS " if good else "FAIL ") + name)
        if not good:
            print("   got :", got)
            print("   want:", want)

    # no-regression: the two forms confirmed correct in-game by the menu proof
    chk("plain sentence",
        to_visual("אם אתה קורא עברית תקינה מימין לשמאל - הכל עובד"),
        "דבוע לכה - לאמשל ןימימ הניקת תירבע ארוק התא םא")
    chk("latin + digits island",
        to_visual("בדיקת כיוון RTL: 12 דולרים"),
        "םירלוד RTL: 12 ןוויכ תקידב")

    # the proof-#3 failures
    v = to_visual("סימני פיסוק: (סוגריים) \"מרכאות\" — מקף, נקודה. סוף!")
    chk("brackets mirrored", "(םיירגוס)" in v, True)
    chk("colon after first word", v.endswith(":קוסיפ ינמיס"), True)

    # tokens
    chk("leading ~z~ kept at front", to_visual("~z~שלום עולם").startswith("~z~"), True)
    v = to_visual("~z~~sl:0.0:1.4~אני הולך.~sl:~ואז חזרתי.")
    chk("~sl: intact", "~sl:0.0:1.4~" in v and "~sl:~" in v and "~:sl~" not in v, True)
    chk("inline token intact",
        "~INPUT_JUMP~" in to_visual("לחץ ~INPUT_JUMP~ כדי לקפוץ"), True)

    # ~n~ keeps line ORDER (the bottom-to-top paragraph bug)
    v = to_visual("שורה ראשונה~n~שורה שנייה")
    chk("line order preserved", v.split("~n~")[0], to_visual("שורה ראשונה"))

    # pure-ASCII / token-only values are untouched
    chk("ascii untouched", to_visual("Rockstar Games ~n~ 2019"), "Rockstar Games ~n~ 2019")

    # whitespace written around a ~n~ must NOT become a left-margin indent
    chk("no stray indent from '~n~ '",
        all(not s.startswith(" ") for s in to_visual("שורה אחת ~n~ שורה שתיים ~n~ סוף").split("~n~")),
        True)
    chk("edge spaces stripped", to_visual("  שלום  "), to_visual("שלום"))

    # wrap
    w = wrap_logical(" ".join(["מילה"] * 40), 30)
    chk("wrap splits", w.count("~n~") > 0, True)
    chk("wrap keeps words", w.replace("~n~", " ").split(), [" ".join(["מילה"] * 40)][0].split())
    chk("short not wrapped", wrap_logical("קצר", 30), "קצר")

    print("\nALL PASS" if ok else "\nFAILURES")
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
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(_selftest())
