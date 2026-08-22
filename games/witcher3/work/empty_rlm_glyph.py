#!/usr/bin/env python3
"""Empty the U+200F (RLM) glyph shape in fonts_ar.redswf so the RLM used to anchor the
<heb>-<Latin> hyphen renders INVISIBLY (font 1 ships a visible 43-byte RLM glyph = the
"thin bar" the user saw). advance is already 0; we only blank the shape -> truly zero.
Same delta-0 CR2W/CFX pipeline as build_font.py (CFX shrinks -> always fits).

Usage: py empty_rlm_glyph.py            # edits release/data/fonts/fonts_ar.redswf in place
       py empty_rlm_glyph.py --check    # report only
"""
import os, sys, struct, zlib, shutil
import gfx_inspect as G
import swf_font as S
from build_font import rebuild_gfx

HERE = os.path.dirname(os.path.abspath(__file__))
REDSWF = os.path.join(HERE, "..", "release", "data", "fonts", "fonts_ar.redswf")
EMPTY_SHAPE = b"\x10\x00"          # NumFill=1/NumLine=0 header + end-record = draws nothing
TARGETS = {0x200F}                  # RLM (our hyphen anchor). U+200E not used by our data.


def main(check_only):
    redswf = open(REDSWF, "rb").read()
    orig_len = len(redswf)
    cfx_off = redswf.find(b"CFX")
    assert cfx_off > 0
    cfx_ver = redswf[cfx_off + 3]
    gfx_uncomp = struct.unpack_from("<I", redswf, cfx_off + 4)[0]
    gfx = b"GFX" + bytes([cfx_ver]) + struct.pack("<I", gfx_uncomp) + zlib.decompress(redswf[cfx_off + 8:])
    cr2w_head = bytearray(redswf[:cfx_off])

    tags = G.list_tags(gfx)
    new_bodies = {}
    changed = 0
    for idx, (code, length, off) in enumerate(tags):
        if code != 75:
            continue
        f = S.parse_definefont3(gfx[off:off + length])
        hit = False
        for i, cp in enumerate(f["codes"]):
            if cp in TARGETS and f["shapes"][i] != EMPTY_SHAPE:
                print(f"  font {f['font_id']} {f['name'][:-1].decode()!r}: U+{cp:04X} "
                      f"shape {len(f['shapes'][i])}B -> empty (advance {f['layout']['advance'][i] if f['has_layout'] else '?'})")
                f["shapes"][i] = EMPTY_SHAPE
                if f["has_layout"]:
                    f["layout"]["advance"][i] = 0
                hit = True; changed += 1
        if hit:
            new_bodies[idx] = S.serialize_definefont3(f)
    print(f"glyphs emptied: {changed}")
    if check_only or not changed:
        return

    new_gfx = rebuild_gfx(gfx, new_bodies)
    comp = zlib.compress(new_gfx[8:], 9)
    new_cfx = b"CFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + comp
    region = orig_len - cfx_off
    print(f"  new CFX {len(new_cfx)}B / region {region}B (headroom {region - len(new_cfx)})")
    assert len(new_cfx) <= region, "CFX grew?!"
    struct.pack_into("<I", cr2w_head, cfx_off - 4, len(new_cfx))     # CR2W CFX diskSize
    new_redswf = bytes(cr2w_head) + new_cfx + b"\x00" * (region - len(new_cfx))
    assert len(new_redswf) == orig_len

    # verify the rebuilt font re-parses and the RLM is now empty
    v_gfx = b"GFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + zlib.decompress(new_redswf[cfx_off + 8:])
    for code, length, off in G.list_tags(v_gfx):
        if code == 75:
            vf = S.parse_definefont3(v_gfx[off:off + length])
            if 0x200F in vf["codes"]:
                i = vf["codes"].index(0x200F)
                assert vf["shapes"][i] == EMPTY_SHAPE, "RLM not empty after rebuild"
    print("  verify: rebuilt font re-parses, RLM shape empty ✓")

    shutil.copy2(REDSWF, REDSWF + ".bak.rlm")
    open(REDSWF, "wb").write(new_redswf)
    print(f"WROTE {REDSWF} ({orig_len}B, delta-0)  backup .bak.rlm")


if __name__ == "__main__":
    main("--check" in sys.argv)
