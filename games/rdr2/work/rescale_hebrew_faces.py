#!/usr/bin/env python3
"""rescale_hebrew_faces.py — scale each face's Hebrew glyphs to THAT FACE'S OWN cap height.

🔴 THE DEFECT (measured with scan_faces.py, never assumed): the original `+27 Hebrew into
every face` pass injected the donor at ONE flat size -- every one of the 17 non-Lino faces
carries a Hebrew median box height of exactly **134**, while their own Latin caps run
179..274. So every Hebrew string on those surfaces renders at ~55-75 % of the size the same
string would have in English. On the death screen that turns the huge "DEAD" headline into
something the size of a menu row, which is exactly what the player reported.

RDR Lino is the one face already correct (Hebrew 214 vs Latin 202 = 1.06) because the
stencil rebuild sized it from that face's own 'M'. This script generalises that rule to the
rest -- and deliberately DOES NOT TOUCH RDR Lino, so the pause menu the user already
approved cannot regress.

WHY SCALE INSTEAD OF RE-INJECT: the letterFORMS were never the complaint, only the size.
Scaling the shipped contours keeps the approved shapes byte-for-byte and changes exactly one
thing, so a regression can only be a size regression.

THE ANCHOR IS A FLAT-TOPPED LATIN CAP (E F H I L T), not 'M' and not the A-Z median: on a
script/display face ('1871 Dreamer Script') a swash or a round overshoot inflates those by
20 %+, and Hebrew has no ascenders or descenders to absorb it. Faces whose Latin is
degenerate (a numbers-only face) fall back to their DIGIT height.

GEOMETRY: contours are delta-encoded from moveToX/moveToY, and edge kind 3 is a quad curve
carrying control+anchor deltas. Reconstruct the ABSOLUTE path, scale, round each absolute
point, and re-emit deltas between the ROUNDED absolutes -- rounding each delta independently
would let the error accumulate along the contour and visibly warp a letter.

    python rescale_hebrew_faces.py report            # the plan, no writes
    python rescale_hebrew_faces.py apply <out.xml>   # write the rescaled dump
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
FI = os.path.join(HERE, "_fontinspect")
SRC = os.path.join(FI, "stencil_full.xml")          # == the currently deployed .gfx
OUT = os.path.join(FI, "rescaled_full.xml")

HEB_LO, HEB_HI = 0x05D0, 0x05EA
FLAT_CAPS = [ord(c) for c in "EFHILT"]              # no overshoot, no swash
DIGITS = list(range(0x30, 0x3A))
# 🔴 SKIP_FACES IS NOW EMPTY, AND THAT WAS THE WHOLE PAUSE-MENU BUG.
# RDR Lino was excluded on the theory that "the menu the user already approved must not
# regress" -- but the user's very FIRST report said the post-death menu "renders huge
# letters", i.e. the menu was NEVER approved. Lino sat at 1.06 through all three builds and
# was therefore the one surface that could not change, which is exactly why the report came
# back "still too big" every time. The user settled it outright: "שהפונט התפריט יהיה אותו
# דבר כמו התפריט הפתיחה" -- the pause menu must match the start menu, and the start menu is
# drawn by one of the faces already at TARGET_RATIO. So Lino joins them.
# UNIVERSAL: an exclusion added to protect an "already-approved" surface must be re-checked
# against what the user ACTUALLY approved -- a wrong exclusion is invisible, because the
# excluded surface reports the same defect after every build and reads as "the fix didn't
# work" rather than "the fix never reached it".
SKIP_FACES = set()
# 🔴 CAP-MATCHING READS OVERSIZED — settled by TWO in-game observations, not by taste.
#   ratio 0.71 (the original flat 134): the menu looked fine, the death headline was too small.
#   ratio 1.06 (RDR Lino's own):        the death headline is correct, every menu is too big.
# Both reports are true, so the answer is between them. Hebrew is UNICASE and dense: at equal
# cap height it carries far more ink per line than Latin, and RDR2's UI faces have no real
# lowercase at all (measured: x-height/cap = 1.01 on eight of them — typing lowercase renders
# capitals), so "match the cap" has no lowercase to be judged against and simply runs heavy.
# 0.85 is the midpoint of the two observations, weighted toward the menu because the menu is
# on every screen while the death headline is one surface. Same shape as the A Plague Tale
# result, where the shipped value also landed below the cap.
# ⚠️ Always recompute from the PRISTINE stencil dump (SRC), never from a rescaled one, or the
# factors compound silently.
TARGET_RATIO = 0.85

RE_FACE = re.compile(r'<item type="FontType"[^>]*>')
RE_NAME = re.compile(r'fontName="([^"]*)"')
RE_NUM = re.compile(r"<item>(-?\d+)</item>")
RE_CODE = re.compile(r'glyphCode="(\d+)"')
RE_GLYPH = re.compile(r'<item type="GlyphType">')
RE_BBOX = re.compile(r"<boundingBox>(.*?)</boundingBox>", re.S)
RE_GI = re.compile(r'<item type="GlyphInfoType"[^>]*/?>')
RE_ADV = re.compile(r'advanceX="(-?\d+)"')
RE_CONT = re.compile(r'<item type="ContourType"([^>]*)>')
RE_MOVEX = re.compile(r'moveToX="(-?\d+)"')
RE_MOVEY = re.compile(r'moveToY="(-?\d+)"')
RE_DATA = re.compile(r"<data>(.*?)</data>", re.S)


# ---------------------------------------------------------------------------- structure

def face_slices(txt):
    marks = [(m.start(), m.group(0)) for m in RE_FACE.finditer(txt)]
    out = []
    for i, (pos, tag) in enumerate(marks):
        nm = RE_NAME.search(tag)
        end = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
        out.append((nm.group(1) if nm else "?", pos, end))
    return out


def glyph_spans(txt, a, b):
    """-> (glyph_items, info_items) as [(start,end)] absolute offsets, parallel by index."""
    gs, ge = txt.find("<glyphs>", a, b), txt.find("</glyphs>", a, b)
    is_, ie = txt.find("<glyphInfo>", a, b), txt.find("</glyphInfo>", a, b)
    gl, gi = [], []
    if gs >= 0 and ge > gs:
        starts = [m.start() for m in RE_GLYPH.finditer(txt, gs, ge)]
        for i, s in enumerate(starts):
            gl.append((s, starts[i + 1] if i + 1 < len(starts) else ge))
    if is_ >= 0 and ie > is_:
        starts = [m.start() for m in RE_GI.finditer(txt, is_, ie)]
        for i, s in enumerate(starts):
            gi.append((s, starts[i + 1] if i + 1 < len(starts) else ie))
    return gl, gi


def codes_of(txt, gi):
    out = []
    for s, e in gi:
        m = RE_CODE.search(txt, s, e)
        out.append(int(m.group(1)) if m else -1)
    return out


def box_of(txt, s, e):
    m = RE_BBOX.search(txt, s, e)
    if not m:
        return None
    n = [int(x) for x in RE_NUM.findall(m.group(1))]
    return tuple(n[:4]) if len(n) >= 4 else None


# ---------------------------------------------------------------------------- geometry

def scale_glyph(seg, k):
    """Rewrite ONE <item type="GlyphType"> block with every coordinate multiplied by k."""
    # --- bounding box
    def _bb(m):
        n = [int(x) for x in RE_NUM.findall(m.group(1))]
        if len(n) < 4:
            return m.group(0)
        sc = [int(round(v * k)) for v in n[:4]]
        inner = "".join(f"<item>{v}</item>" for v in sc)
        return f"<boundingBox>{inner}</boundingBox>"

    seg = RE_BBOX.sub(_bb, seg, count=1)

    # --- contours: reconstruct absolute -> scale -> round -> re-delta
    out, pos = [], 0
    conts = list(RE_CONT.finditer(seg))
    for ci, cm in enumerate(conts):
        nxt = conts[ci + 1].start() if ci + 1 < len(conts) else len(seg)
        out.append(seg[pos:cm.start()])
        attrs = cm.group(1)
        mx = int(RE_MOVEX.search(attrs).group(1))
        my = int(RE_MOVEY.search(attrs).group(1))
        body = seg[cm.end():nxt]

        # exact scaled pen (float) and the emitted (rounded, integer) pen
        fx, fy = mx * k, my * k
        ix, iy = int(round(fx)), int(round(fy))
        new_attrs = RE_MOVEX.sub(f'moveToX="{ix}"', attrs)
        new_attrs = RE_MOVEY.sub(f'moveToY="{iy}"', new_attrs)
        out.append(f'<item type="ContourType"{new_attrs}>')

        pieces, bpos = [], 0
        for dm in RE_DATA.finditer(body):
            n = [int(x) for x in RE_NUM.findall(dm.group(1))]
            pieces.append(body[bpos:dm.start()])
            bpos = dm.end()
            if not n:
                pieces.append(dm.group(0))
                continue
            kind = n[0]
            if kind == 0 and len(n) >= 2:            # horizontal line
                fx += n[1] * k
                nx, ny = int(round(fx)), iy
                vals = [0, nx - ix, 0, 0, 0]
            elif kind == 1 and len(n) >= 2:          # vertical line
                fy += n[1] * k
                nx, ny = ix, int(round(fy))
                vals = [1, ny - iy, 0, 0, 0]
            elif kind == 2 and len(n) >= 3:          # general line
                fx += n[1] * k
                fy += n[2] * k
                nx, ny = int(round(fx)), int(round(fy))
                vals = [2, nx - ix, ny - iy, 0, 0]
            elif kind == 3 and len(n) >= 5:          # quad: control delta + anchor delta
                cxf, cyf = fx + n[1] * k, fy + n[2] * k
                cx, cy = int(round(cxf)), int(round(cyf))
                fx = cxf + n[3] * k
                fy = cyf + n[4] * k
                nx, ny = int(round(fx)), int(round(fy))
                vals = [3, cx - ix, cy - iy, nx - cx, ny - cy]
            else:
                pieces.append(dm.group(0))
                continue
            ix, iy = nx, ny
            pieces.append("<data>" + "".join(f"<item>{v}</item>" for v in vals) + "</data>")
        pieces.append(body[bpos:])
        out.append("".join(pieces))
        pos = nxt
    out.append(seg[pos:])
    return "".join(out)


# ---------------------------------------------------------------------------- driver

def plan(txt):
    """-> [(name, a, b, k, lat_ref, heb_med)] for every face that needs rescaling."""
    rows = []
    for name, a, b in face_slices(txt):
        gl, gi = glyph_spans(txt, a, b)
        n = min(len(gl), len(gi))
        if n == 0:
            continue
        codes = codes_of(txt, gi)
        flats, digits, heb = [], [], []
        for i in range(n):
            bx = box_of(txt, *gl[i])
            if bx is None:
                continue
            h = bx[3] - bx[1]
            c = codes[i]
            if c in FLAT_CAPS:
                flats.append(h)
            elif c in DIGITS:
                digits.append(h)
            elif HEB_LO <= c <= HEB_HI:
                heb.append(h)
        if not heb:
            continue
        # ⚠️ A numbers-only face ('RDR Catalogue Numbers', 'RDR Lino Numbers') carries
        # placeholder LETTER glyphs — its flat-cap median reads 61 while its digits are a
        # real 180+. Digits and caps are the same height in any lining-figure face, so the
        # LARGER of the two medians is always the real cap and the smaller one is the
        # degenerate set. A plain "flatcap unless tiny" rule shrank that face by half.
        fm = sorted(flats)[len(flats) // 2] if flats else 0
        dm = sorted(digits)[len(digits) // 2] if digits else 0
        ref, ref_src = (fm, "flatcap") if fm >= dm else (dm, "digits")
        # A shrink is only trustworthy when the anchor is CORROBORATED by a second,
        # independent measurement — caps and digits are the same height in any lining-figure
        # face, so two medians that agree cannot both be degenerate.
        solid = bool(fm and dm) and min(fm, dm) >= 0.85 * max(fm, dm)
        hm = sorted(heb)[len(heb) // 2]
        if ref <= 40 or hm <= 0:
            rows.append((name, a, b, None, ref, hm, ref_src, solid))
            continue
        k = (ref * TARGET_RATIO) / hm
        rows.append((name, a, b, k, ref, hm, ref_src, solid))
    return rows


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    print(f"reading {SRC} ({os.path.getsize(SRC)/1e6:.0f} MB) ...", flush=True)
    with open(SRC, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    print(f"loaded {len(txt)/1e6:.0f} M chars\n", flush=True)

    rows = plan(txt)
    print(f"{'face':32} {'ref':>6} {'src':>8} {'heb':>5} {'k':>6}  action")
    print("-" * 78)
    todo = []
    for name, a, b, k, ref, hm, src, solid in rows:
        if name in SKIP_FACES:
            print(f"{name[:32]:32} {ref:>6} {src:>8} {hm:>5} {'-':>6}  SKIP (already correct)")
            continue
        if k is None:
            print(f"{name[:32]:32} {ref:>6} {src:>8} {hm:>5} {'-':>6}  SKIP (no usable ref)")
            continue
        if k < 0.95 and not solid:
            # A shrink usually means the ANCHOR is wrong, not that the Hebrew is too big --
            # refuse rather than degrade. But when caps and digits independently agree the
            # anchor is proven real, and then a shrink is the correct answer: RDR Lino is
            # the pause-menu face and its Hebrew was left at 1.06 of its own cap while every
            # other face sits at TARGET_RATIO, which is the whole "menu still too big" bug.
            print(f"{name[:32]:32} {ref:>6} {src:>8} {hm:>5} {k:>6.3f}  "
                  f"SKIP (would SHRINK — bad anchor)")
            continue
        print(f"{name[:32]:32} {ref:>6} {src:>8} {hm:>5} {k:>6.3f}  "
              f"{hm} -> {int(round(hm*k))}")
        todo.append((name, a, b, k))

    if cmd != "apply":
        print("\n(report only — run `apply <out.xml>` to write)")
        return

    out_path = sys.argv[2] if len(sys.argv) > 2 else OUT
    # rewrite from the END so earlier offsets stay valid
    edits = []          # (start, end, replacement)
    total = 0
    for name, a, b, k in todo:
        gl, gi = glyph_spans(txt, a, b)
        n = min(len(gl), len(gi))
        codes = codes_of(txt, gi)
        cnt = 0
        for i in range(n):
            if not (HEB_LO <= codes[i] <= HEB_HI):
                continue
            gs, ge = gl[i]
            edits.append((gs, ge, scale_glyph(txt[gs:ge], k)))
            # advanceX in the parallel GlyphInfoType
            s, e = gi[i]
            seg = txt[s:e]
            m = RE_ADV.search(seg)
            if m:
                adv = int(round(int(m.group(1)) * k))
                edits.append((s, e, seg[:m.start()] + f'advanceX="{adv}"' + seg[m.end():]))
            cnt += 1
        total += cnt
        print(f"  {name}: {cnt} Hebrew glyphs x{k:.3f}", flush=True)

    # ⚠️ Splice with ONE join, never `buf = buf[:s] + rep + buf[e:]` in a loop — that copies
    # the whole 345 M-char document per edit (~460 edits = 160 GB of copying).
    edits.sort(key=lambda t: t[0])
    parts, cur = [], 0
    for s, e, rep in edits:
        if s < cur:
            sys.exit(f"!! overlapping edits at {s} (prev end {cur})")
        parts.append(txt[cur:s])
        parts.append(rep)
        cur = e
    parts.append(txt[cur:])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print(f"\nwrote {out_path} ({os.path.getsize(out_path)/1e6:.0f} MB) — "
          f"{total} Hebrew glyphs rescaled across {len(todo)} faces")


if __name__ == "__main__":
    main()
