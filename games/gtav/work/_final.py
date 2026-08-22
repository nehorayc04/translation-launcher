import struct, sys

def _read_rect(b,p):
    nbits=b[p]>>3
    return p+((5+nbits*4)+7)//8
def tags(path):
    b=open(path,"rb").read()
    p=8; p=_read_rect(b,p); p+=4
    out=[]; idx=0
    while p<len(b)-1:
        rec=struct.unpack_from("<H",b,p)[0]; p+=2
        code=rec>>6; ln=rec&0x3F
        if ln==0x3F: ln=struct.unpack_from("<I",b,p)[0]; p+=4
        out.append((idx,code,ln,b[p:p+ln])); p+=ln; idx+=1
        if code==0: break
    return out
def hexd(bs): return " ".join("%02x"%x for x in bs)

orig=tags(sys.argv[1]); heb=tags(sys.argv[2])
o={i:b for i,c,l,b in orig}; h={i:b for i,c,l,b in heb}

b=h[6]; bo=o[6]
e=b.find(b"\x00",2)
ch=struct.unpack_from("<H",b,e+11)[0]
co=struct.unpack_from("<H",bo,e+11)[0]
# map region: count records at tail
mapstart=len(b)-ch*8
# Dump ALL codepoints in HEB map, sorted, count latin vs hebrew vs other
cps=[]
for r in range(mapstart, len(b), 8):
    if r+8>len(b): break
    cp,adv,off=struct.unpack_from("<HHI",b,r)
    cps.append((cp,adv,off))
print("HEB map records:",len(cps))
hebrew=[c for c in cps if 0x05D0<=c[0]<=0x05EA or 0x05BE<=c[0]<=0x05F4]
latin=[c for c in cps if c[0]<0x250]
print("  Hebrew-block cps in map:",len([c for c in cps if 0x0590<=c[0]<=0x05FF]))
print("  ASCII/Latin-1 cps:",len(latin))
print("  total unique cps:",len(set(c[0] for c in cps)))
print("  cp range: min=0x%x max=0x%x"%(min(c[0] for c in cps),max(c[0] for c in cps)))
# Is original map the SAME first 266 then appended? compare ORIG map
bomapstart=len(bo)-co*8
ocps=[]
for r in range(bomapstart,len(bo),8):
    if r+8>len(bo): break
    cp,adv,off=struct.unpack_from("<HHI",bo,r)
    ocps.append((cp,adv,off))
oset=set(c[0] for c in ocps); hset=set(c[0] for c in cps)
print("\nORIG map cps:",len(ocps)," ORIG has Hebrew:",len([c for c in ocps if 0x0590<=c[0]<=0x05FF]))
print("cps in HEB not in ORIG:",len(hset-oset)," (e.g.",sorted(['U+%04X'%x for x in (hset-oset)])[:15],")")
print("cps in ORIG not in HEB:",len(oset-hset))
# glyph-data region: e+19 (after count u16, 00 00, u32 size) to mapstart
# header bytes: e(00) e+1..2(0060) e+3..5(01df00) e+6..7(3200) e+8..10(1100)+? 
# Actually count is at e+11. So glyph shapes start at e+19 (e+11 +2 count +2 zero +4 u32)
gsize_o=struct.unpack_from("<I",bo,e+15)[0] if False else None
print("\nu32@e+15 ORIG=%d HEB=%d"%(struct.unpack_from("<I",bo,e+15)[0],struct.unpack_from("<I",b,e+15)[0]))
print("glyph-shape region HEB: from ~%d to mapstart=%d  => %d bytes"%(e+19, mapstart, mapstart-(e+19)))
print("u32 (296084) == glyph region size? region=%d"%(mapstart-(e+19)))
