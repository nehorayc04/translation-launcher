#!/usr/bin/env python3
"""Generate SWF/GFx DefineFont3 glyph SHAPE records from a TrueType glyph outline.
TTF is Y-up; the TW3 SWF font is Y-down (verified) -> negate Y. Scale = SWF_EM(20480)/TTF_upm.
"""
from fontTools.pens.basePen import BasePen


class ContourPen(BasePen):
    """Collect contours as lists of ('line', pt) / ('qcurve', ctrl, pt), with the start point."""
    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours = []
        self._cur = None
        self._start = None

    def _moveTo(self, pt):
        self._cur = {"start": pt, "segs": []}
        self._start = pt
        self._last = pt

    def _lineTo(self, pt):
        self._cur["segs"].append(("line", pt))
        self._last = pt

    def _curveToOne(self, p1, p2, p3):
        # cubic -> approximate with two quadratics is overkill; TTF has no cubics. Fallback: line.
        self._cur["segs"].append(("line", p3))
        self._last = p3

    def _qCurveToOne(self, p1, p2):
        self._cur["segs"].append(("qcurve", p1, p2))
        self._last = p2

    def _closePath(self):
        if self._cur is not None:
            self.contours.append(self._cur)
            self._cur = None

    def _endPath(self):
        self._closePath()


class BitWriter:
    def __init__(self):
        self.bits = []

    def u(self, val, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((val >> i) & 1)

    def s(self, val, n):
        if val < 0:
            val += (1 << n)
        self.u(val, n)

    def bytes(self):
        while len(self.bits) % 8:
            self.bits.append(0)
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | self.bits[i + j]
            out.append(b)
        return bytes(out)


def _sbits(*vals):
    """min bits to hold signed vals (incl. sign)."""
    m = 2
    for v in vals:
        need = v.bit_length() + 1 if v >= 0 else (~v).bit_length() + 1
        m = max(m, need)
    return m


def glyph_to_shape(glyphset, glyph_name, scale, y_sign=-1):
    pen = ContourPen(glyphset)
    glyphset[glyph_name].draw(pen)

    def tx(pt):
        return (round(pt[0] * scale), round(pt[1] * scale * y_sign))

    bw = BitWriter()
    bw.u(1, 4)  # NumFillBits = 1
    bw.u(0, 4)  # NumLineBits = 0
    first = True
    cx = cy = 0
    for c in pen.contours:
        sx, sy = tx(c["start"])
        # StyleChangeRecord: MoveTo (+ FS0=1 on the very first)
        bw.u(0, 1)                                  # non-edge
        move_dx, move_dy = sx, sy
        mb = _sbits(move_dx, move_dy)
        if first:
            bw.u(0b00011, 5)                        # StateFillStyle0 | StateMoveTo
        else:
            bw.u(0b00001, 5)                        # StateMoveTo
        bw.u(mb, 5)
        bw.s(move_dx, mb); bw.s(move_dy, mb)
        if first:
            bw.u(1, 1)                              # FillStyle0 = 1 (NumFillBits=1)
            first = False
        cx, cy = sx, sy
        # build absolute segment endpoints then emit relative edges
        pts = []
        for seg in c["segs"]:
            if seg[0] == "line":
                pts.append(("line", tx(seg[1])))
            else:
                pts.append(("qcurve", tx(seg[1]), tx(seg[2])))
        # close contour back to start
        if pts and pts[-1][-1] != (sx, sy):
            pts.append(("line", (sx, sy)))
        for seg in pts:
            if seg[0] == "line":
                nx, ny = seg[1]
                dx, dy = nx - cx, ny - cy
                if dx == 0 and dy == 0:
                    continue
                bw.u(1, 1)                           # edge
                bw.u(1, 1)                           # straight
                if dx != 0 and dy != 0:
                    nb = _sbits(dx, dy)
                    bw.u(nb - 2, 4); bw.u(1, 1)      # general
                    bw.s(dx, nb); bw.s(dy, nb)
                elif dx != 0:
                    nb = _sbits(dx)
                    bw.u(nb - 2, 4); bw.u(0, 1); bw.u(0, 1)  # not general, horizontal
                    bw.s(dx, nb)
                else:
                    nb = _sbits(dy)
                    bw.u(nb - 2, 4); bw.u(0, 1); bw.u(1, 1)  # not general, vertical
                    bw.s(dy, nb)
                cx, cy = nx, ny
            else:
                (ctrlx, ctrly), (anx, any_) = seg[1], seg[2]
                cdx, cdy = ctrlx - cx, ctrly - cy
                adx, ady = anx - ctrlx, any_ - ctrly
                bw.u(1, 1)                           # edge
                bw.u(0, 1)                           # curved
                nb = _sbits(cdx, cdy, adx, ady)
                bw.u(nb - 2, 4)
                bw.s(cdx, nb); bw.s(cdy, nb); bw.s(adx, nb); bw.s(ady, nb)
                cx, cy = anx, any_
    bw.u(0, 6)                                       # EndShapeRecord
    return bw.bytes()
