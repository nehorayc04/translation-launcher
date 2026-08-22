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

heb=tags(sys.argv[1])
h={i:b for i,c,l,b in heb}
b=h[6]
e=b.find(b"\x00",2)
print("FULL HEADER LAYOUT for tag idx6 ($Font2 'ChaletComprime...'):")
print("  [0:2]   charId u16 =", struct.unpack_from("<H",b,0)[0])
print("  [2:%d]  name asciiz = %r"%(e, b[2:e].decode('latin-1')))
print("  [%d]    name-term 00"%e)
print("  [%d:%d] flags/metrics = %s"%(e+1,e+11," ".join("%02x"%x for x in b[e+1:e+11])))
gc=struct.unpack_from("<H",b,e+11)[0]
print("  [%d:%d] glyphCount u16 = %d"%(e+11,e+13,gc))
print("  [%d:%d] reserved 00 00"%(e+13,e+15))
gsz=struct.unpack_from("<I",b,e+15)[0]
print("  [%d:%d] glyphDataSize u32 = %d"%(e+15,e+19,gsz))
print("  [%d:...] glyph shape/coord region (%d bytes of vector edge data)"%(e+19,gsz))
mapstart=len(b)-gc*8
print("  [%d:%d] codepoint map = %d x 8-byte records {cp u16, advance u16, glyphOffset u32}"%(mapstart,len(b),gc))
print("  glyph region [%d:%d]=%d  == glyphDataSize(%d)? %s"%(e+19,mapstart,mapstart-(e+19),gsz, mapstart-(e+19)==gsz))
# dump א glyph vector data
for r in range(mapstart,len(b),8):
    cp,adv,off=struct.unpack_from("<HHI",b,r)
    if cp==0x05D0:
        print("\nU+05D0 (א): advance=%d glyphOffset=0x%x"%(adv,off))
        print("  vector data @off:", " ".join("%02x"%x for x in b[off:off+32]))
        break
