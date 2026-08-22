"""Pin down the LZ4LW block boundary: decode block1 from byte1, report input pos
at the break and the bytes straddling the boundary (suspected next-block header)."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
data = open(RAW, "rb").read()
print("total compressed:", len(data), "expected uncompressed: 5061841")

def decode_block(src, sp):
    """Decode standard LZ4 block until an invalid match offset (> output) or eof.
    Returns (out, sp_at_break, reason, last_token_pos)."""
    out = bytearray(); n=len(src)
    while True:
        tok_pos = sp
        if sp>=n: return out,sp,"eof",tok_pos
        token=src[sp]; sp+=1
        litlen=token>>4
        if litlen==15:
            while True:
                if sp>=n: return out,sp,"eof-litext",tok_pos
                b=src[sp]; sp+=1; litlen+=b
                if b!=255: break
        if litlen:
            if sp+litlen>n: return out,sp,"eof-lit",tok_pos
            out+=src[sp:sp+litlen]; sp+=litlen
        if sp+2>n: return out,sp,"end-after-lit",tok_pos
        off=src[sp]|(src[sp+1]<<8)
        if off==0 or off>len(out):
            return out,sp,f"badoff:{off}>out:{len(out)}",tok_pos
        sp+=2
        mlen=token&0xF
        if mlen==15:
            while True:
                if sp>=n: return out,sp,"eof-mext",tok_pos
                b=src[sp]; sp+=1; mlen+=b
                if b!=255: break
        mlen+=4
        st=len(out)-off
        for i in range(mlen): out.append(out[st+i])

out,sp,why,tokpos = decode_block(data,1)
print(f"block1: uncompressed={len(out)} input consumed=[1..{tokpos}) compressed≈{tokpos-1}")
print(f"stop reason: {why}  (token at input pos {tokpos})")
print("bytes [0..1]:", data[0:1].hex())
print(f"bytes straddling boundary [{tokpos-4}..{tokpos+16}]:", data[tokpos-4:tokpos+16].hex(" "))
print("block1 head (decoded):", bytes(out[:48]).hex(" "))
# does block1 uncompressed look 16-aligned or like a round size?
print("uncompressed mod 16 =", len(out)%16, " /65536=", len(out)/65536)
# try: maybe byte0 (0x3a) and the boundary token region encode block sizes.
# Hypothesis: each block prefixed by u8? show first bytes
print("first 8 bytes:", data[:8].hex(" "))
