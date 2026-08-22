#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roundtrip_test.py — re-encode tex1's ALPHA with ADAPTIVE per-block endpoints
(faithful to the original narrow-range distance field), preserve the colour block
verbatim, and point Hebrew at 'A'. If 'A' still renders clean in-game, my adaptive
alpha encoder is format-faithful (and the earlier fixed 255/0 endpoints were the
bug). If it shows dots, the format is deeper than BC3-alpha.
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, char_to_cid, cid_to_char
from inject_atlas import decode_alpha

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIG = 0xAFBE3792DDA3B358
TEX1 = 0xEFC73FAE0445DAB6
HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]
BACKUP = ".he_backup"


def enc_alpha_adaptive(cell):
    """8-byte DXT5 alpha block with adaptive endpoints (a0=max, a1=min)."""
    lo, hi = int(cell.min()), int(cell.max())
    if hi == lo:
        a0, a1 = hi, lo
        lut = [a0] * 8
    else:
        a0, a1 = hi, lo  # a0>a1 -> 8-value mode
        lut = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    bits = 0
    for i in range(16):
        v = int(cell[i // 4, i % 4])
        idx = min(range(8), key=lambda k: abs(lut[k] - v))
        bits |= idx << (3 * i)
    return bytes([a0, a1]) + bits.to_bytes(6, "little")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpc", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    if args.revert:
        import shutil; shutil.copy2(args.dpc + BACKUP, args.dpc); print("reverted"); return

    src = args.dpc + BACKUP if os.path.exists(args.dpc + BACKUP) else args.dpc
    D = DpcRepack(src)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    t = byid[TEX1]
    head, blocks = t.body[:4], bytearray(t.body[4:])
    alpha = decode_alpha(blocks)
    orig_alpha = alpha.copy()
    bpr = 512 // 4
    for by in range(128):
        for bx in range(128):
            o = (by * bpr + bx) * 16
            blocks[o:o + 8] = enc_alpha_adaptive(alpha[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4])
    # offline fidelity check
    re_alpha = decode_alpha(blocks)
    err = np.abs(re_alpha.astype(int) - orig_alpha.astype(int))
    print(f"adaptive alpha round-trip: max_err={err.max()} mean_err={err.mean():.2f}")
    t.body = head + bytes(blocks); t.dirty = True

    # repurpose 27 Arabic -> Hebrew pointing at 'A'
    fm = byid[BIG]; fz = FontsZ(fm.body)
    A = next(e for e in fz.entries if cid_to_char(e.cid) == "A")

    def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF
    ar = [e for e in fz.entries if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
    for e, ch in zip(ar, HEBREW):
        e.cid = char_to_cid(ch); e.mat = A.mat
        e.adv, e.x0, e.y0, e.x1, e.y1 = A.adv, A.x0, A.y0, A.x1, A.y1
        e.bx, e.by = A.bx, A.by
    fm.body = fz.build(); fm.dirty = True

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ENGLISH_he.DPC")
    open(out, "wb").write(D.build())
    print("wrote", out)
    if args.deploy:
        import shutil
        if not os.path.exists(args.dpc + BACKUP):
            shutil.copy2(args.dpc, args.dpc + BACKUP)
        shutil.copy2(out, args.dpc); print("DEPLOYED ->", args.dpc)


if __name__ == "__main__":
    main()
