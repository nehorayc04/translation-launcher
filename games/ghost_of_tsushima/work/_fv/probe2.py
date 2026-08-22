import os, struct
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
u32=lambda o: struct.unpack_from("<I",data,o)[0]
u16=lambda o: struct.unpack_from("<H",data,o)[0]
f32=lambda o: struct.unpack_from("<f",data,o)[0]

print("== KCAP header dump (first 0x60 as u32) ==")
for o in range(0, 0x60, 4):
    v=u32(o)
    flag=""
    if 0 < v <= n: flag=" <-in-range-offset"
    print(f"  +{o:3d} 0x{o:02x}: 0x{v:08x} ({v})"+flag)

# Map every maximal run of "rich-like" 64-byte records across the whole file.
# rich rec signature used by got_fonk: +8 u32==4, +62 u16==0xffff, +2 u16==0 (cp hi)
GREC=64
def is_rec(p):
    if p+GREC>n: return False
    if u32(p+8)!=4: return False
    if u16(p+62)!=0xffff: return False
    return True
runs=[]
i=0
# find candidate starts by the '04 00 00 00' at +8
pos=data.find(b"\x04\x00\x00\x00")
cand=set()
while pos!=-1:
    p=pos-8
    if p>=0 and is_rec(p): cand.add(p)
    pos=data.find(b"\x04\x00\x00\x00",pos+1)
cand=sorted(cand)
# group consecutive (stride 64) runs
runs=[]
i=0
while i<len(cand):
    start=cand[i]; j=i
    while j+1<len(cand) and cand[j+1]==cand[j]+GREC:
        j+=1
    end=cand[j]+GREC
    runs.append((start,end,(end-start)//GREC))
    i=j+1
print(f"\n== {len(runs)} rich-record runs (>=3 recs) ==")
for s,e,c in runs:
    if c<3: continue
    cps=[u16(s+k*GREC) for k in range(c)]
    lo=min(cps); hi=max(cps)
    # count 0xffff
    nff=sum(1 for x in cps if x==0xffff)
    print(f"  0x{s:x}..0x{e:x}  {c} recs  cp[0x{lo:x}..0x{hi:x}]  ffff={nff}")
