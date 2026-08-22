# -*- coding: utf-8 -*-
"""Render the EXPECTED line from the deployed atlas + our own metrics, fit the
scale by correlation against the real in-game frame, and diff them.

Any ink the engine failed to draw (a clipped line end, a lost detached leg)
shows up as a bright region in the diff — and the fit is done on the whole line,
so it cannot be fooled by a threshold choice.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"


def load():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, g = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g[c] = dict(img=cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)],
                    bw=float(e.x1 - e.x0), bh=float(e.y1 - e.y0),
                    bx=float(e.bx), adv=float(e.x1 - e.x0) + float(e.bx))
    return g


SPACE = 14.0        # atlas units for a space (approx; fitted below if needed)


def render(text, g, s, pad=8):
    """RTL: first char at the right. Returns a float array (0..255)."""
    total = 0.0
    for ch in text:
        total += SPACE if ch == " " else g[ch]["adv"]
    W = int(round(total * s)) + 2 * pad
    H = int(round(max(x["bh"] for x in g.values()) * s)) + 2 * pad
    cv = np.zeros((H, W), float)
    pen = W - pad                                     # right edge
    for ch in text:
        if ch == " ":
            pen -= SPACE * s
            continue
        e = g[ch]
        w = max(1, int(round(e["bw"] * s)))
        h = max(1, int(round(e["bh"] * s)))
        im = np.asarray(Image.fromarray(e["img"], "L").resize((w, h), Image.BILINEAR), float)
        x = int(round(pen - e["adv"] * s))
        if x < 0:
            x = 0
        cv[pad:pad + h, x:x + w] = np.maximum(cv[pad:pad + h, x:x + w], im[:, :cv.shape[1] - x])
        pen -= e["adv"] * s
    return cv


def main():
    g = load()
    im = Image.open(os.path.join(SC, "AUTOCHECK_pad.png")).convert("L")
    real = 255 - np.asarray(im.crop((450, 380, 725, 430)), float)
    real = np.clip((real - 70) * (255 / 150), 0, 255)      # background out
    text = "לחץ על מקש כלשהו"
    best = None
    for s100 in range(60, 130):
        s = s100 / 100.0
        exp = render(text, g, s)
        if exp.shape[0] > real.shape[0] + 20 or exp.shape[1] > real.shape[1] + 30:
            continue
        # slide
        for dy in range(-6, 7):
            for dx in range(-12, 13):
                H = min(exp.shape[0], real.shape[0])
                W = min(exp.shape[1], real.shape[1])
                A = np.zeros_like(real); B = np.zeros_like(real)
                A[:min(H, real.shape[0]), :min(W, real.shape[1])] = \
                    exp[:min(H, real.shape[0]), :min(W, real.shape[1])]
                A = np.roll(np.roll(A, dy, 0), dx, 1)
                B = real
                num = float((A * B).sum())
                den = float(np.sqrt((A * A).sum() * (B * B).sum())) or 1.0
                sc = num / den
                if best is None or sc > best[0]:
                    best = (sc, s, dy, dx)
    sc, s, dy, dx = best
    print(f"best correlation {sc:.4f} at scale {s:.2f} offset dy={dy} dx={dx}")
    exp = render(text, g, s)
    A = np.zeros_like(real)
    H = min(exp.shape[0], real.shape[0]); W = min(exp.shape[1], real.shape[1])
    A[:H, :W] = exp[:H, :W]
    A = np.roll(np.roll(A, dy, 0), dx, 1)
    miss = np.clip(A - real, 0, 255)          # expected but NOT drawn
    extra = np.clip(real - A, 0, 255)
    print(f"missing ink energy {miss.sum()/max(A.sum(),1)*100:.1f}%   "
          f"extra {extra.sum()/max(A.sum(),1)*100:.1f}%")
    colw = np.where((miss > 90).any(axis=0))[0]
    if len(colw):
        print(f"columns with strong MISSING ink: {colw.min()}..{colw.max()} "
              f"(line spans 0..{real.shape[1]})")
        hist = [(int(c), int((miss[:, c] > 90).sum())) for c in colw]
        print("   ", hist[:40])
    out = np.vstack([np.clip(real, 0, 255), np.clip(A, 0, 255), miss])
    Image.fromarray((255 - out).astype(np.uint8), "L").resize(
        (out.shape[1] * 3, out.shape[0] * 3), Image.NEAREST).save(
        os.path.join(SC, "OVERLAY_startline.png"))
    print("saved OVERLAY_startline.png  (top=real, middle=expected, bottom=missing)")


main()
