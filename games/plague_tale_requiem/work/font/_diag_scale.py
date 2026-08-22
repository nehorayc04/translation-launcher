# -*- coding: utf-8 -*-
"""DECISIVE size-model probe: compare the SAME Latin letters across the BIG (cap79)
font and the small subtitle font (cap51). If the only difference is a proportional
box+metrics, on-screen size is atlas-driven (shrinkable). If there is an extra scalar
(line-height/point-size) it will show in the header/tail footer -> that's the real lever."""
import sys, struct
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
FONTS = {
    "BIG_ARABIC(79)": 0xAFBE3792DDA3B358,
    "D4(92)":         0xD4BE9C5580916197,
    "31(79)":         0x31234526891B91BA,
    "C20(51)":        0xC20BD87B48DDCD4C,
    "98(36)":         0x98B16FA4A756F927,
}

D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}

for label, oid in FONTS.items():
    o = byid.get(oid)
    if o is None:
        print(f"{label}: MISSING"); continue
    fz = FontsZ(o.body)
    m2t = resolve_mat_textures(byid, fz)
    print(f"\n=== {label}  oid={oid:016X} count={fz.count} tail_len={len(fz.tail)} ===")
    # header: bytes right after count? (already consumed). show entry 0 raw + tail head.
    matn = struct.unpack_from("<I", fz.tail, 0)[0] if len(fz.tail) >= 4 else -1
    print(f"  material_count={matn}  tail(first 96 bytes hex):")
    print("   ", fz.tail[:96].hex())
    # footer AFTER the material-id table (4 + matn*8) -> likely where a scale/line-height sits
    foot_off = 4 + max(0, matn) * 8
    foot = fz.tail[foot_off:foot_off + 96]
    print(f"  footer @+{foot_off} ({len(fz.tail)-foot_off} bytes), first 96 hex:")
    print("   ", foot.hex())
    # decode the footer as floats + ints to spot a size/line-height field
    if len(foot) >= 32:
        fl = struct.unpack_from("<8f", foot, 0)
        it = struct.unpack_from("<8i", foot, 0)
        print("    as f32:", [round(x, 2) for x in fl])
        print("    as i32:", list(it))
    # per-letter metrics for H,A,o,i
    for ref in "HAoi":
        e = next((x for x in fz.entries if cid_to_char(x.cid) == ref and x.mat in m2t), None)
        if not e:
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        bw, bh = x1 - x0, y1 - y0
        ih = 0
        if x1 > x0 and y1 > y0:
            a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
            ys, _ = np.where(a > 100)
            ih = (ys.max() - ys.min() + 1) if len(ys) else 0
        print(f"  '{ref}': adv={e.adv:7.2f} box={bw}x{bh} ink_h={ih} bx={e.bx:.2f} by={e.by:.2f} z={e.z}")
