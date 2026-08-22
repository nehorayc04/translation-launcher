import os, struct, math
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
u32=lambda o: struct.unpack_from("<I",data,o)[0]
f32=lambda o: struct.unpack_from("<f",data,o)[0]

def ent(b):
    from collections import Counter
    if not b: return 0
    c=Counter(b); import math
    return -sum((v/len(b))*math.log2(v/len(b)) for v in c.values())

def charac(off,size,label):
    b=data[off:off+size]
    # fraction of bytes that are 0
    z=b.count(0)/len(b)
    # float plausibility: read as f32 array, count values in [-2000,2000] and finite
    good=0; tot=0
    for o in range(0,len(b)-4,4):
        v=struct.unpack_from("<f",b,o)[0]
        tot+=1
        if math.isfinite(v) and abs(v)<4000 and (v==0 or abs(v)>1e-6): good+=1
    print(f"{label:22s} 0x{off:x}..0x{off+size:x} sz={size:>7} ent={ent(b):.2f} zero={z:.2f} floatish={good/max(tot,1):.2f}")

print(f"file 0x{n:x}")
for lbl,a,z in [("header",0,0x22c),
                ("before-glyphs",0x230,0x41abe-0x230),
                ("glyph-records",0x41abe,0x44400-0x41abe),
                ("after-glyphs",0x44400,0x8f570-0x44400),
                ("tail",0x8f570,n-0x8f570)]:
    charac(a,z,lbl)

print("\n== dump @0x22c (556) 128B ==")
for i in range(0,128,32):
    print(f"  0x{0x22c+i:x}: {data[0x22c+i:0x22c+i+32].hex()}")

print("\n== dump @0x230 start of 'before-glyphs' 128B ==")
for i in range(0,128,32):
    print(f"  0x{0x230+i:x}: {data[0x230+i:0x230+i+32].hex()}")

# The 'before-glyphs' region 0x230..0x41abe is 270KB. Sample floats mid-way.
print("\n== sample floats in before-glyphs region ==")
for base in (0x1000, 0x8000, 0x20000, 0x40000):
    vs=[round(f32(base+k*4),3) for k in range(8)]
    print(f"  0x{base:x}: {vs}")

print("\n== tail @0x8f570 ==")
for i in range(0, min(n-0x8f570,256), 32):
    print(f"  0x{0x8f570+i:x}: {data[0x8f570+i:0x8f570+i+32].hex()}")
