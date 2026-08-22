# -*- coding: utf-8 -*-
"""Fast trace of +16 -> tail-kind2 via the running game's DATA memory (numpy-vectorized)."""
import sys, os, struct, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
REPO=r"c:/Users/Nehoray_Cohen/Projects/Game translator"
f=open(os.path.join(REPO,"games","ghost_of_tsushima","extract","ghost_title.xpps"),"rb").read()
TAIL_OFF=0x97c8d0; TAIL_LEN=0x9a2750-TAIL_OFF
TAIL_SIG=f[TAIL_OFF:TAIL_OFF+48]
GUID=f[0x98:0xa8]
pd=M.pid()
if not pd: print("not running"); sys.exit(2)
h=M.open_proc(pd)
regs=[r for r in M.regions(h, exec_only=False) if r[1]<=64*1024*1024]  # small regions only
print(f"{len(regs)} small committed regions")
# cache reads
cache={}
def rd(base,size):
    if base not in cache: cache[base]=M.read(h,base,size)
    return cache[base]
def find_sig(sig,cap=6):
    out=[]
    for base,size,prot in regs:
        d=rd(base,size)
        if not d: continue
        o=d.find(sig)
        while o!=-1 and len(out)<cap:
            out.append((base+o,prot)); o=d.find(sig,o+1)
    return out
tail=find_sig(TAIL_SIG)
print("tail-kind2 VA:", [f"0x{a:x}(p{p:#x})" for a,p in tail])
guid=find_sig(GUID)
print("ghost_title base+0x98 VA:", [f"0x{a:x}" for a,p in guid])
# hunt pointers into tail range (numpy), only in small regions
for tva,_ in tail[:1]:
    lo,hi=tva,tva+TAIL_LEN
    print(f"\npointers into tail @0x{tva:x} (len 0x{TAIL_LEN:x}):")
    for base,size,prot in regs:
        d=rd(base,size)
        if not d or len(d)<8: continue
        n=len(d)//8
        arr=np.frombuffer(d[:n*8],dtype='<u8')
        m=(arr>=lo)&(arr<hi)
        idx=np.nonzero(m)[0]
        if len(idx)>=6:
            offs=[int(arr[i])-tva for i in idx[:16]]
            # are they evenly spaced (a table)? check idx deltas
            dd=np.diff(idx[:20])
            print(f"  region 0x{base:x}(p{prot:#x}): {len(idx)} ptrs, idx-stride~{np.bincount(dd).argmax() if len(dd) else 0}, tail-offsets:{offs}")
M.k32.CloseHandle(h)
