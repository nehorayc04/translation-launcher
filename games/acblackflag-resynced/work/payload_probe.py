import os, math, collections
p = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas\70970_88c902b3.bin"
d = open(p,'rb').read()
gfof = d.find(b'GFOF')
print("GFOF at", hex(gfof), "file size", len(d))
body = d[gfof:]
def ent(b):
    c = collections.Counter(b); n=len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())
step = len(body)//12
print("entropy by 1/12 slices:", [round(ent(body[i*step:(i+1)*step]),2) for i in range(12)])
# longest zero runs
mx=0; cur=0; pos=0
for i,ch in enumerate(body):
    if ch==0: cur+=1
    else:
        if cur>mx: mx=cur; pos=i-cur
        cur=0
print("longest zero run in body:", mx, "at", hex(gfof+pos))
# how much of the body is zero
print("zero fraction:", round(body.count(0)/len(body),4))
# structured region: dump 0x114..0x300
for off in range(gfof, gfof+0x100, 16):
    ch=d[off:off+16]
    print(f"{off:06x}  {ch.hex(' ')}  {''.join(chr(c) if 32<=c<127 else '.' for c in ch)}")
