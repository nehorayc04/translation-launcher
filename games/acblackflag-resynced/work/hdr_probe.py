import os, struct, glob
d = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
for p in sorted(glob.glob(os.path.join(d,"*.bin"))):
    n = os.path.basename(p); sz = os.path.getsize(p)
    with open(p,'rb') as f: h = f.read(0x80)
    ver   = struct.unpack_from('<H', h, 0x00)[0]
    uid   = struct.unpack_from('<Q', h, 0x02)[0]
    sz0A  = struct.unpack_from('<I', h, 0x0A)[0]
    mid   = h[0x0E:0x14].hex()
    cls   = struct.unpack_from('<I', h, 0x14)[0]
    sz18  = struct.unpack_from('<I', h, 0x18)[0]
    v1C   = struct.unpack_from('<I', h, 0x1C)[0]
    print(f"{n:24s} size={sz:>9} ver={ver} uid=0x{uid:016X} sz@0A={sz0A} (file-sz0A={sz-sz0A}) mid={mid} cls=0x{cls:08X} sz@18={sz18} (d={sz0A-sz18}) v@1C={v1C}")
    print(f"   0x20..0x51: {h[0x20:0x51].hex()}")
    print(f"   0x51..0x80: {h[0x51:0x80].hex()}")
