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
    # The field that read 0a 01 (orig) vs 85 0d (heb) was at e+11..e+12 in raw stream.
    # locate it: search the 'ff 7f ff 7f 03 80 03 80' anchor which appears right before glyph shape data
    anchor=b"\xff\x7f\xff\x7f\x03\x80\x03\x80"
    ao=bo.find(anchor); ah=bh.find(anchor)
    print("\n=== idx %d ===" % idx)
    print("anchor(ff7f...) ORIG@%d HEB@%d" % (ao,ah))
    # bytes between name-end and anchor = header + glyph-count + glyph-offset-table start
    print("ORIG header[e..anchor]:", hexd(bo[e:ao]))
    print("HEB  header[e..anchor]:", hexd(bh[e:ah]))
    # the two u16 fields right before anchor differ: count & a 32-bit value
    # In orig after '11 00': 0a 01 00 00 30 36 00 00 then anchor
    # In heb : 85 0d 00 00 94 84 04 00 00 00 00 00 02 ... (offset table all 02 00 00 00)
    # Parse count(u16) then offset-count(u32?)
    # find position of count
    pre_o = bo[e:ao]
    pre_h = bh[e:ah]
    # count is 4 bytes before the first 00 00 then a u32
    print("ORIG: u16 count=%d , next u32=%d" % (
        struct.unpack_from("<H",pre_o,len(pre_o)-8)[0],
        struct.unpack_from("<I",pre_o,len(pre_o)-6)[0] if len(pre_o)>=6 else -1))
    # tail: codepoint map region
    print("ORIG tail 40B:", hexd(bo[-40:]))
    print("HEB  tail 40B:", hexd(bh[-40:]))
