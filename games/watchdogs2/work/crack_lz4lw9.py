"""Trace chunked decode: varint(chunk unc size) + LZ4. Inspect chunk1->chunk2 boundary
to find why chunk2 fails; try linked dict + a few varint/dict variants."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read(); N=len(data)

def rd_leb(sp):
    v=0;s=0
    while True:
        b=data[sp];sp+=1;v|=(b&0x7f)<<s;s+=7
        if not(b&0x80):break
    return v,sp

def decode_out(sp, target, base, out):
    end=len(out)+target
    while len(out)<end:
        token=data[sp];sp+=1;litlen=token>>4
        if litlen==15:
            while True:
                b=data[sp];sp+=1;litlen+=b
                if b!=255:break
        if litlen: out+=data[sp:sp+litlen];sp+=litlen
        if len(out)>=end: break
        off=data[sp]|(data[sp+1]<<8);sp+=2
        if off==0 or off>len(out)-base: raise ValueError(f"badoff off={off} winsize={len(out)-base}")
        mlen=token&0xF
        if mlen==15:
            while True:
                b=data[sp];sp+=1;mlen+=b
                if b!=255:break
        mlen+=4;st=len(out)-off
        for i in range(mlen):out.append(out[st+i])
    if len(out)!=end: raise ValueError("overshoot")
    return sp

# trace with linked dict (base=0)
print("=== trace: varint=chunk-unc, LINKED dict (base=0) ===")
out=bytearray();sp=0
for i in range(8):
    v,nsp=rd_leb(sp)
    print(f"chunk{i}: varint@{sp}={v} (bytes {data[sp:nsp].hex()})  sp->{nsp}")
    sp=nsp
    try:
        sp=decode_out(sp, min(v,UNCOMP-len(out)), 0, out)
        print(f"   decoded ok, total_out={len(out)}, next byte @{sp}={data[sp]:#x} ({data[sp:sp+6].hex(' ')})")
    except Exception as e:
        print(f"   FAIL: {e};  bytes@sp-2..sp+10: {data[sp-2:sp+12].hex(' ')}")
        break

# Maybe chunk1 unc isn't 58; maybe varint is COMPRESSED size. Re-trace decode-by-input.
print("\n=== trace: varint=chunk-COMPRESSED size, decode by input, reset dict ===")
def decode_in(sp, comp, base, out):
    end=sp+comp
    while sp<end:
        token=data[sp];sp+=1;litlen=token>>4
        if litlen==15:
            while True:
                b=data[sp];sp+=1;litlen+=b
                if b!=255:break
        if litlen: out+=data[sp:sp+litlen];sp+=litlen
        if sp>=end:break
        off=data[sp]|(data[sp+1]<<8);sp+=2
        if off==0 or off>len(out)-base: raise ValueError(f"badoff off={off}")
        mlen=token&0xF
        if mlen==15:
            while True:
                b=data[sp];sp+=1;mlen+=b
                if b!=255:break
        mlen+=4;st=len(out)-off
        for i in range(mlen):out.append(out[st+i])
    if sp!=end: raise ValueError("inover")
    return sp
out=bytearray();sp=0
for i in range(6):
    v,nsp=rd_leb(sp)
    print(f"chunk{i}: varint@{sp}={v} sp->{nsp}")
    sp=nsp
    try:
        sp=decode_in(sp, v, len(out), out)
        print(f"   ok, total_out={len(out)}, next@{sp}={data[sp:sp+6].hex(' ')}")
    except Exception as e:
        print(f"   FAIL {e}"); break
