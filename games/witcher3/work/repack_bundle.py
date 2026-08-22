#!/usr/bin/env python3
"""Proper POTATO70 bundle repacker for The Witcher 3 — replace ONE entry with new data of any
size, rewriting the data section (16-byte aligned) + patching every shifted entry's offset +
the bundle header. Eliminates the fragile delta-0 + zero-padded-snappy trick: the new entry can
use pack=1 (standard zlib, same as the game's own fonts_en.redswf) at its natural size.

Entry (320B): name[256] hash[16] u32(0) u32 size u32 zsize u32 offs u32 unk4 u32 unk5 zeros[16]
              u32 unk6 u32 pack.   (hash/unk* are NOT validated at load.)
Header: 'POTATO70' u32 filesize u32 size(=data section) u32 header_sz u32 data_sz str(8).

Usage:  py repack_bundle.py deploy            (David font, pack=1 zlib)
        py repack_bundle.py deploy-orig       (ISOLATION: original redswf, pack=1 — content identical)
        py repack_bundle.py revert
"""
import os, sys, struct, zlib, shutil

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
BAK = BUNDLE + ".he_backup"
HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "fonts_ar.redswf"


def _parse(d):
    filesize, size, header_sz, data_sz = struct.unpack_from("<IIII", d, 8)
    n = header_sz // 320
    ents = []
    for i in range(n):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"i": i, "base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})
    return ents


def extract_target_redswf():
    """Return the (uncompressed) fonts_ar.redswf bytes from the CURRENT bundle."""
    import potato_bundle as P
    d, ents = P.list_entries(BUNDLE)
    e = [x for x in ents if x["name"].endswith(TARGET)][0]
    return P.extract(d, e)


def repack(new_uncompressed, pack=1):
    d = bytearray(open(BUNDLE, "rb").read())
    ents = _parse(d)
    tgt = [e for e in ents if e["name"].endswith(TARGET)][0]
    if pack == 1:
        comp = zlib.compress(bytes(new_uncompressed), 9)
    elif pack == 0:
        comp = bytes(new_uncompressed)
    else:
        raise SystemExit("only pack 0/1 supported by this repacker")

    ents_off = sorted(ents, key=lambda x: x["offs"])
    for e in ents_off:
        if e["i"] == tgt["i"]:
            e["raw"] = comp; e["nz"] = len(comp); e["ns"] = len(new_uncompressed); e["np"] = pack
        else:
            e["raw"] = bytes(d[e["offs"]:e["offs"] + e["zsize"]]); e["nz"] = e["zsize"]; e["ns"] = e["size"]; e["np"] = e["pack"]

    data_start = ents_off[0]["offs"]
    out = bytearray(d[:data_start])          # header + TOC (offsets patched below)
    cur = data_start
    for e in ents_off:
        pad = (-cur) % 16
        out += b"\x00" * pad; cur += pad
        e["no"] = cur
        out += e["raw"]; cur += len(e["raw"])

    for e in ents:                            # patch TOC: size / zsize / offs / pack
        b = e["base"]
        struct.pack_into("<III", out, b + 256 + 16 + 4, e["ns"], e["nz"], e["no"])
        struct.pack_into("<I", out, b + 320 - 4, e["np"])
    # header: filesize (@8) + data-section size (@12)
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<I", out, 12, len(out) - data_start)
    delta = len(out) - len(d)
    print(f"repacked fonts_ar: pack={pack} zsize {tgt['zsize']}->{len(comp)}  bundle {len(d)}->{len(out)} ({delta:+d})")
    return bytes(out)


def deploy(orig=False):
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK); print(f"backed up -> {BAK}")
    if orig:
        payload = extract_target_redswf()      # content-identical isolation test
        print(f"ISOLATION: repacking the ORIGINAL redswf ({len(payload)} B) as pack=1 zlib")
    else:
        payload = open(os.path.join(HERE, "fonts", "fonts_ar_david.redswf"), "rb").read()
        print(f"DAVID: repacking fonts_ar_david.redswf ({len(payload)} B) as pack=1 zlib")
    new = repack(payload, pack=1)
    open(BUNDLE, "wb").write(new)
    # verify our own reader round-trips the new entry
    import importlib, potato_bundle as P; importlib.reload(P)
    d, ents = P.list_entries(BUNDLE); e = [x for x in ents if x["name"].endswith(TARGET)][0]
    back = P.extract(d, e)
    print(f"self-check: entry pack={e['pack']} zsize={e['zsize']} -> decompresses {len(back)} B, matches payload: {back==payload}")
    print("Fully restart the game (Text Language = Arabic).")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted r4gui.bundle from backup")
    else:
        print("no backup found")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "deploy"
    if cmd == "revert":
        revert()
    elif cmd == "deploy-orig":
        deploy(orig=True)
    else:
        deploy(orig=False)
