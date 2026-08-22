#!/usr/bin/env python3
"""fOnk research part 3: fully map packman record layout (find the id array end +
any parallel offset/size table), NAMS/texmeshman container header + TOC, and confirm
whether sub-resources are independently compressed (magic scan)."""
import struct, os, math, collections

BASE = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract"
TMM  = os.path.join(BASE, "game.sprig.texmeshman")
PKM  = os.path.join(BASE, "game.sprig.packman")
SHD  = os.path.join(BASE, "all_shaders.texmeshman")

def rd(p):
    with open(p,"rb") as f: return f.read()

def hexdump(b, base=0, n=256):
    out=[]
    for i in range(0, min(n,len(b)), 16):
        c=b[i:i+16]
        hx=" ".join(f"{x:02x}" for x in c)
        asc="".join(chr(x) if 32<=x<127 else "." for x in c)
        out.append(f"  {base+i:08x}  {hx:<47}  {asc}")
    return "\n".join(out)

def packman():
    b=rd(PKM); n=len(b)
    print("="*70); print(f"PACKMAN full map  size={n:,}")
    h0,h1,ca,cb = struct.unpack_from("<QQII", b, 0)
    print(f" hash0=0x{h0:016x} hash1=0x{h1:016x} count_a={ca} count_b={cb}")
    # walk u64 ids from 0x18; detect where the monotonic top-bit-set id array stops
    off=0x18
    ids=[]
    p=off
    while p+8<=n:
        v=struct.unpack_from("<Q",b,p)[0]
        if v & 0x8000000000000000:
            ids.append((p,v)); p+=8
        else:
            break
    print(f" id-array: {len(ids)} u64 ids, from 0x{off:x} to 0x{p:x}")
    print(f"   first id 0x{ids[0][1]:016x}  last id 0x{ids[-1][1]:016x}")
    print(f"   ids sorted ascending? {all(ids[i][1]<=ids[i+1][1] for i in range(len(ids)-1))}")
    print(f"   count vs count_a({ca}): {'MATCH' if len(ids)==ca else 'NO'}  vs count_b({cb}): {'MATCH' if len(ids)==cb else 'NO'}")
    print(f" bytes remaining after id array: {n-p} (=0x{n-p:x}); /4={(n-p)/4}; /8={(n-p)/8}")
    print(" region after id array:")
    print(hexdump(b[p:], p, 256))
    # try interpret remainder as u32 offsets
    rem=n-p
    if rem>=4:
        u32=struct.unpack_from("<%dI"%min(32,rem//4), b, p)
        print(" u32 stream after ids:", [hex(x) for x in u32[:24]])
        # are these ascending offsets into texmeshman? show as decimal
        print("   as dec:", [x for x in u32[:16]])

def nams(path, label):
    b=rd(path); n=len(b)
    print("\n"+"="*70); print(f"{label}  size={n:,}")
    print(hexdump(b,0,128))
    magic=b[:4]
    # header ints
    ints=struct.unpack_from("<8I", b, 4)
    print(" header u32[1..8] after magic:", [hex(x) for x in ints], [x for x in ints])
    # scan for compression magics anywhere
    for mg,name in [(b"\x78\x9c","zlib78 9c"),(b"\x78\xda","zlib78 da"),
                    (b"\x04\x22\x4d\x18","lz4frame"),(b"\x28\xb5\x2f\xfd","zstd"),
                    (b"NAMS","NAMS"),(b"fOnk","fOnk"),(b"XTBS","XTBS(tex)"),
                    (b"KCAP","KCAP")]:
        print(f"   count {name:12} = {b.count(mg)}")
    # readable ascii tokens density (a compressed blob has ~none)
    printable = sum(1 for x in b[:0x10000] if 0x20<=x<0x7f)
    print(f"   printable ratio in first 64KB = {printable/0x10000:.3f} (compressed~0.4-0.5, structured-with-strings higher)")

def fonk_records():
    b=rd(TMM)
    p=b.find(b"fOnk")
    print("\n"+"="*70); print(f"fOnk RECORD-STREAM structure @0x{p:x}")
    # measure spacing of marker b1 39 79 8e across a big region
    mk=bytes([0xb1,0x39,0x79,0x8e])
    reg_lo=p; reg_hi=min(len(b), p+0x100000)
    pos=[i for i in range(reg_lo,reg_hi) if b[i:i+4]==mk]
    if len(pos)>2:
        deltas=[pos[i+1]-pos[i] for i in range(len(pos)-1)]
        cnt=collections.Counter(deltas)
        print(f" marker b1 39 79 8e: {len(pos)} hits in fOnk..+1MB; common gaps: {cnt.most_common(10)}")
    # the '10 2e 46 77' family: count the 4-byte '46 77' anchored motif
    fam=collections.Counter()
    for i in range(reg_lo, reg_hi-5):
        if b[i]==0x10 and b[i+3]==0x77:
            fam[b[i:i+5]]+=1
    print(f" '10 ?? ?? 77 ??' motif total = {sum(fam.values())}; top:")
    for k,v in fam.most_common(12):
        print(f"    {k.hex(' ')}  x{v}")
    # where does the high-entropy fOnk block END? scan entropy forward until it drops
    def H(x):
        if not x: return 0
        c=collections.Counter(x); m=len(x)
        return -sum((v/m)*math.log2(v/m) for v in c.values())
    print(" forward entropy 8KB windows from tag until it clearly drops (<6.0):")
    w=p
    while w < min(len(b), p+0x400000):
        e=H(b[w:w+0x2000])
        if e<6.0:
            print(f"    DROP at 0x{w:08x} H={e:.3f} (candidate fOnk end / next resource)")
            print(hexdump(b[w:w+96], w, 96))
            break
        w+=0x2000
    else:
        print("    no clear drop within +4MB (region stays dense)")

if __name__=="__main__":
    packman()
    nams(TMM, "TEXMESHMAN container (game.sprig.texmeshman)")
    nams(SHD, "all_shaders.texmeshman (compare)")
    fonk_records()
