"""Minimal SWF glyph SHAPE reader -> bounding box + a structural validity check.

Skyrim's shipped DefineFont3 fonts store EMPTY bounds RECTs (all zero), so the only
way to MEASURE a face (cap height, aspect, stroke) is to walk the shape records.
Doubles as a validator for the glyphs we generate: a shape that fails to parse here
would fail in Scaleform too.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "007_first_light" / "tools"))
from swf_font import BitReader   # noqa: E402


def shape_bbox(data: bytes):
    """-> (xmin, ymin, xmax, ymax, n_points) in shape units, or None for an empty glyph."""
    br = BitReader(data, 0)
    nfill = br.u(4)
    nline = br.u(4)
    x = y = 0
    xs: list[int] = []
    ys: list[int] = []
    while True:
        if br.byte >= len(data):
            break
        if br.u(1) == 0:                       # non-edge
            flags = br.u(5)
            if flags == 0:                     # EndShapeRecord
                break
            if flags & 0x01:                   # StateMoveTo
                nb = br.u(5)
                x = br.s(nb)
                y = br.s(nb)
                xs.append(x); ys.append(y)
            if flags & 0x02:                   # StateFillStyle0
                br.u(nfill)
            if flags & 0x04:                   # StateFillStyle1
                br.u(nfill)
            if flags & 0x08:                   # StateLineStyle
                br.u(nline)
            if flags & 0x10:                   # StateNewStyles (not in glyphs)
                raise ValueError("StateNewStyles inside a glyph shape")
        else:                                  # edge
            straight = br.u(1)
            nb = br.u(4) + 2
            if straight:
                if br.u(1):                    # general
                    x += br.s(nb); y += br.s(nb)
                elif br.u(1):                  # vertical
                    y += br.s(nb)
                else:                          # horizontal
                    x += br.s(nb)
                xs.append(x); ys.append(y)
            else:
                cx = x + br.s(nb); cy = y + br.s(nb)
                x = cx + br.s(nb); y = cy + br.s(nb)
                xs.append(cx); ys.append(cy)
                xs.append(x); ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys), len(xs)


def measure_face(f: dict, chars="HMExo") -> dict:
    """f = parsed DefineFont3. -> {char: {adv, w, h, y0, y1}} plus 'cap'/'xh'."""
    cm = {c: i for i, c in enumerate(f["codes"])}
    L = f["layout"]
    out: dict = {}
    for ch in chars:
        i = cm.get(ord(ch))
        if i is None:
            continue
        bb = shape_bbox(f["shapes"][i])
        if not bb:
            continue
        x0, y0, x1, y1, n = bb
        out[ch] = {"adv": L["advance"][i], "w": x1 - x0, "h": y1 - y0,
                   "y0": y0, "y1": y1, "pts": n}
    if "H" in out:
        out["cap"] = out["H"]["h"]
    elif "E" in out:
        out["cap"] = out["E"]["h"]
    if "x" in out:
        out["xh"] = out["x"]["h"]
    return out
