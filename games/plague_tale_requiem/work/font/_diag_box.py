# -*- coding: utf-8 -*-
"""THE decisive offline measurement for the two open defects (size + 'noise around a box').

User's new observation: a dark rectangle EXACTLY around each letter, letters cut with no
transition, and around the rectangle noise 'like bigger text behind it'.

That is the signature of UPSCALING: if the engine maps each glyph's DECLARED BOX to a fixed
on-screen cell, then
  * original Arabic: box ~74-90px -> DOWNscaled to the cell  => smooth, and the ink fills it
  * our Hebrew:      box ~30-40px -> UPscaled ~2x to the cell => every DXT5 block edge and the
                     colour fringe becomes 2px+ wide = 'noise', and the ink still fills the
                     cell = 'too big'.

Measure, on ORIGINAL vs DEPLOYED:
  1. declared box size, ink size, fill ratio (ink_h / box_h)  <- the size lever
  2. does ink ESCAPE the declared box (leftovers around it)   <- the 'text behind' candidate
  3. available slot heights (how tall an em-box we could declare)
  4. a WIDE picture around one glyph of each, both channels   <- so I can SEE what the user sees
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX, BIG, is_ar

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")


def load(path):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    pages = {}

    def pg(t):
        if t not in pages:
            raw = byid[t].body
            pages[t] = (decode_alpha(bytearray(raw[:NPIX])), decode_color(bytearray(raw[:NPIX])))
        return pages[t]
    return fz, m2t, pg


def report(path, label, pick, limit=14):
    fz, m2t, pg = load(path)
    print(f"\n=== {label} ===")
    print(f"{'ch':>3} {'box w x h':>11} {'ink w x h':>11} {'fill_h':>7} {'fill_w':>7} "
          f"{'escape':>7} {'adv':>6}")
    rows = []
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and pick(ord(c))):
            continue
        if e.mat not in m2t:
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        bw, bh = x1 - x0, y1 - y0
        if bw < 6 or bh < 6:
            continue
        a, _ = pg(m2t[e.mat])
        box = a[y0:y1, x0:x1]
        ys, xs = np.where(box > 60)
        if len(ys) < 10:
            continue
        ih, iw = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
        # ink OUTSIDE the declared box, within a 45px halo (would render as 'text behind')
        hy0, hy1 = max(0, y0 - 45), min(512, y1 + 45)
        hx0, hx1 = max(0, x0 - 45), min(512, x1 + 45)
        halo = a[hy0:hy1, hx0:hx1].astype(np.int32).copy()
        halo[y0 - hy0:y1 - hy0, x0 - hx0:x1 - hx0] = 0
        esc = int((halo > 60).sum())
        rows.append((c, bw, bh, iw, ih, ih / bh, iw / bw, esc, e.adv))
        if len(rows) >= limit:
            break
    for c, bw, bh, iw, ih, fh, fw, esc, adv in rows:
        print(f"{c:>3} {bw:>4} x {bh:<4} {iw:>4} x {ih:<4} {fh:>7.2f} {fw:>7.2f} "
              f"{esc:>7} {adv:>6.0f}")
    if rows:
        print(f"  MEAN  box_h={np.mean([r[2] for r in rows]):.0f}  ink_h={np.mean([r[4] for r in rows]):.0f}"
              f"  fill_h={np.mean([r[5] for r in rows]):.2f}  fill_w={np.mean([r[6] for r in rows]):.2f}"
              f"  escaped_ink_px={np.mean([r[7] for r in rows]):.0f}")
    return rows


def slot_sizes(path):
    """How tall a box could we declare?  (repurposable Arabic slots, sorted by height)"""
    fz, m2t, pg = load(path)
    sl = [(int(e.x1 - e.x0), int(e.y1 - e.y0)) for e in fz.entries
          if e.mat in m2t and (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
    sl.sort(key=lambda t: -t[1])
    print(f"\n=== repurposable Arabic slots (n={len(sl)}), tallest first ===")
    print("  top 40 heights:", [h for _, h in sl[:40]])
    for need in (60, 66, 70, 74, 80):
        n = sum(1 for w, h in sl if h >= need and w >= 30)
        print(f"  slots >= 30 x {need}: {n}")


def picture(path, label, pick, out):
    """Wide crop around ONE glyph, alpha + colour, x6 — so the halo is visible."""
    fz, m2t, pg = load(path)
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and pick(ord(c)) and e.mat in m2t):
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        if (x1 - x0) < 12 or (y1 - y0) < 12:
            continue
        a, g = pg(m2t[e.mat])
        m = 30
        hy0, hy1 = max(0, y0 - m), min(512, y1 + m)
        hx0, hx1 = max(0, x0 - m), min(512, x1 + m)
        A = a[hy0:hy1, hx0:hx1]
        G = g[hy0:hy1, hx0:hx1]
        # mark the declared box in a 3rd panel (red frame over alpha)
        rgb = np.dstack([A, A, A]).astype(np.uint8)
        ry0, ry1, rx0, rx1 = y0 - hy0, y1 - hy0, x0 - hx0, x1 - hx0
        rgb[ry0, rx0:rx1] = (255, 0, 0); rgb[ry1 - 1, rx0:rx1] = (255, 0, 0)
        rgb[ry0:ry1, rx0] = (255, 0, 0); rgb[ry0:ry1, rx1 - 1] = (255, 0, 0)
        h, w = A.shape
        sheet = Image.new("RGB", (w * 3 + 20, h), (0, 0, 40))
        sheet.paste(Image.fromarray(A, "L").convert("RGB"), (0, 0))
        sheet.paste(Image.fromarray(G, "L").convert("RGB"), (w + 10, 0))
        sheet.paste(Image.fromarray(rgb, "RGB"), (w * 2 + 20, 0))
        sheet = sheet.resize((sheet.width * 5, sheet.height * 5), Image.NEAREST)
        sheet.save(out)
        print(f"  {label}: '{c}' box={x1-x0}x{y1-y0} -> {out}  (alpha | colour | box-marked)")
        return


heb = lambda cp: 0x05D0 <= cp <= 0x05EA
report(GAME + ".he_backup", "ORIGINAL Arabic glyphs (the shipped font)", is_ar)
report(GAME, "OUR Hebrew glyphs (deployed)", heb)
slot_sizes(GAME + ".he_backup")
print("\n=== wide pictures (alpha | colour | box) ===")
picture(GAME + ".he_backup", "ORIGINAL", is_ar, os.path.join(SC, "BOX_original.png"))
picture(GAME, "DEPLOYED", heb, os.path.join(SC, "BOX_deployed.png"))
