"""LZ4LW = LZ4 with LARGE-WINDOW offsets: top bit of the 16-bit offset is a flag;
when set, an extra byte extends the offset (>32KB window). Test variants, validate
by full decode to UNCOMP with decompressed[0]==0x00. byte0=0x3a prefix (start at 1)."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read(); N = len(data)

def decode(start, variant, linked=True):
    out = bytearray(); sp = start
    while len(out) < UNCOMP:
        if sp >= N: raise ValueError("eof tok")
        token = data[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                b = data[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            out += data[sp:sp+litlen]; sp += litlen
        if len(out) >= UNCOMP: break
        # ---- offset with large-window flag ----
        b0 = data[sp]; b1 = data[sp+1]; sp += 2
        raw = b0 | (b1 << 8)
        if variant == 0:      # top bit of b1 = flag, +1 byte << 15
            if raw & 0x8000:
                b2 = data[sp]; sp += 1
                off = (raw & 0x7fff) | (b2 << 15)
            else:
                off = raw
        elif variant == 1:    # top bit flag, extra byte is HIGH part: off=(raw&0x7fff)+(b2<<15)
            if raw & 0x8000:
                b2 = data[sp]; sp += 1
                off = (raw & 0x7fff) + (b2 << 15)
            else:
                off = raw
        elif variant == 2:    # flag adds, off = (raw&0x7fff); if flag, off += (b2+1)<<15
            if raw & 0x8000:
                b2 = data[sp]; sp += 1
                off = (raw & 0x7fff) + ((b2) << 15) + 0x8000
            else:
                off = raw
        elif variant == 3:    # whole 16 bits value, but if > window use low15 + extra
            if raw & 0x8000:
                b2 = data[sp]; sp += 1
                off = ((raw & 0x7fff) << 8) | b2   # 23-bit big-ish
            else:
                off = raw
        cur = len(out) if linked else None
        if off == 0 or off > len(out): raise ValueError(f"badoff {off}>{len(out)}")
        mlen = token & 0xF
        if mlen == 15:
            while True:
                b = data[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        st = len(out) - off
        for i in range(mlen): out.append(out[st+i])
    return out, sp

for start in (1, 0):
    for variant in (0,1,2,3):
        try:
            out, sp = decode(start, variant)
        except Exception as e:
            # report how far this variant got (debug)
            continue
        if len(out) == UNCOMP and out[0] == 0x00:
            print(f"*** SUCCESS start={start} variant={variant} sp={sp}/{N}")
            print("head:", bytes(out[:40]).hex(" "))
            open(RAW + ".decoded","wb").write(out)
            sys.exit(0)
# if none fully succeeded, report progress for the best (start=1,var0)
print("no full match; measuring how far each variant reaches from start=1:")
for variant in (0,1,2,3):
    out = bytearray(); sp = 1
    try:
        o,_ = decode(1, variant)
    except Exception as e:
        # re-run measuring length
        out = bytearray(); sp=1
        try:
            while len(out) < UNCOMP:
                token=data[sp]; sp+=1; litlen=token>>4
                if litlen==15:
                    while True:
                        b=data[sp];sp+=1;litlen+=b
                        if b!=255:break
                if litlen: out+=data[sp:sp+litlen]; sp+=litlen
                if len(out)>=UNCOMP: break
                b0=data[sp];b1=data[sp+1];sp+=2; raw=b0|(b1<<8)
                if variant==0:
                    off=(raw&0x7fff)|(data[sp]<<15) if raw&0x8000 else raw
                    if raw&0x8000: sp+=1
                elif variant==1:
                    if raw&0x8000: off=(raw&0x7fff)+(data[sp]<<15); sp+=1
                    else: off=raw
                elif variant==2:
                    if raw&0x8000: off=(raw&0x7fff)+(data[sp]<<15)+0x8000; sp+=1
                    else: off=raw
                else:
                    if raw&0x8000: off=((raw&0x7fff)<<8)|data[sp]; sp+=1
                    else: off=raw
                if off==0 or off>len(out): break
                mlen=token&0xF
                if mlen==15:
                    while True:
                        b=data[sp];sp+=1;mlen+=b
                        if b!=255:break
                mlen+=4; stt=len(out)-off
                for i in range(mlen): out.append(out[stt+i])
        except Exception: pass
        print(f"  variant {variant}: reached {len(out)} bytes")
