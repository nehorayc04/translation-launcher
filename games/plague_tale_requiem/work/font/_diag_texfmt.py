# -*- coding: utf-8 -*-
import sys, struct
sys.path.insert(0, ".")
from dpc_repack import DpcRepack

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
TEX1 = 0xEFC73FAE0445DAB6
D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
t = byid[TEX1]
print("=== TEX1 object ===")
print("otype = %016X" % t.otype)
print("is_comp =", t.is_comp, " algo =", t.algo, " unk16 =", t.unk16)
print("info len =", len(t.info))
print("body len =", len(t.body))
print("info hex:", t.info.hex())
print("body[:64] hex:", t.body[:64].hex())
# interpret info as possible header
if len(t.info) >= 4:
    print("\n-- info as int32 LE --")
    n = len(t.info)//4
    ints = struct.unpack_from("<%di" % n, t.info, 0)
    print(ints)
    print("-- info as uint16 LE --")
    n2 = len(t.info)//2
    u16 = struct.unpack_from("<%dH" % n2, t.info, 0)
    print(u16)
# body header 4 bytes
print("\nbody[:4] as u16:", struct.unpack_from("<2H", t.body, 0))
print("body[:4] as i32:", struct.unpack_from("<i", t.body, 0))
