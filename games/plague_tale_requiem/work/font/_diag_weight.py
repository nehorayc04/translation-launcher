# -*- coding: utf-8 -*-
"""Calibrate the Hebrew WEIGHT against the vanilla English in the SAME frame.

The user's own screenshot has the settings menu in ENGLISH (vanilla Latin font, vanilla
requested size) — a perfect calibrated ruler for the Hebrew that replaces it. Measure:
  1. English: x-height, stroke width, stroke/x-height, ink density, AA mid/solid
  2. our deployed Hebrew (from the atlas, scaled to the same on-screen size)
  3. every candidate Hebrew weight at the shipping body, through the SAME render path
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import (decode_alpha, resolve_mat_textures, NPIX, BIG,
                               render_set, cap_span, fit_body, HEBREW, LADDER_INK, BOX_H_FIX)

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
SHOT = os.path.join(SC, "AUTOCHECK_small.png")
GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"


def runs_of(mask):
    out = []
    for y in range(mask.shape[0]):
        n = 0
        for v in mask[y]:
            if v:
                n += 1
            elif n:
                out.append(n); n = 0
        if n:
            out.append(n)
    return out


def english_ref():
    im = np.array(Image.open(SHOT).convert("L")).astype(np.int16)
    # the whole label column of the English settings menu
    reg = 255 - im[275:805, 175:435]
    m = reg > (reg.mean() + 2.2 * reg.std())
    # x-height band: rows whose ink is the lowercase body. Use per-blob heights like before,
    # but for STROKE just take the horizontal runs over all ink (dominated by lowercase stems).
    r = [v for v in runs_of(m) if v <= 8]          # ignore long horizontal bars/underlines
    ink = reg[m]
    soft = reg[(reg > reg.mean() + 0.8 * reg.std()) & ~m]
    print(f"ENGLISH (vanilla, same widget):")
    print(f"   stroke median = {np.median(r):.2f}px   p25={np.percentile(r,25):.1f} "
          f"p75={np.percentile(r,75):.1f}   (x-height 12px measured)")
    print(f"   stroke / x-height = {np.median(r)/12.0:.3f}")
    print(f"   AA mid/solid = {len(soft)/max(len(ink),1):.2f}")
    return np.median(r) / 12.0


def deployed_hebrew():
    D = DpcRepack(GAME)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache = {}
    runs, solid, mid, body = [], 0, 0, 0
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEBREW or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        a = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        ys = np.where((a > 60).any(axis=1))[0]
        if not len(ys):
            continue
        if c == "נ":
            body = ys.max() - ys.min() + 1
        band = a[ys.min():ys.max() + 1]
        runs += [v for v in runs_of(band > 128) if v <= 10]
        solid += int((band > 200).sum()); mid += int(((band > 30) & (band <= 200)).sum())
    sw = float(np.median(runs))
    print(f"\nOUR HEBREW (deployed atlas, body={body}px, box={BOX_H_FIX}):")
    print(f"   stroke median = {sw:.2f}px   stroke / body = {sw/max(body,1):.3f}")
    print(f"   AA mid/solid = {mid/max(solid,1):.2f}")
    return sw / max(body, 1)


def candidates(target_ratio):
    print(f"\nCANDIDATE WEIGHTS at body {LADDER_INK[0]}px  (target stroke/body = {target_ratio:.3f})")
    import glob
    cands = sorted(glob.glob(r"C:\Windows\Fonts\opensanshebrew-*.ttf"))
    cands = [c for c in cands if "italic" not in os.path.basename(c).lower()]
    cands += [r"C:\Windows\Fonts\Alef-regular.ttf", r"C:\Windows\Fonts\lvnm.ttf",
              r"C:\Windows\Fonts\mriam.ttf", r"C:\Windows\Fonts\ptilnarrow-regular-webfont.ttf"]
    for p in cands:
        if not os.path.exists(p):
            continue
        try:
            gs = cap_span(render_set(p, fit_body(p, LADDER_INK[0]), HEBREW))
        except Exception as ex:
            print(f"   {os.path.basename(p):<44} ERR {ex}"); continue
        runs, solid, mid = [], 0, 0
        body = gs["נ"][0].shape[0]
        for ch, (g, _a) in gs.items():
            runs += [v for v in runs_of(g > 128) if v <= 10]
            solid += int((g > 200).sum()); mid += int(((g > 30) & (g <= 200)).sum())
        sw = float(np.median(runs)) if runs else 0
        r = sw / max(body, 1)
        flag = "  <== closest" if abs(r - target_ratio) < 0.012 else ""
        print(f"   {os.path.basename(p):<44} body={body:>3} stroke={sw:>4.1f} "
              f"ratio={r:.3f}  mid/solid={mid/max(solid,1):.2f}{flag}")


t = english_ref()
deployed_hebrew()
candidates(t)
