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

def hexd(bs): return " ".join("%02x"%x for x in bs)

def dump(label, body):
    print("\n=== %s len=%d ===" % (label, len(body)))
    cid=struct.unpack_from("<H",body,0)[0]
    # name: after cid, ascii until 00
    e=body.find(b"\x00",2)
    name=body[2:e].decode("latin-1")
    print("charId=%d name=%r name_end=%d" % (cid,name,e))
    p=e+1
    rest=body[p:p+60]
    print("bytes after name (off %d):"%p, hexd(rest))
    # The 02 00 60 00 ... could be flags. Try interpreting GFx DefineCompactedFont(1007) header:
    # u16 fontId, u16 flags, name?  Actually name is inline here.
    # Show the differing region between orig/heb: print bytes p..p+40
    return p

orig=tags(sys.argv[1]); heb=tags(sys.argv[2])
o={i:b for i,c,l,s,b in orig}; h={i:b for i,c,l,s,b in heb}
for idx in (6,16):
    po=dump("ORIG %d"%idx, o[idx])
    ph=dump("HEB  %d"%idx, h[idx])
    # find first differing byte
    bo,bh=o[idx],h[idx]
    n=min(len(bo),len(bh))
    fd=next((i for i in range(n) if bo[i]!=bh[i]), n)
    print("  first differing byte at offset %d" % fd)
    print("  orig[%d:%d]="%(fd-8,fd+24), hexd(bo[fd-8:fd+24]))
    print("  heb [%d:%d]="%(fd-8,fd+24), hexd(bh[fd-8:fd+24]))
