"""Test chunked LZ4 where each chunk = [varint header][LZ4 block]. Try varint as
LEB128 and as raw-1or2byte, meaning = uncompressed OR compressed chunk size, reset
& linked dict. Validate on full oasisstrings: decode to 5,061,841 with out[0]==0x00."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read(); N = len(data)

def rd_leb(sp):
    v=0; s=0
    while True:
        b=data[sp]; sp+=1; v |= (b & 0x7f) << s; s+=7
        if not (b & 0x80): break
    return v, sp

def rd_gibbed(sp):  # <0xFE: 1 byte; 0xFF: u32
    b=data[sp]
    if b < 0xFE: return b, sp+1
    if b == 0xFF:
        v = data[sp+1] | (data[sp+2]<<8) | (data[sp+3]<<16) | (data[sp+4]<<24)
        return v, sp+5
    raise ValueError("0xFE")

def lz4_out(sp, target, base, out):  # decode to `target` output bytes
    end = len(out) + target
    while len(out) < end:
        token=data[sp]; sp+=1; litlen=token>>4
        if litlen==15:
            while True:
                b=data[sp];sp+=1;litlen+=b
                if b!=255:break
        if litlen: out+=data[sp:sp+litlen]; sp+=litlen
        if len(out)>=end: break
        off=data[sp]|(data[sp+1]<<8); sp+=2
        if off==0 or off>len(out)-base: raise ValueError("badoff")
        mlen=token&0xF
        if mlen==15:
            while True:
                b=data[sp];sp+=1;mlen+=b
                if b!=255:break
        mlen+=4; st=len(out)-off
        for i in range(mlen): out.append(out[st+i])
    if len(out)!=end: raise ValueError("overshoot")
    return sp

def lz4_in(sp, comp, base, out):  # decode consuming exactly `comp` input bytes
    end=sp+comp
    while sp<end:
        token=data[sp]; sp+=1; litlen=token>>4
        if litlen==15:
            while True:
                b=data[sp];sp+=1;litlen+=b
                if b!=255:break
        if litlen: out+=data[sp:sp+litlen]; sp+=litlen
        if sp>=end: break
        off=data[sp]|(data[sp+1]<<8); sp+=2
        if off==0 or off>len(out)-base: raise ValueError("badoff")
        mlen=token&0xF
        if mlen==15:
            while True:
                b=data[sp];sp+=1;mlen+=b
                if b!=255:break
        mlen+=4; st=len(out)-off
        for i in range(mlen): out.append(out[st+i])
    if sp!=end: raise ValueError("inover")
    return sp

def run(rd, sem, reset):
    out=bytearray(); sp=0
    while len(out) < UNCOMP:
        v, sp = rd(sp)
        if v==0 or v>0x4000000: raise ValueError("badv")
        base = len(out) if reset else 0
        if sem=="unc":
            sp = lz4_out(sp, min(v, UNCOMP-len(out)), base, out)
        else:
            sp = lz4_in(sp, v, base, out)
    return out, sp

for rdname, rd in (("leb",rd_leb),("gibbed",rd_gibbed)):
    for sem in ("unc","comp"):
        for reset in (True, False):
            try:
                out, sp = run(rd, sem, reset)
            except Exception as e:
                continue
            if len(out)==UNCOMP and out[0]==0x00:
                print(f"*** SUCCESS varint={rdname} sem={sem} reset={reset} sp={sp}/{N}")
                print("head:", bytes(out[:40]).hex(' '))
                open(RAW+".decoded","wb").write(out); sys.exit(0)
print("no match; diagnostics:")
for label, base_mode in (("reset", "reset"), ("linked", "linked")):
    out=bytearray(); sp=0; chunks=[]
    try:
        while len(out)<UNCOMP and len(chunks)<12:
            v,sp=rd_leb(sp); st=len(out)
            base = len(out)-v if base_mode=="reset" else 0   # reset: window = this chunk only
            base = st if base_mode=="reset" else 0
            sp=lz4_out(sp, min(v,UNCOMP-len(out)), base, out)
            chunks.append((v, len(out)-st))
    except Exception as e:
        chunks.append(("ERR@%d"%len(out), str(e)[:30]))
    print(f"leb/unc/{label}: chunks(varint,produced)=", chunks[:12], " total_out=", len(out))
