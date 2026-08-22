"""Brute-force the Disrupt LZ4LW framing with a manual LZ4-block decoder that
returns (output, bytes_consumed) so blocks can be chained without size headers."""
import struct, sys

RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read()

def lz4_block(src, sp, target):
    """Decode one LZ4 block from src[sp:], producing exactly `target` bytes.
    Returns (bytearray out, new sp) or raises."""
    out = bytearray()
    n = len(src)
    while len(out) < target:
        if sp >= n: raise ValueError("eof token")
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                if sp >= n: raise ValueError("eof litext")
                b = src[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            if sp + litlen > n: raise ValueError("eof lit")
            out += src[sp:sp+litlen]; sp += litlen
        if len(out) >= target:
            break
        # match
        if sp + 2 > n: raise ValueError("eof off")
        off = src[sp] | (src[sp+1] << 8); sp += 2
        if off == 0 or off > len(out): raise ValueError("bad off %d at out %d" % (off, len(out)))
        mlen = token & 0xF
        if mlen == 15:
            while True:
                if sp >= n: raise ValueError("eof mext")
                b = src[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        start = len(out) - off
        for i in range(mlen):
            out.append(out[start + i])
    return out, sp

def try_chain(start, bs, hdr, endian, hdr_is_csz):
    """hdr: bytes of per-block header (0,2,4). hdr_is_csz: header gives compressed size (else uncompressed)."""
    sp = start; out = bytearray(); blocks = 0
    while len(out) < UNCOMP:
        if hdr == 0:
            usz = min(bs, UNCOMP - len(out))
            chunk, sp = lz4_block(data, sp, usz)
            out += chunk
        else:
            fmt = endian + ("H" if hdr == 2 else "I")
            if sp + hdr > len(data): return None
            val = struct.unpack(fmt, data[sp:sp+hdr])[0]; sp += hdr
            if hdr_is_csz:
                usz = min(bs, UNCOMP - len(out))
                if val == 0 or sp + val > len(data): return None
                chunk, _ = lz4_block(data, sp, usz); sp += val
                out += chunk
            else:
                usz = val
                if usz == 0 or usz > 0x1000000: return None
                chunk, sp = lz4_block(data, sp, usz)
                out += chunk
        blocks += 1
        if blocks > 5000: return None
    if len(out) == UNCOMP:
        return out, blocks
    return None

best = None
for start in range(0, 33):
    for bs in (UNCOMP, 0x10000, 0x20000, 0x40000, 0x8000, 0x4000, 0x80000, 0x100000):
        for hdr in (0, 2, 4):
            for endian in ("<", ">"):
                for hdr_is_csz in (True, False):
                    if hdr == 0 and (endian == ">" or hdr_is_csz is False):
                        continue  # endian/csz irrelevant when no header
                    try:
                        r = try_chain(start, bs, hdr, endian, hdr_is_csz)
                    except Exception:
                        r = None
                    if r:
                        out, blocks = r
                        print(f"MATCH start={start} bs={bs:#x} hdr={hdr} endian={endian} csz={hdr_is_csz} blocks={blocks}")
                        print("head:", bytes(out[:32]).hex(" "))
                        print("text sample:", bytes(out[:60]))
                        open(RAW + ".decoded", "wb").write(out)
                        sys.exit(0)
print("no match in brute force grid")
