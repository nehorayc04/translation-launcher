import os, struct, math
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
u32=lambda o: struct.unpack_from("<I",data,o)[0]
u16=lambda o: struct.unpack_from("<H",data,o)[0]
f32=lambda o: struct.unpack_from("<f",data,o)[0]

# parse the section triplet list 0x1d0..0x220 as {offset, fmt, size}
print("== section triplets (offset, fmt, size) ==")
o=0x1d0
secs=[]
while o<0x224:
    off=u32(o); fmt=u32(o+4); sz=u32(o+8)
    if 0<off<n:
        secs.append((off,fmt,sz))
        print(f"  @hdr0x{o:x}: off=0x{off:x} fmt=0x{fmt:08x} size=0x{sz:x}({sz})  low16={fmt&0xffff} hi16={fmt>>16}")
    o+=12

def show_buf(off, stride, count, label, ncols):
    print(f"\n== {label} @0x{off:x} stride={stride} first {count} elems ==")
    for k in range(count):
        base=off+k*stride
        vals=[f32(base+j*4) for j in range(ncols)]
        vs=", ".join(f"{v:9.3f}" for v in vals)
        # also as u16s
        print(f"  [{k:3d}] {vs}")

# 0x4cbd0 stride 16 (4 floats)
show_buf(0x4cbd0, 16, 20, "buf 0x4cbd0 stride16 as 4xf32", 4)
# maybe stride 8 (2D verts)
show_buf(0x4cbd0, 8, 20, "buf 0x4cbd0 stride8 as 2xf32", 2)
# 0x76750
show_buf(0x76750, 16, 12, "buf 0x76750 stride16", 4)
