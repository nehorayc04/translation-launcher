#!/usr/bin/env python3
"""rdr2_metrics.py — real glyph ADVANCE widths from the Scaleform font, for pixel-accurate
line wrapping and right-alignment.

WHY. Proof #5 wrapped and padded by CHARACTER COUNT. In a proportional font that is wrong in
both directions: a 115-char wrap can overflow or under-fill depending on the letters, and
padding a short line with `width - len(line)` spaces only pushes it to about the MIDDLE —
a space advances 90 units while an average Hebrew letter advances ~150-200, so the padding
buys roughly half the distance it needs. (That is exactly what the in-game screenshot showed:
the "right-aligned" paragraph landed centred.)

The font we build already carries the answer. Each `DefineCompactedFont` face in the FFdec
XML ends with a `glyphInfo` array:

    <item type="GlyphInfoType" advanceX="90"  glyphCode="32"/>   <- space
    <item type="GlyphInfoType" advanceX="32"  glyphCode="46"/>   <- period
    <item type="GlyphInfoType" advanceX="270" glyphCode="77"/>   <- 'M'

in units of the face's `nominalSize` (256). Summing those gives an exact relative width for
any string, so we can wrap to a real box width and pad to a real right margin.

The XML is ~350 MB, so `build` streams it once and caches a small JSON; everything else
reads the cache.

    python rdr2_metrics.py build <font.xml> [metrics.json]
    python rdr2_metrics.py show  [metrics.json]
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "font_metrics.json")

_FONT = re.compile(r'<item type="FontType"[^>]*ascent="(?P<asc>-?\d+)"[^>]*'
                   r'fontName="(?P<name>[^"]*)"[^>]*nominalSize="(?P<nom>\d+)"')
_GI = re.compile(r'<item type="GlyphInfoType" advanceX="(?P<adv>-?\d+)"[^>]*glyphCode="(?P<code>\d+)"')


def build(xml_path, out_path=CACHE):
    """Stream the FFdec XML once -> {face: {nominalSize, advances{code:adv}}}."""
    faces, cur = {}, None
    with io.open(xml_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _FONT.search(line)
            if m:
                cur = m.group("name")
                faces.setdefault(cur, {"nominalSize": int(m.group("nom")),
                                       "ascent": int(m.group("asc")), "advances": {}})
                continue
            if cur:
                g = _GI.search(line)
                if g:
                    faces[cur]["advances"][g.group("code")] = int(g.group("adv"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(faces, f)
    return faces


_cache = None


def load(path=CACHE):
    global _cache
    if _cache is None:
        with open(path, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def face_names(path=CACHE):
    return list(load(path))


def _adv_table(face, path=CACHE):
    d = load(path)
    if face not in d:
        raise KeyError(f"no such face {face!r}; have {list(d)[:6]}…")
    return d[face]["advances"], d[face]["nominalSize"]


def text_width(s, face, path=CACHE):
    """Width of `s` in font units (nominalSize per em). Unknown glyph -> the face's mean.

    The SPACE must come from `space_width()`, not the raw table: justification injects spaces
    whose count is computed with the measured advance, so if measuring them back used the
    table value instead, every injected space would add a hidden 2 units and a line with ~90
    of them would silently overshoot the box by ~180 (observed) and get wrapped by the engine
    — reintroducing the inverted line order. Internal consistency matters more here than which
    of the two numbers is closer to the truth.
    """
    adv, _ = _adv_table(face, path)
    if not adv:
        return 0
    mean = sum(adv.values()) / len(adv)
    sp = space_width(face, path)
    return sum(sp if c == " " else adv.get(str(ord(c)), mean) for c in s)


# Measured IN-GAME by the proof-#7 ladder (rows of N spaces followed by the number N; the
# reference row above them is the known-to-fit 120-char ruler = the true right margin):
#   N=200  -> one line, stops ~110px short of the margin
#   N=240+ -> OVERFLOWS and wraps, dropping the number alone on the next line
# so a full box is ~225 spaces, i.e. space ≈ (13500 - width("200")) / 225 ≈ 58 units against
# the 60 the face table predicts — the model is right to within ~3%, with NO face assumption.
# That 3% is why a 71-space pad missed by ~50px and a 22-space pad misses by ~3px: always
# BALANCE the wrap so no single line carries a huge pad.
SPACE_UNITS_MEASURED = 58


def space_width(face, path=CACHE):
    """Advance of a space. Prefers the in-game measurement over the face-table guess, because
    we do not know which of the 18 faces a given surface renders with (they disagree 52-60)."""
    if SPACE_UNITS_MEASURED:
        return SPACE_UNITS_MEASURED
    adv, _ = _adv_table(face, path)
    return adv.get("32", 90)


def wrap_px(text, max_px, face, path=CACHE):
    """Greedy word-wrap on the LOGICAL text to a real pixel budget. Returns a list of lines."""
    lines, cur = [], ""
    for w in text.split():
        cand = w if not cur else cur + " " + w
        if cur and text_width(cand, face, path) > max_px:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def wrap_px_balanced(text, max_px, face, path=CACHE):
    """Wrap into the SAME number of lines as `wrap_px`, but with the widths EVENED OUT.

    A greedy wrap fills every line to the brim and dumps the remainder on the last one, so a
    paragraph ends up as e.g. 13224 / 13272 / 13414 / 9268 units. That last line then needs a
    huge space pad to reach the right margin (71 spaces), and any error in the space advance
    is multiplied by exactly that count — which is why the final line rendered ~50px short
    while the first three looked perfectly flush.

    Balancing to 4 lines of ~12.3k each drops every pad into the ~20-space range, so the same
    relative error becomes visually negligible. Binary-search the smallest target width that
    still yields the original line count.
    """
    n = len(wrap_px(text, max_px, face, path))
    longest_word = max((text_width(w, face, path) for w in text.split()), default=0)
    lo, hi = int(longest_word), int(max_px)
    best = wrap_px(text, max_px, face, path)
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = wrap_px(text, mid, face, path)
        if len(cand) <= n:
            best, hi = cand, mid - 1
        else:
            lo = mid + 1
    return best


def justify(line, max_px, face, path=CACHE):
    """Stretch ONE logical line to `max_px` by widening the gaps BETWEEN words.

    Leading-space padding right-aligns a line but leaves its left edge ragged, so the first
    line of a paragraph visibly starts indented. The game's own English paragraphs are
    JUSTIFIED — flush on both edges — so Hebrew has to be too, or it reads as misaligned next
    to them. Real justification puts the slack in the word gaps instead of at the margin.

    Apply to every line EXCEPT the last: by normal typographic rule the final line stays
    ragged (in RTL that means flush right, ragged left), and stretching it would space the
    words out grotesquely.
    """
    words = line.split()
    gaps = len(words) - 1
    if gaps <= 0:
        return line
    # floor, never round: overshooting the budget can push the line into an engine wrap,
    # which would re-introduce the inverted-line-order bug we pre-wrap to avoid.
    extra = int((max_px - text_width(line, face, path)) / space_width(face, path))
    if extra <= 0:
        return line
    base, rem = divmod(extra, gaps)
    out = words[0]
    for i, w in enumerate(words[1:]):
        out += " " * (1 + base + (1 if i < rem else 0)) + w
    return out


def pad_spaces(line, max_px, face, path=CACHE):
    """How many SPACES to prepend to the VISUAL line so it ends at the right margin."""
    deficit = max_px - text_width(line, face, path)
    # floor, never round — see justify(): overshooting the budget risks an engine wrap.
    return max(0, int(deficit / space_width(face, path)))


def _demo():
    d = load()
    print(f"{len(d)} faces cached")
    for name, info in list(d.items())[:20]:
        print(f"  {name:<28} nominal={info['nominalSize']:>4} glyphs={len(info['advances']):>4}")
    f0 = next(iter(d))
    print(f"\nsample widths on {f0!r} (units, nominal={d[f0]['nominalSize']}):")
    for s in ("space", " "), ("period", "."), ("aleph", "א"), ("word", "בדיקה"):
        print(f"  {s[0]:<8} {text_width(s[1], f0):>8.0f}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        out = sys.argv[3] if len(sys.argv) > 3 else CACHE
        faces = build(sys.argv[2], out)
        print(f"cached {len(faces)} faces -> {out} ({os.path.getsize(out):,} B)")
        for n, i in faces.items():
            print(f"  {n:<28} nominal={i['nominalSize']:>4} glyphs={len(i['advances']):>4}")
    else:
        _demo()
