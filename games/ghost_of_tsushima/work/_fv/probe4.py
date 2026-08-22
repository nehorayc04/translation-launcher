import os, struct
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
u32=lambda o: struct.unpack_from("<I",data,o)[0]
u16=lambda o: struct.unpack_from("<H",data,o)[0]
f32=lambda o: struct.unpack_from("<f",data,o)[0]

# dump the "clean coord" records right after the first table sentinel, fully
print("== records 0x43c3e.. (post first-sentinel), decode +22 as floats ==")
GREC=64
for k in range(8):
    p=0x43c3e+k*GREC
    cp=u16(p); m=f32(p+4)
    f0,f1,f2,f3,f4,f5=[round(f32(p+22+j*4),2) for j in range(6)]
    v12=u32(p+12); v16=u32(p+16)
    print(f"  @0x{p:x} cp=0x{cp:04x} m={m:7.2f} +12=0x{v12:08x} +16=0x{v16:08x}  f@22=[{f0},{f1},{f2},{f3},{f4},{f5}]")

# Header sub-offsets 0x73440/0x739b0/0x76690: dump each
print("\n== header-referenced offsets ==")
for off in (0x73440,0x739b0,0x76690):
    print(f"  @0x{off:x}: {data[off:off+48].hex()}")
    fs=[round(f32(off+j*4),3) for j in range(8)]
    print(f"       floats: {fs}")

# after-glyphs region: interpret as f32 pairs (2D verts). Show a window.
print("\n== after-glyphs @0x44400 as f32 (first 24 values) ==")
for k in range(0,24,4):
    vs=[round(f32(0x44400+(k+j)*4),3) for j in range(4)]
    print(f"  +{(k)*4}: {vs}")

# Scan after-glyphs for runs of 'coordinate-like' float pairs: pairs where both in [-2000,2000], not both 0.
print("\n== scan after-glyphs for dense coord-pair runs ==")
import math
region=(0x44400, 0x8f570)
o=region[0]; run_start=None; runs=[]
while o+8<=region[1]:
    x=f32(o); y=f32(o+4)
    ok = math.isfinite(x) and math.isfinite(y) and abs(x)<3000 and abs(y)<3000 and not (x==0 and y==0)
    if ok:
        if run_start is None: run_start=o
    else:
        if run_start is not None and o-run_start>=64:
            runs.append((run_start,o))
        run_start=None
    o+=8
if run_start is not None: runs.append((run_start,o))
print(f"  {len(runs)} coord-pair runs >=64B")
for s,e in sorted(runs,key=lambda r:-(r[1]-r[0]))[:12]:
    print(f"   0x{s:x}..0x{e:x} ({e-s}B, {(e-s)//8} pairs)")
