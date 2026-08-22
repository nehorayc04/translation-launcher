import struct, sys, os

TAGS = {0:"End",6:"DefineBits",10:"DefineFont",11:"DefineText",13:"DefineFontInfo",
22:"DefineShape2",32:"DefineShape3",33:"DefineText2",37:"DefineEditText",39:"DefineSprite",
48:"DefineFont2",56:"ExportAssets",57:"ImportAssets",62:"DefineFontInfo2",69:"FileAttributes",
71:"ImportAssets2",73:"DefineFontAlignZones",74:"DefineFontInfo?",75:"DefineFont3",77:"Metadata",
83:"DefineShape4",88:"DefineFontName",91:"DefineFont4",
1000:"ExporterInfo",1001:"DefineExternalGradient",1002:"DefineSubImage",1003:"DefineExternalImage",
1004:"FontTextureInfo",1005:"DefineExternalImage2",1006:"DefineGradientMap",1007:"DefineCompactedFont",
1008:"DefineExternalSound",1009:"DefineExternalStreamSound",1010:"DefineSubImageInfo",
1011:"FontTextureInfo2",1012:"Unknown1012",2:"DefineShape",1:"DefineShape?",9:"SetBackgroundColor?"}

def _read_rect(b,p):
    nbits=b[p]>>3
    total=5+nbits*4
    return p+(total+7)//8

def parse(path):
    b=open(path,"rb").read()
    p=8
    p=_read_rect(b,p); p+=4
    out=[]
    idx=0
    while p<len(b)-1:
        start=p
        rec=struct.unpack_from("<H",b,p)[0]; p+=2
        code=rec>>6; ln=rec&0x3F
        hdr=2
        if ln==0x3F:
            ln=struct.unpack_from("<I",b,p)[0]; p+=4; hdr=6
        body=b[p:p+ln]
        out.append((idx,code,TAGS.get(code,"Tag%d"%code),ln,start,body))
        p+=ln; idx+=1
        if code==0: break
    return out

a=parse(sys.argv[1])
h=parse(sys.argv[2])
print("orig tags=%d  heb tags=%d"%(len(a),len(h)))
print("%-4s %-6s %-26s %12s %12s %12s"%("idx","code","name","orig_len","heb_len","delta"))
total_delta=0
for (ia,ca,na,la,sa,ba),(ih,ch,nh,lh,sh,bh) in zip(a,h):
    if ca!=ch:
        print("!! tag stream diverged at idx %d (codes %d vs %d)"%(ia,ca,ch)); break
    d=lh-la
    if d!=0:
        total_delta+=d
        print("%-4d %-6d %-26s %12d %12d %12d"%(ia,ca,na,la,lh,d))
print("--- total grown bytes:",total_delta)
