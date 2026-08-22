# -*- coding: utf-8 -*-
"""Simulate what the ENGINE draws: take the DEPLOYED atlas glyphs, apply the engine's own
scale (REQ / BOX_H) with bilinear filtering exactly as the GPU does, and measure the resulting
per-letter ink height. This is the offline proof that the letters now render at ONE height —
the ±1 px atlas lottery is what the user saw as "no consistency between the letters".
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG, BOX_H_FIX

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
REQ_MENU = 32.5          # measured from the live settings menu at 1600x900


def main():
    D = DpcRepack(GAME)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, glyphs = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        glyphs[c] = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]

    s = REQ_MENU / BOX_H_FIX
    print(f"engine scale = REQ {REQ_MENU} / BOX_H {BOX_H_FIX} = {s:.4f}")
    hs, rows = {}, []
    for c in HEB:
        g = glyphs.get(c)
        if g is None:
            continue
        h, w = g.shape
        sm = np.array(Image.fromarray(g, "L").resize(
            (max(1, int(round(w * s))), max(1, int(round(h * s)))), Image.BILINEAR))
        ys = np.where((sm > 60).any(axis=1))[0]
        if not len(ys):
            continue
        ih = int(ys.max() - ys.min() + 1)
        top = int(ys.min())
        hs[c] = ih
        rows.append((c, top, ih))
    ordn = [r for r in rows if r[0] not in "לי" + "ךןףץק"]
    dsc = [r for r in rows if r[0] in "ךןףץק"]
    print(f"\nORDINARY  n={len(ordn)}  screen heights = {sorted({r[2] for r in ordn})}   "
          f"tops = {sorted({r[1] for r in ordn})}")
    print(f"DESCENDER n={len(dsc)}  screen heights = {sorted({r[2] for r in dsc})}   "
          f"tops = {sorted({r[1] for r in dsc})}")
    for c in "לי":
        if c in hs:
            print(f"  {c}: screen height {hs[c]}px")
    ok = len({r[2] for r in ordn}) == 1 and len({r[1] for r in ordn}) == 1
    print(f"\nVERDICT: {'ONE HEIGHT, ONE BASELINE — consistent' if ok else 'STILL VARIES'}")

    # render a real word so the result is also visible
    word = "הגדרות המשחק"
    imgs = []
    for c in word:
        if c == " ":
            imgs.append(np.zeros((1, max(2, int(6 * s))), np.uint8)); continue
        g = glyphs.get(c)
        if g is None:
            continue
        h, w = g.shape
        imgs.append(np.array(Image.fromarray(g, "L").resize(
            (max(1, int(round(w * s))), max(1, int(round(h * s)))), Image.BILINEAR)))
    H = max(i.shape[0] for i in imgs)
    W = sum(i.shape[1] + 2 for i in imgs)
    canvas = np.zeros((H + 8, W + 8), np.uint8)
    x = 4
    for i in imgs:
        canvas[4:4 + i.shape[0], x:x + i.shape[1]] = np.maximum(
            canvas[4:4 + i.shape[0], x:x + i.shape[1]], i)
        x += i.shape[1] + 2
    out = os.path.join(SC, "SIM_SCREEN.png")
    Image.fromarray(255 - canvas, "L").resize(
        (canvas.shape[1] * 6, (canvas.shape[0]) * 6), Image.NEAREST).save(out)
    print(f"saved {out}  (x6, the word rendered at the engine's own scale)")


main()
