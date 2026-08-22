"""Crack LZ4LW framing. Validation anchors: decompressed rml MUST start 0x00,
and total MUST == UNCOMP. Hypothesis grid: 1-byte prefix (0x3a) then concatenated
standard-LZ4 blocks of FIXED uncompressed size S (reset dict per block, last partial).
Search S over block1's literal-run-end candidates."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read()
N = len(data)

def decode_one_block(src, sp, target, base):
    """Decode standard LZ4 block from src[sp:], producing exactly `target` bytes into
    a buffer whose match-window base index is `base` (offsets reference out[base:]).
    `out` is the GLOBAL list; for reset-dict pass base=len(out) at block start.
    Returns new sp, or raises ValueError on malformed."""
    out = decode_one_block.out
    produced = 0
    while produced < target:
        if sp >= N: raise ValueError("eof token")
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                if sp >= N: raise ValueError("eof litext")
                b = src[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            if sp + litlen > N: raise ValueError("eof lit")
            out += src[sp:sp+litlen]; sp += litlen; produced += litlen
        if produced >= target:
            break
        if sp + 2 > N: raise ValueError("eof off")
        off = src[sp] | (src[sp+1] << 8); sp += 2
        cur = len(out) - base               # output within this block's window
        if off == 0 or off > cur: raise ValueError("badoff")
        mlen = token & 0xF
        if mlen == 15:
            while True:
                if sp >= N: raise ValueError("eof mext")
                b = src[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        st = len(out) - off
        for i in range(mlen): out.append(out[st+i])
        produced += mlen
    if produced != target:
        raise ValueError("overshoot")  # block must end exactly on target (after a literal)
    return sp

def full_decode_fixed(S):
    decode_one_block.out = bytearray()
    out = decode_one_block.out
    sp = 1  # skip byte0 prefix
    while len(out) < UNCOMP:
        target = min(S, UNCOMP - len(out))
        base = len(out)              # reset dictionary each block
        sp = decode_one_block(out, sp, target, base) if False else None
        # NOTE: src is `data`, not out; fix call below
    return out

# fix: src is data
def full_decode(S, reset=True):
    decode_one_block.out = bytearray()
    out = decode_one_block.out
    sp = 1
    while len(out) < UNCOMP:
        target = min(S, UNCOMP - len(out))
        base = len(out) if reset else 0
        sp = _decode_block(data, sp, target, base, out)
    return out, sp

def _decode_block(src, sp, target, base, out):
    produced = 0
    while produced < target:
        if sp >= N: raise ValueError("eof")
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                b = src[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            out += src[sp:sp+litlen]; sp += litlen; produced += litlen
        if produced >= target: break
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
        produced += mlen
    if produced != target: raise ValueError("overshoot")
    return sp

# 1) collect block1 literal-end candidate sizes (where a block could legally end)
def block1_candidates():
    out = bytearray(); sp = 1; cands = []
    while True:
        if sp >= N: break
        token = src = data[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                b = data[sp]; sp += 1; litlen += b
                if b != 255: break
        if litlen:
            out += data[sp:sp+litlen]; sp += litlen
        cands.append((len(out), sp))   # could end here (after a literal run)
        if sp + 2 > N: break
        off = data[sp] | (data[sp+1] << 8)
        if off == 0 or off > len(out): break  # desync = overshoot point
        sp += 2
        mlen = token & 0xF
        if mlen == 15:
            while True:
                b = data[sp]; sp += 1; mlen += b
                if b != 255: break
        mlen += 4
        st = len(out) - off
        for i in range(mlen): out.append(out[st+i])
        if len(out) > 70000: break
    return cands

cands = block1_candidates()
print(f"block1 candidate end-points: {len(cands)} (max out {cands[-1][0]})")
# 2) for each candidate S (reset & linked), try full decode; validate
import itertools
tried = 0
for reset in (True, False):
    for S, sp1 in cands:
        if S < 256: continue
        tried += 1
        try:
            out, endsp = full_decode(S, reset=reset)
        except Exception:
            continue
        if len(out) == UNCOMP and out[0] == 0x00:
            print(f"*** SUCCESS S={S} ({S:#x}) reset={reset} endsp={endsp}/{N} firstbyte={out[0]}")
            open(RAW + ".decoded", "wb").write(out)
            print("head:", bytes(out[:32]).hex(" "))
            sys.exit(0)
print(f"no fixed-S match (tried {tried} candidates x2 modes)")
