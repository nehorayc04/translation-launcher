#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""fonk_decode.py — GoT DC "fOnk" investigation decoder/verifier (attempt #1).

WHAT THIS PROVES (verified against the REAL extract/game.sprig.texmeshman):
  The 4 bytes "fOnk" (66 4f 6e 6b) at offset 0x156bff7 are NOT a font. They are a
  COINCIDENTAL byte match INSIDE a BCn-compressed texture resource
  `custom_ag_bowl_china_001.msac.n.0.sps` (a china-bowl normal-map). So there is no
  fOnk glyph table / codepoint map / vertex data to decode there — the recon premise
  is refuted. The real in-game font is a hash-referenced `SFontData` resource (engine
  tag `FONTK`, sub-sections `FontGlyphs`/`FontVerts`) embedded inside a KCAP package,
  NOT this texture and NOT a TTF.

WHAT THIS TOOL ACTUALLY DECODES (a real, verified crack of the CONTAINER):
  The NAMS ("texmeshman") container directory: header + a resource manifest of
  {dataOffset,u32,nameLen,name}. `locate` maps any byte offset -> the owning resource,
  which is how the fOnk-is-a-texture claim is proven.

CLI:
  info    <texmeshman>            NAMS header + resource count + the fOnk verdict
  locate  <texmeshman> <hexoff>   which resource contains a byte offset
  dump    <texmeshman> <hexoff>   hexdump around an offset + owning resource
"""
import os, sys, struct, re

FONK_OFF = 0x156BFF7


def parse_header(raw):
    assert raw[:4] == b"NAMS", f"not a NAMS container: {raw[:4]!r}"
    ver = struct.unpack_from("<I", raw, 4)[0]
    h0, h1 = struct.unpack_from("<QQ", raw, 8)
    z, count, s1, s2 = struct.unpack_from("<IIII", raw, 0x18)
    return dict(version=ver, hash0=h0, hash1=h1, count=count, size1=s1, size2=s2,
                name_table_off=0x28)


def clean_name(b):
    """Names are framed [0xff][<=8 data bytes] inside the table; strip the 0xff frames."""
    return bytes(x for x in b if x != 0xff)


def harvest_entries(raw, lo=0, hi=None):
    """Scan the manifest for well-formed {dataOffset,field1,nameLen,name} entries.
    Layout (verified): at the file offset of a name N, u32 nameLen == raw[N-4],
    u32 dataOffset == raw[N-12]. We locate names by their asset extensions."""
    hi = len(raw) if hi is None else hi
    ents = []
    # asset names end with one of these tokens; scan for '.sps'/'.xmesh'/'.msac'... names
    for m in re.finditer(rb"[A-Za-z0-9_./|-]{6,}\.(?:sps|xmesh|msac|psd|dds|png|bmp|tga)"
                         rb"(?:\.[a-z0-9]+)*", raw[lo:hi]):
        no = lo + m.start()
        if no < 12:
            continue
        nl = struct.unpack_from("<I", raw, no - 4)[0]
        if not (3 <= nl <= 120):
            continue
        doff = struct.unpack_from("<I", raw, no - 12)[0]
        if not (0x1000 <= doff < len(raw)):
            continue
        ents.append((doff, no, nl, clean_name(raw[no:no + nl])))
    # dedupe by dataOffset, sort
    seen = set(); out = []
    for e in sorted(ents):
        if e[0] in seen:
            continue
        seen.add(e[0]); out.append(e)
    return out


_ENTS_CACHE = {}


def locate(raw, off):
    """Return (resource_offset, name, size, offset_into_resource) that owns `off`.
    The manifest (names+dataOffset) lives in a separate region from the data blobs,
    so we harvest the WHOLE file, sort by dataOffset, then bracket `off`."""
    key = id(raw)
    ents = _ENTS_CACHE.get(key)
    if ents is None:
        ents = harvest_entries(raw)          # whole-file
        _ENTS_CACHE[key] = ents
    for i, (doff, no, nl, nm) in enumerate(ents):
        nxt = ents[i + 1][0] if i + 1 < len(ents) else None
        if doff <= off and (nxt is None or off < nxt):
            size = (nxt - doff) if nxt else None
            return doff, nm, size, off - doff
    return None


def hexdump(b, base=0, n=None):
    n = len(b) if n is None else n
    out = []
    for i in range(0, min(n, len(b)), 16):
        c = b[i:i + 16]
        out.append(f"  {base + i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   + "".join(chr(x) if 32 <= x < 127 else '.' for x in c))
    return "\n".join(out)


def cmd_info(path):
    raw = open(path, "rb").read()
    h = parse_header(raw)
    print(f"NAMS container {os.path.basename(path)}  {len(raw):,} B")
    print(f"  version=0x{h['version']:x} hash0=0x{h['hash0']:016x} hash1=0x{h['hash1']:016x}")
    print(f"  declared resource count={h['count']}  size1={h['size1']} size2={h['size2']}")
    ents = harvest_entries(raw)
    print(f"  harvested {len(ents)} texture/mesh resource entries (by asset name)")
    # verdict on fOnk
    fonk_cnt = raw.count(b"fOnk")
    print(f"\n  'fOnk' occurrences in this file: {fonk_cnt}")
    if b"fOnk" in raw:
        off = raw.find(b"fOnk")
        loc = locate(raw, off)
        if loc:
            doff, nm, size, into = loc
            print(f"  'fOnk'@0x{off:x} is INSIDE resource:")
            print(f"     name = {nm.decode(errors='replace')}")
            print(f"     resource data @0x{doff:x} size={size} -> fOnk is {into} B into it")
            print(f"     => VERDICT: fOnk is coincidental bytes in a texture, NOT a font.")
    for nd in (b"FONTK", b"SFontData", b"FontGlyphs", b"FontVerts"):
        print(f"  real font tag {nd!r} present here: {nd in raw}")


def cmd_locate(path, hexoff):
    raw = open(path, "rb").read()
    off = int(hexoff, 16) if hexoff.lower().startswith("0x") else int(hexoff, 16)
    loc = locate(raw, off)
    if not loc:
        print(f"0x{off:x}: no owning resource found in scan window"); return
    doff, nm, size, into = loc
    print(f"0x{off:x} -> resource {nm.decode(errors='replace')} @0x{doff:x} "
          f"size={size} (+{into} into it)")


def cmd_dump(path, hexoff):
    raw = open(path, "rb").read()
    off = int(hexoff, 16)
    print(hexdump(raw[off - 32:off + 96], off - 32))
    cmd_locate(path, hexoff)


# ---- REAL font: 64-byte FontGlyphs tables inside KCAP (.xpps) packages ----
GREC = 64


def find_glyph_tables(data):
    """Find 64-byte FontGlyphs tables: seed on cp 'A'(0x41) at stride 64 with B,C,D
    following, walk back/forward while cp ascends; sentinel cp=0xffff ends a table."""
    tables = []
    seen = set()
    i = 0
    while True:
        p = data.find(b"\x41\x00", i)
        if p < 0:
            break
        i = p + 1
        if p + 4 * GREC > len(data):
            continue
        if not all(struct.unpack_from("<H", data, p + k * GREC)[0] == 0x41 + k
                   for k in range(1, 4)):
            continue
        # walk back
        s = p
        while s - GREC >= 0:
            a = struct.unpack_from("<H", data, s - GREC)[0]
            c = struct.unpack_from("<H", data, s)[0]
            if a == c - 1 and 1 <= a <= 0x6ff:
                s -= GREC
            else:
                break
        if s in seen:
            continue
        seen.add(s)
        cps = []
        q = s
        while q + GREC <= len(data):
            cp = struct.unpack_from("<H", data, q)[0]
            if cp == 0xffff:
                cps.append(cp); q += GREC; break
            if cps and cp <= cps[-1]:
                break
            if not (1 <= cp <= 0xfffe):
                break
            cps.append(cp); q += GREC
        if len(cps) >= 8:
            tables.append((s, q, cps))
    return tables


def cmd_glyphs(path):
    """Decode 64-byte FontGlyphs tables from a raw KCAP (.xpps) file."""
    data = open(path, "rb").read()
    print(f"KCAP package {os.path.basename(path)}  {len(data):,} B  magic={data[:4]!r}")
    tbls = find_glyph_tables(data)
    print(f"found {len(tbls)} FontGlyphs table(s) (64-byte records, cp@+0)")
    for s, e, cps in tbls[:40]:
        real = [c for c in cps if c != 0xffff]
        if not real:
            continue
        cov = (f"ASCII={sum(1 for c in real if 0x20<=c<=0x7e)} "
               f"Arabic={sum(1 for c in real if 0x600<=c<=0x6ff)} "
               f"Hebrew={sum(1 for c in real if 0x5d0<=c<=0x5ea)} "
               f"CJK={sum(1 for c in real if c>=0x3000)}")
        print(f"  @0x{s:x} n={len(real)} cp[0x{min(real):x}..0x{max(real):x}] {cov}")
    # detail the first table's A record
    if tbls:
        s, e, cps = tbls[0]
        for k, cp in enumerate(cps):
            if cp == 0x41:
                r = data[s + k * GREC:s + k * GREC + GREC]
                print(f"\n  sample record cp=0x41('A') @0x{s+k*GREC:x}:\n    {r.hex()}")
                break


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(0)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "info":
        cmd_info(path)
    elif cmd == "locate":
        cmd_locate(path, sys.argv[3])
    elif cmd == "dump":
        cmd_dump(path, sys.argv[3])
    elif cmd == "glyphs":
        cmd_glyphs(path)
    else:
        print(__doc__)
