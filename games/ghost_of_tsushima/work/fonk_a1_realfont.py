#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_realfont.py — (1) verify fOnk is inside a texture resource; (2) harvest ALL
manifest resource names and grep for font/glyph/text/ui; (3) hunt real sfnt magics."""
import os, struct, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def clean(b): return bytes(x for x in b if x != 0xff)


def main():
    # 1) resource containing fOnk: custom_ag_bowl_china_001.msac.n.0.sps @0x156b6b0.
    #    Dump its header to confirm it's a texture (.sps = XTBS / Sucker Punch texture).
    rstart = 0x156b6b0
    print(f"== resource start @0x{rstart:x} (custom_ag_bowl_china_001.msac.n.0.sps) ==")
    print("   " + raw[rstart:rstart+32].hex())
    print(f"   magic ascii: {raw[rstart:rstart+4]!r}  (reversed {raw[rstart:rstart+4][::-1]!r})")
    # also the .s.0.sps at 0x156c168
    print(f"   next res @0x156c168 magic: {raw[0x156c168:0x156c168+4]!r} "
          f"({raw[0x156c168:0x156c168+4][::-1]!r})  hex {raw[0x156c168:0x156c168+16].hex()}")

    # 2) Harvest EVERY resource name in the manifest. The manifest entry has a
    #    u32 namelen then the name; names end in known suffixes. Simplest: regex for
    #    printable runs >=6 that look like asset names.
    print("\n== all resource-name suffixes (histogram) + font-ish names ==")
    names = []
    for m in re.finditer(rb"[A-Za-z0-9_./|\\-]{5,}", raw):
        s = m.group()
        # asset names contain a '.' extension marker or msac/sps
        if b"." in s and len(s) <= 120:
            names.append((m.start(), s))
    print(f"   {len(names)} printable name-like tokens")
    # suffix histogram
    suf = collections.Counter()
    for _, s in names:
        parts = s.rsplit(b".", 2)
        suf[b".".join(parts[-2:]) if len(parts)>=2 else s] += 1
    print("   top suffixes:")
    for k,c in suf.most_common(25):
        print(f"     {k.decode(errors='replace'):30s} {c}")
    # font-ish
    print("\n   FONT/GLYPH/TEXT/UI/MENU/KANJI/CHAR/TYPE/SUBTITLE name matches:")
    pat = re.compile(rb"font|glyph|kanji|subtitle|latin|arabic|charset|typeface|fontk", re.I)
    hits = [(o,s) for o,s in names if pat.search(s)]
    seen=set()
    for o,s in hits:
        if s in seen: continue
        seen.add(s)
        print(f"     @0x{o:x}: {s.decode(errors='replace')}")
    if not hits:
        print("     (none)")

    # 3) Real sfnt magic hunt across whole file, VALIDATED by first table tag.
    print("\n== validated sfnt/OTTO/ttcf/wOFF font-file magic hunt ==")
    KNOWN = {b"cmap", b"glyf", b"head", b"hhea", b"hmtx", b"loca", b"maxp",
             b"name", b"post", b"OS/2", b"CFF ", b"GPOS", b"GSUB", b"kern",
             b"cvt ", b"fpgm", b"prep", b"gasp", b"GDEF"}
    magics = [b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"wOFF", b"wOF2"]
    found=0
    for mg in magics:
        s=0
        while True:
            i = raw.find(mg, s)
            if i<0: break
            s=i+1
            # validate: sfnt has u16 numTables @+4, then 16-byte table records with 4-char tags
            try:
                numt = struct.unpack_from(">H", raw, i+4)[0]
                if 1 <= numt <= 60:
                    tag0 = raw[i+12:i+16]
                    tag1 = raw[i+28:i+32]
                    if tag0 in KNOWN or tag1 in KNOWN:
                        print(f"   VALID {mg!r} @0x{i:x} numTables={numt} tag0={tag0!r} tag1={tag1!r}")
                        found+=1
            except Exception:
                pass
    if not found:
        print("   0 valid sfnt fonts in game.sprig.texmeshman (confirms recon: no embedded TTF)")

    # 4) count 'fOnk' vs random 4-byte in the texture sea (is it really coincidental?)
    print(f"\n== 'fOnk' occurrences file-wide: {raw.count(b'fOnk')}  "
          f"(expected random in {N:,}B ≈ {N/2**32:.3f})")
    # sanity: how many times do a few other random 'texty' 4-byte combos appear?
    for probe in [b"fOnk", b"Glph", b"Font", b"aXcQ", b"MJwN", b"rRxF"]:
        print(f"     {probe!r}: {raw.count(probe)}")


if __name__ == "__main__":
    main()
