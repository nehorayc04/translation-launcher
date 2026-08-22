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

heb=tags(sys.argv[1])
h={i:b for i,c,l,b in heb}
b=h[6]
# Hebrew cps clustered ~307385-307585. Dump that region as 16/12/8-byte records
print("region around first Hebrew cp (307360..307620):")
reg=b[307360:307620]
# Try to find record stride: Hebrew cps appear at 307385,307409,307425... diffs?
positions=[]
for cp in range(0x05D0,0x05EB):
    le=struct.pack("<H",cp)
    pos=b.rfind(le)  # the map likely uses the LAST occurrence (sorted map)
    positions.append((cp,pos))
positions=[(cp,p) for cp,p in positions if 307000<p<308000]
positions.sort(key=lambda x:x[1])
print("Hebrew cps in map region (sorted by pos):")
prev=None
for cp,pos in positions:
    stride = pos-prev if prev else 0
    print("  U+%04X @ %d  stride=%d  rec=%s" % (cp,pos,stride, hexd(b[pos:pos+16])))
    prev=pos
# Establish map record size from stride
