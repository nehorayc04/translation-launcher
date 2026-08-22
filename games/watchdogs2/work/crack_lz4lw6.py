"""LZ4LW = chunked-by-size? Each block: [H-byte header = size][LZ4 data].
Try header=compressed-size (decode block by consuming exactly that many input bytes)
and header=uncompressed-size (decode block to that many output bytes). reset dict.
Validate: full tile to UNCOMP and decompressed[0]==0x00."""
import sys, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read(); N = len(data)

def decode_by_input(src, sp, complen, base, out):
    """Decode LZ4 consuming exactly complen input bytes from sp; reset-dict window base."""
    end = sp + complen
    while sp < end:
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                b = src[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            out += src[sp:sp+litlen]; sp += litlen
        if sp >= end: break          # block ended on literals
        off = src[sp] | (src[sp+1] << 8); sp += 2
        cur = len(out) - base
        if off == 0 or off > cur: raise ValueError("badoff")
        mlen = token & 0xF
        if mlen == 15:
            while True:
                b = src[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        st = len(out) - off
        for i in range(mlen): out.append(out[st+i])
    if sp != end: raise ValueError("input overshoot")
    return sp

def decode_by_output(src, sp, outlen, base, out):
    target = len(out) + outlen
    while len(out) < target:
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                b = src[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            out += src[sp:sp+litlen]; sp += litlen
        if len(out) >= target: break
        off = src[sp] | (src[sp+1] << 8); sp += 2
        cur = len(out) - base
        if off == 0 or off > cur: raise ValueError("badoff")
        mlen = token & 0xF
        if mlen == 15:
            while True:
                b = src[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        st = len(out) - off
        for i in range(mlen): out.append(out[st+i])
    if len(out) != target: raise ValueError("out overshoot")
    return sp

def run(H, endian, mode, reset=True):
    out = bytearray(); sp = 0
    fmt = endian + {1:"B",2:"H",3:None,4:"I"}[H]
    while len(out) < UNCOMP:
        if sp + H > N: raise ValueError("eof hdr")
        if H == 3:
            v = int.from_bytes(data[sp:sp+3], "little" if endian=="<" else "big")
        else:
            v = struct.unpack(fmt, data[sp:sp+H])[0]
        sp += H
        base = len(out) if reset else 0
        if v == 0 or v > 0x2000000: raise ValueError("bad size")
        if mode == "comp":
            sp = decode_by_input(data, sp, v, base, out)
        else:
            sp = decode_by_output(data, sp, min(v, UNCOMP-len(out)), base, out)
        if len(out) > UNCOMP: raise ValueError("over")
    return out, sp

found = False
for H in (1,2,3,4):
    for endian in ("<", ">"):
        for mode in ("comp", "out"):
            for reset in (True, False):
                try:
                    out, sp = run(H, endian, mode, reset)
                except Exception as e:
                    continue
                if len(out) == UNCOMP and out[0] == 0x00:
                    print(f"*** SUCCESS H={H} endian={endian} mode={mode} reset={reset} sp={sp}/{N}")
                    print("head:", bytes(out[:32]).hex(" "))
                    open(RAW + ".decoded", "wb").write(out)
                    found = True
                    sys.exit(0)
if not found:
    print("no chunked-by-size match")
