# -*- coding: utf-8 -*-
"""ADD the 27 Hebrew letters (David) to gfxfontlib.redswf — the SHARED Scaleform font library.

WHY: the Hebrew mod only ever injected David into `fonts_ar.redswf` font id=1 ("Arial"), which had
27 EXISTING Hebrew code slots to overwrite. But `gfxfontlib.redswf` (the shared font provider that
the MENU/MOVIE/CREDITS panels use — they embed NO fonts of their own) has THREE "PF Din Text Cond
Pro" fonts with **zero** Hebrew glyphs. Any Hebrew label rendered through it comes out as tofu
boxes — e.g. the credits "hold Esc to skip" label ("דלג" = 3 letters -> 3 boxes; user-confirmed:
the boxes stay frozen while holding Esc, so they are NOT the hold-progress indicator).

Unlike build_font.py (which REPLACES existing Hebrew slots) this ADDS glyphs:
  * codes/shapes/advance/bounds get 27 new entries INSERTED at the sorted position
    (Hebrew 0x05D0-0x05EA sits BELOW the fonts' max code 0x2122/0x215f, so it cannot be appended).
  * all three fonts are wide_codes=True, so codes > 0xFF are representable as-is.
  * new glyphs get a zero RECT for bounds (a hint only — the shape defines the real extent, same
    reasoning as build_font.py's "leave bounds alone").
  * font id=1 uses 2-byte (narrow) offsets — if the grown shape table would overflow 0xFFFF we
    promote it to wide offsets rather than corrupt the table.

Output: fonts/gfxfontlib_david.redswf. Deploy with deploy_fonts.py (repacks BOTH font swf into
r4gui.bundle). GAME MUST BE CLOSED.
"""
import os, sys, struct, zlib
import potato_bundle as P
import gfx_inspect as G
import swf_font as S
import swf_glyphgen as GG
import build_font as BF
from fontTools.ttLib import TTFont

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
DAVID = r"C:\Windows\Fonts\david.ttf"
SWF_EM = 20480
HEB = list(range(0x05D0, 0x05EA + 1))          # 27 letters
FONT_WIDE_OFFSETS = 0x01                        # DefineFont3 flag bit


def add_hebrew(f, gs, cmap, scale):
    """Insert the Hebrew letters into a parsed DefineFont3 at the sorted code position."""
    if any(0x05D0 <= c <= 0x05EA for c in f["codes"]):
        return 0                                # already has Hebrew
    add = [cp for cp in HEB if cp in cmap]
    if not add:
        return 0
    # sorted insertion point: first index whose code is greater than the last Hebrew cp
    pos = next((i for i, c in enumerate(f["codes"]) if c > add[-1]), len(f["codes"]))
    shapes, advances, bounds = [], [], []
    for cp in add:
        gname = cmap[cp]
        shapes.append(GG.glyph_to_shape(gs, gname, scale, y_sign=-1))
        advances.append(round(gs[gname].width * scale))
        bounds.append(b"\x00")                  # zero RECT (nbits=0) — bounds are a hint only
    f["codes"] = f["codes"][:pos] + add + f["codes"][pos:]
    f["shapes"] = f["shapes"][:pos] + shapes + f["shapes"][pos:]
    if f["has_layout"]:
        L = f["layout"]
        L["advance"] = L["advance"][:pos] + advances + L["advance"][pos:]
        L["bounds"] = L["bounds"][:pos] + bounds + L["bounds"][pos:]
    f["num"] += len(add)

    # narrow (2-byte) offsets can only address 0xFFFF — promote to wide if the table would overflow
    if not f["wide_off"]:
        total = (f["num"] + 1) * 2 + sum(len(s) for s in f["shapes"])
        if total > 0xFFFF:
            f["wide_off"] = True
            f["flags"] |= FONT_WIDE_OFFSETS
            print("      (promoted font to WIDE offsets — shape table > 64 KB)")
    return len(add)


def build():
    d, ents = P.list_entries(BUNDLE)
    e = [x for x in ents if x["name"].endswith("gfxfontlib.redswf")][0]
    redswf = P.extract(d, e)
    orig_len = len(redswf)
    cfx_off = redswf.find(b"CFX")
    assert cfx_off > 0
    cfx_ver = redswf[cfx_off + 3]
    gfx = G.decompress_gfx(redswf)[0]
    cr2w_head = bytearray(redswf[:cfx_off])

    t = TTFont(DAVID)
    scale = SWF_EM / t["head"].unitsPerEm
    gs = t.getGlyphSet(); cmap = t.getBestCmap()

    tags = G.list_tags(gfx)
    new_bodies = {}
    total = 0
    for idx, (code, length, off) in enumerate(tags):
        if code != 75:
            continue
        f = S.parse_definefont3(gfx[off:off + length])
        n = add_hebrew(f, gs, cmap, scale)
        if n:
            body = S.serialize_definefont3(f)
            # VERIFY: re-parse must give back exactly what we built, with the Hebrew present
            chk = S.parse_definefont3(body)
            heb = sum(1 for c in chk["codes"] if 0x05D0 <= c <= 0x05EA)
            assert chk["num"] == f["num"] and heb == n, "re-parse mismatch"
            new_bodies[idx] = body
            total += n
            print(f"  font id={f['font_id']} glyphs {f['num']-n}->{f['num']}  +{n} Hebrew  "
                  f"({length} -> {len(body)} B)  re-parse hebrew={heb} OK")
    if not total:
        raise SystemExit("no font took Hebrew — nothing to do")
    print(f"total Hebrew glyphs ADDED: {total}")

    new_gfx = BF.rebuild_gfx(gfx, new_bodies)
    comp = zlib.compress(new_gfx[8:], 9)
    new_cfx = b"CFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + comp
    region = orig_len - cfx_off
    print(f"  new CFX {len(new_cfx)} B vs region {region} B (headroom {region - len(new_cfx)})")

    # The CFX buffer is the LAST thing in the redswf (only a few trailing bytes follow), so it can
    # GROW: patch the CFX on-disk size at (cfx_off-4) and the CR2W total-length fields at @24/@28.
    old_disk = struct.unpack_from("<I", cr2w_head, cfx_off - 4)[0]
    trailing = redswf[cfx_off + old_disk:]                                # bytes after the CFX blob
    struct.pack_into("<I", cr2w_head, cfx_off - 4, len(new_cfx))          # CFX on-disk size
    out = bytes(cr2w_head) + new_cfx + trailing
    o = bytearray(out)
    struct.pack_into("<I", o, 24, len(out))                               # CR2W total length
    struct.pack_into("<I", o, 28, len(out))
    out = bytes(o)
    print(f"  GROW: cfx_disk {old_disk} -> {len(new_cfx)} | redswf {orig_len} -> {len(out)} "
          f"({len(out)-orig_len:+d}), trailing {len(trailing)} B preserved")

    # final self-check: decompress our own output and confirm the Hebrew is really there
    chk_gfx = G.decompress_gfx(out)[0]
    heb_total = 0
    for code, length, off in G.list_tags(chk_gfx):
        if code == 75:
            f = S.parse_definefont3(chk_gfx[off:off + length])
            heb_total += sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
    print(f"  SELF-CHECK: rebuilt gfxfontlib has {heb_total} Hebrew glyphs across its fonts")
    assert heb_total == total

    os.makedirs(os.path.join(HERE, "fonts"), exist_ok=True)
    dst = os.path.join(HERE, "fonts", "gfxfontlib_david.redswf")
    open(dst, "wb").write(out)
    print(f"built {os.path.basename(dst)}: {len(out)} B (orig {orig_len})")
    return out


TARGET = "gfxfontlib.redswf"
BAK = BUNDLE + ".gfxfont_backup"


def deploy():
    """Contiguous repack of r4gui.bundle replacing ONLY gfxfontlib (pack=1 zlib, its original mode).
    fonts_ar's David injection and every other entry are copied verbatim — pack modes preserved."""
    payload = build()
    if not os.path.exists(BAK):
        import shutil; shutil.copy2(BUNDLE, BAK); print(f"backed up -> {os.path.basename(BAK)}")

    d = bytearray(open(BUNDLE, "rb").read())
    ents = []
    filesize, size, header_sz, data_sz = struct.unpack_from("<IIII", d, 8)
    for i in range(header_sz // 320):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"i": i, "base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})

    comp = zlib.compress(payload, 9)
    ents_off = sorted(ents, key=lambda x: x["offs"])
    data_start = ents_off[0]["offs"]
    out = bytearray(d[:data_start])
    cur = data_start
    for e in ents_off:
        pad = (-cur) % 16
        out += b"\x00" * pad; cur += pad
        if e["name"].endswith(TARGET):
            raw, e["ns"], e["np"] = comp, len(payload), 1          # pack=1 zlib (its original mode)
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

    # verify from the deployed bundle: gfxfontlib has Hebrew, fonts_ar still has its David Hebrew
    dd, ee = P.list_entries(BUNDLE)
    for nm in [TARGET, "fonts_ar.redswf"]:
        ent = [x for x in ee if x["name"].endswith(nm)][0]
        g = G.decompress_gfx(P.extract(dd, ent))[0]
        heb = 0
        for code, length, off in G.list_tags(g):
            if code == 75:
                f = S.parse_definefont3(g[off:off + length])
                heb += sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
        print(f"  verify {nm}: hebrew glyphs = {heb}")
    print("DEPLOYED. Restart the game (Text Language = Arabic).")


def revert():
    import shutil
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted r4gui.bundle from .gfxfont_backup")
    else:
        print("no backup")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        build()
