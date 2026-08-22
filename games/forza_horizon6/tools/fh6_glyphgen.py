"""TTF outline -> ForzaTech `.vfontN` mesh.

The game stores each glyph as [solid interior triangles, cv = 1] + [per-edge
anti-aliasing band, cv = +-W/edgeLength]. We emit the interior only, on the TRUE
outline, with `cu = 0, cv = 1` — exactly the attribute values the game's own
interior triangles carry, so the result is guaranteed-opaque with no chance of the
halo artefacts a mis-modelled AA band would produce.

Tessellation is an exact **trapezoid decomposition**, not ear clipping:

  * flatten every contour to a polygon;
  * split the plane into horizontal bands at every vertex y — inside a band no two
    edges can cross, because a font outline only meets itself at vertices;
  * in each band, sort the crossing edges and pair them by the NON-ZERO winding
    rule (which handles counters/holes with no special casing at all);
  * emit one quad per span, its corners taken from the exact edge x at the band's
    top and bottom, so slanted strokes stay slanted — no stair-stepping.

Adjacent bands bounded by the same pair of edges are merged, which collapses the
long straight runs Hebrew is full of and keeps the vertex count near the game's own.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

Pt = Tuple[float, float]
Vertex = Tuple[float, float, float, float]

FLAT_TOL = 0.0015          # em; curve flattening error budget
EPS = 1e-9


# --------------------------------------------------------------------------
# flattening
# --------------------------------------------------------------------------
def _quad(p0: Pt, p1: Pt, p2: Pt, tol: float) -> List[Pt]:
    d = math.hypot(p1[0] - (p0[0] + p2[0]) / 2, p1[1] - (p0[1] + p2[1]) / 2)
    n = max(2, min(48, int(math.ceil(math.sqrt(d / max(tol, 1e-9)) * 2))))
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _cubic(p0: Pt, p1: Pt, p2: Pt, p3: Pt, tol: float) -> List[Pt]:
    d = (math.hypot(p1[0] - p0[0], p1[1] - p0[1])
         + math.hypot(p2[0] - p1[0], p2[1] - p1[1])
         + math.hypot(p3[0] - p2[0], p3[1] - p2[1]))
    n = max(2, min(64, int(math.ceil(math.sqrt(d / max(tol, 1e-9)) * 2))))
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


def flatten(glyphset, name: str, scale: float, tol: float | None = None) -> List[List[Pt]]:
    """Outline of `name` as closed polygons, in em units scaled by `scale`.

    ⚠️ `tol` defaults to None and is resolved to the CURRENT `FLAT_TOL` at call
    time. Writing `tol: float = FLAT_TOL` binds the module value at def time, so
    tuning `FLAT_TOL` afterwards silently does nothing.
    """
    tol = FLAT_TOL if tol is None else tol
    pen = DecomposingRecordingPen(glyphset)
    glyphset[name].draw(pen)
    contours: List[List[Pt]] = []
    cur: List[Pt] = []
    start: Pt = (0.0, 0.0)
    cursor: Pt = (0.0, 0.0)
    s = scale

    def P(p):
        return (p[0] * s, p[1] * s)

    for op, args in pen.value:
        if op == "moveTo":
            if len(cur) > 2:
                contours.append(cur)
            cursor = start = P(args[0])
            cur = [cursor]
        elif op == "lineTo":
            cursor = P(args[0])
            cur.append(cursor)
        elif op == "qCurveTo":
            pts = [P(a) for a in args if a is not None]
            if args[-1] is None:                       # all-off-curve (TrueType)
                impl = ((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)
                pts = pts + [impl]
            on = pts[-1]
            offs = pts[:-1]
            prev = cursor
            for i, c in enumerate(offs):
                nxt = on if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2,
                                                    (c[1] + offs[i + 1][1]) / 2)
                cur.extend(_quad(prev, c, nxt, tol))
                prev = nxt
            cursor = on
        elif op == "curveTo":
            pts = [P(a) for a in args]
            cur.extend(_cubic(cursor, pts[0], pts[1], pts[2], tol))
            cursor = pts[2]
        elif op == "closePath":
            if len(cur) > 2:
                contours.append(cur)
            cur = []
            cursor = start
    if len(cur) > 2:
        contours.append(cur)
    # drop the duplicated closing point
    out = []
    for c in contours:
        while len(c) > 1 and abs(c[0][0] - c[-1][0]) < EPS and abs(c[0][1] - c[-1][1]) < EPS:
            c = c[:-1]
        if len(c) > 2:
            out.append(c)
    return out


# --------------------------------------------------------------------------
# tessellation
# --------------------------------------------------------------------------
class _Edge:
    __slots__ = ("x0", "y0", "x1", "y1", "dir", "eid")

    def __init__(self, a: Pt, b: Pt, eid: int):
        self.eid = eid
        if a[1] <= b[1]:
            self.x0, self.y0, self.x1, self.y1, self.dir = a[0], a[1], b[0], b[1], 1
        else:
            self.x0, self.y0, self.x1, self.y1, self.dir = b[0], b[1], a[0], a[1], -1

    def x_at(self, y: float) -> float:
        if self.y1 - self.y0 < EPS:
            return self.x0
        return self.x0 + (self.x1 - self.x0) * (y - self.y0) / (self.y1 - self.y0)


YTOL = 1e-6            # band boundaries closer than this are one boundary


def tessellate(contours: Sequence[Sequence[Pt]]) -> Tuple[List[Pt], List[int]]:
    """Exact trapezoid decomposition under the non-zero winding rule."""
    # 1. merge every vertex y into a set of band boundaries...
    raw = sorted({p[1] for c in contours for p in c})
    ys: List[float] = []
    for y in raw:
        if not ys or y - ys[-1] > YTOL:
            ys.append(y)

    # 2. ...and SNAP each endpoint onto them, so band membership is exact.
    #    (Comparing un-snapped coordinates against rounded boundaries silently
    #    drops edges from bands they belong to.)
    def snap(y: float) -> float:
        i = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        return ys[i] if abs(ys[i] - y) <= YTOL else y

    edges: List[_Edge] = []
    for c in contours:
        for i in range(len(c)):
            a, b = c[i], c[(i + 1) % len(c)]
            a = (a[0], snap(a[1]))
            b = (b[0], snap(b[1]))
            if a[1] != b[1]:
                edges.append(_Edge(a, b, len(edges)))
    if not edges:
        return [], []
    # spans of the previous band, keyed by the bounding edge pair, so runs merge
    quads: List[Tuple[Pt, Pt, Pt, Pt]] = []
    open_runs: Dict[Tuple[int, int], List] = {}

    for bi in range(len(ys) - 1):
        y0, y1 = ys[bi], ys[bi + 1]
        if y1 - y0 < EPS:
            continue
        ym = (y0 + y1) / 2
        act = [e for e in edges if e.y0 <= y0 and e.y1 >= y1]
        act.sort(key=lambda e: e.x_at(ym))
        spans = []
        wind = 0
        left = None
        for e in act:
            prev = wind
            wind += e.dir
            if prev == 0 and wind != 0:
                left = e
            elif prev != 0 and wind == 0 and left is not None:
                spans.append((left, e))
                left = None

        seen = set()
        for le, re in spans:
            key = (le.eid, re.eid)
            seen.add(key)
            run = open_runs.get(key)
            if run is None:
                open_runs[key] = [y0, y1]
            else:
                run[1] = y1
        for key in list(open_runs):
            if key not in seen:
                a, b = open_runs.pop(key)
                le = edges[key[0]]; re = edges[key[1]]
                quads.append(((le.x_at(a), a), (re.x_at(a), a),
                              (re.x_at(b), b), (le.x_at(b), b)))
    for key, (a, b) in open_runs.items():
        le = edges[key[0]]; re = edges[key[1]]
        quads.append(((le.x_at(a), a), (re.x_at(a), a),
                      (re.x_at(b), b), (le.x_at(b), b)))

    verts: List[Pt] = []
    index: Dict[Tuple[int, int], int] = {}
    tris: List[int] = []

    def vid(p: Pt) -> int:
        k = (int(round(p[0] * 1e5)), int(round(p[1] * 1e5)))
        i = index.get(k)
        if i is None:
            i = len(verts)
            index[k] = i
            verts.append(p)
        return i

    for a, b, c, d in quads:
        ia, ib, ic, id_ = vid(a), vid(b), vid(c), vid(d)
        if ia != ib and ib != ic and ia != ic:
            tris += [ia, ib, ic]
        if ia != ic and ic != id_ and ia != id_:
            tris += [ia, ic, id_]
    return verts, tris


# --------------------------------------------------------------------------
# glyph generation
# --------------------------------------------------------------------------
class Donor:
    def __init__(self, path: str):
        self.tt = TTFont(path)
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.hmtx = self.tt["hmtx"]

    def has(self, cp: int) -> bool:
        return cp in self.cmap

    def outline(self, cp: int, scale: float) -> List[List[Pt]]:
        return flatten(self.gs, self.cmap[cp], scale / self.upem)

    def advance(self, cp: int, scale: float) -> float:
        return self.hmtx[self.cmap[cp]][0] * scale / self.upem

    def ink(self, cp: int, scale: float):
        cs = self.outline(cp, scale)
        if not cs:
            return None
        xs = [p[0] for c in cs for p in c]
        ys = [p[1] for c in cs for p in c]
        return min(xs), min(ys), max(xs), max(ys)

    def stem(self, cp: int, scale: float, frac: float = 0.5) -> float:
        """Width of the first ink run on a horizontal cut — the stroke weight."""
        cs = self.outline(cp, scale)
        b = self.ink(cp, scale)
        y = b[1] + (b[3] - b[1]) * frac
        xs = []
        for c in cs:
            for i in range(len(c)):
                a, bb = c[i], c[(i + 1) % len(c)]
                if (a[1] - y) * (bb[1] - y) < 0:
                    xs.append(a[0] + (bb[0] - a[0]) * (y - a[1]) / (bb[1] - a[1]))
        xs.sort()
        return min((xs[i + 1] - xs[i] for i in range(0, len(xs) - 1, 2)),
                   default=0.0)


BAND_W = 0.0283        # em; measured off the game's own glyphs
MITER_LIMIT = 0.25     # don't let a sharp corner shoot out a spike


def signed_area(pts: Sequence[Pt]) -> float:
    n = len(pts)
    return sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n)) / 2


def fill_side(contours: Sequence[Sequence[Pt]]) -> float:
    """Which side of the travel direction the INK is on, for the whole glyph.

    🔴 It must be ONE side for every contour. Deciding per contour from its own
    signed area inverts holes — a hole's enclosed region is empty, so moving
    "into it" grows the ink instead of shrinking it, and counters come out wrong
    (measured: ם and ס 20% off, every other letter exact). The largest contour is
    always an outer one, so its winding names the fill side for the glyph.
    """
    outer = max(contours, key=lambda c: abs(signed_area(c)))
    return 1.0 if signed_area(outer) > 0 else -1.0


def inset_polygon(pts: Sequence[Pt], w: float, s: float) -> List[Pt]:
    """Miter-offset a closed polygon by `w` toward the ink side `s`."""
    n = len(pts)

    def nrm(a: Pt, b: Pt) -> Pt:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return (-dy / L * s, dx / L * s)

    out: List[Pt] = []
    for i in range(n):
        p, v, q = pts[i - 1], pts[i], pts[(i + 1) % n]
        n1, n2 = nrm(p, v), nrm(v, q)
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        m = math.hypot(mx, my)
        if m < 1e-9:                        # 180 degree reversal
            mx, my, m = n1[0], n1[1], 1.0
        mx, my = mx / m, my / m
        cos = max(mx * n1[0] + my * n1[1], MITER_LIMIT)
        out.append((v[0] + mx * w / cos, v[1] + my * w / cos))
    return out


def mesh_for(donor: Donor, cp: int, scale: float, x_bias: float,
             band_w: float = BAND_W
             ) -> Tuple[List[Vertex], List[int], float, float]:
    """(vertices, indices, advance, height) ready for a `.vfontN` block.

    Reproduces the game's own two-part glyph:
      * solid interior on the outline INSET by W, `cu = 0, cv = 1`;
      * one anti-aliasing quad per outline edge spanning inset..outset, carrying
        `cv = +-W/edgeLength` — measured off `H`, where it matches on every edge.

    Without the band the letters have hard polygon edges while the Latin beside
    them is analytically anti-aliased, which reads in-game as rough/noisy text.
    """
    contours = donor.outline(cp, scale)
    verts: List[Vertex] = []
    tris: List[int] = []

    if band_w > 0:
        side = fill_side(contours)
        inner = [inset_polygon(c, band_w, side) for c in contours]
        for c, ci in zip(contours, inner):
            for i in range(len(c)):
                j = (i + 1) % len(c)
                L = math.hypot(c[j][0] - c[i][0], c[j][1] - c[i][1])
                if L < EPS:
                    continue
                cv = band_w / L
                oa = (2 * c[i][0] - ci[i][0], 2 * c[i][1] - ci[i][1])
                ob = (2 * c[j][0] - ci[j][0], 2 * c[j][1] - ci[j][1])
                b = len(verts)
                verts += [(ci[i][0] + x_bias, ci[i][1], 0.0, cv),
                          (oa[0] + x_bias, oa[1], 0.0, -cv),
                          (ci[j][0] + x_bias, ci[j][1], 0.0, cv),
                          (ob[0] + x_bias, ob[1], 0.0, -cv)]
                tris += [b, b + 1, b + 2, b + 1, b + 3, b + 2]
        fill = inner
    else:
        fill = [list(c) for c in contours]

    pts, itris = tessellate(fill)
    base = len(verts)
    verts += [(x + x_bias, y, 0.0, 1.0) for x, y in pts]
    tris += [base + i for i in itris]

    ys = [p[1] for c in contours for p in c]
    return verts, tris, donor.advance(cp, scale), max(ys, default=0.0)
