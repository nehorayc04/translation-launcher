import struct, sys

def _read_rect(b,p):
    nbits=b[p]>>3
    return p+((5+nbits*4)+7)//8

def tags(path):
    b=open(path,"rb").read()
    p=8; p=_read_rect(b,p); p+=4
    out=[]; idx=0
    while p<len(b)-1:
        start=p
        rec=struct.unpack_from("<H",b,p)[0]; p+=2
        code=rec>>6; ln=rec&0x3F
        if ln==0x3F:
            ln=struct.unpack_from("<I",b,p)[0]; p+=4
        body=b[p:p+ln]
        out.append((idx,code,ln,start,body))
        p+=ln; idx+=1
        if code==0: break
    return out

def hexd(bs):
    return " ".join("%02x"%x for x in bs)

def dump_1005(label, body):
    print("\n=== %s  (len=%d) ===" % (label, len(body)))
    print("first 80 bytes:", hexd(body[:80]))
    # Try GFx DefineExternalImage2 layout:
    # u16 characterId, u32 ?, then export name (len-prefixed or nul-term), target W/H, format, data...
    p=0
    cid=struct.unpack_from("<H",body,p)[0]; p+=2
    print("characterId =", cid)
    # GFx 1005 has more header fields; print candidate u32/u16 reads
    for off in range(2,40,2):
        u16=struct.unpack_from("<H",body,off)[0]
        print("  @%2d u16=%d (0x%x)"%(off,u16,u16))
    # find a readable ascii run near the start (export name / filename .dds)
    import re
    runs=re.findall(rb"[\x20-\x7e]{3,}", body[:200])
    print("ascii runs in first 200B:", [r.decode() for r in runs])
    # find DDS magic
    dds=body.find(b"DDS ")
    print("DDS magic offset in body:", dds)
    if dds>=0:
        hdr=body[dds:dds+128]
        # DDS header: magic(4) size(4) flags(4) height(4) width(4) ...
        h=struct.unpack_from("<I",body,dds+12)[0]
        w=struct.unpack_from("<I",body,dds+16)[0]
        print("  DDS height=%d width=%d" % (h,w))
        pf_fourcc=body[dds+84:dds+88]
        print("  DDS pixelformat fourCC:", pf_fourcc)

orig=tags(sys.argv[1])
heb=tags(sys.argv[2])
from_orig={i:(c,l,s,b) for i,c,l,s,b in orig}
from_heb ={i:(c,l,s,b) for i,c,l,s,b in heb}
for idx in (6,16):
    co,lo,so,bo=from_orig[idx]
    ch,lh,sh,bh=from_heb[idx]
    dump_1005("ORIG idx %d"%idx, bo)
    dump_1005("HEB  idx %d"%idx, bh)
