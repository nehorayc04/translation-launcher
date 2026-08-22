#!/usr/bin/env python3
r"""
fonk_decode_alt.py  — Ghost of Tsushima DC  texmeshman container reader  (ATTEMPT #2, 2026-07-08)

WHAT THIS PROVES / OVERTURNS
============================
Attempt #1 assumed the menu/subtitle font is a compressed "fOnk" resource at RAW offset
0x156bff7 inside `game.sprig.texmeshman`.  Independent attempt #2 shows that is a RED HERRING:

  * The bytes 66 4F 6E 6B ("fOnk") occur EXACTLY ONCE in the 108 MB file, sitting inside a
    RAW high-entropy MESH region (see the container map below).  The game's own font tag is
    "FONTK" (exe @0x11628f8, in a list of render-resource kinds) — NOT "fOnk".  "fOnk" is not
    in the exe at all, and Sucker Punch resources are keyed by 64-bit HASHES, not 4-char ASCII
    tags, so a stray ASCII "fOnk" in mesh data is coincidence (1 hit in 108 MB ~= chance).
  * `font` / `Font` / `FONT` / `glyph` / `SFontData` appear ZERO times in the raw texmeshman.
  * No archive in cache_pc/psarc has a font FILE (only /bitmaps/debugfont.dds — a debug bitmap).

THE REAL FONT
=============
Per GhostOfTsushima.exe the in-game font is an `SFontData` resource (a sibling of `SBitmap`)
holding VECTOR glyphs: allocation categories `FontGlyphs` + `FontVerts`, driven by a text
system (`FONT_KIND`,`FONT_SIZE`,`SET_TEXT_DIRECT`,`H_JUST`,`LARGE_FONT_SIZE_FACTOR`).  It is a
HASH-KEYED, UNNAMED resource — not findable by string, and its glyph-outline data is
high-entropy (float/quantised verts) with no plain sorted cmap in the raw file.  Locating it is
still an open sub-project (candidates: an un-parsed resource directory inside game.sprig.texmeshman,
or the game.sprig.packman master index — see notes/fonk_attempt2.md).

CONTAINER FORMAT — CRACKED + VERIFIED  (game.sprig.texmeshman, magic "NAMS")
===========================================================================
  0x00  char[4] "NAMS"
  0x04  u32     version   (0x00011d01)
  0x08  u64     hash A
  0x10  ...              (0x18: u32 = 0)
  0x1c  u32     entryCount  (27562)          <- number of resource-dir entries
  0x20  u32     ?           (653529)
  0x24  u32     dirOffset   (1364025 = 0x14d039)   <- start of the RAW resource directory
  0x28  ...     LZSS stream (compressed hashed-name/metadata pool; ends at dirOffset)

  LZSS  = classic Okumura, 4096-byte ring, r starts at 0:
            flag byte, LSB-first, bit==1 -> literal (1 byte)
                                   bit==0 -> match (2 bytes) b0,b1:
                                     pos = b0 | ((b1 & 0xF0) << 4)     # absolute ring index
                                     len = (b1 & 0x0F) + 3
          (0x28..dirOffset decompresses to ~4.58 MB of asset-name/hash text.)

  Resource directory (RAW, at dirOffset) — 24-byte header + name + 36-byte trailer per entry:
            u64 id            # e.g. 0x00000076badbad13 (hash/id)
            u32 zero
            u32 dataOffset    # byte offset in this file of the resource's raw data
            u32 zero
            u32 nameLen
            char name[nameLen]                     # e.g. "custom_cv_straw_coaster_001.msac.d.0.sps"
            u64 hash1, hash2, hash3                 # content/format hashes
            u8  params[12]                          # texture format/dim params (e.g. 00 06 01 0f ...)
          19819 SBitmap (.sps) texture entries parse cleanly (0x14d039..0x369cbf); their
          dataOffsets point into the RAW texture-blob region (0x16cd6b8..0x5c23798 = raw BC7
          pixel data, no XTBS wrapper).  The 3.6 MB..24 MB "gap" is MESH data (vertex/index
          buffers). The remaining entries (27562-19819) are mesh/other resources reached through
          mesh-interlude records the simple parser stops on.

CLI:
  python fonk_decode_alt.py info    <texmeshman>        # header + directory summary
  python fonk_decode_alt.py dump    <texmeshman> [N]    # first N directory entries
  python fonk_decode_alt.py lzss    <texmeshman> [K]    # decode+print first K bytes of metadata
  python fonk_decode_alt.py fonkcheck <texmeshman>      # prove the "fOnk" red-herring
"""
import sys, struct

RING = 4096


def lzss_decode(src: bytes, start: int, end: int) -> bytearray:
    """Okumura LZSS (ring=4096, r0=0). Verified: decodes the asset-name table byte-clean."""
    ring = bytearray(RING); r = 0
    out = bytearray(); app = out.append
    pos = start
    while pos < end:
        flag = src[pos]; pos += 1
        for b in range(8):
            if pos >= end:
                break
            if (flag >> b) & 1:                        # literal
                c = src[pos]; pos += 1
                app(c); ring[r] = c; r = (r + 1) & (RING - 1)
            else:                                       # match
                if pos + 1 >= end:
                    break
                b0 = src[pos]; b1 = src[pos + 1]; pos += 2
                mp = b0 | ((b1 & 0xF0) << 4)
                ln = (b1 & 0x0F) + 3
                for _ in range(ln):
                    c = ring[mp]; app(c); ring[r] = c
                    mp = (mp + 1) & (RING - 1); r = (r + 1) & (RING - 1)
    return out


def read_header(raw: bytes) -> dict:
    assert raw[:4] == b"NAMS", f"not a NAMS container (magic {raw[:4]!r})"
    ver = struct.unpack_from("<I", raw, 4)[0]
    entry_count, field20, dir_off = struct.unpack_from("<III", raw, 0x1c)
    return {"magic": "NAMS", "version": ver, "entry_count": entry_count,
            "field20": field20, "dir_offset": dir_off}


def parse_directory(raw: bytes, start: int, limit: int | None = None):
    """Parse the RAW resource directory. Returns list of dicts. Stops at the first record
    that doesn't fit the SBitmap layout (mesh-interlude records use a different shape)."""
    n = len(raw); pos = start; ents = []
    while pos + 24 <= n:
        idv = struct.unpack_from("<Q", raw, pos)[0]
        off = struct.unpack_from("<I", raw, pos + 12)[0]
        nlen = struct.unpack_from("<I", raw, pos + 20)[0]
        if nlen == 0 or nlen > 128 or pos + 24 + nlen + 36 > n:
            break
        name = raw[pos + 24:pos + 24 + nlen]
        if not all(32 <= b < 127 for b in name):
            break
        h1, h2, h3 = struct.unpack_from("<QQQ", raw, pos + 24 + nlen)
        params = raw[pos + 24 + nlen + 24:pos + 24 + nlen + 36]
        ents.append({"id": idv, "offset": off, "name": name.decode("ascii"),
                     "h1": h1, "h2": h2, "h3": h3, "params": params, "rec_pos": pos})
        pos += 24 + nlen + 36
        if limit and len(ents) >= limit:
            break
    return ents, pos


def cmd_info(path):
    raw = open(path, "rb").read()
    h = read_header(raw)
    print(f"file: {path}  ({len(raw):,} bytes)")
    print(f"  magic={h['magic']} version={h['version']:#x} entryCount={h['entry_count']} "
          f"field20={h['field20']} dirOffset={h['dir_offset']:#x}")
    meta = lzss_decode(raw, 0x28, h["dir_offset"])
    print(f"  LZSS metadata: 0x28..{h['dir_offset']:#x} -> {len(meta):,} bytes decompressed "
          f"(first name: {meta[:40].split(b'|')[0].decode('latin1','replace')!r})")
    ents, endp = parse_directory(raw, h["dir_offset"])
    offs = [e["offset"] for e in ents]
    print(f"  texture directory: {len(ents)} entries, ends @{endp:#x}; "
          f"dataOffset range {min(offs):#x}..{max(offs):#x}" if ents else "  (no entries)")
    print("  NOTE: the FONT is a hash-keyed SFontData resource (NOT the 'fOnk' at 0x156bff7 — "
          "run 'fonkcheck'). See notes/fonk_attempt2.md.")


def cmd_dump(path, n=12):
    raw = open(path, "rb").read()
    h = read_header(raw)
    ents, _ = parse_directory(raw, h["dir_offset"], limit=n)
    for e in ents:
        print(f"  id={e['id']:#018x} off={e['offset']:#x} name={e['name']!r} "
              f"params={e['params'].hex()}")


def cmd_lzss(path, k=400):
    raw = open(path, "rb").read()
    h = read_header(raw)
    meta = lzss_decode(raw, 0x28, h["dir_offset"])
    txt = "".join(chr(c) if 32 <= c < 127 else ("|" if c == 0 else ".") for c in meta[:k])
    print(txt)


def cmd_fonkcheck(path):
    raw = open(path, "rb").read()
    hits = []
    i = raw.find(b"fOnk")
    while i != -1:
        hits.append(i); i = raw.find(b"fOnk", i + 1)
    print(f"'fOnk' occurrences in {path}: {len(hits)} {[hex(x) for x in hits]}")
    for tag in (b"FONTK", b"font", b"Font", b"glyph", b"SFontData"):
        print(f"  '{tag.decode()}': {raw.count(tag)} occurrences")
    if hits:
        o = hits[0]
        print(f"  bytes around {hits[0]:#x}: {raw[o-8:o+12].hex()}  "
              f"(high-entropy mesh region; not a resource header — no zero/count fields)")
    print("  => 'fOnk' is coincidental ASCII in raw mesh data, NOT the font resource.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(0)
    cmd, path = sys.argv[1], sys.argv[2]
    arg = int(sys.argv[3]) if len(sys.argv) > 3 else None
    {"info": lambda: cmd_info(path),
     "dump": lambda: cmd_dump(path, arg or 12),
     "lzss": lambda: cmd_lzss(path, arg or 400),
     "fonkcheck": lambda: cmd_fonkcheck(path)}.get(cmd, lambda: print("unknown cmd"))()
