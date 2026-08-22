# -*- coding: utf-8 -*-
"""Add the 27 Hebrew letters (David) to EVERY font in fonts_ar.redswf that still lacks them.

ROOT CAUSE of the "3 orange boxes" (user-confirmed: English shows "Escape | Skip", Hebrew shows
"Esc ▮▮▮" = "דלג" tofu'd):  fonts_ar.redswf holds THREE DefineFont3 fonts and the original mod
(build_font.py) only ever touched **id=1 "Arial"** — because that was the only font with EXISTING
Hebrew code slots to overwrite. The other two ship with ZERO Hebrew:
    id=1  Arial                 2138 glyphs   27 Hebrew (David)  <- body text renders through this
    id=4  Arial                  610 glyphs    0 Hebrew          <- tofu
    id=6  PF Din Text Cond Pro   382 glyphs    0 Hebrew          <- tofu (the orange prompt labels)
So any UI element whose text style resolves to id=4/id=6 renders Hebrew as boxes, while the credits
body (id=1) renders fine — exactly the split we observed.

This ADDS glyphs (insert at the sorted code position; Hebrew 0x05D0-0x05EA sits BELOW the fonts'
max code, so it cannot be appended) and grows the CFX buffer, patching the CR2W size fields.
Reuses the machinery proven in inject_gfxfontlib.py.

Usage:  py inject_fonts_all.py            # build + report only
        py inject_fonts_all.py --deploy   # repack into r4gui.bundle (GAME MUST BE CLOSED)
        py inject_fonts_all.py --revert
"""
import os, sys, struct, zlib, shutil
import potato_bundle as P
import gfx_inspect as G
import swf_font as S
import build_font as BF
from inject_gfxfontlib import add_hebrew
from fontTools.ttLib import TTFont

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
BAK = BUNDLE + ".allfont_backup"
HERE = os.path.dirname(os.path.abspath(__file__))
DAVID = r"C:\Windows\Fonts\david.ttf"
SWF_EM = 20480
TARGET = "fonts_ar.redswf"


def build_redswf():
    d, ents = P.list_entries(BUNDLE)
    e = [x for x in ents if x["name"].endswith(TARGET)][0]
    redswf = P.extract(d, e)
    orig_len = len(redswf)
    cfx_off = redswf.find(b"CFX")
    cfx_ver = redswf[cfx_off + 3]
    gfx = G.decompress_gfx(redswf)[0]
    cr2w_head = bytearray(redswf[:cfx_off])

    t = TTFont(DAVID)
    scale = SWF_EM / t["head"].unitsPerEm
    gs = t.getGlyphSet(); cmap = t.getBestCmap()

    new_bodies = {}
    total = 0
    for idx, (code, length, off) in enumerate(G.list_tags(gfx)):
        if code != 75:
            continue
        f = S.parse_definefont3(gfx[off:off + length])
        before = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
        n = add_hebrew(f, gs, cmap, scale)          # no-op when the font already has Hebrew
        nm = f["name"][:-1].decode("latin1", "replace")
        if n:
            body = S.serialize_definefont3(f)
            chk = S.parse_definefont3(body)
            heb = sum(1 for c in chk["codes"] if 0x05D0 <= c <= 0x05EA)
            assert chk["num"] == f["num"] and heb == n
            new_bodies[idx] = body
            total += n
            print(f"  id={f['font_id']:>2} {nm:<24} +{n} Hebrew ADDED  (glyphs {f['num']-n}->{f['num']})")
        else:
            print(f"  id={f['font_id']:>2} {nm:<24} already has {before} Hebrew — untouched")
    if not total:
        raise SystemExit("every font already has Hebrew — nothing to do")

    new_gfx = BF.rebuild_gfx(gfx, new_bodies)
    comp = zlib.compress(new_gfx[8:], 9)
    new_cfx = b"CFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + comp
    old_disk = struct.unpack_from("<I", cr2w_head, cfx_off - 4)[0]
    trailing = redswf[cfx_off + old_disk:]
    struct.pack_into("<I", cr2w_head, cfx_off - 4, len(new_cfx))
    out = bytearray(bytes(cr2w_head) + new_cfx + trailing)
    struct.pack_into("<I", out, 24, len(out))
    struct.pack_into("<I", out, 28, len(out))
    out = bytes(out)
    print(f"  redswf {orig_len} -> {len(out)} ({len(out)-orig_len:+d})  cfx {old_disk} -> {len(new_cfx)}")

    # self-check on our own output
    chk_gfx = G.decompress_gfx(out)[0]
    per = []
    for code, length, off in G.list_tags(chk_gfx):
        if code == 75:
            f = S.parse_definefont3(chk_gfx[off:off + length])
            per.append((f["font_id"], sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)))
    print(f"  SELF-CHECK Hebrew per font: {per}")
    assert all(h >= 27 for _, h in per), "a font still lacks Hebrew"
    return out


def deploy():
    payload = build_redswf()
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK); print(f"backed up -> {os.path.basename(BAK)}")
    d = bytearray(open(BUNDLE, "rb").read())
    filesize, size, header_sz, data_sz = struct.unpack_from("<IIII", d, 8)
    ents = []
    for i in range(header_sz // 320):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})
    comp = zlib.compress(payload, 9)
    ents_off = sorted(ents, key=lambda x: x["offs"])
    data_start = ents_off[0]["offs"]
    out = bytearray(d[:data_start]); cur = data_start
    for e in ents_off:
        pad = (-cur) % 16
        out += b"\x00" * pad; cur += pad
        if e["name"].endswith(TARGET):
            raw, e["ns"], e["np"] = comp, len(payload), 1
        else:
            raw, e["ns"], e["np"] = bytes(d[e["offs"]:e["offs"] + e["zsize"]]), e["size"], e["pack"]
        e["no"], e["nz"] = cur, len(raw)
        out += raw; cur += len(raw)
    for e in ents:
        b = e["base"]
        struct.pack_into("<III", out, b + 256 + 16 + 4, e["ns"], e["nz"], e["no"])
        struct.pack_into("<I", out, b + 320 - 4, e["np"])
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<I", out, 12, len(out) - data_start)
    open(BUNDLE, "wb").write(bytes(out))
    print(f"r4gui.bundle {len(d)} -> {len(out)} ({len(out)-len(d):+d})")

    dd, ee = P.list_entries(BUNDLE)
    for nm in [TARGET, "gfxfontlib.redswf"]:
        ent = [x for x in ee if x["name"].endswith(nm)][0]
        g = G.decompress_gfx(P.extract(dd, ent))[0]
        per = []
        for code, length, off in G.list_tags(g):
            if code == 75:
                f = S.parse_definefont3(g[off:off + length])
                per.append((f["font_id"], sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)))
        print(f"  verify {nm}: {per}")
    print("DEPLOYED. Restart the game.")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted r4gui.bundle from .allfont_backup")
    else:
        print("no backup")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        build_redswf()
