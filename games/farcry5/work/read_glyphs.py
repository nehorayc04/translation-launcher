"""Read the Hebrew off an in-game screenshot by MATCHING glyphs against the atlas.

Transcribing Hebrew from an image by eye reports READING order, not pixel order, which is
exactly the wrong answer when the question is "did the engine reorder my string?"
([[hebrew-screenshot-transcription-trap]]).  So don't read it -- correlate each rendered
glyph against the 27 known atlas bitmaps and print the letters in strict LEFT-TO-RIGHT
pixel order.  That is data, not judgement.

  python -u read_glyphs.py <shot.png> <x0> <y0> <x1> <y1>
"""
import sys, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "extract")
sys.path.insert(0, HERE)
from fc5_font import Atlas, parse_fnt

at = Atlas(os.path.join(OUT, "hebrew.xbt"))
chars = parse_fnt(os.path.join(OUT, "hebrew_roundtrip.fnt"))
EDGE = 99

# reference bitmaps for the 27 letters, thresholded like the UI shader does
refs = {}
for cp in range(0x05D0, 0x05EB):
    if cp not in chars:
        continue
    x, y, w, h, *_ = chars[cp]
    if w <= 0:
        continue
    g = at.mip0[int(round(y)):int(round(y + h)), int(round(x)):int(round(x + w))]
    m = (g >= EDGE)
    ys, xs = np.where(m)
    if not len(ys):
        continue
    refs[cp] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def norm(a, size=(24, 24)):
    return np.array(Image.fromarray((a * 255).astype(np.uint8)).resize(size,
                    Image.BILINEAR)) / 255.0


REF = {cp: norm(m) for cp, m in refs.items()}


def read(path, box):
    im = Image.open(path).convert("L")
    crop = np.array(im.crop(box)).astype(float)
    # menu text is light on a dark panel
    thr = (crop.max() + crop.mean()) / 2
    m = crop >= thr
    cols = m.sum(axis=0)
    runs, st = [], None
    for i, c in enumerate(cols):
        if c > 0 and st is None:
            st = i
        elif c == 0 and st is not None:
            if i - st >= 3:
                runs.append((st, i))
            st = None
    if st is not None and len(cols) - st >= 3:
        runs.append((st, len(cols)))
    print(f"  {os.path.basename(path)} {box}  -> {len(runs)} glyph runs")
    seq = []
    for a, b in runs:
        sub = m[:, a:b]
        ys = np.where(sub.sum(axis=1) > 0)[0]
        if not len(ys):
            continue
        sub = sub[ys.min():ys.max() + 1]
        q = norm(sub)
        best, sc = None, -1
        for cp, r in REF.items():
            s = float((q * r).sum() / np.sqrt((q * q).sum() * (r * r).sum() + 1e-9))
            if s > sc:
                sc, best = s, cp
        seq.append((chr(best), sc, b - a))
    print("   left-to-right: " + "  ".join(f"{c}({s:.2f})" for c, s, _ in seq))
    return "".join(c for c, _, _ in seq)


if __name__ == "__main__":
    shot = sys.argv[1]
    box = tuple(int(v) for v in sys.argv[2:6])
    print("PIXEL ORDER =", read(shot, box))
