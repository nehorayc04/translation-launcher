# -*- coding: utf-8 -*-
"""Per-glyph audit of the START-SCREEN line in the CURRENT build's capture.

Large text, the exact surface the user complained about ("letters at the end of
the sentence are cut"). We know the string, so blob i maps to a known character;
compare each rendered ink width against the atlas ink width at the line's scale.
A low threshold is used on BOTH sides so soft edges are not mistaken for a clip.
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
THR = 40                      # same threshold used on atlas and on screen


def inks():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, out = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        ys = np.where((g > THR).any(axis=1))[0]
        xs = np.where((g > THR).any(axis=0))[0]
        out[c] = dict(w=int(xs.max() - xs.min() + 1), h=int(ys.max() - ys.min() + 1))
    return out


def main(shot, box, text, label, invert):
    info = inks()
    im = Image.open(shot).convert("L")
    a = np.asarray(im.crop(box), float)
    a = (255 - a) if invert else a          # light text on dark -> keep as is
    ink = a > THR
    cols = ink.any(axis=0)
    sp, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        elif not v and s is not None:
            sp.append([s, i]); s = None
    if s is not None:
        sp.append([s, len(cols)])
    m = []
    for x0, x1 in sp:
        if m and x0 - m[-1][1] <= 2:
            m[-1][1] = x1
        else:
            m.append([x0, x1])
    letters = [c for c in text if c != " "]
    rows = np.where(ink.any(axis=1))[0]
    lh = rows.max() - rows.min() + 1
    print(f"\n=== {label}: {len(m)} blobs vs {len(letters)} letters, line ink h={lh} ===")
    if len(m) != len(letters):
        print("    blob/char mismatch — widths only:",
              [(b[0], b[1] - b[0]) for b in m])
        return
    order = list(reversed(letters))
    # scale fitted on the middle letters
    r = [(m[i][1] - m[i][0]) / info[c]["w"] for i, c in enumerate(order)
         if 0 < i < len(order) - 1 and c in info]
    scale = float(np.median(r))
    print(f"    fitted scale {scale:.4f}")
    worst = []
    for i, c in enumerate(order):
        w = m[i][1] - m[i][0]
        exp = info[c]["w"] * scale
        d = w - exp
        role = "LAST(line end)" if i == 0 else ("FIRST" if i == len(order) - 1 else "")
        flag = "  *** SHORT ***" if d < -1.5 else ""
        worst.append(d)
        print(f"    #{i:2d} '{c}' rendered {w:3d}  expected {exp:5.1f}  delta {d:+5.1f} {role}{flag}")
    print(f"    -> line-end delta {worst[0]:+.1f}px, median middle delta "
          f"{np.median(worst[1:-1]):+.1f}px")


if __name__ == "__main__":
    shot = os.path.join(SC, "AUTOCHECK_pad.png")
    # start screen: light text on a light-grey sky -> text is DARK, so invert
    main(shot, (440, 375, 730, 425), "לחץ על מקש כלשהו", "START PROMPT (current build)", True)
