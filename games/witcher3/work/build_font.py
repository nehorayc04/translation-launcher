#!/usr/bin/env python3
"""Build a Hebrew-in-David fonts_ar.redswf for The Witcher 3.
Pipeline: bundle(snappy) -> CR2W -> CFX(zlib) -> GFx -> replace Hebrew glyphs (Arial->David)
in the DefineFont3 tags -> repack GFx -> CFX(zlib) -> CR2W -> loose Mods override.
"""
import os, sys, struct, zlib
import potato_bundle as P
import gfx_inspect as G
import swf_font as S
import swf_glyphgen as GG
from fontTools.ttLib import TTFont

GAME = r"D:\Games\The Witcher 3 - Complete Edition"
HERE = os.path.dirname(os.path.abspath(__file__))
DAVID = r"C:\Windows\Fonts\david.ttf"
SWF_EM = 20480
HEB_LO, HEB_HI = 0x0590, 0x05FF


def _scan_tags(gfx):
    """Like G.list_tags but ALSO records each tag's header start + long/short form, so an
    unchanged tag can be copied byte-for-byte (some tags use the LONG 6-byte header even when
    length < 0x3F — re-emitting them short desyncs the stream)."""
    p = 8
    nbits = gfx[p] >> 3
    p += (5 + nbits * 4 + 7) // 8
    p += 4
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
    return tags, p   # p = end of the End tag (start of any trailing padding)


def rebuild_gfx(gfx, new_bodies):
    """new_bodies: {tag_index: new_body_bytes}. LOSSLESS reassembly: unchanged tags are copied
    verbatim (original header framing preserved); only changed tags get a re-emitted header
    (keeping the original long/short form). The trailing padding after End is preserved, and
    fileLength (offset 4) is bumped by the net body-size delta so it stays consistent."""
    tags, end_of_tags = _scan_tags(gfx)
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
            out += gfx[t["hdr_start"]:t["off"] + t["length"]]   # header+body verbatim
    out += gfx[end_of_tags:]                                    # trailing padding, verbatim
    orig_len = struct.unpack_from("<I", gfx, 4)[0]
    struct.pack_into("<I", out, 4, orig_len + delta)            # keep fileLength consistent
    return bytes(out)


def replace_hebrew(font, david_ts, david_gs, david_cmap, scale):
    n = 0
    for i, cp in enumerate(font["codes"]):
        if HEB_LO <= cp <= HEB_HI and cp in david_cmap:
            gname = david_cmap[cp]
            font["shapes"][i] = GG.glyph_to_shape(david_gs, gname, scale, y_sign=-1)
            if font["has_layout"]:
                adv = david_gs[gname].width
                font["layout"]["advance"][i] = round(adv * scale)
                # LEAVE the original per-glyph bounds bytes untouched — they're just a hint RECT
                # (the shape defines the real extent), and re-encoding a fixed-length RECT risks
                # desyncing Scaleform's bounds reader. Only shape + advance change.
            n += 1
    return n


def build(deploy=False):
    # 1. extract fonts_ar.redswf (snappy) from the bundle
    bundle = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
    d, ents = P.list_entries(bundle)
    e = [x for x in ents if x["name"].endswith("fonts_ar.redswf")][0]
    redswf = P.extract(d, e)
    orig_len = len(redswf)

    # 2. CR2W -> CFX(zlib) -> GFx
    cfx_off = redswf.find(b"CFX")
    assert cfx_off > 0
    cfx_ver = redswf[cfx_off + 3]
    gfx_uncomp = struct.unpack_from("<I", redswf, cfx_off + 4)[0]
    gfx = b"GFX" + bytes([cfx_ver]) + struct.pack("<I", gfx_uncomp) + zlib.decompress(redswf[cfx_off + 8:])
    cr2w_head = redswf[:cfx_off]           # everything before CFX (CR2W header+tables)

    # 3. replace Hebrew glyphs in every DefineFont3 that has Hebrew
    t = TTFont(DAVID)
    scale = SWF_EM / t["head"].unitsPerEm
    gs = t.getGlyphSet(); cmap = t.getBestCmap()
    tags = G.list_tags(gfx)
    new_bodies = {}
    total = 0
    for idx, (code, length, off) in enumerate(tags):
        if code == 75:
            f = S.parse_definefont3(gfx[off:off + length])
            n = replace_hebrew(f, t, gs, cmap, scale)
            if n:
                new_bodies[idx] = S.serialize_definefont3(f)
                total += n
                print(f"  font id={f['font_id']} name={f['name'][:-1].decode()!r}: replaced {n} Hebrew glyphs "
                      f"({length} -> {len(new_bodies[idx])} bytes)")
    print(f"total Hebrew glyphs replaced: {total}")

    # 4. rebuild GFx
    new_gfx = rebuild_gfx(gfx, new_bodies)

    # 5. GFx -> CFX(zlib), then DELTA-0 splice: pad to the exact original region length so the
    #    total redswf size (in the CR2W header @24/@28) stays byte-identical.
    comp = zlib.compress(new_gfx[8:], 9)
    new_cfx = b"CFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + comp
    region = orig_len - cfx_off
    print(f"  new CFX = {len(new_cfx)} bytes; original region = {region} bytes "
          f"(headroom {region - len(new_cfx)})")
    if len(new_cfx) > region:
        raise SystemExit(f"CFX too big by {len(new_cfx)-region} bytes — need CR2W field repack (not delta-0)")
    # ⚠ CRITICAL: the CR2W embedded-buffer table stores the CFX buffer's on-disk (compressed) size
    #   as a u32 at offset (cfx_off - 4). delta-0 pads the region but the CFX CONTENT/size changed,
    #   so this field MUST be updated to the new CFX length or the CR2W loader reads the wrong
    #   buffer extent -> corrupt GFx -> Scaleform crash. (The uncompressed GFx size lives in the CFX
    #   header @cfx_off+4, already set above. No CFX CRC is stored in this CR2W.)
    cr2w_head = bytearray(cr2w_head)
    disk_off = cfx_off - 4
    old_disk = struct.unpack_from("<I", cr2w_head, disk_off)[0]
    struct.pack_into("<I", cr2w_head, disk_off, len(new_cfx))
    print(f"  patched CR2W CFX diskSize @{disk_off}: {old_disk} -> {len(new_cfx)}")
    new_redswf = bytes(cr2w_head) + new_cfx + b"\x00" * (region - len(new_cfx))
    assert len(new_redswf) == orig_len

    outdir = os.path.join(HERE, "fonts")
    open(os.path.join(outdir, "fonts_ar_david.redswf"), "wb").write(new_redswf)
    print(f"built fonts_ar_david.redswf: {len(new_redswf)} bytes (orig {orig_len})")

    if deploy:
        dest = os.path.join(GAME, "Mods", "modHebrewFont", "content",
                            "gameplay", "gui_new", "swf", "witcher3")
        os.makedirs(dest, exist_ok=True)
        open(os.path.join(dest, "fonts_ar.redswf"), "wb").write(new_redswf)
        print(f"DEPLOYED -> {dest}\\fonts_ar.redswf")
    return new_redswf


if __name__ == "__main__":
    build(deploy="--deploy" in sys.argv)
