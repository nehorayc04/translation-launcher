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
        if ln==0x3F:
            ln=struct.unpack_from("<I",b,p)[0]; p+=4
        body=b[p:p+ln]
        out.append((idx,code,ln,body)); p+=ln; idx+=1
        if code==0: break
    return out

def hexd(bs): return " ".join("%02x"%x for x in bs)

def analyze(label, body):
    print("\n=== %s len=%d ===" % (label, len(body)))
    cid=struct.unpack_from("<H",body,0)[0]
    e=body.find(b"\x00",2)
    name=body[2:e].decode("latin-1")
    p=e  # the byte at e is 00 (name term)
    # walk the header fields seen: 00 60 00 | 01 df 00 | 32 00 | 11 00 | <glyphcount u16> | <offset...>
    print("charId=%d name=%r" % (cid,name))
    print("header region:", hexd(body[e:e+12]))
    # field at e+8 is the glyph count (where 0a01 vs 850d sat)
    # e+0=00, e+1..2=6000, e+3..5=01 df 00, e+6..7=3200? Let's index from e
    f=e
    print("  [e+0]=%02x [e+1:3]=%s [e+3:6]=%s [e+6:8]=%s [e+8:10]=%s(=%d) [e+10:14]=%s"%(
        body[f], hexd(body[f+1:f+3]), hexd(body[f+3:f+6]), hexd(body[f+6:f+8]),
        hexd(body[f+8:f+10]), struct.unpack_from("<H",body,f+8)[0], hexd(body[f+10:f+14])))
    gc=struct.unpack_from("<H",body,f+8)[0]
    return cid,name,e,gc

orig=tags(sys.argv[1]); heb=tags(sys.argv[2])
o={i:b for i,c,l,b in orig}; h={i:b for i,c,l,b in heb}
for idx in (6,16):
    co=analyze("ORIG %d"%idx,o[idx])
    ch=analyze("HEB  %d"%idx,h[idx])
    print("  >> glyph count ORIG=%d HEB=%d  (delta=%d)"%(co[3],ch[3],ch[3]-co[3]))
# Search for Hebrew codepoints U+05D0..05EA in HEB font tags (as UTF-16LE and raw u16)
print("\n--- Hebrew codepoint search in HEB idx 6 ---")
b=h[6]
import re
heb_cps=[]
for cp in range(0x05D0,0x05EB):
    le=struct.pack("<H",cp)
    pos=b.find(le)
    heb_cps.append((hex(cp), pos))
print(heb_cps)
