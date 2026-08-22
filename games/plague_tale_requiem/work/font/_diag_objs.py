# -*- coding: utf-8 -*-
"""Enumerate ALL objects in ENGLISH.DPC. Goal: find a FONT DESCRIPTOR object (separate
from the Fonts_Z glyph table) that carries a size/line-height field = the real size lever.
Group by otype; for each Fonts_Z, look for a SMALL sibling object that references its oid."""
import sys, struct
sys.path.insert(0, ".")
from collections import Counter, defaultdict
from dpc_repack import DpcRepack
from fonts_z import FontsZ

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
FONT_OIDS = {
    0xAFBE3792DDA3B358: "BIG_ARABIC",
    0xD4BE9C5580916197: "D4_big",
    0x31234526891B91BA: "31_big",
    0xC20BD87B48DDCD4C: "C20_small",
    0x98B16FA4A756F927: "98_small",
    0x7737F14CA68D3761: "77?",
    0xF4861F247835A182: "F4?",
}

D = DpcRepack(DPC + ".he_backup")
allobj = list(D.db_objs) + [o for _, o, _ in D.fb_objs]
byid = {o.oid: o for o in allobj}
print(f"total objects: {len(allobj)}")

# object-type histogram
tc = Counter(o.otype for o in allobj)
print("\notype histogram (otype -> count):")
for t, c in tc.most_common():
    print(f"  {t:016X} : {c}")

# which otype are the Fonts_Z? and are there OTHER small objects referencing them?
fz_type = byid[0xAFBE3792DDA3B358].otype
print(f"\nFonts_Z otype = {fz_type:016X}")

# Every object whose body/info CONTAINS a reference to a known font oid (a parent descriptor)
print("\n--- objects referencing a font oid (potential parent/descriptor) ---")
for o in allobj:
    if o.oid in FONT_OIDS:
        continue
    blob = (o.info or b"") + (o.body or b"")
    for foid, name in FONT_OIDS.items():
        if len(blob) >= 8:
            for off in range(0, len(blob) - 8, 1):
                if struct.unpack_from("<Q", blob, off)[0] == foid:
                    print(f"  obj {o.oid:016X} otype={o.otype:016X} info={len(o.info)} body={len(o.body)} "
                          f"-> refs {name} @+{off}")
                    break
            else:
                continue
            break

# For each font, dump its OWN info block (wrapper header) as ints/floats — a size may live there
print("\n--- each font object's INFO block (header) decoded ---")
for foid, name in FONT_OIDS.items():
    o = byid.get(foid)
    if not o:
        continue
    info = o.info or b""
    print(f"\n{name} {foid:016X}: otype={o.otype:016X} info_len={len(info)} body_len={len(o.body)}")
    print("  info hex:", info.hex())
    n = len(info) // 4
    if n:
        print("  info f32:", [round(x, 2) for x in struct.unpack_from(f"<{n}f", info, 0)])
        print("  info i32:", list(struct.unpack_from(f"<{n}i", info, 0)))
