"""
Generate branded installer assets for the Translation Manager Inno Setup wizard.

Outputs (next to this script):
  wizard-large.bmp   164 x 314   24-bit BMP   (left side panel)
  wizard-small.bmp   150 x  57   24-bit BMP   (top-right header strip)
  app.ico            multi-res   (16/32/48/64/128/256)

Aesthetic: Cyberpunk 2077 / AAA dark UI.
  - Dark indigo→black radial gradient (#1a0d40 → #050510)
  - Neon yellow #fff700 primary
  - Neon cyan   #00ffe0 secondary
  - Subtle scanline / circuit-grid noise
  - Angular chamfered borders
  - "TM" monogram + "TRANSLATION MANAGER" wordmark
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent

# Brand palette
COL_BG_TOP    = (26,  13,  64)    # #1a0d40
COL_BG_BOT    = (5,    5,  16)    # #050510
COL_YELLOW    = (255, 247,  0)    # #fff700
COL_CYAN      = (0,   255, 224)   # #00ffe0
COL_FAINT     = (50,   30,  80)   # grid lines
COL_WHITE     = (240, 240, 255)
COL_DIM       = (140, 140, 170)


# ────────────────────────────────────────────────────────────────────
# Font discovery — try the prettiest Windows fonts in order.
# All have bold weights and look good at small sizes.
# ────────────────────────────────────────────────────────────────────
WIN_FONTS = Path("C:/Windows/Fonts")
FONT_HEAVY_CANDIDATES = [
    "impact.ttf",          # very bold display
    "arialbd.ttf",         # Arial Bold
    "segoeuib.ttf",        # Segoe UI Bold
    "consolab.ttf",        # Consolas Bold (techy)
]
FONT_MONO_CANDIDATES = [
    "consolab.ttf",
    "consola.ttf",
    "cour.ttf",
]


def _load_font(candidates, size: int) -> ImageFont.FreeTypeFont:
    for name in candidates:
        p = WIN_FONTS / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


# ────────────────────────────────────────────────────────────────────
# Gradient + texture primitives
# ────────────────────────────────────────────────────────────────────
def vertical_gradient(w: int, h: int, top, bot) -> Image.Image:
    """Per-row linear blend top→bot."""
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def radial_glow(w: int, h: int, cx: int, cy: int, radius: int, color, alpha: int = 220):
    """Returns a transparent RGBA layer with a soft circular glow at (cx,cy)."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = layer.load()
    r2 = radius * radius
    for y in range(max(0, cy - radius), min(h, cy + radius)):
        for x in range(max(0, cx - radius), min(w, cx + radius)):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 < r2:
                t = 1 - math.sqrt(d2) / radius
                a = int(alpha * (t ** 2))
                px[x, y] = (color[0], color[1], color[2], a)
    return layer.filter(ImageFilter.GaussianBlur(radius=6))


def circuit_grid(w: int, h: int, step: int = 12, color=COL_FAINT, alpha: int = 60) -> Image.Image:
    """Faint grid lines + a few random-looking 'circuit traces' for tech feel."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    line_col = (*color, alpha)
    # grid
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=line_col, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=line_col, width=1)
    # diagonal accent traces (cyan, very faint)
    trace_col = (COL_CYAN[0], COL_CYAN[1], COL_CYAN[2], 35)
    for i in range(0, max(w, h), step * 4):
        d.line([(0, i), (i, 0)], fill=trace_col, width=1)
        d.line([(w, i), (w - i, 0)], fill=trace_col, width=1)
    return layer


def glow_text(layer: Image.Image, xy, text: str, font, fill, glow, glow_radius: int = 4):
    """Draw `text` with a soft colored glow underneath."""
    w, h = layer.size
    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_img)
    gd.text(xy, text, fill=(*glow, 200), font=font)
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(glow_radius))
    layer.alpha_composite(glow_img)
    d = ImageDraw.Draw(layer)
    d.text(xy, text, fill=fill, font=font)


def chamfered_border(d: ImageDraw.ImageDraw, w: int, h: int, color, inset: int = 3, cut: int = 12, width: int = 2):
    """Draw a Cyberpunk-style chamfered rectangle border with corner cuts."""
    x0, y0 = inset, inset
    x1, y1 = w - inset - 1, h - inset - 1
    pts = [
        (x0 + cut, y0),
        (x1, y0),
        (x1, y1 - cut),
        (x1 - cut, y1),
        (x0, y1),
        (x0, y0 + cut),
        (x0 + cut, y0),
    ]
    d.line(pts, fill=color, width=width, joint="curve")


# ────────────────────────────────────────────────────────────────────
# wizard-large.bmp  (164 × 314)
# ────────────────────────────────────────────────────────────────────
def make_wizard_large() -> Image.Image:
    W, H = 164, 314
    # base gradient
    base = vertical_gradient(W, H, COL_BG_TOP, COL_BG_BOT).convert("RGBA")

    # radial glow behind the monogram (purple→indigo bloom upper portion)
    base.alpha_composite(radial_glow(W, H, W // 2, 95, 110, (90, 60, 200), alpha=180))
    # faint cyan glow lower
    base.alpha_composite(radial_glow(W, H, W // 2, H - 60, 80, COL_CYAN, alpha=120))

    # circuit grid texture
    base.alpha_composite(circuit_grid(W, H, step=14, alpha=55))

    d = ImageDraw.Draw(base)

    # chamfered border (cyan, then yellow inside)
    chamfered_border(d, W, H, (*COL_CYAN, 180), inset=4, cut=14, width=2)
    chamfered_border(d, W, H, (*COL_YELLOW, 110), inset=7, cut=11, width=1)

    # === Monogram "TM" centered up top ===
    f_mono = _load_font(FONT_HEAVY_CANDIDATES, 76)
    # measure
    bbox = d.textbbox((0, 0), "TM", font=f_mono)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (W - tw) // 2 - bbox[0], 50 - bbox[1]
    glow_text(base, (tx, ty), "TM", f_mono, COL_YELLOW, COL_YELLOW, glow_radius=6)

    # underline accent (cyan)
    d = ImageDraw.Draw(base)
    cy_y = 50 + th + 8
    d.line([(28, cy_y), (W - 28, cy_y)], fill=(*COL_CYAN, 230), width=2)

    # === Wordmark stacked vertically: TRANSLATION / MANAGER ===
    f_word = _load_font(FONT_HEAVY_CANDIDATES, 16)
    for i, word in enumerate(["TRANSLATION", "MANAGER"]):
        wbbox = d.textbbox((0, 0), word, font=f_word)
        ww = wbbox[2] - wbbox[0]
        wx = (W - ww) // 2 - wbbox[0]
        wy = cy_y + 14 + i * 22
        glow_text(base, (wx, wy), word, f_word, COL_WHITE, COL_CYAN, glow_radius=3)

    # === Spec block (techy mono lines, dim) ===
    f_meta = _load_font(FONT_MONO_CANDIDATES, 11)
    meta_lines = [
        "> sys.init  [OK]",
        "> eel.bridge[OK]",
        "> ui.loader [OK]",
    ]
    my = H - 110
    for line in meta_lines:
        d.text((14, my), line, fill=COL_DIM, font=f_meta)
        my += 14

    # scanline overlay
    scan = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scan)
    for y in range(0, H, 3):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, 30), width=1)
    base.alpha_composite(scan)

    return base.convert("RGB")


# ────────────────────────────────────────────────────────────────────
# wizard-small.bmp  (150 × 57)
# ────────────────────────────────────────────────────────────────────
def make_wizard_small() -> Image.Image:
    W, H = 150, 57
    # horizontal-ish gradient: dark left, slightly purpler right
    base = Image.new("RGB", (W, H))
    px = base.load()
    for x in range(W):
        t = x / (W - 1)
        r = int(COL_BG_BOT[0] * (1 - t) + COL_BG_TOP[0] * t)
        g = int(COL_BG_BOT[1] * (1 - t) + COL_BG_TOP[1] * t)
        b = int(COL_BG_BOT[2] * (1 - t) + COL_BG_TOP[2] * t)
        for y in range(H):
            px[x, y] = (r, g, b)
    base = base.convert("RGBA")

    # subtle glow on the right (yellow)
    base.alpha_composite(radial_glow(W, H, W - 8, H // 2, 50, COL_YELLOW, alpha=110))

    # fine grid texture
    base.alpha_composite(circuit_grid(W, H, step=10, alpha=40))

    d = ImageDraw.Draw(base)

    # left "TM" badge — small chamfered square with yellow border
    box_w, box_h = 38, 38
    bx0, by0 = 8, (H - box_h) // 2
    bx1, by1 = bx0 + box_w, by0 + box_h
    d.rectangle([bx0, by0, bx1, by1], outline=(*COL_YELLOW, 230), width=2)
    f_tm = _load_font(FONT_HEAVY_CANDIDATES, 22)
    tm_bbox = d.textbbox((0, 0), "TM", font=f_tm)
    ttw = tm_bbox[2] - tm_bbox[0]
    tth = tm_bbox[3] - tm_bbox[1]
    tx = bx0 + (box_w - ttw) // 2 - tm_bbox[0]
    ty = by0 + (box_h - tth) // 2 - tm_bbox[1]
    glow_text(base, (tx, ty), "TM", f_tm, COL_YELLOW, COL_YELLOW, glow_radius=3)

    # wordmark to the right of badge
    f_w1 = _load_font(FONT_HEAVY_CANDIDATES, 13)
    glow_text(base, (bx1 + 8, 10), "TRANSLATION", f_w1, COL_WHITE, COL_CYAN, glow_radius=2)
    d = ImageDraw.Draw(base)
    d.text((bx1 + 8, 28), "MANAGER", fill=COL_WHITE, font=f_w1)

    # right-edge accent line (cyan)
    d.line([(W - 3, 6), (W - 3, H - 6)], fill=COL_CYAN, width=2)

    # subtle scanlines
    scan = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scan)
    for y in range(0, H, 3):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, 25), width=1)
    base.alpha_composite(scan)

    return base.convert("RGB")


# ────────────────────────────────────────────────────────────────────
# app.ico  — multi-resolution
# ────────────────────────────────────────────────────────────────────
def make_icon_512() -> Image.Image:
    """Render the source 512×512, then Image.save() down-scales for the ICO."""
    S = 512
    base = vertical_gradient(S, S, COL_BG_TOP, COL_BG_BOT).convert("RGBA")

    # big radial glow behind monogram
    base.alpha_composite(radial_glow(S, S, S // 2, S // 2 - 30, 280, (90, 60, 200), alpha=220))
    base.alpha_composite(radial_glow(S, S, S // 2, int(S * 0.78), 200, COL_CYAN, alpha=130))

    # circuit grid
    base.alpha_composite(circuit_grid(S, S, step=32, alpha=60))

    d = ImageDraw.Draw(base)

    # chamfered border
    chamfered_border(d, S, S, (*COL_CYAN, 200), inset=14, cut=44, width=6)
    chamfered_border(d, S, S, (*COL_YELLOW, 130), inset=24, cut=36, width=3)

    # huge "TM" monogram
    f_mono = _load_font(FONT_HEAVY_CANDIDATES, 280)
    bbox = d.textbbox((0, 0), "TM", font=f_mono)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (S - tw) // 2 - bbox[0]
    ty = (S - th) // 2 - bbox[1] - 30
    glow_text(base, (tx, ty), "TM", f_mono, COL_YELLOW, COL_YELLOW, glow_radius=14)

    # underline + label
    d = ImageDraw.Draw(base)
    d.line([(S * 0.18, S * 0.78), (S * 0.82, S * 0.78)], fill=(*COL_CYAN, 230), width=4)
    f_label = _load_font(FONT_HEAVY_CANDIDATES, 48)
    lbl = "TRANSLATION MANAGER"
    lbbox = d.textbbox((0, 0), lbl, font=f_label)
    lw = lbbox[2] - lbbox[0]
    lx = (S - lw) // 2 - lbbox[0]
    ly = int(S * 0.81) - lbbox[1]
    glow_text(base, (lx, ly), lbl, f_label, COL_WHITE, COL_CYAN, glow_radius=4)

    return base


def save_ico(img_512: Image.Image, path: Path) -> None:
    # Pillow's ICO writer will generate every requested size from the source.
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img_512.save(path, format="ICO", sizes=sizes)


# ────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────
def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)

    print("[gen] wizard-large.bmp  (164x314)…", end=" ", flush=True)
    big = make_wizard_large()
    big.save(HERE / "wizard-large.bmp", format="BMP")
    print("OK")

    print("[gen] wizard-small.bmp  (150x57)…", end=" ", flush=True)
    small = make_wizard_small()
    small.save(HERE / "wizard-small.bmp", format="BMP")
    print("OK")

    print("[gen] app.ico           (multi-res)…", end=" ", flush=True)
    icon_src = make_icon_512()
    save_ico(icon_src, HERE / "app.ico")
    # keep a PNG preview alongside so the user can inspect easily
    icon_src.convert("RGB").save(HERE / "app_512.png", format="PNG")
    print("OK")

    print()
    print("Wrote:")
    for f in ("wizard-large.bmp", "wizard-small.bmp", "app.ico", "app_512.png"):
        p = HERE / f
        print(f"  {p}    ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
