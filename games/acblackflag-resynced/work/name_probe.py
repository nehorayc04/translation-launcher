import os, struct, glob, string
d = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
for p in sorted(glob.glob(os.path.join(d,"*.bin"))):
    n = os.path.basename(p)
    with open(p,'rb') as f: h = f.read(0x200)
    nl = struct.unpack_from('<I', h, 0x1C)[0]
    blob = h[0x20:0x20+nl]
    term = h[0x20+nl]
    uid_after = struct.unpack_from('<Q', h, 0x20+nl+1)[0]
    cls_after = struct.unpack_from('<I', h, 0x20+nl+9)[0]
    tail = h[0x20+nl+13:0x20+nl+13+64]
    print(f"{n}  nameLen={nl} term=0x{term:02x} uidAfter=0x{uid_after:016X} clsAfter=0x{cls_after:08X}")
    print(f"   blob : {blob.hex()}")
    print(f"   ascii: {''.join(chr(c) if 32<=c<127 else '.' for c in blob)}")
    print(f"   tail : {tail.hex()}")
    print(f"   tailA: {''.join(chr(c) if 32<=c<127 else '.' for c in tail)}")
