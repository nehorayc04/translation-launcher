#!/usr/bin/env python3
"""rdr2_stencil_font.py — build a DISTRESSED/STENCIL Hebrew glyph set matching RDR Lino's
"worn rubber-stamp" look (extra-condensed/extra-bold blocky base + jagged, chaotically eroded
edges — NO interior punch-out holes), and inject it into font_lib_efigs.gfx's RDR Lino
($title1) face — the font used for the pause-menu section titles (MAP/HELP/PROGRESS/PLAYER/
STORY/ONLINE/SOCIAL CLUB/SETTINGS).

Measured facts (this session):
  - RDR Lino ($title1) is the exact face; confirmed by rendering candidate faces and
    comparing against the user's screenshot ("MAP HELP PROGRESS..." blocky/distressed).
  - Its Latin cap height (bbox of 'M', glyphCode=77) = 201 units. The CURRENT (plain donor)
    Hebrew glyphs are only ~134 units tall -> undersized vs rule #2 (body == native cap for
    Hebrew, since it has no ascenders/descenders). This build also fixes that.
  - Winding convention (measured off the live ם/ס glyphs): OUTER contour = POSITIVE signed
    area, INNER/hole contour = NEGATIVE signed area, in this engine's Y-DOWN coordinate
    space. A TrueType donor (Y-UP) has the opposite sign in its own space -- so a plain
    Y-flip (no extra sign logic) makes the winding match automatically.
  - Edge format (reverse-engineered from the live XML): each EdgeType <data> is
    [kind, p1, p2, p3, p4] where kind 0=line(dx=p1,dy=0), 1=line(dx=0,dy=p1),
    2=line(dx=p1,dy=p2), 3=quad-curve(control_d=(p1,p2), anchor_d=(p3,p4)) -- all deltas
    relative to the previous point. Distressed edges are all straight (kind 0/1/2); no
    curves needed since a jittered boundary isn't smooth anyway.
  - User correction (round 2): the first pass carved small interior holes into solid strokes
    for "ink speckle" -- these read as literal DOTS, not as a worn/chipped stencil. Real
    stencil wear is an EDGE phenomenon (torn/eroded boundary), never a hole floating in the
    middle of a stroke. Holes are REMOVED entirely; the edge-jitter/bite noise was made
    richer/more chaotic ("גועש") instead to carry all of the distress.

Donor: Noto Sans Hebrew ExtraCondensed ExtraBold (the user's own pick -- matches the
reference image's narrow, heavy-stroke stencil block letters far better than a slab-serif).

Usage:
    python rdr2_stencil_font.py preview [--seed N]      # offline PNG, no game files touched
    python rdr2_stencil_font.py inject <out_xml> [--seed N]   # build glyphInfo/glyphs <item>s
"""
import math
import os
import random
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DONOR_TTF = r"C:\Users\Nehoray_Cohen\Downloads\Noto_Sans_Hebrew\static\NotoSansHebrew_ExtraCondensed-ExtraBold.ttf"
OUT_DIR = os.path.join(HERE, "_fontinspect", "ttf")

HEB_LO, HEB_HI = 0x05D0, 0x05EA
LETTERS = [chr(c) for c in range(HEB_LO, HEB_HI + 1)]

TARGET_CAP = 201.0   # RDR Lino's own Latin 'M' cap height (measured)


# ---------------------------------------------------------------------------
# 1. extract clean flattened contours from the donor TTF
# ---------------------------------------------------------------------------

def _flatten_qcurve(p0, pts, n=10):
    """pts = the qCurveTo args: [off1, off2, ..., onN]. TrueType allows implied on-curve
    midpoints between consecutive off-curve points -- expand those first, then flatten
    each simple quadratic segment into `n` line segments."""
    pts = list(pts)
    if pts[-1] is None:      # closing back to the contour start; caller fills p0 in
        pts = pts[:-1]
    expanded = []
    i = 0
    cur = p0
    while i < len(pts):
        if i + 1 < len(pts) and _is_off(pts, i) and _is_off(pts, i + 1):
            mid = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            expanded.append((pts[i], mid))
            i += 1
        else:
            nxt = pts[i + 1] if i + 1 < len(pts) else None
            expanded.append((pts[i], nxt if nxt is not None else pts[i]))
            i += 2 if nxt is not None else 1
    out = []
    for ctrl, end in expanded:
        for t in range(1, n + 1):
            tt = t / n
            x = (1 - tt) ** 2 * cur[0] + 2 * (1 - tt) * tt * ctrl[0] + tt ** 2 * end[0]
            y = (1 - tt) ** 2 * cur[1] + 2 * (1 - tt) * tt * ctrl[1] + tt ** 2 * end[1]
            out.append((x, y))
        cur = end
    return out


def _is_off(pts, i):
    return True  # qCurveTo args here are all off-curve control points by construction


def glyph_contours(font, ch, seg_len=None):
    """-> list of contours (each a list of (x,y), no duplicate closing point)."""
    cmap = font.getBestCmap()
    if ord(ch) not in cmap:
        return []
    gname = cmap[ord(ch)]
    pen = RecordingPen()
    font.getGlyphSet()[gname].draw(pen)
    contours, cur, start = [], [], None
    for op, args in pen.value:
        if op == "moveTo":
            if cur:
                contours.append(cur)
            start = args[0]
            cur = [start]
        elif op == "lineTo":
            cur.append(args[0])
        elif op == "qCurveTo":
            cur.extend(_flatten_qcurve(cur[-1], args, n=12))
        elif op == "closePath":
            pass
    if cur:
        contours.append(cur)
    # drop consecutive duplicate points + the closing duplicate of the start
    cleaned = []
    for c in contours:
        out = [c[0]]
        for p in c[1:]:
            if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
                out.append(p)
        if abs(out[-1][0] - out[0][0]) < 1e-6 and abs(out[-1][1] - out[0][1]) < 1e-6:
            out.pop()
        cleaned.append(out)
    if seg_len:
        cleaned = [_resample(c, seg_len) for c in cleaned]
    return cleaned


def _resample(pts, seg_len):
    """Subdivide long straight segments so distress jitter has enough vertices."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        out.append(p0)
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        steps = max(0, int(d / seg_len) - 1)
        for s in range(1, steps + 1):
            t = s / (steps + 1)
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
    return out


# ---------------------------------------------------------------------------
# 2. the distress filter (pure vector: chaotic multi-octave jitter along the local normal +
#    frequent deep "bites" torn out of the boundary -- ALL of the wear lives on the edge,
#    never as a hole punched into a solid fill)
# ---------------------------------------------------------------------------

def _smooth_noise_1d(n, rng, octaves=((1, 1.0), (3, 0.65), (7, 0.45), (14, 0.28))):
    """Cheap band-limited noise on a closed loop of length n: sum of several random-phase
    sine waves at rising frequencies -> a genuinely CHAOTIC/turbulent ("גועש") boundary --
    a slow macro wobble PLUS coarse mid bumps PLUS a fast ragged ripple -- while staying
    band-limited (no raw per-vertex static, which reads as fur, not a torn edge)."""
    phases = [rng.uniform(0, 2 * math.pi) for _ in octaves]
    vals = []
    for i in range(n):
        t = 2 * math.pi * i / n
        v = sum(amp * math.sin(freq * t + ph) for (freq, amp), ph in zip(octaves, phases))
        vals.append(v)
    return vals


def _corner_factor(pts, i, n, angle_thresh=0.42):
    """1.0 on a long straight run, ->0 right at a sharp corner. Real stencil-font wear
    chips the STRAIGHT EDGES, not the corner vertices -- jittering a corner freely
    warps the letterform's silhouette and hurts legibility."""
    a = pts[(i - 1) % n]
    b = pts[i]
    c = pts[(i + 1) % n]
    v1x, v1y = b[0] - a[0], b[1] - a[1]
    v2x, v2y = c[0] - b[0], c[1] - b[1]
    l1 = math.hypot(v1x, v1y) or 1e-6
    l2 = math.hypot(v2x, v2y) or 1e-6
    cos_t = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (l1 * l2)))
    turn = math.acos(cos_t)          # 0 = straight, pi/2 = right angle
    return max(0.0, 1.0 - turn / angle_thresh)


def distress_contour(pts, rng, amp, is_outer, n_bites=None, bite_depth=None):
    """pts already resampled fine. Displace each vertex along its local outward normal
    by chaotic multi-octave noise (amp = displacement scale, damped near sharp corners so
    the letterform silhouette stays legible), then tear several deeper localized bites out
    of the STRAIGHT runs -- the number of bites scales with the contour's own length, so a
    long stroke gets proportionally more visible erosion than a short one."""
    n = len(pts)
    if n < 4:
        return pts
    noise = _smooth_noise_1d(n, rng)
    peak = max(abs(v) for v in noise) or 1.0
    noise = [v / peak for v in noise]
    corner = [_corner_factor(pts, i, n) for i in range(n)]

    if n_bites is None:
        n_bites = max(2, min(5, round(n / 55)))
    if bite_depth is None:
        bite_depth = amp * 1.3
    bite_centers = [rng.uniform(0, n) for _ in range(n_bites)]
    bite_widths = [rng.uniform(n * 0.012, n * 0.03) for _ in range(n_bites)]

    out = []
    for i, (x, y) in enumerate(pts):
        px, py = pts[(i - 1) % n]
        nx_, ny_ = pts[(i + 1) % n]
        tx, ty = nx_ - px, ny_ - py
        tl = math.hypot(tx, ty) or 1.0
        nxn, nyn = ty / tl, -tx / tl
        if not is_outer:
            nxn, nyn = -nxn, -nyn
        cf = corner[i]
        d = noise[i] * amp * cf
        for c, w in zip(bite_centers, bite_widths):
            dist = min(abs(i - c), n - abs(i - c))
            if dist < w:
                d -= bite_depth * cf * math.cos(math.pi / 2 * dist / w) ** 2
        out.append((x + nxn * d, y + nyn * d))
    return out


def _signed_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < xin:
                inside = not inside
    return inside


def _min_dist_to_poly(pt, poly):
    x, y = pt
    n = len(poly)
    best = float("inf")
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 < 1e-9:
            d = math.hypot(x - x1, y - y1)
        else:
            t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / l2))
            px, py = x1 + t * dx, y1 + t * dy
            d = math.hypot(x - px, y - py)
        best = min(best, d)
    return best


def _speckle_holes(outer, holes, rng, n_holes, min_r, max_r, bbox):
    """Small irregular blobs cut into the solid fill (visible ink-loss speckle). Kept
    well clear of every boundary so a stroke reads as WORN, not CUT THROUGH."""
    x0, y0, x1, y1 = bbox
    out = []
    tries = 0
    while len(out) < n_holes and tries < n_holes * 60:
        tries += 1
        px = rng.uniform(x0, x1)
        py = rng.uniform(y0, y1)
        if not _point_in_poly((px, py), outer):
            continue
        if any(_point_in_poly((px, py), h) for h in holes):
            continue
        r = rng.uniform(min_r, max_r)
        margin = r * 2.2
        if _min_dist_to_poly((px, py), outer) < margin:
            continue
        if any(_min_dist_to_poly((px, py), h) < margin for h in holes):
            continue
        pts = []
        k = 7
        for j in range(k):
            ang = 2 * math.pi * j / k
            rr = r * rng.uniform(0.6, 1.0)
            pts.append((px + rr * math.cos(ang), py + rr * math.sin(ang)))
        # must be a HOLE: same sign convention as the letter's own counters
        if _signed_area(pts) * _signed_area(outer) > 0:
            pts = pts[::-1]
        out.append(pts)
    return out


# ---------------------------------------------------------------------------
# 3. build one letter: contours in RDR2 Y-down units, baseline at y=0
# ---------------------------------------------------------------------------

def _rep_point_near_boundary(c):
    """A point robustly INSIDE this contour, right next to its own boundary. A polygon
    centroid fails for a ring/annulus (samekh, final-mem's counter etc.): the centroid of
    the OUTER ring's vertices sits in the hole, not in the solid band. Nudging in from an
    edge midpoint by a tiny epsilon stays correct even when the contour's far interior is
    hollowed out by a nested hole."""
    n = len(c)
    for i in range(n):
        x1, y1 = c[i]
        x2, y2 = c[(i + 1) % n]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        nx_, ny_ = dy / length, -dx / length
        eps = max(length * 0.15, 0.05)
        for sign in (1, -1):
            cand = (mx + nx_ * eps * sign, my + ny_ * eps * sign)
            if _point_in_poly(cand, c):
                return cand
    # degenerate fallback
    return (sum(p[0] for p in c) / n, sum(p[1] for p in c) / n)


def _classify_roles(conts):
    """A contour is a HOLE iff it is nested inside an ODD number of other contours (the
    standard even-odd nesting rule). This is NOT the same as "biggest area = outer,
    everything else = hole" -- a letter like Hebrew He (ה) has its left leg as a SEPARATE
    disjoint SOLID contour, not a hole, and the area-heuristic wrongly punched it out.

    Returns: list of 'solid'|'hole', in the SAME order as `conts`.
    """
    n = len(conts)
    reps = [_rep_point_near_boundary(c) for c in conts]
    roles = []
    for i in range(n):
        depth = sum(1 for j in range(n) if j != i and _point_in_poly(reps[i], conts[j]))
        roles.append("hole" if depth % 2 == 1 else "solid")
    return roles


def build_letter(font, ch, upem, scale, rng, jitter_amp, seg_len, n_holes=0):
    """n_holes is accepted for call-site compatibility but is always ignored -- interior
    punch-out holes read as literal dots, not as worn-stencil texture (see the module
    docstring's round-2 correction). All distress lives on the contour edges."""
    raw = glyph_contours(font, ch, seg_len=seg_len)
    if not raw:
        return [], 0.0, (0, 0, 0, 0)
    # font Y-up -> RDR2 Y-down: negate y, then scale
    conts = [[(x * scale, -y * scale) for (x, y) in c] for c in raw]
    if not conts:
        return [], 0.0, (0, 0, 0, 0)
    roles = _classify_roles(conts)
    distressed = [distress_contour(c, rng, jitter_amp, is_outer=(role == "solid"))
                  for c, role in zip(conts, roles)]
    solids_d = [c for c, role in zip(distressed, roles) if role == "solid"]
    holes_d = [c for c, role in zip(distressed, roles) if role == "hole"]
    # 🔴 The bounding box must cover EVERY contour, not just the ones classified "solid".
    # Scaleform rasterizes a glyph into its cache using these bounds, so an undersized box
    # both CLIPS the glyph and makes it come out at the wrong scale. Measured on the shipped
    # build: solids-only gave ב / נ / צ a height of ~52 against a real ~202 -- a quarter of
    # the letter -- because one role call put their outer ring in the hole set. Taking the
    # union over all contours is correct whatever the classification decides, so a
    # mis-classified contour can no longer damage the metrics.
    allc = solids_d + holes_d
    xs = [p[0] for c in allc for p in c]
    ys = [p[1] for c in allc for p in c]
    pad = TARGET_CAP * 0.02          # the distress can push a vertex just past the outline
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    return allc, _advance(font, ch, scale), bbox, len(solids_d)


def _speckle_holes_multi(solids, holes, rng, n_holes, min_r, max_r, bbox):
    x0, y0, x1, y1 = bbox
    out = []
    tries = 0
    while len(out) < n_holes and tries < n_holes * 60:
        tries += 1
        px = rng.uniform(x0, x1)
        py = rng.uniform(y0, y1)
        if not any(_point_in_poly((px, py), s) for s in solids):
            continue
        if any(_point_in_poly((px, py), h) for h in holes):
            continue
        r = rng.uniform(min_r, max_r)
        margin = r * 2.2
        if any(_min_dist_to_poly((px, py), s) < margin for s in solids):
            continue
        if any(_min_dist_to_poly((px, py), h) < margin for h in holes):
            continue
        pts = []
        k = 7
        for j in range(k):
            ang = 2 * math.pi * j / k
            rr = r * rng.uniform(0.6, 1.0)
            pts.append((px + rr * math.cos(ang), py + rr * math.sin(ang)))
        out.append(pts)
    return out


def _advance(font, ch, scale):
    gname = font.getBestCmap()[ord(ch)]
    return font["hmtx"][gname][0] * scale


# ---------------------------------------------------------------------------
# 4. offline raster preview (nonzero-winding scanline fill via PIL polygon XOR trick is
#    unreliable for true nonzero winding with >2 nested contours, so rasterize by parity
#    per contour depth using PIL's own polygon fill + explicit hole subtraction, which is
#    exactly right for the outer+holes(+speckle) structure we build.)
# ---------------------------------------------------------------------------

def _draw_glyph(d, contours, n_solids, ox, oy):
    for c in contours[:n_solids]:
        d.polygon([(x + ox, y + oy) for x, y in c], fill=0)
    for c in contours[n_solids:]:
        d.polygon([(x + ox, y + oy) for x, y in c], fill=255)


def render_preview(letters_data, cap_px=260, pad=40, per_row=6):
    from PIL import Image, ImageDraw

    n = len(letters_data)
    rows = math.ceil(n / per_row)
    cell = cap_px + pad
    img = Image.new("L", (per_row * cell, rows * cell), 255)
    for idx, (ch, contours, adv, bbox, n_solids) in enumerate(letters_data):
        r, c = divmod(idx, per_row)
        glyph_img = Image.new("L", (cell, cell), 255)
        d = ImageDraw.Draw(glyph_img)
        _draw_glyph(d, contours, n_solids, pad // 2, cap_px + pad // 2)
        img.paste(glyph_img, (c * cell, r * cell))
    return img


def render_words(by_ch, words, out_path, px_pad=60, line_h=340, margin=40):
    """Lay out real Hebrew words RIGHT-TO-LEFT (as they'll actually read on screen) using
    the built letters' own advances, so letterform cohesion + spacing can be judged before
    touching the game."""
    from PIL import Image, ImageDraw

    W = 1700
    img = Image.new("L", (W, line_h * len(words) + margin), 255)
    d = ImageDraw.Draw(img)
    for row, word in enumerate(words):
        canvas_y = margin + row * line_h + line_h - 90
        cursor_x = W - margin
        for ch in word:
            data = by_ch.get(ch)
            if not data:
                continue
            contours, adv, bbox, n_solids = data
            cursor_x -= adv
            _draw_glyph(d, contours, n_solids, cursor_x, canvas_y)
    img.save(out_path)
    print("wrote", out_path)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    seed = 20260805
    if "--seed" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--seed") + 1])
    rng = random.Random(seed)

    font = TTFont(DONOR_TTF)
    upem = font["head"].unitsPerEm
    # measure the donor's own cap height off a flat letter (bet) to get the scale factor
    raw_bet = glyph_contours(font, "ב")
    ys = [p[1] for c in raw_bet for p in c]
    donor_cap = max(ys) - min(ys)
    scale = TARGET_CAP / donor_cap
    jitter_amp = TARGET_CAP * 0.018       # chaotic edge wear, corner-damped -- silhouette stays legible
    seg_len = TARGET_CAP * 0.03           # finer vertex density -- resolves the added high-freq octave

    print(f"donor unitsPerEm={upem} donor_cap(raw)={donor_cap:.1f} scale={scale:.4f} "
          f"jitter_amp={jitter_amp:.1f} seg_len={seg_len:.1f}")

    letters_data = []
    for ch in LETTERS:
        contours, adv, bbox, n_solids = build_letter(font, ch, upem, scale, rng, jitter_amp,
                                                       seg_len, n_holes=0)
        letters_data.append((ch, contours, adv, bbox, n_solids))
        print(f"  U+{ord(ch):04X} {ch}  contours={len(contours)} (solids={n_solids})  "
              f"adv={adv:.0f}  bbox={bbox}")

    if cmd == "preview":
        os.makedirs(OUT_DIR, exist_ok=True)
        img = render_preview(letters_data)
        out = os.path.join(OUT_DIR, "stencil_preview.png")
        img.save(out)
        print("wrote", out)
    elif cmd == "words":
        by_ch = {ch: (contours, adv, bbox, n_solids)
                 for ch, contours, adv, bbox, n_solids in letters_data}
        words = sys.argv[2:] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else \
            ["מפה", "עזרה", "התקדמות", "שחקן", "סיפור"]
        render_words(by_ch, words, os.path.join(OUT_DIR, "stencil_words.png"))
    elif cmd == "inject":
        print("(inject step not run in this call -- preview first)")
    else:
        sys.exit(f"unknown command {cmd!r}")


if __name__ == "__main__":
    main()
