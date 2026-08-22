"""Render the INJECTED glyphs straight out of the BUILT swf -> a PNG.

Judging letterforms/size offline costs a chat message; judging them in-game costs
a launch. This decodes each glyph's SHAPE record (the same parser the validator
uses), rasterises it with PIL, and lays out a real word next to real Latin from
the SAME face so the Hebrew:Latin size ratio is visible before anything ships.

usage: python preview.py [swf] [font_id] [text...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT.parent / "007_first_light" / "tools"))

import swf as SWF                                  # noqa: E402
from swf_font import parse_definefont3, BitReader  # noqa: E402
from PIL import Image, ImageChops, ImageDraw       # noqa: E402


def shape_paths(data: bytes):
    """-> list of contours, each a list of (x, y) points (curves flattened)."""
    br = BitReader(data, 0)
    nfill, nline = br.u(4), br.u(4)
    x = y = 0
    cont: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    while br.byte < len(data):
        if br.u(1) == 0:
            flags = br.u(5)
            if flags == 0:
                break
            if flags & 0x01:
                nb = br.u(5)
                x = br.s(nb); y = br.s(nb)
                if cur:
                    cont.append(cur)
                cur = [(x, y)]
            if flags & 0x02:
                br.u(nfill)
            if flags & 0x04:
                br.u(nfill)
            if flags & 0x08:
                br.u(nline)
        else:
            straight = br.u(1)
            nb = br.u(4) + 2
            if straight:
                if br.u(1):
                    x += br.s(nb); y += br.s(nb)
                elif br.u(1):
                    y += br.s(nb)
                else:
                    x += br.s(nb)
                cur.append((x, y))
            else:
                cx = x + br.s(nb); cy = y + br.s(nb)
                nx = cx + br.s(nb); ny = cy + br.s(nb)
                x0, y0 = cur[-1] if cur else (x, y)
                for i in range(1, 9):                     # flatten the quadratic
                    t = i / 8
                    u = 1 - t
                    cur.append((round(u * u * x0 + 2 * u * t * cx + t * t * nx),
                                round(u * u * y0 + 2 * u * t * cy + t * t * ny)))
                x, y = nx, ny
    if cur:
        cont.append(cur)
    return cont


def render(swf_path, font_id: int, text: str, px: int = 46, pad: int = 14) -> Image.Image:
    s = SWF.read(swf_path)
    f = None
    for t in s.tags:
        if t.code == SWF.DEFINE_FONT3:
            g = parse_definefont3(t.body)
            if g["font_id"] == font_id:
                f = g
                break
    if f is None:
        raise SystemExit(f"font id {font_id} not in {swf_path}")
    cm = {c: i for i, c in enumerate(f["codes"])}
    L = f["layout"]
    scale = px / 20480 * 20            # EM 20480 -> px, x20 for supersampling
    ss = 4
    pen = 0
    runs = []
    for ch in text:
        i = cm.get(ord(ch))
        if i is None:
            pen += int(0.4 * 20480)
            continue
        runs.append((pen, shape_paths(f["shapes"][i])))
        pen += L["advance"][i]
    W = int(pen * scale / 20 * ss) + pad * 2 * ss
    H = int(px * 2.0) * ss
    base = int(H * 0.72)
    size = (max(W, 40), H)
    page = Image.new("1", size, 0)
    # EVEN-ODD fill: a glyph counter (the hole in final-mem / samekh) is a SECOND
    # contour that must SUBTRACT. Filling every contour solid closes the hole and
    # the letter shows as a black box -- indistinguishable from a broken glyph.
    for ox, cont in runs:
        acc = Image.new("1", size, 0)
        for c in cont:
            pts = [(pad * ss + (ox + X) * scale / 20 * ss, base + Y * scale / 20 * ss)
                   for X, Y in c]
            if len(pts) > 2:
                one = Image.new("1", size, 0)
                ImageDraw.Draw(one).polygon(pts, fill=1)
                acc = ImageChops.logical_xor(acc, one)
        page = ImageChops.logical_or(page, acc)
    img = page.convert("L").resize((max(size[0] // ss, 10), size[1] // ss), Image.LANCZOS)
    return Image.merge("RGB", (img, img, img))


if __name__ == "__main__":
    swf_path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "_proof/Interface/fonts_en.swf")
    fid = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    lines = sys.argv[3:] or ["Skyrim שלום 123", "אבגדהוזחטיכךלמםנןסעפףצץקרשת",
                             "יציאה לשולחן העבודה", "HHHxxx Skyrim Whiterun"]
    imgs = [render(swf_path, fid, t) for t in lines]
    W = max(i.width for i in imgs)
    H = sum(i.height for i in imgs)
    out = Image.new("RGB", (W, H), (16, 16, 20))
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height
    p = HERE / f"_preview_id{fid}.png"
    out.save(p)
    print(f"-> {p}  ({W}x{H})")
