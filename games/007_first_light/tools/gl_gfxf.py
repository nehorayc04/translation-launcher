"""
gl_gfxf.py — inject Hebrew glyphs into a 007 First Light Scaleform GFXF font
(BIN1 wrapper + GFx v14/v15, DefineFont3 vector glyphs). Read side + Hebrew ADD.

BIN1 wrapper (verified across all GFXF):
  0   char[4] "BIN1"
  4   u32     version (00 08 01 00)
  8   u32 BE  = (len(prefix)-16) + len(gfx)   [= 68 + gfx_len = size_final - 56]
  12  u32     (0)
  16  u32 LE  = 68 (bytes from offset 16 to the GFx start => GFx at 84)
  84  GFx:    "GFX" + u8 ver + u32 fileLength(LE) + RECT + framerate/count + SWF tags
  +   40-byte trailer after the GFx

The DefineFont3 tags (code 75) are standard SWF vector fonts (0 texture refs). We ADD the
27 Hebrew letters U+05D0..05EA as new glyphs, keeping the CodeTable ascending-sorted (Scaleform
binary-searches it), and re-serialize. Reuses swf_font (DefineFont3 codec) + swf_glyphgen (TTF
-> SWF shape). Wrapper sizes (BIN1 @8, GFx fileLength) are patched to the new lengths.
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import swf_font as SF
import swf_glyphgen as GG

SWF_EM = 20480
HEB_LO, HEB_HI = 0x05D0, 0x05EA   # 27 Hebrew letters aleph..tav
GFX_MAGIC = b"GFX"


# ---------- BIN1 wrapper ----------
def unwrap(gfxf: bytes):
    goff = gfxf.find(GFX_MAGIC)
    if goff < 0:
        raise ValueError("no GFx inside GFXF")
    gfx_len = struct.unpack_from("<I", gfxf, goff + 4)[0]
    prefix = gfxf[:goff]
    gfx = gfxf[goff:goff + gfx_len]
    trailer = gfxf[goff + gfx_len:]
    return bytearray(prefix), gfx, trailer


def rewrap(prefix: bytearray, gfx: bytes, trailer: bytes) -> bytes:
    prefix = bytearray(prefix)
    struct.pack_into(">I", prefix, 8, (len(prefix) - 16) + len(gfx))  # BIN1 @8 (big-endian)
    return bytes(prefix) + gfx + trailer


# ---------- GFx tag stream ----------
def scan_tags(gfx: bytes):
    p = 8
    nbits = gfx[p] >> 3
    p += (5 + nbits * 4 + 7) // 8
    p += 4                              # framerate(2) + framecount(2)
    tags = []
    while p < len(gfx):
        if p + 2 > len(gfx):
            break
        hdr_start = p
        code_len = struct.unpack_from("<H", gfx, p)[0]; p += 2
        code = code_len >> 6
        length = code_len & 0x3F
        long_form = (length == 0x3F)
        if long_form:
            length = struct.unpack_from("<I", gfx, p)[0]; p += 4
        tags.append({"code": code, "length": length, "off": p,
                     "hdr_start": hdr_start, "long_form": long_form})
        if code == 0:
            break
        p += length
    return tags, p


def rebuild_gfx(gfx: bytes, new_bodies: dict) -> bytes:
    tags, end_of_tags = scan_tags(gfx)
    header_end = tags[0]["hdr_start"] if tags else 8
    out = bytearray(gfx[:header_end])
    delta = 0
    for idx, t in enumerate(tags):
        if idx in new_bodies:
            body = new_bodies[idx]
            delta += len(body) - t["length"]
            code = t["code"]
            if t["long_form"] or len(body) >= 0x3F:
                out += struct.pack("<H", (code << 6) | 0x3F)
                out += struct.pack("<I", len(body))
            else:
                out += struct.pack("<H", (code << 6) | len(body))
            out += body
        else:
            out += gfx[t["hdr_start"]:t["off"] + t["length"]]
    out += gfx[end_of_tags:]
    orig_len = struct.unpack_from("<I", gfx, 4)[0]
    struct.pack_into("<I", out, 4, orig_len + delta)   # GFx fileLength stays consistent
    return bytes(out)


# ---------- Hebrew glyph ADD ----------
def add_hebrew_to_font(font: dict, glyphset, cmap: dict, scale: float) -> int:
    """Add U+05D0..05EA as new glyphs, keeping the parallel arrays ascending-sorted by codepoint.
    Returns the number of glyphs added. Skips codepoints already present."""
    present = set(font["codes"])
    has_layout = font["has_layout"]
    adv0 = font["layout"]["advance"] if has_layout else [0] * font["num"]
    bnd0 = font["layout"]["bounds"] if has_layout else [b""] * font["num"]
    # a default bounds bit-span to reuse for new glyphs (hint RECT only; shape defines extent)
    default_bounds = next((b for b in bnd0 if b), b"\x00")
    entries = list(zip(font["codes"], font["shapes"], adv0, bnd0))
    added = 0
    for cp in range(HEB_LO, HEB_HI + 1):
        if cp in present or cp not in cmap:
            continue
        gname = cmap[cp]
        shape = GG.glyph_to_shape(glyphset, gname, scale, y_sign=-1)
        adv = round(glyphset[gname].width * scale)
        entries.append((cp, shape, adv, default_bounds))
        added += 1
    if not added:
        return 0
    entries.sort(key=lambda e: e[0])          # CodeTable ascending
    font["codes"] = [e[0] for e in entries]
    font["shapes"] = [e[1] for e in entries]
    font["num"] = len(entries)
    if has_layout:
        font["layout"]["advance"] = [e[2] for e in entries]
        font["layout"]["bounds"] = [e[3] for e in entries]
    # if any Hebrew codepoint needs wide codes (>255) ensure the flag is set (0x5D0 > 255)
    if max(font["codes"]) > 0xFF and not font["wide_codes"]:
        font["wide_codes"] = True
        font["flags"] |= SF.FONT_WIDE_CODES
    return added


def inject_hebrew(gfxf: bytes, ttf_path: str, only_names=None):
    """Return (new_gfxf_bytes, report). Adds Hebrew to every DefineFont3 that has a code table.
    only_names: optional iterable of substrings; if given, ONLY fonts whose name contains one of
    them are injected (case-insensitive)."""
    from fontTools.ttLib import TTFont
    tt = TTFont(ttf_path)
    upm = tt["head"].unitsPerEm
    scale = SWF_EM / upm
    cmap = tt.getBestCmap()
    glyphset = tt.getGlyphSet()
    filt = [s.lower() for s in only_names] if only_names else None

    prefix, gfx, trailer = unwrap(gfxf)
    tags, _ = scan_tags(gfx)
    new_bodies = {}
    report = []
    for idx, t in enumerate(tags):
        if t["code"] != 75:              # DefineFont3
            continue
        body = gfx[t["off"]:t["off"] + t["length"]]
        font = SF.parse_definefont3(body)
        nm = font["name"][:-1].decode("latin1", "replace")
        if filt and not any(s in nm.lower() for s in filt):
            continue
        n = add_hebrew_to_font(font, glyphset, cmap, scale)
        if n:
            new_bodies[idx] = SF.serialize_definefont3(font)
            report.append((font["font_id"], nm, n))
    new_gfx = rebuild_gfx(gfx, new_bodies)
    return rewrap(prefix, new_gfx, trailer), report


# ---------- CLI / selftest ----------
def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["identity", "fonts", "inject"])
    ap.add_argument("rpkg")
    ap.add_argument("--hash", default="")
    ap.add_argument("--ttf", default="")
    a = ap.parse_args()
    from gl_rpkg import RPKG
    r = RPKG(a.rpkg)
    gfxf_idxs = sorted(r.indices("GFXF"), key=lambda i: r.resources[i].size_final)

    if a.cmd == "identity":
        # wrapper + DefineFont3 parse/serialize round-trip on every GFXF
        wrap_ok = fonts_ok = fonts_total = 0
        for i in gfxf_idxs:
            d = r.read(i)
            prefix, gfx, trailer = unwrap(d)
            if rewrap(prefix, gfx, trailer) == d:
                wrap_ok += 1
            tags, _ = scan_tags(gfx)
            for t in tags:
                if t["code"] == 75:
                    fonts_total += 1
                    body = gfx[t["off"]:t["off"] + t["length"]]
                    f = SF.parse_definefont3(body)
                    if SF.serialize_definefont3(f) == body:
                        fonts_ok += 1
        print(f"GFXF wrapper round-trip: {wrap_ok}/{len(gfxf_idxs)} byte-identical")
        print(f"DefineFont3 parse/serialize: {fonts_ok}/{fonts_total} byte-identical")
    elif a.cmd == "fonts":
        for i in gfxf_idxs:
            d = r.read(i); res = r.resources[i]
            _, gfx, _ = unwrap(d)
            tags, _ = scan_tags(gfx)
            for t in tags:
                if t["code"] == 75:
                    f = SF.parse_definefont3(gfx[t["off"]:t["off"] + t["length"]])
                    heb = sum(1 for c in f["codes"] if HEB_LO <= c <= HEB_HI)
                    cyr = sum(1 for c in f["codes"] if 0x400 <= c <= 0x4FF)
                    lat = sum(1 for c in f["codes"] if 0x20 <= c <= 0x17F)
                    print(f"  {res.hex()} font id={f['font_id']:>4} "
                          f"name={f['name'][:-1].decode('latin1','replace')!r:24} "
                          f"glyphs={f['num']:>5} lat={lat} cyr={cyr} heb={heb} "
                          f"wide_codes={f['wide_codes']}")
    elif a.cmd == "inject":
        i = r._by_hash[int(a.hash, 16)]
        d = r.read(i)
        new, report = inject_hebrew(d, a.ttf)
        out = f"C:/tmp/{r.resources[i].hex()}.hebrew.GFXF"
        open(out, "wb").write(new)
        print(f"injected -> {out} ({len(d)} -> {len(new)} bytes)")
        for fid, name, n in report:
            print(f"   font {fid} {name!r}: +{n} Hebrew glyphs")
        # re-parse to confirm structural validity
        prefix, gfx, trailer = unwrap(new)
        tags, _ = scan_tags(gfx)
        ok = 0
        for t in tags:
            if t["code"] == 75:
                f = SF.parse_definefont3(gfx[t["off"]:t["off"] + t["length"]])
                heb = sum(1 for c in f["codes"] if HEB_LO <= c <= HEB_HI)
                ok += (f["consumed"] == t["length"] and heb > 0)
        print(f"   re-parse OK fonts with Hebrew: {ok}")


if __name__ == "__main__":
    _cli()
