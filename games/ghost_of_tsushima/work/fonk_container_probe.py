#!/usr/bin/env python3
"""fOnk research part 2: (a) exe context around FONTK/FONT reflection tags + hunt for
per-struct field-name reflection; (b) parse game.sprig.packman index; (c) map the fOnk
chunk region inside game.sprig.texmeshman with FourCC scan + entropy windows."""
import struct, math, os, collections

BASE = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract"
EXE  = r"F:/Games/Ghost of Tsushima DC/GhostOfTsushima.exe"
TMM  = os.path.join(BASE, "game.sprig.texmeshman")
PKM  = os.path.join(BASE, "game.sprig.packman")

def rd(p):
    with open(p,"rb") as f: return f.read()

def hexdump(b, base=0, n=256):
    out=[]
    for i in range(0, min(n,len(b)), 16):
        chunk=b[i:i+16]
        hx=" ".join(f"{x:02x}" for x in chunk)
        asc="".join(chr(x) if 32<=x<127 else "." for x in chunk)
        out.append(f"  {base+i:08x}  {hx:<47}  {asc}")
    return "\n".join(out)

def entropy(b):
    if not b: return 0.0
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

def part_a():
    print("="*70); print("PART A — exe reflection tags")
    buf=rd(EXE)
    for tag,off in [("FONT",0x0114b744),("FONTK",0x011628f8),("SFontData",0x01157db8)]:
        # exe is loaded from file; these offsets are FILE offsets from part1 (raw scan)
        print(f"\n-- context around {tag} @0x{off:08x} (file bytes) --")
        print(hexdump(buf[off-32:off+64], off-32, 96))
    # Is 'FONT'/'FONTK' referenced as a FourCC little-endian 'TNOF'/'KTNOF'? scan raw
    for fourcc in [b"fOnk", b"FONT", b"FNTK", b"KTNOF", b"knOf"]:
        n=buf.count(fourcc)
        print(f"exe count {fourcc!r} = {n}")

def part_b():
    print("\n"+"="*70); print("PART B — game.sprig.packman parse")
    b=rd(PKM); print(f"size={len(b):,}")
    print("head:"); print(hexdump(b,0,96))
    # header per task: two u64 hashes, then u32 3621, u32 3614
    h0,h1 = struct.unpack_from("<QQ", b, 0)
    a,c = struct.unpack_from("<II", b, 16)
    print(f"\n hash0=0x{h0:016x} hash1=0x{h1:016x}  count_a={a} count_b={c}")
    # try to find the record array start + stride. Task says 16-byte records
    # {0x80013e8a3870aa1e, +2,...}. Scan for that pattern.
    needle = struct.pack("<Q", 0x80013e8a3870aa1e)
    p = b.find(needle)
    print(f" first record-id 0x80013e8a3870aa1e at file off {p} (0x{p:x})" if p>=0 else " record-id not found")
    if p>=0:
        print(" record region hexdump:")
        print(hexdump(b[p:], p, 160))
        # try strides 8/16/24; show first 12 u64 from p
        u64s = struct.unpack_from("<%dQ"%min(24,(len(b)-p)//8), b, p)
        print(" u64 stream from record start:")
        for i,v in enumerate(u64s):
            print(f"   [{i:2}] 0x{v:016x}  ({v})")
    # total structure sizing guess
    print(f"\n bytes after header(24) = {len(b)-24}; /16={ (len(b)-24)/16 }; /8={(len(b)-24)/8}")
    print(f"  count_a*16={a*16}  count_a*8={a*8}  count_b*16={c*16}")

def part_c():
    print("\n"+"="*70); print("PART C — fOnk region in texmeshman")
    b=rd(TMM); print(f"tmm size={len(b):,}")
    print(f"container magic head: {b[:16]!r}")
    p=b.find(b"fOnk")
    print(f"\n fOnk tag at 0x{p:x} ({p}); occurrences={b.count(b'fOnk')}")
    print(" 128 bytes BEFORE tag:")
    print(hexdump(b[p-128:p], p-128, 128))
    print(" 256 bytes AT/AFTER tag:")
    print(hexdump(b[p:p+256], p, 256))
    # entropy windows to find where high-entropy payload starts/ends
    print("\n entropy per 4KB window, tag-256K .. tag+512K:")
    lo=max(0,p-0x40000); hi=min(len(b),p+0x80000)
    for w in range(lo, hi, 0x4000):
        e=entropy(b[w:w+0x4000])
        star=" *TAG*" if w<=p<w+0x4000 else ""
        print(f"   0x{w:08x}  H={e:.3f}{star}")
    # the recurring marker b1 39 79 8e
    mk=bytes([0xb1,0x39,0x79,0x8e])
    idxs=[i for i in range(max(0,p-0x2000), min(len(b),p+0x40000)) if b[i:i+4]==mk]
    print(f"\n marker b1 39 79 8e near tag (±): count={len(idxs)} first few: {[hex(i) for i in idxs[:12]]}")
    # scan for other 4-byte ASCII FourCC-ish tags in the 64KB after fOnk
    print("\n ascii FourCC-ish tokens in fOnk..+64KB:")
    seen=collections.Counter()
    reg=b[p:p+0x10000]
    for i in range(len(reg)-4):
        c4=reg[i:i+4]
        if all(chr(x).isalnum() or chr(x) in "_ " for x in c4):
            seen[c4]+=1
    for c4,n in seen.most_common(25):
        try: print(f"   {c4!r} x{n}")
        except: pass

if __name__=="__main__":
    part_a(); part_b(); part_c()
