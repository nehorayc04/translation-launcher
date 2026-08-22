"""Greedy LZ4 decode from each start offset; report how far it gets + sample.
Reveals where the real LZ4 stream begins and the block boundary."""
RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
data = open(RAW, "rb").read()

def greedy(src, sp, limit=300000):
    out = bytearray(); n=len(src)
    while len(out) < limit:
        if sp >= n: break
        token = src[sp]; sp += 1
        litlen = token >> 4
        if litlen == 15:
            while True:
                if sp>=n: return out,sp,"eof-litext"
                b=src[sp]; sp+=1; litlen+=b
                if b!=255: break
        if litlen:
            if sp+litlen>n: return out,sp,"eof-lit"
            out += src[sp:sp+litlen]; sp+=litlen
        # a block may legally end right after the last literal run
        if sp+2 > n: return out,sp,"end-after-lit"
        off = src[sp] | (src[sp+1]<<8); sp+=2
        if off==0 or off>len(out): return out,sp,f"badoff({off})@out{len(out)}"
        mlen = token & 0xF
        if mlen==15:
            while True:
                if sp>=n: return out,sp,"eof-mext"
                b=src[sp]; sp+=1; mlen+=b
                if b!=255: break
        mlen+=4
        start=len(out)-off
        for i in range(mlen): out.append(out[start+i])
    return out,sp,"limit"

# how readable is output? count printable ascii + valid-looking arabic utf16
def score(b):
    if not b: return 0
    pr = sum(1 for x in b[:2000] if 9<=x<=13 or 32<=x<=126 or x in (0,) )
    return pr/min(len(b),2000)

best=[]
for start in range(0,80):
    out,end,why = greedy(data,start)
    best.append((len(out), start, why, bytes(out[:40])))
best.sort(reverse=True)
for ln,st,why,sample in best[:12]:
    print(f"start={st:3d} outlen={ln:7d} stop={why:18s} sample={sample.hex(' ')}")
    try: print("        ascii:", sample.decode('latin1').replace(chr(0),'.'))
    except: pass
