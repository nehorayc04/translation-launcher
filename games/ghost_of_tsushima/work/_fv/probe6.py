import os, struct, math
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
f32=lambda o: struct.unpack_from("<f",data,o)[0]

def is_coord(v):
    # a real glyph coordinate: finite, magnitude between ~0.01 and 4000, NOT denormal/huge
    if not math.isfinite(v): return False
    a=abs(v)
    return a==0.0 or (1e-2 <= a <= 4000.0)

# map maximal runs of consecutive f32 (4-byte stride) that are coordinate-like,
# with at least some nonzero variety
best=[]
o=0x100
run=None
while o+4<=n:
    v=f32(o)
    if is_coord(v):
        if run is None: run=[o,o,0,0]
        run[1]=o+4
        if v!=0.0: run[2]+=1  # nonzero count
    else:
        if run and (run[1]-run[0])>=48 and run[2]>=6:
            best.append(tuple(run))
        run=None
    o+=4
if run and (run[1]-run[0])>=48 and run[2]>=6: best.append(tuple(run))

print(f"{len(best)} coordinate-like float runs (>=12 f32, >=6 nonzero)")
for s,e,nz,_ in sorted(best,key=lambda r:-(r[1]-r[0]))[:25]:
    vals=[f32(s+k*4) for k in range((e-s)//4)]
    nzv=[v for v in vals if v!=0]
    print(f"  0x{s:x}..0x{e:x} {(e-s)}B nz={nz} range[{min(nzv):.1f},{max(nzv):.1f}]")
print(f"\ntotal coord-run bytes: {sum(e-s for s,e,_,_ in best):,}")

# Focus: dump 0x76e98 area as pairs with more context, look for contour structure
print("\n== 0x76d00..0x77000 as f32 pairs ==")
for o in range(0x76d80, 0x77000, 8):
    x=f32(o); y=f32(o+4)
    if math.isfinite(x) and math.isfinite(y):
        print(f"  0x{o:x}: ({x:9.3f}, {y:9.3f})")
