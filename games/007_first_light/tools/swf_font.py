#!/usr/bin/env python3
"""SWF/GFx DefineFont3 codec for TW3 fonts_ar.redswf — parse + serialize, keeping each glyph's
shape as RAW bytes (so kept glyphs are byte-identical). Only glyphs we replace get new shapes.
Ref: SWF file format spec (DefineFont3 tag = 75)."""
import struct

FONT_HAS_LAYOUT = 0x80
FONT_WIDE_OFFSETS = 0x08
FONT_WIDE_CODES = 0x04


class BitReader:
    def __init__(self, data, pos=0):
        self.d = data; self.byte = pos; self.bit = 0

    def align(self):
        if self.bit:
            self.bit = 0; self.byte += 1

    def u(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.byte] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit = 0; self.byte += 1
        return v

    def s(self, n):
        v = self.u(n)
        if n and (v >> (n - 1)):
            v -= (1 << n)
        return v


def parse_definefont3(body):
    """body = the DefineFont3 tag payload (without the record header)."""
    p = 0
    font_id = struct.unpack_from("<H", body, p)[0]; p += 2
    flags = body[p]; p += 1
    lang = body[p]; p += 1
    name_len = body[p]; p += 1
    name = body[p:p + name_len]; p += name_len
    num = struct.unpack_from("<H", body, p)[0]; p += 2
    wide_off = bool(flags & FONT_WIDE_OFFSETS)
    wide_codes = bool(flags & FONT_WIDE_CODES)
    has_layout = bool(flags & FONT_HAS_LAYOUT)
    off_start = p
    osz = 4 if wide_off else 2
    ofmt = "<I" if wide_off else "<H"
    offsets = [struct.unpack_from(ofmt, body, off_start + i * osz)[0] for i in range(num)]
    code_table_offset = struct.unpack_from(ofmt, body, off_start + num * osz)[0]
    # glyph shapes are raw byte slices, offsets measured from off_start
    shapes = []
    for i in range(num):
        s0 = off_start + offsets[i]
        s1 = off_start + (offsets[i + 1] if i + 1 < num else code_table_offset)
        shapes.append(body[s0:s1])
    p = off_start + code_table_offset
    cfmt = "<H" if wide_codes else "B"
    csz = 2 if wide_codes else 1
    codes = [struct.unpack_from(cfmt, body, p + i * csz)[0] for i in range(num)]
    p += num * csz
    layout = None
    if has_layout:
        ascent, descent, leading = struct.unpack_from("<hhh", body, p); p += 6
        advance = list(struct.unpack_from("<%dh" % num, body, p)); p += 2 * num
        # bounds: NumGlyphs RECTs (variable bit length) — read via BitReader, keep raw span
        bounds = []
        br = BitReader(body, p)
        for _ in range(num):
            start_byte = br.byte; start_bit = br.bit
            nb = br.u(5)
            br.u(nb * 4)  # xmin xmax ymin ymax
            br.align()
            bounds.append(body[start_byte:br.byte])
        p = br.byte
        kern_count = struct.unpack_from("<H", body, p)[0]; p += 2
        kern_raw = body[p:p + kern_count * 6]  # DefineFont3 kerning record = 2+2+2 (wide codes)
        p += kern_count * 6
        layout = {"ascent": ascent, "descent": descent, "leading": leading,
                  "advance": advance, "bounds": bounds, "kern_count": kern_count, "kern_raw": kern_raw}
    return {"font_id": font_id, "flags": flags, "lang": lang, "name": name, "num": num,
            "wide_off": wide_off, "wide_codes": wide_codes, "has_layout": has_layout,
            "codes": codes, "shapes": shapes, "layout": layout, "consumed": p}


def serialize_definefont3(f):
    out = bytearray()
    out += struct.pack("<H", f["font_id"])
    out += bytes([f["flags"], f["lang"], len(f["name"])])
    out += f["name"]
    num = f["num"]
    out += struct.pack("<H", num)
    osz = 4 if f["wide_off"] else 2
    ofmt = "<I" if f["wide_off"] else "<H"
    # offset table = num offsets + 1 code-table offset; offsets measured from start of offset table
    table_bytes = (num + 1) * osz
    offsets = []
    cur = table_bytes
    for sh in f["shapes"]:
        offsets.append(cur); cur += len(sh)
    code_table_offset = cur
    for o in offsets:
        out += struct.pack(ofmt, o)
    out += struct.pack(ofmt, code_table_offset)
    for sh in f["shapes"]:
        out += sh
    cfmt = "<H" if f["wide_codes"] else "B"
    for c in f["codes"]:
        out += struct.pack(cfmt, c)
    if f["has_layout"]:
        L = f["layout"]
        out += struct.pack("<hhh", L["ascent"], L["descent"], L["leading"])
        out += struct.pack("<%dh" % num, *L["advance"])
        for b in L["bounds"]:
            out += b
        out += struct.pack("<H", L["kern_count"])
        out += L["kern_raw"]
    return bytes(out)


if __name__ == "__main__":
    import sys, gfx_inspect as G
    data = open(sys.argv[1] if len(sys.argv) > 1 else "fonts/fonts_ar.redswf", "rb").read()
    gfx, ver, uncomp = G.decompress_gfx(data)
    tags = G.list_tags(gfx)
    ok_all = True
    for code, length, off in tags:
        if code == 75:  # DefineFont3
            body = gfx[off:off + length]
            f = parse_definefont3(body)
            re = serialize_definefont3(f)
            match = (re == body)
            ok_all &= match
            print(f"  font id={f['font_id']} name={f['name'][:-1].decode()!r} glyphs={f['num']} "
                  f"layout={f['has_layout']} consumed={f['consumed']}/{length} roundtrip={'OK' if match else 'DIFF'}")
    print("ALL ROUNDTRIP OK" if ok_all else "SOME DIFFER")
