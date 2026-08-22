import os, struct, math
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
u32=lambda o: struct.unpack_from("<I",data,o)[0]
u64=lambda o: struct.unpack_from("<Q",data,o)[0]
f32=lambda o: struct.unpack_from("<f",data,o)[0]

# Full dump of header sub-resource area 0x1d0..0x300
print("== header area 0x1d0..0x300 as u32 (mark in-range offsets & hashes) ==")
for o in range(0x1d0,0x300,4):
    v=u32(o)
    tag=""
    if 0x300<v<n: tag=" <-off?"
    print(f"  0x{o:x}: 0x{v:08x} ({v}){tag}")
