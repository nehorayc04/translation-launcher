import os, struct, math
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
f32=lambda o: struct.unpack_from("<f",data,o)[0]
u32=lambda o: struct.unpack_from("<I",data,o)[0]
u16=lambda o: struct.unpack_from("<H",data,o)[0]

def dump_pairs(off, npairs, label):
    print(f"\n== {label} @0x{off:x} ({npairs} f32-pairs) ==")
    xs=[];ys=[]
    for k in range(npairs):
        x=f32(off+k*8); y=f32(off+k*8+4)
        xs.append(x); ys.append(y)
    fin=[(x,y) for x,y in zip(xs,ys) if math.isfinite(x) and math.isfinite(y)]
    if fin:
        X=[p[0] for p in fin]; Y=[p[1] for p in fin]
        print(f"   x range [{min(X):.2f},{max(X):.2f}]  y range [{min(Y):.2f},{max(Y):.2f}]")
    for k in range(min(npairs,16)):
        print(f"   [{k}] ({xs[k]:.3f}, {ys[k]:.3f})")

dump_pairs(0x4bdb8, 24, "run A (269 pairs total)")
dump_pairs(0x77300, 16, "run near-hdr 0x77300")
dump_pairs(0x76e98, 16, "run near-hdr 0x76e98")
dump_pairs(0x78220, 16, "run 0x78220")

# What is at 0x44400..0x4bdb8 (between table-end area and first big coord run)?
print("\n== bytes 0x44400..0x44500 (start of after-glyphs) ==")
for i in range(0,128,32):
    print(f"  0x{0x44400+i:x}: {data[0x44400+i:0x44400+i+32].hex()}")

# The post-table 'coord records' continue how far? Scan 64-byte records from 0x43c3e
print("\n== post-table 64B records: cp / +16 / first coord, until structure breaks ==")
GREC=64; p=0x43c3e; cnt=0
while p+GREC<=len(data) and cnt<40:
    if u32(p+8)!=4 or u16(p+62)!=0xffff:
        print(f"  break @0x{p:x} (+8=0x{u32(p+8):x} +62=0x{u16(p+62):x})"); break
    cp=u16(p); v16=u32(p+16); x=f32(p+22); y=f32(p+26)
    print(f"  @0x{p:x} cp=0x{cp:04x} +16=0x{v16:08x} coord=({x:.1f},{y:.1f})")
    p+=GREC; cnt+=1
