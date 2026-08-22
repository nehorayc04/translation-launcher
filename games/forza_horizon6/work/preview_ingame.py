"""Render the DEPLOYED strings with the DEPLOYED font, exactly as the engine will.

The engine draws glyphs in STORAGE order with no bidi (settled in-game by an
eight-row digit ladder), so laying the stored bytes out strictly left-to-right
reproduces what the screen shows. If this image reads as Hebrew, the game does
too — which is how a size/shape/spacing problem gets caught in a chat message
instead of a game launch.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_font as F                                                # noqa: E402
import fh6_str as S                                                 # noqa: E402
import fh6_zip as Z                                                 # noqa: E402
import numpy as np                                                  # noqa: E402
from PIL import Image, ImageDraw                                    # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
FAM = sys.argv[1] if len(sys.argv) > 1 else "Horizon_RU_A"
SIZE = 46.0
SS = 3                          # supersample, so the preview is not itself jaggy
BG = np.array([13, 13, 19], np.float32)
FG = np.array([238, 238, 244], np.float32)


def raster_into(canvas: "np.ndarray", tri: list, cvs: list) -> None:
    """Composite ONE triangle's analytic-AA coverage into `canvas` (max-blend).

    Reproduces the shader's `alpha = cv / fwidth(cv) + 0.5`: cv==1 (solid
    interior) has zero gradient -> full coverage; a cv that ramps across the
    AA-band quad (cv = +-W/edgeLength) produces a smooth analytic edge. This
    is the SAME math as `test_aa_band.raster(mode='cov')`, just composited
    directly onto the full preview canvas instead of a per-glyph box.
    """
    H, W = canvas.shape
    (ax, ay), (bx, by), (cx, cy) = tri
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-9:
        return
    lo_x = max(0, int(min(ax, bx, cx)))
    hi_x = min(W - 1, int(max(ax, bx, cx)) + 1)
    lo_y = max(0, int(min(ay, by, cy)))
    hi_y = min(H - 1, int(max(ay, by, cy)) + 1)
    if hi_x < lo_x or hi_y < lo_y:
        return
    yy, xx = np.mgrid[lo_y:hi_y + 1, lo_x:hi_x + 1]
    px, py = xx + 0.5, yy + 0.5
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
    l3 = 1 - l1 - l2
    inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
    if not inside.any():
        return
    cv0, cv1, cv2 = cvs
    val = l1 * cv0 + l2 * cv1 + l3 * cv2
    gx = ((by - cy) * cv0 + (cy - ay) * cv1 + (ay - by) * cv2) / den
    gy = ((cx - bx) * cv0 + (ax - cx) * cv1 + (bx - ax) * cv2) / den
    fw = abs(gx) + abs(gy)
    a = np.clip(val / fw + 0.5, 0, 1) if fw > 1e-9 else np.ones_like(val)
    sub = canvas[lo_y:hi_y + 1, lo_x:hi_x + 1]
    np.maximum(sub, np.where(inside, a, 0), out=sub)

ROWS = [
    ("Main", "IDS_MainMenuContinue"), ("Main", "IDS_MainMenuOptions"),
    ("Main", "IDS_MainMenuAccessibility"), ("Main", "IDS_MainMenuExit"),
    ("ScreenTitles", "IDS_GameOptions"), ("Main", "IDS_Options_AudioOptions"),
    ("Main", "IDS_Options_VideoOptions"), ("Main", "IDS_Options_GameOptions"),
    ("Main", "IDS_Options_LanguageSelect"), ("ScreenTitles", "IDS_Difficulty"),
    ("ScreenTitles", "IDS_AdvancedGraphicsOptions"),
    ("TiledMenus", "IDS_Options_TileTitle_Hud"),
    ("TiledMenus", "IDS_Options_TileText_Accessibility"),
    ("TiledMenus", "IDS_Options_TileText_Controls"),
    ("PauseMenu", "IDS_CatTitle_Campaign"), ("PauseMenu", "IDS_CatTitle_Store"),
    ("HelpButtons", "IDS_Select"), ("HelpButtons", "IDS_Back"),
    ("HelpButtons", "IDS_Confirm"), ("HelpButtons", "IDS_Apply"),
    ("InGame", "IDS_LanguageSelect_EN"), ("InGame", "IDS_LanguageSelect_CZ"),
]


def main() -> None:
    _, sp = Z.read(os.path.join(GAME, "media", "Stripped", "StringTables", "EN.zip"))
    _, fp = Z.read(os.path.join(GAME, "media", "UI", "Fonts.zip"))
    font = F.parse(fp[f"{FAM}.vfont"])
    page = fp[f"{FAM}.vfont0"]
    by = font.by_cp()

    tables = {t: S.parse(sp[t + ".str"]).as_dict() for t, _ in ROWS}
    lines = [(f"{t}/{i}", tables[t].get(i, "")) for t, i in ROWS]

    S_, LH = SIZE * SS, int(SIZE * 1.55)
    W, H = 1180, LH * len(lines) + 30
    cov = np.zeros((H * SS, W * SS), np.float32)
    for r, (name, text) in enumerate(lines):
        base = (30 + r * LH + SIZE) * SS
        pen = 40.0 * SS
        for ch in text:
            g = by.get(ord(ch))
            if g is None:
                pen += 0.3 * S_
                continue
            if g.n_verts:
                v, idx = F.read_mesh(page, g)
                scr = [(pen + (p[0] - F.X_BIAS) * S_, base - p[1] * S_) for p in v]
                for i in range(0, len(idx), 3):
                    a, b, c = idx[i], idx[i + 1], idx[i + 2]
                    raster_into(cov, [scr[a], scr[b], scr[c]],
                                [v[a][3], v[b][3], v[c][3]])
            pen += g.adv * S_
    img = BG + (FG - BG) * cov[..., None]
    im = Image.fromarray(img.astype(np.uint8)).resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for r, (name, _) in enumerate(lines):
        base = 30 + r * LH + SIZE
        d.text((W - 330, int(base - SIZE * 0.75)), name, fill=(92, 92, 108))
    p = os.path.join(HERE, "..", "extract", f"ingame_preview_{FAM}.png")
    im.save(p)
    print(f"{p}")
    for name, text in lines:
        print(f"  {name:<46s} {text!r}")


main()
