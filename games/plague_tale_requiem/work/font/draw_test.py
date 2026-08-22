#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draw_test.py — decisive isolation of the BC3 draw/encode on the CONFIRMED page.

Repurpose-to-A already proved: lookup works, mat=1 -> tex EFC73FAE is correct,
box (420,214)-(501,303) renders. So point ALL 27 Hebrew letters at THAT exact box
on mat=1, and DRAW a real 'א' into it (re-encoding those blocks). In-game every
Hebrew char must then show the drawn 'א'. If it does -> draw+encode+box all work.
If tofu -> my BC3 encode is not GPU-valid.
"""
from __future__ import annotations
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dpc_repack import DpcRepack
from fonts_z import FontsZ, char_to_cid, cid_to_char
from inject_atlas import decode_alpha, encode_block, resolve_mat_textures

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIG = 0xAFBE3792DDA3B358
HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]
BOX = (420, 214, 501, 303)          # 'A' box on mat=1 (confirmed)
TEX1 = 0xEFC73FAE0445DAB6
BACKUP = ".he_backup"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpc", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    if args.revert:
        import shutil
        b = args.dpc + BACKUP
        shutil.copy2(b, args.dpc); print("reverted from", b); return

    src = args.dpc + BACKUP if os.path.exists(args.dpc + BACKUP) else args.dpc
    D = DpcRepack(src)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fm = byid[BIG]; fz = FontsZ(fm.body)
    src_e = next(e for e in fz.entries if cid_to_char(e.cid) == "A")

    # render 'א' to the A-box size, draw into tex1 at BOX, re-encode blocks
    x0, y0, x1, y1 = BOX
    w, h = x1 - x0, y1 - y0
    font = ImageFont.truetype(r"C:\Windows\Fonts\FRANKB.TTF", 96)
    im = Image.new("L", (w, h), 0); d = ImageDraw.Draw(im)
    b = font.getbbox("א")
    gw, gh = b[2] - b[0], b[3] - b[1]
    d.text(((w - gw) // 2 - b[0], (h - gh) // 2 - b[1]), "א", fill=255, font=font)
    glyph = np.array(im)

    t = byid[TEX1]
    head, blocks = t.body[:4], bytearray(t.body[4:])
    alpha = decode_alpha(blocks)
    alpha[y0:y1, x0:x1] = glyph
    touched = {(yy // 4, xx // 4) for yy in range(y0, y1) for xx in range(x0, x1)}
    bpr = 512 // 4
    for (by, bx) in touched:
        o = (by * bpr + bx) * 16
        blocks[o:o + 16] = encode_block(alpha[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4])
    t.body = head + bytes(blocks); t.dirty = True
    print(f"drew 'א' into tex1 at {BOX}; {len(touched)} blocks re-encoded")

    # repurpose 27 Arabic entries -> Hebrew, all pointing at BOX on mat=1 (A's metrics)
    def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF
    ar = [e for e in fz.entries if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
    for e, ch in zip(ar, HEBREW):
        e.cid = char_to_cid(ch)
        e.mat = src_e.mat
        e.adv, e.x0, e.y0, e.x1, e.y1 = src_e.adv, float(x0), float(y0), float(x1), float(y1)
        e.bx, e.by = src_e.bx, src_e.by
    fm.body = fz.build(); fm.dirty = True

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ENGLISH_he.DPC")
    rebuilt = D.build(); open(out, "wb").write(rebuilt)
    print(f"rebuilt {len(rebuilt)} (delta {len(rebuilt)-len(D.data):+d})")
    if args.deploy:
        import shutil
        if not os.path.exists(args.dpc + BACKUP):
            shutil.copy2(args.dpc, args.dpc + BACKUP)
        shutil.copy2(out, args.dpc); print("DEPLOYED ->", args.dpc)


if __name__ == "__main__":
    main()
