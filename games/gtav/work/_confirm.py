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

for idx in (6,16):
    bo,bh=o[idx],h[idx]
    e=bo.find(b"\x00",2)
    # count field: at e+11 (u16). data-region-size u32 at e+13? Let's read both.
    # ORIG header[e..]: 00 00 60 00 01 df 00 32 00 11 00 |0a 01| 00 00 |30 36 00 00| ff7f...
    # so layout: e..e+10 = 11 header bytes, count u16 @ e+11, then u32 @ e+15? 
    # Actually: e+11='0a',e+12='01' => count=266; e+13,e+14='00 00'; e+15..e+18='30 36 00 00'
    co=struct.unpack_from("<H",bo,e+11)[0]
    ch=struct.unpack_from("<H",bh,e+11)[0]
    u32o=struct.unpack_from("<I",bo,e+15)[0]
    u32h=struct.unpack_from("<I",bh,e+15)[0]
    print("\n=== idx %d ===" % idx)
    print("name_end e=%d  glyphCount ORIG=%d HEB=%d   u32@e+15 ORIG=%d HEB=%d (=glyph table bytes?)"%(
        e,co,ch,u32o,u32h))
    # heb count 3461, orig 266 => added 3195 glyph slots. The Hebrew alphabet=27, but 3195?
    # Check: maybe count is total incl. all latin reused. Let's see map region size.
    # The 8-byte cp-map: count * 8 bytes near tail
    print("HEB count*8 = %d ; tail map starts ~ %d" % (ch*8, len(bh)-ch*8))
# verify map record for א glyph offset points into glyph-data region
b=h[6]
e=b.find(b"\x00",2)
# read record for U+05D0
pos=307377  # from prev (the d0 05 90 00 ...)
cp,adv,off=struct.unpack_from("<HHI",b,pos)
print("\nU+%04X advance=%d glyph_offset=0x%x (%d)  -> bytes there: %s"%(cp,adv,off,off,hexd(b[off:off+24])))
# also an ascii latin 'A' for comparison
posA=b.find(struct.pack("<H",0x0041))  # may be many; find within map region
# search map region (last ~ ch*8 bytes)
ch=struct.unpack_from("<H",b,e+11)[0]
mapstart=len(b)-ch*8
# scan records for cp==0x41
for r in range(mapstart, len(b)-8, 8):
    c=struct.unpack_from("<H",b,r)[0]
    if c==0x0041:
        cp,adv,off=struct.unpack_from("<HHI",b,r)
        print("U+0041 (A) advance=%d glyph_offset=0x%x"%(adv,off))
        break
print("map region: start=%d end=%d  count=%d records of 8B"%(mapstart,len(b),ch))
