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
        out.append((idx,code,ln,code,b[p:p+ln])); p+=ln; idx+=1
        if code==0: break
    return out

heb=tags(sys.argv[1])
# Real tag CODE of idx 6/16 (the analyzer mislabeled as 1005 — verify true code)
for idx,c,l,code,body in heb:
    if idx in (6,16):
        print("idx %d: REAL tag code=%d  len=%d  name=%r"%(idx,code,l, body[2:body.find(b'\x00',2)].decode('latin-1')))
# Any DDS / bitmap atlas anywhere in file?
full=open(sys.argv[1],"rb").read()
print("\nDDS magic 'DDS ' anywhere:", full.find(b"DDS "))
print("PNG magic anywhere:", full.find(b"\x89PNG"))
print("DXT1/5 fourcc:", full.find(b"DXT"))
# glyph shape data: GFx compacted-font glyphs are vector EM outlines (edge records).
# The 'ff 7f ff 7f 03 80 03 80' anchor = bounding/coord data of first glyph.
b=heb[6][4]
print("\nfirst glyph shape bytes (after header, off 53):", " ".join("%02x"%x for x in b[53:53+40]))
# the cp-map glyph_offset for א=0x188d3 -> dump its glyph
cp,adv,off=struct.unpack_from("<HHI",b,len(b)-3461*8)  # first map record
print("first map cp=U+%04X adv=%d off=0x%x"%(cp,adv,off))
