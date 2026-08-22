#!/usr/bin/env python3
"""gfx_analyze.py — parse a GTA V Scaleform GFx (.gfx) movie and report its tags,
ImportAssets (which font library + symbols it imports), ExportAssets (what it exports),
DefineFont/DefineExternalImage tags, and any font/.ytd references.

GFx == SWF-like tag stream after a small header:
    bytes 0..2  signature 'GFX' (uncompressed) / 'CFX' (zlib)  -- here always GFX
    byte  3     version
    u32   file length
    then RECT (frame size) + u16 framerate + u16 framecount, then tags.
Each tag: u16 (tagcode<<6 | len); if len==0x3F a u32 extended length follows.
"""
import struct, sys, os

# Relevant SWF/GFx tag codes
TAGS = {
    0: "End", 6: "DefineBits", 10: "DefineFont", 11: "DefineText",
    13: "DefineFontInfo", 33: "DefineText2", 37: "DefineEditText",
    39: "DefineSprite", 48: "DefineFont2", 56: "ExportAssets",
    57: "ImportAssets", 62: "DefineFontInfo2", 69: "FileAttributes",
    71: "ImportAssets2", 73: "DefineFontAlignZones", 75: "DefineFont3",
    77: "Metadata", 88: "DefineFontName", 91: "DefineFont4",
    # GFx-specific
    1000: "ExporterInfo", 1001: "DefineExternalGradient", 1002: "DefineSubImage",
    1003: "DefineExternalImage", 1004: "FontTextureInfo", 1005: "DefineExternalImage2",
    1006: "DefineGradientMap", 1007: "DefineCompactedFont", 1008: "DefineExternalSound",
    1009: "DefineExternalStreamSound", 1010: "DefineSubImageInfo",
    1011: "FontTextureInfo2", 1012: "Unknown1012",
}


def _read_rect(b, p):
    nbits = b[p] >> 3
    total = 5 + nbits * 4
    return p + (total + 7) // 8


def parse(path):
    b = open(path, "rb").read()
    sig = b[:3]
    ver = b[3]
    flen = struct.unpack_from("<I", b, 4)[0]
    p = 8
    p = _read_rect(b, p)            # frame RECT
    p += 4                          # framerate(u16)+framecount(u16)
    tags = []
    imports = []                    # (url, [symbols])
    exports = []                    # [symbols]
    fonts = []                      # (tagname, fontid, name)
    extimages = []                  # (id, target_w, target_h, export_name)
    strings = []
    while p < len(b) - 1:
        rec = struct.unpack_from("<H", b, p)[0]
        p += 2
        code = rec >> 6
        ln = rec & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", b, p)[0]
            p += 4
        body = b[p:p + ln]
        name = TAGS.get(code, "Tag%d" % code)
        tags.append((code, name, ln))
        if code == 71 or code == 57:   # ImportAssets2 / ImportAssets
            # url (null-term string) [+2 reserved for ImportAssets2] then count + (id,name)*
            e = body.find(b"\x00")
            url = body[:e].decode("latin-1", "replace")
            q = e + 1
            if code == 71:
                q += 2              # reserved byte + version byte
            cnt = struct.unpack_from("<H", body, q)[0]; q += 2
            syms = []
            for _ in range(cnt):
                q += 2             # id
                se = body.find(b"\x00", q)
                syms.append(body[q:se].decode("latin-1", "replace"))
                q = se + 1
            imports.append((url, syms))
        elif code == 56:           # ExportAssets
            cnt = struct.unpack_from("<H", body, 0)[0]; q = 2
            for _ in range(cnt):
                q += 2
                se = body.find(b"\x00", q)
                exports.append(body[q:se].decode("latin-1", "replace"))
                q = se + 1
        elif code in (10, 48, 75, 91):  # DefineFont*
            fid = struct.unpack_from("<H", body, 0)[0] if len(body) >= 2 else -1
            fonts.append((name, fid))
        elif code in (1003, 1005):  # DefineExternalImage(2)
            extimages.append((name, ln, body[:64]))
        p += ln
        if code == 0:
            break
    return dict(sig=sig, ver=ver, flen=flen, size=len(b), tags=tags,
                imports=imports, exports=exports, fonts=fonts, extimages=extimages)


def summary(path):
    d = parse(path)
    from collections import Counter
    tc = Counter(t[1] for t in d["tags"])
    print(f"\n=== {os.path.basename(path)} ({d['size']}B, sig={d['sig']}, ver={d['ver']}) ===")
    print("  tags:", dict(tc))
    if d["fonts"]:
        print("  DEFINES FONTS:", d["fonts"])
    if d["exports"]:
        print("  EXPORTS:", d["exports"][:20])
    if d["imports"]:
        for url, syms in d["imports"]:
            print(f"  IMPORTS from '{url}': {syms[:20]}")
    if d["extimages"]:
        print(f"  EXTERNAL IMAGES (atlas): {len(d['extimages'])} x DefineExternalImage")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        try:
            summary(a)
        except Exception as e:
            print(f"\n!! {a}: {type(e).__name__}: {e}")
