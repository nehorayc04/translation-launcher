#!/usr/bin/env python3
"""fOnk research part 4: prove packman offset table maps into texmeshman (locate the
fOnk resource boundary), and characterize the fOnk record-stream head + trailing verts."""
import struct, os, collections

BASE = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract"
TMM  = os.path.join(BASE, "game.sprig.texmeshman")
PKM  = os.path.join(BASE, "game.sprig.packman")

def rd(p):
    with open(p,"rb") as f: return f.read()
def hexdump(b, base=0, n=256):
    out=[]
    for i in range(0,min(n,len(b)),16):
        c=b[i:i+16]; hx=" ".join(f"{x:02x}" for x in c)
        asc="".join(chr(x) if 32<=x<127 else "." for x in c)
        out.append(f"  {base+i:08x}  {hx:<47}  {asc}")
    return "\n".join(out)

def main():
    pk=rd(PKM); tm=rd(TMM)
    fonk=tm.find(b"fOnk")
    print(f"fOnk in texmeshman at 0x{fonk:x} ({fonk})")

    # Interpret packman as: header24 | u64 id[N] | u64 off[N] ... find N where the
    # 'off' array contains ascending offsets < len(tm) AND the fOnk offset appears.
    ca = struct.unpack_from("<I", pk, 16)[0]
    cb = struct.unpack_from("<I", pk, 20)[0]
    print(f"count_a={ca} count_b={cb} filelen={len(pk)}")
    # candidate: id array is cb entries, then off array is cb entries
    for N,label in [(cb,"count_b"),(ca,"count_a")]:
        idbeg=24; idend=24+N*8; offend=idend+N*8
        if offend>len(pk):
            print(f" N={N}({label}): off array overruns file"); continue
        offs=struct.unpack_from("<%dQ"%N, pk, idend)
        asc=all(offs[i]<=offs[i+1] for i in range(N-1))
        inb=sum(1 for o in offs if o<=len(tm))
        print(f" N={N}({label}): idend=0x{idend:x} offend=0x{offend:x} ascending={asc} in_texmesh_bounds={inb}/{N} first5={[hex(o) for o in offs[:5]]} last3={[hex(o) for o in offs[-3:]]}")
        if fonk in offs:
            print(f"   *** fOnk offset 0x{fonk:x} IS in this offset array at index {offs.index(fonk)} ***")
        else:
            # nearest
            near=min(offs, key=lambda o: abs(o-fonk))
            print(f"   nearest offset to fOnk: 0x{near:x} (delta {near-fonk})")

    # Just scan the whole packman (u64 aligned) for the fOnk offset or offsets bracketing it
    print("\n scan packman u64 for value bracketing fOnk offset:")
    vals=struct.unpack_from("<%dQ"%(len(pk)//8), pk, 0)
    below=[v for v in vals if v<=fonk and v>fonk-0x100000]
    above=[v for v in vals if v>=fonk and v<fonk+0x100000]
    print(f"   u64 <=fonk within 1MB below: {[hex(v) for v in sorted(set(below))[-6:]]}")
    print(f"   u64 >=fonk within 1MB above: {[hex(v) for v in sorted(set(above))[:6]]}")

    # fOnk record head: dump 512 bytes and try to read leading counts
    print("\n fOnk head +0 .. +64 as various ints:")
    head=tm[fonk:fonk+64]
    print(hexdump(head, fonk, 64))
    print("   after tag(+4): u32s:", [hex(x) for x in struct.unpack_from("<8I", tm, fonk+4)])
    print("   after tag(+4): u16s:", [hex(x) for x in struct.unpack_from("<12H", tm, fonk+4)])

    # The '10 xx yy 77 zz' motif — hypothesize it's a per-glyph record tag. Count total
    # glyphs a font needs: Latin+Arabic+CJK+... Show the byte histogram of the low nibble
    # after '46 77' to see if 'ce/8e/4e/0e' cycle (a 2-bit field).
    reg=tm[fonk:fonk+0x1c0000]
    tag_positions=[i for i in range(len(reg)-5) if reg[i]==0x10 and reg[i+3]==0x77]
    print(f"\n '10 ?? ?? 77 ??' occurrences in fOnk..+1.75MB: {len(tag_positions)}")
    if len(tag_positions)>3:
        d=[tag_positions[i+1]-tag_positions[i] for i in range(len(tag_positions)-1)]
        c=collections.Counter(d)
        print(f"   gap histogram (top): {c.most_common(12)}")
    # low byte after 77
    lb=collections.Counter(reg[i+4] for i in tag_positions)
    print(f"   byte after '..77': {[(hex(k),v) for k,v in lb.most_common(8)]}")

if __name__=="__main__":
    main()
