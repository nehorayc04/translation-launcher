#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_nams.py — crack the NAMS container directory using the SMALL texmeshman
files, then bound the fOnk chunk in the big one. Also try candidate codecs on the
bytes right after fOnk to settle compressed-vs-raw locally."""
import os, struct, math, collections, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
SMALL= [os.path.join(EX, "all_shaders.texmeshman"),
        os.path.join(EX, "pulse.sprig.texmeshman")]
FONK_OFF = 0x156BFF7


def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())


def hd(b, base=0, n=256):
    out=[]
    for i in range(0, min(n,len(b)), 16):
        c=b[i:i+16]
        out.append(f"  {base+i:06x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   + "".join(chr(x) if 32<=x<127 else '.' for x in c))
    return "\n".join(out)


def dump_header(path):
    raw = open(path,"rb").read()
    print(f"\n{'='*72}\n== {os.path.basename(path)} ({len(raw):,} B) magic={raw[:4]!r}")
    print(hd(raw, 0, 256))
    # interpret header ints
    print("   u32[0:16]:", [hex(x) for x in struct.unpack_from("<16I", raw, 0)])
    return raw


def main():
    for p in SMALL:
        raw = dump_header(p)
        # find any 4-byte printable tags near start
        # look for the string table: the 0xff-prefixed names
        ffpos = [i for i in range(0x18, min(2000,len(raw))) if raw[i]==0xff]
        print(f"   0xff positions in [0x18,2000): first {ffpos[:12]} (deltas {[ffpos[i+1]-ffpos[i] for i in range(min(8,len(ffpos)-1))]})")

    # big file header
    raw = open(BIG,"rb").read()
    print(f"\n{'='*72}\n== game.sprig.texmeshman header ==")
    print(hd(raw, 0, 128))
    print("   u32[0:16]:", [hex(x) for x in struct.unpack_from("<16I", raw, 0)])
    # 0xff spacing in the name region
    ffpos = [i for i in range(0x1c, 4000) if raw[i]==0xff]
    print(f"   0xff positions [0x1c,4000): first {ffpos[:16]}")
    print(f"     deltas: {[ffpos[i+1]-ffpos[i] for i in range(min(20,len(ffpos)-1))]}")

    # try codecs on 64KB right after fOnk tag (skip the 4-char tag)
    seg = raw[FONK_OFF+4 : FONK_OFF+4+65536]
    print(f"\n== codec attempts on fOnk+4 .. +64KB ==")
    # zlib/gzip/raw-deflate at various offsets
    import lzma, bz2
    for name, fn in [("zlib", lambda d: zlib.decompress(d)),
                     ("raw-deflate", lambda d: zlib.decompressobj(-15).decompress(d)),
                     ("lzma", lambda d: lzma.decompress(d)),
                     ("bz2", lambda d: bz2.decompress(d))]:
        for off in range(0, 20):
            try:
                out = fn(seg[off:])
                if len(out) > 64:
                    print(f"   {name} @+{off}: OK -> {len(out)} bytes, head {out[:16].hex()}")
                    break
            except Exception:
                pass
    try:
        import lz4.block as lb
        for sz in (0x40000, 0x100000, 0x200000):
            try:
                out = lb.decompress(seg, uncompressed_size=sz)
                print(f"   lz4.block (usize={sz:#x}): OK -> {len(out)} bytes head {out[:16].hex()}")
                break
            except Exception as e:
                pass
    except ImportError:
        print("   lz4 not available")
    try:
        import lz4.frame as lf
        out = lf.decompress(seg)
        print(f"   lz4.frame: OK -> {len(out)}")
    except Exception as e:
        print(f"   lz4.frame: no ({type(e).__name__})")
    print("   (no line above = not a standard codec at those offsets => RAW structured data)")

    # Also: histogram of DELTA between consecutive bytes (delta-coded data has a
    # sharp spike at 0). And check int16 value distribution (small signed).
    seg2 = raw[FONK_OFF:FONK_OFF+65536]
    i16 = struct.unpack_from("<%dh" % (len(seg2)//2), seg2, 0)
    small = sum(1 for v in i16 if -256 <= v <= 256)
    print(f"\n== int16 stats on fOnk+64KB: {len(i16)} values, {100*small/len(i16):.1f}% in [-256,256]")
    absmean = sum(abs(v) for v in i16)/len(i16)
    print(f"   mean|int16|={absmean:.1f}  (small => delta/coord data)")


if __name__ == "__main__":
    main()
